# Inkling-2-Mini (Thinking Machines) on llama.cpp

## Current state (2026-11-22, first run: upstream cannot fit 262K, parked)

- **Installed: the file only.** `Inkling-2-Mini-Uncensored-AD-Q4_K.gguf` (15.39 GiB, sha256
  `36e99f1f…`) and its F16 `mmproj` sit in the model folder; there is **no `models.toml` entry**, no
  launch profile and no adopted engine for it. Parked by the user on 2026-11-22 ("park it without
  configuring it") until Qwen4 ([`DECISIONS.md`](../DECISIONS.md), 2026-11-22).
- **Fit, measured**: **upstream b12633 cannot run 262K on this card.** `--fit` projects 31,855 MiB
  against 24,358 MiB free, and 12,765 MiB of that is the **compute buffer** for the dense
  relative-bias attention mask, not KV (`q8_0`/`q5_1` is only 3,810 MiB). With all MoE moved to the
  CPU it still needs 1,799 MiB more, so `--fit` ends at 25/49 layer parts on the GPU: 4.5 tok/s
  generation, 10.0 tok/s prefill.
- **The GodGMN fork fits 262K**: `GodGMN/llama.cpp` branch `inkling-rdna3` (`cb0e46960`, tag `b12600`
  + 6 commits) computes the bias inside the FA kernel and runs 262K at 42.0 tok/s
  (`q8_0`/`q8_0`, 22,423 MiB) and 41.2 tok/s (`q8_0`/`q5_1`, 21,750 MiB); 64K `f16` 48.2 → 46.3
  tok/s at 19,022 MiB against upstream's 26.5 tok/s at 22,270 MiB
  ([results](../../results/20261122-inkling-uncensored-ad-q4k/README.md)).
- **Smoke only**: one 33-token prompt, two turns per arm, temperature 0, one run per arm. No long
  fill, no retrieval, no refusal check, no coding suite, no `models.toml` entry. `llama-bench` on the fork (q8_0/q8_0): tg128 50.1 / 45.5 / 26.2 tok/s at depth 0 / 65,536 / 196,608 (upstream b12633 f16 depth 0: 26.7).
- **Uncensored, unmeasured**: the measured file is AtomicChat's uncensored AD-Q4_K; the third-party
  refusal and quality numbers in the survey below were not reproduced here.
- **Decision**: parked without a config. Resume triggers in
  [Status](#status-parked-2026-11-22-resume-triggers).
- **Strata became an option (desk review, not installed)**: v0.2.19 ships `strata-inkling` 0.1.65
  and three SQ packs, of which **SQ-20 is 18.02 GiB "for 24 GiB+ GPUs"**. It would fit this card with
  little room left for KV, no latency number exists for gfx1100, and no Flash-Next or Inkling set is
  installed here ([review](strata-qwen-flash-next.md#review-2026-11-22-v0218-and-v0219)).
- **Inkling-2-Small**: still not a candidate: 594B total / 17B active, smallest GGUF ~150 GB
  (peasantsmith) against ~55 GiB of VRAM + RAM.
- **Next session**: [resume checklist](#resume-checklist).

## Quant survey (2026-11-22)

Uncensored and abliterated options, plus the formats that cannot run here. Card figures are the
providers' own and use different references per repo, so KLD values are **not rankable against each
other**; every header in the "format" column was read directly by HTTP range on 2026-11-22.

| Repo | File (GiB) | Published quality (card) | Format / runtime | Verdict here |
|---|---|---|---|---|
| [AtomicChat Uncensored](https://huggingface.co/AtomicChat/Inkling-2-Mini-Uncensored-GGUF) (**chosen**) | AD-Q4_K 15.39 (repo also lists AD-IQ2_M, AD-IQ3_S, AD-Q8_0 and the LoRA + mmproj) | vs. BF16: KLD 0.0115, 95.6% same top-1, MMLU 80.65 → 79.15 | `inkling2_loop`, 24 blocks, 0 scale tensors → stock upstream | **Measured**: fits 262K only on the GodGMN fork; the best published quality of the three uncensored files that load upstream |
| nokeepai Unbound v2 | Q4_K_M 16.56 | refusals 0.4% / 1.1% and useful answers 78.7% / 83.4% (two arms), KLD 0.0318; the same card's head-to-head puts AtomicChat's LoRA at 51.6% / 56.3% useful — author-run comparison, conflict of interest, not re-checked | `inkling2_loop`, 24 blocks | 1.2 GiB larger with ~3x the KLD of the chosen file; not downloaded |
| yanauto / kelsey1337 heretic | not recorded | refusals 100% → 6%, MMLU 78.7 → 78.0, KL 0.049 | `inkling2_loop`, 24 blocks | Abliterated, but the heaviest quality cost of the three; not downloaded |
| [mudler APEX](https://huggingface.co/mudler/Inkling-2-Mini-APEX-GGUF) | I-Quality 18.69 (KLD 0.0063), Compact 13.13 (KLD 0.0245) | card | `inkling2_loop`, 24 blocks, 0 scale tensors; stock-llama.cpp support not checked | Best published KLD, but I-Quality is 18.69 GiB: with 3.7 GiB of 262K KV and any compute buffer it exceeds the card, so ≤190K at best. Compact is smaller with 4x the KLD |
| abenzerps GSQ-RCO | not recorded | none published; part MXFP4 | `inkling2_loop`, 24 blocks, 0 scale tensors | Unmeasured quality; no reason to prefer it over the chosen file |
| Harsha001 ROCmFPX | not recorded | none published | `inkling2`, **48 blocks**, custom type 100, 169 `.scale` tensors; its `inkling2-mini` branch was not found; card says CPU-only validation | Not runnable: needs that fork's custom types and it has no gfx1100 result |
| Kujira CHiPS (UD-Q4_K_XL) | not recorded | none published | **NVFP4** + 40 per-expert scale tensors | Not runnable on RDNA3: FP4 weights need a dequant/NVFP4 path the 48-block layout also lacks upstream |
| onemunanoyo, JoaoZaokk, Unsloth UD | — | — | NVFP4 or CUDA-only | Same as above |
| Makdok AMD-GGUF | — | 7900 XTX numbers | author's own fork, Windows | Not reproducible here |

- The base (non-uncensored) quants surveyed on 2026-11-20 (ggml-org, Unsloth, AtomicChat presets)
  are unchanged in [history](#published-quants-2026-11-20).
- Rows without a size were read from the Hugging Face listing only; their repo id was not kept in
  the session log, so they are named, not linked.

## Runtime findings (2026-11-22)

| | Upstream b12633 (`9c10c94e1`) | GodGMN fork (`cb0e46960`) |
|---|---|---|
| 262K fit | `--fit` projection 31,855 MiB vs. 24,358 free; MoE forced to the CPU; 4.5 tok/s tg, 10.0 pp | fits on the card: 22,423 MiB (`q8_0`/`q8_0`) / 21,750 MiB (`q8_0`/`q5_1`) |
| 262K tg | 4.5 tok/s (MoE offloaded) | 42.0 / 42.7 tok/s (`q8_0`/`q8_0`), 41.2 / 42.3 (`q8_0`/`q5_1`) |
| 64K `f16` KV | 26.5 tok/s, 22,270 MiB | 48.2 → 46.3 tok/s, 19,022 MiB |
| Compute buffer at 262K | 12,765 MiB (the dense relative-bias mask) | not materialized: bias inside the FA kernel (`INK_REL_BIAS`, `INK_FA_REL_BIAS`, fused conv/mix kernels) |

- **Root cause of the upstream wall**: upstream materializes a dense relative-bias attention mask
  per layer, so the compute buffer (12,765 MiB) is 3.4x the 262K KV cache (3,810 MiB). Moving the
  MoE experts to the CPU does not help, because the deficit is in the attention buffer, not in the
  weights. KV type is therefore irrelevant to the fit problem: `q8_0`/`q8_0` at 262K died the same
  way as `q8_0`/`q5_1` without `--fit` (`failed to allocate compute buffers`).
- **Quantized KV is degraded on upstream, not just slow**: the Unsloth report of 8-bit KV using more
  VRAM than `f16` came from Inkling's attention kernel not supporting a quantized KV cache; their fix
  (banded FA + three fused CUDA kernels) is fork-only
  ([unslothai/llama.cpp PR #386](https://github.com/unslothai/llama.cpp/pull/386), benchmarked on
  CUDA). Nothing in b12633 carries it.
- **Fit arithmetic now has one measured point**: 262K `q8_0`/`q5_1` = 3,712 MiB of KV (K `q8_0`
  2,176.00 + V `q5_1` 1,536.00 over the 8 global applications) + 90.62 MiB of sliding-window cache,
  i.e. 3,803 MiB, against the 3.6 GiB estimate in [KV and fit
  arithmetic](#kv-and-fit-arithmetic).
- **Third-party fork claims** (author's own RX 7900 XTX, ROCm 7.2.1, IQ4_NL): 64.0 tok/s `tg128` vs.
  31.9 on b12600, `pp4096` 1,802 vs. 854, and 393,216 context with `q4_0` KV. Our numbers above are
  lower on `tg` and are a different file, KV type and runtime; treat the fork's figures as its
  author's, not as ours ([BUILD.md](../../results/20261122-inkling-rdna3-fork/BUILD.md)).

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
  Check the vendor card again before configuring (AGENTS.md rule). The smoke runs used greedy on purpose.

## KV and fit arithmetic

Every loop pass keeps its own KV ("Each pass keeps its own KV and convolution cache", ggml-org card), so the
growing KV comes from 8 global applications (layer 5 once, 11 and 17 three times each, 23 once):
8 x 2 x 8 heads x 128 = 16,384 values per token, 32 KiB/token at `f16`. The 40 local applications hold
about 240 MiB at `f16` regardless of context.

| KV (K/V) | 262K | 512K | 1M |
|---|---|---|---|
| f16 | 8 GiB | 16 GiB | 32 GiB |
| q8_0/q8_0 | 4.25 GiB | 8.5 GiB | 17 GiB |
| q8_0/q5_1 (repo default) | 3.6 GiB (**measured 3,803 MiB**, 2026-11-22) | 7.25 GiB | 14.5 GiB |
| q4_0/q4_0 (discarded, [DECISIONS](../DECISIONS.md) 2026-09-24) | 2.25 GiB | 4.5 GiB | 9 GiB |

Fit = file + KV + compute buffer against about 23 GiB usable. The compute buffer is where the
2026-11-20 estimate was wrong: it assumed ~1.5 GiB, and upstream b12633 needs **12,765 MiB** at 262K
for the dense relative-bias mask, while the GodGMN fork stays near a conventional size.

- **262K, `q8_0`/`q5_1`, upstream**: does not fit. 15,279 (file) + 3,810 (KV) + 12,765 (compute) =
  31,855 MiB.
- **262K, `q8_0`/`q8_0` or `q8_0`/`q5_1`, GodGMN fork**: fits, 22,423 / 21,750 MiB measured.
- **512K / 1M, any engine**: needs a ≤12.7 GiB file plus `q4_0` KV or better; not attempted, and the
  fork's `q4_0` figure is only its author's.
- Mixed K/V pairs need a HIP build with `GGML_CUDA_FA_QUANTS` ([ENGINES.md](../ENGINES.md)); on the
  fork the pair `q8_0`/`q5_1` is compiled but not covered by its own test cases.

## GGUF formats and engine support

| File | `general.architecture` (`block_count`) | `*exps.scale` tensors | Loads on |
|---|---|---|---|
| AtomicChat Uncensored AD-Q4_K (**measured**) | `inkling2_loop` (24) | 0 | upstream b12591+; measured on b12633 |
| nokeepai Unbound v2, yanauto/kelsey1337 heretic, mudler APEX, abenzerps GSQ-RCO | `inkling2_loop` (24) | 0 | upstream, by header; not run |
| ggml-org IQ4_NL | `inkling2_loop` (24) | 0 | upstream |
| Unsloth UD-Q4_K_XL (root and `Shard_Rewrite/`) | `inkling2` (48) | 40 | Unsloth fork only |
| Kujira CHiPS UD-Q4_K_XL | not recorded | 40, NVFP4 | nowhere here: NVFP4 weights |
| Harsha001 ROCmFPX | `inkling2` (48), custom type 100 | 169 `.scale` | that fork only |

- Upstream support: [PR #32694](https://github.com/ggml-org/llama.cpp/pull/32694), merged 2026-11-20
  22:01 UTC (`29b52d3`); first release b12591. [#32704](https://github.com/ggml-org/llama.cpp/pull/32704)
  (re-share the loop pass slots after the per-expert scale pass) merged 2026-11-21 and is in b12633,
  so the scale-tensor question is settled upstream; the files that carry them still need a layout the
  upstream loader accepts, which was not retested here.
- `inkling2_loop` files need no patch, which is why the chosen file runs on stock b12633 at all.
- Open: NVFP4 kernels on HIP/gfx1100 (RDNA3 has no FP4 hardware) — untouched by this run, and the
  reason the NVFP4-backed quants stay unusable.

## Status: parked (2026-11-22, resume triggers)

Parked without a config: the model needs a third-party fork for the one thing that matters here
(262K), and the user's plan is to wait for Qwen4 rather than maintain a second engine
([`DECISIONS.md`](../DECISIONS.md), 2026-11-22). Nothing is installed beyond the GGUF.

Resume when any of these happens:

1. **Upstream merges an in-kernel relative bias** (the fork's `INK_REL_BIAS` / FA-with-bias path) or
   any change that stops materializing the dense mask; that alone is worth a 262K re-check.
2. **Unsloth's banded-FA quantized-KV work reaches upstream** (`unslothai/llama.cpp` PR #386, fork
   only): it is the fix for quantized KV on this architecture, which we need at 262K.
3. **GodGMN's Inkling kernels are proposed or merged upstream** (the fork documents them; no
   upstream PR was found on 2026-11-22).
4. **Qwen4 has shipped and left room**, or a Strata `strata-inkling` release reports gfx1100 latency
   (today only the pack sizes are published).

A re-check is one `--fit` at 262K plus the [resume checklist](#resume-checklist); the numbers to beat
are 42.0 tok/s (`q8_0`/`q8_0`) and 22,423 MiB on the fork.

## Resume checklist

1. Re-survey quants: Unsloth Dynamic, ISTA-DASLab, ggml-org, AtomicChat AD mid-range, and uncensored
   or abliterated variants (HF API `base_model:quantized:thinkingmachines/Inkling-2-Mini` and
   `finetune:`). Prefer `inkling2_loop` (24 blocks, no scale tensors) while the 48-block layout needs
   a fork.
2. Confirm the trigger above: `--fit` a 262K run on the latest upstream release and read the compute
   buffer line before downloading anything new.
3. Read the chosen file's header, then follow [`sop/new-model.md`](../sop/new-model.md): vendor card,
   `--help` of the exact binary, `--fit` at 262K with `q8_0`/`q5_1`, smoke test, then KLD of the
   candidates against ggml-org Q8_0 (25.9 GiB, partial offload).
4. Only if a full run is wanted: `llama-bench` `pp4096`/`tg128` at depths 0, 65,536 and 196,608 (none
   exists for this model yet), then retrieval and the coding suite before any `models.toml` entry.
5. Record the run under `results/` and the decision in [`DECISIONS.md`](../DECISIONS.md).

## History

### Current state (2026-11-20, desk review, nothing run)

Superseded 2026-11-22 by the measurements above; kept as recorded.

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

### Published quants (2026-11-20)

Superseded 2026-11-22 by the survey above (the uncensored and abliterated files did not exist in this
list); kept as recorded.

| Repo | Files and sizes (GiB) | Published quality | Runtime |
|---|---|---|---|
| [unsloth](https://huggingface.co/unsloth/Inkling-2-Mini-GGUF) | UD-IQ1_S 7.23 … UD-IQ3_XXS 10.86, UD-Q3_K_XL 12.70, UD-IQ4_XS 14.65, UD-Q4_K_M 15.47, UD-Q4_K_XL 16.42, UD-Q8_K_XL 21.30 | vs. UD-Q8_K_XL (7 domains): Q4_K_XL KLD 0.0107 / 98.0% top-1, IQ3_XXS 0.0269 / 94.7% | Unsloth fork |
| [ggml-org](https://huggingface.co/ggml-org/Inkling-2-Mini-GGUF) | IQ4_NL 16.42 (4-bit experts in layers 0-19, rest Q8_0, imatrix), Q8_0 25.91, BF16 48.64 | vs. BF16 (wikitext-2, 40 x 512): IQ4_NL 0.0095 / 95.5%, Q8_0 0.0030 / 97.6% | upstream b12591+ |
| [AtomicChat](https://huggingface.co/AtomicChat/Inkling-2-Mini-GGUF) | AD-IQ1_S 6.41 … AD-IQ3_XXS 11.71, Q4_K_M 16.19, Q5_K_M 18.45, Q6_K 21.80, Q8_0 25.83 (presets without imatrix) | vs. BF16 (30 languages, 87 x 4096): AD-IQ3_XXS 0.027 / 93.3%; presets unmeasured; mid-range imatrix quants "coming next" | draft PR #32695 |

- The expert down projection has rows of 1152, which k-quants cannot take; llama.cpp swaps the type there
  (AtomicChat card), so a "Q4_K_M" uses Q8_0/Q5_0 for it.
