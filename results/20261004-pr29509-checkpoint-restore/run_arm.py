#!/usr/bin/env python3
"""Send the E3 request sequence to a running server and record per-request results.

usage: run_arm.py <arm> <port> <server_log> <server_pid>
Sequence: (a) A, A'  (b) A, B, A'  repeated twice, then cold A' (cache_prompt=false).
Writes <arm>.results.json with timings, first-token top-5 logprobs, text and the server
log lines emitted during each request.
"""
import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
arm, port, log, spid = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])
SEQ = [("a1", "A"), ("a1", "A_prime"),
       ("b1", "A"), ("b1", "B"), ("b1", "A_prime"),
       ("a2", "A"), ("a2", "A_prime"),
       ("b2", "A"), ("b2", "B"), ("b2", "A_prime"),
       ("cold", "A_prime_cold")]
PAT = re.compile(r"created context checkpoint|restored context checkpoint|erased|forcing full prompt"
                 r"|ctx_dft pos_max|found better prompt|prompt cache|cache state|n_past|lcs|f_keep"
                 r"|restored|loading", re.I)

def swap_used_mib():
    m = dict(l.split(":") for l in Path("/proc/meminfo").read_text().splitlines())
    return (int(m["SwapTotal"].split()[0]) - int(m["SwapFree"].split()[0])) // 1024

def first_token(choice):
    lp = choice.get("logprobs") or {}
    for key in ("content", "reasoning_content"):
        if lp.get(key):
            t = lp[key][0]
            return key, t["token"], [(x["token"], x["logprob"]) for x in t["top_logprobs"]]
    return None, None, None

def vmswap_mib(pid):
    for l in Path(f"/proc/{pid}/status").read_text().splitlines():
        if l.startswith("VmSwap:"):
            return int(l.split()[1]) // 1024
    return 0

SWAP0 = int(os.environ.get("E3_SWAP0", swap_used_mib()))  # set by arm.sh before server start
print(f"swap at arm start: {SWAP0} MiB", flush=True)
out = []
for i, (step, name) in enumerate(SEQ):
    if re.search(r":8080\s", subprocess.run(["ss", "-ltnH"], capture_output=True, text=True).stdout):
        sys.exit("ABORT: a server on port 8080 appeared")
    if swap_used_mib() - SWAP0 > 1024 or vmswap_mib(spid) > 1024:
        sys.exit(f"ABORT: swap grew {swap_used_mib() - SWAP0} MiB / server VmSwap {vmswap_mib(spid)} MiB")
    nlines = len(log.read_text(errors="replace").splitlines())
    data = (HERE / "requests" / f"{name}.json").read_bytes()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=data,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=1800))
    wall = time.time() - t0
    time.sleep(1)
    lines = log.read_text(errors="replace").splitlines()[nlines:]
    ch = r["choices"][0]
    src, tok, top5 = first_token(ch)
    msg = ch["message"]
    rec = {"i": i, "step": step, "req": name, "wall_s": round(wall, 2),
           "timings": r.get("timings"), "usage": r.get("usage"),
           "first_src": src, "first_token": tok, "top5": top5,
           "reasoning": msg.get("reasoning_content"), "content": msg.get("content"),
           "finish": ch.get("finish_reason"), "swap_mib": swap_used_mib(), "swap0_mib": SWAP0,
           "server_vmswap_mib": vmswap_mib(spid),
           "log": [l for l in lines if PAT.search(l)]}
    out.append(rec)
    t = rec["timings"] or {}
    print(f"{i:2} {step:4} {name:13} cache_n={t.get('cache_n')} prompt_n={t.get('prompt_n')} "
          f"draft={t.get('draft_n')}/{t.get('draft_n_accepted')} wall={wall:.1f}s tok={tok!r}", flush=True)
    (HERE / f"{arm}.results.json").write_text(json.dumps(out, indent=1))
