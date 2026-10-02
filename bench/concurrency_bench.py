#!/usr/bin/env python3
"""Multi-agent concurrency: one llama-server with `-np N` parallel slots, N concurrent
streaming chat requests. Reuses depth_bench.py's corpus/prompt builder, Monitor (fdinfo
VRAM/GTT/evicted + thermal abort), SSE transport, and the IA_BENCH_INHIBITED + --inhibitor-ok
guard.

Smoke (no GPU, no server): `python concurrency_bench.py --smoke`
Run: `systemd-inhibit --what=sleep:idle --mode=block --why='concurrency bench' env
IA_BENCH_INHIBITED=1 python concurrency_bench.py --run --inhibitor-ok --slots 2 --depth 32000`

Configure via environment variables: BENCH_SERVER, BENCH_MODEL, BENCH_WIKI, BENCH_OUT (see
depth_bench.py).
"""
import argparse
import concurrent.futures
import json
import os
import re
import signal
import subprocess
import time

import depth_bench as b

BASE_HARDCODED = {"-m", "--port", "-c", "-ctk", "-ctv", "-fa", "-np", "--ctx-checkpoints",
                   "-ngl", "--temp", "--top-k", "--min-p"}
MIB = 1024 * 1024


def rotate_wiki(wiki, slot):
    """Rotates the shared corpus so each slot's synthetic prompt has distinct-enough content
    (still built with depth_bench's own build_prompt) instead of every slot sending an
    identical request."""
    if not slot or not wiki:
        return wiki
    cut = (slot * 500_000) % len(wiki)
    return wiki[cut:] + wiki[:cut]


def fire_slot(slot, depth, wiki, out_tokens, case_dir, monitor):
    """Builds one slot's synthetic prompt at `depth` tokens and streams a completion for it.
    Meant to run inside a thread per slot so all slots hit the server concurrently."""
    ids, _, _ = b.build_prompt(rotate_wiki(wiki, slot), depth)
    payload = {"prompt": ids, "n_predict": out_tokens, "temperature": 1, "top_k": 20, "min_p": 0,
               "seed": 900 + slot, "stream": True, "return_progress": True, "cache_prompt": False,
               "ignore_eos": True, "timings_per_token": True}
    (case_dir / f"slot-{slot}-request.json").write_text(json.dumps(payload) + "\n")
    started = time.monotonic()
    response, content = b.stream_completion(payload, case_dir / f"slot-{slot}.sse", monitor)
    elapsed = time.monotonic() - started
    t = (response or {}).get("timings", {})
    return {"slot": slot, "depth_requested": depth, "input_tokens": len(ids), "wall_s": elapsed,
            "timings": t, "predicted_per_second": t.get("predicted_per_second"),
            "prompt_per_second": t.get("prompt_per_second"),
            "draft_n_accepted": t.get("draft_n_accepted"), "draft_n": t.get("draft_n"),
            "predicted_n": t.get("predicted_n"), "prompt_n": t.get("prompt_n"),
            "stop_type": (response or {}).get("stop_type"),
            "truncated": bool((response or {}).get("truncated")), "content_chars": len(content)}


def required_help_flags(args):
    """Returns the llama-server --help flags this run's argv actually depends on: the always-on
    base flags plus --kv-unified/--no-kv-unified, --kv-unified-per-slot and the MTP spec flags
    only when the run actually requests them, so the preflight never refuses a build that lacks
    an optional flag this configuration never passes."""
    required = ["-np", "-fa", "-ctk", "-ctv"]
    if args.kv_unified is not None:
        required.append("--kv-unified" if args.kv_unified else "--no-kv-unified")
    if args.kv_unified_per_slot:
        required.append("--kv-unified-per-slot")
    if args.mtp:
        required += ["--spec-type", "--spec-draft-n-max"]
    return required


def missing_help_flags(help_text, required):
    """Returns the subset of `required` flags that don't appear in `help_text` as a whole token
    (bounded by start/end of line, whitespace, or a comma), so a short flag like -fa or -np can't
    false-positive-match as a substring of an unrelated longer token in the help output."""
    return [flag for flag in required
            if not re.search(r"(?:^|[\s,])" + re.escape(flag) + r"(?:[\s,]|$)", help_text, re.MULTILINE)]


def collect_slot_results(futures_by_slot):
    """Waits for every submitted slot future and returns one row per slot, sorted by slot number:
    fire_slot's own successful result dict, or {"slot": i, "failure": repr(exc)} if that slot's
    future raised. One slot's exception never drops the other slots' results."""
    results = []
    for future, slot in futures_by_slot.items():
        try:
            results.append(future.result())
        except Exception as e:
            results.append({"slot": slot, "failure": repr(e)})
    results.sort(key=lambda r: r["slot"])
    return results


def peak_usage(telemetry_path):
    """Scans a Monitor's telemetry.jsonl for the run's peak VRAM/GTT/evicted/thermal readings.
    Unlike summarize.py's per-phase breakdown, concurrent slots overlap the same Monitor phase
    field, so this only tracks one whole-run peak."""
    peak = {"vram": 0, "gtt": 0, "evicted": 0, "edge": 0, "hotspot": 0}
    if not telemetry_path.exists():
        return peak
    with telemetry_path.open() as telemetry:
        for line in telemetry:
            row = json.loads(line)
            m, s = row["process"]["bytes_by_metric"], row["safety"]
            peak["vram"] = max(peak["vram"], m.get("drm-memory-vram", 0))
            peak["gtt"] = max(peak["gtt"], m.get("drm-memory-gtt", 0))
            peak["evicted"] = max(peak["evicted"], m.get("amd-evicted-vram", 0))
            peak["edge"] = max(peak["edge"], s.get("edge_c") or 0)
            peak["hotspot"] = max(peak["hotspot"], s.get("hotspot_c") or 0)
    return peak


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="validates the CLI and matrix, no server/GPU")
    g.add_argument("--run", action="store_true", help="launches one server and fires --slots concurrent requests")
    ap.add_argument("--inhibitor-ok", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--slots", type=int, default=2, help="parallel server slots (-np) and concurrent requests")
    ap.add_argument("--depth", type=int, default=32000, help="input depth (tokens) per synthetic prompt")
    ap.add_argument("--ctx", type=int, default=262144, help="-c passed to llama-server")
    ap.add_argument("--kv", default="q5_1", help="-ctv value (K stays q8_0, matching depth_bench)")
    ap.add_argument("--kv-unified", dest="kv_unified", action="store_true", default=None,
                     help="pass --kv-unified")
    ap.add_argument("--no-kv-unified", dest="kv_unified", action="store_false", default=None,
                     help="pass --no-kv-unified")
    ap.add_argument("--kv-unified-per-slot", type=int, help="context limit per parallel slot")
    ap.add_argument("--mtp", action="store_true", help="enable MTP (--spec-type draft-mtp)")
    ap.add_argument("--spec-draft-n-max", type=int, default=2, help="draft length when --mtp is set")
    ap.add_argument("--output-tokens", type=int, default=300, help="n_predict per request")
    ap.add_argument("--extra", default="",
                     help='extra llama-server flags appended to the server argv, e.g. '
                          '--extra "-cms 2048"')
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    if args.slots < 1:
        ap.error("--slots must be >= 1")

    if args.smoke:
        print(json.dumps({"ok": True, "cli": "concurrency_bench.py --smoke", "slots": args.slots,
                          "depth": args.depth, "ctx": args.ctx, "kv": args.kv, "mtp": args.mtp,
                          "spec_draft_n_max": args.spec_draft_n_max if args.mtp else None,
                          "kv_unified": args.kv_unified, "kv_unified_per_slot": args.kv_unified_per_slot,
                          "extra": args.extra, "output_tokens": args.output_tokens}, ensure_ascii=False))
        return 0

    if os.environ.get("IA_BENCH_INHIBITED") != "1" or not args.inhibitor_ok:
        ap.error("requires the IA_BENCH_INHIBITED=1 guard and --inhibitor-ok; use systemd-inhibit (see the docstring/README)")
    for p in (b.SERVER, b.MODEL, b.WIKI):
        if not p.is_file(): raise SystemExit(f"Missing required file: {p} (set BENCH_SERVER / BENCH_MODEL / BENCH_WIKI)")

    argv = [str(b.SERVER), "-m", str(b.MODEL), "--port", str(b.PORT), "-c", str(args.ctx),
            "-ctk", "q8_0", "-ctv", args.kv, "-fa", "on", "-np", str(args.slots),
            "--ctx-checkpoints", "4", "-ngl", "all", "--temp", "1", "--top-k", "20", "--min-p", "0"]
    hardcoded = set(BASE_HARDCODED)
    if args.kv_unified is True:
        argv += ["--kv-unified"]
    elif args.kv_unified is False:
        argv += ["--no-kv-unified"]
    if args.kv_unified_per_slot:
        argv += ["--kv-unified-per-slot", str(args.kv_unified_per_slot)]
        hardcoded.add("--kv-unified-per-slot")
    if args.mtp:
        argv += ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(args.spec_draft_n_max)]
        hardcoded |= {"--spec-type", "--spec-draft-n-max"}
    argv += b.extra_argv(args.extra, hardcoded)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = b.BASE / (f"concurrency-{stamp}" + (f"-{args.tag}" if args.tag else ""))
    out.mkdir(parents=True)
    (out / "command.json").write_text(json.dumps(argv, indent=2) + "\n")
    help_result = subprocess.run([str(b.SERVER), "--help"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / "server-help.txt").write_text(help_result.stdout)
    if help_result.returncode:
        raise RuntimeError(f"llama-server --help returned {help_result.returncode}")
    required = required_help_flags(args)
    missing = missing_help_flags(help_result.stdout, required)
    if missing: raise RuntimeError(f"flags this run would use are missing from --help: {missing}")
    wiki = b.WIKI.read_text(errors="replace")
    hashes = {"server": b.sha256(b.SERVER), "model": b.sha256(b.MODEL), "wiki": b.sha256(b.WIKI)}
    power_cap = b.check_power_cap(max(args.depth, args.ctx))
    (out / "metadata.json").write_text(json.dumps({
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "slots": args.slots, "depth": args.depth,
        "ctx": args.ctx, "kv": args.kv, "mtp": args.mtp,
        "spec_draft_n_max": args.spec_draft_n_max if args.mtp else None, "kv_unified": args.kv_unified,
        "kv_unified_per_slot": args.kv_unified_per_slot, "extra": args.extra,
        "output_tokens": args.output_tokens, "sha256": hashes, "command": argv,
        "power_cap": power_cap}, indent=2) + "\n")

    cooldown_s = b.cool_down()
    with (out / "server.log").open("w") as log:
        proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        monitor = None
        try:
            # Monitor construction and start() are inside the try (unlike proc, which Popen
            # itself either succeeds with nothing yet to clean up, or fails with nothing to
            # clean up) so a failure here still reaches the server kill in finally below.
            monitor = b.Monitor(proc.pid, (out / "telemetry.jsonl").open("w"))
            monitor.start()
            b.wait_health(proc, monitor)
            monitor.set_phase("ready")
            started = time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.slots) as pool:
                futures_by_slot = {pool.submit(fire_slot, i, args.depth, wiki, args.output_tokens, out, monitor): i
                                    for i in range(args.slots)}
                results = collect_slot_results(futures_by_slot)
            aggregate_wall_s = time.monotonic() - started
        finally:
            try:
                if monitor:
                    monitor.stop()  # raises if the background thread recorded a thermal/eviction/fdinfo abort
            finally:
                if monitor:
                    monitor.file.close()
                # Inside the inner finally so the server is stopped even when monitor.stop()
                # raises, or when it was never constructed.
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try: proc.wait(timeout=20)
                    except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); proc.wait()

    failures = [r for r in results if "failure" in r]
    total_predicted = sum(r.get("predicted_n") or 0 for r in results)
    peak = peak_usage(out / "telemetry.jsonl")
    summary = {"cooldown_s": cooldown_s, "slots": args.slots, "aggregate_wall_s": aggregate_wall_s,
               "total_predicted_tokens": total_predicted,
               "aggregate_tok_s": total_predicted / aggregate_wall_s if aggregate_wall_s else None,
               "sum_predicted_per_second": sum(r.get("predicted_per_second") or 0 for r in results),
               "peak_vram_mib": peak["vram"] / MIB, "peak_gtt_mib": peak["gtt"] / MIB,
               "peak_evicted_mib": peak["evicted"] / MIB, "peak_edge_c": peak["edge"],
               "peak_hotspot_c": peak["hotspot"], "requests": results}
    with (out / "summary.jsonl").open("w") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(out)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
