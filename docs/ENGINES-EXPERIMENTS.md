# Engine experiments and watchlist

Trials (prepared or run, not adopted) and upstream items being monitored. Nothing here is adopted; the
builds actually in use, with pinned versions and SHA256, are in [`ENGINES.md`](ENGINES.md), and
tried-and-not-adopted results are in [`TRIED.md`](TRIED.md). Proposed experiments below are not local
results unless explicitly marked as run.

## llama.cpp PR #29509 local trial (2026-10-04)

- **What**: b11371 (`99b9548`) plus [#29509](https://github.com/ggml-org/llama.cpp/pull/29509)
  (head `b3c2735`), which stops storing the MTP draft KV in prompt checkpoints. Own build with the
  same [`ENGINES.md`](ENGINES.md) recipe; not published as a release. The PR is open and unreviewed.
- **Evidence**: restores bit-identical to plain b11371 (8/8 per arm, first-token top-5 logprobs Δ0,
  same text and acceptance); checkpoints a constant 149.626 MiB instead of growing ~4,120 B per
  token — [`results/20261004-pr29509-checkpoint-restore/`](../results/20261004-pr29509-checkpoint-restore/README.md).
  Speed and deep-context RSS not measured.
- **Status**: in local trial use since 2026-10-04 as the `hip-kvmix` engine. Rollback: plain b11371.
  Re-evaluate when #29509 or [#28873](https://github.com/ggml-org/llama.cpp/pull/28873) (honors
  `PARTIAL_ONLY` in non-SWA KV; also open) merges.

## Executable optimization queue review (2026-10-03, not run)

**Scope:** review of the manifest, existing measurements, private test queue and actual bench
interfaces; not a new GPU measurement. The launcher dry-run and `check-sync.py` confirm the
[adopted profile](STATUS.md#current-profile). The weights are **IQ3_S-mtp**, not Q8 weights:
`q8_0` describes the K cache, paired with `q5_1` V. Keep that distinction when comparing results.
No model, runtime, harness setting or power limit changes in this review.

### Queue reconciliation and priority

The earlier [quality-first controls](#end-to-end-quality-and-reliability-before-tuning-2026-10-02-proposed-not-run)
still apply. This table is the current execution order; T IDs map the existing private queue,
while the descriptions below are sufficient without access to it.

| Priority | Experiment / existing IDs | Action and prerequisite |
|---|---|---|
| P0 | Cache diagnosis, reasoning retention, capture path (T06/T20/T21/T22) | Consolidate into one request trace; inspect rendered token prefixes, not just ledger deltas. No dedicated GPU run. |
| P0 | Measurement contract; stochastic MTP (T24) | Candidate b11371 is already built, but the existing deep benchmark is greedy. Fix the measurement prerequisite below before judging probabilistic drafting at depth. |
| P1 | Stable tool-result emission (new T25) | Bound new tool outputs with recoverable artifacts instead of rewriting old history. First inventory token contributors, then coding-suite A/B. |
| P1, conditional | Request locality on one slot (new T26) | Only if logs show independent session/summary requests alternating on the same slot; compare scheduling, not more slots. |
| P1 | ~~Broader retrieval (T05)~~ (done 2026-10-03, 40/40), compaction (T02), checkpoint coverage (T23) | Freeze the coding suite first. Threshold control is **70%, not the obsolete 75%**. Checkpoint tuning needs evidence of a missing valid checkpoint. |
| P2 | Probabilistic MTP (T24), n-gram replay (T08/T09), graph optimization (T07) | One factor at a time, each against its pinned control. No dependency on T07 winning. |
| P2 | KVMem real-agent trial (T01) | Finish the existing agent-quality gate; synthetic speed/retrieval results are not adoption. |
| P3 | Verify-path attribution (new T27), then GQA/fusion candidates (T11/T18/T19) | Measure the actual MTP workload before porting a kernel. No new general-purpose fork. |
| Parked | Small flag sweeps, LTO, quant/head changes, MoE, GPU tuning | Keep T10/T12/T14/T15/T16/T17 conditional; revisit only with new applicable evidence or a measured bottleneck. |

**Do not promote:** T04 reasoning-budget tuning without the existing empty-content/length trigger;
presence penalty without observed loops; `preserve_thinking=false` based only on output volume.
The [vendor card](https://huggingface.co/Qwen/Qwen3.8-27B#disable-preserved-thinking) explicitly
connects preserved reasoning to agent consistency, less redundant reasoning and cache utilization.
These are quality-affecting interventions, not free speed knobs.

### P0: make the measurements answer the intended question

The local candidate reports b11371 / `99b9548`; its `--help` includes
`--spec-draft-sampling {greedy,probabilistic}` (default greedy), absent in b11160.
[PR #27694](https://github.com/ggml-org/llama.cpp/pull/27694) is merged and describes rejection
sampling for simple draft/MTP at nonzero temperature. Its author explicitly uses temperature zero
as a control with unchanged accepted length. That is source evidence, not a local gain.

**Blocking mismatch:** `bench/spec_depth_bench.py` sends `temperature: 0`, `seed: 7` in every
request, even though its server argv contains `--temp 1`. `--extra` changes server flags, not
that payload. Repeating these rows measures timing variation, not independent stochastic samples.
It also does not set the adopted reasoning effort explicitly. Existing deep rows remain valid
greedy measurements; do not relabel them as production-sampling or probabilistic-MTP evidence.
The private T24 session contains partial output, not a published adoption result.

Implementation prerequisite for the next measurement change:

1. Extend the existing deep bench, not a second harness, with explicit request temperature and
   seed-list controls; keep its current greedy mode. Record the effective payload and rendered
   template settings alongside `command.json`. Add one regression check that an explicit
   nonzero request temperature reaches the request builder.
2. For production-sampling arms, explicitly use temperature 1.0, top-p 0.95, top-k 20, min-p 0.0,
   medium effort and the adopted engine flags. Keep a separate temperature-zero parity control.
   Confirm these in the request and rendered prompt, not only the server argv.
3. Separate three arms: b11160 greedy draft; b11371 greedy draft; b11371 probabilistic draft.
   The last two isolate the new sampler; comparing only the first and last confounds the engine
   update. Use the same model, depths and seed list; counterbalance arm order across restarts.
4. Screen at empty context, then 190K/240K filled with at least three distinct seeds per task.
   Report cold prefill, warm decode and a growing multi-turn replay separately. Same-seed output
   equality is **not** required between stochastic algorithms with different random-number
   consumption; require task correctness and report output lengths/stop reasons.
5. Proposed go/no-go: at least 5% lower paired median task wall time beyond baseline repeat
   variation, no task/retrieval regression, no new truncation or loops, no evictions and no loss
   of safe system VRAM/host-RAM headroom. An acceptance increase alone does not pass.

The existing scripts can already perform the following **screening only**. Set `BASELINE_SERVER`
and `CANDIDATE_SERVER` to the pinned executable paths, and `BENCH_MODEL` / `BENCH_WIKI` per
[`bench/README.md`](../bench/README.md#configuration). Never run two GPU arms concurrently.

```bash
# First: check interfaces and the configured command without loading a model.
python3 scripts/launch.py --dry-run
python3 scripts/check-sync.py
python3 bench/spec_depth_bench.py --help

# Empty-context, nonzero-temperature screen: control, then candidate's two draft modes.
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \
  BENCH_SERVER="$BASELINE_SERVER" BENCH_OUT="_tmp/optimization/b11160" \
  python3 bench/spec_bench.py --run --variants mtp3 --tag control
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \
  BENCH_SERVER="$CANDIDATE_SERVER" BENCH_OUT="_tmp/optimization/b11371" \
  python3 bench/spec_bench.py --run --variants mtp3 mtp3-prob --tag draft-sampling

# Deep GREEDY parity/timing control only; NOT the stochastic-MTP experiment.
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \
  BENCH_SERVER="$BASELINE_SERVER" BENCH_OUT="_tmp/optimization/greedy-control" \
  python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3 --reps 3 \
  --extra "-ub 256 --top-p 0.95 --reasoning-effort medium"

# Retrieval-only control: five documents at each depth; not a coding-quality verdict.
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \
  BENCH_SERVER="$BASELINE_SERVER" BENCH_EXPECT_POWER_CAP_W=272 \
  python3 bench/longctx_quality.py --run --inhibitor-ok --ctx 262144 \
  --variants q8q51-mtp1 --depths 190000 240000 --docs 5 --mtp-n 3 \
  --extra "-ub 256" --output "_tmp/optimization/retrieval-control"
```

Before every GPU command, verify the GPU is free, the 272 W cap is actually applied, the bench
port is unused and the safety monitor is enabled; never stop the user's server.
The speculative benches do not perform the power-cap preflight themselves
([guard details](../bench/README.md#thermal-and-power-guards)). Do not mistake an environment
variable for enforcement. Hash the model and relevant shared libraries as well as the executable:
the [engine inventory](ENGINES.md) already demonstrates that identical executable hashes can
hide different HIP kernels.

### P0: one prefix trace, then a conditional checkpoint experiment

Capture the exact outgoing messages, tools and template kwargs locally; render/tokenize them with
the **same** model/template as the server. Existing benches use `/apply-template` and `/tokenize`;
reuse that path against an available server, or inspect already captured data offline. Do not
start another model just to call this a "no-GPU" diagnostic. JSON byte differences alone do not
prove token-prefix differences, and aggregate ledger deltas do not prove reasoning retention.

For each adjacent request, record session/request IDs, token longest-common-prefix position,
first changed message category, prompt/cache/output counts, checkpoint create/erase/restore
positions, and any intervening request. Compare `reasoning_content` and embedded thinking blocks
directly; use exact tokenizer counts rather than converting character shares to token estimates.
Publish counts, hashes and categories only; retain private content locally.

Request-level template kwargs override server defaults in the pinned implementation
([source check](SOURCES.md#optimization-queue-source-checks-2026-10-03)).
Therefore a server-side `preserve_thinking=false` A/B can silently do nothing if the client sends
`true`; confirm the effective rendered form. Also measure how much reasoning is actually
**strippable**: the template retains thinking since the last real user query, so a long autonomous
tool loop can keep nearly all of it even with preservation disabled.

The [pinned checkpoint implementation](https://github.com/ggml-org/llama.cpp/blob/70c4e1582/tools/server/server-context.cpp)
first removes nearby older-task checkpoints under pressure, then evicts the oldest if still full.
A usable checkpoint must precede the reusable boundary and satisfy the restore checks; one
**after** the divergence is not useful. Count × stride is not a guaranteed coverage window.
Mid-prompt creation is gated by user-message starts, with last-user and near-end exceptions;
`--checkpoint-min-step` does **not** mean one periodic checkpoint every N tokens.
If a prefix mutation caused the miss, address that producer first. If coverage is the cause,
run `{8192,4}` → `{8192,8}` → `{4096,8}` (stride,count), one factor per adjacent comparison;
consider `{8192,16}` only if host-RAM headroom permits. Measure recovery seconds and peak RSS,
not just hit count. Stop if baseline misses do not reproduce or swapping/headroom regresses.

### New T25: reduce tool-output growth before it enters history

**Hypothesis, not measured:** focused tool responses plus recoverable artifacts can reduce new
prefill tokens and later attention work without invalidating an already cached prefix. This is
not another base-system-prompt trim, nor retrospective `shake` rewriting.

First rank tool categories by their actual newly appended tokens on the frozen coding suite.
If output shaping already eliminates large responses, close this item. Otherwise compare unchanged
behavior with bounded excerpts at emission for the largest category only: preserve errors, paths,
line references and an accessible complete artifact; never silently discard information.
Replay must include a later question needing omitted details, so the agent has to retrieve them.
Record tool-input tokens, artifact re-reads, failures, cache reuse, compactions and task wall time.
Proposed gate: ≥10% lower paired median task wall time, unchanged task success and no missing
evidence; reject if extra reads/retries erase the gain. Implement at the existing tool/harness
response boundary only after this A/B, not as a new middleware service.

### New T26: preserve request locality without adding slots

**Conditional hypothesis:** an unrelated session or background summary on the single slot can
displace useful state. This is distinct from one session mutating its own prefix.
The pinned omp documentation says async compaction can submit a side-session summarization
before the threshold is reached ([source](https://github.com/can1357/oh-my-pi/blob/v18.4.4/docs/compaction.md)).
Inspect that traffic first, including requests absent from the main-session ledger. Correlation
with a threshold band is a lead, not proof of a cache-miss cause. Capture effective settings and
request IDs; if confirmed, compare async enabled/disabled as its own one-factor arm before
implementing scheduling changes. Count foreground compaction cost too, not just the eliminated
background work. Do not change the running harness to collect this comparison.
Only open an A/B after request IDs show such interleaving. Replay the same two fixed request
streams in alternating order and in bounded session-local groups, retaining order within each
stream, identical arrival conditions and the same total work. Keep `-np 1`.
Measure each stream's queue delay, total completion time, cache misses and recovery prefill.
Include interactive p90 latency: a throughput win that starves the other stream is a loss.
Proposed gate: ≥10% less total wall time with no interactive p90 regression or correctness loss.
If useful, reuse the harness's existing scheduling/concurrency control; no general queue service
and no speculative second GPU/model.

### New T27: profile the MTP verification path before porting kernels

The old ~2x deep-decode estimate is an unmeasured roofline opportunity, not a predicted engine
or task speedup. Instrument one fixed coding replay at 64K, 190K and 240K, recording actual
verification batch sizes, draft/target time, attention/KV conversion time, graph/launch gaps and
peak memory. Pin the profiler version and check its gfx1100 support first. Run a matching
uninstrumented control; tracing overhead must not become the reported benchmark.
If detailed profiling is unavailable, retain end-to-end measurements and label attribution unknown.

The [pinned source check](SOURCES.md#optimization-queue-source-checks-2026-10-03) narrows the
candidate: with four query tokens, GQA 6 and head 256, b11160 uses TILE with four-token/two-head
folding and f16 KV staging. It already shares work across the query tokens. The RDNA4 fork's
comparison against its own narrow tile is not our baseline. Simply forcing MMA is insufficient:
b11160's RDNA MMA selector also chooses two-head folding for GQA 6.

If profiling identifies attention/staging as dominant, test a **shape-gated selector patch on the
pinned baseline**, rather than importing the fork: route the observed small verify shapes to MMA
and select eight-head folding, with all other shapes unchanged. Confirm the required compiled
instances first; this is a proposed implementation, not a validated patch. Separate the routing
change from the fold-width change at op level. Both routes still stage KV as f16, so this does not
promise native mixed-quant memory savings. Require backend-op parity, then ≥8% mean decode gain
at both 190K and 240K beyond repeat variation, no >2% empty-context regression, safe memory
headroom and the coding/retrieval gate. Any fault or NaN stops the trial.

T19's `cc1a791` source read is complete: its 16-line `GGML_HIP_FA_KERNEL` override selects TILE
or shape-gated MMA; it adds no kernel. Treat it as a diagnostic reference, not another speed fork.
T18's trunk fusions remain conditional on non-attention time dominating. For T07, first confirm
graphs are actually used on the observed MTP shapes; profile launch gaps rather than assuming the
graph optimization variable is effective.

For scale, using the [recorded busy-time split](#where-the-time-goes), a 10% faster decode rate
alone saves **5.9% of server busy time**; even 2x decode saves 32.4% (1.48x busy-time speedup).
These are calculated illustrations holding all other work fixed, not measured forecasts or
task-wall savings. Cache, context and kernel gains overlap; do not add their percentages.

### Adoption and rollback

Freeze at least six executable coding tasks before quality-affecting A/Bs: a local bug fix,
cross-file change, tool-error recovery, long-context dependency lookup, post-compaction continuation
and retrieval of an artifact omitted from a bounded tool result. Pin repository commits, prompts,
test commands, tool/harness versions and seeds. Use isolated worktrees and independent task
outcomes; an identical synthetic prompt repeated three times is not three quality samples.

After a candidate passes, repeat a real long agent session, including restart/recovery and the
actual streaming tool-call API. Keep retrieval, KLD and coding scores separate. Preserve failing
runs and publish commands/effective settings per [`BENCHMARK-FORMAT.md`](BENCHMARK-FORMAT.md).
Then update the single adopted profile, engine inventory if needed, STATUS and DECISIONS together.
Retain the prior pinned binary/config outside the active manifest for rollback; restore it on a
quality, reliability or memory regression, and re-run `check-sync.py` and real inference smoke.
No adoption, GPU inference or performance improvement is claimed by this review.

### Status after the 2026-10-03 test session (annotations to this review)

The review was written while a test session was running; these notes correct it against the
code and the results now available. Everything else above stands.

- **T24 is no longer "partial output".** The three-arm screen is published in
  [`20261003-b11371-mtp-draft-sampling/`](../results/20261003-b11371-mtp-draft-sampling/README.md),
  including a 240K temperature-1 run with paired seeds. The depth bench now has `--temperature`
  (commit d529d65; seed 7+rep above 0) with a regression test. Result: not adopted, pending.
- **T07 is done and rejected**: −3.6% to −3.9% at 240K
  ([`20261003-graph-opt-mtp/`](../results/20261003-graph-opt-mtp/README.md)).
- **T26 is P0, not P1-conditional.** All six full cache misses of 2026-10-01 coincide to the minute
  with omp "Speculative compaction armed" events. omp 18.5.0 writes the handoff summary with the
  session model on the same single slot, and `maxInFlightRequests: 1` queues the main agent behind
  it (6-14 min waits), twice per compaction epoch (~172K and ~193K). On 2026-10-03 the operator
  moved compaction summaries to a cloud model (`compactionModel` on the local model,
  `methodOrder: [soft, handoff, shake]`, async at its default); see
  [agent-traffic.md](measurements/agent-traffic.md). Its effect is unmeasured until the next real
  session. A server-side `--cache-ram` test of the side-request eviction is in the session queue.
- **T20 needs `-lv 4`**: in b11160 the checkpoint restore and "forcing full prompt re-processing"
  lines are trace level (`SLT_TRC`), absent at the default verbosity.
- **T27 overlaps T11.** Its selector idea is the rdna-boosts GQA-6 band, which the fork's author
  evaluated on a 7900 XTX (commit `b5278a5`: plain decode −12%, MTP n3 +8.6% at ~42K, decode/verify
  not bit-identical) and which only engages when K and V share a type, so not with `q8_0`/`q5_1`.
  Keep T27 as attribution first: a local `test-backend-ops` FA perf case for this exact shape.
- **n-gram benchmarks need non-repeating prompts.** `ngram-mod`'s pool is shared across requests
  (`common/speculative.cpp:1870`), so repeated identical prompts inflate later reps.

## End-to-end quality and reliability before tuning (2026-10-02, proposed; not run)

**Priority:** preserve the adopted profile until a fixed coding-task suite exists. Retrieval checks
and pooled results establish retrieval only; they do not establish repository-editing quality. The
adopted KV/MTP flags have 40/40 retrieval at 190K/240K, while 68/68 pools multiple configurations; neither
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

## Hypothesis review (2026-10-03, no runs)

A desk review of the optimization hypotheses against the 5.8-hour session audit
([`results/20261001-agent-session-audit/`](../results/20261001-agent-session-audit/README.md),
[`agent-traffic.md`](measurements/agent-traffic.md)). Nothing was run and no setting changed; the
outcome is a re-weighted levers table ([`agent-traffic.md`](measurements/agent-traffic.md#speed-levers-at-depth-2026-09-30))
and three no-GPU diagnostics added to the private test plan (T20-T22).

### Where the time goes

| Component | Time | Share of busy |
|---|---|---|
| Server busy | 19,915 s | 100% |
| Decode | 12,916 s | 65% |
| Uncached prefill | 6,999 s | 35% (10.8% in the 2026-09-28 logs) |
| of which: 6 full cache misses | 2,512 s | 13% |
| of which: 3 post-compaction re-processes | 162 s | <1% |

About 78% of output **characters**, not measured tokens, are thinking. The earlier levers table
under-weighted prefill. These shares describe server busy time, not end-to-end task wall time;
see the [calculated examples](#new-t27-profile-the-mtp-verification-path-before-porting-kernels)
for the nonlinear relation between throughput improvement and time saved.

### Cache-miss hypotheses, ranked, and the no-GPU diagnostic

The six misses have no server log (the server ran in the foreground; `scripts/launch.py` always
writes the log since commit 5b8d31b), so the cause is open. Hypotheses, most to least likely given
the miss pattern (each prompt = previous + ~1K tokens, at ~172K and ~193K under a 75%, ~196K
threshold):

| # | Hypothesis | What it predicts in the log |
|---|---|---|
| a | The harness rewrote a message older than the oldest retained checkpoint | Earliest divergence below every checkpoint position |
| b | Checkpoint coverage: placement includes last-user/near-end exceptions; under pressure, b11160 removes nearby older-task checkpoints before oldest-entry eviction | Divergence mid-context, no retained checkpoint passes the restore checks before the reusable boundary |
| c | **New.** Harness history mutation just below the compaction threshold: harnesses commonly prune or truncate old tool results, or inject reminders, as the context nears the threshold; that rewrites an early position and defeats every checkpoint | Divergence near the start, only on requests close to the threshold |
| d | With `preserve_thinking=false`, old reasoning is stripped before the latest real user query; this can invalidate an early prefix even if some checkpoints remain | Only applicable if reasoning actually reaches the template and this option changes its rendering |

Test hypothesis (c) using captured requests and server logs; compare rendered token prefixes, not
JSON serialization alone. `--checkpoint-min-step` is verified in b11160 `--help` and belongs to
the conditional T23 experiment. The [trace protocol](#p0-one-prefix-trace-then-a-conditional-checkpoint-experiment)
also checks intervening requests rather than forcing every miss into a prefix-mutation category.

**Diagnostic (test-plan T20, no GPU):** from the next session's `_tmp/logs/` server log, extract
per request `n_prompt`, cache-hit tokens, `f_sim_best`, `f_keep`, the checkpoint list and the earliest
divergent position; classify only when the trace supports a cause, otherwise retain "unknown".
A small stdlib parser is justified once the log format is confirmed.

### Context growth: `preserve_thinking` (new, highest potential, unmeasured)

Template fact (GGUF `tokenizer.chat_template`): past assistant reasoning is kept unless
`preserve_thinking` is false, and only turns before the last real user query are stripped.
`--chat-template-kwargs '{"preserve_thinking": false}'` exists in b11160 (verified in `--help`).
**Review correction:** "highest potential" was a hypothesis, not a measured ranking. The observed
78% character share cannot establish thinking tokens per turn, their retention in the next request,
or their contribution relative to tool output. Measure those separately before estimating savings.

Unknowns to settle first, no GPU:

1. Does the actual harness send historical reasoning back? Inspect outgoing `reasoning_content`
   and embedded thinking blocks, then the rendered prompt. Ledger deltas are a screening signal
   only: new tool results, template boundaries and compaction confound them.
2. The official card was rechecked: it explicitly ties preserved reasoning to agent consistency,
   reduced redundant reasoning and KV reuse ([SOURCES.md](SOURCES.md#context-length-and-compaction-claims-reviewed-2026-09-30)).
   Keep the default unless a quality-gated trial justifies a change.

Possible trade: fewer retained tokens and shallower depth, but prefix reprocessing and extra
reasoning/retries may offset any saving. Quality across user queries can regress. T21 starts with
the [request trace](#p0-one-prefix-trace-then-a-conditional-checkpoint-experiment), not an assumed
840-token saving or an automatic template change.

### Reasoning budget (T04): gate corrected

Retrieval probes need little thinking, so an exact-match retrieval benchmark cannot detect harm from
a truncated budget on coding tasks; it can only measure token savings. T04 is conditional on the
existing rule's observed empty `content` with `finish_reason: length`, not a proactive speed sweep.
If triggered, record completion tokens, stop reason and task outcomes; adoption still needs the
coding suite. The budget does not change the `medium` system block, while changing effort can
change the rendered prefix. Do not infer next-turn cache reuse from the flag alone.

### Decode at depth: ceiling and MTP on code

The [depth analysis](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4)
estimates ~24% of peak bandwidth and a possible ~2x deep-decode ceiling. This is a roofline
hypothesis, not a measured kernel speedup or proof that the MTP verify path has the same limit.
T27 now gates additional kernel work; T11 is not automatically the only worthwhile build.

Code tasks decode slowest (18.6 vs. 24.4/26.9 tok/s at 240K, [STATUS.md](STATUS.md#headline-numbers))
and at 190K with n=2 code accepted 215/365 (59%) vs. copy 261/275 (95%)
([speculative.md](measurements/speculative.md#ab-at-190k--c-204800-kv-q8q8-kvmix-vs-vec4-mtp-n2)).
Two levers follow: n-gram-map-k stacking (T08/T09) targets exactly the repeated-code case; and
`--spec-draft-p-min` raises acceptance without speed, because an MTP step costs ~117 ms at 240K
regardless of acceptance, so ms/token is the metric, not acceptance. Sampling temperature is a known
acceptance factor that the card rule forbids changing.

### Levers table

Owner: [`agent-traffic.md`](measurements/agent-traffic.md#speed-levers-at-depth-2026-09-30)
(rewritten 2026-10-03 with the shares above; replaces the 2026-09-30 table).

### Questioned and parked (no test)

- 224K `q8_0/q8_0` + 80% threshold vs. 262K `q8_0/q5_1` + 70%: same effective working context
  (~180K) with lower KV KLD ([kv-quality.md](measurements/kv-quality.md)), but 0.3 GiB margin at 240K
  ([depth.md](measurements/depth.md#context-window-ladder-224k-and-240k-272-w-2026-09-25)) and the provider contract is fixed at 262144; not worth a run while both KV mixes are near-lossless.
- `-ub 512` (+5% prefill, +350 MiB): the session peak left 724 MiB free, so no.
- Presence penalty (T03): observed repetition is low; demoted to "run only if loops are observed".
- T07 as a gate for T08-T12: dependency dropped; the adopted profile is the control regardless of
  T07's outcome.

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

**Outcome: candidate = budget 28,672 + `--kvmem-block-tokens 32`; meets 3 of 4 go/no-go criteria, agent run (T6) outstanding, not adopted.** Moved to [`measurements/kvmem.md`](measurements/kvmem.md#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted).

## KVMem trial (round 1 run 2026-09-30, not adopted)

Round 1: tg 40-49 tok/s at 244K vs. 20.8 baseline; budget 49,152 crashed. Moved to [`measurements/kvmem.md`](measurements/kvmem.md#kvmem-trial-round-1-run-2026-09-30-not-adopted).

## Candidates from third-party repositories (2026-10-02, not run)

Source rows and verdicts: [`SOURCES.md`](SOURCES.md#third-party-tuning-repositories-reviewed-2026-10-02).
Nothing here is adopted.

| Candidate | Variable | Why it might matter | Kill criterion |
|---|---|---|---|
| `GGML_CUDA_GRAPH_OPT=1` (env var, exists in b11160, off by default) | Environment only, same binary and flags | Enables graph optimization with concurrent streams when HIP graphs are in use; reported +1.4% tg, +1.0% pp at empty context without MTP (dense model) | Under ~2% tg at 190K/240K with MTP n=3, or any output change at greedy, or a VRAM increase |
| `--spec-type draft-mtp,ngram-map-k` on a replayed multi-turn session | Spec type only | A turboquant-fork build reported -17.4% session wall time that a single-request benchmark cannot see; folds into the prepared n-gram A/B in [`speculative.md`](measurements/speculative.md#n-gram-stacked-on-mtp-how-llamacpp-combines-them-source-reading-2026-09-29) | No wall-time gain across turns, or runaway repetition |
| `-DGGML_LTO=ON` build | Build flag only | Asserted "+5-15%" with an empty A/B table; low prior because decode is memory-bound | Under ~2% tg or pp, or a longer build for no gain |
| `GGML_CUDA_DISABLE_GRAPHS=1` | Environment only | Diagnostic for a HIP-graph exec-update hang reported by a third party; not a speed candidate | Run only if a hang appears; never proactively |
| cafe-llama.cpp fork build (`a0d43f3`, upstream base `f1cee99`), single-backend HIP | Engine build; then `--spec-draft-n-max` 3/4/6 | Hybrid-GDN trunk fusions (`src/models/qwen35.cpp`) may cut the target pass at depth; the author claims cheaper MTP on an RTX 3090, but no draft-cost change for Qwen3.8 was found in the code ([`SOURCES.md`](SOURCES.md#cafe-llamacpp-fork-and-the-quimedesu-x-thread-2026-10-02)); never run on AMD | Under ~5% tg at 190K/240K vs. b11160 `hip-kvmix` n=3, any output change at greedy, a build failure on gfx1100, or a missing `kvmix` FA-quants kernel (the fork is a 275-file diff, not a patch to maintain) |

Not carried here: `--reasoning-budget` (profile-level, see the [hypothesis review](#hypothesis-review-2026-10-03-no-runs)), undervolt (deferred GPU
care) and the fork-only `turbo4`/`turbo2` V caches (not in our engine).

## Upstream watchlist (2026-09-29)

**Keep b11160 pinned: no replacement has been measured on this setup.** The official
[llama.cpp v0.5.0 release](https://github.com/ggml-org/llama.cpp/releases/tag/v0.5.0) lists nightly
b11146, older than this repository's b11160 baseline; its official ROCm binary also lacks the
`q8_0`/`q5_1` FlashAttention kernel required by the current profile. The upstream items below are
monitoring candidates, not evidence to upgrade.

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
