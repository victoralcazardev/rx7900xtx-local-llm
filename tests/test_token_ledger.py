"""Unit tests for scripts/token_ledger.py (stdlib unittest only).

Covers the pure logic: Prometheus text parsing, delta accumulation (including a counter
restart), the per-day bucket, and seed's refuse/--force behavior. No network and no real
ledger directory: `fetch_metrics` is monkeypatched and `LLM_USAGE_DIR` points at a temp dir.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import token_ledger  # noqa: E402

SAMPLE_METRICS_TEXT = """\
# HELP llamacpp:prompt_tokens_total Number of prompt tokens processed, excluding cached tokens
# TYPE llamacpp:prompt_tokens_total counter
llamacpp:prompt_tokens_total 1000
# HELP llamacpp:prompt_tokens_cached_total Number of prompt tokens reused from the cache
# TYPE llamacpp:prompt_tokens_cached_total counter
llamacpp:prompt_tokens_cached_total 5000
# HELP llamacpp:tokens_predicted_total Number of generation tokens processed
# TYPE llamacpp:tokens_predicted_total counter
llamacpp:tokens_predicted_total 300
# HELP llamacpp:n_decode_total Total number of llama_decode() calls
# TYPE llamacpp:n_decode_total counter
llamacpp:n_decode_total 42
# HELP llamacpp:requests_processing Number of requests processing
# TYPE llamacpp:requests_processing gauge
llamacpp:requests_processing 0
"""

METRICS_DISABLED_TEXT = """\
# no llamacpp: metrics here -- --metrics was not passed to llama-server
"""


class TestParseMetrics(unittest.TestCase):
    def test_extracts_the_three_tracked_counters(self):
        parsed = token_ledger.parse_metrics(SAMPLE_METRICS_TEXT)
        self.assertEqual(parsed, {"prompt_new": 1000, "cache_read": 5000, "output": 300})

    def test_ignores_comments_and_unrelated_metrics(self):
        parsed = token_ledger.parse_metrics(SAMPLE_METRICS_TEXT)
        self.assertNotIn("n_decode_total", parsed)
        self.assertEqual(len(parsed), 3)

    def test_empty_or_unrelated_text_returns_empty_dict(self):
        self.assertEqual(token_ledger.parse_metrics(""), {})
        self.assertEqual(token_ledger.parse_metrics(METRICS_DISABLED_TEXT), {})

    def test_malformed_lines_are_skipped(self):
        text = "llamacpp:prompt_tokens_total not-a-number\nnonsense line\n"
        self.assertEqual(token_ledger.parse_metrics(text), {})


class TestApplySample(unittest.TestCase):
    def test_first_sample_becomes_the_full_delta(self):
        state = token_ledger.default_state()
        now = datetime(2026, 9, 25, 10, 0, 0)
        state = token_ledger.apply_sample(state, {"prompt_new": 100, "cache_read": 50, "output": 20}, now)
        self.assertEqual(state["totals"], {"prompt_new": 100, "cache_read": 50, "output": 20})
        self.assertEqual(state["last_sample"], {"prompt_new": 100, "cache_read": 50, "output": 20})
        self.assertEqual(state["last_collected_at"], "2026-09-25T10:00:00")

    def test_second_sample_accumulates_only_the_delta(self):
        state = token_ledger.default_state()
        now1 = datetime(2026, 9, 25, 10, 0, 0)
        now2 = datetime(2026, 9, 25, 10, 1, 0)
        state = token_ledger.apply_sample(state, {"prompt_new": 100, "cache_read": 50, "output": 20}, now1)
        state = token_ledger.apply_sample(state, {"prompt_new": 150, "cache_read": 80, "output": 35}, now2)
        self.assertEqual(state["totals"], {"prompt_new": 150, "cache_read": 80, "output": 35})

    def test_counter_decrease_means_restart_new_value_is_the_delta(self):
        state = token_ledger.default_state()
        now1 = datetime(2026, 9, 25, 10, 0, 0)
        now2 = datetime(2026, 9, 25, 10, 1, 0)
        state = token_ledger.apply_sample(state, {"prompt_new": 1000, "cache_read": 500, "output": 200}, now1)
        # Server restarted: counters reset to 0, then a bit of traffic happened before we polled.
        state = token_ledger.apply_sample(state, {"prompt_new": 30, "cache_read": 10, "output": 5}, now2)
        self.assertEqual(state["totals"], {"prompt_new": 1030, "cache_read": 510, "output": 205})

    def test_per_day_bucket_accumulates_within_a_day_and_starts_fresh_next_day(self):
        state = token_ledger.default_state()
        day1_a = datetime(2026, 9, 25, 9, 0, 0)
        day1_b = datetime(2026, 9, 25, 18, 0, 0)
        day2 = datetime(2026, 9, 26, 9, 0, 0)
        state = token_ledger.apply_sample(state, {"prompt_new": 100, "cache_read": 0, "output": 0}, day1_a)
        state = token_ledger.apply_sample(state, {"prompt_new": 250, "cache_read": 0, "output": 0}, day1_b)
        state = token_ledger.apply_sample(state, {"prompt_new": 260, "cache_read": 0, "output": 0}, day2)
        self.assertEqual(state["daily"]["2026-09-25"]["prompt_new"], 250)  # 100 + 150
        self.assertEqual(state["daily"]["2026-09-26"]["prompt_new"], 10)
        self.assertEqual(state["totals"]["prompt_new"], 260)


    def test_partial_sample_then_restored_counter_uses_last_known_baseline(self):
        state = token_ledger.default_state()
        state = token_ledger.apply_sample(
            state, {"prompt_new": 100, "cache_read": 50, "output": 20},
            datetime(2026, 9, 25, 10, 0, 0),
        )
        state = token_ledger.apply_sample(
            state, {"prompt_new": 150}, datetime(2026, 9, 25, 10, 1, 0),
        )
        self.assertEqual(state["last_sample"]["cache_read"], 50)
        state = token_ledger.apply_sample(
            state, {"prompt_new": 175, "cache_read": 80, "output": 40},
            datetime(2026, 9, 25, 10, 2, 0),
        )
        self.assertEqual(state["totals"], {"prompt_new": 175, "cache_read": 80, "output": 40})

class TestLedgerPersistence(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ledger.json"
            state = token_ledger.default_state()
            state["totals"]["output"] = 42
            token_ledger.save_state(path, state)
            self.assertTrue(path.exists())
            loaded = token_ledger.load_state(path)
            self.assertEqual(loaded["totals"]["output"], 42)

    def test_load_missing_file_returns_default_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "does-not-exist.json"
            self.assertEqual(token_ledger.load_state(path), token_ledger.default_state())

    def test_save_writes_atomically_no_leftover_tmp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ledger.json"
            token_ledger.save_state(path, token_ledger.default_state())
            leftovers = list(pathlib.Path(tmp).glob("*.tmp"))
            self.assertEqual(leftovers, [])


class TestCmdCollect(unittest.TestCase):
    """cmd_collect never touches the network directly in these tests -- fetch_metrics is
    monkeypatched -- and never touches the real ledger directory -- LLM_USAGE_DIR is
    redirected to a temp dir."""

    def _collect(self, tmp: str, fetch_return: str | None):
        with mock.patch.object(token_ledger, "fetch_metrics", return_value=fetch_return), \
             mock.patch.dict("os.environ", {"LLM_USAGE_DIR": tmp}):
            return token_ledger.cmd_collect(argparse_namespace())

    def test_server_down_exits_0_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = self._collect(tmp, None)
            self.assertEqual(rc, 0)
            self.assertFalse((pathlib.Path(tmp) / "ledger.json").exists())

    def test_metrics_disabled_exits_0_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = self._collect(tmp, METRICS_DISABLED_TEXT)
            self.assertEqual(rc, 0)
            self.assertFalse((pathlib.Path(tmp) / "ledger.json").exists())

    def test_successful_collect_writes_the_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = self._collect(tmp, SAMPLE_METRICS_TEXT)
            self.assertEqual(rc, 0)
            ledger = json.loads((pathlib.Path(tmp) / "ledger.json").read_text())
            self.assertEqual(ledger["totals"], {"prompt_new": 1000, "cache_read": 5000, "output": 300})

    def test_two_collects_accumulate(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._collect(tmp, SAMPLE_METRICS_TEXT)
            text2 = SAMPLE_METRICS_TEXT.replace("prompt_tokens_total 1000", "prompt_tokens_total 1100")
            self._collect(tmp, text2)
            ledger = json.loads((pathlib.Path(tmp) / "ledger.json").read_text())
            self.assertEqual(ledger["totals"]["prompt_new"], 1100)


class TestCmdSeed(unittest.TestCase):
    def _seed(self, tmp: str, force: bool = False, note: str = "test baseline"):
        args = argparse_namespace(
            prompt_new=10, cache_read=20, output=30, turns=1, note=note, force=force
        )
        with mock.patch.dict("os.environ", {"LLM_USAGE_DIR": tmp}):
            return token_ledger.cmd_seed(args)

    def test_seed_writes_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = self._seed(tmp)
            self.assertEqual(rc, 0)
            ledger = json.loads((pathlib.Path(tmp) / "ledger.json").read_text())
            self.assertEqual(ledger["baseline"]["prompt_new"], 10)
            self.assertEqual(ledger["baseline"]["turns"], 1)

    def test_seed_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            rc = self._seed(tmp, note="second attempt")
            self.assertEqual(rc, 1)
            ledger = json.loads((pathlib.Path(tmp) / "ledger.json").read_text())
            self.assertEqual(ledger["baseline"]["note"], "test baseline")  # unchanged

    def test_seed_overwrites_with_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            rc = self._seed(tmp, force=True, note="corrected baseline")
            self.assertEqual(rc, 0)
            ledger = json.loads((pathlib.Path(tmp) / "ledger.json").read_text())
            self.assertEqual(ledger["baseline"]["note"], "corrected baseline")


class TestCmdShow(unittest.TestCase):
    def test_show_json_sums_baseline_and_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"LLM_USAGE_DIR": tmp}):
                token_ledger.cmd_seed(argparse_namespace(
                    prompt_new=100, cache_read=200, output=300, turns=5, note="n", force=False
                ))
                with mock.patch.object(token_ledger, "fetch_metrics", return_value=SAMPLE_METRICS_TEXT):
                    token_ledger.cmd_collect(argparse_namespace())

                captured = []
                with mock.patch("builtins.print", side_effect=lambda *a: captured.append(" ".join(map(str, a)))):
                    rc = token_ledger.cmd_show(argparse_namespace(json=True))
                self.assertEqual(rc, 0)
                payload = json.loads(captured[0])
                self.assertEqual(payload["all_time"]["prompt_new"], 1100)  # 100 baseline + 1000 collected
                self.assertEqual(payload["all_time"]["output"], 600)  # 300 baseline + 300 collected


class TestGetPort(unittest.TestCase):
    def test_reads_port_from_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "models.toml"
            path.write_text('[defaults]\nport = 9090\nflags = []\n')
            self.assertEqual(token_ledger.get_port(path), 9090)

    def test_defaults_to_8080_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "models.toml"
            path.write_text("[defaults]\nflags = []\n")
            self.assertEqual(token_ledger.get_port(path), 8080)



class TestCli(unittest.TestCase):
    """main() argument parsing and dispatch: subcommands, required arguments, text output."""

    def _run(self, argv: list[str], tmp: str, fetch_return: str | None = None) -> int:
        with mock.patch.dict("os.environ", {"LLM_USAGE_DIR": tmp}), \
                mock.patch.object(token_ledger, "fetch_metrics", return_value=fetch_return):
            return token_ledger.main(argv)

    def test_no_command_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                self._run([], tmp)

    def test_seed_via_cli_writes_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = self._run(
                ["seed", "--prompt-new", "5", "--cache-read", "7",
                 "--output", "9", "--turns", "2", "--note", "cli test"], tmp
            )
            self.assertEqual(rc, 0)
            ledger = json.loads((pathlib.Path(tmp) / "ledger.json").read_text())
            self.assertEqual(ledger["baseline"]["prompt_new"], 5)
            self.assertEqual(ledger["baseline"]["note"], "cli test")

    def test_seed_missing_required_arguments_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                self._run(["seed", "--prompt-new", "5"], tmp)

    def test_collect_via_cli_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = self._run(["collect"], tmp, fetch_return=SAMPLE_METRICS_TEXT)
            self.assertEqual(rc, 0)
            ledger = json.loads((pathlib.Path(tmp) / "ledger.json").read_text())
            self.assertEqual(ledger["totals"]["prompt_new"], 1000)

    def test_show_text_output_lists_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(["seed", "--prompt-new", "1", "--cache-read", "2", "--output", "3",
                       "--turns", "1", "--note", "n"], tmp)
            captured: list[str] = []
            with mock.patch("builtins.print", side_effect=lambda *a: captured.append(" ".join(map(str, a)))):
                rc = self._run(["show"], tmp)
            self.assertEqual(rc, 0)
            text = "\n".join(captured)
            self.assertIn("all-time:", text)
            self.assertIn("historical baseline:", text)
            self.assertIn("prompt-new=1", text)

def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


if __name__ == "__main__":
    unittest.main()
