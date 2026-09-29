# Sources

External claims checked against this repository's own measurements (`docs/measurements/`). Status:
**verified** (matches an own test or a primary source read directly), **hypothesis** (plausible,
not yet tested here), **refuted** (contradicted by an own test or a primary source read directly).
"Own test" links to where this repository measured the same thing, when it exists.

## Engine / backend

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Official ROCm binaries only ship FlashAttention for symmetric K/V; asymmetric mixes fall to a slow path | [llama.cpp discussion #22411](https://github.com/ggml-org/llama.cpp/discussions/22411) | 2026 | Verified | Resolved by building `hip-kvmix` with `GGML_CUDA_FA_QUANTS` covering q8_0/q5_1 — [`docs/ENGINES.md`](ENGINES.md) |
| With both Vulkan and HIP compiled into one binary, MTP silently routes to ROCm and gets disabled | [llama.cpp issue #23199](https://github.com/ggml-org/llama.cpp/issues/23199) | 2026 | Verified | Single-backend-only policy adopted, see `AGENTS.md` and [`docs/measurements/engines.md`](measurements/engines.md) |
| SYCL/Intel BMG: moving quantized-KV decode from the VEC kernel to TILE gave +128% (Qwen 35B q4_0) / +169% (Gemma 12B) at 118K | [llama.cpp PR #26689](https://github.com/ggml-org/llama.cpp/pull/26689) | 2026-08-28 | Verified (source read) | Motivated testing the `stew675/llama-cpp-rdna-boosts` fork's native-q8 KV path on this GPU — only -2.5% ms/step at depth, far short of the SYCL gain — [`docs/measurements/speculative.md`](measurements/speculative.md) |
| `stew675/llama-cpp-rdna-boosts` fork: the FlashAttention kernel selector returns VEC for ≤2 verified tokens and TILE from 3, converting KV to f16 on every step with quantized KV | [GREEDY-PURITY.md](https://github.com/stew675/llama-cpp-rdna-boosts/blob/main/GREEDY-PURITY.md) | 2026-09 | Verified | Matches this repo's own reading of `fattn.cu`; independent confirmation |
| Same fork's "native q8_0 KV" build avoids the f16 copy, claims −758 MiB VRAM and ±0% tg at short context | [V4-NATIVE-Q8-KV-PLAN.md](https://github.com/stew675/llama-cpp-rdna-boosts/blob/main/archive/work/arch-independent-memory/V4-NATIVE-Q8-KV-PLAN.md) | 2026-09 | Refuted at depth | Built and measured on this hardware: only −2.5% ms/step at ~190K, not worth maintaining a fork — [`docs/ENGINES.md`](ENGINES.md), [`docs/measurements/speculative.md`](measurements/speculative.md) |
| `llama.cpp` issue #26038: "excessive compute buffer reservation" on HIP | [llama.cpp issue #26038](https://github.com/ggml-org/llama.cpp/issues/26038) (labeled `bug-unconfirmed`) | 2026-07-23 | Verified (issue exists) | No fix published; not independently re-measured here |
| `llama.cpp` PR #28003: per-kernel Q4_K GEMV speedup measured on a 7900 XTX | [llama.cpp PR #28003](https://github.com/ggml-org/llama.cpp/pull/28003) (draft) | 2026-08-30 | Verified (source read), not applicable | This repo's model is IQ3_S, not Q4_K — the cited gain doesn't predict a gain here |
| PR #27210: adaptive MTP depth; author recommends against it below draft depth 7 | [llama.cpp PR #27210](https://github.com/ggml-org/llama.cpp/pull/27210) | 2026-08-17 | Verified (source read) | This repo's measured optimum is n=3 at 190K/240K — see [`docs/measurements/speculative.md`](measurements/speculative.md) |
| llama-server `--parallel`/`--kv-unified`/`--kv-unified-per-slot`: multiple slots share one compute stream and one KV cache (or one KV cache per slot with `--kv-unified-per-slot`) | [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), [PR #24124](https://github.com/ggml-org/llama.cpp/pull/24124) | 2026 | Hypothesis | Consistent with this repo's own measurement that a concurrent slot's prefill starves generation on other slots — [`docs/measurements/concurrency.md`](measurements/concurrency.md) |
| MTP is recommended with `--parallel 1` (single slot) | [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | 2026 | Hypothesis | Matches this repo's own multi-agent recommendation (1 slot + MTP, queue) — [`docs/measurements/concurrency.md`](measurements/concurrency.md) |
| PR #28102: FlashAttention tuning change targeting gfx1201 (RDNA4) | [llama.cpp PR #28102](https://github.com/ggml-org/llama.cpp/pull/28102) | 2026 | Refuted (source read, 2026-09-26) | A follow-up commit forced stream-K back on for gfx1100 after a regression — not a gfx1100 deep-prefill risk after all, see the 2026-09-26 community-claims section below |
| Issue #26648: MTP sampler assertion at long context on HIP | [llama.cpp issue #26648](https://github.com/ggml-org/llama.cpp/issues/26648) | 2026 | Hypothesis | Not reproduced here yet — see [`sop/update-engine.md`](sop/update-engine.md) |
| PR #56: RDNA3 IQ2/IQ3 MMVQ scale-multiply change | [halo-box/strix-llama.cpp#56](https://github.com/halo-box/strix-llama.cpp/pull/56) | 2026 | Hypothesis | Not tested here; candidate for a future speed/quality A/B on this GPU's IQ3_S quant |
| With GQA 6, HIP's quantized-KV FlashAttention tile kernel only folds 2 query heads per block (`ncols2 = 2`), refetching/dequantizing each K/V element 3x per query row; on gfx1201 this measured ~276 GB/s for q8_0 vs. ~615 GB/s for f16 in the same kernel | [stew675/llama-cpp-rdna-boosts#45](https://github.com/stew675/llama-cpp-rdna-boosts/issues/45) (`overdoingism`) | 2026-09 | Hypothesis (read), consistent with own analysis | Matches this repo's own roofline estimate at 240K (~226 GB/s, ~24% of peak) — [`docs/measurements/depth.md`](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4); not independently measured on this gfx1100 card, and the fork's own "WMMA full-fold band" fix (+28% on gfx1201) was tested on gfx1100 by the maintainer and **not** integrated (mixed/negative results) |
| llama.cpp issue #27796: same GQA-6/`head_dim` 256 decode-at-depth slowdown reported on gfx1201, closed as expected behavior | [llama.cpp issue #27796](https://github.com/ggml-org/llama.cpp/issues/27796) | 2026 | Verified (issue read) | Matches this repo's own root-cause analysis and closes the same way (no config fix exists) — [`docs/measurements/depth.md`](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4) |
| llama.cpp issue #28867: gfx1201 WMMA kernel-selection threshold, open | [llama.cpp issue #28867](https://github.com/ggml-org/llama.cpp/issues/28867) | 2026 | Verified (issue exists) | gfx1201-specific, not gfx1100; tracked for the next engine update, not independently tested here |
| llama.cpp PR #29393: RMS_NORM+SCALE fusion, author-measured +4.2-4.8% on `pp8000`/`pp20000` for Qwen3.8-27B with `draft-mtp` n=3 on CUDA | [llama.cpp PR #29393](https://github.com/ggml-org/llama.cpp/pull/29393) | 2026 | Verified (source read), HIP benefit not measured | Not yet in the pinned b11160; candidate for the next engine update, see `docs/sop/update-engine.md` |
| ik_llama.cpp routes every AMD FlashAttention batch size to its vec kernel instead of tile ("on AMD the tile kernels perform poorly, use the vec kernel instead") | [ikawrakow/ik_llama.cpp](https://github.com/ikawrakow/ik_llama.cpp), `ggml/src/ggml-cuda/fattn.cu` | 2026 | Verified (source read) | Not built or measured on this GPU — the project's own README deprioritizes ROCm; see `docs/measurements/depth.md` |

## MTP / speculative decoding

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Asymmetric KV (q5_1/q4_0) disables FlashAttention and falls back to slow CPU kernels | AI-summarized answer, no link | 2026-09-24 | Refuted | `hip-kvmix` compiles FA kernels for q8_0/q5_1; runs on GPU, costs ~8% generation speed — [`docs/measurements/speculative.md`](measurements/speculative.md) |
| Constant recurrent state of ~72 MiB regardless of MTP | AI-summarized answer, no link | 2026-09-24 | Refuted | Measured: 150 MiB without MTP, 449 MiB with MTP at 262K — [`docs/measurements/memory.md`](measurements/memory.md) |
| 262K context + vision + MTP with q8/q8 fits at ~100% of 24 GB | AI-summarized answer, no link | 2026-09-24 | Refuted | OOMs while generating; fits only without vision, 99.7% of VRAM — [`docs/measurements/depth.md`](measurements/depth.md) |
| MTP limits usable context to ~136K on a 24 GB card | [llama.cpp issue #20969](https://github.com/ggml-org/llama.cpp/issues/20969) (4090, third-party report) | 2026 | Refuted | 240K with MTP loaded and generated on this GPU — [`docs/measurements/depth.md`](measurements/depth.md) |
| `sudoingX/qwen38-mtp`: 7900 XTX, ROCm, UD-Q4_K_M, 131K, KV q4_0: no MTP 36.3 → MTP n=2 **62.6 tok/s** (+72%), empty context | [`sweeps/radeon.md`](https://github.com/sudoingX/qwen38-mtp/blob/master/sweeps/radeon.md) | 2026-09 | Verified (corroborates) | Matches this repo's own empty-context shape: 39 → 58-69 tok/s with n=2 — [`docs/measurements/speculative.md`](measurements/speculative.md) |
| Same repo: each extra MTP draft slot costs ~150 MiB VRAM | [`sweeps/radeon.md`](https://github.com/sudoingX/qwen38-mtp/blob/master/sweeps/radeon.md) | 2026-09 | Verified (corroborates) | Matches this repo's own recurrent-state estimate — [`docs/measurements/memory.md`](measurements/memory.md) |
| `--spec-draft-p-min` raises acceptance but lowers throughput on fast cards (README rule 2) | [sudoingX/qwen38-mtp README](https://github.com/sudoingX/qwen38-mtp) | 2026-09 | Verified (corroborates, empty context) | n=3 at 262K: p-min 0.60 → 66.2 tok/s (0.85 acceptance), 0.75 → 59.8 (0.91), vs. 68.9 ungated (0.72) — [`docs/measurements/speculative.md`](measurements/speculative.md#community-probe-ab-at-262k-empty-context-2026-09-27) |
| DFlash2 beats MTP at every context depth (RTX 3090, same GSQ-RCO IQ3_S model) | X/Twitter thread, @ItsmeAjayKV | 2026-09-14 | Refuted at depth | At ~190K, DFlash2 is slower than MTP n=2 on 2 of 3 task types and ties on the third, and uses more VRAM — [`docs/measurements/speculative.md`](measurements/speculative.md) |
| 7900 XT, LM Studio, 143K context: 45 → 27 tok/s at 110K filled, MTP accept rate ~85% with real MCP tool-call traffic | X/Twitter, @caseyjp11 (link unverified) | 2026-09 | Hypothesis | This repo's own synthetic-text acceptance at 190K is 55-90% depending on task — same order of magnitude, real-agent acceptance not directly measured yet — see `docs/STATUS.md` next steps |
| Real Hermes-agent traffic on a 7900 GRE: MTP n=3 + p-min 0.75, acceptance 0.87-0.96, no-MTP 28.5-28.8 → with-MTP 44.5-53.8 tok/s (+54%) | [`sweeps/radeon.md`, PR #19, @lsunay's section](https://github.com/sudoingX/qwen38-mtp/blob/master/sweeps/radeon.md) | 2026-09 | Verified (source read) | Suggests this repo's synthetic-text acceptance (55-90%) may be a pessimistic floor vs. real agent traffic; not directly measured on this GPU |
| 2× 7900 XTX (Reddit): MTP acceptance 73% on benchmark text, 87% with 86K of real context, ~64% with real coding-agent traffic | Reddit (fetch blocked, not independently verified) | 2026 | Hypothesis | Nuances the two claims above — real-agent acceptance on this GPU is still unmeasured; don't assume ~0.9 |
| ISTA-DASLab GSQ-RCO HF repo, discussion 6: RTX 5060 Ti, IQ3_S KV q8: 30 → 17 tok/s at 112K filled; IQ3_XXS-MTP: 54.6 → 25.2 at 118K | [HF discussion #6](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF/discussions/6) | 2026 | Verified (corroborates) | Same shape as this repo's own falloff (58-69 empty → ~27 at 128K) on different hardware — [`docs/measurements/depth.md`](measurements/depth.md) |
| gist: 7900 XTX, ROCm 7.2.4, Q3_K_M + separate MTP Q4_0 draft, KV q8/q8: 190,000 real tokens → 19.45 tok/s (9/17 accepted, synthetic, few output tokens) | [gist.github.com/ojus1](https://gist.github.com/ojus1/f7b77c8f032a5895fc3e3f5849ae5bd4) | 2026 | Verified (corroborates) | Consistent with this repo's 22-29 tok/s at 190K (400-token response) — [`docs/measurements/depth.md`](measurements/depth.md) |
| "TILE allocates ~16 GiB extra at 262K context" | [llama.cpp issue #21526](https://github.com/ggml-org/llama.cpp/issues/21526) (AI-summarized citation) | 2026 | Refuted (off by ~16x) | The f16 copy is one layer's K+V (~1 GiB at 262K), inside this repo's measured 1,360 MiB compute buffer — [`docs/measurements/memory.md`](measurements/memory.md) |
| GPU spills weights to GTT with no warning at load time | [llama.cpp issue #26432](https://github.com/ggml-org/llama.cpp/issues/26432) | 2026-08-02 | Verified (issue exists) | Not observed here: GTT stayed at 8 MiB with 0 evicted at 190-240K depth — [`docs/measurements/memory.md`](measurements/memory.md) |
| Prompt checkpoints are "always invalidated on hybrid/recurrent models" | [llama.cpp issue #24055](https://github.com/ggml-org/llama.cpp/issues/24055) | 2026-06-03 | Hypothesis | Not independently re-verified in this repository yet |
| PR #28391 would enable ngram-mod by default and make `--spec-type` additive (`draft-mtp` -> `[ngram-mod, draft-mtp]`) | [llama.cpp PR #28391](https://github.com/ggml-org/llama.cpp/pull/28391) (open, unmerged as of 2026-09-29) | 2026-09-29 | Tracked | Not tested; re-measure the profile when an engine update includes it — [`docs/measurements/speculative.md`](measurements/speculative.md#n-gram-stacked-on-mtp-how-llamacpp-combines-them-source-reading-2026-09-29) |
| `--spec-type draft-mtp,ngram-mod` works on Qwen3.8-27B (Vulkan, gfx1151), mentioned in passing, no numbers; the reported bug is combining it with an external `-md` draft | [llama.cpp issue #27839](https://github.com/ggml-org/llama.cpp/issues/27839) (open) | 2026-09-29 | Hypothesis | Not tested; A/B prepared, not run — same doc as above |
| Greedy output diverges from vanilla with draft-mtp/draft-dspark | [llama.cpp issue #25618](https://github.com/ggml-org/llama.cpp/issues/25618) (open) | 2026-09-29 | Hypothesis | Related to this repo's own finding that text is not bit-identical across MTP n at temperature 0 — [`docs/measurements/speculative.md`](measurements/speculative.md) |
| Qwen3.8-27B, greedy, reasoning/prose/code/recall tok/s: MTP n=3 alone 51.63 / 55.81 / 69.20 / 81.80; MTP n=3 + ngram-mod (defaults 24/48/64) 51.66 / 55.92 / 68.42 / 324.32 — ngram-mod only pays on verbatim recall | [stew675, llama.cpp PR #27210 comment](https://github.com/ggml-org/llama.cpp/pull/27210#issuecomment-5382199265) (AMD hardware per the author's results README, not re-checked) | 2026-08-22 | Community measurement | Not reproduced; closest public match to this repo's prepared `mtp3-moddef` arm — [`docs/measurements/speculative.md`](measurements/speculative.md#n-gram-stacked-on-mtp-how-llamacpp-combines-them-source-reading-2026-09-29) |
| ngram-mod alone: code 52.43 vs. 52.45 tok/s baseline, recall 632.47 (Qwen3.8-27B Q4_K_M, RTX 5090) | [marcusds, llama.cpp PR #27210 comment](https://github.com/ggml-org/llama.cpp/pull/27210#issuecomment-5375448677) | 2026-08-21 | Community measurement | Not reproduced (different GPU vendor) |
| "ngram-mod + MTP vs MTP can be not clear. MTP is sometimes clearly superior" | [am17an, llama.cpp PR #28391 comment](https://github.com/ggml-org/llama.cpp/pull/28391#issuecomment-5542428547) | 2026-09-04 | Maintainer opinion | Not tested; motivates measuring before adopting |
| Qwen3.6 models fall into a `////` repetition loop after long sessions with MTP; one OpenCode user says ngram-mod sped the loop up ("780 t/s"); cause not established, also reported without ngram-mod | [llama.cpp issue #23577](https://github.com/ggml-org/llama.cpp/issues/23577) (open) | 2026-09-29 | Risk, unconfirmed on Qwen3.8 | Not observed here; the prepared A/B checks outputs for runaway repetition — [`docs/measurements/speculative.md`](measurements/speculative.md#n-gram-stacked-on-mtp-how-llamacpp-combines-them-source-reading-2026-09-29) |
| A stuck-loop escape for ngram-mod is in progress ("Same for Qwen3.x models, using ngram-mod" in its thread) | [llama.cpp PR #25819](https://github.com/ggml-org/llama.cpp/pull/25819) (open, WIP) | 2026-09-29 | Tracked | Re-check whether an engine update includes it before adopting ngram-mod |


## KV / weight quantization quality

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| KV bytes/token math: 16 of 64 layers carry growing KV, 4 KV heads, head_dim 256 → 64 KiB/token f16, 34 KiB q8_0, 18 KiB q4_0 | X/Twitter thread, @bountyAIhunter | 2026-08-16/17 | Verified | Matches this repo's own measured VRAM exactly at 204,800 tokens KV q8/q8 (21,679 MiB peak) — [`docs/measurements/memory.md`](measurements/memory.md) |
| "The KV cache doesn't affect model performance/quality" | X/Twitter, @Naw50591287 | 2026 | Refuted | Contradicted directly by this repo's own KLD measurements — [`docs/measurements/kv-quality.md`](measurements/kv-quality.md) |
| BuffedMod variant of the adopted IQ3_S-mtp quant upcasts `output.weight` (the LM head) for better quality at the same quantization level | [tooltd/Qwen3.8-27B-GSQ-RCO-BuffedMod-GGUF](https://huggingface.co/tooltd/Qwen3.8-27B-GSQ-RCO-BuffedMod-GGUF) | 2026 | Hypothesis | Not downloaded or measured here — candidate for a future KLD/speed comparison against the currently adopted quant |

## GPU firmware, thermals and power

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Thermal/power limits are set by the GPU's own firmware and must be read from the hardware, not assumed | ChatGPT round, item F13 | 2026-09-25 | Verified (own primary source) | Read directly from `/sys/class/hwmon` on this GPU: memory critical 108°C/emergency 113°C, junction 110/115°C, edge 100/105°C, power limit 303 W default (min 272, max 350) — [`docs/measurements/thermals-power.md`](measurements/thermals-power.md) |
| 7900 XTX Vulkan, different model, 272 W vs. 302 W: −4% prefill, −1.3% generation at short context | Reddit (not independently verified) | 2026 | Hypothesis | Power tuning is explicitly deprioritized for this repository — see `docs/STATUS.md` |
| RTX 3090 power sweep: MTP is more power-sensitive than no-MTP (350→250 W: −26% with MTP vs. −21% without) | [`sweeps/rtx-3090.md`](https://github.com/sudoingX/qwen38-mtp/blob/master/sweeps/rtx-3090.md), @ctaylor83's section | 2026-09-15 | Verified (source read), different GPU | Not directly transferable across CUDA/GDDR6X vs. RDNA3/GDDR6; not tested here — power tuning deprioritized |
| LACT has known RDNA3 power-reporting quirks (reported power draw doesn't always match the applied limit) | [ilya-zlobintsev/LACT#237](https://github.com/ilya-zlobintsev/LACT/issues/237) | 2026 | Hypothesis | Not independently checked here; this repo reads the power limit from sysfs `power1_cap*` directly rather than through LACT — see `docs/measurements/thermals-power.md` |

## OS / driver

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Some `linux-cachyos` rolling-kernel builds get stuck at the lowest GPU P-state under ROCm compute load | [CachyOS/linux-cachyos#888](https://github.com/CachyOS/linux-cachyos/issues/888) | 2026-06-20 | Verified (issue exists) | Workaround (LTS kernel) documented in `docs/hardware/gpu-7900xtx.md`; check whether it still reproduces on the kernel in use |
| Plasma Wayland session freeze on some rolling-kernel builds with this GPU | [CachyOS/linux-cachyos#1035](https://github.com/CachyOS/linux-cachyos/issues/1035) | 2026-09-12 | Verified (issue exists) | Same caveat as above |

## Methodology references

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| RULER-style multi-key retrieval with distractors is a reasonable long-context quality methodology beyond simple needle-in-haystack | [github.com/NVIDIA/RULER](https://github.com/NVIDIA/RULER) | — | Verified (methodology reference) | Adopted-profile test is complete: 68/68 exact match through 240K; only the broader 190K sample remains pending — see [`docs/measurements/depth.md`](measurements/depth.md) |
| "ctx"/context figures in social-media posts usually mean *reserved* context (`-c`), not *filled* context — inflated tok/s numbers often hide this | Several X/Twitter threads (§ audit review) | 2026 | Verified (methodology finding) | Applied throughout `docs/measurements/`: every figure states filled depth, not just `-c` |

## Agent harness / API compatibility (context only)

This repository's scope is the GPU and the model (`AGENTS.md`); it doesn't recommend or maintain a
particular coding-agent harness. These entries are recorded as context, not a recommendation.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| `llama-server` implements an Anthropic-compatible Messages API endpoint | [Hugging Face blog, ggml-org](https://huggingface.co/blog/ggml-org/anthropic-messages-api-in-llamacpp) | 2026 | Hypothesis | Not exercised here; this repo's own harness wiring (`AGENTS.md`) targets the OpenAI-compatible `baseUrl` shape, not this endpoint |
| `pi` coding agent and its `oh-my-pi` fork can be configured against an OpenAI-compatible provider pointing at `llama-server`; `pi` has a reported RPC hang issue | [earendil-works/pi](https://github.com/earendil-works/pi), [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi), [pi issue #2078](https://github.com/earendil-works/pi/issues/2078) | 2026 | Hypothesis | Not evaluated against this repository's server — kept here only as context for the harness-agnostic wiring already described in `AGENTS.md` |

## Community claims reviewed 2026-09-26

Verdict for this section: **verified** (matches a primary source read directly), **unverified**
(post/thread not fetchable, or no independent reproduction found), **not applicable** (accurate but
doesn't cover this repository's stack or operating depth). Full test plan for the candidates below:
private working notes (not published).

| Claim | Source | Status | Note |
|---|---|---|---|
| 7900 XTX Vulkan command (UD-Q4_K_M, 131072 ctx, KV q4_0/q4_0, `-ub 512`, draft-mtp n-max 3, p-min 0.8) claiming Vulkan ~15% faster than ROCm | X/Twitter, @SergioSV96 (post not fetchable) | Unverified | Flags are valid on current master; "always 15% faster" isn't supported — [issue #20934](https://github.com/ggml-org/llama.cpp/issues/20934) and [discussion #15021](https://github.com/ggml-org/llama.cpp/discussions/15021) show a split (ROCm wins pp, Vulkan often wins tg), short context only, nothing at 100K+ |
| llm-bench.io KV cache quantization guide: 7900 XTX, Qwen3.8-27B UD-Q4_K_M, 65,536 ctx only; KV VRAM (guide's own units) f16 5,891 MB / q8_0 3,972 / q5_0 3,204 / q4_0 2,948; tg 40.4/51.7/47.6/50.3 tok/s; quality via LLM judge | [llm-bench.io KV guide](https://llm-bench.io/guides/kv-cache-quantization) | Not applicable | Guide itself states 128K-240K not tested. Linked Reddit r/LocalLLM thread not fetchable; comments claiming q8 KV "amnesia" beyond 150K are anecdotal, no reproducible report found |
| Long-context KV quality: q8_0 near-lossless to ~41K, Qwen3.6/3.8-27B tolerant even at q4_0 on short tasks; bf16 vs. f16 KV: f16 range-clips on natively-bf16 Qwen3.5, bf16 KV is slower | [discussion #23470](https://github.com/ggml-org/llama.cpp/discussions/23470), [issue #20035](https://github.com/ggml-org/llama.cpp/issues/20035), [discussion #24750](https://github.com/ggml-org/llama.cpp/discussions/24750), [issue #20497](https://github.com/ggml-org/llama.cpp/issues/20497) | Verified (source read), not applicable beyond ~41K | No external data at 128K+ for Qwen3.x's hybrid architecture — motivates a quality re-test at ~220K |
| BeeLlama v0.4.7 KVarN KV cache (K/V independent, per-head Hadamard rotation + per-axis normalization over 128-token tiles) beats q4_0 KLD at similar size | [Anbeeld/beellama.cpp](https://github.com/Anbeeld/beellama.cpp) v0.4.7 (2026-09-25, MIT, base ~upstream b10830), [author benchmarks](https://anbeeld.com/articles/kvarn-kv-cache-implementation-and-benchmarks) | Tested/rejected (2026-09-26) | Author's own benchmark (Qwen 3.6 27B, RTX 3090), no third-party reproduction. Measured here on gfx1100: KVarN's KLD is ~2.7x q8/q8's at every bit width (worse than q8/q5_1), BeeLlama itself ~18-22% slower than `hip-kvmix` — [`results/20260926-beellama-kvarn/`](../results/20260926-beellama-kvarn/), [`measurements/kv-quality.md`](measurements/kv-quality.md#beellama-kvarn-kld-2026-09-26) |
| 5060 Ti 16 GB + 3070 8 GB, UD-Q5_K_M, KvarN5 + MTP n2, 128K ctx: ~18 tok/s at 126K filled | X/Twitter, @Oluwaphilemon1 (post not fetchable) | Unverified | Different vendor (two smaller NVIDIA GPUs); order-of-magnitude consistent with a 5-bit vs. 8-bit KV expectation, not independently confirmed |
| exllamav3-rocm (HIP port of ExLlamaV3 + patched TabbyAPI): on RX 7900 XTX, ROCm 7.2.4, PyTorch 2.13.0+rocm7.2 — MTP decode 92 tok/s @32K / 66-68 @99K, DFlash2 107 @99K, prefill ~945 @99K, NIAH correct at 184,656 and 247,056 tokens | [phoenixhaxor/exllamav3-rocm](https://github.com/phoenixhaxor/exllamav3-rocm) README (created 2026-09-24) | Audited/deprioritized (2026-09-26) | Read-only audit: fork of turboderp exllamav3 @6b84a21b (inherits the #353 determinism fix shipped in v1.5.0), MIT, 14 commits in 2 days by one author (AI-assisted, disclosed), no CI, no security red flags; README numbers use synthetic repetitive prompts, single runs, 10-20% variance admitted, prefill measured with random tokens via the raw API — not comparable to ours. Deprioritized (least interest, 15.3 GB EXL3 model leaves less VRAM headroom) before a practical test — see `docs/STATUS.md` |
| lemonade-sdk/llamacpp-rocm latest builds and nasone32/llama.cpp-RDNA3-7900xtx-opt bring something new for gfx1100 | [lemonade-sdk/llamacpp-rocm](https://github.com/lemonade-sdk/llamacpp-rocm) b1331/b1332 (2026-09-24/25), [nasone32/llama.cpp-RDNA3-7900xtx-opt](https://github.com/nasone32/llama.cpp-RDNA3-7900xtx-opt) | Not applicable | lemonade's ROCm ~10.2 nightly build is just a current-master rebuild, nothing new for us; nasone32 has no commits since ~2026-09-10. Both stay discarded |

## Not pursued

- `unsloth/Qwen3.8-27B-GGUF` `UD-IQ3_S` (12 GB) as an alternative quant — candidate for a
  perplexity/speed comparison at the same size budget, not tested (`docs/models/qwen38-27b-quants.md`).
- Quantized vision projector (`mmproj` Q5_K-MIX, ~0.9 GB) — HF-reported 74.58% vs. 74.93% for BF16
  on 11 benchmarks; not pursued because vision was deprioritized for this hardware.
- Power-limit and undervolt tuning (LACT) — explicitly deprioritized; see `docs/STATUS.md`.

## Ideas for future MoE models (not pursued, 2026-09-29)

All claims below are the authors' own and are unverified here.

- [Strata](https://github.com/Niko1221/Strata) (engine 0.1.24, 2026-09-29): a CUDA-only custom
  engine for Qwen3.8-Flash-Next (MoE, 24,576 experts); `CMakeLists.txt` requires CUDAToolkit and
  `docs/MULTI_GPU.md` lists AMD as unsupported, so it does not run on this card. Ideas (author
  claims, RTX 5070): KV streaming (`--kv-resident`: only the most-read part of the KV in VRAM, the
  rest in RAM; claims Q2_0 at 262K 50.9 -> 62.6 tok/s); an adaptive VRAM expert cache with the CPU
  computing uncached experts in place concurrently; MTP plus gated prompt lookup (claims code
  edits 6-11% faster); `--calibrate` per-machine settings search. llama.cpp has no KV streaming or
  adaptive expert cache; static `--n-cpu-moe`/`-ot` exist.
- Qwen3.8-Flash-Next fit note (file sizes from the HF API, ISTA-DASLab repos): shard 1 (weights)
  Coder IQ1_M 29.6 GB, Q2_0 37.6 GB, IQ2_XS 39.2 GB, IQ3_XXS 47.0 GB, IQ3_S 54.8 GB; shard 2 is a
  per-layer n-gram embedding table of 28.8 GB, identical across variants. The model card says
  standard llama.cpp runs it and `-lm mmap --lazy-mode on` keeps shard 2 memory-mapped on disk
  (needs an SSD). Our b11146 `/usr/bin/llama-server` `--help` has `--lazy-mode` and `--n-cpu-moe`
  (b11160 not checked). With 24 GB VRAM + 32 GB RAM, Coder IQ1_M might fit via `--n-cpu-moe`
  (estimate, unmeasured). Decision 2026-09-29: not pursued now; wait for better future models.
