# 2026-09-29 — Vulkan vs. HIP with the GPU memory clock pinned

**Measures**: whether Vulkan closes the generation gap to HIP (`hip-kvmix`) once the GPU memory
clock is pinned at 1249 MHz. It closes the open item left by
`../20260926-speed-round4-vulkan-depth/`. `llama-bench` build b11160 (commit `70c4e1582`),
Qwen3.8-27B GSQ-RCO IQ3_S-mtp, 272 W power cap, kernel 7.2.8-1-cachyos, Mesa/RADV 26.2.3
(`vulkan-radeon 3:26.2.3-1`; the same Mesa as the 2026-09-26 screen, and the latest in the Arch
repos, so there was no newer stable Mesa to try). Args:
`-fa on -ctk q8_0 -ctv q5_1 -p 512 -n 64 -d 0,65536 -r 1`. Vulkan used `-ub 512` (avoids the
`-ub 256` prefill collapse); HIP `hip-kvmix` used `-ub 256` (the adopted profile's value). Vulkan
binary: the official `ubuntu-vulkan` b11160 (RADV NAVI31, `KHR_coopmat`). `pp_dpm_mclk` and
`pp_dpm_sclk` on `card1` were logged every 2 s. Single run each (`-r 1`). No MTP in `llama-bench`
(plain decode).

## Run A: `profile_peak` (confounded)

`power_dpm_force_performance_level=profile_peak`: mclk 1249 MHz in 151 of 151 samples. But
`profile_peak` also caps the core clock: HIP lost ~13% tg and ~18% pp vs. the 2026-09-26 `auto`
run with the same flags, so this run is confounded. Kept for the record only.

| Backend | pp512 | tg64 | pp512 @64K | tg64 @64K |
|---|---:|---:|---:|---:|
| HIP `profile_peak` | 701.47 | 32.58 | 451.67 | 20.14 |
| Vulkan `profile_peak` | 729.46 | 22.81 | 309.57 | 19.63 |

## Run B: `manual` + memory clock pinned (the clean run)

`power_dpm_force_performance_level=manual` and `echo 3 > pp_dpm_mclk` (memory pinned only, core
clock left dynamic): mclk 1249 MHz in 133 of 133 samples; sclk ranged ~2100-2371 MHz under load
(2371 MHz most common). Forcing mclk through sysfs did apply on this kernel (some reports say
manual powerplay is buggy on Navi3x; not observed here).

| Backend | pp512 | tg64 | pp512 @64K | tg64 @64K |
|---|---:|---:|---:|---:|
| Vulkan mclk pinned | 773.76 | 22.02 | 343.70 | 19.77 |
| HIP mclk pinned | 792.73 | 35.91 | 532.93 | 23.30 |
| *Ref: HIP `auto`, 2026-09-26* | 856.57 | 37.56 | 544.59 | 23.86 |
| *Ref: Vulkan `auto -ub 256`, 2026-09-26* | 160.07 | 11.04 | 126.53 | 10.64 |

## Conclusion

- **Pinning the memory clock nearly doubles Vulkan decode at 64K depth** (10.64 → 19.77 tok/s), so
  memory-clock throttling did explain Vulkan's collapse at depth. At depth 0 Vulkan tg is
  unchanged (~22-23 tok/s, same as the 2026-09-26 `-ub 512` diagnostic, 23.58).
- **Even with the clock fixed, HIP wins everywhere**: tg +63% at depth 0 (35.91 vs. 22.02), tg
  +18% at 64K (23.30 vs. 19.77), pp +55% at 64K (532.93 vs. 343.70). That is before MTP, which
  gives +109% on HIP and is unverified on Vulkan.
- So "Vulkan loses because the memory clock drops" is only half right: the clock explains the
  depth collapse, not the whole gap. The depth-0 decode gap (~22 vs. ~36-38 tok/s) is a
  backend/kernel difference on this model (hybrid Qwen3.8 27B, IQ3_S), not clocks. Community
  reports of Vulkan beating ROCm on tg for small dense Q4_0 models
  ([llama.cpp#20934](https://github.com/ggml-org/llama.cpp/issues/20934)) are the opposite
  direction — don't generalize either way.
- Pinning mclk does not help HIP (under `auto` it already holds 1249 MHz and scored equal or
  better). Keep `auto`; **no config change**.
- **Decision**: Vulkan re-test closed; Vulkan stays reference-only for this model. Re-open only if
  a future llama.cpp/Mesa build shows a large Vulkan decode change.

## Reproduce

```sh
echo manual | sudo tee /sys/class/drm/card1/device/power_dpm_force_performance_level
echo 3 | sudo tee /sys/class/drm/card1/device/pp_dpm_mclk
# run llama-bench with the args above
echo auto | sudo tee /sys/class/drm/card1/device/power_dpm_force_performance_level   # revert
```

The card index may differ (`card1` here); the setting also reverts on reboot.

**Raw data**: `bench/res/v2-vulkan-mclk-pinned-20260929/` with `profile_peak/` and `manual_mclk3/`
(each: `vulkan-ub512.md`, `hip-ub256.md`, `*.err`, `mclk.log`, `run.sh`) — local only, `bench/res`
is git-ignored. See `docs/measurements/engines.md` for the measurement write-up.
