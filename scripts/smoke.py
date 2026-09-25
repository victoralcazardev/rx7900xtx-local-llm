"""Starts ONE model/profile for real and checks it serves responses.

One model per invocation (it doesn't walk the whole list): in this batch
each model weighs 10-17 GB and there's only one port, :8080.

Usage:
    python scripts/smoke.py <alias> [--profile P] [--backend vulkan|hip|cuda]
                             [--manifest path.toml]
Exit: 0 = OK, 1 = failure, 2 = preflight (a server is already alive, or a manifest error).
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from manifest import (  # noqa: E402
    REPO, ManifestError, backend_for, load, build_argv, server_executable, resolve,
    running_servers, validate,
)

LOAD_WAIT_S = 600  # 10-17 GB from disk, on an engine not yet benchmarked
MAX_TOKENS = 200
QUESTION = "Answer in one sentence: what is model quantization?"


def _request(url: str, payload: dict, timeout: int):
    req = urllib.request.Request(url, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _wait_healthy(port: int, proc: subprocess.Popen, wait: int) -> bool:
    deadline = time.time() + wait
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(2)
    return False


def _chat(port: int, alias: str) -> dict:
    t0 = time.time()
    d = _request(f"http://127.0.0.1:{port}/v1/chat/completions",
                 {"model": alias, "max_tokens": MAX_TOKENS,
                  "messages": [{"role": "user", "content": QUESTION}]}, timeout=600)
    elapsed = time.time() - t0
    msg = d["choices"][0]["message"]
    usage = d.get("usage") or {}
    timings = d.get("timings") or {}
    tokens = usage.get("completion_tokens") or 0
    tps = timings.get("predicted_per_second") or (tokens / elapsed if elapsed else 0)
    return {
        "content": (msg.get("content") or "").strip(),
        "reasoning": len(msg.get("reasoning_content") or ""),
        "finish": d["choices"][0].get("finish_reason"),
        "tokens": tokens,
        "tps": round(tps, 1),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("alias")
    p.add_argument("--profile")
    p.add_argument("--backend")
    p.add_argument("--manifest", type=pathlib.Path)
    args = p.parse_args()

    try:
        m = load(manifest=args.manifest)
        model, profile_name, profile = resolve(m, args.alias, args.profile)
        backend = backend_for(model, profile, args.backend)
        validate(m, model, profile_name, profile, backend,
                 allow_low_context=m.allow_low_context)
        exe = server_executable(m, backend)
    except ManifestError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    alive = running_servers()
    if alive:
        print(f"ABORTED: llama-server is already alive (PID {alive}). Stop it first.")
        return 2

    argv = build_argv(m, model, profile_name, profile, backend, port=m.default_port)
    print(f">> {args.alias}/{profile_name} (:{m.default_port}, backend={backend}) ...")
    print("command:", " ".join(["llama-server"] + argv))

    logs = REPO / "_tmp" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs / f"smoke-{args.alias}-{profile_name}-{stamp}.log"
    with open(log_path, "w") as log:
        proc = subprocess.Popen([str(exe)] + argv, cwd=str(exe.parent),
                                stdout=log, stderr=subprocess.STDOUT)
        try:
            if not _wait_healthy(m.default_port, proc, LOAD_WAIT_S):
                print(f"FAILED: did not respond on /health within {LOAD_WAIT_S}s"
                      if proc.poll() is None else f"FAILED: process died (rc={proc.poll()})")
                print(f"server log: {log_path}")
                return 1

            r = _chat(m.default_port, args.alias)
            if r["content"]:
                print(f"OK: {r['content'][:80]!r} - tok/s={r['tps']}")
                return 0
            if r["finish"] == "length":
                print(f"OK*: empty content, used up the {MAX_TOKENS} tokens reasoning "
                      f"({r['reasoning']} reasoning chars) - tok/s={r['tps']}")
                return 0
            print(f"FAILED: empty content, finish={r['finish']}")
            print(f"server log: {log_path}")
            return 1
        except Exception as e:  # network, json, timeout...
            print(f"FAILED: {type(e).__name__}: {e}")
            print(f"server log: {log_path}")
            return 1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
