# 2026-10-23: D1, native q8_0 K + q5_1 V in the FA TILE kernel, end to end at 240K

**Question**: does the op-level win of llama.cpp PR #30792 extended with a `q5_1` V loader
([op level, 2026-10-22](../20261022-fa-native-q8q51-tile-op-level/README.md): MTP verify op -29% at
240K) carry over to end-to-end decode on the production profile at 240K fill?

## Setup

- Model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`, production flags of `262k-q8q51-mtp` (KV q8_0/q5_1, MTP n=3
  + `ngram-map-k4v`, `-ub 256`); exact argv per arm in `command-<arm>.json`.
- Engines (own builds, recipe and patch in the op-level folder and [`docs/ENGINES.md`](../../docs/ENGINES.md)):
  - A: `llama-b11820-linux-rocm10-gfx1100-kvmix` (commit `d77256999f21`, no patch).
  - B: `llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix` (A + [`pr30792-q5_1.patch`](../20261022-fa-native-q8q51-tile-op-level/pr30792-q5_1.patch)).
- Command, once per engine (`BENCH_SERVER`), A then B, back to back:

  ```bash
  systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 BENCH_EXPECT_POWER_CAP_W=272 \
    python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 3 --extra "-ub 256"
  ```

- 272 W cap, temperature 0 (seed 7), Brave closed, desktop ~0.6 GiB VRAM before the run. Rep 1 is the
  cold warm-up (full 240K prefill); reps 2-4 reuse the cached prompt. Raw rows: `summary-<arm>.jsonl`
  (machine paths replaced).

## Results

Mean of reps 2-4 (min-max in brackets). The greedy text hash of every task is **identical across all
eight runs of both arms**, so the speed difference is the kernel, not a different text:

| Task | tg A b11820 (tok/s) | tg B + PR #30792 q5_1 (tok/s) | Change | Draft acceptance A / B |
|---|---|---|---|---|
| essay | 26.15 [26.11-26.18] | 31.11 [30.46-31.66] | **+19.0%** | 0.798 / 0.798 |
| copy | 45.50 [45.48-45.52] | 53.78 [53.57-53.89] | **+18.2%** | 0.91 / 0.91 |
| code | 17.61 [17.61-17.62] | 22.39 [22.28-22.46] | **+27.1%** | 0.431 / 0.435 |

| Metric | A | B |
|---|---|---|
| Cold 240K prefill (tok/s) | 396.0 | 393.6 (-0.6%) |
| Peak process VRAM (MiB, fdinfo) | 22,642 | 22,646 |
| Evicted VRAM | 0 | 0 |
| Peak hotspot (°C) | 94 | 95 |

## Conclusion

- B beats A by 18-27% decode at 240K with identical greedy output, no VRAM cost and no prefill change
  (the `ne[1] <= 8` guard keeps prefill on b11820's path by construction). That exceeds the op-level
  estimate of ~15%, because the patch also speeds up the single-token (n_q 1) MTP draft attention
  (-59% at op level), which the estimate left out [INFERENCE].
- A vs. the production b11718 on 2026-10-18 (essay 26.22, copy 45.58, code 17.54): b11820 alone is
  neutral, as the op level predicted.
- Adoption gate per [`docs/sop/update-engine.md`](../../docs/sop/update-engine.md) step 3: speed passes
  and the coding suite shows no regression (below). **B adopted** as the `hip-kvmix` engine.

## Coding suite on B

`bench/coding_suite.py --run --label d1-b11820-pr30792q51` (suite v2, seed 1, production sampling) against
B launched with the exact production argv, then `--compare` with the
[27B baseline](../20261018-coding-suite-baseline-27b/README.md) (b11718): **6/6 pass, verdict "no
regression"**. Per task in `coding-suite/CS*-s1/` (`result.json`, `model.diff`), `meta.json` alongside.

|Task|tests|Turns|Wall s (B)|Wall s (baseline b11718)|
|---|---|---|---|---|
|CS1 local bug fix|pass|17|65.7|73.1|
|CS2 cross-file change|pass|16|126.5|261.3|
|CS3 tool-error recovery|pass|14|103.5|63.8|
|CS4 long context (114,229 tokens)|pass|3|320.8|324.5|
|CS5 post-compaction continuation|pass|8|27.1|138.8|
|CS6 artifact in a bounded result|pass|14|42.1|43.0|

Wall times are sampled episodes (temperature 1) with different turn counts, not a speed comparison.

## Limits

- Single machine, one prompt per task, temperature 0: speed, not answer quality.
- Local patch on top of an open upstream PR; PR #30792 may change before it merges.
- Cross-session spread: a same-engine rerun of arm B on 2026-10-24 gave essay 33.12, copy 54.41, code
  22.49 tok/s with the same text ([b11846 check](../20261024-engine-b11846-240k/README.md)). Copy and code
  reproduce within ~1%, so their +18% / +27% hold; essay moved 6.5%, so its ratio is uncertain by about
  that much (26.15 → 33.12 would be +26.6%). The arms also started differently: A after ~0.06 s of
  cooldown, B after 60 s (`cooldown_s` in the summaries).
