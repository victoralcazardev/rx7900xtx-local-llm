# Inkling-2-Mini (Thinking Machines) on llama.cpp

## Current state (2026-11-20, desk review, nothing run)

- **Installed: nothing.** No GGUF downloaded, no engine built, no `models.toml` entry. Paused by the user on
  2026-11-20 to wait for a better quant (Unsloth Dynamic v3/v3.1, ISTA-DASLab or another provider), ideally an
  uncensored or abliterated one, and an updated upstream llama.cpp.
- **Fit (arithmetic, unmeasured)**: a 16.4 GiB 4-bit file plus 262K context with KV `q8_0/q5_1` is about
  21.5 GiB; the full 1M context does not fit with an acceptable KV type ([fit](#kv-and-fit-arithmetic)).
- **Runnable today on upstream without a fork**: only `ggml-org/Inkling-2-Mini-GGUF` IQ4_NL
  ([formats](#gguf-formats-and-engine-support)).
- **Strata**: not supported (Strata v0.2.11 knows Qwen3.8-Flash-Next, Qwen3.6-35B-A3B and DeepSeekV4.1-Flash
  only), and not needed: the model fits in VRAM.
- **Uncensored**: none with weights yet ([quants](#published-quants-2026-11-20)).
- **Watch** (user decision 2026-11-20, [DECISIONS](../DECISIONS.md)): upstream loading the 48-block `inkling2`
  layout (Unsloth, AtomicChat; draft PR [#32695](https://github.com/ggml-org/llama.cpp/pull/32695)) or the per-expert
  scale fix for loop passes; Unsloth or AtomicChat files re-uploaded as `inkling2_loop`; uncensored weights.
- **Inkling-2-Small**: not a candidate: 594B total / 17B active, smallest GGUF ~150 GB (peasantsmith) against
  ~55 GiB of VRAM + RAM (scout, card and quant READMEs, 2026-11-20).
- **Next session**: [checklist](#resume-checklist).

## Model facts

Source: [`thinkingmachines/Inkling-2-Mini`](https://huggingface.co/thinkingmachines/Inkling-2-Mini) card and
`config.json` (read 2026-11-20).

- 26.2B total, 3.4B active (5.4B effective per token), 128 experts with 8 active, no shared expert. Text and
  image input. Apache-2.0. Released 2026-11-20.
- Looped transformer: 24 layers of weights; layers 6-17 run 3 passes (`loop_config`), so 48 layer applications
  per token. Compute per token is higher than the active parameter count suggests.
- Attention: 4 global layers (5, 11, 17, 23); the other 20 are local with `sliding_window_size` 1024.
  `num_key_value_heads` 8, `head_dim` 128.
- Native context 1,048,576 (`model_max_length`). Checkpoint: NVFP4 experts in layers 0-19, MXFP8 in 20-23.
- MTP head in the checkpoint (`mtp_config`, 3 layers); Unsloth also ships a `dspark` drafter. Neither checked.
- Card warnings: may get stuck in long reasoning loops (limit output tokens); `reasoning_effort` minimum does
  not fully disable reasoning; weaker in long multi-turn conversations.
- Sampling (Unsloth guide, from the vendor's generation config): `temp 1.0, top-p 1.0, top-k 0, min-p 0.0`.
  Check the vendor card again before configuring (AGENTS.md rule).

## KV and fit arithmetic

Every loop pass keeps its own KV ("Each pass keeps its own KV and convolution cache", ggml-org card), so the
growing KV comes from 8 global applications (layer 5 once, 11 and 17 three times each, 23 once):
8 x 2 x 8 heads x 128 = 16,384 values per token, 32 KiB/token at `f16`. The 40 local applications hold
about 240 MiB at `f16` regardless of context.

| KV (K/V) | 262K | 512K | 1M |
|---|---|---|---|
| f16 | 8 GiB | 16 GiB | 32 GiB |
| q8_0/q8_0 | 4.25 GiB | 8.5 GiB | 17 GiB |
| q8_0/q5_1 (repo default) | 3.6 GiB | 7.25 GiB | 14.5 GiB |
| q4_0/q4_0 (discarded, [DECISIONS](../DECISIONS.md) 2026-09-24) | 2.25 GiB | 4.5 GiB | 9 GiB |

Fit = file + KV + about 1.5 GiB compute buffer (estimate; logits alone are ~0.4 GiB per 512-token ubatch at a
201K vocabulary) against about 23 GiB usable:

- 262K, `q8_0/q5_1`: a 16.4 GiB file is about 21.5 GiB. Fits, about 2 GiB margin.
- 512K, `q8_0/q5_1`: a 12.7 GiB 3-bit file is about 21.5 GiB; a 16.4 GiB file does not fit.
- 1M: fits only with KV `q4_0` and a 3-bit file, or with a 1-bit file. Not worth it.
- Mixed K/V pairs need a HIP build with `GGML_CUDA_FA_QUANTS` ([ENGINES.md](../ENGINES.md)); a stock prebuilt
  binary likely accepts only `q8_0/q8_0` (about 22.2 GiB at 262K).

## GGUF formats and engine support

Header bytes read directly (first 12 MB of each file, 2026-11-20):

| File | `general.architecture` (`block_count`) | `*exps.scale` tensors | Loads on upstream b12591 |
|---|---|---|---|
| ggml-org IQ4_NL | `inkling2_loop` (24) | 0 | yes |
| Unsloth UD-Q4_K_XL (root) | `inkling2` (48) | 40 | no: needs the Unsloth fork `b12568-mix-8eebad4` |
| AtomicChat Q4_K_M | `inkling2` (48) | 0 | no: needs draft PR [#32695](https://github.com/ggml-org/llama.cpp/pull/32695) |

- Upstream support: [PR #32694](https://github.com/ggml-org/llama.cpp/pull/32694), merged 2026-11-20 22:01 UTC
  (`29b52d3`); first release b12591. Upstream registers both `inkling2` and `inkling2_loop`, but the 48-block
  `inkling2` files fail with `'blk.24.attn_q.weight' not found`
  ([Unsloth discussion #6](https://huggingface.co/unsloth/Inkling-2-Mini-GGUF/discussions/6), field).
- Unsloth keeps the original NVFP4 experts with per-expert scales. Its `Shard_Rewrite/` copies use the upstream
  layout, but their README says stock #32694 "needs one fix first: re-share the loop pass slots after the
  per-expert scale pass. Without it the later loop passes lose their per-expert scales and the output is
  wrong." None of the 9 merged commits addresses it and the slot copies are made before the scale pass
  (hypothesis, read by a research subagent; not re-checked). Files without scale tensors are not affected.
- Unsloth's fork ships prebuilt ROCm binaries per GPU family; `gfx110X` is RDNA3 (the 7900 XTX is gfx1100).
  Build flags unknown.
- Open: NVFP4 kernels on HIP/gfx1100 (RDNA3 has no FP4 hardware) — speed or support unknown; this decides
  whether NVFP4-preserving quants are usable here.

## Published quants (2026-11-20)

Survey of the Hugging Face API (`base_model:quantized:`, `finetune:` and name searches). KLD values use
different references and corpora per provider and cannot be ranked against each other.

| Repo | Files and sizes (GiB) | Published quality | Runtime |
|---|---|---|---|
| [unsloth](https://huggingface.co/unsloth/Inkling-2-Mini-GGUF) | UD-IQ1_S 7.23 … UD-IQ3_XXS 10.86, UD-Q3_K_XL 12.70, UD-IQ4_XS 14.65, UD-Q4_K_M 15.47, UD-Q4_K_XL 16.42, UD-Q8_K_XL 21.30 | vs. UD-Q8_K_XL (7 domains): Q4_K_XL KLD 0.0107 / 98.0% top-1, IQ3_XXS 0.0269 / 94.7% | Unsloth fork |
| [ggml-org](https://huggingface.co/ggml-org/Inkling-2-Mini-GGUF) | IQ4_NL 16.42 (4-bit experts in layers 0-19, rest Q8_0, imatrix), Q8_0 25.91, BF16 48.64 | vs. BF16 (wikitext-2, 40 x 512): IQ4_NL 0.0095 / 95.5%, Q8_0 0.0030 / 97.6% | upstream b12591+ |
| [AtomicChat](https://huggingface.co/AtomicChat/Inkling-2-Mini-GGUF) | AD-IQ1_S 6.41 … AD-IQ3_XXS 11.71, Q4_K_M 16.19, Q5_K_M 18.45, Q6_K 21.80, Q8_0 25.83 (presets without imatrix) | vs. BF16 (30 languages, 87 x 4096): AD-IQ3_XXS 0.027 / 93.3%; presets unmeasured; mid-range imatrix quants "coming next" | draft PR #32695 |

- The expert down projection has rows of 1152, which k-quants cannot take; llama.cpp swaps the type there
  (AtomicChat card), so a "Q4_K_M" uses Q8_0/Q5_0 for it.
- Uncensored: [AtomicChat/Inkling-2-Mini-Uncensored-GGUF](https://huggingface.co/AtomicChat/Inkling-2-Mini-Uncensored-GGUF)
  has only the mmproj ("in progress"); `IndrasMirror/Inkling-2-Mini-XQ-Uncensored` is an empty draft for the
  Xolotl runtime. No huihui, heretic, mradermacher, bartowski or ISTA-DASLab Mini repo found.
- Own option: quantize ggml-org BF16 with its published `imatrix.gguf` to Q5_K_M (~18.5 GiB, fits about
  128-200K with `q8_0/q5_1`).

## Resume checklist

1. Re-survey quants: Unsloth Dynamic v3/v3.1, ISTA-DASLab, ggml-org, AtomicChat AD mid-range, and uncensored or
   abliterated variants (HF API `base_model:quantized:thinkingmachines/Inkling-2-Mini` and `finetune:`).
2. Read the chosen file's header: `inkling2_loop` and 24 blocks loads on upstream; scale tensors need the
   per-expert scale fix confirmed in upstream first.
3. Build the latest upstream release for ROCm gfx1100 with `GGML_CUDA_FA_QUANTS` ([`sop/update-engine.md`](../sop/update-engine.md)).
4. Follow [`sop/new-model.md`](../sop/new-model.md): vendor card, `--help` of the exact binary, `--fit` at 262K
   with `q8_0/q5_1`, smoke test, then KLD of the candidates against ggml-org Q8_0 (25.9 GiB, partial offload).
5. Record the run under `results/` and the decision in [`DECISIONS.md`](../DECISIONS.md).
