# 2026-09-25 — long-context retrieval quality, `200k-q8q8-mtp` (RULER-style, Spanish)

**Measures**: whether retrieval quality holds as the context fills, for the `200k-q8q8-mtp`
profile (`-c 204800`, KV q8/q8, MTP n=2). `bench/longctx_quality.py`: a Spanish-language
multi-key retrieval test (deliberately Spanish — see the script's own docstring and
[`../../docs/STYLE.md`](../../docs/STYLE.md) §1), 5 documents × 4 questions per depth,
temperature 0. See [`../../docs/measurements/depth.md`](../../docs/measurements/depth.md)
"Quality (RULER-style)".

**Conditions**: engine `hip-kvmix` (own ROCm 10 build), Qwen3.8-27B GSQ-RCO IQ3_S-mtp,
`-c 204800`, KV `q8_0/q8_0`, MTP `--spec-draft-n-max 2`, temperature 0, 200-token cap per answer.
32K and 128K ran at the factory 303 W power limit; 190K ran under the 272 W power cap (set after
a first 190K attempt at 303 W was stopped by the operator on thermal grounds — see
`../../docs/measurements/thermals-power.md`).

**Command**: `bench/longctx_quality.py --ctx 204800 --variants q8q8-mtp1 --depths 32000 128000
190000` (32K/128K run); `bench/longctx_quality.py --ctx 204800 --variants q8q8-mtp1 --depths
190000` (190K re-run at 272 W, stopped after document 0's 4 questions — see "Caveats" below).

**Files** (personal machine paths replaced with placeholders; the full documents/prompts and raw
SSE streams are not published — only the extracted per-question fields, matching
`docs/BENCHMARK-FORMAT.md` "How `results/` is laid out"):

- `summary-32k-128k.jsonl` / `metadata-32k-128k.json` — 32K and 128K, 20 questions each (5
  documents × 4 questions), run at 303 W.
- `summary-190k-doc0.jsonl` / `metadata-190k-doc0.json` — 190K, document 0 only (4 questions),
  run at 272 W.

**Results**:

| Depth | Power cap | n | Exact match | Loops | tg (min-max) | Prefill (first request) |
|---:|---:|---:|---|---:|---|---:|
| 32,000 | 303 W | 20 | 20/20 | 0 | 64.1-67.2 tok/s | 853.5 tok/s |
| 128,000 | 303 W | 20 | 20/20 | 0 | 36.8-38.9 tok/s | 584.8 tok/s |
| 190,000 | 272 W | 4 | 4/4 | 0 | 24.3-29.2 tok/s | 459.1 tok/s |

**Total: 44/44 exact match, 0 loop detections.**

**Conclusion**: retrieval quality does not collapse anywhere measured from 32K to 190K fill of
the 200K window — every question answered exactly, no output loops. The 190K sample is partial
(1 of 5 planned documents, 4 of 20 planned questions) — parked by the user after this document
("si 200K funciona bien, podemos dejar 190K aparcado") rather than run to completion, since the
32K/128K result plus this single 190K document were judged sufficient evidence to stop chasing
190K specifically. The 272 W prefill at 190K is **~6% slower** than the 303 W reference at the
same depth (459 vs. ~487 tok/s — see
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md)'s 190K A/B at
303 W) and peaks the hotspot at 99°C instead of 100-106°C (see
`../../docs/measurements/thermals-power.md`). This is the evidence behind promoting
`200k-q8q8-mtp` past "quality test pending" in
[`../../docs/STATUS.md`](../../docs/STATUS.md) — see there and `depth.md` for the full context.

**Caveats**: single sample per question (no repetition); the 190K result covers only 1 of the 5
planned documents (a broader sample at 190K, and the remaining 16 questions, were not run — see
"parked" above); 32K/128K and 190K were measured under different power caps (303 W vs. 272 W),
so throughput isn't directly comparable across the three rows above (thermal/power effects on
speed are covered separately in `thermals-power.md`, not by this quality test).
