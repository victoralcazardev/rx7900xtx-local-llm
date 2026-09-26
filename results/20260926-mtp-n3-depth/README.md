# 2026-09-26 — MTP n=3 confirmed at depth (190K and 240K fill)

**Measures**: whether MTP `--spec-draft-n-max 3` — content-dependent and not adopted in the
2026-09-25 128K-fill screening (`speculative.md`) — wins at the actual long-context operating
depths of the 224K and 262K profiles. `bench/spec_depth_bench.py`, three task types
(essay/copy/code), temperature 0, 400 forced output tokens, 1 repetition (cold + warm identical),
272 W power cap.

## P6 — 224K window (`-c 229376`, KV q8_0/q8_0), 190K fill

Also includes `--spec-draft-p-min 0.8` (the @SergioSV96 community config, minus its q4_0 KV — see
`docs/SOURCES.md`).

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|
| n=2 (reference) | 24.0 | 28.0 | 21.1 | 24.4 | 76% | 22,733 MiB |
| **n=3** | **26.1** | **32.2** | **21.4** | **26.6 (+9%)** | 67% | 22,883 MiB |
| n=3 + `--spec-draft-p-min 0.8` | 26.7 | 31.6 | 20.6 | 26.3 | 96% | 22,883 MiB |

Prefill ~455 tok/s all variants. Hotspot 98°C, 0 evicted.

**Raw data**: `bench/res/spec-depth-20260926-110910-p6-n2/`,
`bench/res/spec-depth-20260926-111916-p6-n3/`,
`bench/res/spec-depth-20260926-112925-p6-n3-pmin08/` (local only, `bench/res` is git-ignored).

## P5b — 262K window (`-c 262144`, KV q8_0/q5_1), 240K fill

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|
| n=2 (reference) | 22.2 | 22.9 | 18.0 | 21.0 | 81% | 22,830 MiB |
| **n=3** | **25.7** | **26.9** | **17.6** | **23.4 (+11%)** | 71% | 22,980 MiB |

Prefill 400 tok/s, hotspot 99°C, 0 evicted.

**Raw data**: `bench/res/spec-depth-20260926-113943-p5b-262k-q8q51-n2/`,
`bench/res/spec-depth-20260926-115338-p5b-262k-q8q51-n3/` (local only).

**Conclusion**: **n=3 wins at depth on both profiles** (+9-11% mean tg), unlike the 128K-fill
screening in `speculative.md` where only literal copy favored n=3 — the earlier "content-dependent,
not adopted" call was scoped to that shallower depth. `--spec-draft-p-min 0.8` raises acceptance
(67%→96%) but not speed (26.6→26.3, within noise) — not adopted on its own. P5b's 240K mean tg
(23.4, later 23.3 with `-ub 256` — see `20260926-ubatch256-262k/`) meets the user's floor of ≥15
(target ≥17) with 0 evicted, closing the P5c decision criterion for the 262K default switch. See
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md) and
[`../../docs/DECISIONS.md`](../../docs/DECISIONS.md).
