# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Strata v0.2.8 + Qwen3.8-Flash-Next IQ2_XS installed (`models.toml` `[strata.iq2_xs]`, mapped mode, 262K, KV int8): warm short decode 59-65 tok/s, 240K decode 36.7 tok/s, 128K retrieval 8/8; long prompts need `GPU_PINNED_MIN_XFER_SIZE=1048576` on ROCm or every memory mode stalls; hipBLASLt table and a larger prompt chunk rejected ([`results/20261030-strata-iq2xs-baseline/`](results/20261030-strata-iq2xs-baseline/README.md)).
- Strata SOP: IQ2_XS install with `--low-ram mmap`, the ROCclr userptr stall and its fix, setup's stale `args` and missing hipBLASLt rebuild, the start wrapper's server log ([`docs/sop/strata.md`](docs/sop/strata.md)).
- Strata IQ2_XS plan challenged: llama.cpp's `--moe-cache-mib` (merged, in b11846) still measures below Strata for Flash-Next, so Strata stays; first IQ2_XS session must confirm `tool_call_recovery` (default from v0.2.8) and count valid tool calls; Qwen4 has no confirmed date ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#alternative-without-strata-plain-llamacpp)).
- Next Strata model chosen: IQ2_XS (install planned, not started); Strata's own fit check on this PC keeps it out of the SSD while IQ3_XXS is not, and a five-step install plan with first-start log checks is written ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#fit-check-2026-10-30-iq2_xs-and-iq3_xxs-without-ssd-reads)).
- Strata 32 GB field evidence: IQ2_XS 48.7-51.4 and IQ3_XXS 33.1-38.7 tok/s on an RTX 3060 12 GB with SSD reads (upstream, not reproduced), so IQ3_XXS stays a candidate; `STRATA_RAM_ADAPT` queued as tuning arm F4d; gfx1100 risks #4556 and #3463 noted ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#fit-check-2026-10-30-iq2_xs-and-iq3_xxs-without-ssd-reads)).
- Strata Coder IQ1_M shard 1 and pack deleted to make room for a full-expert size; fit check: on 32 GB neither IQ2_XS (~4-7 GiB short) nor IQ3_XXS (~11-14 GiB short) keeps every expert out of the SSD ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#fit-check-2026-10-30-iq2_xs-and-iq3_xxs-without-ssd-reads)).
- Reviewed a community Strata Windows IQ3_XXS config against this setup: the "speed-projection" control vector is a refusal projection (rejected), k8v4 and a 1400 MiB reserve already lost here. The Strata tuning plan gains F0 (update Strata and re-check every flag before each pickup, new models via C1 first) and F4 (`--spec-min-p 0.70`, `--prefill auto:16384`, four env switches); upstream now v0.2.8 ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#tuning-plan-2026-10-16-not-run)).
- Re-checked ROCmFPX at its new official repo (`ROCmFPX/ROCmFPX`): RDNA 3 is build/runtime support only and tuning targets RDNA 3.5; not tested ([`docs/SOURCES-alternatives.md`](docs/SOURCES-alternatives.md#vllm-rocm-forks-and-low-bit-llamacpp-forks-2026-10-03)).
- Strata reinstalled at v0.2.4.2 with the 2026-10-19 Coder IQ1_M (Gyro-S data removed); first start and smoke pass, speed and quality not yet measured on it ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#review-2026-10-24-v0242-the-2026-10-19-coder-and-the-27b)).
- `scripts/strata.py` (`status`, `apply`, `update`): Strata settings tracked in `models.toml` `[strata.*]` and re-applied after every Strata update; `local.toml` gains `strata_dir` ([`docs/sop/strata.md`](docs/sop/strata.md)).
- E4: probabilistic MTP draft sampling at 240K on the new engine is undecided with 3 temperature-1 samples (code +9.9%, copy -10.3%, wall -3.3%); not adopted, waits for the session replay ([`results/20261024-e4-mtp-prob-240k/`](results/20261024-e4-mtp-prob-240k/README.md)).
- `hip-kvmix` engine rebased to b11846 (same TILE patch): neutral at 240K, identical text, coding suite 6/6; a same-engine rerun showed up to ~6% cross-session spread, so engine A/Bs stay within one session ([`results/20261024-engine-b11846-240k/`](results/20261024-engine-b11846-240k/README.md)).
- `hip-kvmix` engine moves to b11820 + native `q8_0`/`q5_1` TILE FlashAttention (PR #30792 extended): 240K decode +18-27% with identical greedy text, coding suite 6/6; b11718 is the rollback ([`results/20261023-d1-pr30792q51-240k/`](results/20261023-d1-pr30792q51-240k/README.md)).
- Follow-up runs on the new engine: MTP n=4 still loses at 240K (n=3 stays); KV `q8_0`/`q8_0` at 245,760 is no faster and costs +591 MiB VRAM (quality-only ≤240K alternative); empty context is now 76.3 tok/s (39.1 without MTP); `spec_depth_bench.py` gains an `n4-map` variant ([`results/INDEX.md`](results/INDEX.md)).
- Qwen4 day-one checklist (card fields, engine support, FA shape check, 262K fit, quality, speed, MoE offload order) ([`docs/sop/new-model.md`](docs/sop/new-model.md#qwen4-day-one-checklist)).
- Engines b11820 and b11820 + native `q8_0`/`q5_1` TILE FlashAttention (PR #30792 extended) built as candidates; op level the MTP verify step is -29% at 240K; b11718 stays in production until the 240K A/B ([`results/20261022-fa-native-q8q51-tile-op-level/`](results/20261022-fa-native-q8q51-tile-op-level/README.md)).
- Decision: Gyro-S and Strata v0.2.0-beta are installed but not tested; Strata/Flash-Next work waits for a 24 GB Gyro size or Qwen4 ([`docs/DECISIONS.md`](docs/DECISIONS.md)).
- b11718 engine measured at 240K against b11454 + PR #29509 and kept; engine updates now take one 240K pair plus one coding-suite run ([`results/20261018-engine-b11718-vs-b11454-240k/`](results/20261018-engine-b11718-vs-b11454-240k/README.md), [`docs/sop/update-engine.md`](docs/sop/update-engine.md)).
- `bench/coding_suite.py`: the fixed six-task coding suite runner (streaming tool calls, worktrees, scoring, `--smoke`, `--verify-fixtures`, `--rescore`, `--compare`) with its frozen task data ([`bench/README.md`](bench/README.md)).
- Designed the fixed six-task coding suite (pinned repos, injected bugs, pass rules, 128K long-context task, regression rule); tool-eval-bench reviewed and not reused ([`docs/ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md#coding-suite-design-b1a-2026-10-18)).
- README front page lists every model and engine (Qwen3.8-27B default, Flash-Next Coder via Strata, Qwen4 planned, Nemotron 3.5 Bolt candidate); the upstream-contributions section is removed ([`README.md`](README.md#models)).
- Reviewed the tinygrad-qwen38 fork (~100 tok/s claim), llama.cpp's verify-batch FA dispatch and TurboQuant KV; planned T29, a native quantized-KV multi-query verify kernel ([`docs/ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md#new-t29-native-quantized-kv-multi-query-verify-kernel-2026-10-18-not-started), [`docs/SOURCES.md`](docs/SOURCES.md#tinygrad-qwen38-fork-verify-kernel-references-and-turboquant-kv-2026-10-18)).
- Current execution plan with dependencies and gates (measure b11718, coding suite, Qwen4, Strata, Nemotron, T29); replaces the 2026-10-03 queue ([`docs/ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md#current-plan-2026-10-18)).
- `hip-kvmix` engine moves to llama.cpp b11718 (own build, no PR #29509 patch: upstream #30514 replaces it); not measured on this machine, rollback b11454 + PR #29509 ([`docs/ENGINES.md`](docs/ENGINES.md)).
- Strata Coder setup moves to 262K, KV int8 and `--vram-reserve-mib 3072` (~1.4 GiB VRAM left for the desktop; a Slack launch no longer crashes it; 240K retrieval 20/20); the optional harness provider is renamed `local-flash-262k` (contextWindow 262144) in `check-sync.py` ([`results/20261016-strata-coder-vram-reserve/`](results/20261016-strata-coder-vram-reserve/README.md)).
- No second GPU on this machine (no room in the case); desktop VRAM headroom comes from engine settings ([`docs/measurements/coexistence.md`](docs/measurements/coexistence.md)).
- Strata + Qwen3.8-Flash-Next Coder IQ1_M as an optional second engine on `:8080` (128K, KV int8); `check-sync.py` accepts an optional `local-flash-128k` provider ([`docs/sop/strata.md`](docs/sop/strata.md), [`results/20261015-strata-coder-first-run/`](results/20261015-strata-coder-first-run/README.md)).
- Reviewed Nemotron 3.5 Bolt 74B-A9B 24GB GGUF: b11454 cannot load it (per-layer expert counts, NVFP4 scale tensors); KV at 262K is only ~1.06 GiB q8_0, so text-only likely fits once a newer build loads it ([`docs/SOURCES.md`](docs/SOURCES.md#ideas-for-future-moe-models-not-pursued-2026-09-29)).
- Reviewed the awesome-local-ai catalog: nothing changes the profile; tool-eval-bench noted as a tool-calling quality lead ([`docs/SOURCES.md`](docs/SOURCES.md#awesome-local-ai-catalog-2026-10-10)).
- Reviewed glm53-flash-offload (GLM-5.3-Flash with a VRAM/RAM/NVMe expert cache): CUDA only and sized for 55+ GiB RAM; not applicable ([`docs/SOURCES.md`](docs/SOURCES.md#ideas-for-future-moe-models-not-pursued-2026-09-29)).
- Strata v0.1.41 / Flash-Next RAM budget re-check: the resident copy is sized from `MemAvailable`, so on 31.25 GiB only the Coder IQ1_M fits at long context; llama.cpp b11501 check keeps the b11454 pin ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#review-2026-10-08-releases-amd-notes-and-ram-budget)).
- `scripts/cache_misses.py` classifies prompt-cache reuse per request from a server log: full, partial, compaction, miss, LRU, unknown ([`docs/measurements/agent-traffic.md`](docs/measurements/agent-traffic.md#first-session-after-the-compaction-change-2026-10-03-evening-single-session)).
- Classified the first session after the compaction change (2026-10-03): bootstrap-extension misses and one inferred local compaction-summary fallback ([`docs/measurements/agent-traffic.md`](docs/measurements/agent-traffic.md#first-session-after-the-compaction-change-2026-10-03-evening-single-session)).
- Measured a `-DGGML_LTO=ON` build of b11454: all deltas within ±0.6%, `libggml-hip.so` byte-identical; not adopted ([`results/20261006-t12-lto-b11454/`](results/20261006-t12-lto-b11454/README.md)).
- Measured a local port of llama.cpp PR #29827 (512 MiB FlashAttention convert cap) on b11454: -0.39 GiB VRAM, code tg -2.9%, non-deterministic greedy output; not adopted ([`results/20261006-pr29827-port-b11454/`](results/20261006-pr29827-port-b11454/README.md)).
- Measured DFlash2 `--spec-draft-n-max 7` (third-party tip) against MTP at 240K on b11454: essay -36%, copy -53%, code +5.9%; not adopted. `bench/spec_depth_bench.py` gains a `dfl7` variant ([`results/20261006-t28-dflash2-n7-240k/`](results/20261006-t28-dflash2-n7-240k/README.md)).
- Strata v0.1.40 / xyzzing gfx1100 fork review: the ">100 tok/s" decode claim is not in any primary source, and nothing transfers directly to llama.cpp ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#review-2026-10-06-v0140-and-the-xyzzing-gfx1100-fork)).
- `scripts/launch.py` starts a passive GPU thermal/VRAM logger (`scripts/gpu_watch.py`) and writes `<log>.gpu.csv` next to the server log on Linux ([`docs/sop/launch-model.md`](docs/sop/launch-model.md)).
- llama.cpp PR #29509 on b11371: bit-identical checkpoint restores and constant 149.6 MiB checkpoints; in local trial use ([`results/20261004-pr29509-checkpoint-restore/`](results/20261004-pr29509-checkpoint-restore/README.md)).
- Recall on real agent history at 80K and 176K with production sampling: no position-dependent loss ([`results/20261004-real-history-recall-80k-176k/`](results/20261004-real-history-recall-80k-176k/README.md)).
- Remaining cache-miss classes after the compaction change, from one session ([`docs/measurements/agent-traffic.md`](docs/measurements/agent-traffic.md#remaining-miss-classes-after-the-compaction-change-2026-10-04-single-session)).
- Moved the KVMem trial write-up out of the experiments queue; added a KVMem row to TRIED ([`docs/measurements/kvmem.md`](docs/measurements/kvmem.md)).
- SOP to keep the repo description, README, release and upstream links in sync after a push ([`sop/publish-sync.md`](docs/sop/publish-sync.md)).
- README links the upstream contributions: local-ai-registry recipe (merged) and qwen38-mtp #88 (open) ([`README.md`](README.md); section removed 2026-10-18).
- Published the b11371 `hip-kvmix` engine as a GitHub release; quick start points to it ([`ENGINES.md`](docs/ENGINES.md)).
- Power at depth: decode at 240K is power-limited at the 272 W minimum; overdrive procedure for an undervolt/clock cap ([`sop/power-cap.md`](docs/sop/power-cap.md)).
- Measured llama.cpp b11371 (neutral vs. b11160) and `--spec-draft-sampling probabilistic` (not adopted, pending) ([`results/20261003-b11371-mtp-draft-sampling/`](results/20261003-b11371-mtp-draft-sampling/README.md)).
- Measured n-gram drafting stacked on MTP n=3: large gains on copy-heavy tasks at empty context and 240K ([`docs/measurements/speculative.md`](docs/measurements/speculative.md)).
- Full retrieval sample on the adopted flags: 40/40 exact at 190K and 240K ([`docs/measurements/depth.md`](docs/measurements/depth.md)).
- Root cause of the 2026-10-01 full cache misses (harness speculative compaction on the local slot) and the harness compaction change ([`docs/measurements/agent-traffic.md`](docs/measurements/agent-traffic.md#root-cause-speculative-compaction-on-the-local-slot-2026-10-03)).
- Host prompt cache: the default 8 GiB cannot keep a ~180K state across a side request; 12 GiB can ([`results/20261003-cache-ram-side-request/`](results/20261003-cache-ram-side-request/README.md)).
- KVarN speed screen on BeeLlama at 128K: -37% decode, rejected ([`results/20261003-kvarn-beellama-screen/`](results/20261003-kvarn-beellama-screen/README.md)).
- FlashAttention attribution for this model's shape: ~55% of a 240K MTP step ([`results/20261003-fa-attribution-qwen38-shape/`](results/20261003-fa-attribution-qwen38-shape/README.md)).
- Reviewed Paiton, vllm-radiance, ROCmFPX, BeeLlama preview-v0.4.8 and KVarN sizes: not applicable or pending ([`docs/SOURCES.md`](docs/SOURCES.md#vllm-rocm-forks-and-low-bit-llamacpp-forks-2026-10-03)).
- Reconciled the optimization queue with actual bench behavior, documented the temperature-zero blocker for deep probabilistic-MTP trials, and added gated tool-output, request-locality and verify-path experiments; no runtime change ([`docs/ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md#executable-optimization-queue-review-2026-10-03-not-run)).
- Reviewed vLLM on ROCm and HyperQwen as llama.cpp replacements at 200K-262K context: not pursued, no run ([SOURCES.md](docs/SOURCES.md#vllm-on-rocm-and-hyperqwen-2026-10-03)).
- Added an end-to-end coding-quality, cache-diagnosis and reliability experiment order with external evidence limits; no profile or runtime settings changed ([`ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md)).
- Reviewed four third-party 7900 XTX tuning repositories: 11 source rows and three engine candidates, none run ([SOURCES.md](docs/SOURCES.md#third-party-tuning-repositories-reviewed-2026-10-02)).
- Audit of a 5.8-hour agent session: six full cache misses at ~172K-194K, VRAM headroom
  ([agent-traffic.md](docs/measurements/agent-traffic.md#full-cache-misses-in-a-long-session-2026-10-01)).
- Published the `hip-kvmix` engine artifact as the
  [`engine-b11160-rocm10-gfx1100-kvmix` GitHub release](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11160-rocm10-gfx1100-kvmix).

### Changed

- README opens with key findings and a copyable quick start; the Strata doc is renamed `docs/models/strata-qwen-flash-next.md` and opens with a current-state block ([`docs/models/strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md)).
- Scope narrowed to Qwen3.8-27B (llama.cpp), Qwen3.8-Flash-Next via Strata and Qwen4 when released; the Nemotron 3.5 Bolt candidate is removed from the README, STATUS, the plan and SOURCES ([`docs/DECISIONS.md`](docs/DECISIONS.md)).
- CI runs Python 3.11 and 3.14 with `actions/checkout@v7` and `actions/setup-python@v7` ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).
- One GPU sysfs lookup, `gpu_device()` (largest VRAM card), shared by the launcher, `gpu_watch.py`, `ladder_bench.py` and `probe_ab.py`; `gpu_watch.py` CSV gains trailing `sclk_mhz`, `mclk_mhz`, `vddgfx_mv` columns ([`scripts/manifest.py`](scripts/manifest.py)).
- Bench fixes: `--sampling` accepts scientific notation and rejects NaN/inf; `depth_bench.py`/`coding_suite.py` no longer crash when two runs start in the same second; `ladder_bench.py --help` and `probe_ab.py` work without amdgpu; guard rules in the README match the code ([`bench/README.md`](bench/README.md)).
- Docs audit: STATUS/ENGINES state b11718 as measured at 240K only; README drops the Strata row (parked) and updates tested-setup versions; README, STATUS and TRIED back under their word budgets ([`docs/STATUS.md`](docs/STATUS.md)).
- `ENGINES-EXPERIMENTS.md` keeps only the live plan and open trials (finished write-ups in [`docs/archive/engines-experiments-2026.md`](docs/archive/engines-experiments-2026.md)); `SOURCES.md` becomes an index over `SOURCES-upstream`/`-community`/`-alternatives`; all old anchors kept as pointers ([`docs/SOURCES.md`](docs/SOURCES.md)).
- update-engine SOP watchlist reduced to live upstream items (#28391, #30573, #30792, #28867); the hipBLASLt negative result is marked invalid (package not installed, IQ3_S uses MMQ) ([`docs/sop/update-engine.md`](docs/sop/update-engine.md)).
- Headline 240K numbers now come from the adopted profile on b11454 (essay/copy/code 25.9 / 45.9 / 19.3 tok/s, prefill 391, 22,641 MiB); the MTP-only b11160 figures stay as context ([`docs/STATUS.md`](docs/STATUS.md#headline-numbers)).
- `hip-kvmix` engine moves to llama.cpp b11454 (v0.6.0-dev) + PR #29509: +0.7..+3.2% tg at 240K, same VRAM and PPL; published as the `engine-b11454-rocm10-gfx1100-kvmix` release ([`results/20261006-b11454-engine-update/`](results/20261006-b11454-engine-update/README.md)).
- Scoped long-context retrieval claims to the 40/40 run's settings (b11160, temperature 0, thinking off, no n-gram map) ([`docs/measurements/depth.md`](docs/measurements/depth.md)).
- Removed answered items from the measurement docs' Open questions (answers kept in History), dropped the duplicate 0.66 MTP acceptance copies, and trimmed the README to its 1,000-word budget ([`docs/measurements/agent-traffic.md`](docs/measurements/agent-traffic.md)).
- Profile adopts `--spec-type draft-mtp,ngram-map-k4v` and `--cache-ram 12288`; `hip-kvmix` engine moves to b11371 ([`docs/STATUS.md`](docs/STATUS.md)).
- Rejected `GGML_CUDA_GRAPH_OPT=1` and dropped the rdna-boosts GQA-6 FA band without building it ([`docs/TRIED.md`](docs/TRIED.md)).
- Hypothesis review with no runs: reframed the speed levers by measured session time share, ranked the
  cache-miss hypotheses, added `preserve_thinking` and harness history mutation as hypotheses, and
  pruned duplicate open questions and stale pointers; no profile change
  ([`ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md#hypothesis-review-2026-10-03-no-runs)).
- KVMem rerun helpers fail safely instead of leaving a half-written result (`results/`).
- Bench scripts return nonzero on incomplete measurements and close telemetry on exit (`bench/`).
- Corrected the documentation's evidence qualifiers: 68/68 retrieval matches are pooled across
  configurations, only 8/8 used the exact adopted flags, 190 MiB is system-wide free VRAM (not a
  process delta), the 70% compaction threshold is current, and the original HF revision is unknown
  ([`docs/measurements/depth.md`](docs/measurements/depth.md)).
- `scripts/launch.py` writes the server log to `_tmp/logs/` in foreground mode too, echoing it to
  the console ([launch-model.md](docs/sop/launch-model.md)).
- Checked llama.cpp b11320 (no update) and recorded the fork-vs-wait analysis: no fork, patch on demand; rdna-boosts GQA-6 FA band recorded as a gfx1100 engine candidate, not run; demoted to plan item 6 behind the cache-miss diagnosis and coding suite on 2026-10-02 (`docs/ENGINES-EXPERIMENTS.md`).
- Ran KVMem trial round 2 and a final round: `--kvmem-block-tokens 32` fixes the 240K retrieval miss (8/8), budget 49,152 crash reproduced, candidate (budget 28,672, block 32) 2.2x decode at 244K and exact at 190K-240K; still not adopted pending the agent run (`results/20260930-kvmem-trial-round2/README.md`).
- Ran KVMem trial round 1 on ROCm (2.3x decode at 244K, ~15 GiB VRAM; 7/8 retrieval at budget 28,672, 8/8 at 49,152, one 190K crash): promising, not adopted (`results/20260930-kvmem-trial/README.md`).
- Rewrote `AGENTS.md` as a short index (read-when pointers, rules, commands, evidence discipline)
  and added the documentation workflow (single owner per fact, routing table, word budgets) as
  `docs/STYLE.md` §8.
- Corrected host RAM to 32 GiB installed / 31.25 GiB usable; added a speed-levers summary
  ([agent-traffic.md](docs/measurements/agent-traffic.md#speed-levers-at-depth-2026-09-30)).
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
- Re-validated 240K retrieval on the exact adopted flags: 8/8; pooled cumulative result was 68/68
  across configurations, not 68/68 on the adopted flags (`docs/measurements/depth.md`).
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
