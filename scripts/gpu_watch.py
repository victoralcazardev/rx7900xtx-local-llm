"""Passive GPU thermal/VRAM logger to run next to a long llama-server session.

Read-only: reads amdgpu sysfs sensors and GET /slots; never writes sysfs,
never sends inference. One CSV row per sample on stdout (redirect to a file).
Timestamps are UTC ISO so rows align with the server log start time.
Rows crossing the safety gate (junction >104 C, mem >105 C, VRAM free <300 MiB)
get flag=HOT/VRAM and a line on stderr; nothing is stopped automatically.

Usage:
    python3 scripts/gpu_watch.py [--interval 5] [--count N] [--port 8080] > _tmp/logs/gpu-watch.csv
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
import time
import urllib.request

LIMITS = {"junction": 104.0, "mem": 105.0, "vram_free_mib": 300}
FIELDS = ["utc", "edge_c", "junction_c", "mem_c", "power_w", "busy_pct",
          "vram_used_mib", "vram_free_mib", "processing", "flag"]


def find_card() -> pathlib.Path:
    for dev in sorted(pathlib.Path("/sys/class/drm").glob("card[0-9]*/device")):
        if (dev / "mem_info_vram_total").exists():
            return dev
    sys.exit("no amdgpu card with mem_info_vram_total found")


def read(path: pathlib.Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def processing(port: int) -> str:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/slots", timeout=1) as r:
            return str(int(any(s.get("is_processing") for s in json.load(r))))
    except Exception:  # server down or /slots disabled
        return ""


def sample(dev: pathlib.Path, port: int) -> dict:
    hw = next(dev.glob("hwmon/hwmon*"))
    temps = {}
    for label in hw.glob("temp*_label"):
        value = read(hw / label.name.replace("_label", "_input"))
        temps[label.read_text().strip()] = value / 1000 if value is not None else None
    power = read(hw / "power1_average")
    used, total = read(dev / "mem_info_vram_used"), read(dev / "mem_info_vram_total")
    free_mib = (total - used) // 2**20 if used is not None and total is not None else None
    flag = []
    if (temps.get("junction") or 0) > LIMITS["junction"] or (temps.get("mem") or 0) > LIMITS["mem"]:
        flag.append("HOT")
    if free_mib is not None and free_mib < LIMITS["vram_free_mib"]:
        flag.append("VRAM")
    return {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "edge_c": temps.get("edge"), "junction_c": temps.get("junction"), "mem_c": temps.get("mem"),
        "power_w": power / 1e6 if power is not None else None,
        "busy_pct": read(dev / "gpu_busy_percent"),
        "vram_used_mib": used // 2**20 if used is not None else None,
        "vram_free_mib": free_mib, "processing": processing(port), "flag": "+".join(flag),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--count", type=int, default=0, help="stop after N samples (0 = forever)")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    dev = find_card()
    print(",".join(FIELDS), flush=True)
    n = 0
    while not args.count or n < args.count:
        row = sample(dev, args.port)
        print(",".join("" if row[k] is None else str(row[k]) for k in FIELDS), flush=True)
        if row["flag"]:
            print(f"gpu_watch {row['utc']} {row['flag']}: junction={row['junction_c']} "
                  f"mem={row['mem_c']} vram_free_mib={row['vram_free_mib']}", file=sys.stderr, flush=True)
        n += 1
        if not args.count or n < args.count:
            time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
