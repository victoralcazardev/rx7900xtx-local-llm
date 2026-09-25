"""Unit tests for bench/concurrency_bench.py (stdlib unittest only).

Covers `rotate_wiki` (distinct-enough per-slot synthetic content), `peak_usage` (telemetry.jsonl
scan for peak VRAM/GTT/evicted/thermal), `required_help_flags`/`missing_help_flags` (the
--help preflight, built from flags this run's argv actually uses and matched as whole tokens),
and `collect_slot_results` (one slot's failure must not drop another slot's result). Pure
functions: no server, no GPU, no network.
"""
from __future__ import annotations

import concurrent.futures
import json
import pathlib
import sys
import tempfile
import types
import unittest

BENCH_DIR = pathlib.Path(__file__).resolve().parent.parent / "bench"
sys.path.insert(0, str(BENCH_DIR))

import concurrency_bench  # noqa: E402


def _args(**overrides):
    base = {"kv_unified": None, "kv_unified_per_slot": None, "mtp": False}
    base.update(overrides)
    return types.SimpleNamespace(**base)


class TestRotateWiki(unittest.TestCase):
    @staticmethod
    def _non_periodic_corpus():
        # A repeating fixture (e.g. "abc" * N) can coincidentally rotate back onto itself when
        # the cut lands on a period boundary; a sequence of increasing decimal numbers has no
        # short period, so a rotation is only ever unchanged for slot 0.
        return "".join(str(i) for i in range(300_000))

    def test_slot_zero_returns_original_text(self):
        wiki = self._non_periodic_corpus()
        self.assertEqual(concurrency_bench.rotate_wiki(wiki, 0), wiki)

    def test_empty_wiki_returns_empty(self):
        self.assertEqual(concurrency_bench.rotate_wiki("", 1), "")

    def test_other_slots_are_a_rotation_not_a_truncation(self):
        wiki = self._non_periodic_corpus()
        rotated = concurrency_bench.rotate_wiki(wiki, 1)
        self.assertEqual(len(rotated), len(wiki))
        self.assertEqual(sorted(rotated), sorted(wiki))
        self.assertNotEqual(rotated, wiki)

    def test_different_slots_get_different_content(self):
        wiki = self._non_periodic_corpus()
        self.assertNotEqual(
            concurrency_bench.rotate_wiki(wiki, 1), concurrency_bench.rotate_wiki(wiki, 2)
        )


class TestPeakUsage(unittest.TestCase):
    def test_missing_file_returns_zeros(self):
        peak = concurrency_bench.peak_usage(pathlib.Path("/nonexistent/telemetry.jsonl"))
        self.assertEqual(peak, {"vram": 0, "gtt": 0, "evicted": 0, "edge": 0, "hotspot": 0})

    def test_tracks_the_maximum_across_rows(self):
        rows = [
            {"process": {"bytes_by_metric": {"drm-memory-vram": 100, "drm-memory-gtt": 10,
                                              "amd-evicted-vram": 0}},
             "safety": {"edge_c": 40.0, "hotspot_c": 50.0}},
            {"process": {"bytes_by_metric": {"drm-memory-vram": 300, "drm-memory-gtt": 5,
                                              "amd-evicted-vram": 20}},
             "safety": {"edge_c": 60.0, "hotspot_c": None}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "telemetry.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            peak = concurrency_bench.peak_usage(path)
        self.assertEqual(peak, {"vram": 300, "gtt": 10, "evicted": 20, "edge": 60.0, "hotspot": 50.0})


class TestRequiredHelpFlags(unittest.TestCase):
    def test_base_flags_are_always_required(self):
        self.assertEqual(concurrency_bench.required_help_flags(_args()), ["-np", "-fa", "-ctk", "-ctv"])

    def test_kv_unified_true_requires_the_on_flag_only(self):
        required = concurrency_bench.required_help_flags(_args(kv_unified=True))
        self.assertIn("--kv-unified", required)
        self.assertNotIn("--no-kv-unified", required)

    def test_kv_unified_false_requires_the_off_flag_only(self):
        required = concurrency_bench.required_help_flags(_args(kv_unified=False))
        self.assertIn("--no-kv-unified", required)
        self.assertNotIn("--kv-unified", required)

    def test_kv_unified_per_slot_not_requested_is_not_required(self):
        required = concurrency_bench.required_help_flags(_args())
        self.assertNotIn("--kv-unified-per-slot", required)

    def test_kv_unified_per_slot_requested_is_required(self):
        required = concurrency_bench.required_help_flags(_args(kv_unified_per_slot=4096))
        self.assertIn("--kv-unified-per-slot", required)

    def test_mtp_not_requested_spec_flags_not_required(self):
        required = concurrency_bench.required_help_flags(_args())
        self.assertNotIn("--spec-type", required)
        self.assertNotIn("--spec-draft-n-max", required)

    def test_mtp_requested_spec_flags_required(self):
        required = concurrency_bench.required_help_flags(_args(mtp=True))
        self.assertIn("--spec-type", required)
        self.assertIn("--spec-draft-n-max", required)


class TestMissingHelpFlags(unittest.TestCase):
    def test_all_present_flags_are_not_missing(self):
        help_text = "-np,   --parallel N   number of server slots\n-fa,   --flash-attn [on|off|auto]\n"
        self.assertEqual(concurrency_bench.missing_help_flags(help_text, ["-np", "-fa"]), [])

    def test_absent_flag_is_reported_missing(self):
        help_text = "-np,   --parallel N   number of server slots\n"
        self.assertEqual(concurrency_bench.missing_help_flags(help_text, ["-np", "--spec-type"]),
                         ["--spec-type"])

    def test_substring_of_a_longer_flag_does_not_count_as_present(self):
        # Regression: a raw substring check would let "-np" match inside an unrelated longer
        # token (e.g. "-npx" below, which contains "-np" but is a different flag); only a
        # whole-token match should count.
        help_text = "--enable-npx-mode some unrelated flag\n"
        self.assertIn("-np", help_text)
        self.assertEqual(concurrency_bench.missing_help_flags(help_text, ["-np"]), ["-np"])

    def test_flag_at_end_of_line_is_present(self):
        help_text = "some help text ending in -np"
        self.assertEqual(concurrency_bench.missing_help_flags(help_text, ["-np"]), [])


class TestCollectSlotResults(unittest.TestCase):
    @staticmethod
    def _done_future(result=None, exc=None):
        f = concurrent.futures.Future()
        if exc is not None:
            f.set_exception(exc)
        else:
            f.set_result(result)
        return f

    def test_all_slots_succeed(self):
        futures_by_slot = {
            self._done_future({"slot": 0, "predicted_n": 10}): 0,
            self._done_future({"slot": 1, "predicted_n": 20}): 1,
        }
        results = concurrency_bench.collect_slot_results(futures_by_slot)
        self.assertEqual([r["slot"] for r in results], [0, 1])
        self.assertTrue(all("failure" not in r for r in results))

    def test_one_slot_failure_does_not_drop_the_others(self):
        futures_by_slot = {
            self._done_future({"slot": 0, "predicted_n": 10}): 0,
            self._done_future(exc=RuntimeError("connection reset")): 1,
            self._done_future({"slot": 2, "predicted_n": 30}): 2,
        }
        results = concurrency_bench.collect_slot_results(futures_by_slot)
        self.assertEqual([r["slot"] for r in results], [0, 1, 2])
        self.assertNotIn("failure", results[0])
        self.assertIn("connection reset", results[1]["failure"])
        self.assertNotIn("failure", results[2])

    def test_results_are_sorted_by_slot_regardless_of_completion_order(self):
        futures_by_slot = {
            self._done_future({"slot": 2, "predicted_n": 1}): 2,
            self._done_future({"slot": 0, "predicted_n": 1}): 0,
            self._done_future({"slot": 1, "predicted_n": 1}): 1,
        }
        results = concurrency_bench.collect_slot_results(futures_by_slot)
        self.assertEqual([r["slot"] for r in results], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
