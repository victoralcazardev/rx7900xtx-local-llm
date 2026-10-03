# 2026-10-03: long-context retrieval, full 5-document sample at 190K and 240K (T05)

Question: does the adopted profile keep exact retrieval on the full planned sample? Before this
run, 190K had 1 of 5 documents (on an earlier profile) and 240K had 2 of 5 on the exact flags
([`depth.md`](../../docs/measurements/depth.md)).

## Setup and command

Engine b11160 `hip-kvmix`, model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`, `-c 262144`, KV `q8_0`/`q5_1`,
MTP n=3, `-ub 256`, 272 W. `bench/longctx_quality.py` (Spanish multi-key retrieval; raw token prompts,
no chat template, no thinking), temperature 0, max 200 output tokens, `cache_prompt`:

```bash
cd bench && systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \
  BENCH_SERVER=... BENCH_MODEL=... BENCH_WIKI=... python3 longctx_quality.py --run --inhibitor-ok \
  --ctx 262144 --variants q8q51-mtp1 --depths 190000 240000 --docs 5 --mtp-n 3 --extra "-ub 256"
```

## Results

| Depth | Exact match | Field accuracy | Loops / truncated | Finish | Decode tok/s | Cold prefill tok/s |
|---|---|---|---|---|---|---|
| 190K | 20/20 | 1.0 | 0 / 0 | all `eos` | 31.2-34.8 | 429-434 |
| 240K | 20/20 | 1.0 | 0 / 0 | all `eos` | 27.6-29.5 | 379 |

5 documents x 4 questions per depth; follow-up questions reuse the document's KV. Peak process
VRAM 22,643 MiB.

## Conclusion

40/40 exact at 190K-240K on the adopted flags: the open "broader retrieval sample" question is
answered. This is a retrieval check, not evidence of coding quality.

**Raw data**: `summary-compact.jsonl` (per question: depth, document, expected/parsed answer,
match, timings; response text omitted), `metadata.json`.
