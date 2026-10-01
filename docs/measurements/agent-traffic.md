# Real coding-agent traffic

What the adopted profile (`qwen38-iq3s-mtp` / `262k-q8q51-mtp`) actually spends its time on when a
coding-agent harness drives it, as opposed to the synthetic depth and speculative benchmarks in the
other measurement docs. Log and session analysis only: no new GPU run.

## Current conclusion (2026-10-01)

- **Long sessions lose prefill time to full cache misses** (2026-10-01, 5.8-hour session at the
  75% threshold): prefill was 35% of server busy time, not the 10.8% of the 2026-09-28 logs. Six
  requests at ~172K and ~193K depth reused 0 cached tokens with no compaction before them and
  re-processed the whole context (381-456 s each, 42 min in total). Cause open — see "Full cache
  misses in a long session" below. Decode speed and MTP acceptance (0.66) match earlier data.
- **Reasoning dominates generated output**: ~78% of output characters are thinking at
  `--reasoning-effort medium` (1,301 agent turns). Mean output is ~1,080 tokens per turn, p90
  2,744. `--reasoning-effort low` would be the largest speed lever, but it is **not pursued**:
  quality has priority over speed for this workload (see `docs/DECISIONS.md`, 2026-09-30).
- **MTP acceptance with real agent traffic at temperature 1.0: 0.66** (186,582 drafted tokens),
  vs. 0.71 on the synthetic temperature-0 depth benchmark at 240K fill. This answers the open
  question in `docs/STATUS.md`; the gap is small and does not change the n=3 choice.
- **Tool-call loops are rare**: 2.6% of 1,551 tool calls exactly repeat an earlier call in the same
  session (same tool, same arguments), and most of those are legitimate polling of a
  state-machine CLI. Only 1 back-to-back identical call. The longest turns are long but
  **non-repetitive** reasoning (e.g. 484 of 502 thinking lines unique in a 21,022-token turn), so
  the data shows over-long reasoning, not degenerate loops. One turn hit the harness's
  `max_tokens` (32,768) with nothing usable stored; the cause can't be recovered from the session
  file.
- **The harness's base prompt is ~14.5K tokens, down from ~32K**: the ~32K figure in
  [`memory.md`](memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29) came from the
  harness version in use until 2026-09-29. After the harness update (omp v18.4.4) the first request
  of a session is ~14.5K tokens, so the known checkpoint-miss cost drops from ~42 s to roughly
  ~19 s (estimated at the ~770 tok/s cold prefill rate, not measured).
- **Compaction is a full re-process on this hybrid model**: each of the 14 measured compactions
  cost a median ~83 s before the next turn could start, plus the summary's own generation. See
  "Compaction cost on this hybrid model" below.
- **No server config change.** Three A/B tests remain open: compaction threshold, compaction
  method order and presence penalty (see "Open A/B tests" below).

## Data and method

- **Server logs**: the two `scripts/launch.py --background` logs of 2026-09-28 (b11160
  `hip-kvmix`, exact adopted profile flags, `--reasoning-effort medium`). Parsed from the server's
  own `print_timing` lines: `prompt eval time`, `eval time` and `draft acceptance`.
- **Harness session files**: 31 sessions of one coding-agent harness (omp), 2026-09-25 to
  2026-09-30, keeping only the 1,301 assistant turns served by the local profile. Per turn: depth
  (`usage.input + usage.cacheRead`), output tokens, content blocks (thinking / text / tool call)
  and stop reason. The sessions mix a main agent and subagents, on one user's workload (a video
  editing pipeline plus general coding).
- **Base prompt**: the harness's first request was captured by pointing an isolated copy of its
  configuration at a dump-only HTTP stub on another port (no model loaded), then counted with the
  harness's embedded Qwen 3.5+ tokenizer (`omp toks`). The request carries no sampling parameters
  (only `max_tokens` and `chat_template_kwargs.enable_thinking`), so the server's `--temp`/`--top-p`
  and any penalty flags are what actually apply.

### Server time split (2026-09-28 logs)

| Log | Requests | Prefill | Generation | Gen tok/s | Prefill share | MTP acceptance | Max context |
|---|---:|---:|---:|---:|---:|---:|---:|
| Morning | 73 | 218 s / 99,237 tok | 2,006 s / 78,146 tok | 39.0 | 9.8% | 0.668 | 148,837 |
| Afternoon | 228 | 334 s / 147,812 tok | 2,541 s / 107,181 tok | 42.2 | 11.6% | 0.655 | 116,743 |
| **Total** | **301** | **552 s** | **4,547 s** | | **10.8%** | **0.660** | |

### Harness base prompt (first request of a session, Qwen tokenizer)

| Part | Tokens |
|---|---:|
| System prompt | 7,818 |
| Tool schemas (12 tools) | 5,501 |
| Injected context (skill bootstrap, date/cwd reminder) | 1,182 |
| **Total** | **~14,500** |

The same capture from a different project directory gave ~13,900 tokens. Before the harness update
the server logs show 32,076 and 32,137 tokens for the same first request.

### Agent turns by depth (31 sessions)

Wall tok/s = output tokens / turn duration, so it includes time to first token (prefill and any
cold re-process); it is lower than the server's pure generation rate.

| Depth | Turns | Mean output tokens | Thinking share (chars) | Wall tok/s |
|---|---:|---:|---:|---:|
| 0-32K | 156 | 1,250 | 87% | 24.1 |
| 32-64K | 280 | 1,034 | 78% | 31.9 |
| 64-96K | 342 | 1,047 | 74% | 34.4 |
| 96-128K | 330 | 1,044 | 81% | 29.2 |
| 128-160K | 192 | 1,087 | 73% | 19.1 |
| 160-192K | 1 | 7,416 | 91% | 23.6 |

- 1,301 turns, 1.40M output tokens; output characters are 78% thinking, 19% tool-call arguments,
  3% visible text.
- Stop reasons: 1,227 tool use, 25 stop, 44 error, 4 aborted, 1 length. All 44 errors are the
  harness failing to connect (server not up yet), not model failures.
- 14 compactions across these sessions; deepest turn 169,482 tokens.
- Wall tok/s falls from ~34 at 64-96K to ~19 at 128-160K, consistent with the decode slowdown with
  depth in [`depth.md`](depth.md).

## Limitations

- Thinking share is measured in characters, not tokens (the ratio is close, since both are
  English-dominated text).
- A "repeat" is an exact match on tool name and arguments; a loop that varies its arguments
  slightly is not counted, and legitimate polling is.
- One harness and one user's workload; the base-prompt figure is specific to omp v18.4.4 and its
  configured tools and skills.
- The runaway `max_tokens` turn stored an empty tool-call body, so whether it was degenerate
  repetition is unknown.

## Compaction cost on this hybrid model (2026-09-30)

All 14 compactions in the sessions above ran at the harness's then 60% threshold (~157K). 13 used
the harness's `handoff` method (an LLM-written summary replaces the history) and 1 used `soft`.

| Measure | Value |
|---|---|
| Context before → after | ~157K → 46K-67K tokens (one outlier to 26K) |
| Time to first token of the next turn | 36-106 s, median ~83 s |
| Summary length | 7,659-28,082 characters, typically ~16K (~4K tokens) |

- **Every compaction is a full re-process of what is kept.** Qwen3.8 is hybrid (48 Gated DeltaNet
  layers): its recurrent state can't be rolled back to an arbitrary position, and a rewritten
  history has no matching context checkpoint, so the server re-processes the whole kept context.
  The ~83 s median matches re-processing ~55K tokens at the ~660-770 tok/s cold prefill rate.
- **The summary itself costs generation time on top**: ~4K tokens at the ~20 tok/s decode rate
  near 157K is roughly 3-4 minutes. This is an estimate: the harness doesn't store the summary
  request's timing.
- **An in-place reduction (the harness's `shake` method: old tool results replaced with
  recoverable `artifact://` references, no LLM call) does not avoid this.** It rewrites old history
  too, so it also forces a full re-process — of a larger kept context. Freeing ~50K of ~190K would
  mean re-processing ~140K tokens, roughly 4-5 minutes at the ~450-550 tok/s prefill rate expected
  at that depth. That is estimated, not measured. It skips the summary generation, keeps more exact
  detail, and leaves the session deeper, so decode is slower and the next compaction comes sooner.
  Whether that beats `handoff` is an open A/B test, not something the numbers above settle.
- **A later threshold means fewer compactions but more turns in the slowest band.** Wall tok/s in
  the table above falls from ~34 at 64-96K to ~19 at 128-160K. Each avoided compaction saves
  roughly 5 minutes (summary plus re-process) and one lossy summary.
- **Neither 60% nor any other threshold has a special basis.** Context rot is documented as
  continuous with input length (Chroma "Context Rot"; Du et al. 2025, see `docs/SOURCES.md`), and
  compaction is lossy. The Qwen3.8 card evaluates its agentic coding benchmarks with the Claude
  Code harness and a 256K context window. That shows the model is meant to run agents in a 256K
  window. It does not show that a nearly full window works as well as a half-full one: the window
  size is not the fill level, and the harness compacts on its own.
- **Harness threshold changed to 75% (~196K) on 2026-09-30.** This is an operator choice, not
  based on a measurement here. The data above predates it.
- **Harness threshold changed to 70% (~183K) on 2026-10-01**, an operator choice after the
  full-miss audit below. It sits above the ~172K miss depth and below the ~193K one.
- **Workload shape**: the local model runs as the harness's main agent, carrying out an already
  documented, detailed plan for hours. Compaction is therefore automatic (`handoff` on threshold),
  not a manual `/handoff`. The harness's `handoff` summarizes into the same session; it does not
  open a new one.
- **`compaction.handoffSaveToDisk` enabled on 2026-09-30**: each automatically triggered handoff
  now also writes `handoff-<ISO timestamp>.md` to the session's artifact directory, so the state
  each compaction kept is recoverable from disk. Manual `/handoff` is not written by this setting.
  No runtime cost.

## Full cache misses in a long session (2026-10-01)

Evidence: [`results/20261001-agent-session-audit/`](../../results/20261001-agent-session-audit/README.md)
(server counters plus the harness session file; no server log, the server ran in the foreground).

- 344 main-agent turns, 3 compactions, deepest context 201,519 tokens. Server busy 96% of uptime;
  32.9 tok/s mean decode, 433 tok/s mean uncached prefill, 94.2% of prompt tokens served from cache.
- Six turns were a full re-process with no compaction before them: the prompt was the previous one
  plus ~1K tokens, yet cache read was 0. Two per compaction epoch, at ~172K and ~193K. Together
  2,512 s, against 162 s for the three post-compaction re-processes.
- Not yet explained. Hypotheses: the harness rewrites a message older than the oldest of the 4
  kept context checkpoints (`--ctx-checkpoints 4`), or checkpoint placement leaves no checkpoint
  before the divergence (since llama.cpp PR #22929 the server checkpoints before the latest user
  message and otherwise only every `--checkpoint-min-step` = 8,192 tokens). The 2026-09-29 test in
  [`memory.md`](memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29) found 4 and 32
  checkpoints equal for warm turns but did not cover this pattern.
- The 2026-09-28 sessions at the then 60% threshold (~157K) show no such misses: prefill was 10.8%
  of server time and context never passed 149K. Both miss depths lie above 157K, so a lower
  threshold may avoid them — a correlation across two days, not a test.
- Next step: `scripts/launch.py` now always writes a log (2026-10-01). When a miss repeats, read
  where the prompt diverged. Near the start means the harness changed early content and more
  checkpoints can't help; mid-context means test `--ctx-checkpoints` 16 (open A/B 4 below). Host
  RAM is that test's cost: checkpoints measured 270-515 MiB each up to ~93K and grow with depth.

## Open A/B tests

All need the same fixed agent task suite (a test repository with a handful of tasks that have
tests), at least 2 passes per arm, measuring tasks solved, total wall time, exact repeated tool
calls, output tokens per turn, number of compactions, time to first token after each compaction
and full re-processes in the server log.

1. **Compaction threshold**: the harness's current 75% (~196K of 262K) vs. the previous 60%
   (~157K). The trade-off is set out in "Compaction cost on this hybrid model" above. Only sessions
   that pass ~150K are affected.
2. **Compaction method order**: the effective current order is `handoff` → `shake` → `soft`
   (`remote` isn't configured and `snapcompact`, which renders history as images, was never
   used in these sessions) vs. `shake` first. See the re-process cost above.
3. **Context checkpoints** (only if the log shows a mid-context divergence): `--ctx-checkpoints 4`
   vs. 16, counting full re-processes, their time and peak host RAM.
4. **Presence penalty**: `--presence-penalty 0` (Qwen3.8 card's thinking-mode value, the current
   setting) vs. `1.0`. The data above shows little repetition to fix, and the card warns that
   higher values can cause language mixing, which matters for non-English work — adopt only if the
   A/B shows fewer repeated tool calls or shorter reasoning without a quality or language cost.

## History

- **2026-09-30, superseded 2026-10-01 for long sessions.** Generation dominates wall time, not
  prefill: 89% of server time is generation, 11% prefill (301 requests, two server logs). Prefix
  caching already keeps prefill small, so speed work should target generated tokens and decode
  speed at depth, not prompt processing.
