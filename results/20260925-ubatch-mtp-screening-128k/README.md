# 2026-09-25 — `-ub` and MTP screening at 128K fill (272 W cap)

**Measures**: fast, cool screening at 128K fill depth (of the 200K `-c 204800` window) for two
levers before confirming a winner at 190K depth: prefill micro-batch size (`-ub`) and MTP draft
tuning (`--spec-draft-n-max 3`, `--spec-draft-p-min 0.3`). 128K fill is used only to screen —
`-ub`'s VRAM effect only shows clearly near a full context, so any change here still needs
confirming near 190-200K before adoption (see
[`../../docs/measurements/depth.md`](../../docs/measurements/depth.md) and
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md)).

**Conditions**: engine `hip-kvmix` (own ROCm 10 build), Qwen3.8-27B GSQ-RCO IQ3_S-mtp,
`-c 204800`, KV `q8_0/q8_0`, `-np 1`, power cap 272 W (this card's driver minimum — see
`../../docs/measurements/thermals-power.md`). Prompt filled to 127,982-127,987 exact tokens
(three task types: essay/summarize, literal copy, code), temperature 1 (vendor sampling), 400
forced output tokens (`ignore_eos`), 2 repetitions per task (rep 1 = cold prefill, rep 2 = warm
cache via `cache_prompt`) — see [`../../docs/BENCHMARK-FORMAT.md`](../../docs/BENCHMARK-FORMAT.md).

**Command**: `bench/spec_depth_bench.py --depth 128000 --ctx 204800 --kv q8_0 --reps 1` with
`--variants n2` (base and `--extra "-ub 1024"`/`"-ub 2048"`), `--variants n3`, and `--variants n2
--extra "--spec-draft-p-min 0.3"`.

**Files** (personal machine paths replaced with placeholders; per-request SSE streams are not
published — see `docs/BENCHMARK-FORMAT.md` "How `results/` is laid out"):

- `summary-base-n2.jsonl` / `command-base-n2.json` — MTP n=2, `-ub 512` (default).
- `summary-ub1024.jsonl` / `command-ub1024.json` — MTP n=2, `-ub 1024`.
- `summary-ub2048.jsonl` / `command-ub2048.json` — MTP n=2, `-ub 2048`.
- `summary-n3.jsonl` / `command-n3.json` — MTP n=3, `-ub 512`.
- `summary-pmin03.jsonl` / `command-pmin03.json` — MTP n=2, `--spec-draft-p-min 0.3`, `-ub 512`.

**Results** (tg = mean of the two repetitions' `timings.predicted_per_second`; accept = sum of
`draft_n_accepted` ÷ sum of `draft_n` across both repetitions and all three tasks; pp = cold
prefill, `timings.prompt_per_second` on the first, cache-empty request):

| Variant | pp | tg essay | tg copy | tg code | Accept | Peak VRAM | Peak hotspot |
|---|---:|---:|---:|---:|---:|---:|---:|
| base (n2, `-ub 512`) | 552.6 | 30.6 | 36.0 | 27.7 | 75% | 21,648 MiB | 96°C |
| `-ub 1024` | 551.7 | 30.1 | 35.9 | 27.6 | 75% | 22,238 MiB (+590 MiB) | 98°C |
| `-ub 2048` | 543.4 (−1.7%) | 30.6 | 35.8 | 26.7 (−3.6%) | 74% | 23,420 MiB (+1,772 MiB) | 98°C |
| n3 | 551.3 | 31.3 (+2%) | 42.1 (+17%) | 27.5 (≈) | 64% | 21,797 MiB | 98°C |
| `--spec-draft-p-min 0.3` (n2) | 551.8 | 31.3 | 36.4 | 27.5 | 78% | 21,647 MiB | 98°C |

GTT and evicted VRAM stayed negligible/zero in every case (no spill).

**Conclusion**: `-ub 512` (the default) stays optimal at this depth — `-ub 1024` gains nothing and
costs 590 MiB, `-ub 2048` is strictly worse (slower prefill, slower code generation, +1.8 GiB
VRAM). This supersedes the earlier `pp2048`-only, empty-context reading in
[`../../docs/measurements/engines.md`](../../docs/measurements/engines.md) ("within ±1% of
default"), which never exercised `-ub` at depth. `--spec-draft-p-min 0.3` is within noise of plain
n=2 — not adopted. MTP n=3 is the first n≥3 data point measured at depth: strongly content-
dependent (+17% on literal copy, ≈ on code, small essay gain), but costs 11 points of acceptance
vs. n=2 (75% → 64%) — not adopted as the default, but a candidate for copy/refactor-heavy work.
See [`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md) for the
full discussion.
