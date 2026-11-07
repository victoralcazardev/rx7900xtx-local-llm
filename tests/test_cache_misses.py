"""Unit tests for scripts/cache_misses.py (stdlib unittest only, synthetic log lines)."""
from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import cache_misses  # noqa: E402

LOG = """\
1.00.000.000 I slot      release: id  0 | task 1 | stop processing: n_tokens = 100000, truncated = 0
1.01.000.000 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.990 (> 0.100 thold), f_keep = 1.000
1.02.000.000 I slot print_timing: id  0 | task 2 | prompt eval time =    1000.00 ms /  1000 tokens (    1.00 ms per token,  1000.00 tokens per second)
2.00.000.000 I slot      release: id  0 | task 2 | stop processing: n_tokens = 120000, truncated = 0
2.01.000.000 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.990 (> 0.100 thold), f_keep = 0.980
2.02.000.000 I slot print_timing: id  0 | task 3 | prompt eval time =    5000.00 ms /  4000 tokens (    1.25 ms per token,   800.00 tokens per second)
3.00.000.000 I slot      release: id  0 | task 3 | stop processing: n_tokens = 200000, truncated = 0
3.01.000.000 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.400 (> 0.100 thold), f_keep = 0.080
3.02.000.000 I slot print_timing: id  0 | task 4 | prompt eval time =   50000.00 ms / 40000 tokens (    1.25 ms per token,   800.00 tokens per second)
4.00.000.000 I slot      release: id  0 | task 4 | stop processing: n_tokens = 50000, truncated = 0
4.01.000.000 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.500 (> 0.100 thold), f_keep = 0.480
4.02.000.000 I slot print_timing: id  0 | task 5 | prompt eval time =   60000.00 ms / 49000 tokens (    1.22 ms per token,   816.67 tokens per second)
"""


class TestParse(unittest.TestCase):
    def setUp(self):
        self.events = cache_misses.parse(LOG.splitlines())

    def test_one_event_per_slot_selection_with_prefill_cost(self):
        self.assertEqual([e["line"] for e in self.events], [2, 5, 8, 11])
        self.assertEqual([e["prefill_tokens"] for e in self.events], [1000, 4000, 40000, 49000])
        self.assertAlmostEqual(self.events[2]["prefill_s"], 50.0)

    def test_classes(self):
        self.assertEqual([e["cls"] for e in self.events], ["full", "partial", "compaction", "miss"])

    def test_estimates(self):
        compaction = self.events[2]
        self.assertEqual(compaction["old_tokens"], 200000)
        self.assertEqual(compaction["lcp_est"], 16000)
        self.assertEqual(compaction["new_est"], 40000)

    def test_lru_selection_has_no_similarity_but_is_counted(self):
        log = [
            "1.00.000.000 I slot      release: id  0 | task 1 | stop processing: n_tokens = 90000, truncated = 0",
            "1.01.000.000 I slot get_availabl: id  0 | task -1 | selected slot by LRU, t_last = 123",
            "1.02.000.000 I slot print_timing: id  0 | task 2 | prompt eval time =  90000.00 ms / 95000 tokens (x)",
        ]
        [e] = cache_misses.parse(log)
        self.assertEqual((e["cls"], e["old_tokens"], e["f_keep"], e["prefill_tokens"]), ("lru", 90000, None, 95000))

    def test_slots_tracked_separately(self):
        log = [
            "1 I slot      release: id  0 | task 1 | stop processing: n_tokens = 100000, truncated = 0",
            "2 I slot      release: id  1 | task 2 | stop processing: n_tokens = 1000, truncated = 0",
            "3 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.990 (> 0.100 thold), f_keep = 0.980",
            "4 I slot get_availabl: id  1 | task -1 | selected slot by LCP similarity, f_sim_best = 0.990 (> 0.100 thold), f_keep = 1.000",
            "5 I slot print_timing: id  1 | task 4 | prompt eval time =    10.00 ms /    10 tokens (x)",
            "6 I slot print_timing: id  0 | task 3 | prompt eval time =  2000.00 ms /  2000 tokens (x)",
        ]
        events = cache_misses.parse(log)
        self.assertEqual([(e["slot"], e["old_tokens"], e["cls"], e["prefill_tokens"]) for e in events],
                         [(1, 1000, "full", 10), (0, 100000, "partial", 2000)])

    def test_request_released_without_prefill_line_is_dropped(self):
        log = [
            "1 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.500 (> 0.100 thold), f_keep = 0.400",
            "2 I slot      release: id  0 | task 1 | stop processing: n_tokens = 5000, truncated = 0",
            "3 I slot print_timing: id  0 | task 2 | prompt eval time =  100.00 ms /  100 tokens (x)",
        ]
        self.assertEqual(cache_misses.parse(log), [])


    def test_selection_without_known_slot_size_is_unknown(self):
        log = [
            "1 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.500 (> 0.100 thold), f_keep = 0.400",
            "2 I slot print_timing: id  0 | task 1 | prompt eval time =  100.00 ms /  100 tokens (x)",
        ]
        [e] = cache_misses.parse(log)
        self.assertEqual((e["cls"], e["old_tokens"], e["lcp_est"]), ("unknown", None, None))


# Excerpt of _tmp/logs/huihui-iq3s-mtp-262k-q8q51-mtp-20261106-144605.log (lines 1086 and 1674 with their
# previous release): a 35% compaction that re-processed the 28K shared prefix, then an ordinary partial miss.
LOG_35 = """\
67.30.492.203 I slot      release: id  0 | task 40996 | stop processing: n_tokens = 92036, truncated = 0
67.30.629.908 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.583 (> 0.100 thold), f_keep = 0.306
69.18.390.832 I slot print_timing: id  0 | task 43212 | prompt eval time =   74336.09 ms / 48262 tokens (    1.54 ms per token,   649.24 tokens per second)
42.58.434.088 I slot      release: id  0 | task 24188 | stop processing: n_tokens = 62203, truncated = 0
42.58.533.711 I slot get_availabl: id  0 | task -1 | selected slot by LCP similarity, f_sim_best = 0.939 (> 0.100 thold), f_keep = 0.940
43.22.867.652 I slot print_timing: id  0 | task 26088 | prompt eval time =   11931.20 ms /  6110 tokens (    1.95 ms per token,   512.10 tokens per second)
"""


class TestCompaction35(unittest.TestCase):
    def test_35_percent_compaction_from_a_real_log(self):
        events = cache_misses.parse(LOG_35.splitlines())
        self.assertEqual([e["cls"] for e in events], ["compaction", "miss"])
        self.assertEqual([cache_misses.prefix_lost(e) for e in events], [True, False])

    def test_compaction_boundaries(self):
        cases = (  # (f_keep, new, old, class)
            (0.499, 69_999, 100_000, "compaction"),
            (0.500, 69_999, 100_000, "miss"),        # f_keep not under 0.5
            (0.499, 70_000, 100_000, "miss"),        # not under 0.7 of the old slot
            (0.900, 49_999, 100_000, "compaction"),  # the original under-half rule still holds
        )
        for f_keep, new, old, cls in cases:
            with self.subTest(f_keep=f_keep, new=new):
                self.assertEqual(cache_misses.classify(f_keep, new, old), cls)

    def test_prefix_lost_boundaries(self):
        cases = (  # (lcp_est, new_est, prefill_tokens, lost)
            (20_000, 50_000, 45_000, True),
            (19_999, 50_000, 50_000, False),   # LCP under 20K
            (20_000, 50_000, 44_999, False),   # prefill under 0.9 x new prompt
            (None, None, 90_000, False),       # LRU or unknown: no LCP
        )
        for lcp, new, prefill, lost in cases:
            with self.subTest(lcp=lcp, prefill=prefill):
                e = {"lcp_est": lcp, "new_est": new, "prefill_tokens": prefill}
                self.assertEqual(cache_misses.prefix_lost(e), lost)

    def test_summary_line(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log") as f:
            f.write(LOG_35)
            f.flush()
            out = io.StringIO()
            with mock.patch.object(sys, "argv", ["cache_misses.py", f.name]), contextlib.redirect_stdout(out):
                cache_misses.main()
        self.assertIn("\nshared prefix lost (LCP >= 20000, prefill >= 0.9 x new):         1           48262         74\n",
                      out.getvalue())


if __name__ == "__main__":
    unittest.main()
