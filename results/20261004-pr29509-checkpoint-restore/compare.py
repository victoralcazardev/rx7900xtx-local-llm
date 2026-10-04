#!/usr/bin/env python3
"""Compare baseline vs patch results: per-request table, first-token top-5 deltas, checkpoint sizes."""
import json, re
from pathlib import Path

H = Path(__file__).resolve().parent
arms = {a: json.load(open(H / f"{a}.results.json")) for a in ("baseline", "patch")}
cold = {a: r[-1] for a, r in arms.items()}

def ck(r):
    return [re.search(r"size = ([\d.]+) MiB", l).group(1) for l in r["log"] if "created context checkpoint" in l]

def nrest(r):
    return sum("restored context checkpoint" in l for l in r["log"])

def maxdiff(x, y):
    if [t for t, _ in x] != [t for t, _ in y]:
        return float("inf")
    return max(abs(a - b) for (_, a), (_, b) in zip(x, y))

print("| # | step | req | cache_n b/p | prompt_n b/p | draft acc b | draft acc p | restores b/p | max top5 dlogprob vs base | vs own cold | text equal |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
worst = 0.0
for b, p in zip(arms["baseline"], arms["patch"]):
    tb, tp = b["timings"], p["timings"]
    d = maxdiff(b["top5"], p["top5"])
    dc = maxdiff(p["top5"], cold["patch"]["top5"]) if p["req"].startswith("A_prime") else None
    worst = max(worst, d)
    same = (b["reasoning"], b["content"]) == (p["reasoning"], p["content"])
    print(f"| {b['i']} | {b['step']} | {b['req']} | {tb['cache_n']}/{tp['cache_n']} | {tb['prompt_n']}/{tp['prompt_n']} "
          f"| {tb['draft_n_accepted']}/{tb['draft_n']} | {tp['draft_n_accepted']}/{tp['draft_n']} "
          f"| {nrest(b)}/{nrest(p)} | {d:.2e} | {'' if dc is None else f'{dc:.2e}'} | {same} |")
print(f"\nworst first-token top-5 |dlogprob| baseline vs patch: {worst:.2e}")
for a in arms:
    sizes = sorted({s for r in arms[a] for s in ck(r)}, key=float)
    print(f"{a} checkpoint sizes (MiB): {sizes}")
    acc = sum(r["timings"]["draft_n_accepted"] for r in arms[a]); dr = sum(r["timings"]["draft_n"] for r in arms[a])
    print(f"{a} total acceptance {acc}/{dr} = {acc/dr:.3f}")
    print(f"{a} cold vs baseline cold max dlogprob: {maxdiff(cold[a]['top5'], cold['baseline']['top5']):.2e}")
    log = (H / f"{a}.server.log").read_text(errors="replace")
    print(f"{a} MTP ctx_dft warnings: {len(re.findall(r'ctx_dft pos_max', log))}")
print("first token / top5 (baseline A_prime a1):", arms["baseline"][1]["first_token"], arms["baseline"][1]["top5"])
