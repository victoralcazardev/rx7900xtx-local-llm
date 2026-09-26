# 2026-09-26 — `-ub 256` on `262k-q8q51-mtp` n=3, and system VRAM headroom

**Measures**: whether a smaller `-ub` (physical batch size) trims process VRAM for the new
262K/MTP-n=3 default, and how much system VRAM margin the long-context profiles actually leave
once the desktop's own usage is accounted for. Same method as `20260926-mtp-n3-depth/`
(`bench/spec_depth_bench.py`, essay/copy/code, temperature 0, 400 forced output tokens, 1
repetition, 262,144 context, KV q8_0/q5_1, MTP n=3, 240K fill, 272 W).

## P10 — `-ub 256` vs. the `-ub 512` default (P5b n=3)

| Variant | Essay | Copy | Code | Mean | Accept | Peak process VRAM | pp | Hotspot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| n=3, `-ub 512` (P5b) | 25.7 | 26.9 | 17.6 | 23.4 | 71% | 22,980 MiB | 400 | 99°C |
| **n=3, `-ub 256`** | 24.4 | 26.9 | 18.6 | 23.3 | 71% | **22,630 MiB (-350)** | 380 (-5%) | 99°C |

0 evicted in both. **Raw data**: `bench/res/spec-depth-20260926-120803-p10-262k-n3-ub256/` (local
only, `bench/res` is git-ignored).

## System VRAM (all processes, `mem_info_vram_used`, 24,560 MiB total), peak

| Configuration | Peak used | Free |
|---|---:|---:|
| 224K, n=2, `-ub 512` | 24,426 MiB | 134 MiB |
| 262K, n=2, `-ub 512` | 24,548 MiB | 12 MiB |
| 262K, n=3, `-ub 512` | 24,534 MiB | 26 MiB |
| **262K, n=3, `-ub 256`** | **24,370 MiB** | **190 MiB** |

Desktop idle VRAM on this measurement day was ~1.5 GiB (other days ~0.8 GiB) — process VRAM never
evicted in any case, but system-wide headroom is thin regardless of `-ub`.

**Conclusion**: `-ub 256` is adopted for the `262k-q8q51-mtp` default — it trims 350 MiB of
process VRAM and buys the most system-wide free VRAM of any configuration measured (190 MiB), at
a small prefill cost (-5%) and no generation-speed cost (23.3 vs. 23.4 tok/s mean, within noise).
**Correction**: `docs/measurements/depth.md`'s "~1.8 GiB system VRAM margin" figure for the 224K
profile was measured with a lighter desktop (~0.8 GiB idle) than this session's ~1.5 GiB — the
actual margin depends on what else is using the GPU, not just the profile. Recommendation:
**close heavy GPU applications (video players, browsers with GPU-accelerated video) before
long-context work**, regardless of profile. See
[`../../docs/measurements/memory.md`](../../docs/measurements/memory.md).
