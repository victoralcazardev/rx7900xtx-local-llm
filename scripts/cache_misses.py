"""Classify prompt-cache reuse per request from a llama-server log (`_tmp/logs/*.log`).

For every request that selected the slot by LCP similarity, llama-server logs `f_sim_best`
(LCP / new prompt tokens) and `f_keep` (LCP / tokens left in the slot by the previous request).
This script pairs each with the previous `stop processing: n_tokens` and the request's
`prompt eval time`, and classifies it:
    full        f_keep 1.000: the previous request's tokens, generated reasoning included, are
                all a prefix of the new prompt
    partial     f_keep >= 0.95: the tail of the previous request was not reused
    compaction  f_keep < 0.95 and the new prompt is under half the old slot (summary shape)
    miss        f_keep < 0.95 otherwise: the prompt diverged early without shrinking, i.e. a
                rewrite of earlier history; read the request around that line to see why
Estimated LCP = f_keep x old tokens; estimated new prompt = LCP / f_sim_best. Both use the
three decimals that the log prints, so they are approximate.

Usage: python3 scripts/cache_misses.py <server.log> [--all]
"""
from __future__ import annotations

import argparse
import re

RE_RELEASE = re.compile(r"stop processing: n_tokens = (\d+)")
RE_SELECT = re.compile(r"f_sim_best = ([\d.]+) .*f_keep = ([\d.]+)")
RE_PREFILL = re.compile(r"prompt eval time = +([\d.]+) ms / +(\d+) tokens")
CLASSES = ("full", "partial", "compaction", "miss")


def parse(lines):
    events, old, pending = [], 0, None
    for n, line in enumerate(lines, 1):
        if m := RE_RELEASE.search(line):
            old = int(m[1])
        elif m := RE_SELECT.search(line):
            f_sim, f_keep = float(m[1]), float(m[2])
            lcp = round(f_keep * old)
            new = round(lcp / f_sim) if f_sim else 0
            cls = ("full" if f_keep >= 0.9995 else "partial" if f_keep >= 0.95
                   else "compaction" if new < old / 2 else "miss")
            pending = {"line": n, "old_tokens": old, "f_sim": f_sim, "f_keep": f_keep,
                       "lcp_est": lcp, "new_est": new, "cls": cls}
        elif pending and (m := RE_PREFILL.search(line)):
            pending.update(prefill_tokens=int(m[2]), prefill_s=float(m[1]) / 1000)
            events.append(pending)
            pending = None
    return events


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--all", action="store_true", help="list every request, not only non-full ones")
    a = ap.parse_args()
    with open(a.log, errors="replace") as f:
        events = parse(f)
    print(f"{'line':>7} {'class':<10} {'old':>8} {'f_sim':>6} {'f_keep':>6} {'lcp~':>8} {'new~':>8} {'prefill':>8} {'s':>6}")
    for e in events:
        if a.all or e["cls"] != "full":
            print(f"{e['line']:>7} {e['cls']:<10} {e['old_tokens']:>8} {e['f_sim']:>6.3f} {e['f_keep']:>6.3f} "
                  f"{e['lcp_est']:>8} {e['new_est']:>8} {e['prefill_tokens']:>8} {e['prefill_s']:>6.1f}")
    print("\nclass       requests  prefill_tokens  prefill_s")
    for c in CLASSES:
        sel = [e for e in events if e["cls"] == c]
        print(f"{c:<10} {len(sel):>9} {sum(e['prefill_tokens'] for e in sel):>15} {sum(e['prefill_s'] for e in sel):>10.0f}")


if __name__ == "__main__":
    main()
