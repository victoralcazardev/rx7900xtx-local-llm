#!/usr/bin/env python3
"""Cold Q8/Q5 and MTP2 matrix. Run: systemd-inhibit --what=sleep:idle --mode=block
--why='llama 262k benchmark' env IA_BENCH_INHIBITED=1 python bench/depth_bench.py
--smoke --inhibitor-ok (or --run). Refuses to run the benchmark without both guards.

Configure via environment variables before running:
    BENCH_SERVER  path to the llama-server binary
    BENCH_MODEL   path to the GGUF being measured
    BENCH_WIKI    path to a wikitext-2-raw wiki.train.raw file (or similar long corpus)
    BENCH_OUT     output directory (default: ./res next to this script)
    BENCH_MAX_HOTSPOT_C       overrides the Monitor's hotspot abort threshold (default 104)
    BENCH_EXPECT_POWER_CAP_W  expected GPU power cap (W) for a deep run; warns on stderr if the
                              active power1_cap read from sysfs is above it
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

AQUI = Path(__file__).resolve().parent
SERVER = Path(os.environ.get("BENCH_SERVER", ""))
MODEL = Path(os.environ.get("BENCH_MODEL", ""))
WIKI = Path(os.environ.get("BENCH_WIKI", ""))
BASE = Path(os.environ.get("BENCH_OUT", str(AQUI / "res")))
PORT = 18080
DEPTHS = (128000, 200000, 240000)
REPS = 2
OUT_TOKENS = 1500
URL = f"http://127.0.0.1:{PORT}"
DEEP_RUN_TOKENS = 128_000  # depth/ctx at or above this counts as a "deep" run for the power-cap check


def resolve_max_hotspot_c(env):
    """Resolves the Monitor's hotspot abort threshold (°C) from BENCH_MAX_HOTSPOT_C, defaulting
    to 104 -- below the project's ~105°C unattended-run policy (docs/measurements/thermals-power.md),
    with a small margin. Pure function of the given environment mapping.

    A non-numeric value is a clear operator mistake and aborts (`float()` can't parse it either
    way). A numeric but non-finite value ('nan', 'inf', '-inf') is different: `float()` parses it
    fine, but the Monitor's `hotspot >= MAX_HOTSPOT_C` comparison is always False against NaN,
    which would silently disable the hotspot abort guard instead of raising. Reject it and fall
    back to the safe default with a warning instead."""
    raw = env.get("BENCH_MAX_HOTSPOT_C")
    if not raw:
        return 104.0
    try:
        value = float(raw)
    except ValueError:
        raise SystemExit(f"invalid BENCH_MAX_HOTSPOT_C: {raw!r} (must be a number)")
    if not math.isfinite(value):
        print(f"warning: BENCH_MAX_HOTSPOT_C={raw!r} is not a finite number (would silently "
              "disable the hotspot abort guard); using the default 104 instead", file=sys.stderr)
        return 104.0
    return value


MAX_HOTSPOT_C = resolve_max_hotspot_c(os.environ)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def extra_argv(extra, hardcoded):
    """Shlex-splits a `--extra "..."` passthrough string into argv tokens, for A/B-testing new
    llama-server flags without editing this script. Warns on stderr (doesn't fail) if a
    flag-looking token duplicates one this script already hardcodes for the case being built,
    since the effect of passing the same flag twice depends on llama-server's own argv parsing."""
    if not extra:
        return []
    tokens = shlex.split(extra)
    dupes = sorted({t for t in tokens
                     if t.startswith("-") and (t in hardcoded or t.split("=", 1)[0] in hardcoded)})
    if dupes:
        print(f"warning: --extra duplicates hardcoded flag(s): {', '.join(dupes)}", file=sys.stderr)
    return tokens


def http_json(path, data=None, timeout=60):
    raw = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(URL + path, data=raw, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def wait_health(proc, monitor=None, timeout=1800):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if monitor and (monitor.error or monitor.bad):
            raise RuntimeError(f"monitor failed while loading: {monitor.error or monitor.bad}")
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited while loading (exit {proc.returncode})")
        try:
            with urllib.request.urlopen(URL + "/health", timeout=2) as r:
                if r.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(.5)
    raise TimeoutError("timed out waiting for /health")


def read_fdinfo(pid):
    root = Path(f"/proc/{pid}/fdinfo")
    try:
        files = list(root.iterdir())
    except OSError as e:
        raise RuntimeError(f"fdinfo unreadable for pid {pid}: {e}") from e
    clients = {}
    for entry in files:
        try:
            data = entry.read_text(errors="replace")
        except FileNotFoundError:
            continue  # fd closed between listdir and read
        except OSError as e:
            raise RuntimeError(f"fdinfo unreadable ({entry}): {e}") from e
        vals = {}
        for line in data.splitlines():
            m = re.match(r"\s*(drm-client-id|drm-memory-[\w-]+|amd-[\w-]+):\s*(\d+)(?:\s*(KiB|MiB|bytes?))?", line, re.I)
            if m:
                value, unit = int(m.group(2)), (m.group(3) or "bytes").lower()
                vals[m.group(1)] = value * (1024 if unit == "kib" else 1024*1024 if unit == "mib" else 1)
        if "drm-client-id" in vals:
            clients[str(vals["drm-client-id"])] = vals
    totals = {}
    for row in clients.values():
        for k, v in row.items():
            if k != "drm-client-id":
                totals[k] = totals.get(k, 0) + v
    return {"clients": clients, "bytes_by_metric": totals}


def sysfs_snapshot():
    out = {"cards": {}, "hwmon": {}}
    for p in Path("/sys/class/drm").glob("card[0-9]*/device"):
        card = p.parent.name
        vals = {}
        for name in ("mem_info_vram_used", "mem_info_vram_total", "mem_info_gtt_used", "mem_info_gtt_total"):
            try: vals[name] = int((p / name).read_text().strip())
            except (OSError, ValueError): pass
        if vals: out["cards"][card] = vals
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        vals = {}
        for f in hw.iterdir():
            if not (f.name.endswith("_input") or f.name.endswith("_label") or f.name.endswith("_average")): continue
            try: vals[f.name] = int(f.read_text().strip())
            except ValueError:
                try: vals[f.name] = f.read_text().strip()
                except OSError: pass
            except OSError: pass
        if vals: out["hwmon"][hw.name] = vals
    return out


def find_power_cap_paths():
    """Globs the GPU power-cap sysfs files instead of hardcoding a card/hwmon index -- that
    index can change across reboots or driver reloads."""
    return sorted(Path("/sys/class/drm").glob("card*/device/hwmon/hwmon*/power1_cap"))


def read_power_cap_w(path):
    """Reads one power1_cap sysfs file (microwatts) and returns watts, or None if unreadable."""
    try:
        return int(path.read_text().strip()) / 1_000_000
    except (OSError, ValueError):
        return None


def power_cap_snapshot():
    """Read-only snapshot of the active GPU power cap via sysfs for EVERY AMD card found (never
    writes power1_cap). A host can expose power1_cap on more than one card (e.g. an iGPU plus
    this dGPU); recording only the first lexically sorted match could silently check/record the
    wrong device (card10 also sorts before card2). `cards` lists every match; `path`/
    `power1_cap_w` mirror the first card for backward compatibility with older callers/records,
    but `check_power_cap` below checks every card, not just this one."""
    paths = find_power_cap_paths()
    cards = [{"path": str(p), "power1_cap_w": read_power_cap_w(p)} for p in paths]
    first = cards[0] if cards else {"path": None, "power1_cap_w": None}
    return {**first, "cards": cards}


def power_cap_warning(power_cap_w, depth_or_ctx, expect_w, deep_threshold=DEEP_RUN_TOKENS):
    """Pure decision, no I/O: returns a warning string when a deep run (depth/ctx >=
    deep_threshold) has an active power cap above the expected BENCH_EXPECT_POWER_CAP_W value,
    or None otherwise (below the depth threshold, no expectation set, or cap unknown).
    power1_cap resets to the factory default on reboot and is not persisted by the driver (see
    docs/measurements/thermals-power.md), so a stale expectation can silently regress."""
    if depth_or_ctx < deep_threshold or expect_w is None or power_cap_w is None:
        return None
    if power_cap_w > expect_w:
        return (f"WARNING: GPU power cap is {power_cap_w:.0f} W, above the expected "
                f"{expect_w:.0f} W (BENCH_EXPECT_POWER_CAP_W) for this deep run (depth/ctx "
                f"{depth_or_ctx} >= {deep_threshold}). power1_cap resets to the factory default "
                "on reboot and is not persisted -- see docs/measurements/thermals-power.md.")
    return None


def power_cap_warnings(cards, depth_or_ctx, expect_w, deep_threshold=DEEP_RUN_TOKENS):
    """Like power_cap_warning, but checks every card in `cards` (the `power_cap_snapshot()["cards"]`
    list) instead of assuming the first glob match hosts the benchmarked process -- a multi-GPU
    host can expose power1_cap on more than one device, and the one actually running the
    benchmark isn't guaranteed to sort first. Returns a list of warning strings (one per card
    whose active cap exceeds expect_w for a deep run), empty if none do."""
    warnings = []
    for card in cards:
        warning = power_cap_warning(card.get("power1_cap_w"), depth_or_ctx, expect_w, deep_threshold)
        if warning:
            path = card.get("path")
            warnings.append(f"{warning} (path: {path})" if path else warning)
    return warnings


def resolve_expect_power_cap_w(env):
    """Resolves BENCH_EXPECT_POWER_CAP_W, or None if unset. Unlike resolve_max_hotspot_c (a
    safety guard, where invalid input aborts the whole matrix), a malformed value here only
    disables the deep-run power-cap warning for this run: it prints a warning to stderr and
    returns None instead of raising, so one bad env value can't crash an otherwise-valid run."""
    raw = env.get("BENCH_EXPECT_POWER_CAP_W")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        print(f"warning: invalid BENCH_EXPECT_POWER_CAP_W: {raw!r} (must be a number); "
              "ignoring the expected power cap for this run", file=sys.stderr)
        return None


def check_power_cap(depth_or_ctx, env=None):
    """Pre-run check for a deep (128K+) run: reads the active power cap from sysfs for every AMD
    card found (never writes it), prints a warning to stderr for each card whose cap exceeds
    BENCH_EXPECT_POWER_CAP_W (if set and valid), and returns a snapshot dict meant to be recorded
    in the run's metadata/command JSON."""
    env = os.environ if env is None else env
    snapshot = power_cap_snapshot()
    expect_w = resolve_expect_power_cap_w(env)
    warnings = power_cap_warnings(snapshot["cards"], depth_or_ctx, expect_w)
    for warning in warnings:
        print(warning, file=sys.stderr)
    return {**snapshot, "expect_power_cap_w": expect_w, "warnings": warnings}


def mapped_libraries(pid):
    path = Path(f"/proc/{pid}/maps")
    try: lines = path.read_text(errors="replace").splitlines()
    except OSError as e: raise RuntimeError(f"maps unreadable for pid {pid}: {e}") from e
    return sorted({line.split()[-1] for line in lines if line.split() and line.split()[-1].endswith(".so")})


class Monitor:
    def __init__(self, pid, file):
        self.pid, self.file = pid, file
        self.phase, self.running, self.error = "loading", True, None
        self.lock = threading.Lock()
        self.t0 = time.monotonic()
        self.bad = {}
        self.consecutive = 0
        self.gtt_base = {}
        self.thread = threading.Thread(target=self.loop, daemon=True)
    def set_phase(self, phase):
        with self.lock: self.phase = phase
    def start(self): self.thread.start()
    def loop(self):
        try:
            while self.running:
                with self.lock: phase = self.phase
                process, system = read_fdinfo(self.pid), sysfs_snapshot()
                metrics = process["bytes_by_metric"]
                temps = []
                for hw, vals in system["hwmon"].items():
                    for name, value in vals.items():
                        if "temp" in name and name.endswith("_input"):
                            label = vals.get(name[:-6]+"_label", "")
                            temps.append((f"{name} {label}", value/1000))
                edge = max((v for n, v in temps if "edge" in n.lower()), default=None)
                hotspot = max((v for n, v in temps if "junction" in n.lower() or "hotspot" in n.lower()), default=None)
                evicted = sum(v for k, v in metrics.items() if "evicted" in k.lower())
                unsafe = (edge is not None and edge >= 95) or (hotspot is not None and hotspot >= MAX_HOTSPOT_C) or evicted > 512*1024*1024
                self.consecutive = self.consecutive+1 if unsafe else 0
                abort_reason = None
                if self.consecutive >= 3:
                    self.bad["abort_reason"] = f"thermal/memory: edge={edge}, hotspot={hotspot}, evicted_bytes={evicted}"
                    abort_reason = self.bad["abort_reason"]
                for card, vals in system["cards"].items():
                    used = vals.get("mem_info_gtt_used"); base = self.gtt_base.setdefault(card, used)
                    vals["mem_info_gtt_base"] = base
                    vals["mem_info_gtt_growth"] = used-base if used is not None and base is not None else None
                row = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "elapsed_s": time.monotonic()-self.t0,
                       "phase": phase, "process": process, "system": system,
                       "safety": {"edge_c": edge, "hotspot_c": hotspot, "evicted_bytes": evicted, "abort": abort_reason}}
                self.file.write(json.dumps(row) + "\n"); self.file.flush()
                if abort_reason: raise RuntimeError(abort_reason)
                time.sleep(.2)
        except Exception as e:
            self.error = e
    def stop(self):
        self.running = False; self.thread.join(timeout=3)
        if self.error: raise RuntimeError(f"GPU monitor stopped: {self.error}")


def build_prompt(wiki, target):
    # The final instruction asks for a long essay; only the corpus length is adjusted, and
    # the prompt is tokenized through the full chat template, preserving its exact prefix/suffix.
    # Deliberately Spanish (STYLE.md exception): this project's models are driven in Spanish.
    instruction = "\n\nEscribe un ensayo detallado de al menos 2000 palabras que sintetice, explique y conecte las ideas del texto anterior. Continúa hasta completar el ensayo."
    lo, hi = 1, len(wiki)
    while lo <= hi:
        mid = (lo + hi) // 2
        content = wiki[:mid]+instruction
        rendered = http_json("/apply-template", {"messages": [{"role": "user", "content": content}]})["prompt"]
        ids = http_json("/tokenize", {"content": rendered, "add_special": False})["tokens"]
        n = len(ids)
        if n == target: return ids, rendered, content
        if n < target: lo = mid + 1
        else: hi = mid - 1
    raise RuntimeError(f"could not build an exact depth of {target} tokens")




def stream_completion(payload, events_path, monitor=None):
    req = urllib.request.Request(URL + "/completion", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    pieces, response = [], None
    with urllib.request.urlopen(req, timeout=7200) as r, events_path.open("w") as f:
        for rawline in r:
            line = rawline.decode("utf-8", "replace").rstrip("\r\n")
            f.write(line + "\n"); f.flush()
            if line.startswith("data: "):
                if monitor and monitor.error: raise RuntimeError(f"monitor: {monitor.error}")
                if monitor and monitor.bad: raise RuntimeError(monitor.bad["abort_reason"])
                try: event = json.loads(line[6:])
                except json.JSONDecodeError: continue
                if "prompt_progress" in event and monitor and not monitor.phase.startswith("warm"): monitor.set_phase("prefill")
                if event.get("content"):
                    if monitor:
                        gen = "warm-generation" if monitor.phase.startswith("warm") else "generation"
                        if monitor.phase != gen: monitor.set_phase(gen)
                    pieces.append(event["content"])
                response = event
    return response, "".join(pieces)


# Deliberately Spanish (STYLE.md exception): a short follow-up question, as in a real
# conversation with this project's models.
WARM_Q = "Gracias. Ahora, en un párrafo breve, dime cuál es la idea más importante del texto y por qué."
WARM_OUTPUT = 500


def warm_turn(case, user_content, answer, rep, mon):
    """Second turn on the same server, like a real conversation: history + a short question.
    Measures how much KV is reused (cache_n) and tg at depth with a warm cache.
    A failure here is recorded but doesn't invalidate the main measurement."""
    try:
        mon.set_phase("warm-prefill")
        msgs = [{"role": "user", "content": user_content}, {"role": "assistant", "content": answer},
                {"role": "user", "content": WARM_Q}]
        rendered = http_json("/apply-template", {"messages": msgs})["prompt"]
        ids = http_json("/tokenize", {"content": rendered, "add_special": False})["tokens"]
        payload = {"prompt": ids, "n_predict": WARM_OUTPUT, "temperature": 1, "top_k": 20, "min_p": 0, "seed": 142+rep,
                   "stream": True, "return_progress": True, "cache_prompt": True, "ignore_eos": True,
                   "timings_per_token": True}
        (case/"warm-request.json").write_text(json.dumps(payload) + "\n")
        t0 = time.monotonic()
        response, content = stream_completion(payload, case/"warm-response.sse", mon)
        timings = (response or {}).get("timings", {})
        return {"input_tokens": len(ids), "elapsed_s": time.monotonic()-t0, "timings": timings,
                "completed": bool(response and response.get("stop")) and timings.get("predicted_n") == WARM_OUTPUT,
                "reused_fraction": (timings.get("cache_n") or 0) / len(ids)}
    except Exception as e:
        return {"error": repr(e)}
    finally:
        mon.set_phase("complete")


def cool_down(max_edge=55, limit_s=900):
    """Waits for the GPU to drop below max_edge °C before loading another case (chained cases heat up)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s:
        s = sysfs_snapshot()["hwmon"]
        edges = [v[n[:-6]+"_input"]/1000 for v in s.values() for n in v if n.endswith("_label") and v[n] == "edge" and n[:-6]+"_input" in v]
        if not edges or max(edges) <= max_edge: return time.monotonic() - t0
        time.sleep(10)
    return time.monotonic() - t0


def run_case(out, kv, mtp, depth, rep, wiki, hashes, args):
    cooldown_s = cool_down()
    case = out / f"kv-{kv}_mtp-{int(mtp)}_d-{depth}_r-{rep}"
    case.mkdir(parents=True, exist_ok=False)
    argv = [str(SERVER), "-m", str(MODEL), "--port", str(PORT), "-c", "262144",
            "-ctk", "q8_0", "-ctv", kv, "-fa", "on", "-np", "1", "--ctx-checkpoints", "4",
            "-ngl", "all", "--temp", "1", "--top-k", "20", "--min-p", "0"]
    hardcoded = {"-m", "--port", "-c", "-ctk", "-ctv", "-fa", "-np", "--ctx-checkpoints", "-ngl", "--temp", "--top-k", "--min-p"}
    if mtp:
        argv += ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]
        hardcoded |= {"--spec-type", "--spec-draft-n-max"}
    argv += extra_argv(args.extra, hardcoded)
    (case / "command.json").write_text(json.dumps(argv, indent=2) + "\n")
    started = time.monotonic()
    failed = None
    system_baseline = sysfs_snapshot()
    power_cap = check_power_cap(depth)
    with (case / "server.log").open("w") as log:
        proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        mon = None
        try:
            mon = Monitor(proc.pid, (case / "telemetry.jsonl").open("w")); mon.start()
            wait_health(proc, mon)
            libraries = mapped_libraries(proc.pid)
            mon.set_phase("ready")
            ids, rendered, user_content = build_prompt(wiki, 2048 if args.smoke else depth)
            depth_actual = len(ids)
            # cache_prompt=True: a fresh server per case (cache_n=0 on this request), but it
            # leaves the KV available for the warm turn that follows.
            payload = {"prompt": ids, "n_predict": 32 if args.smoke else OUT_TOKENS, "temperature": 1, "top_k": 20, "min_p": 0,
                       "seed": 42+rep, "stream": True, "return_progress": True, "cache_prompt": True,
                       "ignore_eos": True, "timings_per_token": True}
            (case / "request.json").write_text(json.dumps(payload, ensure_ascii=False) + "\n")
            request_started = time.monotonic(); mon.set_phase("prefill")
            response, content = stream_completion(payload, case/"response.sse", mon)
            request_elapsed = time.monotonic()-request_started
            mon.set_phase("complete")
            timings = (response or {}).get("timings", {})
            prompt_n = timings.get("prompt_n")
            cache_n = timings.get("cache_n")
            acceptance = {"health_ok": True, "exact_depth": depth_actual == (2048 if args.smoke else depth),
                "generated": bool(content), "stream_completed": bool(response and response.get("stop")),
                "predicted_n": timings.get("predicted_n"), "expected_output": payload["n_predict"],
                "prompt_n": prompt_n, "cache_n": cache_n,
                "truncated": bool((response or {}).get("truncated"))}
            acceptance["prompt_depth_ok"] = prompt_n is not None and cache_n is not None and prompt_n+cache_n == depth_actual
            acceptance["accepted"] = acceptance["health_ok"] and acceptance["exact_depth"] and acceptance["generated"] and acceptance["stream_completed"] and acceptance["predicted_n"] == payload["n_predict"] and acceptance["prompt_depth_ok"] and not acceptance["truncated"]
            if not acceptance["accepted"]: raise RuntimeError(f"acceptance criteria not met: {acceptance}")
            if mon.error or mon.bad: raise RuntimeError(f"monitor: {mon.error or mon.bad}")
            (case/"content.txt").write_text(content, encoding="utf-8")
            warm = None if args.no_warm else warm_turn(case, user_content, content, rep, mon)
            if mon.error or mon.bad:
                # A monitor abort during the warm turn is swallowed inside warm_turn(); catch it
                # here so this case fails once (in the `except`/`finally` below) instead of both
                # writing an accepted row here and a failed row from mon.stop() in `finally`.
                raise RuntimeError(f"monitor: {mon.error or mon.bad}")
            result = {"date": dt.datetime.now(dt.timezone.utc).isoformat(), "case": case.name, "kv_v": kv, "mtp2": mtp,
                "depth_requested": depth, "depth_actual": depth_actual, "repetition": rep, "output_requested": payload["n_predict"],
                "output_chars": len(content), "response_final": response, "load_elapsed_s": request_started-started,
                "request_elapsed_s": request_elapsed, "cooldown_s": cooldown_s, "acceptance": acceptance, "warm": warm, "hashes": hashes,
                "command": argv, "telemetry_file": str(case/"telemetry.jsonl"), "runtime_libraries": libraries,
                "system_baseline": system_baseline, "power_cap": power_cap}
            (case/"result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
            with (out/"summary.jsonl").open("a") as f: f.write(json.dumps(result, ensure_ascii=False)+"\n")
        except Exception as e:
            failed = e
            raise
        finally:
            if mon:
                try: mon.stop()
                except Exception as e:
                    failed = failed or e
                finally: mon.file.close()
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try: proc.wait(timeout=20)
                except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            if failed:
                with (out/"summary.jsonl").open("a") as f:
                    f.write(json.dumps({"case": case.name, "kv_v": kv, "mtp2": mtp, "depth_requested": depth,
                        "repetition": rep, "accepted": False, "failure": str(failed), "hashes": hashes,
                        "command": argv, "telemetry_file": str(case/"telemetry.jsonl"),
                        "system_baseline": system_baseline})+"\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="one short case: 2048 tokens in, 32 out")
    g.add_argument("--run", action="store_true", help="full matrix (12 cases)")
    ap.add_argument("--inhibitor-ok", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--depths", type=int, nargs="+", default=list(DEPTHS), help="exact input depths")
    ap.add_argument("--reps", type=int, default=REPS, help="repetitions per configuration")
    ap.add_argument("--no-warm", action="store_true", help="skip the second, warm-cache turn")
    ap.add_argument("--target-only", action="store_true", help="only the target profile q8/q5_1+MTP2")
    ap.add_argument("--extra", default="",
                     help='extra llama-server flags appended to every case, for A/B-testing a '
                          'new flag without editing this script, e.g. --extra "-cms 2048"')
    args = ap.parse_args()
    if os.environ.get("IA_BENCH_INHIBITED") != "1" or not args.inhibitor_ok:
        ap.error("requires the IA_BENCH_INHIBITED=1 guard and --inhibitor-ok; use systemd-inhibit (see the docstring/README)")
    for p in (SERVER, MODEL, WIKI):
        if not p.is_file(): raise SystemExit(f"Missing required file: {p} (set BENCH_SERVER / BENCH_MODEL / BENCH_WIKI)")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = BASE/f"depth-{stamp}"; out.mkdir(parents=True)
    help_result = subprocess.run([str(SERVER), "--help"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    help_text = help_result.stdout
    (out/"server-help.txt").write_text(help_text)
    if help_result.returncode: raise RuntimeError(f"llama-server --help returned {help_result.returncode}")
    required = ["--ctx-checkpoints", "--spec-type", "--spec-draft-n-max", "-fa", "-ctk", "-ctv", "--min-p", "--top-k", "--temp", "-ngl", "-np"]
    missing = [flag for flag in required if flag not in help_text]
    if missing: raise RuntimeError(f"flags this script would use are missing from --help: {missing}")
    wiki = WIKI.read_text(errors="replace")
    hashes = {"server": sha256(SERVER), "model": sha256(MODEL), "wiki": sha256(WIKI)}
    (out/"metadata.json").write_text(json.dumps({"created": dt.datetime.now(dt.timezone.utc).isoformat(),
        "server": str(SERVER), "model": str(MODEL), "wiki": str(WIKI), "sha256": hashes,
        "depths": ([2048] if args.smoke else args.depths), "repetitions": (1 if args.smoke else args.reps), "output": (32 if args.smoke else OUT_TOKENS), "port": PORT,
        "extra": args.extra,
        "acceptance": "exact tokenized depth; health OK; final SSE event captured; fdinfo reachable"}, indent=2)+"\n")
    cases = [("q5_1", True, 2048, 1)] if args.smoke else [(kv, mtp, d, r) for kv, mtp in ([("q5_1", True)] if args.target_only else [("q5_1", True), ("q8_0", False)]) for d in args.depths for r in range(1, args.reps+1)]
    for kv, mtp, depth, rep in cases: run_case(out, kv, mtp, depth, rep, wiki, hashes, args)
    print(out)


if __name__ == "__main__": main()
