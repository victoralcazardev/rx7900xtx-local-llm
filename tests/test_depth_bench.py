"""Unit tests for bench/depth_bench.py (stdlib unittest only).

Covers `extra_argv`, the `--extra "<flags>"` passthrough helper shared by depth_bench.py and
spec_depth_bench.py: shlex-splitting and the duplicate-flag warning; `resolve_max_hotspot_c`,
the BENCH_MAX_HOTSPOT_C threshold resolution used by the shared Monitor; and `power_cap_warning`,
the pure BENCH_EXPECT_POWER_CAP_W decision used by `check_power_cap`. Pure functions: no server,
no GPU, no network.
"""
from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

BENCH_DIR = pathlib.Path(__file__).resolve().parent.parent / "bench"
sys.path.insert(0, str(BENCH_DIR))

import depth_bench  # noqa: E402


class TestExtraArgv(unittest.TestCase):
    def test_empty_extra_returns_empty_list(self):
        self.assertEqual(depth_bench.extra_argv("", {"-c"}), [])

    def test_splits_multiple_flags(self):
        self.assertEqual(depth_bench.extra_argv("-cms 2048", {"-c"}), ["-cms", "2048"])

    def test_splits_several_flag_value_pairs(self):
        self.assertEqual(
            depth_bench.extra_argv("--spec-draft-p-min 0.3 --foo bar", set()),
            ["--spec-draft-p-min", "0.3", "--foo", "bar"],
        )

    def test_honors_shell_quoting(self):
        self.assertEqual(
            depth_bench.extra_argv('--label "two words"', set()),
            ["--label", "two words"],
        )

    def test_no_warning_when_no_duplicate(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            depth_bench.extra_argv("-cms 2048", {"-c", "-ctk"})
        self.assertEqual(buf.getvalue(), "")

    def test_warns_on_duplicate_flag(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = depth_bench.extra_argv("-c 999", {"-c"})
        self.assertEqual(result, ["-c", "999"])
        self.assertIn("-c", buf.getvalue())

    def test_warns_on_duplicate_flag_in_equals_form(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = depth_bench.extra_argv("--spec-draft-n-max=3", {"--spec-draft-n-max"})
        self.assertEqual(result, ["--spec-draft-n-max=3"])
        self.assertIn("--spec-draft-n-max", buf.getvalue())

    def test_no_warning_when_equals_form_value_is_not_hardcoded(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            depth_bench.extra_argv("--foo=bar", {"-c"})
        self.assertEqual(buf.getvalue(), "")


class TestResolveMaxHotspotC(unittest.TestCase):
    def test_default_is_104_when_unset(self):
        self.assertEqual(depth_bench.resolve_max_hotspot_c({}), 104.0)

    def test_default_is_104_when_empty_string(self):
        self.assertEqual(depth_bench.resolve_max_hotspot_c({"BENCH_MAX_HOTSPOT_C": ""}), 104.0)

    def test_uses_override_when_set(self):
        self.assertEqual(depth_bench.resolve_max_hotspot_c({"BENCH_MAX_HOTSPOT_C": "99"}), 99.0)

    def test_accepts_float_override(self):
        self.assertEqual(depth_bench.resolve_max_hotspot_c({"BENCH_MAX_HOTSPOT_C": "97.5"}), 97.5)

    def test_rejects_non_numeric_override(self):
        with self.assertRaises(SystemExit):
            depth_bench.resolve_max_hotspot_c({"BENCH_MAX_HOTSPOT_C": "hot"})

    def test_nan_falls_back_to_default_with_warning(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = depth_bench.resolve_max_hotspot_c({"BENCH_MAX_HOTSPOT_C": "nan"})
        self.assertEqual(result, 104.0)
        self.assertIn("nan", buf.getvalue())

    def test_inf_falls_back_to_default_with_warning(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = depth_bench.resolve_max_hotspot_c({"BENCH_MAX_HOTSPOT_C": "inf"})
        self.assertEqual(result, 104.0)
        self.assertIn("inf", buf.getvalue())

    def test_negative_inf_falls_back_to_default_with_warning(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = depth_bench.resolve_max_hotspot_c({"BENCH_MAX_HOTSPOT_C": "-inf"})
        self.assertEqual(result, 104.0)
        self.assertIn("-inf", buf.getvalue())


class TestPowerCapWarning(unittest.TestCase):
    def test_no_warning_below_deep_threshold(self):
        self.assertIsNone(depth_bench.power_cap_warning(303, 32_000, 272))

    def test_no_warning_without_expectation(self):
        self.assertIsNone(depth_bench.power_cap_warning(303, 190_000, None))

    def test_no_warning_when_cap_unknown(self):
        self.assertIsNone(depth_bench.power_cap_warning(None, 190_000, 272))

    def test_no_warning_when_cap_at_or_below_expectation(self):
        self.assertIsNone(depth_bench.power_cap_warning(272, 190_000, 272))
        self.assertIsNone(depth_bench.power_cap_warning(250, 190_000, 272))

    def test_warns_when_deep_run_cap_exceeds_expectation(self):
        msg = depth_bench.power_cap_warning(303, 190_000, 272)
        self.assertIsNotNone(msg)
        self.assertIn("303", msg)
        self.assertIn("272", msg)

    def test_warns_exactly_at_deep_threshold(self):
        self.assertIsNotNone(depth_bench.power_cap_warning(303, 128_000, 272))

    def test_no_warning_just_below_deep_threshold(self):
        self.assertIsNone(depth_bench.power_cap_warning(303, 127_999, 272))


class TestResolveExpectPowerCapW(unittest.TestCase):
    def test_none_when_unset(self):
        self.assertIsNone(depth_bench.resolve_expect_power_cap_w({}))

    def test_none_when_empty_string(self):
        self.assertIsNone(depth_bench.resolve_expect_power_cap_w({"BENCH_EXPECT_POWER_CAP_W": ""}))

    def test_parses_numeric_value(self):
        self.assertEqual(
            depth_bench.resolve_expect_power_cap_w({"BENCH_EXPECT_POWER_CAP_W": "272"}), 272.0
        )

    def test_invalid_value_warns_and_returns_none_instead_of_raising(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = depth_bench.resolve_expect_power_cap_w({"BENCH_EXPECT_POWER_CAP_W": "272W"})
        self.assertIsNone(result)
        self.assertIn("272W", buf.getvalue())


class TestPowerCapWarnings(unittest.TestCase):
    def test_empty_cards_list_returns_no_warnings(self):
        self.assertEqual(depth_bench.power_cap_warnings([], 190_000, 272), [])

    def test_single_card_within_expectation_no_warning(self):
        cards = [{"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 272}]
        self.assertEqual(depth_bench.power_cap_warnings(cards, 190_000, 272), [])

    def test_single_card_over_expectation_warns(self):
        cards = [{"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 303}]
        warnings = depth_bench.power_cap_warnings(cards, 190_000, 272)
        self.assertEqual(len(warnings), 1)
        self.assertIn("303", warnings[0])
        self.assertIn("card0", warnings[0])

    def test_checks_every_card_not_just_the_first(self):
        # Regression for "only the first glob match was checked": a second card over the
        # expected cap must still produce a warning even though the first card is fine.
        cards = [
            {"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 272},
            {"path": "/sys/.../card1/.../power1_cap", "power1_cap_w": 303},
        ]
        warnings = depth_bench.power_cap_warnings(cards, 190_000, 272)
        self.assertEqual(len(warnings), 1)
        self.assertIn("card1", warnings[0])

    def test_multiple_cards_over_expectation_each_warn(self):
        cards = [
            {"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 303},
            {"path": "/sys/.../card1/.../power1_cap", "power1_cap_w": 350},
        ]
        warnings = depth_bench.power_cap_warnings(cards, 190_000, 272)
        self.assertEqual(len(warnings), 2)

    def test_below_deep_threshold_no_warnings(self):
        cards = [{"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 303}]
        self.assertEqual(depth_bench.power_cap_warnings(cards, 32_000, 272), [])


class TestCheckPowerCap(unittest.TestCase):
    """check_power_cap orchestrates power_cap_snapshot + resolve_expect_power_cap_w +
    power_cap_warnings; power_cap_snapshot itself touches real sysfs, so it's stubbed here."""

    def _snapshot(self, cards):
        first = cards[0] if cards else {"path": None, "power1_cap_w": None}
        return {**first, "cards": cards}

    def test_records_snapshot_and_expectation_no_warnings(self):
        cards = [{"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 272}]
        with mock.patch.object(depth_bench, "power_cap_snapshot", return_value=self._snapshot(cards)):
            result = depth_bench.check_power_cap(190_000, env={"BENCH_EXPECT_POWER_CAP_W": "272"})
        self.assertEqual(result["expect_power_cap_w"], 272.0)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["cards"], cards)

    def test_invalid_expect_env_does_not_raise(self):
        cards = [{"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 303}]
        with mock.patch.object(depth_bench, "power_cap_snapshot", return_value=self._snapshot(cards)):
            result = depth_bench.check_power_cap(190_000, env={"BENCH_EXPECT_POWER_CAP_W": "not-a-number"})
        self.assertIsNone(result["expect_power_cap_w"])
        self.assertEqual(result["warnings"], [])

    def test_prints_one_warning_per_offending_card(self):
        cards = [
            {"path": "/sys/.../card0/.../power1_cap", "power1_cap_w": 303},
            {"path": "/sys/.../card1/.../power1_cap", "power1_cap_w": 272},
        ]
        buf = io.StringIO()
        with mock.patch.object(depth_bench, "power_cap_snapshot", return_value=self._snapshot(cards)):
            with contextlib.redirect_stderr(buf):
                result = depth_bench.check_power_cap(190_000, env={"BENCH_EXPECT_POWER_CAP_W": "272"})
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("card0", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
