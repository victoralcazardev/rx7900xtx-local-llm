# Depth: context, KV and MTP at long context

## Current conclusion

**Profile: `262k-q8q51-mtp`** (`models.toml`) — recommended daily long-context default
(`scripts/launch.py`'s default when no alias is given): engine `hip-kvmix`, `-c 262144`, KV
q8_0/q5_1, MTP n=3, `-ub 256`, vision disabled, measured under a 272 W power cap (this card's
driver minimum — see `thermals-power.md`).

- **18.6-26.9 tok/s at 240K fill** across three task types (essay/copy/code, temperature 0),
  process VRAM peak **22,630 MiB**, 0 evicted. See "MTP n=3 confirmed at depth" and "`-ub 256`" in
  `speculative.md`/`memory.md`, and
  [`../../results/20260926-mtp-n3-depth/`](../../results/20260926-mtp-n3-depth/),
  [`../../results/20260926-ubatch256-262k/`](../../results/20260926-ubatch256-262k/).
- **`224k-q8q8-mtp` was the alternative profile** (`-c 229376`, KV q8_0/q8_0, MTP n=3,
  `-ub 512` default): 21.4-32.2 tok/s at 190K fill, process VRAM peak 22,883 MiB. **Removed
  2026-09-26** from `models.toml` — one best default, no overlapping alternatives (see
  `docs/DECISIONS.md`); the measurement stands as evidence.
- **Long-context quality validated up to 240K fill (68/68 exact match total)**: 52/52 up to 220K
  (see below) plus 8/8 at 240K on the adopted `262k-q8q51-mtp` profile (KV q8_0/q5_1) — the +27%
  KLD of q8_0/q5_1 over q8_0/q8_0 does not show up as a retrieval error at this depth — plus a
  further 8/8 at 240K re-run on the *exact* adopted server flags (MTP n=3, `-ub 256`, not just the
  KV variant). See "Quality (RULER-style)" below.
- The `200k-q8q8-mtp` and `240k-q8q8-mtp` profiles were **removed from `models.toml`**: 262K
  q8_0/q5_1 now gives more context than either at the same validated quality and less process VRAM
  than 240K q8/q8 (see "Context-window ladder" below).
- **System VRAM margin depends on the desktop's own usage, not just the profile**: a corrected
  reading found only ~0.2-0.3 GiB of total system headroom across every long-context configuration
  measured on 2026-09-26 (vs. the ~1.8 GiB figure below, measured with a lighter desktop) — see
  `memory.md`. Close heavy GPU applications (video players, browsers with GPU video) before
  long-context work, regardless of profile.
- All of the above is measured under the 272 W power cap adopted after a 303 W run overheated
  (see `thermals-power.md`) — about 6% slower prefill than the older 303 W measurements at a
  comparable depth, with more thermal margin (hotspot 98-101°C vs. 100-106°C at 303 W). The 303 W
  figures elsewhere in this file are kept as historical data points (different power policy, not
  a correction — see `docs/STYLE.md` §7), not superseded.

## Context, KV and MTP: server-real matrix (empty-context baseline)

`llama-server`, 1024-token response to a short prompt, IQ3_S-mtp, ROCm:

| Context | KV | Vision | MTP | Peak VRAM | tok/s | MTP acceptance |
|---|---|---|---|---:|---:|---:|
| 128K | q8/q8 | yes | no | 17.5 GiB | 38.8 | — |
| 128K | q8/q8 | yes | n=2 | 18.9 GiB | 59.1-62.2 | 56-62% |
| 128K | q8/q8 | yes | n=3 | 19.1 GiB | 60.6 | 56% |
| 128K | q8/q8 | yes | n=4 | 19.2 GiB | 45.8 | 31% |
| 128K | q8/q8 | yes | n=5 | 19.3 GiB | 40.0 | 23% |
| 262K | q8/q8 | yes | no | 22.4 GiB | 38.7 | — |
| 262K | q8/q8 | yes | n=2 | — | OOM while generating | — |
| 262K | q8/q8 | no | n=2 | 23.3 GiB | 60.2 | 60% |
| 262K | q4_0/q4_0 | yes | n=2 | 20.4 GiB | 60.7 | 60% |

KV q4_0 is **discarded on quality grounds** (see `kv-quality.md`): it doesn't improve MTP acceptance
or speed enough to justify the quality loss.

## Context-full stress test (total VRAM including desktop, 24,560 MiB)

The context is filled with N real tokens (`wiki.train`) and a response is requested; VRAM is sampled
every second.

| Case | Prompt tokens | Mean pp | tg at that depth | Peak VRAM | Result |
|---|---:|---:|---:|---:|---|
| 128K, q8/q8, vision, MTP n=2 | 104,185 | 608 tok/s | 30.7 tok/s (66% acc.) | 20,455 MiB | OK |
| 262K, q8/q8, no vision, no MTP | 182,132 | 521 tok/s | 19.3 tok/s | 22,347 MiB | OK |
| 262K, q8/q8, no vision, MTP n=2 (1st attempt) | ~104K of 182K | 640-740 | — | — | FAILED: `Memory access fault by GPU` |
| Same case (2nd attempt, `LLAMA_ATTN_ROT_DISABLE=1`) | 182,132 | 498 | 21.8 | **24,489 MiB** | OK, 71 MiB free |
| Same case (3rd attempt, without the variable) | 182,132 | 498 | 23.2 | **24,512 MiB** | OK, 48 MiB free |

Conclusion: the 262K+MTP failure is **running out of VRAM at the margin**, and depends on how much
VRAM the desktop is using at that moment — not a bug the environment variable fixes (see
`engines.md` on why `LLAMA_ATTN_ROT_DISABLE` isn't used). **262K with MTP and q8/q8 is not reliable
in 24 GB.**

## Depth matrix at 262K target (128K / 240K, `llama-server`, 400-token response)

Profile under test: IQ3_S-mtp, `-c 262144`, KV `q8_0/q5_1`, MTP n=2, no vision, `-np 1`.

| Case | Prompt tokens | Mean pp | **tg** | MTP | Peak total VRAM* | GTT at end |
|---|---:|---:|---:|---:|---:|---:|
| Case A: q8/q5_1 + MTP (ROCm 10 kvmix) | 130,250 | 586 | **27.5** | 58% | 24,260 MiB | 537 MiB |
| Case B: q8/q5_1 + MTP (ROCm 10 kvmix) | 239,314 | 430 | **23.8** | 90% | 24,373 MiB | 542 MiB |
| Case C: q8/q8, no MTP (official) | 130,250 | 607 | 23.7 | — | 23,112 MiB | 527 MiB |
| Case D: q8/q8, no MTP (official) | 239,314 | 453 | 16.0 | — | 22,912 MiB | 525 MiB |
| Case E: Case B + `-ub 256` | 239,314 | 412 | 19.4 | 63% | 22,983 MiB | **1,304 MiB** (warning) |

\* Total VRAM includes the desktop, which **varied between ~0.3 and ~1.1 GiB** within the same
session (0.44 GiB at 18:00, 1.09 GiB at 22:00, 0.28 GiB at 23:00) — these totals aren't comparable to
each other. Per-process VRAM via fdinfo (see `memory.md`) is the reliable metric used from this point
on.

- The 262K target profile clears 20 tok/s at 240K (23.8) here, and MTP gives +49% vs. not using it
  (16.0) — but this is a **single sample per case**, one content type (English summarization). MTP
  acceptance varies a lot between runs (58-90%). **Statistically thin** — see the corrected 240K
  measurement below. The +49% figure compares Case B (kvmix, q8/q5_1, 90% acceptance) with Case D
  (**official engine, q8/q8**) — it mixes engine, KV type and an unusually high acceptance rate, so
  it doesn't isolate MTP's effect. With 58% acceptance (see the 240K result below), it would be
  **~+15%** vs. the same Case D. The no-MTP reference with kvmix q8/q5_1 at 240K is still missing.
- **Update, 2026-09-26** (current default profile, MTP n=3, q8_0/q5_1, 262K, 240K fill): `-ub 256`
  shows **no spill** — system GTT 662-678 MiB vs. 642-680 MiB with `-ub 512`, per-process GTT
  8 MiB, 0 evicted, process VRAM 22,630 MiB vs. 22,980 MiB with `-ub 512`. This supersedes the
  2026-09-24 reading below (Case E), which used the older MTP n=2 depth matrix at a different
  profile stage. See `memory.md`'s "`-ub 256`" section and
  [`../../results/20260926-ubatch256-262k/`](../../results/20260926-ubatch256-262k/).
- **2026-09-24 (superseded by the update above)**: Case E (`-ub 256`) appeared to make things
  worse: ~770 MiB more spilled to GTT (silent overflow, see
  [#26432](https://github.com/ggml-org/llama.cpp/issues/26432)), and both tg and pp dropped
  relative to the `-ub 512` default at the time.

## 128K and 240K with fdinfo, and the aborted first 240K attempt

- **128K** (single sample, method described in `../BENCHMARK-FORMAT.md`): 262,144 reserved,
  q8_0/q5_1, MTP2, no vision, 128,000 exact prompt tokens, 1,500-token output, cache reuse 0, no
  truncation, seed 43. MTP accepted 787 of 1,423 drafts (55.3%). Prefill 587.64 tok/s / 217.82 s;
  generation **26.99 tok/s** / 55.53 s; full request 273.39 s. The >20 tok/s bar is met in **this
  single sample**. Per-process fdinfo peak: load/ready 21,895.31 MiB VRAM; prefill 22,828.86;
  generation 22,828.96. GTT 8.07 MiB throughout, 0 evicted. Hotspot peaked 98°C in prefill, 95°C in
  generation (edge 77/76°C).
- A first **240K** attempt with the same profile did not finish: the client ran out of allotted
  tokens and canceled the request at 67,584 of 240,000 prompt tokens (27%, ~748 tok/s), the server
  was orphaned and stopped by hand. **Not a valid result** — repeated below.

## 240K with fdinfo (repeated, q8/q5_1 + MTP n=2, 262,144 reserved)

Prompt from `wiki.train` (English) with an instruction to write an essay in Spanish, 1,500 forced
output tokens (`ignore_eos`), followed by a warm turn (history + short question, 500 tokens).

| Case | Prompt | pp | **tg** | MTP | Warm turn: reused/new | tg warm | Peak process VRAM | Process GTT | Evicted | Hotspot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240K (a) | 240,000 | 430 | **18.4** | 58% | 239,996 / 1,544 | 16.7 | 22,832 MiB | 8.1 MiB | 0 | 102°C |
| 240K (b) | 240,000 | 428 | **18.4** | 58% | 239,996 / 1,544 | 17.2 | 22,832 MiB | 8.1 MiB | 0 | 105°C |
| 128K (reference) | 128,000 | 588 | 27.0 | 55% | — | — | 22,829 MiB | 8.1 MiB | 0 | 98°C |

- **No memory problem at 240K.** Per-process VRAM by phase: load 21,895 MiB → prefill 22,829 →
  warm turn 22,832. GTT 8 MiB, **0 evicted**. The silent GTT overflow from
  [#26432](https://github.com/ggml-org/llama.cpp/issues/26432) does not appear with `-ub 512`.
- **Warm cache works**: the second turn reuses 239,996 of 240,000 tokens and only processes the new
  ones (~4 s instead of ~9 min) — this is what real agent usage looks like.
- **Speed: 18.4 tok/s, below the 20 tok/s bar.** (a) and (b) used the same seed: this confirms the
  result **reproduces**, but they are not independent samples. The earlier Case B figure (23.8) used 400
  output tokens and a 90% acceptance rate — not comparable one-to-one.
- Not caused by temperature: the core stayed at 2,500 MHz. tg per 250-token window ranged 15.7-22.2
  tok/s and tracked MTP acceptance (43-81%). With this synthetic, hard-to-predict text (the model
  "thinks" by listing loose Wikipedia topics), **MTP barely helps at 240K**.
- Long prefills (7-9 min at full 303 W power) push the hotspot to 100-105°C (edge 78-83°C) even
  starting from a cold GPU (edge ≤55°C) — see `thermals-power.md`.

## Target change: ~200K (2026-09-25)

200K accepted "if done well", instead of chasing 262K with a 3-hour measurement campaign. With
`-c 204800`, **KV q8/q8 fits** (better cache quality than q8/q5_1, and without its ~8% tg cost — see
`engines.md`). This is the profile measured in `speculative.md`'s 190K A/B, which is the basis for
the current conclusion at the top of this file.

Extrapolation ahead of the 190K measurement: (1) estimate (hypothesis, 2 points with one sample
each, q8/q5_1, 55-58% acceptance): ms/step ≈ 32.6 + 0.354 × (thousands of context tokens) →
**~21.5 tok/s at 190K**; q8/q8 should do somewhat better (no ~8% V-q5_1 cost). (2) VRAM estimate
with `-c 204800` q8/q8: KV ~6,800 MiB (vs. 7,424) and MTP KV ~800 (vs. 1,024) → **~22,000 MiB
process VRAM** (hypothesis; confirmed close by the measured 21,679 MiB above). (3) With
temperature 0, acceptance tends to run **higher** than at the vendor's temperature 1 — validate the
chosen n with a temperature-1 series. (4) Add `--spec-draft-p-min` (e.g. 0.5/0.7) to the matrix.

## Context-window ladder: 224K and 240K, 272 W (2026-09-25)

Stepping the `qwen38-iq3s-mtp` context window up from the 200K profile, fill = window − 8K, KV
q8/q8, MTP n=2, under the 272 W power cap; stops on the first failure to fit. Same method as the
190K A/B in `speculative.md` (three task types, temperature 1, 400 forced output tokens, 2
repetitions). Raw data and exact commands:
[`../../results/20260925-context-window-ladder/`](../../results/20260925-context-window-ladder/).

| Case | Fill | pp | tg essay | tg copy | tg code | Process VRAM peak | System VRAM | Hotspot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 224K (`-c 229376`) | 221,167 | 422 | 22.3 | 25.1 | 18.7 | 22,700 MiB | ~1.8 GiB margin | 98°C |
| 240K (`-c 245760`) | 237,551 | 410 | 22.5 | 24.4 | 18.7 | 23,407 MiB | ~0.3 GiB margin | 101°C |

GTT stayed at 8 MiB and evicted at 0 MiB in both cases. **Both fit and clear 18 tok/s on every
task.** 224K was adopted as the default profile (`224k-q8q8-mtp`) at the time — ~1.8 GiB of system
VRAM margin even with another light GPU client running. 240K was the measured maximum
(`240k-q8q8-mtp`) — only ~0.3 GiB margin, tight. The ladder was stopped after 240K (262K, which
would need KV `q8_0/q5_1` to fit, was not attempted in this ladder).

**Superseded 2026-09-26**: 262K with KV `q8_0/q5_1` was measured directly (below and in
`speculative.md`/`memory.md`) and adopted as the new default (`262k-q8q51-mtp`), fitting more
context than 240K at less process VRAM; `200k-q8q8-mtp` and `240k-q8q8-mtp` were removed from
`models.toml`. `224k-q8q8-mtp` stayed as the alternative profile (removed 2026-09-26, see
`docs/DECISIONS.md`). The ~1.8 GiB system VRAM margin
figure above was measured with a lighter desktop than later sessions — see `memory.md`'s
`-ub 256`/system-VRAM finding for the corrected reading.

## Quality (RULER-style), `200k-q8q8-mtp`

`bench/longctx_quality.py`: a Spanish-language multi-key retrieval test (deliberately Spanish, see
the script's own docstring and `STYLE.md` §1), 5 documents × 4 questions per depth, `-c 204800`,
KV q8/q8, MTP n=2, temperature 0. Raw data and exact commands:
[`../../results/20260925-longctx-quality-200k/`](../../results/20260925-longctx-quality-200k/).

| Depth | Power cap | n | Exact match | Loops | tok/s (min-max) |
|---:|---:|---:|---|---:|---|
| 32,000 | 303 W | 20 | 20/20 | 0 | 64.1-67.2 |
| 128,000 | 303 W | 20 | 20/20 | 0 | 36.8-38.9 |
| 190,000 | 272 W | 4 | 4/4 | 0 | 24.3-29.2 |

**Total: 44/44 exact match, 0 loop detections.** Exact match doesn't collapse anywhere measured
from 32K to 190K fill, and no output loops were observed — retrieval quality holds up to 190K for
this profile. **190K is a partial sample**: the first attempt at the factory 303 W limit was
stopped by the operator when the hotspot reached 106°C (see `thermals-power.md`); the re-run at a
272 W power cap completed one of the five planned documents (4/4 exact) before 190K testing was
deprioritized (200K judged sufficient if it works well) — the 32K/128K result plus this one 190K
document were judged sufficient evidence. The 272 W prefill at 190K (459 tok/s) is ~6%
slower than the 303 W reference at the same depth (487 tok/s, see `speculative.md`'s 190K A/B).

### 220K, `224k-q8q8-mtp` (2026-09-26)

Same script, the real operating depth of the adopted `224k-q8q8-mtp` profile (`-c 229376`, KV
q8/q8, MTP n=2, 272 W). 2 documents × 4 questions, temperature 0. Raw data:
[`../../results/20260926-longctx-quality-224k/`](../../results/20260926-longctx-quality-224k/).

**8/8 exact match, field accuracy 1.0, 0 loops, 0 truncated.** Prompt 220,109 tokens, cold prefill
420.3 tok/s (~8.7 min); warm turns reuse 219,593 tokens, generation 25.1-26.1 tok/s. Peak process
VRAM 22,702 MiB, 0 evicted, hotspot 98°C.

**Cumulative: 52/52 exact match, 32K-220K fill** (44/44 above + this 8/8). Closes the "no
validation at the real 220K depth" gap; anecdotal "q8 KV amnesia beyond 150K" claims (`SOURCES.md`)
do not reproduce here.

### 240K, `262k-q8q51-mtp` (2026-09-26)

Same script, the real operating depth of the newly adopted `262k-q8q51-mtp` profile (`-c 262144`,
KV q8_0/q5_1, MTP n=2, 272 W). 2 documents × 4 questions, temperature 0. Raw data:
[`../../results/20260926-longctx-quality-262k/`](../../results/20260926-longctx-quality-262k/).

**8/8 exact match, 0 loops, 0 truncated.** Prompt 240,111 tokens, cold prefill 400 tok/s;
follow-up turns reuse 239,595 cached tokens, generation 23.0-24.0 tok/s. Peak process VRAM 22,830
MiB, 0 evicted, hotspot 98°C.

**Cumulative: 60/60 exact match, 32K-240K fill** (52/52 above + this 8/8). The +27% KLD of KV
q8_0/q5_1 over q8_0/q8_0 (`kv-quality.md`) does not show up as a retrieval error at this depth —
one of the criteria that closed the decision to adopt `262k-q8q51-mtp` as the default profile
(`docs/DECISIONS.md`).

### 240K, exact adopted flags (MTP n=3, `-ub 256`), 2026-09-26

The 240K run above used MTP n=2 and no `-ub 256` — not the exact flags `262k-q8q51-mtp` ships
with. Repeated on those exact flags via `bench/longctx_quality.py`'s new `--mtp-n`/`--extra`
options (commit 17567ff): `--ctx 262144 --variants q8q51-mtp1 --depths 240000 --docs 2 --mtp-n 3
--extra "-ub 256"`. Same corpus, 2 documents × 4 questions, temperature 0. Raw data:
[`../../results/20260926-longctx-quality-262k/README.md`](../../results/20260926-longctx-quality-262k/README.md#exact-adopted-config-confirmation-mtp-n3--ub-256-2026-09-26).

**8/8 exact match, field accuracy 1.0, 0 loops, 0 truncated, 0 failures.** Prompts
240,105-240,111, cold prefill 380-382 tok/s; follow-up questions reuse 239,845-239,851 cached
tokens and process ~255-262 new tokens at 142-152 tok/s; generation 27.9-29.7 tok/s (vs.
23.0-24.0 tok/s on the n=2/no-`-ub 256` run above). Peak process VRAM 22,628 MiB, GTT 8 MiB,
0 evicted, hotspot 99°C, system VRAM peak 24,432 of 24,560 MiB.

**Cumulative: 68/68 exact match, 32K-240K fill** (60/60 above + this 8/8). Confirms quality holds
not only for the KV q8_0/q5_1 variant but on the exact server flags (MTP n=3, `-ub 256`) the
default profile actually launches with — closing the gap left by the n=2/no-`-ub 256` run above
(also relevant since generated text is not bit-identical across n=2/n=3/`-ub 256` at temperature
0 for some task types — see `speculative.md`'s "n=4 checked again at 240K").

## Open questions / pending (priority order)

1. A broader 190K quality sample (the remaining 4 of 5 planned documents, 16 of 20 questions) —
   deprioritized, not required to keep `224k-q8q8-mtp`/`262k-q8q51-mtp` adopted (32K/128K are
   fully validated, and the one 190K document validated exactly).
2. Real agent-usage MTP acceptance at depth (temperature 1, 3 seeds): the synthetic benchmark above is
   pessimistic — a third-party report (`sweeps/radeon.md`,
   [sudoingX/qwen38-mtp](https://github.com/sudoingX/qwen38-mtp/blob/master/sweeps/radeon.md))
   measured **~93% acceptance** with a real agent (Hermes, MTP n=3 + p-min 0.75, 29-37K context) on
   a 7900 GRE — our synthetic figures likely undervalue real usage.
3. Statistical repetition: the 5-10-prompt, multi-seed MTP acceptance campaign originally planned was
   not completed — most depth numbers above are single- or double-sample.
4. Quality beyond English wikitext (Spanish and code tasks with a verifiable answer) — perplexity on
   English wikitext-2 only ranks variants of the same model, it isn't a quality test on its own.
5. A third-party report of the same model on a 7900 XTX via **Windows/Vulkan** claims 41 → 85 tok/s
   with MTP ([sudoingX/qwen38-mtp](https://github.com/sudoingX/qwen38-mtp)) — not reproduced here
   (Linux only so far); Windows/Vulkan doesn't appear to suffer the Linux memory-clock throttling
   described in `engines.md`.
6. ~~262K with KV `q8_0/q5_1` was not attempted in the 224K/240K ladder above~~ — done 2026-09-26,
   see "240K, `262k-q8q51-mtp`" above and `speculative.md`'s "MTP n=3 confirmed at depth".

## History

- **2026-09-24**: first context/KV/MTP matrix and stress tests (128K/262K); 262K target profile
  measured at 128K and 240K depth (single samples), 240K attempt #1 invalid (client timeout).
- **2026-09-24, night**: 240K repeated twice with fdinfo instrumentation — confirms 18.4 tok/s
  (below the >20 tok/s bar), supersedes the earlier single-sample 23.8 reading for the 262K profile.
- **2026-09-25**: target changed to ~200K; `200k-q8q8-mtp` measured at 190K
  (22-30 tok/s, see `speculative.md`) and adopted as the new candidate profile, superseding
  `262k-q8q51-mtp`. Quality test still pending as of this date.
- **2026-09-25, later**: long-context quality test (RULER-style) run partially — 32K and 128K
  validated (20/20 exact match, 0 loops); 190K stopped on thermal grounds at 303 W (106°C hotspot),
  re-run in progress at 272 W.
- **2026-09-25, evening**: 272 W adopted as a permanent power cap; 190K quality re-run completed
  one document (4/4 exact, 99°C hotspot) before being deprioritized — 44/44 exact match total,
  0 loops. Context-window ladder measured 224K and 240K (both fit, 18-25 tok/s); 224K adopted as
  the new default profile (`224k-q8q8-mtp`), 240K as the measured maximum (`240k-q8q8-mtp`),
  superseding `200k-q8q8-mtp` as the recommended daily default (kept as a narrower candidate).
- **2026-09-26**: quality re-tested at 220K fill, the real `224k-q8q8-mtp` operating depth — 8/8
  exact match, 0 loops. Cumulative 52/52 exact match from 32K to 220K.
- **2026-09-26, later**: quality re-tested at 240K fill on `262k-q8q51-mtp` (KV q8_0/q5_1) — 8/8
  exact match, 0 loops, cumulative 60/60 from 32K to 240K. MTP n=3 confirmed at depth (190K/240K,
  +9-11% mean tg) and adopted for both long-context profiles. `262k-q8q51-mtp` (MTP n=3, `-ub 256`)
  adopted as the new default, superseding `224k-q8q8-mtp` (kept as the alternative);
  `200k-q8q8-mtp` and `240k-q8q8-mtp` removed from `models.toml`. See `speculative.md` and
  `memory.md` for the full evidence.
- **2026-09-26, night**: MTP n=4 re-checked at 240K on the exact adopted flags (`-ub 256`) — still
  loses to n=3 (-8% mean tg), as it did at 128K empty-context. Quality re-validated at 240K on the
  *exact* adopted flags (MTP n=3, `-ub 256`, not just the KV variant): 8/8 exact match, cumulative
  68/68 from 32K to 240K. See `speculative.md`.
