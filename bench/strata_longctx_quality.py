#!/usr/bin/env python3
"""longctx_quality.py's Spanish multi-key retrieval test against a running Strata server (no launch).

Same documents, questions and scoring as `longctx_quality.py` (build_document, evaluate); only the transport
differs: tokens are counted with Strata's `/v1/messages/count_tokens` and questions go to `/v1/chat/completions`
with temperature 0 and thinking off (`chat_template_kwargs.enable_thinking=false`). Start Strata first.

  python3 strata_longctx_quality.py --depths 128000 190000 240000 --docs 5 [--url http://127.0.0.1:8080]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
import urllib.request

import longctx_quality as lq

OUTPUT_DIR = lq.AQUI / "res" / "strata_longctx_quality"


class StrataTokenizer:
    """count(text) = tokens of `text` as a user message, minus the template's fixed wrapper around it."""

    def __init__(self, url: str):
        self.url = url.rstrip("/") + "/v1/messages/count_tokens"
        self.wrapper = 0
        self.wrapper = self.count("")

    def count(self, text: str) -> int:
        r = lq.request_json(self.url, {"model": "x", "messages": [{"role": "user", "content": text}]}, timeout=600)
        if not isinstance(r.get("input_tokens"), int):
            raise RuntimeError(f"Unexpected count_tokens response: {r!r}")
        return r["input_tokens"] - self.wrapper


def ask(url: str, prompt: str) -> tuple[dict, float]:
    payload = {"model": "x", "messages": [{"role": "user", "content": prompt}], "max_tokens": lq.MAX_OUTPUT_TOKENS,
               "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}
    started = time.monotonic()
    r = lq.request_json(url.rstrip("/") + "/v1/chat/completions", payload)
    return r, time.monotonic() - started


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--depths", type=int, nargs="+", default=list(lq.DEPTHS))
    ap.add_argument("--docs", type=int, default=lq.DOCS)
    ap.add_argument("--output", type=pathlib.Path, default=OUTPUT_DIR)
    args = ap.parse_args()
    out = args.output / time.strftime("strata-longctx-%Y%m%d-%H%M%S")
    (out / "documents").mkdir(parents=True)
    tok = StrataTokenizer(args.url)
    model = lq.request_json(args.url.rstrip("/") + "/v1/models")
    lq.save(out / "metadata.json", {"created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "server": args.url,
                                    "models": model, "depths": args.depths, "docs_per_depth": args.docs,
                                    "questions_per_doc": lq.QUESTIONS_PER_DOC, "seed_base": lq.BASE_SEED,
                                    "temperature": 0, "max_tokens": lq.MAX_OUTPUT_TOKENS, "thinking": False,
                                    "template_wrapper_tokens": tok.wrapper})
    summary = out / "summary.jsonl"
    documents: dict[int, list[dict]] = {}
    for depth in args.depths:
        documents[depth] = []
        for i in range(args.docs):
            seed = lq.BASE_SEED + depth * 10 + i      # longctx_quality.py's seeds: same values and needles
            doc = lq.build_document(tok, depth, i, seed)
            if doc["document_tokens"] != depth:
                raise RuntimeError("document depth doesn't match target")
            lq.save(out / "documents" / f"d{depth}-n{i:02d}.json", doc)
            documents[depth].append(doc)
            for q, question in enumerate(doc["questions"]):
                row = {"variant": "strata-mtp0", "depth": depth, "document_index": i, "question": q}
                try:
                    r, elapsed = ask(args.url, question["prompt"])
                    choice = r["choices"][0]
                    content = choice["message"].get("content") or ""
                    score = lq.evaluate(content, question["expected"])
                    row.update({"seed": seed, "document_tokens": doc["document_tokens"],
                                "document_sha256": hashlib.sha256(doc["document"].encode()).hexdigest(),
                                "needle_index": question["needle_index"], "needle_token": question["needle_token"],
                                "expected": question["expected"], "response_text": content,
                                "reasoning_chars": len(choice["message"].get("reasoning_content") or ""),
                                "finish_reason": choice.get("finish_reason"), "timings": r.get("timings", {}),
                                "elapsed_s": elapsed, "truncated": choice.get("finish_reason") == "length", **score})
                    print(f"d{depth} n{i} q{q}: exact={score['exact_match']} finish={row['finish_reason']} "
                          f"{elapsed:.0f} s", flush=True)
                except Exception as e:                  # one failed question is recorded; the run continues
                    row.update({"failure": repr(e)})
                    print(f"d{depth} n{i} q{q}: FAILED {e!r}", flush=True)
                with summary.open("a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    rows = [json.loads(line) for line in summary.read_text().splitlines() if line.strip()]
    failures = [r for r in rows if "failure" in r]
    scores, status = lq.aggregate_scores([r for r in rows if "failure" not in r], failures, documents,
                                         (("strata", False),), tuple(args.depths))   # rows are named "strata-mtp0"
    lq.save(out / "scores.json", scores)
    print(json.dumps(scores, indent=1))
    print(out)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
