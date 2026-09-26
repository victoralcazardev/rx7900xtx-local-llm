# 2026-09-26 — MTP n=3 confirmed at depth (190K and 240K fill)

**Measures**: whether MTP `--spec-draft-n-max 3` — content-dependent and not adopted in the
2026-09-25 128K-fill screening (`speculative.md`) — wins at the actual long-context operating
depths of the 224K and 262K profiles. `bench/spec_depth_bench.py`, three task types
(essay/copy/code), temperature 0, 400 forced output tokens, 1 repetition (cold + warm identical),
272 W power cap.

## MTP depth sweep — 224K window (`-c 229376`, KV q8_0/q8_0), 190K fill

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

## MTP depth sweep — 262K window (`-c 262144`, KV q8_0/q5_1), 240K fill

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|
| n=2 (reference) | 22.2 | 22.9 | 18.0 | 21.0 | 81% | 22,830 MiB |
| **n=3** | **25.7** | **26.9** | **17.6** | **23.4 (+11%)** | 71% | 22,980 MiB |

Prefill 400 tok/s, hotspot 99°C, 0 evicted.

**Raw data**: `bench/res/spec-depth-20260926-113943-p5b-262k-q8q51-n2/`,
`bench/res/spec-depth-20260926-115338-p5b-262k-q8q51-n3/` (local only).

### n=4 at 240K on the exact adopted flags (`-ub 256`)

Repeated with `-ub 256` (adopted after the table above was measured — see
`20260926-ubatch256-262k/`), to compare n=4 against the adopted n=3 + `-ub 256` baseline instead
of the no-`-ub 256` n=3 row above. Same method: `bench/spec_depth_bench.py`, 262K window
(`-c 262144`, KV q8_0/q5_1), 240K fill, temperature 0, 400 forced output tokens, 1 repetition
(cold + warm identical).

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|
| n=3 + `-ub 256` (adopted, reference) | 24.4 | 26.9 | 18.6 | 23.3 | 71% | 22,630 MiB |
| **n=4** + `-ub 256` | **21.9** | **25.6** | **16.7** | **21.4 (-8%)** | 66% | 22,781 MiB |

Prefill ~380 tok/s both, hotspot 99°C, 0 evicted.

**Command**: `bench/spec_depth_bench.py --run --depth 240000 --ctx 262144 --kv q5_1 --reps 1
--variants none --extra "--spec-type draft-mtp --spec-draft-n-max 4 -ub 256"`.

**Conclusion**: n=3 stays adopted; n=4 loses at 240K just as it did at the 128K empty-context
screening (`speculative.md`).

**Non-bit-identical output note**: at temperature 0, generated text is **not bit-identical**
across n=2 / n=3 / `-ub 256` for the essay and code tasks (copy is identical) — batched
verification of different draft sizes changes floating-point rounding, and greedy decoding
eventually diverges downstream. Quality (exact-match retrieval) results must therefore be
validated on the exact adopted flags, not assumed from a differently-configured run — see
[`../20260926-longctx-quality-262k/README.md`](../20260926-longctx-quality-262k/README.md#exact-adopted-config-confirmation-mtp-n3--ub-256-2026-09-26).

**Conclusion**: **n=3 wins at depth on both profiles** (+9-11% mean tg), unlike the 128K-fill
screening in `speculative.md` where only literal copy favored n=3 — the earlier "content-dependent,
not adopted" call was scoped to that shallower depth. `--spec-draft-p-min 0.8` raises acceptance
(67%→96%) but not speed (26.6→26.3, within noise) — not adopted on its own. The 262K window's 240K
mean tg (23.4, later 23.3 with `-ub 256` — see `20260926-ubatch256-262k/`) meets the floor of ≥15
(target ≥17) with 0 evicted, one of the criteria for the 262K default switch. See
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md) and
[`../../docs/DECISIONS.md`](../../docs/DECISIONS.md).
