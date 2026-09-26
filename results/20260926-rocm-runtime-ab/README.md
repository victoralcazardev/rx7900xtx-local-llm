# 2026-09-26 — ROCm runtime A/B: TheRock 10.0.0 runtime vs. system ROCm 7.2.4

**Measures**: whether swapping the ROCm *runtime* libraries (not the compiler) changes speed,
closing the runtime-library question left open by the compile-vs-runtime split in
`docs/measurements/engines.md`. Engine `hip-kvmix` (own ROCm 10 compiler build, b11160), KV
q8_0/q8_0, `-fa 1`, ABA order to control for drift.

**Command**: `llama-bench -m <model>.gguf -ngl 999 -fa 1 -ctk q8_0 -ctv q8_0 -p 512 -n 128 -d
0,16384 -r 3` against the same `hip-kvmix` binary: once against the system ROCm 7.2.4 runtime
(reference, run twice for an A1/A2 bracket), once with `LD_LIBRARY_PATH` pointed at TheRock
10.0.0 `_rocm_sdk_core` libs (rocm_sysdeps + llvm libs; rocBLAS/hipBLAS still system 7.2.4).

**Files**: `summary.md` — extracted `llama-bench` rows per variant.

**Results** (tok/s):

| Variant | pp512 | tg128 | pp512 @d16384 | tg128 @d16384 |
|---|---:|---:|---:|---:|
| Reference A1 (ROCm 10 compiler, system ROCm 7.2.4 runtime) | 961.99 ± 27.04 | 37.90 ± 0.05 | 816.85 ± 11.29 | 35.75 ± 0.06 |
| ROCm 10 HIP runtime (TheRock `_rocm_sdk_core` libs via `LD_LIBRARY_PATH`) | 908.94 ± 103.16 | 37.20 ± 0.12 | 777.76 ± 71.35 | 35.41 ± 0.42 |
| Reference A2 | 951.79 ± 24.48 | 38.10 ± 0.08 | 808.99 ± 15.13 | 35.74 ± 0.04 |

**Conclusion**: the ROCm 10 runtime is 1-2% slower on `tg` and ~5% slower on `pp`, with much
higher variance (±103 vs. ±27 on pp @16K) — **rejected**, below the +3% adoption bar. Combined
with the 2026-09-24 finding that the ROCm 7.2.4 *compiler* costs -7.5% tg @16K
([`engines.md`](../../docs/measurements/engines.md)), the current combo (ROCm 10 compiler + ROCm
7.2.4 runtime) is the best of the three tested so far.

**Pitfalls found**: the full ROCm 10 venv `_rocm_sdk_devel/lib` aborts at init (rocBLAS has no
gfx1100 `TensileLibrary`: the arch-specific libraries wheel was never installed); a partial
`LD_LIBRARY_PATH` missing `rocm_sysdeps` makes llama.cpp silently fall back to CPU (2.8 tok/s) —
always check `--list-devices` / the backend column in the log before trusting a run.

**Side data point**: 303 W → 272 W costs ~3.4% tg128 at empty context (39.35 → 38.0 tok/s; the
303 W value is from a single earlier run the same morning, not a controlled A/B) — see
[`thermals-power.md`](../../docs/measurements/thermals-power.md).
