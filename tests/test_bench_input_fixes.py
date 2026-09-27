"""Regression tests for benchmark input handling and complete-row aggregation."""
from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

BENCH_DIR = pathlib.Path(__file__).resolve().parent.parent / "bench"
sys.path.insert(0, str(BENCH_DIR))

import oom_probe  # noqa: E402
import probe_ab  # noqa: E402
import spec_bench  # noqa: E402
import spec_depth_bench  # noqa: E402




class TestProbeStartup(unittest.TestCase):
    def test_live_server_without_health_times_out(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        with (
            mock.patch.object(probe_ab.time, "monotonic", side_effect=[0, 2]),
            mock.patch.object(probe_ab.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(TimeoutError, "arm-a: timed out waiting for /health"):
                probe_ab.wait_for_health(proc, lambda: False, "arm-a", timeout=1)
        sleep.assert_not_called()

class TestSpecAggregation(unittest.TestCase):
    def test_incomplete_rows_are_excluded_from_aggregates(self):
        rows = [
            {"variant": "none", "task": "code", "incomplete": False,
             "predicted_per_second": 10, "wall_s": 2, "draft_n": 4,
             "draft_n_accepted": 2, "predicted_n": 20},
            {"variant": "none", "task": "code", "incomplete": True,
             "predicted_per_second": 1000, "wall_s": 1, "draft_n": 8,
             "draft_n_accepted": 8, "predicted_n": 100},
        ]

        summary, incomplete_count = spec_bench.aggregate_rows(rows)

        self.assertEqual(incomplete_count, 1)
        self.assertEqual(summary["none"]["n"], 1)
        self.assertEqual(summary["none"]["median_tg"], 10)
        self.assertEqual(summary["none/code"]["n"], 1)
        self.assertEqual(summary["none/code"]["predicted_n"], [20])
        self.assertEqual(len(rows), 2)  # raw rows remain intact for callers to persist


class TestOomProbeArguments(unittest.TestCase):
    def test_rejects_nonpositive_character_count_before_corpus_access(self):
        with mock.patch.object(sys, "argv", ["oom_probe.py", "-1"]), \
             mock.patch.dict("os.environ", {"BENCH_WIKI": "/path/that/must/not/be/read"}), \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as ctx:
                oom_probe.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("n_chars must be a positive integer", stderr.getvalue())


class TestSpecDepthVariants(unittest.TestCase):
    def test_unknown_variant_is_rejected_by_argparse(self):
        with mock.patch.object(sys, "argv", ["spec_depth_bench.py", "--run", "--variants", "typo"]), \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as ctx:
                spec_depth_bench.main()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())
        self.assertIn("dfl5", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
