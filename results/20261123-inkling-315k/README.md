# Inkling-2-Mini q8d on maya-ik2 above 262K: 315,392 adopted, 352,256 too tight (2026-11-23)

Goal: the largest context that keeps about 1.5 GiB of the 24 GiB card free, for omp with compaction at 75%.

| What | Value |
|---|---|
| Model | `Inkling-2-Mini-Uncensored-IQ4_NL-q8dense.gguf` (`inkling2-mini-unc-q8d`, sha256 `375eea1b...`) |
| Engine | GodGMN `maya-ik2` `hip-port` `f472e94`, `--serve-ik2 --chunk 2048`, the launcher's `262k-maya` env (FP8 KV, `IK2_PAGED_KV=1`, `IK2_RESIDENT_ONLY=1`) |
| Test | the port's `tests/ik2_retrieval.py`: a seeded four-word phrase at a given depth of a GSM8K-distractor prompt of `ctx - 256` tokens, `--direct-answer`, greedy, cold prefill |
| Memory | `mem_info_vram_used` of the whole device (desktop included) sampled every 2 s; card total 24,560 MiB |
| Conditions | RX 7900 XTX at the 272 W cap, desktop open |
| Script | [`raw/run.sh`](raw/run.sh) `<ctx> <percent>` |

| Context | Depth | Retrieval | Cold prefill | Peak VRAM | Free |
|---|---|---|---|---|---|
| 352,256 | 50% | exact | 328.6 s | 23,577 MiB | 983 MiB |
| 315,392 | 5% | exact | 271.2 s | 22,874 MiB | 1,686 MiB |
| 315,392 | 50% | exact | 271.7 s | 22,874 MiB | 1,686 MiB |
| 315,392 | 95% | exact | 272.1 s | 22,874 MiB | 1,686 MiB |

Decision: 315,392 (`315k-maya`, the launcher default); 352,256 leaves about 1.0 GiB, under the 1.5 GiB target.
Not measured: decode speed at 300K+, and any task quality beyond literal retrieval.
