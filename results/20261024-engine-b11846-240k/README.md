# 2026-10-24: engine b11846 + native q8_0/q5_1 TILE patch vs. b11820 + the same patch, 240K

**Question**: does rebasing the production engine from b11820 to llama.cpp b11846 (latest release on
2026-10-24) change speed, output or VRAM on the production profile? Upstream check b11820 → b11846:
no change to `fattn*`, the HIP backend or `common/speculative.cpp`'s MTP path that this profile uses;
in range are CUDA graph chunking (#30804/#31053), DFlash2 probabilistic sampling (#30663), the qwen4exp
`kq_mask` removal (#30965) and server fixes. Recorded in [`docs/DECISIONS.md`](../../docs/DECISIONS.md).

## Setup

- Engines (own builds, recipe [`docs/ENGINES.md`](../../docs/ENGINES.md)):
  - A: `llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix` (production).
  - B: `llama-b11846-pr30792q51-linux-rocm10-gfx1100-kvmix`: b11846 (commit `1a24df1`) +
    [`pr30792-q5_1.patch`](../20261022-fa-native-q8q51-tile-op-level/pr30792-q5_1.patch) kernel hunks
    (applied cleanly; its `test-backend-ops.cpp` hunk conflicts with the Qwen-shape test cases and was
    left out) + [`tests-kvmix-cases.patch`](../20261022-fa-native-q8q51-tile-op-level/tests-kvmix-cases.patch)
    (applied with offsets). `--help` identical to b11820.
- Correctness on B: `test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=q8_0'` 30/30 OK.
- Speed: `bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 3 --extra "-ub 256"`,
  A then B back to back, under `systemd-inhibit`, 272 W cap, temperature 0, Brave closed. Argv per arm in
  `command-<arm>.json`, rows in `summary-<arm>.jsonl`.
- Quality: `bench/coding_suite.py --run --label b11846-pr30792q51` (suite v2, seed 1) against B launched with
  the production argv, then `--compare` with the [27B baseline](../20261018-coding-suite-baseline-27b/README.md).

## Results

Mean of cached reps 2-4; greedy text identical between A and B on every task:

| Task | A b11820 (tok/s) | B b11846 (tok/s) | Change | Acceptance |
|---|---|---|---|---|
| essay | 33.12 | 33.18 | +0.2% | 0.798 |
| copy | 54.41 | 54.68 | +0.5% | 0.91 |
| code | 22.49 | 22.54 | +0.2% | 0.435 |

Cold 240K prefill 395.7 vs. 394.5 tok/s (-0.3%); peak process VRAM 22,645 MiB in both.

Coding suite on B: 6/6 pass (CS1-CS6), `--compare` verdict "no regression". Per task in
`coding-suite/CS*-s1/`.

## Conclusion

- b11846 is neutral (within 0.5%) with identical text: **adopted** as the `hip-kvmix` engine to keep the
  base current; b11820 + patch stays as rollback.
- **Session variance**: arm A here is the same engine, flags and greedy text as
  [D1](../20261023-d1-pr30792q51-240k/README.md) arm B, yet essay is 33.12 vs. 31.11 tok/s (+6.5%), copy
  +1.2%, code +0.4%. GPU clocks, power and temperatures during generation matched (sclk ~2,405 MHz,
  mclk 1,249 MHz, ~270 W, junction ~91°C), so the cause is unknown. Comparisons across sessions need a
  same-session reference arm; differences under ~6% between sessions are not evidence.
