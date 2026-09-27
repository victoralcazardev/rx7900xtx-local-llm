#!/usr/bin/env python3
"""Fills the context with ~N real tokens (wiki.train) and asks for a response: detects OOM
with a full context.

Usage: python oom_probe.py <n_chars>   (BENCH_WIKI must point at a wikitext-2-raw
       wiki.train.raw file, or similar long corpus)
"""
import argparse
import json, os, time, urllib.request, pathlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n_chars", type=int, help="approximate number of corpus characters to use")
    args = parser.parse_args()
    if args.n_chars <= 0:
        parser.error("n_chars must be a positive integer")
    wiki_path = os.environ.get("BENCH_WIKI")
    if not wiki_path:
        raise SystemExit("set BENCH_WIKI to a long text file (see depth_bench.py)")
    text = pathlib.Path(wiki_path).read_text()[:args.n_chars]
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


if __name__ == "__main__":
    main()
