# 2026-09-26 — Speed round 4: Vulkan vs. HIP depth screen

**Measures**: whether Vulkan closes the generation gap to HIP (`hip-kvmix`) at depth, as a
candidate lever for the `262k-q8q51-mtp` default profile's slow long-context decode. `llama-bench`,
Qwen3.8-27B GSQ-RCO IQ3_S-mtp, build b11160, 272 W power cap, `perf_level=auto`,
`-fa 1 -ctk q8_0 -ctv q5_1 -ub 256 -p 512 -n 64 -d 0,65536,131072 -r 1`. Vulkan run used the
official `ubuntu-vulkan` b11160 binary (RADV NAVI31, `KHR_coopmat`); HIP run used `hip-kvmix`
(ROCm 10 compiler, see `docs/measurements/engines.md`). A short diagnostic pass followed
(`-p 512 -n 32 -r 1`, depth 0, `-ub 256`/`-ub 512` × K/V `q8_0/q8_0`/`q8_0/q5_1`) to isolate whether
the collapse seen at `-ub 256` was specific to the K/V type. Memory clock (`pp_dpm_mclk`) and
hotspot were logged every ~5 s throughout.

## V1: HIP vs. Vulkan, `-ub 256`

| Backend | pp512 | tg64 | pp512 @64K | tg64 @64K | pp512 @128K | tg64 @128K |
|---|---:|---:|---:|---:|---:|---:|
| HIP `hip-kvmix` | 856.57 | 37.56 | 544.59 | 23.86 | 385.52 | 16.65 |
| Vulkan `ubuntu-vulkan` | 160.07 | 11.04 | 126.53 | 10.64 | — | — |

Vulkan was stopped (killed, exit 143) after the 64K depth: at its measured prefill speed, the
128K-depth case would have taken roughly another 45 minutes. Memory clock (`pp_dpm_mclk`) sat at
**456 MHz in 93 of 118 Vulkan monitor samples** (1249 MHz in only 8), vs. ROCm's 1249 MHz seen in
47 of 48 samples in the 2026-09-24 baseline (`docs/measurements/engines.md`). Hotspot peaked 94°C.

## Diagnostic: `-ub 256` vs. `-ub 512`, depth 0 (Vulkan only, `-p 512 -n 32 -r 1`)

| `-ub` | K/V | pp512 | tg32 |
|---:|---|---:|---:|
| 512 | q8_0/q8_0 | 847.07 | 23.58 |
| 512 | q8_0/q5_1 | 834.88 | 23.22 |
| 256 | q8_0/q8_0 | 162.16 | 23.34 |
| 256 | q8_0/q5_1 | 162.57 | 23.37 |

**Vulkan prefill collapses ~5x at `-ub 256`**, independent of the V cache type (Vulkan's
`supports_op` accepts `q5_1` and mixed K/V without recompiling — see `docs/measurements/engines.md`).
Generation (tg32) stays flat at 23.2-23.6 tok/s across all four combinations at depth 0 — but the V1
run above shows tg varying 11.0-23.9 tok/s at the *same* `-ub 256`/K-V config, purely with which
memory-clock state (456/772/1249 MHz) the driver happened to be in during that sample window.

**Raw data**: `bench/res/v1-vulkan-depth-20260926-160341/` (`hip.md`, `vulkan.md`, `diag-*.md`,
`monitor.csv`, `run.log`) — local only, `bench/res` is git-ignored.

## Conclusion

**Inconclusive for decode at depth**, because the GPU memory clock was not pinned and Vulkan's
`-ub 256` prefill collapse (unrelated to the clock issue) means this screen didn't even reach a
depth where decode-at-depth could be judged fairly. A fair re-test needs `-ub >= 512` (to avoid the
prefill collapse) with the memory clock pinned at the root. **Not pursued further** this round:

- `-ub 512` costs ~350 MiB more process VRAM than the adopted `-ub 256`
  (`docs/measurements/memory.md`), while the current default profile leaves only **190 MiB** of
  system-wide VRAM headroom (`../20260926-ubatch256-262k/`) — not enough margin to try it safely at
  240K fill.
- Vulkan already reports ~1.7 GB less free VRAM than ROCm at startup (`--list-devices`: 22,781 MiB
  vs. 24,504 MiB free).
- Vulkan's prefill already fell off faster with depth than ROCm's in the 2026-09-24 baseline
  (`docs/measurements/engines.md`).
- MTP-on-Vulkan correctness is unverified on this stack.

Context (priority #1 per `AGENTS.md`) outweighs chasing this lever further. See
`docs/measurements/engines.md` for the updated Vulkan section and
`docs/measurements/depth.md` for the separate attention-bandwidth analysis of why HIP itself slows
down with depth.
