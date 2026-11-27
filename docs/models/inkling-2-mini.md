# Inkling-2-Mini (Thinking Machines) on llama.cpp and the `maya-ik2` HIP port

## Current state (2026-11-22, wired on the GodGMN fork)

- **In use since 2026-11-23: `inkling2-mini-unc-q8d` / `315k-maya`** (315,392 context, [run](../../results/20261123-inkling-315k/README.md); the launcher's no-alias fallback,
  not a recommendation) — the Abiray file with its head and
  non-expert attention/conv matrices re-typed to Q8_0 (experts byte-identical), so `maya-ik2` takes its planar Q8
  decode path: decode 106.1 / 98.2 / 90.0 / 68.9 tok/s at 512 / 8K / 32K / 128K (+7-11%), 1.3 GiB more VRAM,
  GSM8K 187/192 vs. 188/192. Engine `hip-port` `f472e94` since 2026-11-23. DSpark loads with rocBLAS's gfx1100 device
  pack but decodes 4-17% slower, not wired ([round 3](../../results/20261123-inkling-round/README.md#dspark-drafter-the-hiperrorinvalidimage-cause-fixed-slower-on-this-card)). Launch:
  `python3 scripts/launch.py inkling2-mini-unc-q8d --profile 262k-maya`
  ([round](../../results/20261123-inkling-round/README.md)). To rebuild the file from a new Abiray release:
  `python3 -I results/20261123-inkling-round/raw/retype_q8.py --src <Abiray.gguf> --dst <models_root>/Inkling-2-Mini-Uncensored-Abiray-q8dense/Inkling-2-Mini-Uncensored-IQ4_NL-q8dense.gguf` (the path `models.toml` reads).
- **Two profiles since 2026-11-22 (second pass)**: `262k-maya` on the `maya` backend (GodGMN's `maya-ik2` HIP
  port of `alesha-pro/maya-inkling-mini`) is the faster one: decode 95 / 63.6 / 51.1 tok/s and prefill
  1,894 / 1,292 at 512 / 128K / 262K, GSM8K 95/96, 262K retrieval 3/3, tool calls and prefix reuse working
  ([run](../../results/20261122-inkling-maya-vs-fork/README.md)). Launch:
  `python3 scripts/launch.py inkling2-mini-unc-q8d --profile 315k-maya` ([SOP](../sop/launch-model.md)); the IQ4_NL
  file's own `262k-maya` profile was removed on 2026-11-24 in favor of the faster q8d re-type. Both GodGMN
  projects are in use: the llama.cpp fork serves `inkling2-mini-unc/262k-q8q8`, the HIP port serves the q8d profiles. The bullets
  below describe the fork profile.
- **Wired llama.cpp profile** (`262k-q8q8`, the comparison arm; the Q8_0 re-typed `262k-maya` on the HIP
  port above is the setup in use since 2026-11-23): `models.toml` alias `inkling2-mini-unc` (Abiray IQ4_NL, below),
  profile `262k-q8q8` (262,144 context, KV `q8_0`/`q8_0`, text only), backend `hip-inkling` = the GodGMN fork below
  (`local.toml` `[engines] hip-inkling`). Launch: `python3 scripts/launch.py inkling2-mini-unc --profile 262k-q8q8`.
  `smoke.py` with the final flags (temp 1.0, min-p 0.0): **44.1 tok/s**. This fork is the only llama.cpp
  path that holds 262K on this card ([`DECISIONS.md`](../DECISIONS.md)).
- **Sampling**: vendor `generation_config.json` sets only `temperature 1.0` (re-read 2026-11-22), so
  `top_p`/`top_k` stay at the engine default; the `top-p 1.0, top-k 0` of the Unsloth guide below is
  not the vendor's. Vendor warning: limit output tokens and agent turns (reasoning loops).
- **Why `q8_0`/`q8_0` and not the repo's `q8_0`/`q5_1`**: on this fork q8/q8 is faster (42.0 vs. 41.2
  tok/s), still leaves ~1.9 GiB of margin, and the fork's own tests do not cover `q8_0`/`q5_1`. KV
  parity against `f16` on this fork is not measured.
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
- **File: Abiray uncensored IQ4_NL since 2026-11-22** (13.90 GB, sha256 `e6680ab9…`, the OpenUncensored edit),
  replacing AtomicChat AD-Q4_K: decode 61.1 / 52.1 / 43.1 tok/s at depth 0 / 64K / 192K (AtomicChat 50.1 / 45.5 /
  26.2), 21,305 MiB at 262K, 0/8 keyword refusals, `smoke.py` 59.1 tok/s
  ([results](../../results/20261122-inkling-abiray-iq4nl/README.md)). Its IQ4_NL experts also load in `maya-ik2`.
  The AtomicChat file and its mmproj were deleted on 2026-11-22 (user confirmed); sha256 kept in the
  [earlier results](../../results/20261122-inkling-uncensored-ad-q4k/README.md).
- **Next**: the DSpark drafter loads on the port once rocBLAS gets its gfx1100 device pack, but decodes
  4-17% slower, so it stays out of the profile; n-gram speculation on the port is untested. Ranked path in
  [Engine and variant review](#engine-and-variant-review-2026-11-22-second-pass).
- **Decision**: the port profile is the setup in use since 2026-11-23 and the launcher's no-alias
  fallback; no setup is recommended ([`DECISIONS.md`](../DECISIONS.md)). Wiring history and the former
  park triggers stay in [Status](#status-parked-2026-11-22-resume-triggers) and [History](#history).
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
- Unbound v2.1 card (re-read 2026-11-25): "Recommended settings: thinking on, `--temp 0.6 --top-p 0.95`, and a
  thinking cap"; "No DRY or other repetition samplers". `262k-nib` follows it since 2026-11-25.
- **Reasoning loop observed (2026-11-25, `262k-nib` at temp 1.0, top-k 256, MTP on)**: one Gentle Shell turn at
  ~65K context spent the harness's `max_tokens` 32,768 (135 s, 242 tok/s) on thinking that cycled through the
  same 6 paragraphs 61 times (381 paragraphs, 19 unique) and returned `finish_reason: length` with no tool call.
  Nib `2e16cf0` samples only temperature/top-k/top-p/min-p (`src/server.cpp` `SampleParams`), has no thinking
  cap and silently ignores `presence_penalty`. **Repeated at the card's temp 0.6 / top-p 0.95** (11:27, same task
  resumed in a new session, ~67K context): 32,768 tokens in 145 s, 402 paragraphs, 41 unique, a ~4-paragraph cycle
  ×27. Both loops circle the same unresolved premise conflict in the task (which machine owns a refresh token,
  docs vs. files), so the trigger looks task-driven and the card sampling does not prevent it. Engine, MTP or
  model still not separated. Both ran at effort 0.7: the Gentle Shell `local-262k` entry has
  `supportsReasoningEffort: false`, so it sends no effort and Nib defaults to medium ([`ENGINES.md`](../ENGINES.md)).
  The vendor names lower effort, not lower temperature, as the lever ([sources](../SOURCES-upstream.md)); below
  0.7 is untested here. Since 2026-11-25 `262k-nib` caps thinking at the card's 4,096 tokens with a local Nib
  patch ([`results/20261125-nib-reasoning-budget/`](../../results/20261125-nib-reasoning-budget/README.md)).
- **Nib `bdc9307` (2026-11-25) is not adopted**: its exact GPU sampler makes the vendor sampling fast at `top_k 0`
  (113-157 tok/s, was ~31) with text-identical greedy output and GSM8K 187/192, but it segfaults in
  `hipGraphInstantiate` on 3 of 9 `serve` starts in the A/B run and 2 of 10 in the retest (0/15 on `2e16cf0`), in
  `bench`, and in `serve` without `--mtp`; the installed engine stays `2e16cf0` ([results](../../results/20261125-nib-bdc9307/README.md)).

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

## Comparison plan (open)

Superseded the same day by the ranked path in
[Engine and variant review](#engine-and-variant-review-2026-11-22-second-pass).

## Engine and variant review (2026-11-22, second pass)

User constraints for every arm (2026-11-22): the **272 W power cap stays**; the AtomicChat uncensored model is
preferred a priori, but another uncensored download is acceptable if it runs better; a profile above 262K only if
there is headroom; check the drafter ("MTP"). Evidence status follows [SOURCES](../SOURCES-community.md#inkling-2-mini-engines-drafters-and-adapters-2026-11-22).

### Engines

Who is who (the names overlap; none of these engines is this repository's own code, we only build and configure them):

| Name | Author | What it is |
|---|---|---|
| llama.cpp | ggml-org | the standard engine; the Qwen setup runs our own build of it plus a patch |
| `GodGMN/llama.cpp` branch `inkling-rdna3` | GodGMN (Sergio) | llama.cpp with Inkling HIP kernels; the `hip-inkling` engine wired here |
| Project Maya (`mw00/project-maya`) | Peasant Smith and contributors | a separate engine family that grew out of Strata, not llama.cpp |
| `alesha-pro/maya-inkling-mini` | alesha-pro | Maya's Inkling-only engine `maya-ik2`, CUDA |
| `GodGMN/maya-inkling-mini` branch `hip-port` | GodGMN (Sergio) | the AMD (HIP, gfx1100) port of `maya-ik2`; the 117 tok/s claim |

| Engine | Decode | Prefill | Context | Files it reads | Here |
|---|---|---|---|---|---|
| GodGMN llama.cpp fork `inkling-rdna3` `cb0e46960` (`hip-inkling`) | **50.0 tok/s** (code and prose, near-empty context, [run](../../results/20261122-inkling-dspark-fork/README.md)); `llama-bench` tg128 50.1 / 45.5 / 26.2 at 0 / 64K / 192K | not measured with `llama-bench` pp here | 262K `q8_0`/`q8_0`, 22,710 MiB in use | every llama.cpp type | **wired** |
| GodGMN `maya-inkling-mini` branch `hip-port` (`maya-ik2`, HIP port of `alesha-pro/maya-inkling-mini`, Project Maya v1.1.70 base) | **here, 272 W, Abiray IQ4_NL, tuned (`IK2_PAGED_KV=1`, `--chunk 2048`): 95 / 88.0 / 81 / 63.6 / 51.1 tok/s** at 512 / 8K / 32K / 128K / 262K ([run](../../results/20261122-inkling-maya-vs-fork/README.md)); author: 117.11 / 107.47 / 93.70 at 512 / 8,192 / 32,768 | here (tuned): 3,356 / 2,922 / 1,894 / 1,292 at 8K / 32K / 128K / 262K; author: 3,365.65 on 8,192 | author: 393,216 reserved, E4M3 KV | experts IQ4_NL, NVFP4 or Q8_0 only; **not AtomicChat AD-Q4_K** (below) | **built, measured (GSM8K 95/96 vs. fork 93/96), not wired** ([build](../ENGINES.md#maya-inkling-mini-hip-maya-ik2-experimental-inkling-2-mini-only)) |
| Upstream Project Maya (`mw00/project-maya`) v1.1.74 | field (#1116, 7900 XTX, ROCm 7.2.4): 109.1 tok/s (unsloth UD-Q4_K_XL), 94-95 (Heretic UD-Q4_K_XL) | field: 2,267 tok/s on 8K | field: 131,072 | Unsloth UD layout | not built |
| Strata `strata-inkling` 0.1.65 | no gfx1100 Inkling number (headline 198.9-250.3 tok/s is an RTX 5090) | — | claim "up to 1M" | its own SQ packs (SQ-20 18.02 GiB, claimed lossless) | not installed |
| Upstream llama.cpp b12633 | 4.5 tok/s at 262K (MoE offloaded) | 10.0 | 262K does not fit | every type | not wired |
| [Chromadera/nib](https://github.com/Chromadera/nib) `2e16cf0` (2026-11-24) | **here, 272 W, Nib-Pack NVFP4-Mixed, DSpark + sparse 224, temp 1.0 `top_k 256`: 122.6 / 102.2 / 97.3 / ~104 tok/s** at 7.8K / 33K / 134K / 258K (dense attention 110.5 / 99.2 / 78.4 / 59.7); card sampling without top-k ~31 tok/s; publisher: 186.8 | here: 3,620 / 3,399 / 3,041 / 2,982 at 7.8K / 33K / 134K / 258K | 262,848, Q8_0 KV, 21.50 GiB | Q8_0 + NVFP4 only | **wired, default** (`inkling2-mini-unbound-nib`, [trial](../../results/20261124-nib-trial/README.md)); GSM8K 187/192 (Unbound graft); retrieval 35/36 sparse vs. 36/36 dense to ~184K |

- **Why `maya-ik2` is faster** (author's text, CUDA): llama.cpp runs about 7,350 kernel launches per token for
  this model, `maya-ik2` 757 replayed as one graph; the HIP port keeps graph replay (`hipGraph`) and adds RDNA3
  WMMA prefill and IQ4_NL byte-permute decode kernels (`docs/HIP-PORT.md`).
- **Our file does not load in `maya-ik2`** (source-checked, `GodGMN/maya-inkling-mini` `2b31ffe`): the decoder
  knows NVFP4, Q8_0, IQ4_NL, Q5_K, Q6_K, IQ3_XXS and IQ4_XS (`src/ik2/ik2_kernels.cu:5994`), the RDNA3 expert GEMM
  only IQ4_NL, NVFP4 and Q8_0 (`src/ik2/ik2_rdna3.hip:441`), and gate/up/down must share one type
  (`src/ik2/ik2_main.cu:3193`). AtomicChat AD-Q4_K's 48 expert tensors are 24 `Q4_K` + 24 `Q5_0` (read with
  gguf-py on 2026-11-22).
- **Build environment**: the port was built and measured inside `ghcr.io/ggml-org/llama.cpp:server-rocm-b11176`
  (ROCm 7.2.1); upstream Maya refuses ROCm < 7 and documents ROCm 7 only. Our system runtime is ROCm 10.1
  ([install](../sop/install.md#known-errors)); a ROCm 7 container is the low-risk route. The author's power cap is
  not stated, so 117 tok/s is not a 272 W number.
- **Author's quality checks** (IQ4_NL, E4M3 KV): GSM8K 184/192, MMLU 207/256 (eight subjects); FP16 sliding-window
  KV 188/192 and 206/256 at 117.65 tok/s; retrieval at 392,960 input tokens in `docs/HIP-PORT.md`.

### Lessons from the CUDA original (`alesha-pro/maya-inkling-mini`, read 2026-11-22)

- **Tool calls**: Inkling sometimes writes `{"name":"read_file"args":{...}}` (comma and quote before `args` missing;
  llama.cpp's chat endpoint hides it with its tool-call grammar). alesha-pro's `549d734` reads that shape; the HIP
  port lacks it, so it is cherry-picked locally (21/21 `serve.test_inkling2_frontend`). Needed for agent harnesses.
- **Residency**: when not every expert fits in VRAM, decode falls to about half speed; the engine logs
  `resident: every expert in VRAM` when it does (it does here at 262,144 and 393,216).
- **FP8 vs FP16 KV**: median KL 1.1e-3 (alesha-pro, CUDA); FP8 is faster deep in a context. The HIP port's
  `IK2_KV=fp8-global` keeps sliding-window layers in FP16 (author: GSM8K 188/192 vs. 184/192, +150 MiB).
- **The drafter is the CUDA engine's biggest lever** (code and edits 149-212 tok/s vs. 124-126 plain on an RTX 3090)
  and is disabled on HIP: its block verification uses NVIDIA MMA. A HIP port of that path is the largest open gain.
- **Tried and did not help** (CUDA, alesha-pro): the drafter through the general prompt path (code 66 tok/s); a
  drafter context cut to 16K (2.24 vs. 3.07 tokens per window at 64K); a vocabulary shortlist in the drafter head;
  skipping V reads for small attention weights (0.0% skippable at 64K); more prefetch in the dense Q8 kernels
  (already 715 GB/s); int8 DP4A expert input (125 tok/s but GSM8K 71 vs. 73 of 96).
- `alesha-pro` also merged a gfx12 (RDNA4) HIP build (`003f225`, DeseretSaint) and `--parallel N` batching; neither
  is in the gfx1100 port.

### Lessons from the Intel Arc B70 cookbook (`SergiioB/intel-arc-pro-b70-inference-cookbook`, read 2026-11-22)

Another single-card, no-FP4/FP8-hardware target (Arc Pro B70, 32 GB, Xe2), so its closed arms transfer better
than CUDA numbers. All figures are the author's (`docs/inkling2-mini/README.md`, `docs/DO-NOT-REPEAT.md`), not
re-measured here.

- **Best B70 route is vLLM XPU on the official safetensors** (NVFP4/MXFP8 experts unpacked to BF16 for XMX, BF16 KV)
  plus upstream vLLM PR #69186 (FP32 `lm_head` without recasting the BF16 weight every step: +42% decode, DNR-042).
  Stock: 54.5 / 44.7 / 31.7 tok/s at 0 / 32K / 128K, 262,144 context at `max_num_batched_tokens` 1024. With
  DSpark `k=7` and an opt-in CUTLASS Xe2 MoE: 80.4 / 63.6 / 55.3 tok/s at 0 / 32K / 104K. Our tuned `maya-ik2`
  ([run](../../results/20261122-inkling-maya-vs-fork/README.md)) is ahead without a drafter: 95 / 81 / 63.6 at 512 /
  32K / 128K. vLLM ROCm on gfx1100 for Inkling was not found (an SGLang cookbook snippet says its AMD path is MI350X/MI355X only; unverified).
- **Larger GGUFs are not more precise** (DNR-040): the release stores the experts of layers 0-19 only as NVFP4, so
  Q8_0 or BF16 GGUFs re-encode the same 4-bit values. By the same argument an IQ4_NL file (Abiray, ggml-org)
  re-quantizes NVFP4 experts and can only lose against an NVFP4-expert GGUF; `maya-ik2` reads NVFP4 experts, so an
  uncensored GGUF that keeps NVFP4 experts in the `inkling2_loop` layout would be the precision upper bound
  (none checked so far; see the variants table below).
- **Vocabulary**: `config.json` says 201,024 (padded); the GGUF tokenizer has 200,058. The DSpark drafter keeps the
  padded 201,024 rows, which is exactly the `markov_w1.weight` shape our fork rejects
  ([run](../../results/20261122-inkling-dspark-fork/README.md)): a loader fix is a row slice, not a new conversion
  (inferred).
- **DSpark under card sampling can lose**: on llama.cpp SYCL, `--spec-draft-n-max 3` at temperature 1.0 gave 13.5
  vs. 19.5 tok/s plain (-31%, acceptance 43%; DNR-034). It only paid off with a cheap block verify (vLLM `k=7`).
  Same message as the playbook: measure drafting at the card's temperature 1.0, not only greedy.
- **Fused prompt GEMMs need a KL gate**: a fused NVFP4 dequant GEMM gave 1.55-2.4x prefill but mean KL 0.00112,
  top-1 98.49%, greedy output changed on 4 of 5 prompts (DNR-039); the author's gate is mean KL <= 1e-4 and top-1
  >= 99.5%.
- Card sampling restated there: `temperature=1.0`, `top_p=1.0` (`generation_config.json`), default
  `reasoning_effort` 0.9; matches our profile (temperature only).

### Drafter ("MTP")

- Inkling has **no MTP head**: the checkpoint ships a 3-layer **DSpark** block drafter (`mtp.safetensors`, block 8);
  `--mtp` / `draft-mtp` do not apply (Unsloth `dspark/README.md`).
- **Our fork cannot load it**: `markov_w1.weight` 256 x 201,024 vs. the expected 256 x 200,058
  ([run](../../results/20261122-inkling-dspark-fork/README.md)). Inkling DSpark in llama.cpp is ggml-org PR
  #32218 (open draft, changes requested; one Mac M3 report of x1.05-x1.64) and Unsloth's fork.
- `maya-ik2` HIP: the author's benchmark CLI raised decode 117.22 -> 137.49 tok/s (512 input) with adaptive
  drafting, but a 257-token story fell 116.26 -> 89.51; the packaged server runs plain decode, and serving rejects
  a drafter unless the block-verification path is on (`docs/HIP-PORT.md`, `src/ik2/ik2_main.cu:5393`).
- No DFlash, DFlash2, lilicorr or EAGLE3 drafter for Inkling was found; MLX extracts exist (bouroo, unread).

### Uncensored variants against the engines

| Variant | Size | Edit | llama.cpp fork | `maya-ik2` |
|---|---|---|---|---|
| AtomicChat AD-Q4_K (**on disk**) | 15.39 GiB | merged; card KLD 0.0115 | runs | **no** (Q4_K/Q5_0 experts) |
| AtomicChat `Inkling-2-Mini-Uncensored-LoRA.gguf` | 41.8 MiB | card: rank-1 on 49 residual-write sites, "for any GGUF of AtomicChat/Inkling-2-Mini-GGUF"; card's own LoRA row: MMLU -1.50 pt (p = 0.006) | `--lora` on `inkling2_loop` untested | no LoRA path found |
| OpenUncensored `Inkling-2-Mini-Uncensored-LoRA` | 1 MB | rank-2 projection on `attn.wo_ud` of layers 4-23, experts untouched; author: 0/32 refusals, MMLU 78.95 -> 79.47 | as an offline edit | as an offline edit to ggml-org IQ4_NL (experts byte-identical to the file the port was validated on) |
| Abiray `Inkling-2-Mini-Uncensored-IQ4_NL.gguf` (GGUF of OpenUncensored's merged model) | 13.9 GiB | the OpenUncensored edit already merged (experts byte-identical to the base before quantization); `inkling2_loop`, 48 expert tensors all IQ4_NL, 0 scale tensors (header read 2026-11-22) | expected to run (same layout as AD-Q4_K), not run | readable by type (IQ4_NL experts), not run |
| JoaoZaokk Heretic UD-Q4_K_XL | 16.42 GiB | abliterated, quality not published here | not checked | ran on upstream Maya + 7900 XTX at 94-95 tok/s (field, #1116) |
| nokeepai Unbound v2.1 | GGUF Q8_0 25.91 GiB (we graft only its 120 attention tensors, 631 MiB) | abliteration + LoRA fine-tune merged into the q/k/v/output/gate attention projections of all 24 layers; experts byte-identical. Card's same-test comparison (263 harmful prompts, Q8_0, one judge; author's own release ranked first): useful answers thinking off/on 83.7/85.2% vs. OpenUncensored (the edit in our Abiray file) 33.1/41.8%, KLD 0.0439 vs. 0.0228, MMLU-300 74.3 vs. 75.3 | — | grafted onto the Nib-Pack for `nib` ([trial](../../results/20261124-nib-trial/README.md#uncensored-file)); graftable onto `q8dense` too, not built |

Expert types read from the remote headers on 2026-11-22: JoaoZaokk Heretic and onemunanoyo UD-Q4_K_XL are
`inkling2` 48-block, NVFP4 (40) + Q8_0 (8) with 40 scale tensors (not loadable on the llama.cpp fork);
AtomicChat AD-IQ3_S is IQ4_NL (24) + IQ3_S (24) (IQ3_S not readable by `maya-ik2`); IndrasMirror XQ mixes NVFP4 and
IQ3/IQ4 types; ggml-org IQ4_NL is IQ4_NL (40) + Q8_0 (8). **Abiray's IQ4_NL is the only ready-made uncensored file
both engines can read**, so no own edit is needed.
Also checked in the Hugging Face `base_model:quantized` list (about 80 repos, 2026-11-22): IsValorum Abliterated
APEX-I-MiniPlus mixes Q5_0/IQ3_S/IQ4_NL/IQ3_XXS experts; carsenk ROGUE is K-quants; electroglyph and aday777 publish
safetensors only; every uncensored Q8_0 (Abiray, nokeepai, KookiesXy, yanauto) is Maya-readable by type but 25.91 GiB,
more than the card.

The OpenUncensored edit is `W' = W - s Q Q^T W` on 20 BF16 matrices; on a GGUF it means dequantize those 20
`attn_output` tensors, apply the rank-2 delta, requantize to their original type. The tensor-name mapping
(`attn.wo_ud` -> GGUF) and their type in the ggml-org file are not checked yet.

### Hugging Face survey (2026-11-23)

All `base_model:` derivatives (quantized ~300, finetune ~30, adapter 14, merge 0) plus name searches, filtered for
files this engine can read: `maya-ik2` HIP takes IQ4_NL, Q8_0 and NVFP4 experts (NVFP4 kernels exist,
`src/ik2/ik2_main.cu:3193`, but were only tested on generated weights, `docs/HIP-PORT.md` "NVFP4 expert WMMA on
RDNA3"); it rejects K-quant expert rows (`a row is not whole Q6_K blocks`, measured) and has no F8_E4M3 type.
Numbers are each publisher's own, on different harnesses (not reproduced here unless stated).

| Candidate | Size | Experts | Edit and published quality | Here |
|---|---|---|---|---|
| Abiray IQ4_NL (OpenUncensored), ours | 13.90 GB | IQ4_NL | rank-2 on `attn.wo_ud` L4-23, s 4.0/2.5; nokeep table: useful 34.3/43.0%, refused 1.4/0.7%, KLD 0.0228 | in use (q8dense re-type) |
| bartowski `nokeepai_Inkling-2-Mini-Unbound-IQ4_NL` (Unbound v1.0) | 16.11 GB | IQ4_NL, but `gate_up` L0 Q6_K + L1-4 Q5_K; head/attn Q8_0 (header read) | conv-aware norm-preserving, same 20 tensors, s 3; useful 51.6/62.1%, refused 0/0, KLD 0.0102 | loads only after re-typing the 5 K-quant tensors to Q8_0 (17.29 GB, 1.9 GiB free at 262K) |
| nokeepai Unbound v2 GGUFs | 11.2-27.8 GB | K-quants / IQ3_M | v1.0 + r16 self-distill on 120 tensors; useful 78.7/83.4%, KLD 0.0318, refused 0.4/1.1% | not readable; would need a self-built IQ4_NL from BF16 (`edit.pt` published) |
| onemunanoyo Abliterated v2 Balanced / Aggressive | 16.6-17.6 GB | Unsloth UD mix (NVFP4 + Q8_0 `down`, K-quant `gate_up`) | KLD 0.062 / 0.071 vs. its UD base, MMLU -2 to -3 pp | not readable (K-quant `gate_up`, unverified by header) |
| IndrasMirror XQ-Uncensored | 13.93 GB | 13 layers original NVFP4, rest Q2_0/IQ3/IQ4 | Unbound v2 edit | not readable (Q2_0/IQ3) |
| AtomicChat, dealignai, JoaoZaokk Heretic, Kujira CHiPS, SC117, KookiesXy | 13-17.6 GB | K-quant / IQ3 / Q4_0 | AtomicChat KLD 0.0078 (lowest drift, but edits experts) | not readable |

Format quality (Xylolabs, one harness, KLD vs. BF16 on WikiText-2): NVFP4-XL 0.0026, NVFP4-Lite 0.0030, plain
IQ4_NL 0.0087 (ggml-org card: 0.0095). So the IQ4_NL experts every readable uncensored file uses cost ~3x the KLD of
the vendor-native NVFP4 bits, and no uncensored file with all-NVFP4 experts exists. Field caveat: one independent
review (note.com/sakusakujapan, 2026-11-22) found the base model already refuses 0/30 of its prompts and that the
OpenUncensored edit did not change usefulness; nokeep's "useful" rate is measured by a judge that also picked v2's
training data. Best path to higher quality: an uncensored edit applied to the vendor's NVFP4 experts (no such file yet)
or a self-built Unbound file.

### Hugging Face re-survey (2026-11-24)

New `base_model:` derivatives since the 2026-11-23 survey, plus the two Strata packs the user named. Expert and
head types below were read from the first 30 MB of each GGUF (header parse, no full download); quality numbers are
each publisher's own, not reproduced here. **No published uncensored file beats `q8dense` on `maya-ik2` as is**;
nothing downloaded or measured.

| Candidate | Header / card facts | Verdict for this setup |
|---|---|---|
| nokeepai Unbound **v2.1** (`nokeepai/Inkling-2-Mini-Unbound-GGUF`, current 2026-11-24) | `v2.1-Q8_0.gguf` 25.91 GB: `inkling2_loop`, 24 blocks, `attn_{q,k,v,output,gate,rel}` and experts Q8_0. Card: only the 120 BF16 attention matrices change, experts byte-identical; useful 83.7/85.2% (OpenUncensored 33.1/41.8%), refused 0.4/0.4%, KLD 0.0439 (ours 0.0228), MMLU-300 74.3 (ours 75.3), GSM8K-100 98; greedy hits the 4,096-token thinking cap on 22.1% of its prompts, temp 0.6 fixes most | Too big as published (Q8_0 experts) and its Q4_K_M has K-quant experts. **Buildable**: graft its 120 Q8_0 attention tensors onto `q8dense` (same size, same 315K headroom); same path for v1.0 (`Inkling-2-Mini-Unbound-Q8_0.gguf`, KLD 0.0102, useful 51.3/61.6%). User chose not to now (2026-11-24) |
| electroglyph `Inkling-2-Mini-Unbound-GGUF` UD-Q4_K_M (15.47 GiB; Unbound main = v2.x) | `inkling2_loop` 24; experts NVFP4 x20 + `down` Q8_0 x4 + `gate_up` Q5_K x4, **no `ffn_*_exps.scale`**; dense and head Q8_0. UD-IQ4_XS: NVFP4 x20 + IQ4_XS/Q4_K/Q5_K/Q5_0, head Q6_K | Not loadable: the port dies on NVFP4 without `.scale` (`src/ik2/ik2_main.cu:4850`) and rejects K-quant rows |
| Wa1k3r `…NVFP4exp-Q8-draft-LexiSuite-AIO-for-AMD-RDNA` (18.26 GB) | `inkling2_loop` 24; experts NVFP4 x20 with `.scale` + Q8_0 x4; head Q8_0; drafter in the file. Repo also ships secure-boot OS images | Base model (not uncensored), +1.6 GiB over `q8dense` (no 315K); not pursued |
| notfakerv Abliterated WSP, Mir2k Uncensored (Q4_K_M 16.28 GiB), y0uq AD-IQ4_XS, YukijThird IQ2_S, diablomike20 / npario (AtomicChat re-uploads), kelsey1337 `…-Maya-GGUF` (Unsloth UD, 16.42 GiB) | K-quant, IQ4_XS or IQ2 experts (file names / cards). notfakerv card: edits `attn_output` and all experts' `ffn_down`, KLD 0.034 | Not readable by `maya-ik2` |
| orcarouter `Inkling-2-Mini-abliterated-GGUF` (Mix-16G 14.64 GiB) | Gated; card unread | Not checked |
| strata-engine `Inkling-2-Mini-Strata` (SQ-10 / 15 / 20: 10.47 / 14.35 / 19.35 GB) | Card: SQ-20 matches the original 100% (lossless experts); RX 7900 XT 20 GB over OCuLink 54.7+ tok/s on SQ-10 (no 7900 XTX row); not uncensored | Possible quality arm (lossless vs. IQ4_NL), but the card's only RDNA3 number is about half our `maya-ik2` decode; not tried ([`sop/strata.md`](../sop/strata.md)) |
| Kujira `Inkling-2-Mini-Strata-CHiPS-Abliterated` (SQ-20 19.35 GB, preview) | SQ-20 with CHiPS v6: only layer 11 attention output changed, experts byte-identical (card); refusal numbers measured on a UD-IQ2_XXS GGUF, not on the pack (310/312 -> 0/312 "thinking heads toward refusal"); no GSM8K/MMLU; Strata 0.2.20 cannot install custom packs from the app | Uncensored Strata option if Strata is ever measured here; same speed caveat |
| @SergioGMN / GodGMN abliterated | No upload (`?author=GodGMN` empty) | Still on watch |

### Engine round (2026-11-27)

Every engine update of the day against the `262k-nib` default; decode tok/s at 7.8K / 33K / 134K / 258K. **The
default stays**: nothing else was faster at any depth.

| Engine, file | Decode | Record |
|---|---|---|
| nib `2e16cf0` + patch, sparse 224 (default; loaded host) | 121 / 121 / 108 / 107 | [nib-v022](../../results/20261127-nib-v022/README.md) |
| nib `2e16cf0` + patch, dense (`--sparse-pages 0`) | 143 / 106 / 87 / 66 | [tintero](../../results/20261127-tintero-dflash2/README.md) |
| nib `v0.2.2` + patch, card sampling without `top_k` | 121 / 110 / 111 / 103; dies at start-up on ~half the starts (upstream) | [nib-v022](../../results/20261127-nib-v022/README.md) |
| Tintero `dc52e6f`, Abiray q8dense, dense / sparse / + DFlash2 | 94 / 79 / 55 / 41; 98 / 92 / 79 / 90; at most +13% | [tintero](../../results/20261127-tintero-dflash2/README.md) |
| Strata 0.2.23, ISTA GSQ-RCO IQ3_S | 58 / 44 / 25 / 18 | [strata](../../results/20261127-strata-0223-inkling-iq3s/README.md) |
| Project Maya v1.1.83 / alesha-pro `27daec5` | not run: needs the Maya-L layout (disk) / no gfx1100 build | [maya](../../results/20261127-project-maya-v1183/README.md) |

Retest triggers: nib start-up fix (then drop `top_k 256`), Project Maya once 18 GB are free, Strata only for models
that do not fit VRAM.

### Hugging Face re-survey (2026-11-27)

New uncensored derivatives since 2026-11-24, read from the HF API and cards only (no header parse, nothing
downloaded); every number is the publisher's. Engine fit uses the documented readers: `nib` = Q8_0 + NVFP4 experts
(Nib-Pack layout), `tintero` = IQ4_NL or Unsloth UD-Q4_K_XL ([`SOURCES-community.md`](../SOURCES-community.md#tintero-strata-0221-0222-ista-gsq-rco-and-inkling-cyber-2026-11-27)).
**No uncensored GSQ-RCO file exists**: [ISTA-DASLab](https://huggingface.co/ISTA-DASLab/Inkling-2-Mini-GSQ-RCO-GGUF)
added nothing after 2026-11-26, and `joyfox/Inkling-2-Mini-GSQ-RCO-Uncensor` is ISTA's IQ3_S plus an unmerged
43.8 MB AtomicChat LoRA (49 residual writers), with no refusal numbers for the pair.

| Candidate (2026-11-26/27) | Card facts | Fit here |
|---|---|---|
| [onemunanoyo Abliterated-Aggressive](https://huggingface.co/onemunanoyo/Inkling-2-Mini-Abliterated-Aggressive-GGUF) UD-Q4_K_XL 17.63 GB (also Q8_K_XL to Q2_K_XL) | Unsloth UD requant; edits `attn_output`, `ffn_down_exps`, `attn_gate`, `ffn_gate_inp`, `output`; 0/40 refusals, KLD 0.0706, MMLU 77.98% | **Next candidate**: UD-Q4_K_XL may load on `nib` and `tintero` (unverified); experts edited, so not graftable onto the Nib-Pack |
| [OBLITERATUS](https://huggingface.co/OBLITERATUS/Inkling-2-Mini-OBLITERATED) `v2e-IQ4_NL` 14 GB | rank-2 projection on `attn_output` layers 4-21; 86.8% answered of 740 | `tintero`, llama.cpp |
| [savealamb abliterated-tuned](https://huggingface.co/savealamb/Inkling-2-Mini-abliterated-tuned-GGUF) Q4_K_M 17.48 GB | `attn_output` + all `ffn_down_exps` layers 4-23, LoRA merged; 7/104 refusals, KLD 0.021, HumanEval 94.5% | llama.cpp only (K-quant experts) |
| [KatterMobile ARA-HERETIC](https://huggingface.co/KatterMobile/Inkling-2-Mini-ARA-HERETIC-GGUF) Q4_K_M | 15/100 refusals, KL 0.2725 | llama.cpp only |
| [isichan-ai Unlock](https://huggingface.co/isichan-ai/Inkling-2-Mini-Unlock-GGUF) UD quants (gated) | attention only | not checked (gated) |
| [MECHUK Tideglass](https://huggingface.co/MECHUK/Tideglass-Inkling-2-Mini-Unbound-v2.1-GGUF), [AiAF](https://huggingface.co/AiAF/Inkling-2-Mini-Unbound-v2.1-GGUF) | Unbound v2.1 on Q4_0 / Q4_K_M experts | llama.cpp only; our graft covers it |
| [GCSA-AiLab Uncensored](https://huggingface.co/GCSA-AiLab/Inkling-2-Mini-Uncensored) safetensors | 113 attention + 23 router-bias tensors; StrongREJECT 5/180 refusals | vLLM only |
| [sergiogmn Cyber](https://huggingface.co/sergiogmn/Inkling-2-Mini-Cyber-GGUF) IQ4_NL / Q6_K / Q8_0 | 20 Q8_0 `blk.4-23.attn_output` changed; HumanEval+ 93.3% -> 82.9% | graftable onto the Nib-Pack; security use, worse at code |

Buildable fallback if nothing better appears: graft the 120 Unbound v2.1 Q8_0 attention tensors onto ISTA IQ3_S, as
done for the Nib-Pack; it would run on llama.cpp only, which decoded Inkling at 57.6 / 44.5 / 37.8 tok/s here.

### Reference repos and engine updates (2026-11-23)

Read by scouts from the primary repos; author numbers, not re-measured here unless stated.

- **GodGMN (port author) runs our engine and preset**, with the stock ggml-org IQ4_NL (not uncensored), 393,216
  positions and `--chunk 1024`; decode 117.11 / 107.47 / 93.70 tok/s at 512 / 8K / 32K (`docs/HIP-PORT.md`, commit
  `9a0f164`). No power cap is documented, so the gap to our 106.1 / 98.2 / 90.0 at 272 W is probably power
  (unverified; a 303 W run is outside the user's cap).
- **`IK2_SUFFIX` prompt lookup** (no drafter, verified against the model): author's copy 105 -> 271 tok/s and single
  edit 106 -> 197 at window 64, identical final answers. Present in our build (`src/ik2/ik2_main.cu:5098`, off with
  `--draft`, window capped at `--chunk` and 128). Measured here: [round](../../results/20261123-inkling-round/README.md).
- **`IK2_KV=fp8-global`** (sliding layers FP16, global E4M3): author GSM8K 188/192 vs. 184/192, prefill at 512 -17%,
  KV 6.31 vs. 6.16 GiB. Measured here: same GSM8K, prefill -12 to -15% at 512, not adopted ([round 2](../../results/20261123-inkling-round/README.md#ik2_kvfp8-global-sliding-layers-fp16-global-layers-e4m3-no-gain-here-not-adopted)).
- **`IK2_CACHE_SLOTS=2`**: warm follow-ups 0.3 s vs. 130 s cold, but the reserved context is split (2 x 131K at 262K).
- **DSpark on AMD**: in project-maya #1163 (RX 7900 XT, v1.1.73) `--drafting auto` measured the drafter at -1.0 tok/s
  (unusable) and kept prompt lookup. #1154 was squashed into project-maya v1.1.75 (2026-11-23), which reads no IQ4_NL
  experts. On our port the `hipErrorInvalidImage` was rocBLAS's missing gfx1100 device pack; with it the drafter loads
  but decodes 4-17% slower ([round 3](../../results/20261123-inkling-round/README.md#dspark-drafter-the-hiperrorinvalidimage-cause-fixed-slower-on-this-card)).
- **Strata v0.2.20** (`strata-inkling` 0.1.66): no IQ4_NL in its lossless list; a field report shows 52 -> 47 tok/s on
  a 7900 XTX for another model (#6791); the gfx11 prefill/KV-snapshot work of #6685 is unmerged. Not tried.
- **llama.cpp b12651**: #32752 (chunked mask) and #32740 (FA compact bias) open; #32218 (DSpark) has changes
  requested; #32773 (DSpark 16 GB) works on Vulkan/RADV only. The GodGMN fork already computes the bias in-kernel.
- **Watch: an abliterated Inkling from @SergioGMN** (post relayed by the user, 2026-11-23: "terminando de ultimar
  los detalles antes de subir Inkling abliterated", first Hugging Face upload). Not published yet. When it appears:
  check the expert and head types against what `maya-ik2` reads (IQ4_NL / Q8_0 / NVFP4 experts, no K-quant rows;
  `retype_q8.py` covers K-quant experts) and run the round's bench + GSM8K 192 + refusal set against q8dense.
- **Since 2026-11-23 (round 2)**: `hip-port` gained `IK2_KV=fp4-global` and `--lora` for GGUF attention-output
  adapters (OpenUncensored's edit is attention-output only, so it could run as an adapter on a stock file); details
  and the upstream recheck in the [round](../../results/20261123-inkling-round/README.md#round-2-2026-11-23-afternoon).
- **Round 3 (2026-11-23)**: `hip-port` `f472e94` adopted (same speed and GSM8K, the loop guard recovers instead of
  cutting); `IK2_KV=fp4-global` needs `IK2_PAGED_KV=0` and loses 34% decode at 128K ([round 3](../../results/20261123-inkling-round/README.md#round-3-2026-11-23-evening-hip-port-f472e94-dspark-loads-ik2_kvfp4-global)).

### Ranked path

1. **`maya-ik2` HIP port: done (2026-11-22)**, on Abiray IQ4_NL with our ROCm 10 build (no container needed).
   Tuned with `IK2_PAGED_KV=1 --chunk 2048`: 1.6x decode at 512, 1.35x at 262K, 2.2x prefill at 262K, GSM8K 95/96
   vs. 93/96, refusals 0/8, tool calls and prefix reuse work
   ([run](../../results/20261122-inkling-maya-vs-fork/README.md)). Open: wiring it into `launch.py` (the user's
   call), the coding suite and a 262K retrieval check on it, and 393K (fits: every bench ran with 393,216 reserved).
2. **Fork above 262K**: arithmetic only (~300K `q8_0`/`q8_0`, ~350K `q8_0`/`q5_1`, ~550K `q4_0`); wiring it
   in a harness needs a window-named entry like `local-315k` (AGENTS.md).
3. **Drafter**: loads on `maya-ik2` with rocBLAS's device pack but is 4-17% slower ([round 3](../../results/20261123-inkling-round/README.md#dspark-drafter-the-hiperrorinvalidimage-cause-fixed-slower-on-this-card)); retest
   when the port takes project-maya's newer drafter code, or #32218 lands.
4. **Strata: on hold (2026-11-25, desk review of v0.2.21, not installed)**. On 24 GB HIP cards setup keeps VRAM
   for "the first 32K tokens of a conversation and no more", then "the engine moves its conversation memory to RAM
   ... (5.7 tokens per second at 200K tokens in our test)" ([v0.2.21 notes](https://github.com/Niko1221/Strata/releases/tag/v0.2.21));
   `262k-nib` keeps 262K in VRAM at 97-104 tok/s past 134K, and the agent sessions here run at 60-70K. It also
   applies no default sampling to Inkling (greedy unless the client sends one; owner in
   [#7092](https://github.com/Niko1221/Strata/issues/7092), fix planned for 0.2.22), and HIP KV is fp16 or fp8 only
   (fp8 18-24% slower on a 7900 XT, field report #7032, unverified). Resume when a release keeps 262K of KV in VRAM
   on a 24 GB HIP card, a smaller pack leaves room for it, or a gfx1100 Inkling number at 64K+ beats `262k-nib`.
5. Upstream llama.cpp: on the [triggers](#status-parked-2026-11-22-resume-triggers).
6. **Above 262K on maya: done (2026-11-23), `315k-maya` adopted** ([run](../../results/20261123-inkling-315k/README.md): 315,392 peaks at 22,874 MiB, retrieval exact; 352,256 leaves ~1.0 GiB). The plan it followed: FP8 KV grows 16 KiB per token (only the 8 global layer passes
   grow), so 352,256 adds ~1.4 GiB over 262K: about 22.2 GiB for `inkling2-mini-unc` and 23.4 GiB for `-q8d`
   (whole device, desktop included) on a 24 GiB card. Measure before adding a profile: start at 352,256 with
   `--chunk 2048 IK2_PAGED_KV=1`, read `resident: every expert in VRAM` and the free VRAM, run a retrieval check near
   the end of the window and decode at 262K/340K. Then raise `LOCAL_262K_CONTEXT`'s check in `check-sync.py`
   and omp's `contextWindow`. Done the same day: omp advertises 315,392 and compacts the local model at 75% (`DECISIONS.md`).

## Status: parked (2026-11-22, resume triggers)

Superseded the same day: the model was wired on the fork (see [Current state](#current-state-2026-11-22-wired-on-the-godgmn-fork)).
The triggers below are now the re-check list for [upstream](#comparison-plan-open).

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
   or abliterated variants (HF API `filter=base_model:quantized:thinkingmachines/Inkling-2-Mini`; the
   website's `other=` parameter is ignored by the API and returns unrelated models; and
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
