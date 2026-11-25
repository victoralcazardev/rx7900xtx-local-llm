#!/usr/bin/env python3
"""Compare two greedy_parity.py outputs: same prompt, same text?

Reports per prompt whether the texts are identical, and when they differ, the first differing
character offset, the context around it and the generated length of both runs.

usage: greedy_compare.py <a.jsonl> <b.jsonl>
"""
import json
import sys


def load(path):
    with open(path) as f:
        return {r["prompt"]: r for r in (json.loads(line) for line in f)}


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    same = 0
    for name in a:
        ta, tb = a[name]["text"], b[name]["text"]
        if ta == tb:
            same += 1
            print(f"{name}: identical ({len(ta)} chars, {a[name]['generated']} tokens)")
            continue
        pos = next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))
        print(f"{name}: DIFFERENT at char {pos} (a={len(ta)} chars/{a[name]['generated']} tokens, "
              f"b={len(tb)} chars/{b[name]['generated']} tokens)")
        print(f"  a: {ta[max(0, pos - 40):pos + 40]!r}")
        print(f"  b: {tb[max(0, pos - 40):pos + 40]!r}")
    print(f"summary: {same}/{len(a)} prompts identical")


if __name__ == "__main__":
    main()
