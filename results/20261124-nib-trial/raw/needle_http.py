#!/usr/bin/env python3
"""Multi-needle long-context retrieval over an OpenAI-compatible chat endpoint.

Each case builds a seeded haystack of GSM8K questions (distractors) of about --depth tokens and hides
--needles "access code" facts at seeded positions; one request asks for every code. A needle counts as
found when its exact code appears in the answer. Greedy, thinking off, deterministic per seed, so two
engine configurations (e.g. sparse attention on and off) see byte-identical prompts.

usage: needle_http.py <port> <gsm8k-test.jsonl> --depths 32000 128000 240000 [--cases 3] [--needles 4]
       [--chars-per-token 3.6] [--out FILE]
"""
import argparse
import json
import random
import time
import urllib.request

WORDS = ("amber", "basalt", "cobalt", "delta", "ember", "fjord", "garnet", "harbor", "indigo", "juniper",
         "kestrel", "lumen", "marble", "nectar", "onyx", "prairie", "quartz", "raven", "sierra", "tundra")


def build(rng, pool, depth, n, cpt):
    names = rng.sample(WORDS, n)
    codes = [f"{rng.randrange(10**5, 10**6)}" for _ in names]
    target_chars = int(depth * cpt)
    parts, size = [], 0
    while size < target_chars:
        q = rng.choice(pool)
        parts.append(q)
        size += len(q) + 2
    slots = sorted(rng.sample(range(1, len(parts)), n))
    for pos, name, code in sorted(zip(slots, names, codes), reverse=True):
        parts.insert(pos, f"Note: the access code for the {name} vault is {code}.")
    hay = "\n\n".join(parts)
    ask = ("Above is a long list of unrelated notes. Somewhere in it are access codes for these vaults: "
           + ", ".join(names) + ". Reply with one line per vault in the form `name: code`, nothing else.")
    depths = [round(100 * s / len(parts)) for s in slots]
    return hay + "\n\n" + ask, list(zip(names, codes, depths))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port")
    ap.add_argument("data")
    ap.add_argument("--depths", type=int, nargs="+", required=True)
    ap.add_argument("--cases", type=int, default=3)
    ap.add_argument("--needles", type=int, default=4)
    ap.add_argument("--chars-per-token", type=float, default=3.6)
    ap.add_argument("--seed", type=int, default=20261124)
    ap.add_argument("--out")
    a = ap.parse_args()
    pool = [json.loads(line)["question"] for line in open(a.data)]
    out = open(a.out, "w") if a.out else None
    found = total = 0
    for depth in a.depths:
        for case in range(a.cases):
            rng = random.Random(a.seed * 1000 + depth + case)
            prompt, facts = build(rng, pool, depth, a.needles, a.chars_per_token)
            body = {"messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 200,
                    "reasoning_effort": "none"}
            t = time.monotonic()
            req = urllib.request.Request(f"http://127.0.0.1:{a.port}/v1/chat/completions",
                                         json.dumps(body).encode(), {"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=3600))
            text = r["choices"][0]["message"].get("content") or ""
            hits = [code in text for _, code, _ in facts]
            found += sum(hits)
            total += len(hits)
            row = dict(depth=depth, case=case, prompt_tokens=r["usage"]["prompt_tokens"], found=sum(hits),
                       of=len(hits), needles=[dict(name=n, code=c, percent=p, hit=h)
                                              for (n, c, p), h in zip(facts, hits)],
                       seconds=round(time.monotonic() - t, 1), answer=text[:300])
            print(json.dumps({k: row[k] for k in ("depth", "case", "prompt_tokens", "found", "of", "seconds")}),
                  flush=True)
            if out:
                out.write(json.dumps(row) + "\n")
                out.flush()
    summary = dict(found=found, total=total)
    print(json.dumps(summary))
    if out:
        out.write(json.dumps(summary) + "\n")


if __name__ == "__main__":
    main()
