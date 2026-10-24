# Sources: alternative stacks and model ideas

vLLM on ROCm, HyperQwen and low-bit forks, items not pursued, and ideas for future MoE models. Status labels and the one-row-per-claim rule are defined in [`SOURCES.md`](SOURCES.md).

## vLLM on ROCm and HyperQwen (2026-10-03)

Goal checked: can vLLM replace llama.cpp here at 200K-262K context on one 24 GB card? No run.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| HyperQwen (patched vLLM 0.30.0, int8 Marlin GEMM, KVarN 4/2-bit KV, MTP and DFlash2) gives Qwen3.8-27B 127 tok/s, 381 while quoting the prompt, and 67/164 at 240K on one RTX 3090 | [syv-ai/HyperQwen](https://github.com/syv-ai/HyperQwen) | 2026-10 | source-checked (README): CUDA only, no ROCm/HIP path mentioned; fill depth behind the 240K figure not confirmed | not applicable (NVIDIA kernels) |
| vLLM lists the Radeon RX 7900 series (gfx1100/1101) as a ROCm target, ROCm 6.3 or newer; v0.28.0 notes "ROCm enablement on gfx11" | [vLLM GPU install docs](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/), [releases](https://github.com/vllm-project/vllm/releases) | 2026-10 | source-checked (page opened via WebFetch summary) | none |
| On AMD GPUs vLLM supports only FP8 W8A8 and GGUF; AWQ, GPTQ, Marlin, INT8 W8A8 and bitsandbytes are unsupported. GGUF is "highly experimental and under-optimized" | [quantization README](https://github.com/vllm-project/vllm/blob/main/docs/features/quantization/README.md), [GGUF docs](https://docs.vllm.ai/en/latest/features/quantization/gguf/) | 2026-10 | source-checked (table and GGUF quote); the table is stale: it has no compressed-tensors W4A16 row, which runs on gfx1100 per #56992 | none |
| Qwen3.8-27B INT4 W4A16 on a 7900 XTX, vLLM 0.27.1.dev, 2K context, no MTP: 29.1 tok/s with bf16 KV, 21.6 with fp8 KV (gfx11 has no native FP8) | [vLLM issue #56992](https://github.com/vllm-project/vllm/issues/56992) | 2026 | source-checked | none; compare 68.9 tok/s here at empty context with MTP n=3 |
| Unmerged PR ("DO NOT MERGE") adds gfx1100 W4A16 GEMM and INT8/INT4 KV; 113-119 tok/s with MTP k=3 up to 167K, on **4x** 7900 XTX (TP4) | [vLLM PR #57925](https://github.com/vllm-project/vllm/pull/57925) | 2026-09 | source-checked (page opened via WebFetch summary): draft tracking branch, no split-out PR merged, "No CI covers gfx1100" | none; no single-GPU number |
| vLLM MTP speculative decoding for Qwen 27B is tested on MI300X/MI355X only, not Radeon | [vLLM blog 2026-08-23](https://vllm.ai/blog/2026-08-23-speculative-decoding-amd-gpus) | 2026-08 | source-checked (page opened via WebFetch summary) | none |

Conclusion: not pursued. Mainline vLLM has no validated 4-bit path for gfx1100, the only
single-card number is less than half of ours without MTP, and 262K on 24 GB depends on unmerged
KV code (INT8 KV for gfx11 is still an open request, [#33480](https://github.com/vllm-project/vllm/issues/33480)).
Re-checked 2026-10-03 against the pages above: unchanged. Revisit when the INT8 KV and RDNA3
attention kernels of PR #57925 land as separate merged PRs.

## vLLM ROCm forks and low-bit llama.cpp forks (2026-10-03)

Checked for one gfx1100 at 200K-262K context. No run.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Paiton: vLLM plugin plus a proprietary compiled runtime; "Tested GPU: one Radeon AI PRO R9700, 32 GB, RDNA4 / gfx1201. Other GPUs have not been qualified." Its Qwen3.8 guide (3-bit W3A4 + DFlash2) reports 72-76 tok/s decode at a 257,992-token prompt (TTFT 126 s) | [Eliovp-BV/paiton-vllm-plugin](https://github.com/Eliovp-BV/paiton-vllm-plugin) | 2026-10 | not applicable (gfx1201, FP8/FP4 WMMA, closed runtime) | none; only a reference that depth decode can be much faster with better kernels |
| vllm-radiance: vLLM v0.30.0 fork with hand-written gfx1201 kernels, ROCm 7.14; primary qualified setup is two R9700 (TP2) with mandatory FP8 KV | [magiccodingman/vllm-radiance](https://github.com/magiccodingman/vllm-radiance) | 2026-10 | not applicable (gfx1201, two GPUs, FP8 KV) | none |
| ROCmFPX: llama.cpp fork with AMD FP2-FP8 weight formats; for gfx1100 "dedicated build scripts are provided; results vary". A post claiming "ROCmFPX v2 TP2 + MTP5 + Ngram on 2x R9700" has no published numbers | [charlie12345/ROCmFPX](https://github.com/charlie12345/ROCmFPX) | 2026-10 | source-checked (README); the TP2 claim unverified | none; needs another model file |
| serrynaimo/ROCmFPX (fork of ROCmFPX): Swift-1.5-Qwen3.8-27B ROCmFP4 "MQ-Q4S" (14.97 GiB), `q4_0`/`q4_0` KV, `-c 81920`, MTP n=4 on an RX 7900 **XT** (Windows, ROCm 7.2): decode 43.8 prose / 65.3 code tok/s (34.4 without MTP), prefill 580/516/455 tok/s at 18K/45K/74K; "nothing here has been measured on an XTX". Commit `0200c066fc` claims the `sched_group_barrier` in `dequantize_V_q4_0` (from [#29478](https://github.com/ggml-org/llama.cpp/pull/29478), present in b11454 `fattn-common.cuh:422`) costs ~25% on the FA vec kernel with 2+ query columns (MTP verify) with `q4_0` KV; not reported upstream. Its D=256 WMMA FA and tiled gated delta-net kernels (pwilkin, no upstream PR) dispatch on RDNA3_5 only; its TOP_K kernels are upstream [#28313](https://github.com/ggml-org/llama.cpp/pull/28313) (open), an op the `qwen35` graph does not use | [serrynaimo/ROCmFPX](https://github.com/serrynaimo/ROCmFPX) @ `42ecc32338` | 2026-10-06 | source-checked (README, recipe doc, commit diffs vs. b11454); speed numbers claimed by the fork | none; the barrier only touches `q4_0` V, not our `q8_0`/`q5_1`. Open lead: A/B the barrier on the XTX with `q4_0` KV and report on #29478 |
| BeeLlama: the only release after the tested v0.4.7 is preview-v0.4.8 (2026-10-01), an upstream sync still built with ROCm 7.2 | [Anbeeld/beellama.cpp](https://github.com/Anbeeld/beellama.cpp) | 2026-10-01 | source-checked (release list) | v0.4.7 measured 2026-09-26 ([TRIED.md](TRIED.md)) |
| KVarN (Huawei, arXiv 2606.03458): at 262,144 tokens kvarn5/kvarn4 KV would take 4,992 MiB vs. 7,424 MiB for our `q8_0`/`q5_1` | [author article](https://anbeeld.com/articles/kvarn-kv-cache-implementation-and-benchmarks) | 2026-10 | source-checked (sizes computed for this model) | KLD measured 2026-09-26 (~2.7x q8/q8); speed screen 2026-10-03: tg64 @128K 10.53 vs. 16.64 tok/s for `hip-kvmix` q8_0/q5_1 (-37%), rejected — [`results/20261003-kvarn-beellama-screen/`](../results/20261003-kvarn-beellama-screen/README.md) |

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
- **Update, later on 2026-09-29 (Strata v0.1.25/v0.1.26)**: the "CUDA-only, does not run on this
  card" statement above is superseded. v0.1.25 merged an experimental Linux AMD HIP backend
  (gfx1100 only) and a `--kv k8v4` KV cache; v0.1.26 added a low-RAM mode (experts memory-mapped
  from disk). The author's "8GB+ AMD GPU", "1,250 tok/s prompt" and "k8v4 +10%" claims are checked
  against upstream's own docs in
  [`docs/models/strata-flash-next.md`](models/strata-flash-next.md).
- **Update 2026-10-06 (upstream v0.1.40, xyzzing/Strata v0.1.39-rocm.1)**: a community post for
  the [xyzzing gfx1100 fork](https://github.com/xyzzing/Strata) claims decode above 100 tok/s on
  an RX 7900 XTX. Status: hypothesis, not found in any primary source (best: 88.4 tok/s, warm,
  repeated short request, 96 GB RAM). Its "+22.8% prefill" is source-checked but replaces a
  fallback llama.cpp does not have. Details in
  [`docs/models/strata-flash-next.md`](models/strata-flash-next.md#review-2026-10-06-v0140-and-the-xyzzing-gfx1100-fork).
- **Update 2026-10-08 (upstream v0.1.40.1 to v0.1.41)**: `docs/AMD_HIP.md` reports a 74K prompt on an
  RX 7900 XTX (gfx1100, reporter's run): 2,583 tok/s with the lend-coverage line complete (6201 of 6201),
  1,810 tok/s with it short (5093 of 6202). Status: reporter-measured, hypothesis here; mechanism
  source-checked. The "925 to 2,503 tok/s" chain is also reporter-measured and not re-measured upstream.
  "A 32 GB PC with a 24 GB GPU runs Q2_0, IQ2_XS and the Coder resident (~16-18 GB of experts in RAM, the
  GPU holds ~18 GB)" (`docs/DETAILS.md`): source-checked as setup's own heuristic (VRAM - 5 GB at 32K; the
  engine sizes the copy from `MemAvailable` minus 4 GiB), hypothesis for this machine, where the computed
  budget only fits Q2_0 at 32K and the Coder at any depth.
  Details in [`docs/models/strata-flash-next.md`](models/strata-flash-next.md#review-2026-10-08-releases-amd-notes-and-ram-budget).
- **Update 2026-10-24 (upstream v0.2.4.2, Coder shard 1 replaced 2026-10-19)**: the new Coder claims SWE-bench
  Verified 75.60 to 79.20 (card, source-checked, not reproduced); Strata setup still pins the old shard (re-pin:
  open PR #3445), but accepts the new one through `--gguf-dir` (locally verified). Details in
  [`docs/models/strata-flash-next.md`](models/strata-flash-next.md#review-2026-10-24-v0242-the-2026-10-19-coder-and-the-27b).
- **[sybil-solutions/glm53-flash-offload](https://github.com/sybil-solutions/glm53-flash-offload)
  (checked 2026-10-08, README only)**: GLM-5.3-Flash EXL3 3.05 bpw (125 GB; 42 MoE layers x 288
  experts, 8 active, 9.4 MB per expert) on one 24 GB RTX 3090, built on exllamav3 + an SGLang
  base image (Docker, NVIDIA container toolkit; no ROCm path). Three-tier expert cache: ~1,300
  hottest experts in VRAM (12.4 GB), a pinned RAM tier sized by `--memory`, all experts on NVMe
  (117 GB, O_DIRECT), plus a 22-thread AVX2 CPU lane computing RAM experts in place. Claimed
  decode (1 user): all-RAM `fast` (~218 GiB RAM) 28.2 tok/s; `nvme` 55 GiB 17.3; `nvme` 16 GiB
  12.9; `nvme-exact` 8.3; prefill only at 8K/32K, no maximum context stated. Test rig: EPYC 7443P,
  8-channel DDR4, 4x Samsung 9100 PRO (PCIe 5.0) in RAID0. Status: source-checked (README), speed
  numbers claimed by the author. Not applicable here: CUDA only; 31 GiB RAM allows only the 16 GiB
  mode, and our single PCIe 4.0 NVMe (KIOXIA Exceria Plus G3) would likely cut it to a few tok/s
  (estimate, unmeasured). Useful as a reference for decode vs. RAM-tier size in an expert cache.
- **[NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-GGUF](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-GGUF)
  (checked 2026-10-15, card + GGUF header via HTTP range read; not downloaded or run)**: text+vision
  MoE, 74B total / 9B active, QAD-trained so experts in IQ2_XXS (2.06 bpw) are the native format.
  Card sampling: temperature 1.0, top_p 0.95 (matches `general.sampling.*`). Vendor hardware: NVIDIA
  Ada/Blackwell only; recipes ask for 32 GB+ (65K context with `mmproj` and DFlash drafter).
  Files (HF API): model 20.51 GiB, `mmproj` 1.61 GiB, LiLiCorr DFlash drafter 0.93 GiB.
  Header: `nemotron_h_moe`, 88 blocks = 40 Mamba + 40 MoE + 8 attention (2 KV heads, head 128);
  tensor types IQ2_XXS (experts), NVFP4 (Mamba `ssm_in`/`ssm_out` plus F32 `.scale` tensors), Q8_0
  (embeddings/output); routed experts **vary per layer** (240/304/368/432/496), top-k 9.
  - **b11454 cannot load it** (from source, not run): `src/models/nemotron-h.cpp` creates expert
    tensors with the global `expert_count` (496) and has no `ssm_in.scale`/`ssm_out.scale`. Needs a
    newer llama.cpp; HIP kernel speed for NVFP4/IQ2_XXS on gfx1100 is unknown.
  - **Context is not the constraint**: only 8 layers keep KV, 4,096 elements/token, so 262K costs
    ~1.06 GiB at q8_0 (~2.0 GiB f16); Mamba state ~0.2 GiB, fixed. Estimate text-only at 262K q8_0:
    ~22.3-22.8 GiB (compute buffer guessed at 0.5-1.0 GiB, unverified); `mmproj` or the drafter would
    not fit alongside.
  - **A sub-15 GB requant is unlikely to help**: it needs ~1.5 bpw experts (IQ1_S/IQ1_M) requantized
    from BF16, losing the QAD training (expected quality loss, unmeasured).
  Status: source-checked (card, file sizes, header); fit and speed are hypotheses. Next: build
  llama.cpp master for gfx1100, load text-only with KV q8_0, measure peak VRAM at 262K.
