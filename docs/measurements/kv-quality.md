# Quantization quality: KV cache and model weights

## Current conclusion

- **KV `q8_0/q8_0` is effectively free** (KLD 0.000587 vs. f16, 98.76% same top-1 token).
  **`q8_0/q5_1` costs 27% more KLD than q8/q8** but is still small (0.000744) — the right choice to
  save VRAM at long context. **`q4_0/q4_0` is discarded**: KLD 4x higher than q8/q8 and the only mix
  below 98% top-1 match.
- For comparison, quantizing the model *weights* themselves to IQ3_S vs. BF16 gives a third-party
  KLD of ~0.03 (see below) — about 40x the KV-quantization KLD. The KV cache is not where the
  quality budget goes.
- **Weight quantization**: Qwen3.8-27B GSQ-RCO **IQ3_S-mtp** is the model in use. IQ3_S and
  IQ3_S-mtp measure the **same perplexity** (the MTP head doesn't change the base model). IQ3_S
  beats IQ3_XXS by ~3% in perplexity and accepts more MTP drafts, despite IQ3_XXS being ~3% faster
  without MTP. On RDNA3, IQ quantizations generate faster than K quantizations at the same
  file size class.
- Limitation: KLD was measured at 32K of context. At 262K the KV error could accumulate further —
  this is now checked: a long-context retrieval/quality test (RULER-style) is **done**, 68/68 exact
  match from 32K to 240K fill (q8_0/q8_0 up to 220K, q8_0/q5_1 at 240K, including on the exact
  adopted `262k-q8q51-mtp` server flags) — see [`depth.md`](depth.md).

## KV cache quantization: KLD vs. f16

Same weights (IQ3_S-mtp), one variable: the KV type. `llama-perplexity -c 32768 --chunks 2` over
`wiki.test.raw` (32K tokens evaluated). Logits are first saved with KV f16
(`--kl-divergence-base`), then each type is compared with `--kl-divergence`. Measured on the own
gfx1100 build (`llama-b11160-linux-rocm10-gfx1100-kvmix`, see `engines.md`), because the official
binary ships no FlashAttention kernels for the mixed types.

| KV K/V | Mean KLD | KLD p99 | KLD p99.9 | Max KLD | Same top-1 | PPL(Q)/PPL(f16) |
|---|---:|---:|---:|---:|---:|---:|
| q8_0/q8_0 | **0.000587** | 0.0046 | 0.0172 | 0.074 | **98.76%** | 1.00017 |
| q8_0/q5_1 | 0.000744 | 0.0056 | 0.0185 | 0.145 | 98.55% | 1.00093 |
| q8_0/q4_1 | 0.001244 | 0.0086 | 0.0264 | 0.626 | 98.23% | 1.00100 |
| q4_0/q4_0 | 0.002450 | 0.0183 | 0.0465 | 0.147 | 97.38% | 1.00109 |

- q8/q4_1 doubles the KLD of q8/q8 and has high peaks (max 0.63). q4_0/q4_0 quadruples it and is the
  only combination below 98% top-1 match; third-party reports (below) also show q4_0 degrading much
  more with long documents. **q4_0 is discarded.**
- `llama-perplexity` batches through MMA/TILE kernels (K and Q in f16). Generation uses the VEC
  kernel instead, which also quantizes Q to q8_1 when K is quantized (`ggml-cuda/fattn-vec.cuh:97`).
  This KLD measures the KV error itself, but **not the numerical path actually used during
  generation**. Possible follow-up: KLD with `-ub 2` on the VEC engine.

## BeeLlama KVarN KLD (2026-09-26)

BeeLlama v0.4.7's KVarN KV cache (per-head Hadamard rotation + per-axis normalization over
128-token tiles), measured with the same protocol as above but on the BeeLlama binary itself (base
PPL 6.2628 ± 0.0815, f16 KV — **not comparable in absolute terms** to the table above, different
engine/kernels). Raw data:
[`../../results/20260926-beellama-kvarn/`](../../results/20260926-beellama-kvarn/).

| K/V | Mean KLD | Max KLD | PPL(Q)/PPL(base) |
|---|---:|---:|---:|
| q8_0/q8_0 | 0.000754 | 0.131 | 1.00038 |
| q8_0/q6_0 | 0.000785 | 0.147 | 1.00038 |
| q8_0/q5_1 | 0.000905 | 0.273 | 1.00103 |
| kvarn8/kvarn8 | 0.002022 | 0.501 | 1.00006 |
| kvarn6/kvarn6 | 0.002041 | 0.556 | 1.00024 |
| kvarn5/kvarn5 | 0.002168 | 0.372 | 1.00048 |

`q8_0/kvarnN` is rejected by the binary (forces K to `kvarnN`) — K/V mixes with KVarN don't exist.

**KVarN discarded**: ~2.7x the KLD of q8/q8 at every bit width (an error floor independent of
bits), worse than q8/q5_1; KLD exercises the prefill path, which writes nearly all KV in agent
use; BeeLlama is also ~20% slower than our engine even with standard KV (see `engines.md`). Depth
tests skipped. **Side finding**: `q8_0/q6_0` is near-lossless (+4% KLD vs. q8/q8) but q6_0 KV
exists only in BeeLlama/ik_llama.cpp — idea, not scheduled.

## Weight quantization matrix (perplexity, tok/s)

ROCm, KV q8_0/q8_0. `llama-bench` + `llama-perplexity` (wikitext-2-raw, ci corpus from ggml-org),
relative indicator between quantizations of the same base model — mixes finetune effect and
quantization effect on the finetuned variants (HauhauCS, RVN).

| Model | GGUF size | Perplexity ± | tg128 (0 / 16K) | pp512 (0 / 16K) | MTP n=2, 128K |
|---|---:|---:|---:|---:|---:|
| GSQ-RCO IQ3_XXS-mtp | 10.4 GB | 6.948 ± 0.087 | 40.5 / 38.1 | 942 / 817 | 56.3 tok/s (50%) |
| GSQ-RCO IQ3_S | 11.8 GB | 6.734 ± 0.084 | 39.1 / 36.8 | 992 / 850 | — |
| **GSQ-RCO IQ3_S-mtp** | 12.1 GB | **6.734 ± 0.084** | 39.3 / 37.0 | 980 / 851 | **62.2 tok/s (62%)** |
| HauhauCS Aggressive IQ4_XS (finetune) | 15.7 GB | 6.823 ± 0.086 | 37.4 / 35.4 | 1013 / 862 | — (no MTP) |
| RVN Q4_K_M-mtp (finetune) | 17.0 GB | 6.710 ± 0.084 | 34.1 / 32.4 | 980 / 845 | 48.2 tok/s (55%) |
| Q4_K_M | 17.1 GB | **6.639 ± 0.083** | 34.2 / 32.6 | 946 / 836 | — (no MTP) |

- IQ3_S and IQ3_S-mtp give **the same perplexity**: the MTP head doesn't change the base model. The
  no-MTP file adds nothing on top of the MTP one.
- IQ3_S vs. IQ3_XXS: 3% better perplexity and **faster with MTP** (accepts more drafts), even though
  IQ3_XXS is 3% faster without MTP.
- On RDNA3, IQ quantizations generate faster than K quantizations per byte of model. Q4_K_M
  (17.1 GB) generates slower than IQ4_XS (15.7 GB) despite being a smaller quant tier. Matches a
  third-party report on a different card (below).

## Third-party quantization quality references (unverified locally, cited as context)

- [ISTA-DASLab GSQ-RCO model card](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF):
  WikiText2 BF16 7.05 → IQ3_S 7.07 → IQ3_XXS 7.20. IQ3_S keeps 99.8% of the average task score
  (AIME25 and LiveCodeBench equal to BF16). Our local PPL (6.734 vs. 6.948, IQ3_S vs. IQ3_XXS) moves
  in the same direction.
- Kingy.ai (KLD vs. BF16 on a different IQ3_S, AD-IQ3_S): 0.0325, top-1 92.4%. This is the figure
  used above to compare against the KV-quantization KLD.
- No quantization was found with published numbers beating GSQ-RCO IQ3_S in the 12-15 GB class.
- [`llama.cpp` discussion #23470](https://github.com/ggml-org/llama.cpp/discussions/23470) (KV
  asymmetry, different model): "q4_0 on K alone reproduces the full collapse, while q4_0 on V alone
  changes 1/500 responses" — **K is sensitive, V tolerates much more**. On Qwen3.8-27B at 65K,
  "q8_0/q5_1 is only 19% worse for about 15% less cache" — consistent with the local +27% at 32K
  above. A separate report (localbench) found q4_0 "concentrates nearly all damage in long
  documents (KL 0.581)".
- [sergiiob: KV cache quantization on Intel Arc B70](https://sergiiob.dev/posts/b70-kv-cache-quantization-context-ceilings/)
  (SYCL, different hardware): asymmetric KV (K q8_0 + V q4_1) as their standard, halving KL vs.
  q5_0/q4_1. Consistent with the q8_0/q5_1 direction used here. Note: the official ROCm binary needs
  `-DGGML_CUDA_FA_QUANTS` to get a FlashAttention kernel for mixed types at all — see `engines.md`.
- [sergiiob: RX 7800 XT benchmarks](https://sergiiob.dev/posts/rx7800-xt-llama-cpp-benchmarks-moe-context/)
  (gfx1101, ROCm 6.4.4): IQ quantizations outperform K quantizations on RDNA3 — **confirmed** by the
  local matrix above.

## History

- **2026-09-24**: initial KLD measurement (32K context) and weight-quantization matrix (6
  quantizations, ROCm). Conclusion: q8/q8 and q8/q5_1 both safe, q4_0 discarded on quality grounds
  for KV; IQ3_S-mtp selected as the model.
- **2026-09-25**: VEC-vs-TILE numerical path caveat added (see above); does not change the KLD
  conclusion, flags a caveat for future work.
- **2026-09-26**: BeeLlama v0.4.7 KVarN KLD measured — discarded (~2.7x the KLD of q8/q8 at every
  bit width); `q8_0/q6_0` noted as near-lossless but not adopted (BeeLlama-only KV type).
