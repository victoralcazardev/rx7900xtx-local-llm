"""Unit tests for scripts/cache_misses.py (stdlib unittest only, synthetic log lines)."""
from __future__ import annotations

import pathlib
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
