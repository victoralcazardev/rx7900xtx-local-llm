# Speculative decoding: MTP vs. DFlash2 vs. n-gram

## Current conclusion

Headline numbers and the adopted flags: [`../STATUS.md`](../STATUS.md).

- **MTP `--spec-draft-n-max 3` is the adopted default at depth (2026-09-26)**: confirmed at both
  long-context profiles' real operating fill, it wins across all three task types, +9% mean tg at
  190K (`224k-q8q8-mtp`, removed 2026-09-26) and +11% at 240K (`262k-q8q51-mtp`, the current
  default) — see "MTP n=3 confirmed at depth" below. **n=4 is slower**: at the 128K empty-context
  screening, n=4 drops to 45.8 tok/s and 31% acceptance vs. n=3's 60.6 tok/s and 56% (see
  `depth.md`'s server-real matrix). Confirmed again at 240K depth on the exact adopted flags
  (`-ub 256`): 21.4 vs. 23.3 tok/s mean (-8%), 66% vs. 71% acceptance — see "n=4 checked again at
  240K" below. `--spec-draft-p-min 0.8` (a community config) raises acceptance
  substantially (67%→96%) but **not speed** — not adopted on its own.
- **At depth, MTP's gain over no speculation grows, it does not shrink (corrected 2026-09-27)**:
  on the adopted profile at 240K fill, spec-off decodes at 11.2 tok/s and MTP n=3 at 23.3
  (**+109%**), vs. +85% at empty context on the same profile.
  See "MTP vs. spec-off at 240K fill" below.
- **Community `probe.py` A/B, empty context, 262K profile (2026-09-27)**: spec-off 37.2 → n=2
  68.6 / **n=3 68.9** / n=4 66.9 tok/s (n=2 and n=3 tie within noise); `--spec-draft-p-min`
  0.60/0.75 raises acceptance (0.72 → 0.85/0.91) but lowers speed (66.2/59.8). See "Community
  probe A/B at 262K" below.
- **DFlash2 does not beat MTP** once measured at depth (190K): slower on two of three task types,
  ties on the third, and costs more VRAM. A third-party claim that DFlash2 wins at all depths on a
  different GPU (RTX 3090) does not reproduce here.
- **n-gram stacked on MTP**: a single sample suggests it can help on repetitive content (code edits,
  +6%) and hurt on reasoning (−8%); not adopted without repeated measurement. The A/B on the
  adopted n=3 profile is prepared but not run — see "n-gram stacked on MTP: how llama.cpp
  combines them" below.
- The **root cause of MTP's depth slowdown is identified but not fully explained**: verifying ≥3
  tokens per step (MTP n≥2) routes through the FlashAttention TILE kernel, which converts the whole
  KV cache to f16 on every step; a fork that removes that conversion only recovered ~2.5% of the
  step time, so the conversion is a minor contributor, not the main cost.

## MTP vs. DFlash2 vs. n-gram, empty context

IQ3_S-mtp, 128K, KV q8/q8, vision enabled, ROCm b11160. Method: 3 content types, 1500 tokens per
prompt, `seed 42`, vendor Qwen sampling (temp 1.0). Draft model for DFlash2:
[`z-lab/Qwen3.8-27B-DFlash2-GGUF`](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF) (Q4_K_M
1.1 GB / Q8_0 2.0 GB), `-md <draft> -ngld all`.

| Configuration | New code | Reasoning | Edit given code | VRAM |
|---|---:|---:|---:|---:|
| No speculation | 38.4 | 38.3 | 38.1 | 17.8 GiB |
| **MTP n=2** | **57.7** (54%) | **68.8** (74%) | 63.2 (65%) | **19.7 GiB** |
| ngram-map-k4v + MTP n=2 | 57.8 (54%) | 63.3 (61%) | **67.1** (58%) | 19.7 GiB |
| DFlash2 Q4_K_M n5 p0.4 | 49.9 (44%) | 69.4 (60%) | 59.4 (53%) | 20.3 GiB |
| DFlash2 Q8_0 n5 p0.4 | 46.6 (41%) | 71.3 (64%) | 59.0 (55%) | 21.2 GiB |
| DFlash2 Q4_K_M n7 (z-lab's example) | 44.9 (26%) | 67.8 (47%) | 47.0 (28%) | 20.6 GiB |
| ngram-map-k4v + DFlash2 Q8_0 n5 p0.4 | 46.6 (41%) | 70.4 (58%) | 65.0 (54%) | 21.2 GiB |

Generation tok/s (accepted-draft percentage in parentheses).

- DFlash2 only beats MTP on reasoning (+1-4%), loses 6-20% on code, and costs 0.6-1.5 GiB more. With
  24 GB VRAM and a 262K target, it doesn't pay off. A third-party figure (QingYis, 68 tok/s on
  reasoning with DFlash2) matches MTP's number here.
- ngram-map-k4v stacked on MTP: +6% editing code (repetitive content), −8% reasoning, **single
  sample**. Candidate for a "coding agent" profile; needs repetition before adopting.
- This comparison is **with an empty context**. DFlash2's draft metadata
  (`dflash.attention.sliding_window 2048` across its 5 layers) shows its attention uses a **2K
  sliding window**: its cost and KV don't grow with context, while the MTP layer attends to the
  full context in f16. A user with an RTX 3090 and this same model (@ItsmeAjayKV, 2026-09-14, no
  published method) reports DFlash2 beating MTP at every depth. **This needed repeating at ~190K**
  before trusting "MTP is better" for long-context use — see the 190K result below, where DFlash2
  is measured directly and does not reproduce that claim on this GPU.

## n-gram stacked on MTP: how llama.cpp combines them (source reading, 2026-09-29)

Read in `common/speculative.cpp` on llama.cpp master (last commit touching it: f1ea206,
2026-09-28). **Not verified: that b11160 (our engine) has the same behavior, and any speed gain on
this card.**

- `common_speculative_init` builds the implementations in a **fixed priority order**, not the
  order given in `--spec-type`: ngram-simple, ngram-map-k, ngram-map-k4v, ngram-mod, ngram-cache,
  then draft-simple, draft-eagle3, draft-mtp, draft-dflash, draft-dspark.
- `common_speculative_draft` calls each implementation in that order and stops at the first that
  returns a non-empty draft. With `draft-mtp,ngram-mod`, ngram-mod drafts whenever its hash pool
  has a match; otherwise MTP drafts. `docs/speculative.md` upstream says the same: "If a draft
  model is combined with a draftless decoding the draftless decoding has higher precedence."
- Draft length: `common_speculative_n_max` takes the max over the enabled types (draft types use
  `--spec-draft-n-max`, ngram-mod uses `--spec-ngram-mod-n-max`), so `--spec-draft-n-max 3` does
  **not** cap ngram-mod drafts (up to 64 by default).
- There is no acceptance- or cost-based gating: if an n-gram matches, its draft is used. (Contrast:
  the Strata engine's prompt lookup drafts only where measured acceptance and cost say it pays;
  see `docs/SOURCES.md`.)
- ngram-mod: rolling LCG hash of the last n tokens -> next token, ~16 MB, pool shared across
  slots, variable draft length. Upstream notes small n is not recommended and dense models can
  lower `--spec-ngram-mod-n-min`/`--spec-ngram-mod-n-max`. b11160 `--help` defaults: n-match 24,
  n-min 48, n-max 64.
- Upstream: [PR #28391](https://github.com/ggml-org/llama.cpp/pull/28391) (open, unmerged as of
  2026-09-29) would enable ngram-mod by default and make `--spec-type` additive
  (`--spec-type draft-mtp` -> `[ngram-mod, draft-mtp]`); once an engine update includes it, the
  current profile would silently become MTP + ngram-mod, so re-measure then.
  [Issue #27839](https://github.com/ggml-org/llama.cpp/issues/27839) (open): a reporter says
  `--spec-type draft-mtp,ngram-mod` works on Qwen3.8-27B (Vulkan, gfx1151) in passing, no numbers;
  the bug there is combining it with an external `-md` draft.
  [Issue #25618](https://github.com/ggml-org/llama.cpp/issues/25618) (open): greedy output
  diverges from vanilla with draft-mtp/draft-dspark.

**Why the 2026-09-24 result is not enough**: it is a single sample, at n=2 (the adopted profile is
n=3), with ngram-map-k4v (not ngram-mod), at empty context only (the adopted profile runs at up to
240K fill).

**Expected shape (hypothesis)**: helps repetitive agentic edits, where long verbatim spans are
copied; may hurt reasoning, where a match is a poor predictor and a long wrong draft costs a
verification pass.

**Prepared, not yet run** (the GPU is in daily use; nothing below has been executed):

```
# empty context, 6 tasks x 3 seeds
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 BENCH_SERVER=... BENCH_MODEL=... \
    python3 bench/spec_bench.py --run --variants mtp3 mtp3-mod mtp3-moddef mtp3-map --tag ngram-stack
# 240K fill
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 BENCH_SERVER=... BENCH_MODEL=... BENCH_WIKI=... \
    python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3 n3-mod n3-moddef --reps 3 --tag ngram-stack --extra "-ub 256"
```

`mtp3-mod`/`n3-mod` use n-match 24 / n-min 8 / n-max 32; `mtp3-moddef`/`n3-moddef` use the
upstream defaults (24 / 48 / 64). `spec_depth_bench.py` does not hardcode `-ub 256`, so the
command passes it via `--extra` to match the adopted profile (its greedy temperature 0 makes
`--top-p` irrelevant).

**Community data (verified 2026-09-29, not reproduced here)**: the closest public match to the
`mtp3-moddef` arm is stew675's Qwen3.8-27B greedy run (PR #27210 comment, 2026-08-22): MTP n=3
alone 51.63 / 55.81 / 69.20 / 81.80 tok/s (reasoning / prose / code / recall) vs. MTP n=3 +
ngram-mod 51.66 / 55.92 / 68.42 / 324.32. So the only large win reported is verbatim recall; new
code, prose and reasoning are unchanged. No published agentic-coding trace exists, so the `agent`
task (return a full file with one change) is the one to watch. Risk: issue #23577 (`////`
repetition loops after long sessions, reportedly faster with ngram-mod) and PR #25819 (WIP
stuck-loop escape for ngram-mod). Details and links in `docs/SOURCES.md`.

**Decision rule**: adopt only if the agent/editing tasks gain beyond seed noise and the reasoning
and code tasks do not lose, at both empty context and 240K, **and** no arm shows runaway
repetition (for example a `////` run or `predicted_n` hitting the cap on a task that normally
stops). Otherwise record it here as not adopted.

## VEC vs. TILE kernel selection at depth

In `ggml/src/ggml-cuda/fattn.cu` (`ggml_cuda_get_best_fattn_kernel`), the RX 7900 XTX (RDNA3: WMMA,
no NVIDIA-style MMA or MFMA) and Qwen3.8's attention shape (head_dim 256, GQA 6 → effective GQA
ratio 2) fall into the generic kernel selection path:

- Quantized KV and **≤2 tokens** in the batch → **VEC** kernel, reads q8_0/q5_1 directly.
- **≥3 tokens** → **TILE** kernel, needs K and V in f16 (`need_f16_K/V`): **converts the entire
  layer's KV to f16 on every step** (hundreds of MiB per layer at 240K).
- Generating without MTP = 1 token (VEC). **MTP n=1 verifies 2 tokens (VEC). MTP n=2 verifies 3
  (TILE). n=3 verifies 4 (TILE).**

This matches what's measured: MTP gains +50-60% with an empty context (converting little KV is
cheap), but very little at 240K. It likely also explains part of the +933 MiB of VRAM seen during
prefill (f16 conversion buffer) — see `memory.md`.

**Correction (2026-09-27)**: "very little at 240K" was wrong for the adopted profile. It came
from comparing MTP against a KV q8_0/q8_0 spec-off baseline. Against spec-off with the adopted
KV q8_0/q5_1, MTP n=3 is **+109%** at 240K fill (see "MTP vs. spec-off at 240K fill" below): the
VEC path spec-off uses pays the V q5_1 dequant cost (-25% vs. V q8_0), while TILE's per-step f16
conversion is a smaller cost than this section assumed. The kernel selection described above is
still correct; the conclusion drawn from it was not.

**Experimental engine `llama-b11160-linux-rocm10-gfx1100-kvmix-vec4`**: same build with one line
changed (`Q->ne[1] <= 2` → `<= 4` in that branch), so 3-4-token batches stay on VEC. Patch:
`vec4.patch`. **Not adopted without measuring speed and quality** — see the 190K A/B below, where it
loses.

(1) TILE selection is **verified in the code**. (2) Risks of vec4: VEC doesn't apply the GQA
optimization, and with 3-4 tokens it launches 2 blocks of 2 columns, so it **reads the KV twice**
per step — the gain could go either way, needs measuring (out-of-range accesses are guarded,
`fattn-vec.cuh:164,215,280,434,511`). It also **changes the numerics**: TILE uses Q/K in f16, VEC
quantizes Q to q8_1 (`:97`), same as no-MTP generation. (3) Doubt that the +933 MiB in prefill is
the conversion buffer: `ggml_cuda_flash_attn_ext_get_alloc_size` reserves it inside the compute
buffer, and that +933 MiB is **identical at 128K and 240K** — a hypothesis, not confirmed. (4)
**Untried lever: `--spec-draft-p-min`** (default 0.00; MTP respects it,
`common/speculative.cpp:1684`). If the draft is unsure, it proposes 1 token, 2 get verified, and
VEC is used **without needing the patch**.

Bugs relevant to why MTP costs so much VRAM/compute at depth (open as of b11160/b11170):
[#28433](https://github.com/ggml-org/llama.cpp/issues/28433) (draft context sized by total context,
not per-sequence — confirmed **not applicable here** since it only multiplies with `-np > 1`, and
this setup uses `-np 1`), [#26038](https://github.com/ggml-org/llama.cpp/issues/26038) (MTP draft
over-reserves compute buffers on HIP), [#26432](https://github.com/ggml-org/llama.cpp/issues/26432)
(silent GTT fallback when context + MTP exceed VRAM), [#27282](https://github.com/ggml-org/llama.cpp/issues/27282)
(shared MTP compute arena, open with a CUDA proof-of-concept patch), and
[#28003](https://github.com/ggml-org/llama.cpp/pull/28003) (RDNA3 single-token MMVQ, draft). No flag
exists to limit the MTP draft's own context or compute footprint.

## A/B at 190K (`-c 204800`, KV q8/q8): kvmix vs. vec4, MTP n=2

One server per variant; 190,000-token document + 3 tasks (essay, literal copy, code); temperature 0;
400 tokens max, natural EOS. First request per task does the prefill (not counted), second reuses
the cache (`cache_n` 189,979-189,983).

| Engine | Essay | Copy | Code | Accepted/proposed (essay, copy, code) |
|---|---:|---:|---:|---|
| **kvmix (b11160 + ROCm 10), n=2** | **25.2** | **29.4** | **22.1** | 238/321, 261/275, 215/365 |
| vec4, n=2 | 21.6 | 24.5 | 18.5 | 241/313, 261/275, 215/365 |

- **With 200K reserved and q8/q8, the current engine stays above 20 tok/s at 190K on all three
  tasks** (temperature 0: an optimistic acceptance rate, see `depth.md`). Switching task reuses
  189,467 tokens of cache and only reprocesses ~515 (end-of-document checkpoint).
- **vec4 is 14-17% slower: discarded.** The TILE-converts-KV-to-f16 hypothesis above is **confirmed**
  (own code reading + an independent source below), but the VEC-based fix is worse: VEC doesn't
  apply the GQA optimization and, with 3 tokens, reads the KV twice (2 blocks of 2 columns), as the
  external audit predicted. vec4 with n=3 was not measured. The `...-kvmix-vec4` engine is kept only
  as a reference.
- Even with matching acceptance rates, vec4 changes the numerics (VEC quantizes Q to q8_1), so
  accepted-draft counts differ slightly (321 vs. 313 for essay).

## DFlash2 and the "native q8 KV" fork, at 190K

Same method as the 190K A/B above. VRAM = per-process fdinfo maximum by phase. ms/step = generation
time / (generated − accepted), warm turn.

| Variant | Essay | Copy | Code | ms/step | VRAM ready → peak | Prefill @190K |
|---|---:|---:|---:|---:|---:|---:|
| **kvmix, MTP n=2** (reference) | **25.2** | **29.4** | **22.1** | 97.7 | 20,712 → **21,679 MiB** | 487 tok/s |
| kvmix, DFlash2 Q4_K_M n=5, p-min 0.4 (GGUF without MTP) | 21.3 | 26.5 | 22.2 | — | 21,440 → 21,979 MiB | — |
| Fork stew675 v16 (`ebbb18522`), MTP n=2, native q8_0 (auto) | 26.5 | 30.1 | 22.4 | 95.4 | 20,033 → 21,847 MiB | 489 tok/s |

GTT stayed at 8 MiB and 0 evicted for all three; hotspot peaked at 103°C.

- **DFlash2 does not beat MTP at 190K**: slower on essay and copy, ties on code, +300 MiB. The
  @ItsmeAjayKV (RTX 3090) claim from the empty-context section above does not reproduce here.
  **Discarded.** DFlash2 n=3 was not measured (deprioritized).
- **"Native q8" fork** ([stew675/llama-cpp-rdna-boosts](https://github.com/stew675/llama-cpp-rdna-boosts),
  `GREEDY-PURITY.md` §14 and `V4-NATIVE-Q8-KV-PLAN.md`; same TILE-converts-to-f16 finding as above,
  independently documented): reads q8_0 KV directly in TILE/MMA instead of converting to f16. It
  claims −758 MiB VRAM for a 27B model at 204,800 context, `-ub 512`, q8_0/q8_0 only. Measured here:
  `ready` VRAM drops 680 MiB (close to the claim), but **prefill peak is 170 MiB higher**, and the
  per-step cost only improves ~2.5% (97.7 → 95.4 ms). Per-task tok/s differences also mix in
  different text (different code base, different hashes). **Not adopted** — experimental fork on an
  older upstream base. Engine kept as
  `llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100` (`test-backend-ops -o FLASH_ATTN_EXT` with
  hsk=256 and q8_0: 10/10 OK). `GGML_CUDA_FA_KV_NATIVE=0` (old f16 path) was not isolated against the
  auto (native) mode separately.
- Cost model: at 240K, one MTP n=2 step costs ~117 ms whether acceptance is 90% or 58% (see
  `depth.md`) — tg ≈ steps/s × tokens/step, so **it's mostly the acceptance rate that drives tg**,
  not the per-step cost varying. A step of n=2 costs ~1.9x a single non-MTP token (ideally it should
  be 1.1-1.3x) — that overhead is the real target to fix. The "native q8" fork's 2.5% improvement
  shows the f16 conversion is only a few ms of the ~98 ms step; the rest is the attention computation
  itself over the long KV, plus the draft steps. Without per-kernel profiling, the bulk of the
  overhead is still unexplained.
- Not measured (deprioritized this session): kvmix without MTP at 190K, MTP n=3, `--spec-draft-p-min`
  sweep, temperature 1 with multiple seeds.

## `-ub` and MTP screening at 128K fill, 272 W (2026-09-25)

Fast, cool screening at 128K fill (of the 200K `-c 204800` window) under the 272 W power cap
(`thermals-power.md`), before confirming any winner at 190-240K depth — this is the first n≥3 and
`--spec-draft-p-min` data measured at depth rather than with an empty context. Same three task
types, temperature 1 (vendor sampling), 400 forced output tokens, 2 repetitions. Raw data and
exact commands: [`../../results/20260925-ubatch-mtp-screening-128k/`](../../results/20260925-ubatch-mtp-screening-128k/).

| Variant | pp | tg essay | tg copy | tg code | Accept | Peak VRAM | Peak hotspot |
|---|---:|---:|---:|---:|---:|---:|---:|
| base (n2, `-ub 512`) | 552.6 | 30.6 | 36.0 | 27.7 | 75% | 21,648 MiB | 96°C |
| `-ub 1024` | 551.7 | 30.1 | 35.9 | 27.6 | 75% | 22,238 MiB | 98°C |
| `-ub 2048` | 543.4 | 30.6 | 35.8 | 26.7 | 74% | 23,420 MiB | 98°C |
| n3 | 551.3 | 31.3 | 42.1 | 27.5 | 64% | 21,797 MiB | 98°C |
| `--spec-draft-p-min 0.3` (n2) | 551.8 | 31.3 | 36.4 | 27.5 | 78% | 21,647 MiB | 98°C |

- **`-ub 512` (the default) is optimal at this depth**: `-ub 1024` gains nothing and costs 590 MiB,
  `-ub 2048` is strictly worse (slower prefill, −3.6% code tg, +1.8 GiB VRAM). This supersedes the
  earlier `pp2048`-only, empty-context reading in `engines.md` ("within ±1% of default"), which
  never exercised `-ub` at depth.
- **`--spec-draft-p-min 0.3` is within noise of plain n=2**: essentially the same tg and VRAM,
  accept +3 points (78% vs. 75%) — not a clear win, **not adopted**.
- **MTP n=3 is strongly content-dependent**: +17% on literal copy (predictable text, the draft is
  right more often even at lower acceptance), ≈ on code, small essay gain — but acceptance drops 11
  points vs. n=2 (75% → 64%), consistent with a longer, harder-to-verify draft. **Not adopted as
  the default** (n=2 remains the better all-round choice); a candidate for a copy- or
  refactor-heavy profile where the content is more predictable. Needs confirming at 190-240K depth
  before any such profile is added (TILE-kernel cost grows with depth — see the VEC/TILE section
  above).

## MTP n=3 confirmed at depth (190K and 240K fill, 2026-09-26)

The 128K-fill screening above left n=3 as "content-dependent, not adopted". Repeated at the two
long-context profiles' actual operating depths (`bench/spec_depth_bench.py`, essay/copy/code,
temperature 0, 400 forced output tokens, 1 repetition, 272 W). Raw data and exact commands:
[`../../results/20260926-mtp-n3-depth/`](../../results/20260926-mtp-n3-depth/).

**224K profile (`-c 229376`, KV q8_0/q8_0), 190K fill:**

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|
| n=2 | 24.0 | 28.0 | 21.1 | 24.4 | 76% | 22,733 MiB |
| **n=3** | **26.1** | **32.2** | **21.4** | **26.6 (+9%)** | 67% | 22,883 MiB |
| n=3 + `--spec-draft-p-min 0.8` | 26.7 | 31.6 | 20.6 | 26.3 | 96% | 22,883 MiB |

**262K profile (`-c 262144`, KV q8_0/q5_1), 240K fill:**

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|
| n=2 | 22.2 | 22.9 | 18.0 | 21.0 | 81% | 22,830 MiB |
| **n=3** | **25.7** | **26.9** | **17.6** | **23.4 (+11%)** | 71% | 22,980 MiB |

Prefill ~455 tok/s (224K) / 400 tok/s (262K), hotspot 98-99°C, 0 evicted in every case.

- **n=3 wins at both depths, across all three task types** — unlike the 128K-fill screening,
  where only literal copy favored it. **Adopted as the default MTP draft length** for both
  long-context profiles, superseding the 2026-09-25 "not adopted" call at this depth.
  `--spec-draft-p-min 0.8` (the @SergioSV96 community config, minus its q4_0 KV — see
  `docs/SOURCES.md`) raises acceptance substantially (67%→96% at 190K) but not speed (26.6→26.3,
  within noise) — **not adopted on its own**.
- The 262K profile's 240K mean tg (23.4, later 23.3 with `-ub 256` — see `memory.md`) meets the
  floor (≥15 tok/s, target ≥17) with 0 evicted, one of the criteria for adopting
  `262k-q8q51-mtp` as the new default profile (see `docs/DECISIONS.md`).

### n=4 checked again at 240K, exact adopted flags (`-ub 256`, 2026-09-26)

The 128K empty-context screening above already showed n=4 losing to n=3 (45.8 tok/s @ 31% accept
vs. 60.6 @ 56%). Re-checked at the 262K profile's real 240K operating depth, on the exact flags
`262k-q8q51-mtp` ships with (`-ub 256`, adopted after the n=3-at-depth measurement above — see
`../../results/20260926-ubatch256-262k/`). Same method: `bench/spec_depth_bench.py`, essay/copy/
code, temperature 0, 400 forced output tokens, 1 repetition (cold + warm identical), 272 W.

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|
| n=3 + `-ub 256` (adopted, reference) | 24.4 | 26.9 | 18.6 | 23.3 | 71% | 22,630 MiB |
| **n=4** + `-ub 256` | **21.9** | **25.6** | **16.7** | **21.4 (-8%)** | 66% | 22,781 MiB |

Prefill ~380 tok/s both, hotspot 99°C, 0 evicted. Raw data and exact command:
[`../../results/20260926-mtp-n3-depth/README.md`](../../results/20260926-mtp-n3-depth/README.md#n4-at-240k-on-the-exact-adopted-flags--ub-256).

- **n=3 stays adopted; n=4 loses at 240K depth too**, not just at the 128K empty-context
  screening.
- **Generated text is not bit-identical at temperature 0** across n=2/n=3/`-ub 256` for the essay
  and code tasks (copy is identical): batched verification of different draft sizes changes
  floating-point rounding, and greedy decoding eventually diverges. Retrieval-quality results
  must therefore be validated on the exact adopted flags rather than assumed from a
  differently-configured run — see the "exact adopted config" confirmation in
  [`depth.md`](depth.md#quality-ruler-style-200k-q8q8-mtp).

## Community probe A/B at 262K, empty context (2026-09-27)

The [sudoingX/qwen38-mtp](https://github.com/sudoingX/qwen38-mtp) community table measures MTP
with one fixed instrument (`probe.py`: three short prompts × three runs, 400 tokens, thinking
off) and a strict contract (same serving flags in both arms, `--parallel 1`, medians of ≥3). Ran
it **unmodified** (commit `1e514a8`) on the adopted `262k-q8q51-mtp` flags through
[`bench/probe_ab.py`](../../bench/probe_ab.py): three complete passes per arm, row = median of
the three pass medians, acceptance from the server log with warm-ups excluded.

| Arm | Row tok/s | Code / prose / Bash | vs. spec-off | Acceptance |
|---|---:|---|---:|---:|
| spec off | 37.2 | 36.9 / 37.3 / 37.1 | — | — |
| n=2 | 68.6 | 76.5 / 59.3 / 68.6 | +84% | 0.80 |
| **n=3** (adopted) | **68.9** | 82.1 / 51.9 / 68.9 | **+85%** | 0.72 |
| n=4 | 66.9 | 87.1 / 46.3 / 66.9 | +80% | 0.62 |
| n=3, p-min 0.60 | 66.2 | 78.2 / 46.7 / 66.2 | +78% | 0.85 |
| n=3, p-min 0.75 | 59.8 | 79.2 / 45.1 / 59.8 | +61% | 0.91 |

- n=2 and n=3 tie at empty context (pass-to-pass noise ±2 tok/s); n=3 remains the default
  because it wins at the operating depth (section below and "MTP n=3 confirmed at depth").
- Deeper drafts keep paying on code and lose on prose at every step, the same shape as the other
  24 GB cards in that table.
- `--spec-draft-p-min` trades speed for acceptance on this card. Not adopted.

Raw data and environment: [`../../results/20260927-probe-ab-262k/`](../../results/20260927-probe-ab-262k/).

## MTP vs. spec-off at 240K fill, adopted profile (2026-09-27)

The spec-off reference on the exact adopted flags (`hip-kvmix`, KV q8_0/q5_1, `-ub 256`) had
never been measured at depth (`depth.md` listed it as missing). `bench/spec_depth_bench.py`,
240K fill, essay/copy/code, temperature 0, 400 output tokens, **3 warm repetitions** per task
(medians), plus a spec-off KV q8_0/q8_0 control on the same engine.

| Variant | Essay | Copy | Code | Mean | vs. spec-off (same KV) | Acceptance | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| spec off, q8_0/q5_1 | 11.1 | 11.2 | 11.2 | 11.2 | — | — | 20,102 MiB |
| **MTP n=3, q8_0/q5_1** (adopted) | **24.2** | **27.0** | **18.8** | **23.3** | **+109%** | 0.69 | 22,631 MiB |
| spec off, q8_0/q8_0 (control) | 14.9 | 14.9 | 15.0 | 14.9 | — | — | 21,381 MiB |

- **MTP more than doubles decode at the adopted profile's operating depth.** The relative gain
  is larger than at empty context (+85%), not smaller.
- **Spec-off pays for V q5_1**: -25% vs. V q8_0 at the same depth and engine. The n=3 figure
  reproduces the 2026-09-26 adopted-flags measurement (23.3 tok/s mean), so the MTP arm is stable
  across days.
- Against the q8_0/q8_0 spec-off control, the adopted profile is still +57% at 240K while fitting
  the full 262K window.
- Not measured: MTP n=3 with KV q8_0/q8_0 at 240K (262K + MTP + q8/q8 is not reliable on this
  card, see `depth.md`), so how much V q5_1 costs *with* MTP is not isolated.

Raw data: [`../../results/20260927-depth-240k-none-vs-n3/`](../../results/20260927-depth-240k-none-vs-n3/).

## Investigation notes on nearby forks (not adopted)

- **Lemonade b1331** (llama.cpp base ≈ b11170): its build workflow does not enable
  `GGML_CUDA_FA_ALL_QUANTS`, so it almost certainly doesn't support KV q8_0/q5_1 with FlashAttention.
  A/B against it was dropped for the target profile.
- **nasone32 `llama.cpp-RDNA3-7900xtx-opt`**: based on an upstream snapshot older than b11160, no
  binaries provided. Its FlashAttention patches target RDNA3.5/RDNA4 or prefill; its sparse-attention
  patch is for a different architecture (`qwen4exp`, not Qwen3.8) and its cmake doesn't enable
  `FA_ALL_QUANTS`. Nothing in it attacks long-context generation on gfx1100. **Discarded.**
- Checked against the latest release (b11170, 2026-09-24): no commit between b11160 and b11170
  touches MTP, the draft path, or HIP.

## Open questions

- ~~MTP acceptance rate with real agent-style tool use at ~190K (temperature 1, multiple seeds)~~ —
  answered 2026-09-30: **0.66** over 186,582 drafted tokens, see
  [`agent-traffic.md`](agent-traffic.md). Original note: the synthetic Wikipedia-summarization benchmark used above is a pessimistic proxy — a third-party
  report on a different setup saw 85-93% acceptance with real agent traffic (see `depth.md`).
- How much V q5_1 costs *with* MTP: spec-off pays 25% for it at 240K (vs. V q8_0), but MTP n=3
  with KV q8_0/q8_0 at 262K is not reliable on this card, so it would have to be measured at a
  smaller window (~224K), which gives up the context the default profile exists for.
- Whether ngram-mod stacked on MTP n=3 helps agentic editing at empty context and at 240K without
  hurting reasoning (prepared, not run; see "n-gram stacked on MTP: how llama.cpp combines them").
- Whether a future llama.cpp release picks up #27282 (shared MTP compute arena) or #26038, which
  would reduce MTP's VRAM/compute overhead at depth.

## History

- **2026-09-24**: MTP vs. DFlash2 vs. n-gram measured with an empty context (table above). MTP n=2
  selected as the default speculative-decoding profile.
- **2026-09-25**: VEC/TILE kernel-selection hypothesis formed and confirmed by an independent fork;
  vec4 patch tested and discarded (slower); DFlash2 and the "native q8" fork measured directly at
  190K and both discarded. This supersedes the empty-context-only comparison above for any
  long-context decision — see `depth.md` for the depth-specific throughput numbers.
- **2026-09-25, evening**: `-ub` and MTP n=3/`--spec-draft-p-min` measured at depth (128K fill,
  272 W) for the first time — `-ub 512` confirmed optimal, p-min 0.3 within noise, n=3
  content-dependent and not adopted as the default.
- **2026-09-26**: MTP n=3 re-measured at 190K and 240K fill (the two long-context profiles' actual
  operating depths) — wins across all three task types at both depths (+9-11% mean tg), superseding
  the 128K-fill "content-dependent, not adopted" call; adopted as the new default MTP draft length.
- **2026-09-26, later**: n=4 re-checked at 240K on the exact adopted flags (`-ub 256`) — still
  loses to n=3 (-8% mean tg), confirming the 128K-fill screening's call at depth too. Also found
  generated text is not bit-identical across n=2/n=3/`-ub 256` at temperature 0 for essay and
  code; retrieval quality re-validated on the exact adopted flags (`depth.md`), 8/8 at 240K. The
  68/68 total is pooled across configurations.
- **2026-09-27**: ran the sudoingX/qwen38-mtp community `probe.py` A/B on the adopted profile
  (empty context: n=3 +85%, n=2 ties, n=4 and p-min lose) and measured the missing spec-off
  reference at 240K fill: MTP n=3 is +109% there, correcting the earlier "gain shrinks at depth"
  conclusion (it was measured against a q8_0/q8_0 spec-off baseline).
- **2026-09-29**: read how llama.cpp combines n-gram drafting with MTP (fixed priority, no gating,
  `--spec-draft-n-max` does not cap ngram-mod) and prepared the n=3 ngram-mod/ngram-map A/B; not
  run.
- **2026-09-30, moved from "Current conclusion"** (superseded statements, kept for the record):
  - Older finding, empty context (superseded at depth by n=3): before the depth-specific
    measurements, `--spec-draft-n-max 2` looked like the best overall option and used the least
    VRAM: no separate draft model needed, the head ships inside the GGUF (`-mtp`). With an empty
    context: **+50-60%** generation speed (39 → 58-69 tok/s depending on task).
  - MTP n=3, first measured at 128K fill (272 W): strongly content-dependent — +17% on literal
    copy, ≈ on code, small essay gain — but acceptance drops 11 points vs. n=2 (75% → 64%). At
    that depth it was **not adopted** as the default (later superseded by the 190K/240K
    confirmation). `--spec-draft-p-min 0.3` is within noise of plain n=2 at the same depth — not
    adopted. See "`-ub` and MTP screening at 128K fill" above.
  - The earlier "+15-50% at depth" reading of MTP's gain compared against a KV q8_0/q8_0 spec-off
    baseline; spec-off with the adopted V q5_1 is 25% slower than with V q8_0 at 240K (11.2 vs.
    14.9 tok/s), so that baseline flattered spec-off (corrected 2026-09-27).
