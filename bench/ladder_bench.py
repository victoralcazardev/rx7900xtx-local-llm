#!/usr/bin/env python3
"""Model-selection ladder (see docs/models/qwen38-27b-quants.md) against a real llama-server.

For each case: starts the server (argv built the same way as the launcher), waits for
/health, measures VRAM, asks for a long response and records tok/s and MTP acceptance.
Results in res/ladder.jsonl. Needs bench/local.bench.toml (git-ignored, see
local.example.toml for the shape) to resolve models_root and the engine binaries.

Usage: python ladder_bench.py <backend> <case> [<case> ...]
       case = model_folder:context:kvK/kvV:spec_n_max(0=no MTP)[:nomm]  (nomm = no mmproj)
"""
import argparse, json, pathlib, subprocess, sys, time, urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path.insert(0, str(REPO / "scripts"))
from manifest import Model, load, build_argv, running_servers, server_executable  # noqa: E402

HEALTH_WAIT_S = 1800  # same deadline as bench/depth_bench.py's wait_health

# Deliberately Spanish (STYLE.md exception): the actual prompt sent to the model.
PROMPT = ("Escribe en Python una funcion que lea un CSV de ventas (fecha, producto, importe), "
          "agrupe por mes y producto y devuelva un resumen ordenado. Incluye tests con pytest.")
MMPROJ = "mmproj-Qwen3.8-27B-BF16.gguf"


def request_json(url, payload=None, timeout=900):
    req = urllib.request.Request(url, json.dumps(payload).encode() if payload else None,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _vram_used_path():
    """Path to mem_info_vram_used for the amdgpu device with the most total VRAM (see
    scripts/manifest.py's free_vram_gib for the same heuristic)."""
    best = None
    for dev in pathlib.Path("/sys/class/drm").glob("card*/device"):
        try:
            total = int((dev / "mem_info_vram_total").read_text())
        except (OSError, ValueError):
            continue
        if best is None or total > best[0]:
            best = (total, dev / "mem_info_vram_used")
    if best is None:
        raise SystemExit("no amdgpu device found under /sys/class/drm")
    return best[1]


VRAM = _vram_used_path()


def run_case(m, backend, spec):
    (AQUI / "res").mkdir(parents=True, exist_ok=True)
    alive = running_servers()
    if alive:
        return {"backend": backend, "case": spec,
                "error": f"llama-server is already running (PID {alive}). Stop it first."}
    folder, ctx, kv, n, *extra = spec.split(":")
    profile = {"context": int(ctx), "kv": kv.split("/")}
    if int(n):
        profile["spec_n_max"] = int(n)
    d = m.models_root / folder
    model = Model(alias=folder, gguf=d / f"{folder}.gguf", backend=backend, mtp=bool(int(n)),
                  sampling=m.models["qwen38-iq3s-mtp"].sampling,  # official Qwen3.8-27B card
                  mmproj=None if "nomm" in extra else d / MMPROJ, profiles={})
    argv = build_argv(m, model, spec, profile, backend)
    exe = server_executable(m, backend)
    log = AQUI / "res" / f"{backend}-{spec.replace('/', '_').replace(':', '-')}.log"
    vram_before = int(VRAM.read_text())
    t0 = time.time()
    proc = subprocess.Popen([str(exe)] + argv, cwd=exe.parent, stdout=open(log, "w"),
                            stderr=subprocess.STDOUT)
    r = {"backend": backend, "case": spec}
    try:
        deadline = time.time() + HEALTH_WAIT_S
        while True:
            if proc.poll() is not None:
                r["error"] = f"died while loading rc={proc.returncode} ({log.name})"
                return r
            if time.time() > deadline:
                r["error"] = f"timed out waiting for /health after {HEALTH_WAIT_S}s ({log.name})"
                return r
            try:
                request_json("http://127.0.0.1:8080/health", timeout=3)
                break
            except OSError:
                time.sleep(2)
        r["load_s"] = round(time.time() - t0)
        r["vram_gib"] = round((int(VRAM.read_text()) - vram_before) / 2**30, 2)
        try:
            d = request_json("http://127.0.0.1:8080/v1/chat/completions",
                             {"max_tokens": 1024, "messages": [{"role": "user", "content": PROMPT}]})
        except OSError as e:
            oom = "out of memory" in log.read_text(errors="replace")
            r["error"] = ("OOM during inference" if oom else f"{type(e).__name__}") + f" ({log.name})"
            return r
        t = d.get("timings", {})
        r["tok_s"] = round(t.get("predicted_per_second", 0), 1)
        r["tokens"] = t.get("predicted_n")
        if t.get("draft_n"):
            r["mtp_accept"] = f"{t.get('draft_n_accepted')}/{t['draft_n']}"
        r["vram_peak_gib"] = round((int(VRAM.read_text()) - vram_before) / 2**30, 2)
        return r
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("backend", help="backend defined in bench/local.bench.toml")
    ap.add_argument("specs", nargs="*", help="case specs (see usage above)")
    args = ap.parse_args()
    backend = args.backend
    m = load(local=AQUI / "local.bench.toml")
    for s in args.specs:
        r = run_case(m, backend, s)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        with open(AQUI / "res" / "ladder.jsonl", "a") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
