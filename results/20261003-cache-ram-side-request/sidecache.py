#!/usr/bin/env python3
"""T26 server-side: does an unrelated side request (like omp's speculative compaction summary)
evict a deep main prompt from the single slot, and does the host prompt cache (--cache-ram) restore it?
Usage: sidecache.py <llama-server> <tag> <cache_ram_mib> [main_tokens]
Sequence: main(N) cold -> main(N)+q2 warm -> side(20K, different prefix) -> main(N)+q3. Records timings."""
import json, os, subprocess, sys, time, urllib.request
srv, tag, cram = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 180000
MODEL, WIKI = os.environ["BENCH_MODEL"], os.environ["BENCH_WIKI"]
PORT = 18081
URL = f"http://127.0.0.1:{PORT}"
cmd = [srv, "-m", MODEL, "--port", str(PORT), "-c", "262144", "-ctk", "q8_0", "-ctv", "q5_1", "-fa", "on",
       "-np", "1", "--ctx-checkpoints", "4", "-ngl", "all", "-ub", "256", "--temp", "1", "--top-p", "0.95",
       "--top-k", "20", "--min-p", "0", "--reasoning-effort", "medium", "--spec-type", "draft-mtp",
       "--spec-draft-n-max", "3", "--cache-ram", cram]
here = os.path.dirname(os.path.abspath(__file__))
log = open(os.path.join(here, f"server-{tag}.log"), "w")
p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)

def post(path, body, timeout=3600):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def rss_mib():
    for l in open(f"/proc/{p.pid}/status"):
        if l.startswith("RssAnon"): return int(l.split()[1]) // 1024

try:
    for _ in range(600):
        try:
            if json.load(urllib.request.urlopen(URL + "/health")).get("status") == "ok": break
        except Exception: pass
        time.sleep(1)
    text = open(WIKI, encoding="utf-8").read()
    ids = post("/tokenize", {"content": text[:4_000_000], "add_special": False})["tokens"]
    assert len(ids) > N + 60000, len(ids)
    q = lambda s: post("/tokenize", {"content": s, "add_special": False})["tokens"]
    main = ids[:N]
    side = ids[N + 20000:N + 40000]
    steps = [("main-cold", main + q("\nQ1: summarize the first paragraph.")),
             ("main-warm", main + q("\nQ2: list three names.")),
             ("side", side + q("\nSummarize this conversation.")),
             ("main-after-side", main + q("\nQ3: what is the last word?"))]
    for name, prompt in steps:
        t0 = time.monotonic()
        r = post("/completion", {"prompt": prompt, "n_predict": 32, "temperature": 0, "cache_prompt": True})
        t = r.get("timings", {})
        print(json.dumps({"tag": tag, "cache_ram": cram, "step": name, "n_prompt": len(prompt),
                          "cache_n": t.get("cache_n"), "prompt_n": t.get("prompt_n"),
                          "prompt_s": round(t.get("prompt_ms", 0) / 1000, 1),
                          "wall_s": round(time.monotonic() - t0, 1), "rss_anon_mib": rss_mib()}), flush=True)
finally:
    p.terminate(); p.wait(60)
