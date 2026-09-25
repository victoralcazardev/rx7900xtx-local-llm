# Depth matrix at 262K target, 128K/240K (extracted from server logs, not copied raw)

`llama-server`, context filled with real tokens from `wiki.train`, 400-token response. Raw logs
(`profundo-P1..P5...log`) are console `slot print_timing` output and are not published here (see
`../../docs/BENCHMARK-FORMAT.md`); this is the final timing line from each, plus fdinfo/total-VRAM
readings noted in the session log.

Profile: IQ3_S-mtp, `-c 262144`, KV `q8_0/q5_1` unless noted, MTP n=2 unless noted, no vision,
`-np 1`.

| Case | Prompt tokens | Mean pp | tg | MTP acceptance | Peak total VRAM* | GTT at end |
|---|---:|---:|---:|---:|---:|---:|
| P1 q8/q5_1 + MTP (ROCm 10 kvmix) | 130,250 | 586 | 27.5 | 58% | 24,260 MiB | 537 MiB |
| P2 q8/q5_1 + MTP (ROCm 10 kvmix) | 239,314 | 430 | 23.8 | 90% | 24,373 MiB | 542 MiB |
| P3 q8/q8, no MTP (official) | 130,250 | 607 | 23.7 | — | 23,112 MiB | 527 MiB |
| P4 q8/q8, no MTP (official) | 239,314 | 453 | 16.0 | — | 22,912 MiB | 525 MiB |
| P5 = P2 + `-ub 256` | 239,314 | 412 | 19.4 | 63% | 22,983 MiB | 1,304 MiB (spilled) |

\* Total VRAM includes the desktop, which varied ~0.3-1.1 GiB within the session — not directly
comparable across rows. See `../../docs/measurements/memory.md` for the per-process fdinfo method
used in later measurements.

See [`../../docs/measurements/depth.md`](../../docs/measurements/depth.md#depth-matrix-at-262k-target-128k--240k-llama-server-400-token-response)
for the discussion, including why P2's headline number was later corrected.
