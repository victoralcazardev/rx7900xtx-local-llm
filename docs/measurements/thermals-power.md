# Thermals and power

## Current conclusion

- **272 W (this card's driver minimum; stock 303 W) is the permanent power cap**, applied at boot
  by a systemd oneshot unit — procedure in [`../sop/power-cap.md`](../sop/power-cap.md). Headline numbers: [`../STATUS.md`](../STATUS.md).
- **272 W vs. 303 W at 190K** (see "272 W vs. 303 W at 190K" below): prefill is **~6% slower**
  (459 vs. 487 tok/s) and the hotspot peaks **7-8°C cooler** (99°C vs. 100-106°C). The thermal
  margin is worth more than the throughput at this depth.
- The reason for the cap: at the factory 303 W limit, long prefills at depth push the hotspot to
  100-106°C, leaving as little as 4°C before the firmware begins limiting frequency at 110°C (the
  junction critical limit — see the sensor table below).
- Project preference: keep the hotspot well below ~105°C in unattended runs; the bench scripts
  abort after 3 consecutive readings above 104°C by default.
- Care for the GPU (undervolt, broader tuning) is explicitly deprioritized as a standalone work
  item — the priority ordering is context > model quality > cache quality > speed; the permanent
  cap is the working default, not a tuning effort.

## Sustained-load temperatures (ROCm and Vulkan, 303 W)

Edge 71°C, junction (hotspot) 92°C, memory 82°C — all well below the critical limits (100/110/108°C
respectively; see the per-sensor limits below). On RDNA3, `fan1_input` reports 0 rpm even while the
fans are spinning; this is a known reporting gap, not a stopped fan.

## Long-prefill thermal ramp (long-context depth tests)

Long prefills (7-9 minutes at full 303 W) bring the hotspot to 100-106°C (edge 78-83°C) even when
starting from a cold GPU (edge ≤55°C). Two 240K-depth runs hit hotspot 102°C and 105°C respectively;
a 190K-depth quality-test prefill hit 106°C and was stopped by the operator (2026-09-25, at the
factory 303 W limit — see `depth.md`). This was not caused by clock throttling: the core held
2,500 MHz throughout. During one measurement campaign, a 108°C cutoff (operational, not a hardware
spec) aborted a second 240K case and a 200K case; the firmware itself limits frequency starting at
110°C regardless of any script-level cutoff.

By contrast, the 2026-09-25 concurrency measurements (see `concurrency.md`) — shorter, 32K-depth
prefills, run under a 272 W power cap — peaked at hotspot 95-98°C. This isn't a controlled A/B
against 303 W at the same depth (different depth, different workload), but it's consistent with the
272 W cap being cooler.

The bench scripts' own automated abort guard (the shared `Monitor` in `depth_bench.py`, reused by
`longctx_quality.py`, `spec_depth_bench.py` and `concurrency_bench.py`) aborts a run after 3
consecutive unsafe readings. Its hotspot threshold defaults to 104°C — below the ~105°C
unattended-run policy above, with a small margin — and is overridable per run via the
`BENCH_MAX_HOTSPOT_C` environment variable (see `bench/README.md`). The 106°C event described
above happened before this default existed (the guard was 108°C at the time, and the run was
stopped by the operator, not by the automated guard).

## 272 W vs. 303 W at 190K (2026-09-25)

The 190K-depth long-context-quality prefill (`depth.md`'s RULER-style test) ran once at each power
cap, same profile (`-c 204800`, KV q8/q8, MTP n=2):

| Power cap | Prefill (`prompt_per_second`) | tg (min-max) | Peak hotspot |
|---|---:|---|---:|
| 303 W (factory default) | 487 tok/s | — | 100-106°C |
| 272 W (driver minimum) | 459 tok/s (**−6%**) | 24.3-29.2 tok/s | 99°C (**7-8°C cooler**) |

This isn't a fully controlled A/B (different runs, different days, single sample each side — see
`docs/BENCHMARK-FORMAT.md` "n (repetitions)"), but it directly answers the open question below:
**272 W costs about 6% of prefill throughput at 190K and buys back most of the thermal margin** —
the 106°C event that started this policy doesn't reproduce at 99°C peak. See
[`../../results/20260925-longctx-quality-200k/`](../../results/20260925-longctx-quality-200k/) and
`depth.md`'s "Context-window ladder" (224K/240K, also measured at 272 W: hotspot 98-101°C).

## Sensor limits (read from `/sys/class/hwmon`, no sudo needed)

| Sensor | Critical | Emergency |
|---|---:|---:|
| Memory | 108°C | 113°C |
| Junction (hotspot) | 110°C | 115°C |
| Edge | 100°C | 105°C |

Power: 303 W factory default, 272 W minimum, 350 W maximum. The ~94-95°C memory temperature seen
while generating leaves ~13°C of margin; the ~105°C hotspot seen during long prefills is within 5°C
of the junction critical limit. These limits are read from this specific card's firmware, not a
universal AMD spec — a different card may report different values.

## Power limit (`power1_cap`)

The power limit is read and set via sysfs, `/sys/class/drm/card*/device/hwmon/hwmon*/power1_cap*`
(microwatts): `power1_cap` is the active limit, `power1_cap_min`/`power1_cap_max` bound it
(272 W/350 W on this card), and `power1_cap_default` is the factory value (303 W). **Writing
`power1_cap` needs root**, and the value **resets to `power1_cap_default` on reboot** — it is not
persisted by the driver. As of 2026-09-25, the power cap on this machine is set to 272 W.

**Setting and persisting it**: procedure (manual command, verification, the systemd oneshot unit that applies it at boot) in [`../sop/power-cap.md`](../sop/power-cap.md).

Because the cap is not persisted, the shared bench code (`depth_bench.check_power_cap`, reused by
`concurrency_bench.py` and `longctx_quality.py`) reads the active cap from sysfs before a run —
for every AMD card found by globbing `card*/device/hwmon/hwmon*/power1_cap`, not a fixed
card/hwmon index and not just the first match — records all of them in that run's metadata/command
JSON, and prints a warning to stderr for each card whose active cap is above the optional
`BENCH_EXPECT_POWER_CAP_W` value (an invalid value is ignored with a warning, not a crash) for a
deep run (depth or `-c` ≥ 128K). It never writes `power1_cap` itself. See `bench/README.md`.

## Power draw at 240K, and what is left below 272 W (2026-10-03)

Telemetry from the 240K `n3-map` run at temperature 1 (b11371, adopted flags; `power1_average`
sampled by the bench monitor): median **271 W in prefill (2,590 samples) and 271 W in decode
(818 samples)**, maxima 309 W / 303 W. Decode at depth is therefore **power-limited at the 272 W
cap**, not only prefill. 272 W is the driver minimum (`power1_cap_min`), so the cap cannot go lower.

The remaining levers are a core-clock cap and a voltage offset through `pp_od_clk_voltage`, which
does not exist on this machine: overdrive is off (`ppfeaturemask` `0xfff7bfff`, bit `0x4000`
clear). Enabling it needs a kernel parameter and a reboot
([procedure](../sop/power-cap.md#below-272-w-clock-cap-and-undervolt)). Because decode is
power-limited, an undervolt should give the same or higher clocks at 272 W (same or better tg,
lower hotspot); a clock cap trades speed for J/token. Neither is measured here; no published
llama.cpp undervolt benchmark for this card was found. Test plan: T17 (greedy output hash after
every step, since an unstable compute undervolt can corrupt output silently).

## Open questions (future work, not prioritized this session)

- Undervolting / clock cap (needs overdrive, see above) and `pp_power_profile_mode` COMPUTE
  profile on Vulkan — not attempted.
- Whether 272 W changes throughput/temperature at 240K+ the same ~6%/7-8°C it does at 190K — only
  measured directly at 190K (this section) and by proxy at 224K/240K (`depth.md`'s ladder, no 303 W
  comparison at those depths).

## History

- **2026-09-24**: baseline sustained-load temperatures measured (ROCm and Vulkan, 303 W); all well
  inside limits.
- **2026-09-24/25**: long-prefill hotspot ramp observed during 240K/200K depth campaigns; operational
  108°C cutoff added to the measurement scripts (see `depth.md`); firmware sensor limits read
  directly from hwmon.
- **2026-09-25**: a 190K-depth quality-test prefill at 303 W reached hotspot 106°C and was stopped
  by the operator; power cap set to 272 W (driver minimum) for subsequent deep-prefill runs;
  concurrency measurements at 272 W (32K depth, see `concurrency.md`) peaked hotspot 95-98°C.
  Whether 272 W changes 190K throughput/temperature vs. 303 W is still pending.
- **2026-09-25**: lowered the shared bench `Monitor`'s hotspot abort threshold from 108°C to
  104°C by default (`BENCH_MAX_HOTSPOT_C`), and added a pre-run power-cap check
  (`depth_bench.check_power_cap`) that records the active `power1_cap` in run metadata and warns
  on stderr if a deep run (128K+) is above `BENCH_EXPECT_POWER_CAP_W`.
- **2026-09-25, evening**: 272 W vs. 303 W measured directly at 190K (−6% prefill, 7-8°C cooler
  hotspot) and by proxy at 224K/240K (`depth.md`'s context-window ladder, hotspot 98-101°C); 272 W
  adopted as the **permanent** power cap (not just for deep-prefill tests) and applied via a
  systemd oneshot unit instead of a manual per-boot command; `check_power_cap` hardened to check
  every AMD card instead of just the first glob match, and to warn instead of crash on an invalid
  `BENCH_EXPECT_POWER_CAP_W` (see `bench/depth_bench.py`).
- **2026-09-30, moved from "Current conclusion"** (state before the 272 W decision, kept for the
  record): sustained load at the factory 303 W power limit stays well inside the card's critical
  limits, but long prefills at depth push the hotspot to 100-106°C, leaving as little as 4°C of
  margin before the firmware begins limiting frequency at 110°C. Nothing in that session's
  measurements exceeded a safe operating range, but there was little headroom left during long
  prefills. On 2026-09-25 a 190K-depth prefill at 303 W reached hotspot 106°C and was stopped by
  the operator (see `depth.md`'s quality test); deep-prefill tests (128K+) then ran under a 272 W
  cap, and the cap was later made permanent and set via a systemd oneshot unit instead of a manual
  per-boot command.
