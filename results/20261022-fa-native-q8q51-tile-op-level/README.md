# FlashAttention op level: native q8_0 K + q5_1 V in the TILE kernel (2026-10-22)

**What.** Does dequantizing K `q8_0` / V `q5_1` inside the TILE kernel (llama.cpp
[PR #30792](https://github.com/ggml-org/llama.cpp/pull/30792), open, extended here with a `q5_1` V
loader) cut the decode/MTP-verify attention cost of the adopted profile? Op level only: no
llama-server, no end-to-end tg, no prefill.

**Engines** (own builds, recipe in [`docs/ENGINES.md`](../../docs/ENGINES.md), ROCm 10.0.0 toolchain,
`GGML_CUDA_FA_QUANTS="f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0"`, gfx1100):

- A: llama.cpp `b11820` (commit `d77256999f21`), no patch.
- B: A + [`pr30792-q5_1.patch`](pr30792-q5_1.patch) (PR #30792 head `3c25375` plus a `q5_1` V tile loader, a
  `(Q8_0, Q5_1)` tile instance, and every native-dequant path limited to `Q->ne[1] <= 8`, applied
  identically in kernel selection, scratch sizing and launch; for `ne[1] > 8` dispatch is b11820's).
- Test cases for the Qwen3.8-27B attention shape (D=256, 4 KV heads, GQA 6):
  [`tests-kvmix-cases.patch`](tests-kvmix-cases.patch), applied to both trees.

**Commands** (`test-backend-ops` from each build, 272 W cap, no llama-server running, ~2 GiB VRAM used by
the desktop; host load average 70-90 from unrelated work, repeat rounds agreed within ~1-3%):

```bash
test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=q8_0'
test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=f16,type_V=q8_0'
test-backend-ops perf -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256,hsv=256,nh=4,nr23=\[6,1\],kv=(131072|240128)'
```

Perf ran twice in the order A, B, A, B. Raw logs: [`raw/`](raw/).

## Correctness (vs. CPU)

|Filter|A|B|
|---|---|---|
|`hsk=256.*type_K=q8_0` (q8_0/q5_1 and q8_0/q8_0; n_q 1-4, 8 tile, 9 and 64 MMA; odd and permuted KV, softcap, KV 16384)|30/30 OK|30/30 OK|
|`hsk=256.*type_K=f16,type_V=q8_0` (PR's cases)|—|5/5 OK|

## Perf (µs per FA op, mean of 2 rounds; B/A lower is better)

|KV|K/V|n_q 1|n_q 2|n_q 3|n_q 4|n_q 8|
|---|---|---|---|---|---|---|
|240,128|q8_0/q5_1 A|3,986|3,640|4,541|4,550|6,253|
|240,128|q8_0/q5_1 B|1,625|2,635|3,242|3,244|4,839|
|240,128|B/A|0.41|0.72|0.71|0.71|0.77|
|131,072|q8_0/q5_1 B/A|0.42|0.69|0.70|0.70|0.76|
|240,128|f16/f16 control B/A|0.96|1.02|1.02|1.01|1.01|

q8_0/q8_0 improves similarly (B/A 0.70-0.82 at 240K, n_q 2-8). Per-round numbers: `raw/perf-{A,B}-r{1,2}.txt`
(`.txt` because the repository ignores `*.log`).

## Conclusion

- b11820 alone does not change FA for this profile: A matches the 2026-10-03 attribution
  ([`20261003-fa-attribution-qwen38-shape/`](../20261003-fa-attribution-qwen38-shape/)), 3.97 ms at n_q 1
  and 4.57 ms at n_q 4.
- B cuts the MTP n=3 verify op (n_q 4) by 29% at 240K and 131K and the single-token op by 59%.
  Calculated, not measured: 16 full-attention layers x 1.31 ms = ~21 ms less per verify step of
  ~134 ms, an upper bound of ~15% end-to-end decode at 240K.
- Not measured: end-to-end tg/pp, MTP acceptance, prefill (the `ne[1] <= 8` guard keeps prefill on the
  b11820 path by construction). The `q5_1` dequant runs in half precision like the existing VEC path.
- Next: the 240K end-to-end A/B in [`docs/sop/update-engine.md`](../../docs/sop/update-engine.md)
  step 3, A vs. B ([`ENGINES-EXPERIMENTS.md`](../../docs/ENGINES-EXPERIMENTS.md#cheaper-route-via-llamacpp-pr-30792-2026-10-22)).
