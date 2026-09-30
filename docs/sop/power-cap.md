# SOP: permanent 272 W power cap

Why: at the factory 303 W limit, long prefills at depth push the hotspot to 100-106°C; 272 W (this
card's driver minimum) costs ~6% prefill and runs the hotspot 7-8°C cooler — evidence in
[`../measurements/thermals-power.md`](../measurements/thermals-power.md). Writing the cap needs
root, and the driver resets it to the factory value on every reboot, hence the boot-time unit.

## One-off (until next reboot)

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

## Permanent: a systemd oneshot unit

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

