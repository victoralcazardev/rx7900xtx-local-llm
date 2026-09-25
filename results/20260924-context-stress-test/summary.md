# Context-full stress test (extracted from server + fdinfo logs, not copied raw)

Context filled with N real tokens (`wiki.train`), a response requested, VRAM sampled every second.
Total VRAM including desktop, on a 24,560 MiB card. Raw logs (`estres-*.log`) are console output and
are not published here (see `../../docs/BENCHMARK-FORMAT.md`).

| Case | Prompt tokens | Mean pp | tg at that depth | Peak VRAM | Result |
|---|---:|---:|---:|---:|---|
| 128K, q8/q8, vision, MTP n=2 | 104,185 | 608 tok/s | 30.7 tok/s (66% acc.) | 20,455 MiB | OK |
| 262K, q8/q8, no vision, no MTP | 182,132 | 521 tok/s | 19.3 tok/s | 22,347 MiB | OK |
| 262K, q8/q8, no vision, MTP n=2 (1st attempt) | ~104K of 182K | 640-740 | — | — | FAILED: Memory access fault by GPU |
| Same case (2nd attempt, LLAMA_ATTN_ROT_DISABLE=1) | 182,132 | 498 | 21.8 | 24,489 MiB | OK, 71 MiB free |
| Same case (3rd attempt, without the variable) | 182,132 | 498 | 23.2 | 24,512 MiB | OK, 48 MiB free |

See [`../../docs/measurements/depth.md`](../../docs/measurements/depth.md#context-full-stress-test-total-vram-including-desktop-24560-mib)
for the conclusion (VRAM margin, not a driver bug, is the failure mode).
