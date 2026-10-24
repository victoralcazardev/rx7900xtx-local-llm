# 2026-10-23: MTP n=4 vs. n=3 at 240K on the native q8_0/q5_1 TILE engine

**Question**: the patched engine ([D1](../20261023-d1-pr30792q51-240k/README.md)) makes the multi-query
verify step cheaper, which should move the best MTP draft depth up. Does `--spec-draft-n-max 4` now beat
n=3 at 240K? (n=4 lost by 8% on b11160 in 2026-09-26.)

## Setup

- Engine `llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix` (see [`docs/ENGINES.md`](../../docs/ENGINES.md)),
  model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`, production flags with `--spec-draft-n-max 4` (`n4-map` variant:
  `draft-mtp,ngram-map-k4v`); argv in `command-n4-map.json`.
- `bench/spec_depth_bench.py --run --depth 240000 --variants n4-map --reps 3 --extra "-ub 256"`, under
  `systemd-inhibit`, 272 W cap, temperature 0, right after the D1 runs (same session, Brave closed).
- n=3 reference: arm B of [D1](../20261023-d1-pr30792q51-240k/README.md), same engine, same day.

## Results

Mean of cached reps 2-4:

| Task | n=3 (tok/s) | n=4 (tok/s) | Change | Acceptance n=3 / n=4 | Greedy text vs. n=3 |
|---|---|---|---|---|---|
| essay | 31.11 | 28.11 | -9.7% | 0.798 / 0.733 | differs |
| copy | 53.78 | 48.65 | -9.5% | 0.91 / 0.875 | identical |
| code | 22.39 | 17.31 | -22.7% | 0.435 / 0.360 | differs |

Cold prefill 394.0 tok/s (n=3: 393.6).

## Conclusion

n=4 still loses on every task, also on copy where the text is identical: the extra drafted token's
acceptance does not pay for the deeper draft. n=3 stays.
