#!/usr/bin/env python3
"""Fills the context with ~N real tokens (wiki.train) and asks for a response: detects OOM
with a full context.

Usage: python oom_probe.py <n_chars>   (BENCH_WIKI must point at a wikitext-2-raw
       wiki.train.raw file, or similar long corpus)
"""
import json, os, sys, time, urllib.request, pathlib

N_CHARS = int(sys.argv[1])  # ~4 characters per token in English
wiki_path = os.environ.get("BENCH_WIKI")
if not wiki_path:
    sys.exit("set BENCH_WIKI to a long text file (see depth_bench.py)")
text = pathlib.Path(wiki_path).read_text()[:N_CHARS]
msg = text + "\n\nSummarize in 3 sentences what the first paragraphs of this text are about."
req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
      json.dumps({"max_tokens": 400, "messages": [{"role": "user", "content": msg}]}).encode(),
      {"Content-Type": "application/json"})
t0 = time.time()
d = json.load(urllib.request.urlopen(req, timeout=3600))
t = d["timings"]
print(json.dumps({"prompt_tokens": t["prompt_n"], "pp_tok_s": round(t["prompt_per_second"], 1),
                  "tg_tok_s": round(t["predicted_per_second"], 1), "mtp": f"{t.get('draft_n_accepted')}/{t.get('draft_n')}",
                  "total_s": round(time.time() - t0)}))
