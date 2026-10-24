# 2026-10-24: E4, probabilistic MTP draft sampling at 240K on the native TILE engine

**Question**: with the cheaper verify step of the native `q8_0`/`q5_1` TILE engine, does
`--spec-draft-sampling probabilistic` (rejection-sampled drafts) now beat greedy drafts at temperature 1?
On b11371 (2026-10-03) it was code +12.4%, copy -2.7%, essay -4.6%, wall -2.1%
([results](../20261003-b11371-mtp-draft-sampling/README.md)).

## Setup

- Engine `llama-b11846-pr30792q51-linux-rocm10-gfx1100-kvmix`, production flags (`n3-map`) vs. the same plus
  `--spec-draft-sampling probabilistic` (`n3-prob-map`); argv in `command-<variant>.json`.
- `bench/spec_depth_bench.py --run --depth 240000 --variants <variant> --reps 3 --temperature 1 --extra "-ub 256"`,
  `n3-map` then `n3-prob-map` back to back (same session), `systemd-inhibit`, 272 W cap, Brave closed.
  Temperature 1 with seed 7+rep: every rep samples a different text, so per-rep spread is the sampling
  spread, not noise to average away. Rows in `summary-<variant>.jsonl`.

## Results

Reps 2-4 (mean, min-max), acceptance aggregated over the three reps:

| Task | greedy drafts (tok/s) | probabilistic (tok/s) | Change | Acceptance greedy / prob |
|---|---|---|---|---|
| essay | 32.47 [32.31-32.68] | 32.54 [31.74-32.95] | +0.2% | 0.775 / 0.777 |
| copy | 58.83 [45.38-71.92] | 52.78 [51.28-54.24] | -10.3% | 0.899 / 0.888 |
| code | 21.89 [19.92-24.84] | 24.05 [23.24-25.61] | +9.9% | 0.408 / 0.485 |

Wall time of the nine measured requests: 115.1 s vs. 111.4 s (-3.3%). Cold prefill 394.5 vs. 394.0 tok/s.

## Conclusion

- Same shape as on b11371: code gains (acceptance 0.41 → 0.49), essay is flat, copy's mean drops but
  copy's greedy-draft spread (45-72 tok/s) is wider than the difference, so three samples do not decide it.
  Overall wall time -3.3%, inside the spread of a three-sample test.
- **Not adopted.** Three temperature-1 samples per task cannot resolve a few percent; the deciding test
  stays a real coding-session replay (T24), as on 2026-10-03.
