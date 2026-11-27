#!/usr/bin/env python3
"""Compare two greedy_parity.py outputs: same prompt, same text?

Reports per prompt whether the texts are identical, and when they differ, the first differing
character offset, the context around it and the generated length of both runs.

usage: greedy_compare.py <a.jsonl> <b.jsonl>

Exit: 0 only when every prompt is present in both files and both texts are non-empty and identical;
1 when a prompt differs, is missing from one side, came back empty, or no prompt was compared.
"""
import json
import sys


def load(path):
    with open(path) as f:
        return {r["prompt"]: r for r in (json.loads(line) for line in f)}


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: greedy_compare.py <a.jsonl> <b.jsonl>")
    try:
        a, b = load(sys.argv[1]), load(sys.argv[2])
    except (OSError, ValueError) as e:
        sys.exit(f"cannot read the two runs: {e}")
    names = list(a) + [name for name in b if name not in a]
    same = failed = 0
    for name in names:
        ra, rb = a.get(name), b.get(name)
        if ra is None or rb is None:
            print(f"{name}: MISSING from {'a' if ra is None else 'b'}")
            failed += 1
            continue
        ta, tb = ra["text"], rb["text"]
        if not ta or not tb:
            print(f"{name}: EMPTY output (a={len(ta)} chars, b={len(tb)} chars)")
            failed += 1
            continue
        if ta != tb:
            pos = next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))
            print(f"{name}: DIFFERENT at char {pos} (a={len(ta)} chars/{ra['generated']} tokens, "
                  f"b={len(tb)} chars/{rb['generated']} tokens)")
            print(f"  a: {ta[max(0, pos - 40):pos + 40]!r}")
            print(f"  b: {tb[max(0, pos - 40):pos + 40]!r}")
            failed += 1
            continue
        same += 1
        print(f"{name}: identical ({len(ta)} chars, {ra['generated']} tokens)")
    print(f"summary: {same}/{len(names)} prompts identical, {failed} not")
    if failed or not names:
        sys.exit(1)


if __name__ == "__main__":
    main()
