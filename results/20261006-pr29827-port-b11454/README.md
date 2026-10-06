# 2026-10-06: llama.cpp PR #29827 (chunked FA convert buffer) ported onto b11454 + PR #29509

Question: does [PR #29827](https://github.com/ggml-org/llama.cpp/pull/29827) cut VRAM at 240K depth
on the adopted profile without costing decode speed? Gate, set before the run: adopt if peak VRAM
drops by >= 0.4 GiB and no task loses more than 2% median tg.

## Setup

- PR #29827 (closed unmerged upstream, author fork) caps the FlashAttention f16 K/V convert buffer
  used for quantized KV and processes the KV in chunks. The default cap was raised locally to
  512 MiB (`GGML_CUDA_FATTN_CONVERT_BYTES` overrides it).
- Port: local branch on b11454 (`462524043`) + PR #29509, i.e. the adopted `hip-kvmix` engine
  ([`20261006-b11454-engine-update/`](../20261006-b11454-engine-update/README.md)) plus the PR.
  4 conflict hunks with upstream [#29435](https://github.com/ggml-org/llama.cpp/pull/29435)
  resolved by hand. Same `kvmix` recipe and ROCm 10 toolchain. Not published.
- Baseline: plain b11454 + PR #29509, the b11454 arm of the engine update (same command, same
  night).
- Model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`, adopted profile (KV `q8_0`/`q5_1`, MTP n=3 +
  `ngram-map-k4v`, `-ub 256`), temperature 0, 272 W cap.

## Commands

```bash
# op level, port build (local test cases add the kv=240128 rows)
test-backend-ops -b ROCm0 -o FLASH_ATTN_EXT                                    # default cap
GGML_CUDA_FATTN_CONVERT_BYTES=1048576 test-backend-ops -b ROCm0 -o FLASH_ATTN_EXT   # 1 MiB cap
test-backend-ops perf -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256,hsv=256,nh=4,nr23=\[6,1\]'
GGML_CUDA_FATTN_CONVERT_BYTES=1099511627776 test-backend-ops perf ...          # unchunked
# end to end, 240K fill, 3 reps after a cold-prefill warm-up
python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 3 --extra "-ub 256"
```

## Results

Op level (`FLASH_ATTN_EXT`, hsk=hsv=256, nh=4, nr23=[6,1], nb=4, K `q8_0` / V `q5_1`):

- Correctness: 4009/4009 OK at the default cap and at a 1 MiB cap (forces chunking).
- kv=240128: 512 MiB cap 4,615.40 / 4,658.36 us vs. unchunked 4,505.51 / 4,534.88 us (+2.6%).
  kv=131072 is not chunked at 512 MiB (2,505.70 / 2,529.60 vs. 2,516.20 / 2,540.35 us).
- An earlier sweep on the PR's original base (kv=240128): 64 MiB cap +16%, 512 MiB +2.4%.

End to end, 240K depth, median tg tok/s over 3 warm reps:

| Task | b11454 + #29509 | + PR #29827 port | Delta |
|---|---|---|---|
| essay | 25.94 | 26.80 | +3.3% |
| copy | 45.94 | 46.27 | +0.7% |
| code | 19.33 | 18.77 | -2.9% |

- Peak process VRAM (`drm-memory-vram`): 22,641 -> 22,240 MiB (-401 MiB, 0.39 GiB).
- Determinism: with the port, the copy task alternates between two output hashes (`ff04a5f8` /
  `d7e88c3c`) for identical input at temperature 0; reps 2 and 3 diverge at character 1776, on a
  whitespace token. Plain b11371 and b11454 produce one hash per task across all reps.

## Decision

Not adopted. The gate fails on both axes (VRAM -0.39 GiB < 0.4 GiB; code -2.9% > 2%), and the port
makes greedy output non-deterministic. The engine stays b11454 + PR #29509.

**Raw data**: `depth240k-port512-summary.jsonl` (server path replaced with a placeholder),
`op-tests-perf-extract.txt` ("tests passed" lines and the `q8_0`/`q5_1` perf lines). The full
`test-backend-ops` eval logs, SSE streams and server logs stay local (`_tmp/`, git-ignored).
