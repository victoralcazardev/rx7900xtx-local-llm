# Qwen3.8-27B — candidate quant inventory

Architecture and provenance research written before the GPU was installed. The KV-size estimates
and config table below are **arithmetic, not measurement** — for real numbers (throughput, VRAM,
quality) see `docs/measurements/` and `models.toml`, which now reflects what was actually measured
and adopted.

Files covered (GGUF, relative to `models_root`):

- `Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf` (15.7 GB) — not adopted (see below)
- `Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf` (11.8 GB) — was `qwen38-iq3s`, no MTP
- `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` (12.1 GB) — `qwen38-iq3s-mtp`, **adopted model**
- `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` (10.4 GB) — was `qwen38-iq3xxs-mtp`
- `RVN-Q4_K_M-multilingual-mtp.gguf` (17.0 GB) — was `qwen38-rvn-mtp`
- `mmproj-Qwen3.8-27B-BF16.gguf` (vision projector, 0.93 GB)

**2026-09-26**: `models.toml` now carries only `qwen38-iq3s-mtp` (single model, single profile —
one best default, no overlapping alternatives, see `docs/DECISIONS.md`). The other three text
models above were removed from the manifest; they stay documented here for quant-comparison
provenance.

## 1. Local metadata (all text models share the base architecture)

Extracted with the `gguf` Python package, reading only the GGUF's KV header — no tensors loaded,
no server started.

| Key | Value (all 5 text models) |
|---|---|
| `general.architecture` | `qwen35` |
| `qwen35.block_count` | **64** in the non-`-mtp` files (`IQ3_S`); **65** in the `-mtp` files and in HauhauCS (1 extra MTP layer) |
| `qwen35.embedding_length` | 5120 |
| `qwen35.attention.head_count` | 24 |
| `qwen35.attention.head_count_kv` | 4 |
| `qwen35.attention.key_length` / `value_length` | 256 / 256 |
| `qwen35.full_attention_interval` | 4 → only 1 of every 4 layers carries "real" attention; the rest are SSM/linear layers |
| `qwen35.ssm.conv_kernel` / `.group_count` / `.inner_size` / `.state_size` / `.time_step_rank` | 4 / 16 / 6144 / 128 / 48 (present in all 5 files → confirms a hybrid with recurrent state, not KV that grows in those layers) |
| `qwen35.rope.dimension_count` | 64 (of a 256 head_dim → partial rotary, matches the official card) |
| `qwen35.context_length` | 262144 |
| `qwen35.nextn_predict_layers` | `1` **only** in the `-mtp` files (and in HauhauCS, even though its filename doesn't say so) |
| `general.sampling.*` (temp/top_p/top_k/min_p/penalty_repeat) | `1.0` / `0.95` / `20` / `0.0` / `1.0` in the 4 Qwen-derived files with the full key set; `RVN` only carries `temp`/`top_k`/`top_p`, no `min_p` |
| `tokenizer.chat_template` | 8,952 characters, contains `<think>` and `enable_thinking`, does **not** contain `channel` (not Gemma's format) |

The hybrid indicator is the `ssm.*` keys + `full_attention_interval`, not a literal `hybrid` tag.

### Per file

| File | `general.name` | `general.file_type` (GGUF code) | Embedded `base_model` | MTP (`nextn_predict_layers`) |
|---|---|---|---|---|
| HauhauCS IQ4_XS | `Qwen3.8-27B-Uncensored-HauhauCS-Aggressive` | 30 = `IQ4_XS` | `Qwen/Qwen3.8-27B` | Yes (1) |
| GSQ-RCO IQ3_S | `Qwen3.8-27B GSQ-RCO` | 26 = `IQ3_S` | `Qwen/Qwen3.8-27B` | No |
| GSQ-RCO IQ3_S-mtp | `Qwen3.8-27B GSQ-RCO` | 26 = `IQ3_S` | `Qwen/Qwen3.8-27B` | Yes (1) |
| GSQ-RCO IQ3_XXS-mtp | `Qwen3.8-27B GSQ-RCO` | **26 = `IQ3_S`** (not XXS!) | `Qwen/Qwen3.8-27B` | Yes (1) |
| RVN Q4_K_M-multilingual-mtp | `Qwen38 Ara v5` | 15 = `Q4_K_M` | not embedded | Yes (1) |

**Finding worth noting**: the `IQ3_XXS-mtp` file reports `general.file_type=26` (`IQ3_S`), not 23
(`IQ3_XXS`). GSQ-RCO assigns a different quantization type per tensor, so `general.file_type` is
just a nominal pipeline label and **does not describe the actual mix** — don't trust that key for
these files; the file name and the model card's own table are the correct source for which build is
which. (Code mapping verified in llama.cpp's `LlamaFileType` enum,
`gguf-py/gguf/constants.py`.)

## 2. Hugging Face provenance (verified by opening each raw README, not a search summary)

- **Qwen/Qwen3.8-27B** (official card): https://huggingface.co/Qwen/Qwen3.8-27B
- **ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF**: https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF
- **HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF**: https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF
- **0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF** (the actual repo for the RVN file): https://huggingface.co/0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF

Method note: a first pass with a web-search/fetch tool that summarizes with an intermediate model
returned figures and claims for HauhauCS and RVN that **did not match** the raw README (it mixed up
variants and invented details of a chained "RVN" fork that isn't the actual repo for our file).
Everything below is verified against the raw Markdown — a research subagent's summary is a
hypothesis, not a fact (see `AGENTS.md`).

### Qwen3.8-27B (official)

Architecture confirmed in the official card ("Model Overview"): `16 × (3 × (Gated DeltaNet → FFN) →
1 × (Gated Attention → FFN))`, 64 language layers, Gated Attention with 24 Q heads / 4 KV heads /
head_dim 256 / RoPE dim 64; Gated DeltaNet with 48 V heads / 16 QK heads / head_dim 128. This
matches the local metadata's `full_attention_interval=4` exactly: of the 64 blocks, **16 carry real
attention** (growing KV) and **48 are DeltaNet** (fixed-size recurrent state). Native context
262,144, extensible to 1,000,000 with YaRN.

Recommended sampling (matches what's baked into the GGUF):

- Thinking mode (default): `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0.0`,
  `presence_penalty=0.0`, `repetition_penalty=1.0`.
- Instruct/no-thinking mode: `temperature=0.7`, `top_p=0.80`, `top_k=20`, `min_p=0.0`,
  `presence_penalty=1.5`, `repetition_penalty=1.0`, `enable_thinking=false`.
- `reasoning_effort`: `xhigh` (default) / `medium` / `low`. `preserve_thinking` on by default.

YaRN (only needed beyond 262,144, not tested on this hardware): `rope_type: yarn`, `factor: 4.0`,
`original_max_position_embeddings: 262144`, `partial_rotary_factor: 0.25`.

MTP: the official card states "trained with multiple steps" — the MTP head is part of official
training, not a third-party addition.

### GSQ-RCO (ISTA-DASLab)

**GSQ** = *Gumbel-Softmax Quantization*: post-training scalar quantization that learns per-coordinate
grid assignments via Gumbel-Softmax relaxation. **RCO** = *Riemannian Constrained Optimization*:
assigns a GGUF quantization type per tensor under a total size budget, formulated as a Riemannian
manifold in logit space for gradient-based optimization without tuning constraint hyperparameters.
Both from the Deep Algorithms and Systems Lab (DASLab), ISTA. Papers: arXiv:2604.18556 (GSQ) and
arXiv:2605.00649 (RCO); code at `github.com/IST-DASLab/GSQ` and `github.com/IST-DASLab/RCO`.

Quality claim (quoted from the README, not independently verified): `IQ3_S` (3.50 bpw, 11.8 GB) is
"task-lossless" — matches the base model on AIME25 (100.00) and LiveCodeBench v6 (85.71), and is
0.51 points below on GPQA-Diamond, vs. the 53.8 GB BF16 (4.6x larger). The README also claims its
variants beat comparable Unsloth Dynamic (UD) quants at equivalent file size — taken from their own
results table, not independently reproduced here.

Each variant optionally ships an `-mtp` build (~0.35 GB larger) adding the MTP head; the README
states explicitly "the weights are otherwise identical, so quality is unchanged" — `-mtp` doesn't
change model quality, only adds the speculation head.

Sampling: the README doesn't set its own; it uses the same recorded `general.sampling.*` as the
official model.

### HauhauCS Aggressive (Uncensored)

Author: **HauhauCS**. Base: `Qwen/Qwen3.8-27B` (declared in the README's YAML frontmatter). The
"Aggressive" profile is a de-refusal tune described as "direct answers, no refusal behavior, and
minimal preamble on hard prompts", with a self-reported "0/465 Refusals" figure — vendor's own
number, not independently re-verified. The README does not detail the de-refusal method.

The local file (`IQ4_XS`, 15.7 GB) matches the README's download table exactly: `IQ4_XS | 4.60 bpw |
15.71 GB`. **Every text GGUF in this repo preserves Qwen3.8's native NextN head** (quoted verbatim
from the README) — this is why the local metadata shows `nextn_predict_layers=1` even though the
filename doesn't say `-mtp`. The repo separately offers a **HauhauCS FastMTP** sidecar (903 MB, not
part of the local download) with its own acceleration claims — **not applicable** to the local file,
which only carries the native NextN head, not the FastMTP sidecar.

Recommended sampling: identical to the official Qwen card (cited literally as taken from it).

**Discrepancy worth noting** (per `AGENTS.md`: "if the card and the repo's guardrail disagree, note
it"): the HauhauCS README's example command includes `--reasoning-format deepseek`. This
repository's policy (`AGENTS.md`) is to **never set `--reasoning-format`** and leave the `auto`
default, since forcing `deepseek` has been observed to break parsing on other channel-format models.
For this `qwen35` family with `<think>` it may not matter, but the repository's policy stays above
the vendor's example command until measured otherwise.

### RVN-Q4_K_M-multilingual-mtp

**Is it really Qwen3.8-27B?** Yes — confirmed, not a different base model. The actual distributing
repo is `0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF`, with `base_model:
Qwen/Qwen3.8-27B` in the YAML frontmatter, and its file table literally lists
`RVN-Q4_K_M-multilingual-mtp.gguf` at `17.00 GB / 15.83 GiB` — matching the local file exactly
(16,998,720,992 bytes). The local metadata's architecture (head counts / `ssm.*` / block_count /
rope) is identical to the other Qwen3.8-27B-derived files — independent confirmation of the same
skeleton.

**RVN** is a "double-refined" ablation variant: starts from `trohrbaugh/Qwen3.8-27B-heretic-ara`
(an ARA ablation by Tim Rohrbaugh) and applies **two additional full-weight ARA passes** targeting
residual refusals. The README quotes KL≈0.0085 (very low behavioral damage) and a refusal-rate drop
from 3/100 to 0-1/100 in independent measurements — vendor figures, not reproduced here.

**ARA** = *Arbitrary-Rank Ablation*, implemented in `p-e-w/heretic`
(https://github.com/p-e-w/heretic): instead of subtracting a single "refusal direction" (classic
directional ablation), it treats ablation as an LBFGS matrix optimization problem over attention
output and MLP down-projections, with three objectives (preserve/steer/overcorrect).

The file belongs to the repo's **"multilingual"** family: rebuilt with a pinned multilingual/code
calibration imatrix (not English-only), recommended by the README as the default for new downloads
over the "legacy" files without that suffix, especially at 4-bit or below. The README confirms the
`-mtp` twins load with 866 tensors, `qwen35.block_count=65` and `qwen35.nextn_predict_layers=1` —
matching the local metadata.

**No sampling of its own**: per `AGENTS.md`'s rule ("what the vendor doesn't say, don't set"), this
file uses the official Qwen3.8-27B card's sampling, with nothing RVN-specific invented. Note: this
GGUF's local metadata does **not** carry `min_p` in `general.sampling.*` (only temp/top_k/top_p) —
`min_p 0.0` must be set explicitly (llama.cpp's default is 0.05, not 0).

## 3. KV cache estimate (ARITHMETIC, not measurement — see `docs/measurements/memory.md` for real numbers)

The hybrid architecture is also confirmed in llama.cpp's own source: `qwen35` appears in
`llm_arch_is_hybrid()` (`src/llama-arch.cpp`), and the hybrid KV layer filter for QWEN35 in
`src/llama-model.cpp` is `filter_attn = il < n_layer && !hparams.is_recr(il)` — **only the
non-recurrent layers grow KV**; DeltaNet layers use `llama_memory_recurrent` (fixed-size state, does
not grow with context). The same source also notes that the MTP head (`--spec-type draft-mtp`) uses
a **separate** plain attention KV cache from the hybrid main cache ("Dense MTP heads use a plain
attention KV cache instead of the hybrid wrapper") — its extra cost per token was not estimated here
(a single layer, presumably small relative to the total, but unconfirmed at estimate time; see
`docs/measurements/memory.md` for the measured value).

Formula: `2 (K+V) × real_KV_layers × n_kv_heads × head_dim × bytes_per_element`. With
`real_KV_layers = 16`, `n_kv_heads = 4`, `head_dim = 256`:

| KV type | Bytes/token/real-layer | Bytes/token (16 layers) |
|---|---:|---:|
| f16 (2 B) | 4,096 | 65,536 B (64 KiB) |
| q8_0 (1 B) | 2,048 | 32,768 B (32 KiB) |
| q4_0 (0.5 B) | 1,024 | 16,384 B (16 KiB) |

> **Correction**: in ggml, `q8_0` uses 34 B per 32-value block (**1.0625 B/element**) and `q4_0` uses
> 18 B per block (**0.5625 B/element**), due to each block's f16 scale. Real bytes per token are
> **~34 KiB (q8_0)** and **~18 KiB (q4_0)**, 6% and 12.5% more than the table above. The token
> maximums below are therefore somewhat optimistic; `--fit`'s measured value always wins.

Budget: 24 GB VRAM − 1 GB reserved for compute buffers (a simplification; the real compute buffer
also scales somewhat with context/batch, so the real `--fit` number is more conservative) − weight
file size:

| File | Weights (GB) | VRAM free for KV (GB) | Max tokens f16 | Max tokens q8_0 | Max tokens q4_0 |
|---|---:|---:|---:|---:|---:|
| HauhauCS IQ4_XS | 15.71 | 7.29 | ~111,000 | ~222,000 | ~262,144 (native cap; raw ~445,000) |
| GSQ-RCO IQ3_S | 11.77 | 11.23 | ~171,000 | ~262,144 (cap; raw ~343,000) | ~262,144 (cap; raw ~685,000) |
| GSQ-RCO IQ3_S-mtp | 12.12 | 10.88 | ~166,000 | ~262,144 (cap; raw ~332,000) | ~262,144 (cap; raw ~664,000) |
| GSQ-RCO IQ3_XXS-mtp | 10.44 | 12.56 | ~191,000 | ~262,144 (cap; raw ~383,000) | ~262,144 (cap; raw ~767,000) |
| RVN Q4_K_M-multilingual-mtp | 17.00 | 6.00 | ~91,000 | ~183,000 | ~262,144 (cap; raw ~366,000) |

"Cap" = capped at the native 262,144 context even if the KV arithmetic would allow more; going
beyond would need YaRN (not exercised on this hardware/engine).

## 4. MTP / speculative decoding in llama.cpp

Confirmed in `tools/server/README.md` and `common/arg.cpp` at the time of writing:

- The flag is `--spec-type`, values `none,draft-simple,draft-eagle3,draft-mtp,draft-dflash,
  draft-dspark,ngram-simple,ngram-map-k,ngram-map-k4v,ngram-mod,ngram-cache`. For the MTP head
  baked into the GGUF, the value is **`draft-mtp`**.
- Related tuning flags: `--spec-draft-n-max` (draft tokens per step, default 3),
  `--spec-draft-n-min` (default 0), `--spec-draft-p-min`/`--draft-p-min` (default 0.00),
  `--spec-draft-p-split`/`--draft-p-split` (default 0.10).
- **Requires the MTP tensors baked into the GGUF.** The non-`-mtp` GSQ-RCO files (no
  `nextn_predict_layers` in metadata) **cannot** use `--spec-type draft-mtp`. Files that can:
  HauhauCS IQ4_XS, `IQ3_S-mtp`, `IQ3_XXS-mtp` and `RVN-...-multilingual-mtp`.

No official documentation gives an "accept rate" or performance figure for MTP specific to
RDNA3/Vulkan — any such figure found in forums or third-party READMEs (e.g. HauhauCS FastMTP
numbers on Ada/Blackwell) is **not applicable to this hardware**; see `docs/SOURCES.md` for how
third-party MTP claims were checked against real measurements here.

## 5. Adopted configuration

This section originally proposed a draft configuration before the hardware existed. The actual
adopted configuration lives in `models.toml`; the resolution, for reference:

- **Adopted model**: `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` (`qwen38-iq3s-mtp`) — best perplexity/MTP
  trade-off of the GSQ-RCO family (see `docs/measurements/kv-quality.md`).
- **KV type**: `q8_0/q8_0` for the current daily profile (`224k-q8q8-mtp`); `q8_0/q5_1` was measured
  and works but is slower at depth and was not adopted as the default (see
  `docs/measurements/speculative.md`); `q4_0/q4_0` was ruled out on quality grounds (see
  `docs/measurements/kv-quality.md`).
- **MTP**: `--spec-draft-n-max 2` — the measured sweet spot (see `docs/measurements/speculative.md`).
- **Backend**: `hip`/`hip-kvmix` — see `docs/measurements/engines.md` and `docs/ENGINES.md`.

## 6. 262K test ladder (historical plan, resolved)

The original goal was the full native 262,144-token context at the best quality that fits in 24 GB.
The test ladder that was actually run (IQ3_S-mtp + 262K sweep → KV mix trade-offs → the eventual
190-200K daily profile) is documented with real numbers in `docs/measurements/depth.md` and
`docs/measurements/speculative.md`. Summary of the resolution: 262K with q8/q8 + MTP does not fit
safely (see `docs/measurements/memory.md`); the adopted daily profile trades some context (200K
instead of 262K) for headroom and depth throughput. The **long-context quality test (RULER-style
retrieval) is still pending** at the time of writing — see `docs/measurements/depth.md#open-questions`.

## Open questions

- Exact accept rate of `--spec-type draft-mtp` on RDNA3 across content types beyond what
  `docs/measurements/speculative.md` already covers.
- HauhauCS "Aggressive" de-refusal method (the README names the profile but not the algorithm,
  unlike RVN which documents ARA/heretic in detail).
- GSQ-RCO's quality claims vs. Unsloth Dynamic — quoted from their own results table, not
  independently reproduced.
- Third-party refusal-rate and KL figures for HauhauCS and RVN — vendor claims, not measured here.
