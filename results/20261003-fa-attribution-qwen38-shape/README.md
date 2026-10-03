# 2026-10-03: FlashAttention cost for Qwen3.8-27B's exact shape (T27 attribution)

Question: before any kernel or selector work, how much of a decode/verify step at depth is
FlashAttention, and how much of it is the quantized-KV path?

## Setup and command

b11160 source (`70c4e1582`) with local perf cases added to `tests/test-backend-ops.cpp`
(`test-backend-ops-local-cases.patch`): head 256, 4 KV heads, GQA 6 (`nr23=[6,1]`), mask on,
K/V `q8_0`/`q5_1` and `f16`/`f16`, `nb` (query tokens) 1, 2 and 4, KV 32K-240K. Built with the
`kvmix` recipe (`docs/ENGINES.md`), 272 W:

```bash
test-backend-ops perf -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256,hsv=256,nh=4,nr23=\[6,1\]'
```

`nb=1` is plain decode, `nb=4` the MTP n=3 verify width. In b11160 this shape selects VEC for
`nb<=2` with quantized KV, and TILE with an f16 conversion of the whole K/V view for `nb=4`.

## Results (µs per FA op)

| KV | nb=1 q8/q5_1 | nb=1 f16 | nb=2 q8/q5_1 | nb=2 f16 | nb=4 q8/q5_1 | nb=4 f16 |
|---|---|---|---|---|---|---|
| 32,768 | 603 | 185 | 433 | 273 | 719 | 353 |
| 131,072 | 2,078 | 675 | 2,071 | 1,059 | 2,557 | 1,383 |
| 196,608 | 3,220 | 1,010 | 3,085 | 1,579 | 3,710 | 2,082 |
| 240,128 | 3,970 | 1,234 | 3,772 | 1,926 | 4,574 | 2,559 |

## Interpretation (calculated, not measured end to end)

- At 240K, 16 attention layers x 4.57 ms = ~73 ms of FA per MTP verify step. The adopted profile
  runs ~134 ms per step on essay at 240K (24.55 tok/s, acceptance 0.765 x 3 + 1 = ~3.3 tokens per
  step), so FA is ~55% of the step: above the 25% gate set for kernel work.
- The quantized path costs 1.8x f16 at `nb=4` and 3.2x at `nb=1`. A kernel that read `q8_0`/`q5_1`
  at f16 speed would save ~32 ms per step (~+30% decode at 240K, an upper-bound estimate).
- The op moves ~445 MiB of quantized K/V at 240K in 4.57 ms, about 10% of the card's nominal
  bandwidth: the kernels are far from bandwidth-bound.

## Conclusion

Attribution done; kernel work is justified by the numbers but not started (a native quantized-KV
verify kernel for head 256 / GQA 6 is development, not a flag). f16 KV is not an option at 262K.

**Raw data**: `perf.txt`, `test-backend-ops-local-cases.patch`.
