# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Published the `hip-kvmix` engine artifact as the
  [`engine-b11160-rocm10-gfx1100-kvmix` GitHub release](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11160-rocm10-gfx1100-kvmix).

### Changed

- Analyzed prompt-cache reuse from 7 server logs (~330 coding-agent requests): prefix reuse works,
  with one known 42.2 s miss mode (FIFO eviction of the base-prompt checkpoint at
  `--ctx-checkpoints 4`); no config change. Documented llama.cpp PR #29393's expected (unmeasured)
  effect on the HIP build and the evaluated-but-unusable OrcaSAQ-2-27B quant. See
  `docs/measurements/memory.md`, `docs/ENGINES.md`, `docs/models/qwen38-27b-quants.md`.
- Re-tested Vulkan vs. HIP with the GPU memory clock pinned at 1249 MHz (`-ub 512`): pinning
  nearly doubles Vulkan decode at 64K depth (10.64 → 19.77 tok/s), but HIP still wins tg +63% at
  depth 0 and +18% at 64K, so the earlier "Vulkan loses because of the memory clock" explanation
  is only half right. Vulkan stays reference-only, no config change. See
  `results/20260929-vulkan-mclk-pinned/` and `docs/measurements/engines.md`.
- Measured the missing spec-off reference at 240K fill on the adopted profile: 11.2 tok/s vs.
  23.3 with MTP n=3 (**+109%**), correcting the earlier "MTP's gain shrinks at depth" conclusion,
  which compared against a KV q8_0/q8_0 spec-off baseline (14.9 tok/s on the same engine: V q5_1
  costs spec-off decode 25%). See `docs/measurements/speculative.md`.
- Ran the sudoingX/qwen38-mtp community `probe.py` A/B on the adopted profile (empty context):
  spec-off 37.2 → MTP n=3 68.9 tok/s (+85%); n=2 ties, n=4 and `--spec-draft-p-min` 0.60/0.75
  lose. Added `bench/probe_ab.py`.
- Measured MTP n=4 at 240K depth on the exact adopted flags (`-ub 256`): -8% mean tg vs. n=3
  (21.4 vs. 23.3 tok/s), 66% vs. 71% acceptance — n=3 stays adopted. Also found generated text is
  not bit-identical across n=2/n=3/`-ub 256` at temperature 0 for essay and code tasks.
- Re-validated long-context retrieval quality at 240K on the exact adopted server flags (MTP n=3,
  `-ub 256`, not just the KV q8_0/q5_1 variant, using `bench/longctx_quality.py`'s `--mtp-n`/
  `--extra` options): 8/8 exact match — cumulative 68/68 exact match, 32K-240K fill.
- Closed round 4 (speed research at depth for `262k-q8q51-mtp`) with **no config change**:
  identified the root cause of the long-context decode slowdown (a GQA-6 attention-bandwidth limit
  in HIP's quantized-KV FlashAttention kernels, reaching only ~24% of peak memory bandwidth) and
  screened a Vulkan depth re-test, which was inconclusive (unpinned memory clock, `-ub 256`
  prefill collapse) and not pursued further. See `docs/measurements/depth.md`,
  `docs/measurements/engines.md`, and `docs/DECISIONS.md`.

## [2026-09-26]

### Changed

- Adopted `262k-q8q51-mtp` (262,144 context, KV `q8_0/q5_1`, MTP n=3, `-ub 256`) as the single
  default profile — see `docs/DECISIONS.md` and `docs/STATUS.md`.
- Reduced `models.toml` to a single model/profile and a single harness provider entry
  (`local-262k`), removing overlapping alternatives.
- Validated long-context retrieval quality: 60/60 exact match, 0 loop detections, 32K-240K fill.
- Evaluated and rejected the ROCm 10.0.0 runtime libraries (kept the ROCm 10 compiler) and
  BeeLlama v0.4.7's KVarN KV cache quantization — see `docs/measurements/engines.md` and
  `docs/measurements/kv-quality.md`.
### Added

- Added a systemd unit for the permanent 272 W power cap.
- Added community and CI files (`CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `CITATION.cff`, issue/PR templates, GitHub Actions CI) for public contributions.

## [2026-09-25]

### Added


- Initial curated public release: config, launcher, benchmark scripts, and measurement
  write-ups for running long-context Qwen3.8-27B on an AMD RX 7900 XTX.
