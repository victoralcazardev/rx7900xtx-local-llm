#!/usr/bin/env python3
"""Throwaway KVMem-trial retrieval check: replays saved bench/longctx_quality.py documents (same
prompts as the baseline runs) over /v1/chat/completions and scores them with that script's own
evaluate(). Server must already run on :8080 with --temp 0 and thinking off.

usage: kvmem_quality.py --out FILE doc.json [doc.json ...]
"""
import argparse, importlib.util, json, sys, time, urllib.request
from pathlib import Path

def find_repo_root(script_file):
    for parent in Path(script_file).resolve().parents:
        if (parent / "bench/longctx_quality.py").is_file():
            return parent
    raise RuntimeError(f"Cannot find repository bench/longctx_quality.py above {script_file}")


ROOT = find_repo_root(__file__)
spec = importlib.util.spec_from_file_location("lq", ROOT / "bench/longctx_quality.py")
lq = importlib.util.module_from_spec(spec); spec.loader.exec_module(lq)

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True, type=Path)
ap.add_argument("docs", nargs="+", type=Path)
a = ap.parse_args()
for path in a.docs:
    doc = json.loads(path.read_text())
    for q, question in enumerate(doc["questions"]):
        body = {"messages": [{"role": "user", "content": question["prompt"]}], "max_tokens": lq.MAX_OUTPUT_TOKENS,
                "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=3600) as r:
            resp = json.load(r)
        msg = resp["choices"][0]["message"]
        content = msg.get("content") or ""
        score = lq.evaluate(content, question["expected"])
        row = {"doc": path.name, "question": q, "expected": question["expected"], "content": content,
               "reasoning_chars": len(msg.get("reasoning_content") or ""), "finish": resp["choices"][0]["finish_reason"],
               "usage": resp.get("usage"), "timings": resp.get("timings"), "elapsed_s": round(time.monotonic() - t0, 1),
               **{k: score[k] for k in ("exact_match", "field_accuracy", "parsed", "loop_detected")}}
        with a.out.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(path.name, q, "EXACT" if row["exact_match"] else "MISS", row["parsed"], "expected", question["expected"],
              "prompt", (row["usage"] or {}).get("prompt_tokens"), "cache", (row["timings"] or {}).get("cache_n"),
              f"{row['elapsed_s']}s", flush=True)
