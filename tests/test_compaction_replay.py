"""Unit tests for bench/compaction_replay.py (stdlib unittest only, no server)."""
from __future__ import annotations

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "bench"))

import compaction_replay  # noqa: E402


class TestReplay(unittest.TestCase):
    def test_text_is_deterministic_and_sized_in_words(self):
        a = compaction_replay.text("s", 1300, 1.3)
        self.assertEqual(a, compaction_replay.text("s", 1300, 1.3))
        self.assertNotEqual(a, compaction_replay.text("t", 1300, 1.3))
        self.assertEqual(len(a.split()), 1000)

    def test_compaction_keeps_only_the_system_prompt(self):
        msgs = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "u"},
                {"role": "assistant", "content": "a"}]
        out = compaction_replay.compact(msgs, "S")
        self.assertIs(out[0], msgs[0])
        self.assertEqual(out[1:], [{"role": "user", "content": "Summary of the work so far:\nS"}])


if __name__ == "__main__":
    unittest.main()
