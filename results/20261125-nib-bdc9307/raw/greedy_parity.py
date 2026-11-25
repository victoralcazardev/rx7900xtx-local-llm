#!/usr/bin/env python3
"""Greedy output per prompt over /v1/completions, to compare two engine builds token for token.

Three prompts: prose, code, and this repository's docs text at about 33K tokens (chars-per-token
2.9, the same ratio as the speed runs). temperature 0 and no other sampling field, 256 tokens each.
Writes one JSON line per prompt with the generated text, so greedy_compare.py can diff two runs.

usage: greedy_parity.py <port> --label L --out FILE [--chars-per-token 2.9] [--gen 256]
"""
import argparse
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]

PROSE = ("Write the first paragraph of a short story about a lighthouse keeper who finds a "
         "weathered notebook in the rocks after a storm.")
CODE = ("Write a Python function that merges two sorted lists into one sorted list without using "
        "sorted() or list.sort(), and explain the time complexity in one sentence.")
DEPTH_TEXT = ("Continue the documentation above with a new section about tuning long-context "
              "inference servers.")


def corpus():
    return "\n\n".join(p.read_text() for p in sorted((ROOT / "docs").rglob("*.md")))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chars-per-token", type=float, default=2.9)
    ap.add_argument("--depth", type=int, default=32768)
    ap.add_argument("--gen", type=int, default=256)
    a = ap.parse_args()
    base = corpus()
    need = int(a.depth * a.chars_per_token)
    filler = (base * (need // len(base) + 1))[:need]
    prompts = [
        ("prose", PROSE),
        ("code", CODE),
        ("depth33k", f"Session greedy-parity.\n\n{filler}\n\n{DEPTH_TEXT}"),
    ]
    with open(a.out, "w") as out:
        for name, prompt in prompts:
            body = {"prompt": prompt, "temperature": 0, "max_tokens": a.gen}
            req = urllib.request.Request(f"http://127.0.0.1:{a.port}/v1/completions",
                                         json.dumps(body).encode(), {"Content-Type": "application/json"})
            t = time.monotonic()
            r = json.load(urllib.request.urlopen(req, timeout=1800))
            ch = r["choices"][0]
            row = dict(label=a.label, prompt=name, text=ch.get("text") or "",
                       finish=ch["finish_reason"], prompt_tokens=r["usage"]["prompt_tokens"],
                       generated=r["usage"]["completion_tokens"],
                       seconds=round(time.monotonic() - t, 2))
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(f"{a.label} {name}: {row['generated']} tokens, {row['finish']}, "
                  f"{row['prompt_tokens']} prompt tokens, {row['seconds']} s", flush=True)


if __name__ == "__main__":
    main()
