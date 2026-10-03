# 2026-10-03: n-gram drafting stacked on MTP n=3 (T08)

Question: does adding an n-gram drafter to MTP n=3 (`--spec-type draft-mtp,ngram-*`) speed up the
adopted profile without hurting reasoning/code tasks? Decision rule from
[`speculative.md`](../../docs/measurements/speculative.md): adopt only if agent/editing tasks gain
beyond seed noise and reasoning/code do not lose, at empty context and at 240K, with no runaway
repetition.

## Setup and commands

Engine b11160 `hip-kvmix`, adopted flags (`-c 262144`, KV `q8_0`/`q5_1`, `-ub 256`,
`--ctx-checkpoints 4`, `-np 1`), 272 W. Control `mtp3`/`n3` = the same-day b11160 run in
[`20261003-b11371-mtp-draft-sampling/`](../20261003-b11371-mtp-draft-sampling/).

| Variant | Extra server flags |
|---|---|
| `mod` | `--spec-type draft-mtp,ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 8 --spec-ngram-mod-n-max 32` |
| `moddef` | `--spec-type draft-mtp,ngram-mod` (defaults) |
| `map` | `--spec-type draft-mtp,ngram-map-k4v` |

```bash
python3 bench/spec_bench.py --run --variants mtp3-mod mtp3-moddef mtp3-map --tag ngram-stack   # empty, temp 1, 6 tasks x 3 seeds
python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3-mod n3-moddef --reps 3 --extra "-ub 256"   # temp 0
python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 3 --extra "-ub 256"
```

## Results: empty context, temperature 1 (median tok/s of 3 seeds)

| Task | `mtp3` | `mod` | `moddef` | `map` |
|---|---|---|---|---|
| agent (return a whole file with one change) | 83.6 | 136.1 (+63%) | 131.3 (+57%) | 129.3 (+55%) |
| editing | 76.8 | 75.7 (-1%) | 71.7 (-7%) | 104.7 (+36%) |
| extraction | 68.5 | 69.4 (+1%) | 67.3 (-2%) | 71.7 (+5%) |
| code | 69.0 | 68.4 (-1%) | 69.0 (0%) | 69.1 (0%) |
| reasoning | 73.3 | 72.9 (-1%) | 71.9 (-2%) | 71.8 (-2%) |
| spanish | 52.5 | 51.2 (-2%) | 50.6 (-4%) | 52.0 (-1%) |

No arm hit the output cap on a task that normally stops early; no repetition runs.

## Results: 240K fill, temperature 0

**Measurement caveat**: `ngram-mod` keeps one n-gram pool shared across requests (b11160
`common/speculative.cpp:1870`, reset only when occupancy passes a threshold). The depth bench
repeats the identical prompt, so reps 2-4 draft from the previous reps' outputs (essay climbs
23.4 → 47 → 53 → 55 tok/s). Only rep 1 (first exposure) is comparable with the control; that is a
single sample per cell.

| Task, rep 1 | `n3` | `mod` | `moddef` |
|---|---|---|---|
| essay | 24.27 | 23.39 (-3.6%) | 23.38 (-3.7%) |
| copy | 26.92 | 34.63 (+28.6%) | 29.63 (+10.1%) |
| code | 18.40 | 18.22 (-1.0%) | 18.62 (+1.2%) |

With n-gram drafting the temperature-0 output is no longer bit-identical across reps (SHA changes
from rep 2 on), consistent with verify-batch-size numerics; quality must be checked separately.

`map` at 240K, run on b11371 (speed-neutral vs. b11160, same tokens), median of 3 warm reps.
`ngram-map-k4v` indexes positions of the slot's current token sequence and cleans entries beyond
a new, shorter prompt on each request (b11371 `common/ngram-map.cpp:121-136`); per-key statistics
may persist, which fits reps 2-4 being a little faster than rep 1. Rep 1 alone already gains +43%
on copy. Its output SHA equals the MTP-only control on every task (lossless at temperature 0):

| Task | `n3` (b11371) | `map` | Delta |
|---|---|---|---|
| essay | 24.64 | 24.58 | -0.2% |
| copy | 27.03 | 43.85 | +62% (rep 1: 38.59, +43%) |
| code | 18.71 | 18.61 | -0.5% |

Peak process VRAM 22,634 MiB, GTT 8 MiB. This arm ran after a 25-minute GPU rest (hotspot 48°C at start, so the
bench's pre-variant cooldown was 0 s); essay and code match the control, so the copy gain is not thermal.

## 240K at temperature 1 (production sampling)

Same command with `--temperature 1` (seeds 9, 10, 11, as in the MTP-only control of
[`20261003-b11371-mtp-draft-sampling/`](../20261003-b11371-mtp-draft-sampling/README.md#240k-at-temperature-1-s2c)),
b11371, median of 3:

| Task | `n3` | `map` | Delta |
|---|---|---|---|
| code | 16.79 | 16.82 | +0.2% |
| copy | 27.36 | 38.26 (33.15-57.03) | +40% |
| essay | 24.83 | 24.93 | +0.4% |

Each seed produced the same output SHA as the MTP-only control, so the gain is speed only. Total
warm wall time over the 9 runs: 170.5 s vs. 158.9 s (-6.8%).

## Conclusion

**Adopted `--spec-type draft-mtp,ngram-map-k4v`** (profile key `spec_type` in `models.toml`). It
passes the decision rule at both depths: large gains where the answer copies context (agent +55%,
editing +36% at empty context; copy +62% at 240K), -0..-2% elsewhere, identical temperature-0
output, no repetition loops, no VRAM change. `ngram-mod` is not adopted: its cross-request pool
makes the benchmark unreliable and it loses on editing at empty context; it may still help real
agent loops (T09 replay).

**Raw data**: `empty-ngram-aggregate.json`, `depth240k-ngram-mod-summary.jsonl`, `depth240k-ngram-map-b11371-summary.jsonl`, `depth240k-temp1-ngram-map-b11371-summary.jsonl`.
