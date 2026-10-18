# 2026-10-18: engine b11718 vs. b11454 + PR #29509 at 240K (A1, reduced)

**Question**: is the `hip-kvmix` engine switched to b11718 on 2026-10-18 (unmeasured until now) slower
than the build it replaced, b11454 + PR #29509, on the production profile at deep context?

**Scope, reduced by the user's request**: only the 240K depth. The planned 190K pair and the
retrieval run were dropped ("me parece excesivo"); coding quality on b11718 is measured by the coding
suite instead ([`docs/ENGINES-EXPERIMENTS.md`](../../docs/ENGINES-EXPERIMENTS.md#current-plan-2026-10-18), A1).

## Setup

- Model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`, production flags of `262k-q8q51-mtp` (KV q8_0/q5_1, MTP n=3
  + n-gram map, `-ub 256`); exact argv per arm in `command-<arm>.json`.
- `bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 3 --extra "-ub 256"`, once
  per engine (`BENCH_SERVER`), back to back, under `systemd-inhibit`, 272 W cap, temperature 0.
  Rep 1 is the cold warm-up (full 240K prefill); reps 2-4 reuse the cached prompt.
- Engines: `llama-b11718-linux-rocm10-gfx1100-kvmix` and `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix`
  ([`docs/ENGINES.md`](../../docs/ENGINES.md)). Desktop: Brave closed; a first attempt with Brave open
  was aborted by the GPU monitor when 10.9 GiB of the server's VRAM was evicted.
- Raw rows: `summary-b11718.jsonl`, `summary-b11454pr.jsonl` (machine paths replaced).

## Results

Mean of reps 2-4 (spread within each arm ≤ 1%; the text hash is identical across all four reps of
every arm):

| Task | tg b11718 (tok/s) | tg b11454+PR (tok/s) | Change | Draft acceptance (b11718 / b11454+PR) | Greedy text |
|---|---|---|---|---|---|
| essay | 26.22 | 25.57 | +2.5% | 0.798 / 0.782 | differs |
| copy | 45.58 | 45.06 | +1.2% | 0.91-0.91 / 0.91-0.93 | identical |
| code | 17.54 | 19.10 | -8.2% | 0.431 / 0.502 | differs |

Cold 240K prefill: 394.8 tok/s (b11718) vs. 387.5 tok/s (+1.9%).

## Conclusion

- No kernel slowdown: where the greedy text is identical (copy) b11718 is 1.2% faster, essay is 2.5%
  faster, and prefill is 1.9% faster.
- The code task is 8.2% slower because b11718 decodes a different greedy text on which the MTP draft
  is accepted less often (0.431 vs. 0.502). With 3 drafted tokens per step that predicts
  (1 + 3 × 0.431) / (1 + 3 × 0.502) = -8.5% tokens per step, matching the observed -8.2%: the cost
  per step is unchanged. Different greedy text is expected from upstream numeric changes (e.g. the
  FA tile fix #30103); which text the model produces is a quality question for the coding suite,
  not a speed regression.
- Decision: keep b11718 ([`docs/DECISIONS.md`](../../docs/DECISIONS.md), 2026-10-18). The plan's
  "tg within 2%" gate fails only on the code task, for the reason above.
- Single machine, single prompt per task, temperature 0: it measures speed, not answer quality.
