# Sources: community claims, forks and repositories

Community posts, third-party tuning repositories, forks, catalogs and the verify-kernel references behind the T29 trial. Status labels and the one-row-per-claim rule are defined in [`SOURCES.md`](SOURCES.md).

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

## Context length and compaction claims reviewed 2026-09-30

A third-party recommendation (an LLM chat answer) to compact at ~190K, run `shake` before `handoff`, keep
`preserve_thinking` and try KVMem was checked claim by claim. The Qwen card and the KVMem README were read
raw; the other rows came through a summarizing fetch tool.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Qwen evaluates Qwen3.8-27B's agentic coding benchmarks (SWE-bench Pro, DeepSWE 1.1, QwenSWEBench) with the Claude Code harness, temperature 1.0 and a 256K context window | [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) (raw README footnotes) | 2026-09-30 | Source-checked. QwenSWEBench says "an 8-hour timeout, max_tokens=32,768", not "sessions of up to 8 hours". | No local reproduction; window size is not fill level, so this does not establish near-full quality — [`docs/measurements/agent-traffic.md`](measurements/agent-traffic.md#compaction-cost-on-this-hybrid-model-2026-09-30) |
| `preserve_thinking` is on by default; retaining historical thinking "is especially beneficial for agent scenarios where decision consistency and reduced redundant reasoning are critical. It also improves KV cache utilization" | [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) (raw README) | 2026-09-30 | Verified | Left at the default; not measured |
| Input length alone degrades performance by 13.9%-85% even with perfect retrieval, on math, QA and coding, within the models' claimed windows (5 models) | [Du et al., arXiv:2510.05381](https://arxiv.org/abs/2510.05381) | 2025-10 | Verified (abstract, via fetch tool) | Motivates the compaction-threshold A/B; no 60%/75% threshold follows from it |
| Compaction is lossy (keeps high-level facts, loses specifics) | [Claude Cookbook, context engineering](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools); [Claude blog, session management and 1M context](https://claude.com/blog/using-claude-code-session-management-and-1m-context) | 2026 | Verified (fetch tool quotes). "Don't compact if the session fits comfortably" was **not found** on an Anthropic page | Each compaction here also costs a full re-process — [`docs/measurements/agent-traffic.md`](measurements/agent-traffic.md#compaction-cost-on-this-hybrid-model-2026-09-30) |
| Qwen3.8-27B in llama.cpp has a performance cliff around 80-130K context | [llama.cpp issue #27623](https://github.com/ggml-org/llama.cpp/issues/27623) (open): decode collapses ~25x beyond ~80K | 2026-08-23 | Partially true: one report, from ~80K, CUDA (RTX 4080 SUPER) only; nothing for 130K, ROCm or Vulkan | Not seen here: decode falls gradually (synthetic 23.3 tok/s at 240K fill), but real-traffic wall tok/s still drops from ~34 at 64-96K to ~19 at 128-160K — [`docs/measurements/agent-traffic.md`](measurements/agent-traffic.md) |
| omp `shake` compacts locally without an LLM call, replacing eligible tool results and large blocks with recoverable `artifact://` references, with a protected recent window; v18.4.4 documents asynchronous snapshots and discarding stale snapshots | [oh-my-pi v18.4.4 `docs/compaction.md`](https://github.com/can1357/oh-my-pi/blob/v18.4.4/docs/compaction.md) | 2026-10-02 | Source-checked at the release tag. Historical `omp config list` on v18.4.4 showed `supersedeReads`, `dropUseless`, `asyncEnabled` and `midTurnEnabled` as true; current effective settings were not inspected | A prefix rewrite can force reprocessing; inventory current settings and request/cache timelines before testing background compaction or shake — [`ENGINES-EXPERIMENTS.md`](archive/engines-experiments-2026.md#end-to-end-quality-and-reliability-before-tuning-2026-10-02-proposed-not-run) |
| KVMem keeps a 256K+ agent workspace and serves a bounded GPU-resident active context: Qwen3.8-27B DeepSWE 43.8% (compaction only) vs. 48.4%; a 32K active context is "essentially lossless" vs. full 256K (LongMemEval-S 85.6% vs. 86.6%, AgentLongBench 60.9% vs. 59.5%) | [arXiv:2609.04852](https://arxiv.org/abs/2609.04852), [kvmem/kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp) (raw README) | 2026-09 | Verified, but 32K is not identical to 256K (-1.0 / +1.4 points). The README's recipe uses the same GSQ-RCO IQ3_S-mtp file as this repo and supports `--spec-type draft-mtp`. Caveats: ROCm builds are older "rc3-rocm-beta2" packages, not the current v0.17.0 source; mixed KV pairs other than `q8_0/q4_0` (so `q8_0/q5_1` too) have argument-parsing checks only; "ROCm/Vulkan combinations have not been validated" | Tested round 1 (2026-09-30, ROCm build from v0.17.0 source): tg 40-49 tok/s at 244K vs. 20.8 baseline, VRAM ~15 GiB; retrieval 7/8 at budget 28,672, 8/8 at 49,152 (one crash at 190K) — [`results/20260930-kvmem-trial/`](../results/20260930-kvmem-trial/), [`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md#kvmem-trial-round-1-run-2026-09-30-not-adopted). The 32K-vs-256K figures are the paper's, not reproduced |
| Mid-band retrieval collapse beyond ~210K context, open; reporter config block 32, budget 36,864, RTX 4070 Ti Super | [kvmem/kvmem-llama.cpp#4](https://github.com/kvmem/kvmem-llama.cpp/issues/4) | 2026-09 | Verified (issue text exists and says this) | Related, not reproduced: one mid-band needle missed at budget 28,672, block 128, 240K (fixed at 49,152 and by block 32 at 28,672) — [`results/20260930-kvmem-trial/`](../results/20260930-kvmem-trial/), [`round 2`](../results/20260930-kvmem-trial-round2/) |
| The upstream ROCm validation doc says budget 36,864 slowed ROCm 10 on a 16 GiB RX 9060 XT | `docs/rocm10-beta2-validation.md` in [kvmem/kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp) | 2026-09 | Verified (text). Hypothesis: that card spilled to shared memory, which does not apply to 24 GiB | Budget 49,152 ran at 40.2 vs. 48.6 tok/s for 28,672 at 244K, VRAM 16.0 GiB of 24 — [`results/20260930-kvmem-trial/`](../results/20260930-kvmem-trial/) |
| Maintainers recommend `--kvmem-block-tokens 32` for recall | Reported by a research subagent, not checked against the issue text | 2026-09 | Hypothesis (unverified): not checked against the issue text | Own test, round 2: block 32 at budget 28,672 fixed a block-128 miss at 240K (8/8), budget 36,864 at block 128 did not — [`results/20260930-kvmem-trial-round2/`](../results/20260930-kvmem-trial-round2/) |

## Third-party tuning repositories reviewed 2026-10-02

Four public repositories were read in full clones; cited files and lines were re-checked at the pinned
commits. Verdict labels as in the 2026-09-26 section. Candidates that follow from these rows live in
[`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md#candidates-from-third-party-repositories-2026-10-02-not-run).

| Claim | Source | Status | Note |
|---|---|---|---|
| `--reasoning-budget 512` at 120K: 8/8 retrieval and 8/8 counting correct, all 16 `finish_reason: stop`, counting median completion 2,532 → 515 tokens, retrieval unchanged (178.5); reasoning is cut mid-sentence and the next turn reuses the prefix (cached 119,959) | [szafranski/rx7900xtx-qwen3.8-27b-tuning](https://github.com/szafranski/rx7900xtx-qwen3.8-27b-tuning) @ `4335323`, `docs/context-and-quality.md:536-560`, `data/kv-budget-512-120k.json` | Verified (raw data read); n=16, Q4_K_XL on a Vulkan fork | Not run on this profile. Touches the `--reasoning-budget` rule in `AGENTS.md`, so adoption needs a [`DECISIONS.md`](DECISIONS.md) row and a rule edit |
| `--reasoning-effort low` at 120K: 64/64 correct, 2.9x fewer tokens, bimodal (6/32 above 1,000 tokens); changes the system block, so the prompt cache is lost | same repo, `docs/context-and-quality.md` (effort arms) | Verified (read); other model/backend | Consistent with the 2026-09-30 rejection of `low` in [`DECISIONS.md`](DECISIONS.md) |
| `--spec-type draft-mtp,ngram-map-k` cuts a replayed ten-turn session from 253.5 s to 209.5 s (README says "-21% wall time"; the raw `session_s` values give -17.4%, +21% throughput); neutral on a single request | same repo, `docs/speculative-decoding.md:70-85`, `data/multiturn-session.jsonl` (`p1-mtp` vs. `p1-ngmapk`, 2 reps each; `ngmod` 218.7 s, `ngsimple` 211.0 s) | Hypothesis: raw numbers read, not reproduced; fork-only `ngram-map-k` build, Vulkan, 128K, one transcript | Own 2026-09-24 sample was single-shot at empty context, so it could not see this effect — [`speculative.md`](measurements/speculative.md#n-gram-stacked-on-mtp-how-llamacpp-combines-them-source-reading-2026-09-29) |
| Undervolt offsets beyond -100 mV are clamped under a clock cap: at 2,200 MHz, -75 mV gave 715.6 mV average VDDGFX and -200 mV gave 704.8 mV | same repo, `docs/power-and-undervolt.md:79-86`, `data/undervolt-clamp-vddgfx.tsv` | Verified (data read); not measured here | GPU care is deferred — [`STATUS.md`](STATUS.md#next-steps) |
| 2,200 MHz SCLK cap at 272 W: -5.2% throughput, -13.9% J/token; 272 W vs. 303 W: -2.2% throughput | same repo, `docs/power-and-undervolt.md:15-35` | Hypothesis (read); other quant and backend | Own 272 W figures differ (tg128 ~-3.4%, prefill -6%) — [`thermals-power.md`](measurements/thermals-power.md) |
| `turbo4` V cache: -1.5% decode and -1,194 MiB at 128K, next-token spread ~8x q8_0 (0.0144 vs. 0.0017) | same repo, `README.md:98` (fork-only note) | Hypothesis; not applicable | Exists only in the TheTom turboquant fork on Vulkan; not in b11160 and not KLD-comparable to [`kv-quality.md`](measurements/kv-quality.md) |
| `GGML_CUDA_GRAPH_OPT=1` gives +1.4% tg and +1.0% pp (r=3, empty context, no MTP, dense IQ4_XS, f16 KV) | [salvatoretrimarchi/llama.cpp_build_7900XTX](https://github.com/salvatoretrimarchi/llama.cpp_build_7900XTX) @ `b4ea8e9`, `scripts/start-server.sh:43` | Verified (the variable exists in b11160, `ggml/src/ggml-cuda/ggml-cuda.cu:4611`, off by default); gain is Hypothesis | Not in any doc here before. Untested with MTP at depth |
| `-DGGML_LTO=ON` gives "+5-15%" | same repo, `.gitea/workflows/build.yml:141` | Refuted locally on b11454 (2026-10-06): pp/tg within ±0.6%, `libggml-hip.so` byte-identical | [`results/20261006-t12-lto-b11454/`](../results/20261006-t12-lto-b11454/README.md) |
| "Apply RDNA3 optimization patches" step; "WMMA FA on"; `-DGGML_HIP_NO_VMM=ON` | same repo, `.gitea/workflows/build.yml:99-110, 140` | Refuted / not applicable: the patch step applies nothing (no `patches/` directory); `GGML_HIP_ROCWMMA_FATTN` is never set and no longer exists ([`ENGINES.md`](ENGINES.md)); `GGML_HIP_NO_VMM` already defaults to ON (`ggml/CMakeLists.txt:218`) | The recipe builds unpinned upstream HEAD as one HIP+Vulkan binary, which [llama.cpp #23199](https://github.com/ggml-org/llama.cpp/issues/23199) breaks for MTP |
| `GGML_CUDA_DISABLE_GRAPHS=1` as a workaround for a HIP-graph exec-update wedge under VRAM pressure (cites rocm-systems#10021); `--cache-type-v turbo2` at 200K; ~70 tok/s with MTP, 16.7 GB at 200K | [Chromadera/local-llm-stack-config](https://github.com/Chromadera/local-llm-stack-config) @ `39a366b`, `turboquant_full_config_handoff.md:353-378`, `README.md:28-40` | Hypothesis (prose only, no logs; the cited issue was not read); turbo2 not applicable | Diagnostic only, if a hang appears. Fork-only V cache, not KLD-checked here |
| rdna-boosts gives +7.16% tg at empty context (IQ4_XS, no KV quant); `draft-mtp-adaptive` recipe; ROCm 7.2.4/7.14/10.0 within ~1-3% | [BittyBunnyBytes/RX-7900-XTX-AI-Optimization-Guide](https://github.com/BittyBunnyBytes/RX-7900-XTX-AI-Optimization-Guide) @ `fe4b2a5`, `docs/Optimizations/Recommended/llama-cpp tuning.md:22-31`, `docs/Recipes/Qwen3.8 27B.md:21` | Not applicable: empty context, no KV quant | Nothing new: rdna-boosts is already covered above, `draft-mtp-adaptive` is already in [`TRIED.md`](TRIED.md) |

## cafe-llama.cpp fork and the @quimedesu X thread (2026-10-02)

Fork read in a full clone: [quimmedes/cafe-llama.cpp](https://github.com/quimmedes/cafe-llama.cpp)
@ `a0d43f3`, merge base upstream `f1cee99` (#29816, 2026-10-01), 275 files changed. The tree also carries
PrismML (`bri-prism`) work: DFlash/DSpark, hybrid-graph fusions and the draft-context `n_rs_seq` fix.
Candidate: [`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md#candidates-from-third-party-repositories-2026-10-02-not-run).

| Claim | Source | Status | Note |
|---|---|---|---|
| "I made mtp as light as dflash" | X thread by @quimedesu, 2026-10-01; fork @ `a0d43f3` | Hypothesis: no draft-cost reduction for Qwen3.5/3.8 found in the code. The `draft-mtp` driver diff (`common/speculative.cpp:2131-2178, 2330-2560`) is DeepSeek-sparse-attention index sharing, a gemma4-assistant shared-KV test and an optional `--spec-adaptive` window trim (`:3020`, off by default). Qwen3.5/3.8 gains would come from target-side GDN fusions (raw gates, `ggml_swiglu_split`, joint `l2_norm`: `src/models/qwen35.cpp:323, 447, 486, 543`), PrismML work reported at +2.5% decode on CUDA 9B | Verification is untouched: `common/sampling.*` and the server accept path are unchanged, so output stays lossless. The 27B MTP head is an attention layer, so GDN fusions do not touch the draft. Our own cost model: a step is dominated by the target pass at depth ([`speculative.md`](measurements/speculative.md)) |
| `--spec-draft-n-max 4` for "any" model, 6 also works; the README says 4 is the sweet spot, 5 equal, 3 and 6 slightly slower, 7+ halves decode | same thread; fork `README.md:88-97` | Hypothesis; measured on RTX 3090 CUDA with an own 27B quant. The 8-token verify cliff is real but not new: `MMVQ_MAX_BATCH_SIZE 8` is also in b11160 (`ggml/src/ggml-cuda/mmvq.cuh:3`) | Not contradicted by [`TRIED.md`](TRIED.md): n=4 was measured with upstream b11160 draft cost (240K: 21.4 vs. 23.3 tok/s for n=3). The fork README and the thread disagree on n=6 |
| "Doubling decode speed from one update", ~65 tok/s dense 27B, ~60-80 tok/s Flash-Next | same thread; fork `README.md:72, 88` | Hypothesis (author numbers, no raw data in the repo); RTX 3090, CUDA, 64K context, `-ctkd q4_0`; the Flash-Next figure uses `-hmoe` host-expert offload, which the dense 27B does not use | Not comparable to 240K+ depth on gfx1100; the baseline of "doubling" is not stated |
| "CUDA path is supposed to compile for ROCm, but I don't have AMD" | same thread | Verified as an untested statement: the changed CUDA files are shared with HIP via `ggml/src/ggml-cuda/vendors/hip.h`, and the fork adds ROCm release CI (`44238f0`), but no AMD result exists | Build success is not evidence of speed or correctness on gfx1100 |
| Quality "tanked when draft tokens drifted on tool-heavy turns"; lower `n-max` when big JSON tool results enter context (@sunsetsyntax) | same thread, second-hand | Hypothesis; implausible as a pure draft-length effect: the fork leaves acceptance and verification as upstream, so output is distribution-preserving at any `n-max` | A real quality drop would indicate a bug (e.g. the stale draft-context positions the `n_rs_seq` fix targets) or sampler differences, not draft depth. Lower acceptance on JSON would cost speed, not quality |

## llama.cpp fork survey (2026-10-02)

GitHub survey for forks or GGUF engines not yet covered above, checked against this setup (gfx1100
HIP, `qwen35` hybrid + MTP, `q8_0`/`q5_1` FA at 262K, IQ3_S). Already-evaluated engines keep their
verdicts in [`TRIED.md`](TRIED.md) and [`ENGINES.md`](ENGINES.md). No new fork is expected to beat
b11160 `hip-kvmix`; likely gains arrive through upstream (GDN fusions, the rdna-boosts GQA-6 band).

| Claim | Source | Status | Note |
|---|---|---|---|
| A HIP flash-attention kernel A/B override | [TheTom commit `cc1a791`](https://github.com/TheTom/llama-cpp-turboquant/commit/cc1a791) (2026-09-06), rechecked 2026-10-03 | source-checked: 16 added lines force TILE or shape-gated MMA with `GGML_HIP_FA_KERNEL`; no new kernel | Diagnostic capability, not evidence of a gfx1100 mixed-KV speedup. T19 source-read complete; any selector A/B belongs to T27 on the pinned baseline, not an entire fork build. |
| 41 tok/s baseline, 68 tok/s on reasoning, 98 tok/s on repetitive content on an RX 7900 XTX | [theGiallo/llama-7900xtx-qwen3.8-27b](https://github.com/theGiallo/llama-7900xtx-qwen3.8-27b) @ `8739978` (README) | Hypothesis (README only) | Upstream + DFlash2 + a ROCmFP4 weight quant with RDNA3 WMMA MMQ/MMVQ kernels; `q4_0` KV at 256K conflicts with the KV-quality policy, DFlash2 already lost here, fp4 needs another model file |
| ROCm, Vulkan and Metal issues will not be resolved by the maintainers | [ikawrakow/ik_llama.cpp](https://github.com/ikawrakow/ik_llama.cpp) @ `5f89bfc`, `README.md:14` | Verified | Active, with `qwen35` and MTP fixes, but no HIP support path; not applicable |
| AMD's own fork is a maintained ROCm line | [AMD-Ecosystem/llama.cpp](https://github.com/AMD-Ecosystem/llama.cpp) (ROCm/llama.cpp redirects here) | Refuted as a performance lead: 10 commits ahead, 341 behind `ggml-org/master` on 2026-10-02 | Upstream mirror |
| Other candidates | BeeLlama preview-v0.4.8 (upstream sync only), lemonade-sdk/llamacpp-rocm b1336 (master rebuild), PrismML-Eng/llama.cpp `prism` (no HIP evidence), koboldcpp-rocm (last push 2026-07-29), mozilla-ai/llamafile (packaging), rocktboy1982/llama-cpp-7900xt-optimization (turbo4 V, short context) | Checked 2026-10-02 | Not applicable. No KIVI/QJL/PolarQuant or EAGLE/tree-speculation fork for gfx1100 + `qwen35` was found |

## awesome-local-ai catalog (2026-10-10)

[SeraphimSerapis/awesome-local-ai](https://github.com/SeraphimSerapis/awesome-local-ai) @ `35affc47b0`
lists about 30 projects, mostly for Apple Silicon/MLX, DGX Spark/GB10 or CUDA. Read the README only;
no project was cloned or run.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Evaluates tool-calling quality against a self-hosted OpenAI-compatible endpoint with deterministic mock-tool scenarios and conversation traces; difficulty tiers are author estimates, localization is German-focused | [SeraphimSerapis/tool-eval-bench](https://github.com/SeraphimSerapis/tool-eval-bench) | 2026-10-10 | source-checked (README, `pyproject.toml` and scenario code at `42a100b18ff7`, 2026-10-18) | Not reused for the coding suite: all 97 scenarios use mock tools and none edits a repository or runs tests; needs `httpx`, `python-dotenv`, `pyyaml`, `rich`. Only its call-count error injection was borrowed ([coding suite design](ENGINES-EXPERIMENTS.md#coding-suite-design-b1a-2026-10-18)) |
| Measures prompt processing and token generation at several context depths through the server API | [eugr/llama-benchy](https://github.com/eugr/llama-benchy) | 2026-10-10 | source-checked (catalog entry only) | none; our protocol uses `llama-bench` ([`sop/measure-backend.md`](sop/measure-backend.md)) |
| Serving benchmark with prose, code, structured output, cache tests and concurrent requests | [alexellis/rigmark](https://github.com/alexellis/rigmark) | 2026-10-10 | source-checked (catalog entry only) | none; overlaps llama-benchy |
| DwarfStar / ds4, TensorFold, Splash, mlx-serve, oMLX, boots, Spark/GB10 tools, MCP servers and skills | catalog README | 2026-10-10 | not applicable (ds4 needs its own GGUF files and targets 96+ GB Macs; TensorFold and the MLX servers have no AMD path; boots is host bootstrapping with no license) | none. Strata is tracked in [Ideas for future MoE models](SOURCES-alternatives.md#ideas-for-future-moe-models-not-pursued-2026-09-29) |

## tinygrad-qwen38 fork, verify-kernel references and TurboQuant KV (2026-10-18)

Lead from an X post (@splizard, 2026-10-17: "Qwen 3.8 27B up to 100 tok/s on my 7900XTX"). Fork read
at [Splizard/tinygrad-qwen38](https://github.com/Splizard/tinygrad-qwen38) branch `amd-gemv-qwen38` @
`4c5e380` (2026-08-25, MIT); key lines re-checked at that commit. Upstream dispatch re-checked on
llama.cpp master the same day. No run. The trial that follows from these rows is
[T29](ENGINES-EXPERIMENTS.md#new-t29-native-quantized-kv-multi-query-verify-kernel-2026-10-18-not-started).

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Qwen3.8-27B on an RX 7900 XTX at "~100 tok/s" with MTP; decode 53.5 tok/s without MTP; tensor-core prefill ~860 tok/s | Commits `c21c5dd`, `bfd2bbf`; `--benchmark` in `tinygrad/llm/cli.py` generates from BOS only | 2026-10-18 | hypothesis (commit message; no log, no depth). Runs `UD-Q3_K_XL` with `MTP_K` 3 (`model.py:658`), `--max_context` default 4096, claimed 163,840 max | Not comparable to our 68.9 tok/s empty / 25.9 tok/s at 240K ([STATUS](STATUS.md#headline-numbers)); the engine also misses the 262K provider contract |
| Multi-query flash decoding (`AMD_ATTN_MQ=1`, default): all T x G query rows of one KV head score each 16-position KV tile together, so quantized KV is read once per MTP step; `attn_prep` (q/k/v rotate + quantize, q to int8 per row), `attn_pfd` (chunk partials, 256 positions, `v_wmma_i32_16x16x16_iu8` for QK, `v_wmma_f32_16x16x16_f16` for PV, V dequantized to f16 in LDS), `attn_merge_mq` (online-softmax merge). 63 to 44 ms/step at 32K, 87 to 57 at 65K | `tinygrad/llm/amd_prefill.py:341-366, 397-520 (WMMA :480, :505; mask :490), 616-651`; `amd_gemv.py:1472-1478`; commit `e1eca01` | 2026-10-18 | source-checked (design); timings hypothesis, and relative to the fork's own previous per-token kernel, not to llama.cpp TILE | Design reference for T29. HIP C++ generated from Python f-strings for tinygrad's runtime: about 360 kernel lines to port by hand, not a drop-in. Asserts `D == 256`, `G <= 8`, `T <= 8`: our shape (D 256, GQA 6, verify 4) fits |
| KV "TurboQuant-style" k4+QJL / v4: random-sign + Walsh-Hadamard rotation, one norm per vector, 4-bit Lloyd-Max codebook, 1-bit QJL key residual; 300 B per position per KV head (~6.8x smaller than f32) | `amd_gemv.py:1099-1142, 1188-1237` | 2026-10-18 | source-checked (format); quality unmeasured: the fork has no PPL/KLD/retrieval test, only greedy MTP=0 vs. MTP=1 token equality (`MTP_PLAN.md`) | Our `q8_0` K + `q5_1` V is 464 B per position per KV head; 4-bit V already lost on KLD here ([kv-quality.md](measurements/kv-quality.md)) |
| llama.cpp master, quantized K/V at D 256: `Q->ne[1] <= 2` selects VEC (native quantized reads); 3-8 query tokens (our MTP n=3 verify is 4) select TILE, which converts the whole K/V view to f16 every call | [`fattn.cu`](https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-cuda/fattn.cu) lines 713-718 (gate), 733-745 (`need_f16_K/V`) | 2026-10-18 | source-checked; unchanged since the b11160 row in [Optimization queue source checks](SOURCES-upstream.md#optimization-queue-source-checks-2026-10-03) | At 240K and 4 tokens, f16 KV costs 2,559 µs vs. 4,574 µs for `q8_0`/`q5_1` per FA op ([attribution](../results/20261003-fa-attribution-qwen38-shape/README.md)): ~2.0 ms per layer is the quantized path's overhead |
| Quantized KV with batch > 1 always pays the f16 conversion; letting VEC take batch 4 was 19-22% slower; asks for native quantized tiles | [issue #29935](https://github.com/ggml-org/llama.cpp/issues/29935) (open, CUDA sm86) | 2026-10-18 | source-checked (issue text); NVIDIA numbers | Rules out "just widen the VEC gate" as the T29 shortcut. Capping the convert buffer instead (PR #29827 port) already lost here: -0.39 GiB VRAM, code -2.9% ([TRIED.md](TRIED.md)) |
| Native `q8_0` K/V (also f16 K with `q8_0` V) in the TILE flash-attention kernel, dequantized to `half2` in registers, no f16 scratch: tg +19.0% (16K) to +61.9% (63K) on gfx1151 with a 35B-A3B MoE and `q8_0`/`q8_0`; a commenter saw -77.5% prefill on gemma-4 26B-A4B when native V also ran in prefill (`ne[1] > 2`) | [PR #30792](https://github.com/ggml-org/llama.cpp/pull/30792) (open, not merged; closes #30790); diff `fattn-tile.cuh`, `fattn.cu` | 2026-10-22 | source-checked (PR text, diff, comments); author numbers on RDNA3.5 (gfx1151), not gfx1100; the commenter's numbers are agent-measured by their own note | Not run. The adopted K `q8_0` / V `q5_1` pair is not a native type there, so the PR alone changes nothing for this profile; [T29 cheaper route](ENGINES-EXPERIMENTS.md#cheaper-route-via-llamacpp-pr-30792-2026-10-22) adds a `q5_1` V loader and an `ne[1] <= 8` guard |
| Vulkan: folding 2 verify tokens x GQA heads into one FA row, FA 1,072 to 563 µs at 4 tokens / 52,480 KV; server +14.6% (39.66 to 45.44 tok/s) on gfx1100 | [PR #30190](https://github.com/ggml-org/llama.cpp/pull/30190) (open) | 2026-10-18 | hypothesis (author numbers); Vulkan, not our backend | Second design reference for T29 (same folding idea in another backend) |
| Metal: tensor-API FA for 1-4 tokens with GQA packing, 4-token FA 737.9 to 404.5 µs at 32K | [PR #30645](https://github.com/ggml-org/llama.cpp/pull/30645) (open) | 2026-10-18 | hypothesis (author numbers); not applicable to HIP | Same pattern; confirms the verify shape is underserved upstream |
| vLLM Triton unified attention packs the query heads of one KV group into one tile and has a split-K path for query lengths up to 8 ("1 + num_speculative_tokens") | `vllm/v1/attention/ops/triton_unified_attention.py` (`MAX_3D_QUERY_LEN`) | 2026-10-18 | hypothesis (scout read; not re-checked here) | Third design reference for the split-K merge |
| No TurboQuant/QJL KV type in llama.cpp: about 20 TurboQuant PRs closed unmerged (e.g. #21089, #23617); the merged piece is Hadamard rotation of quantized K/V | [PR #21038](https://github.com/ggml-org/llama.cpp/pull/21038) (merged 2026-04-01) | 2026-10-18 | source-checked (#21038 state); PR survey by scout | Rotation is already on in every KV measurement here ([engines.md](measurements/engines.md#llama_attn_rot_disable-not-needed-here)); its 4-bit result is the `q4_0` row that lost |
| `turbo2`/`turbo3`/`turbo4` KV types (WHT + PolarQuant, no QJL) build for HIP; turbo4 PPL +0.23% vs. `q8_0`; KLD (Qwen3.5-35B, 512 ctx) `q8_0` 0.001549, `q4_0` 0.008091, turbo4 0.009633; `q8_0` K + turbo3 V gave NaN on HIP | [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) `docs/KV-cache-quantization.md` (pushed 2026-10-14); gfx1100-only port [domvox/llama.cpp-turboquant-hip](https://github.com/domvox/llama.cpp-turboquant-hip) (base b8680, stale since 2026-04-26) | 2026-10-18 | hypothesis (vendor numbers, short context) | Not queued: turbo4's own KLD is worse than plain `q4_0`, which already lost here; the forks' FA paths would replace our `hip-kvmix` kernels; no KLD at ≥100K exists. Revisit only if T29 lands and VRAM, not quality, becomes the limit |
| QJL residual is dropped in production TurboQuant forks: it lowers MSE but adds variance that softmax turns into attention noise | turboquant_plus README (via scout) | 2026-10-18 | hypothesis | Argues against copying the fork's QJL key format |
| RX 7900 XTX + 30 GB DDR5, CachyOS, ROCm 7.2.4, ISTA IQ2_XS on Strata 0.1.45: tuned config 87.3 tok/s chat, 99.7 agent (59.8 / 75.5 with the same machine's earlier config); gfx12 switch sets and route tail skip on gfx1100 | [Niko1221/Strata PR #3665](https://github.com/Niko1221/Strata/pull/3665) (closed 2026-10-29, kept for a community page) | 2026-11-05 | source-checked | Read in the PR README; not reproduced here. Tail skip changes answers (KL 0.036). Recipe and per-switch table: [`models/strata-tuning-gfx1100.md`](models/strata-tuning-gfx1100.md#the-pr-3665-recipe-community-measured-on-a-7900-xtx-30-gb) |

## RDNA-FAST fork (2026-11-06)

[serrynaimo/RDNA-FAST](https://github.com/serrynaimo/RDNA-FAST) at `2ec3411`: a llama.cpp fork on ROCmFPX for
agents on AMD consumer GPUs. Only the README and `docs/` were read; no code was built or run. Its README: RX
7900 XT 20 GB, Ryzen 9 7900, Windows 11, ROCm 10.1, "Nothing here has been measured on an XTX". Candidates and
kill criteria: [ENGINES-EXPERIMENTS.md](ENGINES-EXPERIMENTS.md#candidates-from-the-rdna-fast-fork-2026-11-06-not-run).

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Two-agent scripted session 93 s vs. 130 s, same model, quant and context | README, "Speed" | 2026-11-06 | hypothesis (vs. LM Studio's runtime 2.69.0, not stock llama.cpp) | None |
| SSD prompt cache: back to a 40-53K conversation 77-105 s (stock) to 2.9 s; first request after a restart 30-50 s to 4.2 s | README, "The SSD prompt cache" | 2026-11-06 | hypothesis | None; candidate R3 |
| Checkpoint eviction keeps the one at the first user message and drops the one leaving the smallest gap | README, quick-start flag table | 2026-11-06 | source-checked (README only) | Matches our post-compaction miss; candidate R2 |
| `ROCMFPX_DRAFT_VOCAB=24576`: decode +9% short, +3-5% at 41K; main model verifies against the full vocabulary | README, environment variables | 2026-11-06 | hypothesis | None; candidate R4 |
| Lean MTP reserve 80 vs. 784 MiB; rollback by replay saves 0.8 GB at two slots, decode equal | README, environment variables and "Rollback by replay" | 2026-11-06 | hypothesis | None; candidate R5 |
| `GDN_CONV_SNAP` with `MMVQ_FUSE_VERIFY`: decode +2.3-3.9%, short prompts +9-17% | README, environment variables | 2026-11-06 | hypothesis | None; candidate R6 |
| Without `--reasoning-preserve`, a client that drops past thinking (Hermes) re-prefills a median 5K tokens per exchange | README, quick-start flag table | 2026-11-06 | locally reproduced in kind: dropping `reasoning_content` re-processes the previous answer ([agent-traffic.md](measurements/agent-traffic.md#multi-turn-prefix-reuse-with-reasoning-2026-10-03)) | Hermes unchecked; candidate R1 |
| `GGML_HIP_FA_GQA6`: decode +10-12% at 41K for Qwen3.8-27B | README, environment variables | 2026-11-06 | not applicable (a GQA-6 band needs K and V of one type; ours is `q8_0`/`q5_1`, [TRIED.md](TRIED.md)) | None |
| WMMA GEMM prefill: 17K cold prompt 781 to 864 t/s on IQ4_XS, batches of 512 tokens or more | README, "Prompts through a WMMA GEMM" | 2026-11-06 | not applicable at `-ub 256` | None |

## Flash-Next low-bit quants for agents (2026-11-07)

Whether a 2-bit Qwen3.8-Flash-Next set is good enough for an agent harness. Vendor tables measure single-turn tasks;
agentic evidence is scarce. Strata side: [`strata-tuning-gfx1100.md`](models/strata-tuning-gfx1100.md#next-round-when-a-new-set-or-engine-ships).

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| "while all the GGUFs I tested performed very well on non-agentic tasks, even down to "Q1", agentic tasks are a different story. Even higher-end Q2 variants, like UD-Q2_K_XL, show significant degradation"; recommends GSQ-RCO IQ3_S ("far smaller" than UD-Q4_K_XL, on par with the original model); only four variants evaluated | [Benjamin Marie, kaitchup](https://kaitchup.substack.com/p/agentic-coding-with-qwen38-flash) | ~2026-10-10 | source-checked (quotes fetched 2026-11-07) | Consistent with ours: ISTA IQ2_XS failed the coding suite on invented tool calls ([results](../results/20261030-strata-iq2xs-quality/README.md)) |
| Same author's long-horizon chart, pass@1 recovery vs. BF16: IQ3_S 100%, UD-Q4_K_XL 100%, UD-Q2_K_XL 73.8% (+15% tokens), Coder IQ1_M 64.3% (+71% tokens) | Chart in the article above (read by a research subagent from the SVG) | ~2026-10 | hypothesis (numbers not re-read here) | None |
| ISTA card, single-turn task average (AIME25, GPQA-D, LiveCodeBench v6), BF16 93.12: IQ3_S 93.26, IQ3_XXS 92.57, IQ2_XS 89.16, Q2_0 89.07; no tool-calling evaluation | [ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF) | 2026-11 | hypothesis (read by a research subagent; IQ2_XS 89.16 also on the vramcalculator Strata page) | IQ2_XS: 128K retrieval 8/8, coding suite failed |
| Strata's same-top-token-as-Q8_0 table: IQ3_S 87.69%, IQ3_XXS 84.46%, Q2_0 80.60% (IQ2_XS not measured) | Strata `docs/QUANTS.md:76-82` at `146df3c4` | 2026-11-07 | hypothesis (read by a research subagent) | None |
| HF discussion "Thinking hallucination, looping for IQ2_XS but not q2_0" | ISTA-DASLab Flash-Next GGUF discussions #45 | ~2026-10 | unverified (title only, body not reached) | None |

## DSpine draft model and the Ajay9o9 dspine fork (2026-11-08)

[aj9o9/Qwen3.8-27B-DSpine-b16-GGUF](https://huggingface.co/aj9o9/Qwen3.8-27B-DSpine-b16-GGUF) (GGUFs of
`tencent/Qwen3.8-27B-DSpine-b16`, Q4_K_M 1.26 GB) needs
[Ajay9o9/llama.cpp `dspine`](https://github.com/Ajay9o9/llama.cpp/tree/dspine): one commit, `d493f841b2`
(2026-11-08), +323 lines in conversion, `src/llama-arch.*` and `src/models/dflash.cpp` (generic ggml ops,
no backend kernels). It runs as `--spec-type draft-dflash`, so it replaces `draft-mtp` instead of stacking
on it. Only the card and the commit diff were read; no build, no run, paper not read. Set aside:
[DECISIONS.md](DECISIONS.md) 2026-11-08.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Short context, temperature 0: 90.1 tok/s overall (3.19x), code 128.7, math 122.8, prose 41.6, vs. 28.2 without speculation (RTX 3090, Q4_K_M target, `--spec-draft-n-max 15`) | Card, "Speed by task" | 2026-11-08 | hypothesis (CUDA only, ~6,000 tokens per setup) | None; MTP n=3 here is 1.95x at empty context ([STATUS](STATUS.md)) |
| Max `-c` on 24 GB with q8_0 KV: 65,536 at n=15, 98,304 at n=7, 176,128 without speculation; the target keeps a ~150 MB recurrent-state copy per drafted token | Card, "Maximum context on 24 GB" | 2026-11-08 | source-checked (card only) | None; 262K with n=15 is not expected to fit beside our 22,645 MiB peak |
| Decode at depth (prose): 31.1 tok/s at 32K vs. 23.8 without speculation; drafter attends an 8K sliding window | Card, "Speed at increasing context depth" | 2026-11-08 | hypothesis (one 256-token run per cell) | DFlash2's 2K window lost to MTP at 190K/240K ([speculative.md](measurements/speculative.md#dflash2-and-the-native-q8-kv-fork-at-190k)) |


## inference-optimisation agent skill (2026-11-20)

[sybil-solutions/inference-optimisation-skill](https://github.com/sybil-solutions/inference-optimisation-skill)
@ `fda968e` (2026-11-16) is an agent skill (`SKILL.md`, references, stdlib bench scripts) for hill-climbing
local-server speed: theoretical ceiling first, one change at a time, control/candidate/control runs with
medians, a ledger of every result, and a long-context needle gate. Its own results are EXL3/SGLang/vLLM on
Intel Arc, RTX 3090 and H200; none are llama.cpp on AMD. Not adopted: this repository already applies the
same discipline. One idea not yet here: a computed decode ceiling (bytes per token ÷ bandwidth) for the
current profile, to tell how far ~40 tok/s is from the card's limit. Only `README.md`, `gotchas.md` and
`levers.md` were read; no script was run. Kept as a methodology reference: consult its `references/` (ceilings,
measurement traps, levers, publishing gates) when planning a new measurement campaign, and re-read it for new
AMD or llama.cpp entries at each engine update. Candidates that follow from it:
[`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md#candidates-from-the-inference-optimisation-skill-2026-11-20-not-run).

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| llama.cpp q8_0 KV dropped decode from 45.4 to 27.0 tok/s on a model with KV in only 16 of 64 layers | `references/levers.md:46`, `references/gotchas.md:40` | 2026-11-16 | hypothesis (no backend, model or raw data given) | Open: no same-build decode-speed A/B of `q8_0/q5_1` vs. `f16` was located during this review; f16 rows exist in [`engines.md`](measurements/engines.md) |
| llama.cpp MTP lost to no draft on hard prompts: 36.7 vs. 45.4 tok/s | `references/levers.md:36` | 2026-11-16 | hypothesis (no setup given) | None; see [`speculative.md`](measurements/speculative.md) for MTP here |
| HIP graphs leaked until crash on ROCm; disabling them was stable at 115.6 tok/s | `references/gotchas.md:46` | 2026-11-16 | not applicable (ExLlama/TabbyAPI, not llama.cpp) | `GGML_HIP_GRAPHS` is on by default here and not a lever — [`depth.md`](measurements/depth.md) |
| A busy host CPU costs GPU decode on laptops: 107 → 75 tok/s | `references/gotchas.md:47` | 2026-11-16 | hypothesis (laptop, ExLlama) | None |

## Inkling-2-Mini uncensored quants, the GodGMN fork and exllamav3-rocm (2026-11-22)

Model cards read through the Hugging Face API and the GGUF headers read by HTTP range, both on 2026-11-22;
the fork's documentation was read the same day. Nothing below is a measurement of ours except where it
says so. Owner docs: the survey in [`models/inkling-2-mini.md`](models/inkling-2-mini.md#quant-survey-2026-11-22)
and the [engine-alternatives review](ENGINES-EXPERIMENTS.md#engine-alternatives-review-2026-11-22-desk-review-nothing-built).

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| AtomicChat's uncensored AD-Q4_K: KLD 0.0115 vs. BF16, 95.6% same top-1, MMLU 80.65 → 79.15. nokeepai Unbound v2: refusals 0.4% / 1.1%, useful answers 78.7% / 83.4%, KLD 0.0318. The heretic file: refusals 100% → 6%, MMLU 78.7 → 78.0, KL 0.049 | [AtomicChat Uncensored](https://huggingface.co/AtomicChat/Inkling-2-Mini-Uncensored-GGUF) card and the two sibling repos' cards | 2026-11-22 | source-checked; KLD references differ per repo, so the three are not rankable against each other | Speed and fit only, no KLD/MMLU/refusal run ([results](../results/20261122-inkling-uncensored-ad-q4k/README.md)) |
| The same cards' head-to-head ranks AtomicChat's LoRA at 51.6% / 56.3% useful answers against nokeepai's 78.7% / 83.4% | nokeepai card (author-run comparison) | 2026-11-22 | hypothesis (conflict of interest: the comparison is published by a competing quantizer) | Not re-run; this repository has no useful-answer metric |
| GodGMN `inkling-rdna3`: tg128 64.0 tok/s vs. 31.9 on b12600, pp4096 1,802 vs. 854, 393,216 context with `q4_0` KV at a 23.2 GB peak, 10 of 10 facts retrieved | [fork](https://github.com/GodGMN/llama.cpp) `docs/inkling-rdna3.md` at `cb0e46960` | 2026-11-21 | source-checked (author's own RX 7900 XTX, ROCm 7.2.1, IQ4_NL); not reproduced | Different file, KV type and runtime: 42.0 tok/s at 262K, 48.2 tok/s at 64K `f16` ([BUILD.md](../results/20261122-inkling-rdna3-fork/BUILD.md)) |
| Inkling's attention kernel ignored a quantized KV cache, so 8-bit KV used more VRAM than `f16`; fixed with banded FA plus three fused CUDA kernels | [unslothai/llama.cpp PR #386](https://github.com/unslothai/llama.cpp/pull/386) | 2026-11-22 | source-checked (fork-only PR, CUDA-benchmarked) | Not measured: that fork is not built here and every arm used `f16` or `q8_0`/`q5_1` KV on the other path |
| exllamav3-rocm is stale since 2026-09-26, its RDNA3 work moved to `SelfRef/exllamav3-rdna`, and Q8 KV caps around 192-196K | repository state plus [issue #2](https://github.com/phoenixhaxor/exllamav3-rocm/issues/2) (the user's pointer; issue body not re-read) | 2026-11-22 | source-checked (repository state) | Nothing run; no EXL3 model is installed |

## Inkling-2-Mini engines, drafters and adapters (2026-11-22)

Desk review plus one local run ([DSpark on the fork](../results/20261122-inkling-dspark-fork/README.md)).
Owner of the conclusions: [inkling-2-mini.md](models/inkling-2-mini.md#engine-and-variant-review-2026-11-22-second-pass).

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| B70 (Xe2, 32 GB) best Inkling route is vLLM XPU + PR #69186 on the official safetensors: 54.5 / 44.7 / 31.7 tok/s at 0 / 32K / 128K, 262K context; +DSpark k=7 80.4 at 0 | [SergiioB B70 cookbook](https://github.com/SergiioB/intel-arc-pro-b70-inference-cookbook/blob/master/docs/inkling2-mini/README.md) | 2026-11-22 | author-reported | none (no vLLM ROCm Inkling path found for gfx1100) |
| Q8_0/BF16 Inkling GGUFs cannot beat NVFP4 experts (release has 4-bit experts only) | same repo, `docs/DO-NOT-REPEAT.md` DNR-040 | 2026-11-22 | reasoned from `hf_quant_config.json` | none |
| DSpark n=3 on llama.cpp SYCL at temperature 1.0: -31% (13.5 vs. 19.5 tok/s, 43% acceptance) | same, DNR-034 | 2026-11-21 | author-reported | our fork cannot load the drafter ([run](../results/20261122-inkling-dspark-fork/README.md)) |
| llama.cpp IQ4_NL: prompts > ~96 tokens give all-`?` output (CUDA and CPU) | [llama.cpp #32778](https://github.com/ggml-org/llama.cpp/issues/32778) | 2026-11-22 | open issue, read | not seen on the GodGMN fork with Abiray IQ4_NL (32K prompts, [run](../results/20261122-inkling-fork-ngram/README.md)) |
| Upstream dense rel-bias mask: chunked build (#32752) and compact bias in FLASH_ATTN_EXT (#32740), both open | [#32752](https://github.com/ggml-org/llama.cpp/pull/32752), [#32740](https://github.com/ggml-org/llama.cpp/pull/32740) | 2026-11-21 | open PRs, read | none |
| `maya-ik2` HIP port on an RX 7900 XTX: 117.11 / 107.47 / 93.70 tok/s decode after 512 / 8,192 / 32,768 input tokens, 3,365.65 tok/s prefill on 8,192, 393,216 positions reserved, ggml-org IQ4_NL, E4M3 KV | [GodGMN/maya-inkling-mini `hip-port`](https://github.com/GodGMN/maya-inkling-mini/tree/hip-port) README and `docs/HIP-PORT.md` (commit `2b31ffe`); the author's post | 2026-11-22 | hypothesis (author's numbers; ROCm 7.2.1 container, power cap not stated) | None; fork baseline 50.0 tok/s at 272 W |
| The port's expert kernels read IQ4_NL, NVFP4 and Q8_0 only, one type for gate/up/down | same repo, `src/ik2/ik2_rdna3.hip:441`, `src/ik2/ik2_kernels.cu:5994`, `src/ik2/ik2_main.cu:3193` | 2026-11-22 | source-checked | AtomicChat AD-Q4_K experts are Q4_K + Q5_0: not loadable |
| Drafter in the port: 117.22 -> 137.49 tok/s at 512 input, 116.26 -> 89.51 on a 257-token story; serving rejects a drafter without the block path | `docs/HIP-PORT.md` "Completed archive and drafter runs"; `src/ik2/ik2_main.cu:5393` | 2026-11-22 | source-checked (rule), hypothesis (numbers) | None |
| project-maya v1.1.75 (`8621f7a7`, #1154 squashed in): Inkling drafting "on AMD", decode +29% at 262K on a Radeon 8065S; "Radeon RX 7000 / 9000 cards are built but untested"; reads NVFP4 / Q8_0 / Q5_K / Q6_K / IQ3_XXS / IQ4_XS blocks, not IQ4_NL | [release v1.1.75](https://github.com/mw00/project-maya/releases/tag/v1.1.75), `CHANGELOG.md`, `src/ik2/ik2_kernels.cu:7594` | 2026-11-23 | source-checked; gfx1100 not measured | The GodGMN port's drafter on gfx1100: 4-17% slower ([round 3](../results/20261123-inkling-round/README.md#dspark-drafter-the-hiperrorinvalidimage-cause-fixed-slower-on-this-card)); v1.1.75 skipped (cannot read our IQ4_NL experts) |
| Upstream Maya on a 7900 XTX (ROCm 7.2.4): 109.1 tok/s decode (unsloth UD-Q4_K_XL), 94-95 (JoaoZaokk Heretic UD-Q4_K_XL), ~2,270-2,320 prefill, 131,072 context | [mw00/project-maya#1116](https://github.com/mw00/project-maya/issues/1116) | 2026-11-22 | hypothesis (one field report) | None |
| CUDA `maya-ik2` on an RTX 3090 (300 W): 124-128 tok/s plain, 131 prose / 149-212 code and edits with the DSpark drafter, llama.cpp b12590 57.0 | [alesha-pro/maya-inkling-mini](https://github.com/alesha-pro/maya-inkling-mini) README | 2026-11-22 | hypothesis | not applicable (CUDA) |
| Inkling has no MTP head; its DSpark drafter runs as `--spec-type draft-dspark -md <drafter>` on Unsloth's build | [unsloth `dspark/README.md`](https://huggingface.co/unsloth/Inkling-2-Mini-GGUF/blob/main/dspark/README.md) | 2026-11-22 | source-checked | Fork rejects it: `markov_w1.weight` 201,024 vs. 200,058 ([run](../results/20261122-inkling-dspark-fork/README.md)) |
| Inkling DSpark in llama.cpp: PR #32218 open draft, changes requested; x1.05-x1.64 on a Mac M3 | [ggml-org/llama.cpp#32218](https://github.com/ggml-org/llama.cpp/pull/32218) | 2026-11-22 | hypothesis (scout summary of the PR page) | None |
| OpenUncensored LoRA: rank-2 projection on `attn.wo_ud` of layers 4-23, experts untouched; 0/32 refusals, MMLU 78.95 -> 79.47 | [OpenUncensored/Inkling-2-Mini-Uncensored-LoRA](https://huggingface.co/OpenUncensored/Inkling-2-Mini-Uncensored-LoRA) card | 2026-11-21 | source-checked (method), hypothesis (numbers, author-run) | None |
| AtomicChat LoRA GGUF (41.8 MiB, "rank-1 on the 49 places that write into the residual stream"); LoRA row MMLU 80.65 -> 79.15 (p = 0.006) | [AtomicChat/Inkling-2-Mini-Uncensored-GGUF](https://huggingface.co/AtomicChat/Inkling-2-Mini-Uncensored-GGUF) card | 2026-11-21 | hypothesis (scout summary) | None |
| Strata 0.2.19 `strata-inkling`: SQ-20 "bit-exact lossless", 198.9-250.3 tok/s | [Niko1221/Strata releases](https://github.com/Niko1221/Strata/releases) | 2026-11-22 | hypothesis (no gfx1100 Inkling number; speed is an RTX 5090) | None |
| No source reports ~800K context on a 24 GB 7900 XTX; GodGMN's figure is 393K | [ggml-org/llama.cpp#32694](https://github.com/ggml-org/llama.cpp/pull/32694) comment; the port's README | 2026-11-21/22 | source-checked | not applicable |

## inference-optimization-playbook (2026-11-22)

[alesha-pro/inference-optimization-playbook](https://github.com/alesha-pro/inference-optimization-playbook)
@ `53868e2` (2026-11-21, MIT) is a map of 115 tested speed ideas, each with a verdict, numbers, the reason and a
"revisit when", from DeepSeek V4.1 Flash, Qwen3.8-Flash-Next, GLM-5.3-Flash, MiniMax-M3.1-Flash and Hy4 Flash on
4x RTX 3090 with experts offloaded to RAM, plus Inkling 2 Mini on one RTX 3090 with every expert in VRAM. Engines:
Strata, Maya forks, an exllamav3 fork, llama.cpp, vLLM. The repo root is an agent skill (`SKILL.md`, 16 chapters
in `playbook/`, `ledger/hypotheses.md` with condition tags, `cases/`, `protocol/`, two stdlib tools). No AMD
data and no concurrent-load data.

**How to use it here.** Before planning a speed campaign or a new model bring-up, fill its
`protocol/situation-card.md`, take the tag line, and grep the ledger with it; then check this repository's
[`TRIED.md`](TRIED.md) as usual. Our single-card regime is `#in-vram #1gpu` (the playbook says it has little
data of its own there: read chapters 08 drafter, 11 sessions and prompt cache, 13 output head, 14 benchmark traps).
The Inkling-2-Mini case (`cases/inkling-2-mini.md`) and Qwen3.8-Flash-Next case are the closest to
[`models/inkling-2-mini.md`](models/inkling-2-mini.md) and [`sop/strata.md`](sop/strata.md). Treat every number as
CUDA/Ampere evidence: it transfers as a mechanism, never as a value, until reproduced on gfx1100.

**New versions.** It is a living notebook (dated entries, superseded results kept). At each engine update or
new-model bring-up, read its `CHANGELOG.md` since the commit pinned above, record new rows that touch
`#in-vram`, `#1gpu`, `#kv`, `#drafter` or `#agent` here, and move the pin.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| Inkling 2 Mini, every expert in VRAM, one token as one CUDA graph: decode 57 (llama.cpp) → 112 tok/s on one RTX 3090 | `ledger/hypotheses.md` PL-15, `cases/inkling-2-mini.md` | 2026-11-21 | source-checked (author's numbers; CUDA-only engine) | None; our Inkling numbers are in [`models/inkling-2-mini.md`](models/inkling-2-mini.md) |
| Final resident engine, FP8 KV, 344K window: decode 128.7 / 105.6 / 62.3 tok/s at 47 / 64K / 340K tokens | `cases/inkling-2-mini.md` | 2026-11-21 | source-checked (author's numbers) | None |
| A short benchmark promised +27% decode; real generation gave +2% | `README.md` | 2026-11-21 | source-checked (no setup given in the README) | Consistent with our policy of 240K pairs and real traffic ([`BENCHMARK-FORMAT.md`](BENCHMARK-FORMAT.md)) |
| A drafter change matched on 4,400 tokens of the first turn and broke the second turn | `README.md` | 2026-11-21 | hypothesis for llama.cpp MTP | None; argues for multi-turn checks in [`speculative.md`](measurements/speculative.md) |

## Intel XPU inference-optimisation skill and the B70 Inkling posts (2026-11-23)

[SergiioB/intel-xpu-inference-optimisation-skill](https://github.com/SergiioB/intel-xpu-inference-optimisation-skill)
(pushed 2026-11-23T10:35Z) is the Intel Arc B60/B70 (Xe2) adaptation of the
[sybil-solutions skill](#inference-optimisation-agent-skill-2026-11-20) (that one is still at `fda968e`, pushed
2026-11-16: nothing new). Same layout (`skills/intel-xpu-inference-optimisation/SKILL.md`, `references/`), plus
`kv-and-context.md`, `quantization.md`, `kernels-xe2.md` and a do-not-repeat list (`DNR-*`). Its Inkling numbers
are vLLM XPU + `vllm-inkling2-xpu` (B70); none are AMD. A post by @VeidtKV (2026-11-23, read through an X mirror)
reports Inkling-2-Mini Q4_K_M running on a B70 with llama.cpp Vulkan, no numbers, drafter still being worked on.

**How to use it here.** A prior for KV and drafter decisions, never a value: re-read `kv-and-context.md` and
`levers.md` when changing the KV policy or when a drafter runs on gfx1100, and record new rows that touch
`maya-ik2`, llama.cpp HIP/Vulkan or Inkling.

| Claim | Source | Date | Status | Own test |
|---|---|---|---|---|
| llama.cpp disables flash attention automatically for models with an additive attention bias (`kq_b`), "like Inkling" | `references/kv-and-context.md:63` | 2026-11-23 | source-checked (quote); mechanism not re-checked in llama.cpp source | Our production engine for Inkling is `maya-ik2`, not llama.cpp; [`models/inkling-2-mini.md`](models/inkling-2-mini.md) |
| `q4_0` K cache: mean KLD ~5.5 "regardless of V precision" | `references/kv-and-context.md:22` | 2026-11-23 | source-checked (quote; B70 SYCL, model not stated in that row) | Our KV policy and measurements: [`measurements/kv-quality.md`](measurements/kv-quality.md) |
| Inkling 2 Mini on B70: vLLM XPU + DSpark k=7, 57.2 -> 80.4 tok/s card sampling, 8/8 PASS | `references/levers.md:12,47` | 2026-11-23 | source-checked (author's numbers; Intel-only stack) | not applicable (DSpark does not load on our HIP build: [round](../results/20261123-inkling-round/README.md)) |
| llama.cpp SYCL graph replay on Inkling: +34.1% short / +26.6% at 8K, 5/5 greedy identical | `references/levers.md:23` | 2026-11-23 | source-checked (SYCL-only flag) | not applicable: `maya-ik2` already replays one graph per decode step (engine log) |
