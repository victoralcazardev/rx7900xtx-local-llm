# VRAM breakdown at load (extracted from `-lv 4` logs, not copied raw)

`llama-server -lv 4` at 262K context, IQ3_S-mtp; one run per variant. Raw logs are console output
(`memoria-V1..V6...log`) and are not published here (see `../../docs/BENCHMARK-FORMAT.md`); this is
`common_memory_breakdown_print`'s final line from each, in MiB.

| Variant | Weights | KV | RS | Compute | MTP KV | MTP compute | Process VRAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| V1 q8/q5_1 + MTP, MTP KV f16 (default) | 11,160 | 7,424 | 449 | 1,360 | 1,024 | 324 | 22,073 |
| V2 q8/q5_1 + MTP, `-ctkd q8_0 -ctvd q8_0` | 11,160 | 7,424 | 449 | 1,360 | 544 | 1,360 | 22,499 |
| V3 q8/q8 + MTP, MTP KV q8 | 11,160 | 8,704 | 449 | 1,360 | 544 | 1,360 | 22,896 |
| V4 = V3 + `-ub 256` | 11,160 | 8,704 | 449 | 1,192 | 544 | 1,192 | 23,482 |
| V5 = V3 + `-ub 128` | 11,160 | 8,704 | 449 | 1,108 | 544 | 1,108 | 23,314 |
| V6 q8/q8, no MTP | 11,160 | 8,704 | 150 | 1,360 | — | — | 21,368 |

See [`../../docs/measurements/memory.md`](../../docs/measurements/memory.md#vram-breakdown-at-load--lv-4-log-262k-context-mib)
for the discussion (why MTP's draft KV stays at f16).
