# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Published the `hip-kvmix` engine artifact as the
  [`engine-b11160-rocm10-gfx1100-kvmix` GitHub release](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11160-rocm10-gfx1100-kvmix).

### Changed

- Ran KVMem trial round 1 on ROCm (2.3x decode at 244K, ~15 GiB VRAM; 7/8 retrieval at budget 28,672, 8/8 at 49,152, one 190K crash): promising, not adopted (`results/20260930-kvmem-trial/README.md`).
- Rewrote `AGENTS.md` as a short index (read-when pointers, rules, commands, evidence discipline)
  and added the documentation workflow (single owner per fact, routing table, word budgets) as
  `docs/STYLE.md` §8.
- Corrected host RAM to 32 GiB installed / 31.25 GiB usable; added a speed-levers summary
  (`docs/STATUS.md`).
- Enabled harness `compaction.handoffSaveToDisk` and prepared a KVMem trial (`docs/ENGINES.md`).
- Measured compaction cost (14 compactions, median ~83 s to next turn), checked a third-party
  compaction/KVMem claim, set the harness threshold to 75% (`docs/measurements/agent-traffic.md`,
  `docs/SOURCES.md`).
- Analyzed real agent traffic (1,301 turns): 89% generation, ~78% reasoning, MTP acceptance 0.66,
  base prompt ~14.5K tokens; no config change (`docs/measurements/agent-traffic.md`).
- Analyzed prompt-cache reuse (7 logs, ~330 requests): reuse works, one 42.2 s FIFO-eviction miss
  mode at `--ctx-checkpoints 4`; documented PR #29393 and the unusable OrcaSAQ-2-27B quant
  (`docs/measurements/memory.md`, `docs/models/qwen38-27b-quants.md`).
- Re-tested Vulkan with the memory clock pinned: decode nearly doubles at 64K (10.64 -> 19.77
  tok/s) but HIP still wins +63% at depth 0 and +18% at 64K; no change
  (`docs/measurements/engines.md`, `results/20260929-vulkan-mclk-pinned/`).
- Measured spec-off at 240K fill: 11.2 vs. 23.3 tok/s with MTP n=3 (+109%), correcting the
  "MTP gain shrinks at depth" conclusion (`docs/measurements/speculative.md`).
- Ran the community `probe.py` A/B (empty context): 37.2 -> 68.9 tok/s (+85%); n=2 ties, n=4 and
  `--spec-draft-p-min` lose; added `bench/probe_ab.py` (`docs/measurements/speculative.md`).
- MTP n=4 at 240K on the adopted flags: -8% mean tg vs. n=3, 66% vs. 71% acceptance; output is
  not bit-identical across n=2/n=3/`-ub 256` at temperature 0 (`docs/measurements/speculative.md`).
- Re-validated 240K retrieval on the exact adopted flags: 8/8, cumulative 68/68 exact match
  (`docs/measurements/depth.md`).
- Closed round 4 (speed at depth) with no config change: root cause is a GQA-6 attention-bandwidth
  limit in HIP's quantized-KV FlashAttention (~24% of peak); Vulkan depth screen inconclusive
  (`docs/measurements/depth.md`, `docs/DECISIONS.md`).

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
