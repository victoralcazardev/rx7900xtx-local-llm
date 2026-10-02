# Engine experiments and watchlist

Trials (prepared or run, not adopted) and upstream items being monitored. Nothing here is adopted; the
builds actually in use, with pinned versions and SHA256, are in [`ENGINES.md`](ENGINES.md), and
tried-and-not-adopted results are in [`TRIED.md`](TRIED.md). Proposed experiments below are not local
results unless explicitly marked as run.

## End-to-end quality and reliability before tuning (2026-10-02, proposed; not run)

**Priority:** preserve the adopted profile until a fixed coding-task suite exists. Retrieval checks
and pooled results establish retrieval only; they do not establish repository-editing quality. The
exact adopted flags have 8/8 retrieval at 240K, while 68/68 pools multiple configurations; neither
is a coding-agent quality score ([`depth.md`](measurements/depth.md#quality-ruler-style-200k-q8q8-mtp)).
The six full cache misses in the long agent session remain unexplained; do not attribute them to
checkpoint count or compaction threshold without a diagnostic trace
([`agent-traffic.md`](measurements/agent-traffic.md#full-cache-misses-in-a-long-session-2026-10-01)).

### Sequence and controls

1. **Capture a baseline, without changing the profile.** On the next naturally occurring cache miss,
   retain the server log and record prompt/cache token counts, `f_sim_best`, `f_keep`, checkpoint
   positions and the earliest divergent prefix position. Do not publish raw prompts, tool outputs or
   private session logs. If the divergence is near the start, compare the effective serialized
   system prompt, tool schema and conversation prefix first. If it is mid-prefix, record whether a
   retained checkpoint exists before that position. The current b11160 server already evicts nearby
   checkpoints and handles the last-user/near-end cases; an older FIFO-eviction report is not proof
   that this build lacks those fixes ([`memory.md`](measurements/memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29), [SOURCES.md](SOURCES.md#engine--backend)).
2. **Freeze a small coding-task suite before runtime A/Bs.** Use repeatable, real repository tasks
   with clean worktrees, fixed task prompts, an executable test or explicit pass/fail rubric, and
   recorded tool-call trajectories. Include short and long-context tasks; use the same model weights,
   compatible MTP artifact, harness, tools, sampling and task order policy across arms. A task is a
   success only when its specified tests pass and no required tool/result is omitted. Keep retrieval
   probes as a separate metric, not a proxy for code quality.
3. **Run paired, counterbalanced repetitions.** First collect the unchanged baseline, then change
   exactly one factor at a time. Repeat the same tasks/contexts at approximately 190K and 240K where
   feasible; report per-task results and sample count, not only an aggregate. Record exact model
   file hashes, engine commit/build flags, runtime/harness version and effective settings, GPU/host
   baseline, power cap, context fill, sampling, tools, task seeds and commands. Apart from the one
   deliberately varied factor, differences in these controls make an arm confounded; do not attribute
   its outcome to the intended change.

### Metrics and stop gates

- **Primary:** task pass rate, regressions by task, correct tool-call/result handling, incomplete or
  repeated work, and whether output limits or errors prevented task completion. Require no loss of
  task correctness before accepting a speed or memory gain.
- **Latency/cost:** end-to-end wall time; time-to-first-token; prefill and decode rates; p50/p90 by
  context depth; actual prompt/cache/output token counts; compaction and summary time; cache misses;
  tool retries and stop reasons. Count tokens, not output characters.
- **Resource/reliability:** peak process VRAM and system-wide free VRAM as distinct measures, host
  RSS/free RAM/swap, GPU temperature/power, evictions, server restarts, faults and NaNs. Stop on a
  GPU memory fault or NaN and diagnose the captured failure; do not hide it with startup retry loops.
  Stay within the existing 272 W cap and current safety limits.
- **Decision rule:** report paired task outcomes and latency distributions with conditions. Reject a
  faster arm if task correctness, tool reliability, output completion or safe resource headroom
  regresses. Label single-sample, external, estimated and not-run evidence explicitly.

### Ordered experiments after the baseline

1. **Cache-miss diagnosis first.** Only if a trace shows repeatable mid-prefix divergence and a
   missing usable checkpoint before it, compare `--ctx-checkpoints 4` with `16` in the fixed suite.
   Track retained positions, host-memory cost and miss recovery time. Locally measured checkpoints
   ranged about 270–515 MiB at positions around 30.7K–92.9K; their sizes at deeper positions,
   including 190K/240K, are unknown. Do not extrapolate or raise the count speculatively. If the
   serialized prefix differs near the beginning, fix/standardize that serialization instead of
   increasing checkpoints. No cache-cause conclusion is established yet.
2. **Harness compaction costs.** Inventory actual effective settings and request timelines before
   changing compaction. The official omp v18.4.4 documentation describes asynchronous snapshot
   summarization and discarding stale snapshots; it does not establish that this harness currently
   enables that path. Because this server is configured `-np 1`, possible contention from background
   summarization is a hypothesis only: compare request timing, cache reuse and wall time under the
   same single-slot workload before considering any setting change. A local `shake` avoids a model
   summarization call but rewrites the prefix and can force reprocessing; it is not free. Do not turn
   on asynchronous compaction as an assumed optimization.
3. **Compaction and sampling A/Bs.** After the suite baseline, compare the current 70% threshold
   against 60%, and compare compaction method/order one factor at a time. Keep Qwen's documented
   sampling and `reasoning_effort=medium` initially: the model card describes medium as a speed/quality
   balance and warns lower effort can increase failures/retries. Test presence penalty only as its
   own quality-gated arm; do not silently lower reasoning effort or add unlisted sampling flags.
4. **Quant-versus-context Pareto (optional).** Compare candidate quants built from the same base
   weights with compatible MTP artifacts. First compare each quant with the adopted baseline at
   matched context fill and identical tasks/settings, to isolate quant effects. Then test that
   quant's lower-context policy as a separate arm; include 64K/128K/190K/240K only where it fits
   safely. Do not assume a 4-bit quant fits any particular context on this 24 GB card. Report quality
   and resource/latency tradeoffs; perplexity alone is not an adoption criterion.
5. **Upstream candidates are routine-update checks, not the first optimization.** Keep b11160 pinned
   until an exact engine commit is built and validated. PR #28003 has a draft gfx1100 single-token
   no-MoE Q4_K kernel result, not an IQ3_S or MTP verification result; PR #29393 reports a CUDA
   prefill gain, while HIP benefit is unmeasured. PR #27489 reports a CUDA memory saving and has no
   HIP speed evidence. Recheck their exact revisions/status at the next planned engine update; do
   not choose a floating `latest` tag or claim a local gain. See [SOURCES.md](SOURCES.md#engine--backend).
6. **Lower-priority candidate checks.** The rdna-boosts GQA-6 route is RDNA4/gfx1201 evidence and
   is not a ready gfx1100/q8_0-q5_1 speedup; a community report also found slower non-MTP decode.
   Do not prioritize a fork build ahead of the cache diagnosis and coding suite. If later tested,
   pin the precise source revision (the fork's release/latest references conflict), verify the
   exact kernels and backend, and run the same paired quality and performance suite. KVMem remains
   pending the real-agent T6 run in [its trial record](#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted);
   its existing trial numbers are not repeated here or evidence of adoption.

**Status:** all work in this section is proposed and unrun. No configuration, engine, harness setting,
or profile has changed as a result of this plan.

## Fork vs. wait for upstream, and the rdna-boosts GQA-6 FA band (2026-10-01, candidate, not run)

Question: instead of waiting for the tracked upstream items, carry them as patches on our own build?
Checked llama.cpp b11301 → b11320 first (19 commits): nothing touches HIP, ROCm, `fattn` or the KV
cache. [#29019](https://github.com/ggml-org/llama.cpp/pull/29019) (preserve batch order for
speculative layer inputs) only matters with concurrency > 1 and a DFlash drafter; this profile runs
`-np 1` with MTP.

**Most tracked items have no code to merge.** Linked pull requests per issue (GitHub timeline,
2026-10-01):

| Item | Code available | Value for this profile |
|---|---|---|
| [#26038](https://github.com/ggml-org/llama.cpp/issues/26038) MTP draft FA workspace on HIP | Only the reporter's own downstream patch (gfx1030/1031, bundled with unrelated changes) | VRAM only; size on this profile not measured |
| [#27282](https://github.com/ggml-org/llama.cpp/issues/27282) duplicate MTP compute arena | [PR #27489](https://github.com/ggml-org/llama.cpp/pull/27489): open, conflicting, last updated 2026-08-21, auto-enabled only for "single-CUDA-device"; −1,042 MiB peak on a CUDA card; users report aborts | VRAM only (could buy V `q8_0` or `-ub 512` if the saving holds on HIP); a HIP port with no maintainer buy-in |
| [#28433](https://github.com/ggml-org/llama.cpp/issues/28433) draft context sized from `llama_n_ctx` | None; the proposed fix was withdrawn by its contributor; [PR #29208](https://github.com/ggml-org/llama.cpp/pull/29208) (open) clamps to `n_ctx_train` | None: hits multi-slot unified KV, this profile is `-np 1` |
| [#26432](https://github.com/ggml-org/llama.cpp/issues/26432) silent GTT fallback with MTP | None | None: the 262K profile is measured without spill |
| [#28867](https://github.com/ggml-org/llama.cpp/issues/28867) gfx1201 FA threshold | None | gfx1201 only |
| RDNA3 FlashAttention GQA folding (the depth-decode bottleneck, [depth.md](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4)) | No upstream PR; one fork implementation, below | Not yet demonstrated as a compatible or beneficial gfx1100/q8_0-q5_1 change; lower priority than cache diagnosis and the coding suite |

Conclusion: do not maintain a fork. Patch on demand: apply a specific change on top of the pinned tag
(as with `kvmix-vec4` in [`ENGINES.md`](ENGINES.md)), A/B it, and keep it only if it wins.

**Candidate: the rdna-boosts GQA-6 decode/verify band.**
[stew675/llama-cpp-rdna-boosts#45](https://github.com/stew675/llama-cpp-rdna-boosts/issues/45)
(closed, shipped in release `v16-84e76d8a2-r4`, extended to f16/bf16 in `r5`) addresses the same
cause as [depth.md](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4):
"With GQA 6, `ncols2` falls back to 2, and ... every K/V element is fetched and dequantized three
times per query token". It routes `n_q <= 8` (decode and MTP verify) to the existing MMA-f16 instance
`(256, ncols1 4, ncols2 8)` and splits KV round-robin so decode and verify stay bit-identical.

- Reported (R9700, gfx1201, Qwen3.8-27B, q8_0 K/V, `draft-mtp`): FA at kv 204800, `n_q` 3: 4121 →
  1654 µs; `llama-server` decode at 110K: 28.20 → 36.03 t/s; plain decode without MTP ~5% slower;
  `test-backend-ops` FA cases and greedy `plain == draft-mtp` pass.
- **Gated to RDNA4** (the fork README: "`r4` the block-15 RDNA4 GQA-6 decode/verify flash-attention
  band"). On gfx1100 it does not engage. The same README states the WMMA FA path also runs on RDNA3.0
  with a head limit of 256; this model's `head_dim` is 256. Whether the band builds and wins on
  first-generation RDNA3 WMMA is unknown.
- This repo's earlier rdna-boosts trial (`v16-ebbb18522-r13`, −2.5% ms/step at ~190K, see
  [`ENGINES.md`](ENGINES.md)) predates the band, so it says nothing about it.
- Risk: [stew675/llama-cpp-rdna-boosts#60](https://github.com/stew675/llama-cpp-rdna-boosts/issues/60)
  (open, 2x 7900 XTX, different MoE model) reports a 334.39 MiB allocation OOM in long prefill from
  `r5` on, avoided by `GGML_CUDA_FA_KV_NATIVE=0` or a smaller `-ub`. The reporter's title attributes it
  to an unrelated indexer reserve, not the band. This profile peaks at 22,630 MiB, so headroom is thin.

Test plan (not run):

1. Select and pin one exact fork commit/release after reconciling the fork's release and `/releases/latest`
   references; do not use a floating `latest` tag. Build for gfx1100 with the `kvmix` FA-quants flags,
   widening the band's architecture gate to RDNA3.
2. `test-backend-ops -o FLASH_ATTN_EXT` for head 256 with `q8_0`/`q5_1`, and greedy `plain ==
   draft-mtp` at depth.
3. One A/B against `kvmix` at 190K and 240K fill: decode, prefill and peak VRAM.

Go if decode at 240K improves by more than ~10% with no quality or VRAM regression; otherwise record it
in [`TRIED.md`](TRIED.md).

## KVMem trial round 2 and final round (2026-09-30, not adopted)

**Outcome: candidate = budget 28,672 + `--kvmem-block-tokens 32`; meets 3 of 4 go/no-go criteria,
agent run (T6) outstanding, not adopted.** Background, source pin and protocol are under the round 1
section below; evidence: [`results/20260930-kvmem-trial-round2/`](../results/20260930-kvmem-trial-round2/).
Single samples.

| Criterion | Result |
|---|---|
| Decode at 160K+ at least ~1.3x the current profile | Met: 45.5 tok/s at 244K vs. 20.8 (2.2x); VRAM 15.1 GiB; round 1 at block 128 gave 48.6 |
| Retrieval 8/8 exact at 240K | Met: 8/8 at 240K; 4/4 at 190K and 4/4 at 220K; 128K 8/8 was measured at block 128 and not re-run at 32 |
| At least ~4 GiB host RAM free at 256K | Met: minimum 10.15 GiB at 244K (RSS 13.67 GiB) |
| Agent run without output-cap failures | Not run (T6) |

- Block size, not budget, fixes the round 1 miss (`PLANO-01-03-469`): block 32 at 28,672 is 8/8;
  budget 36,864 at block 128 is 3/4 with the same miss.
- Budget 49,152 is unusable: the 190K crash reproduced (2 of 2), a GPU `Memory access fault` at the
  end of prefill, and the faulted server ignores SIGTERM. Not traced; not reported upstream, nor is
  the ROCm build fix.
- Not done: candidate speed at 128K/190K, MTP n=3, traced crash run, quality on the remaining
  documents. The 16,384-token per-turn output cap remains a risk. Next step: T6 with the candidate.

## KVMem trial (round 1 run 2026-09-30, not adopted)

[kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp) (paper
[arXiv:2609.04852](https://arxiv.org/abs/2609.04852)) is a llama.cpp fork with its own
`llama-kvmem-server`. It keeps the full logical workspace (`-c 262144`) in host RAM and, for each
agent step, retrieves the relevant 128-token KV blocks into a bounded GPU working set
(`--kvmem-budget` + `--kvmem-gen-reserve`). Attention then runs over that set instead of the whole
history. It is the one candidate that could bound decode cost at depth, where the current profile
drops to ~19-23 tok/s (see `measurements/agent-traffic.md` and `measurements/depth.md`). Claims and
caveats are checked in [`SOURCES.md`](SOURCES.md#context-length-and-compaction-claims-reviewed-2026-09-30).

**Round 1 outcome (2026-09-30): promising, not adopted; next round pending.** Evidence, exact
commands and raw data: [`results/20260930-kvmem-trial/`](../results/20260930-kvmem-trial/). Built
from source at `abe72b38256d` with two local ROCm build fixes (`rocm-build-fix.patch`, not reported
upstream); `llama-kvmem-server` lacks `/tokenize` and `/completion`, so `bench/depth_bench.py` and
`bench/longctx_quality.py` could not be used and two chat-API scripts replaced them (steps 3-4
below were run that way). Single samples; the arms also differ in KV types (q8/q8 vs. q8/q5_1),
MTP n (2 vs. 3) and `-ub`, so ratios are not a pure KVMem effect.

| Criterion | Result |
|---|---|
| Decode at 160K+ at least ~1.3x the current profile | Met: at 244K, 48.6 tok/s (budget 28,672, 2.34x) and 40.2 (budget 49,152, 1.93x) vs. 20.8; VRAM ~15-16 GiB vs. 22.6 GiB |
| Retrieval 8/8 exact at 240K | Budget 28,672: 7/8 (deterministic miss, needle at token 40,302); 128K 8/8. Budget 49,152: 8/8 |
| At least ~4 GiB host RAM free at 256K | Met: minimum 6.51 GiB (RSS 9.4 GiB at budget 28,672, 13.1 GiB at 49,152) |
| Agent run without output-cap failures | Not run (T6) |

Other findings: budget 49,152 crashed once at the end of a 190K prefill (`Memory access fault by
GPU node-1`, not reproduced); thinking is off by default and needs `--enable-thinking`; MTP
acceptance is not reported; smoke test 71.5 tok/s at empty context. Blockers before adoption:
reproduce the crash, run the agent run, and accept the 16,384-token per-turn output cap.
Third-party context: [`SOURCES.md`](SOURCES.md) (upstream issue #4 on mid-band retrieval collapse).

**Next round**: run as round 2 above (crash reproduced, budget 36,864, block 32); budget 40,960, 3 repeats and MTP n=3 were not run.

**Source pinned for the trial**: `kvmem/kvmem-llama.cpp` commit `abe72b38256d` (2026-09-30, source
version 0.17.0), llama.cpp submodule `7fe450e19305`. The prebuilt ROCm packages are older
(`rc3-rocm-beta2`, built on Ubuntu 24.04 against a ROCm 10 runtime), so build from source with the
same ROCm 10 venv toolchain as `hip-kvmix` (above):

```bash
git clone https://github.com/kvmem/kvmem-llama.cpp.git && cd kvmem-llama.cpp
git checkout abe72b38256d && git submodule update --init
source ~/src/rocm10-venv/bin/activate && export ROCM_PATH=$(rocm-sdk path --root)
python3 scripts/build-rocm.py --linux --gpu-targets gfx1100 --jobs 6   # output: build-hip-linux/
ctest --test-dir build-hip-linux --output-on-failure
```

Build only with the model server stopped: HIP kernel compilation needs several GiB of RAM per job,
and a loaded `llama-server` plus the desktop can leave as little as ~9 GiB available on this host.

**Known fit constraints (from the upstream README and ROCm guide, not yet verified here):**

- **KV types**: `f16`, `q8_0`, `q5_0`, `q4_0` only; there is **no `q5_1`**. The upstream IQ3 recipe
  uses `q8_0/q8_0`, which the bounded GPU working set makes affordable. Mixed pairs other than
  `q8_0/q4_0` have argument-parsing checks only, and "ROCm/Vulkan combinations have not been
  validated".
- **Per-turn output cap**: one generation can't exceed `--kvmem-gen-reserve` (16,384 tokens on the
  IQ3 recipe), thinking included. In the real agent traffic here, 4 of 1,303 turns went over 16,384
  output tokens. The upstream launcher also passes `--reasoning-budget 4096`; this repository sets
  a reasoning budget only with evidence (`AGENTS.md`), so the trial leaves it out and records any
  turn that hits the cap.
- **Retrieval anchor**: the IQ3 launchers use `--kvmem-query-policy user`, so retrieval is keyed
  on the last real user message. Tool results are not treated as user messages. The upstream
  query-replay report says the already-read suffix after that user message is kept rather than
  re-selected. In a harness session where one user message starts hours of tool calls, that
  suffix can exceed the GPU budget. How KVMem behaves there is the main open question for this
  workload, even though the paper's DeepSWE result (43.8% → 48.4%) is the same kind of
  single-task agent loop.
- **MTP**: the ROCm launcher uses MTP n=2 with `--kvmem-mtp-state replay`; the current profile uses
  n=3.
- **Host RAM**: the ROCm guide measures ~13-14 GiB of runtime host memory at 256K and recommends
  32 GiB of system RAM. This host has 32 GiB installed, 31.25 GiB usable (`MemTotal`; ~890 MiB is
  reserved by firmware and the kernel), plus zram swap. KVMem replaces `llama-server` (~3.5 GiB
  RSS with the current profile), so the net increase is ~10 GiB. With the desktop's current usage
  that should leave ~10 GiB available; the trial measures it.
- **GPU KV budget**: the ROCm launchers default to `KVMEM_GPU_KV_BUDGET=28672`, validated on a
  16 GiB card. This card has 24 GiB, so a larger budget is possible.

**Trial protocol** (GPU free, `llama-server` stopped):

1. Build and `ctest` as above; check `llama-kvmem-server --help` for every flag below before
   using it.
2. Smoke test on port 8080, text-only (no `--mmproj`), card sampling, with the upstream IQ3 KVMem
   flags: `-c 262144 --kvmem --kvmem-budget 28672 --kvmem-gen-reserve 16384
   --kvmem-block-tokens 128 --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --spec-type draft-mtp
   --spec-draft-n-max 2 --kvmem-mtp-state replay --reasoning-effort medium` (if supported).
3. Decode speed at depth: `BENCH_SERVER=.../llama-kvmem-server` with `bench/depth_bench.py
   --extra "<KVMem flags>"` at 128K/190K/240K fill; also MTP n=3 and a larger `--kvmem-budget`.
4. Long-context quality: `bench/longctx_quality.py --server .../llama-kvmem-server --variants
   <q8q8 MTP variant> --extra "<KVMem flags>"` at 128K and 240K. Exact-match retrieval is exactly
   what a bounded working set could lose.
5. Real agent run: 1-2 hours of the harness's local agent on a documented plan, then the same
   session analysis as `measurements/agent-traffic.md`: wall tok/s by depth, compactions, repeated
   tool calls, turns hitting the output cap.
6. Record peak process VRAM, host RSS, exact commands and commit hashes (upstream asks for the
   same).

**Go/no-go**: continue to a longer trial only if decode at 160K+ fill is at least ~1.3x the current
profile's (~19-23 tok/s), long-context retrieval matches the current 8/8 exact at 240K, at least
~4 GiB of host RAM stays free at 256K, and the agent run shows no output-cap failures and no loss
of task state. Otherwise record the numbers and drop it.

## Candidates from third-party repositories (2026-10-02, not run)

Source rows and verdicts: [`SOURCES.md`](SOURCES.md#third-party-tuning-repositories-reviewed-2026-10-02).
Nothing here is adopted; the order and conditions are in the private test plan.

| Candidate | Variable | Why it might matter | Kill criterion |
|---|---|---|---|
| `GGML_CUDA_GRAPH_OPT=1` (env var, exists in b11160, off by default) | Environment only, same binary and flags | Enables graph optimization with concurrent streams when HIP graphs are in use; reported +1.4% tg, +1.0% pp at empty context without MTP (dense model) | Under ~2% tg at 190K/240K with MTP n=3, or any output change at greedy, or a VRAM increase |
| `--spec-type draft-mtp,ngram-map-k` on a replayed multi-turn session | Spec type only | A turboquant-fork build reported -17.4% session wall time that a single-request benchmark cannot see; folds into the prepared n-gram A/B in [`speculative.md`](measurements/speculative.md#n-gram-stacked-on-mtp-how-llamacpp-combines-them-source-reading-2026-09-29) | No wall-time gain across turns, or runaway repetition |
| `-DGGML_LTO=ON` build | Build flag only | Asserted "+5-15%" with an empty A/B table; low prior because decode is memory-bound | Under ~2% tg or pp, or a longer build for no gain |
| `GGML_CUDA_DISABLE_GRAPHS=1` | Environment only | Diagnostic for a HIP-graph exec-update hang reported by a third party; not a speed candidate | Run only if a hang appears; never proactively |
| cafe-llama.cpp fork build (`a0d43f3`, upstream base `f1cee99`), single-backend HIP | Engine build; then `--spec-draft-n-max` 3/4/6 | Hybrid-GDN trunk fusions (`src/models/qwen35.cpp`) may cut the target pass at depth; the author claims cheaper MTP on an RTX 3090, but no draft-cost change for Qwen3.8 was found in the code ([`SOURCES.md`](SOURCES.md#cafe-llamacpp-fork-and-the-quimedesu-x-thread-2026-10-02)); never run on AMD | Under ~5% tg at 190K/240K vs. b11160 `hip-kvmix` n=3, any output change at greedy, a build failure on gfx1100, or a missing `kvmix` FA-quants kernel (the fork is a 275-file diff, not a patch to maintain) |

Not carried here: `--reasoning-budget` (profile-level, see [`STATUS.md`](STATUS.md#next-steps)), undervolt (deferred GPU
care) and the fork-only `turbo4`/`turbo2` V caches (not in our engine).

## Upstream watchlist (2026-09-29)

**Keep b11160 pinned: no replacement has been measured on this setup.** The official
[llama.cpp v0.5.0 release](https://github.com/ggml-org/llama.cpp/releases/tag/v0.5.0) lists nightly
b11146, older than this repository's b11160 baseline; its official ROCm binary also lacks the
`q8_0`/`q5_1` FlashAttention kernel required by the current profile. Keep the clock-pinned Vulkan
retest (see "Other engines evaluated" in [`ENGINES.md`](ENGINES.md)) pending; the upstream items below are monitoring candidates, not evidence to upgrade.

| Upstream item | State and relevance | Limit |
|---|---|---|
| [#27530](https://github.com/ggml-org/llama.cpp/pull/27530) | Merged; cleanup after failed K/V and recurrent/hybrid state restoration. A robustness candidate. | No measured Qwen throughput or quality gain established here. |
| [#29393](https://github.com/ggml-org/llama.cpp/pull/29393) | Merged 2026-09-25; RMS_NORM+SCALE fusion, with an author-reported 4.2–4.8% MTP prefill gain on two CUDA GPUs. | HIP benefit on gfx1100 is unmeasured; check at the next pinned engine update, not a promised gain or a reason to upgrade alone. |
| [#28003](https://github.com/ggml-org/llama.cpp/pull/28003) | Draft; gfx1100 single-token, no-MoE RDNA3 GEMV fast path; author reports Q4_K per-GEMV 68.91→62.58 µs and 32-token total 493.9→448.5 ms on a 7900 XTX. | Not measured on IQ3_S, MTP verification batches or this repository's server profile; no local validation. |
| [#27489](https://github.com/ggml-org/llama.cpp/pull/27489) | Open; single-sequence/single-CUDA-device compute-buffer sharing; author reports 1,042 MiB saved on RTX 4090. | CUDA-only evidence; no HIP proof or speed result. Memory-watch only, not an optimization recommendation. |
| [#26648](https://github.com/ggml-org/llama.cpp/issues/26648) | MTP sampler assertion at long context on HIP; closed per [`depth.md`](measurements/depth.md). Moved from STATUS 2026-10-02. | Re-check on the next update |
| [#26038](https://github.com/ggml-org/llama.cpp/issues/26038), [#27282](https://github.com/ggml-org/llama.cpp/issues/27282), [#28433](https://github.com/ggml-org/llama.cpp/issues/28433) | MTP compute and draft-context sizing on HIP; open as of b11178. Moved from STATUS 2026-10-02. | Re-check on the next update |
| [halo-box/strix-llama.cpp#56](https://github.com/halo-box/strix-llama.cpp/pull/56) | RDNA3 IQ2/IQ3 MMVQ scale change ([`SOURCES.md`](SOURCES.md)). Moved from STATUS 2026-10-02. | Not in upstream |
| [BuffedMod IQ3_S quant](https://huggingface.co/tooltd/Qwen3.8-27B-GSQ-RCO-BuffedMod-GGUF) | Same quant with an upcast `output.weight` ([`SOURCES.md`](SOURCES.md)). Moved from STATUS 2026-10-02. | Model, not engine; untested here |

These items are watchlist candidates only; this document does not assert whether any is included in
the current b11160 binary. Reassess only after a compatible build is available and benchmarked on
the adopted Qwen profile.
