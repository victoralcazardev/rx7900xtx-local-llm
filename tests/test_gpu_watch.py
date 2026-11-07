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


def _fake_device(root: pathlib.Path, hwmon: dict[str, str], used_gib: float = 20) -> pathlib.Path:
    dev = root / "device"
    hw = dev / "hwmon" / "hwmon3"
    hw.mkdir(parents=True)
    (dev / "mem_info_vram_total").write_text(str(24 * 2**30))
    (dev / "mem_info_vram_used").write_text(str(int(used_gib * 2**30)))
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
        self.assertEqual(gpu_watch.FIELDS[10:13], ["sclk_mhz", "mclk_mhz", "vddgfx_mv"])

    def test_missing_clock_sensors_leave_the_columns_empty(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(gpu_watch, "processing", return_value=""):
            row = gpu_watch.sample(_fake_device(pathlib.Path(tmp), {}), 8080)
        self.assertEqual((row["sclk_mhz"], row["mclk_mhz"], row["vddgfx_mv"]), (None, None, None))

    def test_flags_trip_only_above_the_limits(self):
        sensors = {"temp2_label": "junction", "temp3_label": "mem", "temp3_input": "90000"}
        cases = (  # (junction millidegrees, VRAM used GiB, expected flag)
            ("104000", 20, ""),                      # at the junction limit, 4 GiB free
            ("104100", 20, "HOT"),
            ("90000", 24 - 300 / 1024, ""),          # exactly 300 MiB free
            ("104100", 24 - 299 / 1024, "HOT+VRAM"),
        )
        for temp, used, flag in cases:
            with self.subTest(temp=temp, used=used), tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(gpu_watch, "processing", return_value=""):
                dev = _fake_device(pathlib.Path(tmp), {**sensors, "temp2_input": temp}, used_gib=used)
                self.assertEqual(gpu_watch.sample(dev, 8080)["flag"], flag)


def _fake_proc(root: pathlib.Path, procs: dict[int, tuple[str, list[int], str | None]]) -> pathlib.Path:
    """procs: pid -> (comm, child pids, RssAnon kB or None for a status file without it)."""
    for pid, (comm, children, rss_kb) in procs.items():
        task = root / str(pid) / "task" / str(pid)
        task.mkdir(parents=True)
        (root / str(pid) / "comm").write_text(comm + "\n")
        (task / "children").write_text("".join(f"{c} " for c in children))
        status = f"Name:\t{comm}\nVmRSS:\t  999999 kB\n"
        (root / str(pid) / "status").write_text(status + (f"RssAnon:\t {rss_kb} kB\n" if rss_kb else ""))
    return root


class TestServerRss(unittest.TestCase):
    def test_rss_column_is_appended_after_vddgfx(self):
        self.assertEqual(gpu_watch.FIELDS[10:], ["sclk_mhz", "mclk_mhz", "vddgfx_mv", "rss_anon_mib"])

    def test_direct_pid_is_the_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _fake_proc(pathlib.Path(tmp), {100: ("llama-server", [], "12582912")})
            self.assertEqual(gpu_watch.server_pid(100, proc), 100)
            self.assertEqual(gpu_watch.rss_anon_mib(100, proc), 12288)

    def test_wrapped_pid_resolves_to_the_server_child(self):
        procs = {100: ("systemd-inhibit", [101], "512"), 101: ("sh", [102], "256"),
                 102: ("llama-server", [], "2097152")}
        with tempfile.TemporaryDirectory() as tmp:
            proc = _fake_proc(pathlib.Path(tmp), procs)
            self.assertEqual(gpu_watch.server_pid(100, proc), 102)
            self.assertEqual(gpu_watch.rss_anon_mib(gpu_watch.server_pid(100, proc), proc), 2048)

    def test_missing_pid_or_field_leaves_the_column_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _fake_proc(pathlib.Path(tmp), {100: ("systemd-inhibit", [], "512"),
                                                  200: ("llama-server", [], None)})
            self.assertIsNone(gpu_watch.server_pid(100, proc))   # wrapper without a server child
            self.assertIsNone(gpu_watch.server_pid(999, proc))   # pid gone
            self.assertIsNone(gpu_watch.rss_anon_mib(None, proc))
            self.assertIsNone(gpu_watch.rss_anon_mib(999, proc))
            self.assertIsNone(gpu_watch.rss_anon_mib(200, proc))  # status without RssAnon

    def test_sample_reports_the_server_rss(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(gpu_watch, "processing", return_value=""):
            dev = _fake_device(pathlib.Path(tmp), {})
            proc = _fake_proc(pathlib.Path(tmp) / "proc", {100: ("llama-server", [], "1048576")})
            with mock.patch.object(gpu_watch, "PROC", proc):
                self.assertEqual(gpu_watch.sample(dev, 8080, 100)["rss_anon_mib"], 1024)
                self.assertIsNone(gpu_watch.sample(dev, 8080)["rss_anon_mib"])


if __name__ == "__main__":
    unittest.main()
