# Engine experiments and watchlist

Live plan, open trials and upstream items being monitored. Nothing here is adopted; the builds actually in
use, with pinned versions and SHA256, are in [`ENGINES.md`](ENGINES.md), and tried-and-not-adopted results are
in [`TRIED.md`](TRIED.md). Proposed experiments below are not local results unless explicitly marked as run.
Finished, superseded or rejected write-ups (PR #29509 trial, the 2026-10-03 queue, the quality plan, the
hypothesis review, fork vs. upstream, dated version checks) are in
[`archive/engines-experiments-2026.md`](archive/engines-experiments-2026.md); headings below that point there
keep older links working.

## Current plan (2026-10-18)

Replaces the [2026-10-03 queue](archive/engines-experiments-2026.md#queue-reconciliation-and-priority) as the
execution order. Context: b11820 + native `q8_0`/`q5_1` TILE FlashAttention is the `hip-kvmix` engine in use (D1, 2026-10-23), Qwen3.8-27B tuning is
paused until Qwen4 ([DECISIONS.md](DECISIONS.md)), Strata's coding quality is unmeasured, and the coding suite
(B1) has one seed-1 baseline on the 27B; every quality-affecting A/B gates on it.

**Rules for every step.** A failed gate stops that step's line, not the plan. Results go to
`results/YYYYMMDD-topic/` plus one row in `results/INDEX.md` ([STYLE.md](STYLE.md) §8). Before any
GPU run: 272 W cap active, no GPU-heavy apps, run under `systemd-inhibit` as each bench's `--help`
shows, `BENCH_EXPECT_POWER_CAP_W=272`; one engine on `:8080` at a time. Engine paths come from
`local.toml` `[engines]`, never hard-coded. New trial IDs: check the private queue for collisions
first (T28 was already taken). Publishing a release, pushing, or editing the GitHub About needs the
user's explicit go each time.

| Step | Action | Depends on | Check | Done when / rollback |
|---|---|---|---|---|
| A1 | Engine b11718 vs. b11454 + #29509, 240K pair only. Future engine updates repeat this pair ([sop/update-engine.md](sop/update-engine.md)) | user go | Greedy text hash equal or the difference explained; tg per task | **Done 2026-10-18**: b11718 kept (prefill +1.9%, tg +1.2% / +2.5%, code -8.2% on a different greedy text), [results](../results/20261018-engine-b11718-vs-b11454-240k/README.md). Rollback: the b11454 + PR #29509 build |
| A2 | Next real agent session: `python3 scripts/cache_misses.py` on the newest `_tmp/logs/` log | a real session | Per-request reuse table | No in-flight wait > 60 s and no full miss outside compaction; one dated entry in [agent-traffic.md](measurements/agent-traffic.md) and the STATUS open question closed or kept |
| B1a | Coding suite design | — | User review | **Done 2026-10-18**: [design](#coding-suite-design-b1a-2026-10-18); gate rules in [DECISIONS.md](DECISIONS.md) (2026-10-18); the coding harness itself stays out of scope ([SOURCES](SOURCES.md#agent-harness--api-compatibility-context-only)) |
| B1b | `bench/coding_suite.py` runner + `bench/coding_suite_tasks/` | B1a | `python3 -m unittest discover -s tests`, `python3 scripts/check-repo.py` | **Done 2026-10-18**: 23 unit tests, `--verify-fixtures` and `--smoke` 6/6 without a server |
| B1c | Seed-1 baseline of the six tasks on the 27B | B1b | Pass/fail per task | **Cut to one seed-1 run 2026-10-18** at the user's request: [results](../results/20261018-coding-suite-baseline-27b/README.md). Found and fixed the whole-file-write limit (suite v2, `edit_file`); flakiness and ceiling unmeasured |
| B2 | Baseline the suite on the 27B default profile and on the Strata Coder (`local-flash-262k`, [sop/strata.md](sop/strata.md)), stopping one engine before starting the other | A1 or its "not approved" path; B1c | Pass rate per task per engine | One result folder; README "Models" row for Strata updated; STATUS open question on Strata quality closed |
| C1 | Qwen4 day one, via [sop/new-model.md](sop/new-model.md): vendor card first, quant that fits 262K with quantized KV, KV KLD vs. `f16`, depth bench, retrieval, suite. If the current engine lacks support, run the engine update first and treat it like A1 | Qwen4 release; B1c | Same measurements as the 27B rows | Adopt only if suite pass rate ≥ the 27B's with no task lost, 262K kept, and 240K tg ≥ 19.3 tok/s (the 27B's slowest 240K task); update `models.toml`, STATUS, README, DECISIONS together; keep the 27B profile for rollback. Record head dim, GQA and MTP verify width for D1 |
| C2 | Strata [tuning plan](models/strata-qwen-flash-next.md#tuning-plan-2026-10-16-not-run) | B2 | Its own per-phase metrics plus the suite | One factor at a time; the suite must not regress |
| D1 | [T29](#new-t29-native-quantized-kv-multi-query-verify-kernel-2026-10-18-not-started) verify kernel; start with its [cheaper route](#cheaper-route-via-llamacpp-pr-30792-2026-10-22) (PR #30792 + q5_1 V loader + `ne[1] <= 8` guard), write the full kernel only if that falls short | A1 path settled; C1 shows the adopted model keeps quantized KV with an attention shape T29 covers, or the user keeps the 27B | T29's op-level and end-to-end gates | **Done 2026-10-23**: 240K tg +18-27% vs. plain b11820, identical greedy text, suite 6/6; adopted ([results](../results/20261023-d1-pr30792q51-240k/README.md)). The full T29 kernel is not needed for now. Rollback: b11718 |
| D2 | Workload items one at a time: T25 tool-output bounding, T02 compaction threshold, T24 probabilistic MTP (needs a non-greedy bench), T09 n-gram replay | B1c | The suite plus the item's own metric | Each needs its own result folder and DECISIONS row |
| Parked | T26, T23, T07, T10-T18, KVMem (T01), TurboQuant KV ([SOURCES](SOURCES.md#tinygrad-qwen38-fork-verify-kernel-references-and-turboquant-kv-2026-10-18)) | new evidence | — | Revisit only with a logged trigger or a measured bottleneck |

Order of work now: A1, B1 and D1 are done; Strata is installed again (2026-10-24, [sop/strata.md](sop/strata.md)):
next C2's F2 (A/B/C, no numbers yet), then B2.
A2 whenever a real session happens. C1 pre-empts everything except a running measurement once Qwen4
ships. [Next batch](#next-batch-2026-10-23) lists the GPU runs that remain worth doing before then.

### Next batch (2026-10-23)

Ordered by expected gain per GPU hour on the current engine. Each is one `bench/spec_depth_bench.py` or
`llama-bench` run with the production flags plus one change, compared with a reference arm **in the same
session** (cross-session spread reaches ~6%: [results](../results/20261024-engine-b11846-240k/README.md)).

| ID | Change | Why now | Gate |
|---|---|---|---|
| E5 | Upstream rebase when PR #30792 merges | Drop the local patch if upstream covers `q5_1` V | 240K pair per [sop/update-engine.md](sop/update-engine.md) |

Done in this batch: MTP n=4 re-check, n=3 stays ([results](../results/20261023-mtp-n4-240k-pr30792q51/README.md));
E2 KV `q8_0`/`q8_0` at 245,760: no faster than `q8_0`/`q5_1` on a same-session rerun, +591 MiB VRAM and 16K
less context; a quality-only ≤240K alternative, not adopted ([results](../results/20261024-kv-q8q8-240k-pr30792q51/README.md)); E3 empty context:
MTP n=3 76.3 tok/s, spec off 39.1 ([results](../results/20261024-probe-ab-262k-pr30792q51/README.md)); engine rebased to
b11846, neutral, adopted ([results](../results/20261024-engine-b11846-240k/README.md)); E4 probabilistic drafts at
240K, temperature 1: code +9.9%, copy -10.3%, essay +0.2%, undecided with 3 samples, not adopted; next is the
T24 session replay ([results](../results/20261024-e4-mtp-prob-240k/README.md)).

## Coding suite design (B1a, 2026-10-18)

**Status:** implemented (B1b: [`bench/coding_suite.py`](../bench/coding_suite.py), usage in
[`bench/README.md`](../bench/README.md)); run once, seed 1 on the 27B
([results](../results/20261018-coding-suite-baseline-27b/README.md)). The gate policy is in
[DECISIONS.md](DECISIONS.md) (2026-10-18).

Each task is a pinned release of a pure-Python repository whose own tests run on stdlib `unittest` with no install
step. A stored small mutation injects a bug (CS6 instead asks for a new error message); the model fixes it with three
tools in a throwaway `git worktree`. Injected bugs are new code, so the fix is not in any training set; replaying real
upstream fixes was rejected because those fixes are public and older than the models.

| ID | Category | Repo @ commit (tag) | Injected change | Test command | Timeout |
|---|---|---|---|---|---|
| CS1 | local bug fix | [hukkin/tomli](https://github.com/hukkin/tomli) @ `a2a578949199336ebc3884eeba4aede87da41ef2` (2.5.0) | `_parser.py`: `\U` escapes read 4 hex digits instead of 8 | `PYTHONPATH=src python3 -m unittest -q` | 1,200 s |
| CS2 | cross-file change | [more-itertools](https://github.com/more-itertools/more-itertools) @ `4aeb4338ae1407d8da9723e86da99efeb446f719` (v11.2.1) | `iequals` removed from `more.py`, `more.pyi` and `docs/api.rst`; the prompt specifies it | `python3 -m unittest discover -s tests -q` + a hidden structural test (stub, docs, `__all__`) | 1,200 s |
| CS3 | tool-error recovery | [bottlepy/bottle](https://github.com/bottlepy/bottle) @ `b0a0a1014f7a7e6f6b7c193886a0913f46ee3ee6` (0.13.4) | `parse_range_header` off by one; the 1st `write_file` and the 1st `run_tests` return injected errors | `python3 -m unittest discover -s test -t . -q` | 1,200 s |
| CS4 | long-context dependency lookup | [Python-Markdown](https://github.com/Python-Markdown/markdown) @ `2258b48e551d0df7b149ea9c33969bea7c7a0a2b` (3.11.1) | `util.code_escape` stops escaping `&`; the symptom is reported for code spans and blocks | `python3 -m unittest discover -s tests -t . -q` | 3,600 s |
| CS5 | post-compaction continuation | bottle, same commit | `html_escape` stops escaping `'`; the only description is in a fixed compaction summary, then "Continue." | as CS3 | 1,200 s |
| CS6 | artifact omitted from a bounded tool result | tomli, same commit | none; a hidden test outside the worktree expects a new duplicate-table message, visible only in the full log that the truncated `run_tests` result points to | as CS1, then the hidden test | 1,200 s |

- **Tools**: `read_file`, `write_file`, `edit_file` (one exact, unique replacement), `run_tests` (the visible command,
  last 4,000 characters; CS6 shows 3 lines). `edit_file` came in suite version 2 (B1c, 2026-10-18): with whole-file
  writes only, CS2 (`more.py`, ~4,900 lines) and CS3 (`bottle.py`, ~4,500 lines) hit `max_tokens` while rewriting
  the file (5/5 episodes `length`), a limit failure, not a quality one. CS3's injected write error hits the first
  write of either kind.
  Limits: 40 assistant turns, `max_tokens` 32768. Harness wiring is out of scope; the runner is its own client of
  `/v1/chat/completions` with streaming tool calls, attached to the engine already serving `:8080`.
- **Scoring**: restore the test folder from the pinned commit (edited tests cannot pass), add hidden tests, run the
  command on the final worktree, always. Two columns: `tests` (exit 0, the quality outcome) and `completed` (final
  message inside the timeout and turn limit); pass = both. Speed A/Bs compare the columns separately.
- **Sampling**: the alias's `models.toml` sampling table sent per request (27B: temperature 1.0, top_p 0.95, top_k
  20, min_p 0.0), seed 1 by default, one fresh worktree per task and seed. The run records any control the server
  ignores.
- **Regression rule** (screening, not proof of equivalence; seed-1 default since 2026-10-18, to keep an engine update
  to one ~1 h run): per task against the baseline arm, a seed-1 loss (baseline passes, candidate fails) reruns that
  task with seeds 2-3 on both arms; on seeds 1-3 a `tests` drop of 2 or more is a regression, a drop of 1 reruns seeds
  4-6 on both arms, where a drop of 2 or more of 6 is a regression. Any regression rejects the arm.
- **CS4 depth**: real files, `util.py` first so the cause is at the earliest position and farthest from the symptom,
  then the rest of the package, tests and docs, until the initial request would pass 120,000 tokens (Qwen3.8-27B
  tokenizer). The file list is then frozen, so every model gets the same bytes and reports its own token count. 128K
  sits in the middle of real sessions, which compact at ~157-183K and resume at 46K-67K
  ([agent-traffic.md](measurements/agent-traffic.md)). A frozen **CS4-deep** variant (180,000 tokens) runs only
  for A/Bs that target depth and is reported outside the standard score. The depth benches already cover 240K.

**Fixture check** (Python 3.14.8, no model): each commit resolved from its release tag in a fresh clone; for all six
tasks the visible tests exit 0 on the pinned commit, exit 1 with the bug and exit 0 with the reference fix. Baseline
suites: tomli 18 tests, more-itertools 930, Python-Markdown 1,126, bottle 377 (needs `-t .`), each under 10 s.

**Rejected**: [tool-eval-bench](SOURCES.md#awesome-local-ai-catalog-2026-10-10) (mock tools only, four
third-party packages); kjd/idna (its suite needs `hypothesis`); a 190K or 240K default depth, and 150K (too close to a
60% compaction threshold).

**Limits and open items**: one seed per task catches only large regressions and a task the baseline fails gives no
signal; flakiness and the ceiling risk were not measured (B1c cut); the 120,000-token cutoff is measured in B1b;
whether Strata honours `seed` is unverified; CS5
uses a fixed summary, so it tests continuation, not the harness's compaction quality.

## llama.cpp PR #29509 local trial (2026-10-04)

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#llamacpp-pr-29509-local-trial-2026-10-04).

## Executable optimization queue review (2026-10-03, not run)

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#executable-optimization-queue-review-2026-10-03-not-run). T25, T29 and the adoption rules stay open below.

### Queue reconciliation and priority

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#queue-reconciliation-and-priority).

### P0: make the measurements answer the intended question

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#p0-make-the-measurements-answer-the-intended-question).

### P0: one prefix trace, then a conditional checkpoint experiment

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#p0-one-prefix-trace-then-a-conditional-checkpoint-experiment).

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

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#new-t26-preserve-request-locality-without-adding-slots).

### New T27: profile the MTP verification path before porting kernels

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#new-t27-profile-the-mtp-verification-path-before-porting-kernels).

### New T29: native quantized-KV multi-query verify kernel (2026-10-18, not started)

**Why.** T27's attribution already answered "is attention dominant": FA is ~55% of a 240K MTP step
([results](../results/20261003-fa-attribution-qwen38-shape/README.md)). llama.cpp master still sends
our 4-token verify with `q8_0`/`q5_1` KV to TILE, which first converts the whole K/V view to f16;
that path costs 4,574 µs per op at 240K vs. 2,559 µs with f16 KV, and moves only ~10% of nominal
bandwidth. Widening the VEC gate is not the shortcut (#29935: -19 to -22% at batch 4). Evidence and
references: [SOURCES.md](SOURCES.md#tinygrad-qwen38-fork-verify-kernel-references-and-turboquant-kv-2026-10-18).

**Design to port, not code to import.** The tinygrad-qwen38 fork's `AMD_ATTN_MQ` path is the
closest working gfx1100 reference for our exact shape (D 256, GQA up to 8, up to 8 query tokens):

1. One work-group per (KV head, 256-position chunk); all `n_tokens x 6` query rows of that KV head
   share each 16-position KV tile, so K/V are read once per verify step, natively quantized.
2. QK with `v_wmma_i32_16x16x16_iu8`: Q quantized to int8 per row (llama.cpp VEC already uses a
   `q8_1` Q for quantized K), `q8_0` K used as stored, the per-32 K scale applied per pair of WMMA
   steps. PV with `v_wmma_f32_16x16x16_f16` after dequantizing `q5_1` V into LDS.
3. Split-K partials (m, l, unnormalized O) per chunk, then one merge kernel (flash decoding).
   Cross-check the merge against vLLM's Triton unified attention split-K and Vulkan #30190.

Skip the fork's KV format (4-bit codebook + QJL): it changes quality, which this trial must not.

**Steps and gates.**

1. Re-run the T27 `test-backend-ops` perf case on the adopted b11718 `hip-kvmix` build to confirm
   the dispatch and the 240K numbers did not move.
2. Write the kernel in `ggml/src/ggml-cuda/` as a new FA path gated to HIP RDNA3, D 256, quantized
   `q8_0`/`q5_1`, `3 <= ne[1] <= 8`; every other shape unchanged. Keep it a local patch on the
   pinned build, recorded in [`ENGINES.md`](ENGINES.md).
3. Op level: `test-backend-ops` FLASH_ATTN_EXT correctness for the new cases (NMSE within the
   existing TILE tolerance), then µs per op at 32K/131K/196K/240K and nb 3/4. First bar: at or below
   the f16 TILE time (2,559 µs at 240K, ~+30% decode upper bound); a bandwidth-bound kernel would go
   further (~0.6 ms per op for ~445 MiB at ~770 GB/s; calculated, not a forecast).
4. End to end: the T27 gate (≥8% mean decode at 190K and 240K beyond repeat variation, no >2%
   empty-context regression, memory headroom), plus KLD vs. the current build because int8 Q changes
   numerics, plus the retrieval/coding gate. Any fault or NaN stops the trial.

Precondition: Qwen3.8-27B tuning is paused until Qwen4 ships ([DECISIONS.md](DECISIONS.md)); the
kernel is shape-specific (D 256, GQA 6), so recheck Qwen4's attention shape before starting.

#### Cheaper route via llama.cpp PR #30792 (2026-10-22)

Try this before writing the kernel above. Source, read 2026-10-22 (PR text, diff and comments):
[#30792](https://github.com/ggml-org/llama.cpp/pull/30792) "CUDA: native q8_0 KV (and f16 K / q8_0 V) in the
flash-attn tile kernel" is **open and not merged** (updated 2026-10-22; one reviewer question about overlap with
#30202, no approval).

- **What it does.** TILE loads `q8_0` K/V blocks raw and dequantizes them to `half2` in registers during the
  global-to-shared copy (`flash_attn_tile_load_tile_q8_0`); the shared layout is the f16 one, so the math is
  unchanged, and `ggml_cuda_flash_attn_ext_get_alloc_size()` stops requesting the f16 scratch. That scratch
  conversion is the cost T29 measured. The selector keeps VEC for `ne[1] <= 2` unless the types are native and
  `gqa_opt_applies`.
- **Why it does nothing for us as is.** Native means K and V both `q8_0`, or f16 K with `q8_0` V (K also needs
  `ne[0] % 64 == 0`). The adopted pair is K `q8_0` with V `q5_1`, so it still stages both as f16. The native
  decision is by type only, so every `ne[1]` that reaches TILE takes it, prefill included; a commenter measured
  -77.5% prefill on gemma-4 26B-A4B (256/512-head attention) with native V in prefill, and none when native V was
  limited to decode.
- **Author numbers (not ours).** gfx1151 (RDNA3.5 iGPU), a 35B-A3B MoE at Q4_K_M, no MTP: tg +19.0% at 16K
  and +61.9% at 63K with `q8_0`/`q8_0`, f16 control within ±0.2%, `test-backend-ops -o FLASH_ATTN_EXT`
  3998/3998. Nothing is measured on gfx1100, the 27B, 240K or MTP verify.

Extension, a local patch on b11820 (written and op-level validated 2026-10-22,
[results](../results/20261022-fa-native-q8q51-tile-op-level/README.md)):

1. A `q5_1` V loader (same register dequantization to the shared f16 layout) and a native rule for K `q8_0`
   + V `q5_1`, mirrored in `get_alloc_size()` (the PR's own comment requires both places to agree).
2. An `ne[1] <= 8` guard on the native decision in both places: MTP verify (3-4 tokens) takes the native
   loader, larger batches keep the f16-staged path.
3. Gates are T29's steps 1, 3 and 4: dispatch re-check, `FLASH_ATTN_EXT` cases for K `q8_0` / V `q5_1` at
   `ne[1]` 3, 4 and 9 (the last must not change), µs per op at 240K against 4,574 µs now and 2,559 µs for f16 KV,
   then the end-to-end gate. Hypothesis to check by parity: the loader yields the same f16 values as the
   current staging, so KLD should not move; still measure it.

**Op-level outcome (2026-10-22).** Steps 1-3 done: 30/30 `FLASH_ATTN_EXT` cases OK (n_q 1-4, 8, 9, 64), and at
240K the verify op (n_q 4) drops from 4,550 to 3,244 µs (-29%), n_q 1 from 3,986 to 1,625 µs (-59%), f16
control unchanged. 3,244 µs misses the f16 TILE bar (2,559 µs), so the gain ceiling is ~15% end-to-end at
240K (calculated). Next: the end-to-end 240K A/B against plain b11820; the full kernel above only if a
measured gap remains worth it.

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

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#status-after-the-2026-10-03-test-session-annotations-to-this-review).

## End-to-end quality and reliability before tuning (2026-10-02, proposed; not run)

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#end-to-end-quality-and-reliability-before-tuning-2026-10-02-proposed-not-run).

## Hypothesis review (2026-10-03, no runs)

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#hypothesis-review-2026-10-03-no-runs).

## Fork vs. wait for upstream, and the rdna-boosts GQA-6 FA band (2026-10-01, candidate, not run)

Archived: [archive/engines-experiments-2026.md](archive/engines-experiments-2026.md#fork-vs-wait-for-upstream-and-the-rdna-boosts-gqa-6-fa-band-2026-10-01-candidate-not-run).

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
| `-DGGML_LTO=ON` build | Build flag only | Asserted "+5-15%" with an empty A/B table; low prior because decode is memory-bound | Under ~2% tg or pp, or a longer build for no gain. **Killed 2026-10-06**: within ±0.6%, HIP library byte-identical ([results](../results/20261006-t12-lto-b11454/README.md)) |
| `GGML_CUDA_DISABLE_GRAPHS=1` | Environment only | Diagnostic for a HIP-graph exec-update hang reported by a third party; not a speed candidate | Run only if a hang appears; never proactively |
| cafe-llama.cpp fork build (`a0d43f3`, upstream base `f1cee99`), single-backend HIP | Engine build; then `--spec-draft-n-max` 3/4/6 | Hybrid-GDN trunk fusions (`src/models/qwen35.cpp`) may cut the target pass at depth; the author claims cheaper MTP on an RTX 3090, but no draft-cost change for Qwen3.8 was found in the code ([`SOURCES.md`](SOURCES.md#cafe-llamacpp-fork-and-the-quimedesu-x-thread-2026-10-02)); never run on AMD | Under ~5% tg at 190K/240K vs. b11160 `hip-kvmix` n=3, any output change at greedy, a build failure on gfx1100, or a missing `kvmix` FA-quants kernel (the fork is a 275-file diff, not a patch to maintain) |

Not carried here: `--reasoning-budget` (profile-level, see the [hypothesis review](archive/engines-experiments-2026.md#hypothesis-review-2026-10-03-no-runs)), undervolt (deferred GPU
care) and the fork-only `turbo4`/`turbo2` V caches (not in our engine).

## Upstream watchlist (2026-09-29)

Upstream items to re-check at each engine update ([`sop/update-engine.md`](sop/update-engine.md)); the pinned build
is in [`ENGINES.md`](ENGINES.md). Dated per-update checks and the 2026-09-29 pin note moved to the
[archive](archive/engines-experiments-2026.md#upstream-watchlist-2026-09-29).

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
