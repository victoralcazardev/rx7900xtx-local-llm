"""Unit tests for scripts/gpu_watch.py (stdlib unittest only): sensor sampling from a fake sysfs tree."""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import gpu_watch  # noqa: E402


def _fake_device(root: pathlib.Path, hwmon: dict[str, str]) -> pathlib.Path:
    dev = root / "device"
    hw = dev / "hwmon" / "hwmon3"
    hw.mkdir(parents=True)
    (dev / "mem_info_vram_total").write_text(str(24 * 2**30))
    (dev / "mem_info_vram_used").write_text(str(20 * 2**30))
    (dev / "gpu_busy_percent").write_text("97")
    for name, value in {"temp1_label": "edge", "temp1_input": "55000", "power1_average": "272000000",
                        **hwmon}.items():
        (hw / name).write_text(value)
    return dev


class TestSample(unittest.TestCase):
    def test_logs_clocks_and_voltage_after_the_original_columns(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(gpu_watch, "processing", return_value="1"):
            dev = _fake_device(pathlib.Path(tmp), {"freq1_input": "2400000000", "freq2_input": "1249000000",
                                                   "in0_input": "1100"})
            row = gpu_watch.sample(dev, 8080)
        self.assertEqual((row["sclk_mhz"], row["mclk_mhz"], row["vddgfx_mv"]), (2400, 1249, 1100))
        self.assertEqual((row["power_w"], row["vram_free_mib"], row["busy_pct"]), (272.0, 4096, 97))
        self.assertEqual(gpu_watch.FIELDS[:10], ["utc", "edge_c", "junction_c", "mem_c", "power_w", "busy_pct",
                                                 "vram_used_mib", "vram_free_mib", "processing", "flag"])
        self.assertEqual(gpu_watch.FIELDS[10:], ["sclk_mhz", "mclk_mhz", "vddgfx_mv"])

    def test_missing_clock_sensors_leave_the_columns_empty(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(gpu_watch, "processing", return_value=""):
            row = gpu_watch.sample(_fake_device(pathlib.Path(tmp), {}), 8080)
        self.assertEqual((row["sclk_mhz"], row["mclk_mhz"], row["vddgfx_mv"]), (None, None, None))


if __name__ == "__main__":
    unittest.main()
