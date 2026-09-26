# Thermals and power

## Current conclusion

- Sustained load at the factory 303 W power limit stays well inside the card's critical limits, but
  long prefills at depth push the hotspot to 100-106°C, leaving as little as 4°C of margin before
  the firmware begins limiting frequency at 110°C (the junction critical limit — see the sensor
  table below). Nothing in this session's measurements exceeded a safe operating range, but
  there's little headroom left during long prefills.
- **2026-09-25**: a 190K-depth prefill at the factory 303 W limit reached hotspot 106°C and was
  stopped by the operator (see `depth.md`'s quality test). Project preference from this point on:
  keep the hotspot well below ~105°C in unattended runs. Deep-prefill tests (128K+) now run under a
  272 W power cap (this card's driver minimum — see "Power limit" below).
- **272 W vs. 303 W at 190K, now measured** (see "272 W vs. 303 W at 190K" below): prefill is
  **~6% slower** (459 vs. 487 tok/s) and the hotspot peaks **7-8°C cooler** (99°C vs. 100-106°C).
  **272 W is kept as the permanent power cap**, not just for deep-prefill tests — the thermal
  margin is worth more than the throughput at this depth.
- **272 W is now set via a systemd oneshot unit** (see "Power limit" below) instead of a manual
  per-boot command, so it survives a reboot without the operator remembering to re-run anything.
- Care for the GPU (lower power limit, undervolt) is **explicitly deprioritized** as a standalone
  work item — the priority ordering is context > model quality > cache quality > speed — but the
  190K/106°C event above makes a conservative, permanent power cap the working default, not a
  broader tuning effort.

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

**Setting it** (root, per boot — the hwmon index can change across reboots or driver reloads, so
resolve the exact path first instead of guessing it; on a multi-GPU host, filter `cap_path` down
to the AMD card actually running the benchmark instead of writing to every `power1_cap` match):

```bash
cap_path=$(ls /sys/class/drm/card*/device/hwmon/hwmon*/power1_cap)
echo "$cap_path"                              # confirm it resolved to the card you mean
echo 272000000 | sudo tee "$cap_path"
```

**Verifying it** (no root needed):

```bash
cat "$cap_path"
```

Because the cap is not persisted, the shared bench code (`depth_bench.check_power_cap`, reused by
`concurrency_bench.py` and `longctx_quality.py`) reads the active cap from sysfs before a run —
for every AMD card found by globbing `card*/device/hwmon/hwmon*/power1_cap`, not a fixed
card/hwmon index and not just the first match — records all of them in that run's metadata/command
JSON, and prints a warning to stderr for each card whose active cap is above the optional
`BENCH_EXPECT_POWER_CAP_W` value (an invalid value is ignored with a warning, not a crash) for a
deep run (depth or `-c` ≥ 128K). It never writes `power1_cap` itself. See `bench/README.md`.

### Making it permanent: a systemd oneshot unit

Since the manual command above has to be re-run after every reboot, the 272 W cap is applied by a
`systemd` oneshot unit that runs once at boot, instead of relying on the operator to remember it.
Both files are tracked in this repository, generic and with no personal machine paths:
[`scripts/systemd/gpu-power-cap.sh`](../../scripts/systemd/gpu-power-cap.sh) and
[`scripts/systemd/gpu-power-cap.service`](../../scripts/systemd/gpu-power-cap.service).

- Targets the card by **PCI device ID** (`1002:744c`, this GPU's vendor:device ID — stable across
  reboots and hwmon index renumbering, unlike `card*`/`hwmon*`), scanning every `card*/device` for
  that vendor/device pair instead of assuming a fixed card index.
- Writes the cap **only if it falls within the resolved `power1_cap_min`/`power1_cap_max` bounds**
  read from sysfs at run time — never a value hardcoded past what the card itself reports as valid.
- Runs once at boot (`Type=oneshot`, `RemainAfterExit=yes`, no `Restart=`), and exits — it does not
  stay resident or re-apply the cap while the machine is running (a later manual `echo` still takes
  effect until the next boot).

Install (run as separate commands; the card index, e.g. `card1`, and the hwmon index vary per
machine — the script scans for them, don't hardcode either):

```bash
sudo install -m755 scripts/systemd/gpu-power-cap.sh /usr/local/bin/
sudo install -m644 scripts/systemd/gpu-power-cap.service /etc/systemd/system/
sudo systemctl enable --now gpu-power-cap.service
```

Verify:

```bash
cat /sys/class/drm/card*/device/hwmon/hwmon*/power1_cap   # expect 272000000
journalctl -u gpu-power-cap
```

## Open questions (future work, not prioritized this session)

- Undervolting, and `pp_power_profile_mode` COMPUTE profile on Vulkan (would need `sudo`, reversible)
  — not attempted.
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
