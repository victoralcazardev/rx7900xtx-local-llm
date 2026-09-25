# 128K and 240K with per-process fdinfo (extracted from telemetry, not copied raw)

Profile: IQ3_S-mtp, `-c 262144`, KV q8_0/q5_1, MTP n=2, no vision, `-np 1`, ROCm 10 kvmix engine.
Prompt from `wiki.train` (English) with an instruction to write an essay in Spanish, 1,500 forced
output tokens, followed by a warm turn (history + short question, 500 tokens). Raw telemetry/server
logs are not published (see `../../docs/BENCHMARK-FORMAT.md`).

## 128K (single sample)

262,144 reserved, no truncation, seed 43. MTP accepted 787 of 1,423 drafts (55.3%). Prefill
587.64 tok/s / 217.82 s; generation 26.99 tok/s / 55.53 s; full request 273.39 s. Per-process fdinfo
peak: load/ready 21,895.31 MiB VRAM; prefill 22,828.86; generation 22,828.96. GTT 8.07 MiB
throughout, 0 evicted. Hotspot peaked 98C in prefill, 95C in generation.

## 240K (repeated twice, same seed)

| Case | Prompt | pp | tg | MTP | Warm turn: reused/new | tg warm | Peak process VRAM | Process GTT | Evicted | Hotspot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240K (a) | 240,000 | 430 | 18.4 | 58% | 239,996 / 1,544 | 16.7 | 22,832 MiB | 8.1 MiB | 0 | 102C |
| 240K (b) | 240,000 | 428 | 18.4 | 58% | 239,996 / 1,544 | 17.2 | 22,832 MiB | 8.1 MiB | 0 | 105C |

A first 240K attempt (not shown) was aborted by the client at 67,584 of 240,000 prompt tokens (27%)
and is not a valid result.

See [`../../docs/measurements/depth.md`](../../docs/measurements/depth.md#128k-and-240k-with-fdinfo-and-the-aborted-first-240k-attempt)
and [`240k-with-fdinfo-repeated`](../../docs/measurements/depth.md#240k-with-fdinfo-repeated-q8q5_1--mtp-n2-262144-reserved)
for the conclusion (18.4 tok/s at 240K, below the 20 tok/s bar; this supersedes the earlier
single-sample 23.8 tok/s reading in `20260924-depth-262k-deep`).
