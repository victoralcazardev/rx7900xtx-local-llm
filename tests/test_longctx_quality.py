"""Unit tests for bench/longctx_quality.py (stdlib unittest only).

Covers `parse_variants` (the --variants parsing/validation helper extracted
from main() so it's testable without argparse/SystemExit plumbing),
`_parse_port` (the urlparse-based port extraction for --tokenizer-url), and
`resolve_monitor_abort` (decides whether a monitor abort caught during
cleanup should replace an exception already propagating from the run, or be
chained onto it instead). All are pure functions: no server, no GPU, no
network.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

BENCH_DIR = pathlib.Path(__file__).resolve().parent.parent / "bench"
sys.path.insert(0, str(BENCH_DIR))

import longctx_quality  # noqa: E402


class TestParseVariants(unittest.TestCase):
    def test_single_valid_variant(self):
        self.assertEqual(
            longctx_quality.parse_variants(["q8q51-mtp1"]),
            (("q8q51", True),),
        )

    def test_multiple_valid_variants(self):
        self.assertEqual(
            longctx_quality.parse_variants(["q8q51-mtp1", "q8q8-mtp0"]),
            (("q8q51", True), ("q8q8", False)),
        )

    def test_empty_list_returns_empty_tuple(self):
        self.assertEqual(longctx_quality.parse_variants([]), ())

    def test_unknown_kv_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            longctx_quality.parse_variants(["q4q4-mtp0"])
        self.assertIn("q4q4-mtp0", str(ctx.exception))

    def test_bad_mtp_digit_rejected(self):
        with self.assertRaises(ValueError):
            longctx_quality.parse_variants(["q8q8-mtp2"])

    def test_missing_mtp_suffix_rejected(self):
        with self.assertRaises(ValueError):
            longctx_quality.parse_variants(["q8q8"])

    def test_first_invalid_value_stops_parsing(self):
        with self.assertRaises(ValueError):
            longctx_quality.parse_variants(["q8q8-mtp0", "garbage"])


class TestParsePort(unittest.TestCase):
    def test_extracts_port(self):
        self.assertEqual(longctx_quality._parse_port("http://127.0.0.1:18080"), 18080)

    def test_extracts_port_with_path(self):
        self.assertEqual(longctx_quality._parse_port("http://127.0.0.1:9999/v1"), 9999)

    def test_missing_port_raises_systemexit(self):
        with self.assertRaises(SystemExit):
            longctx_quality._parse_port("http://127.0.0.1")


class TestRunMatrixCompleteness(unittest.TestCase):
    def test_complete_quality_miss_is_a_successful_measurement(self):
        rows = [{"variant": "q8q8-mtp0", "depth": 32_000, "exact_match": False,
                 "field_accuracy": 0.0, "loop_detected": False, "truncated": True},
                {"variant": "q8q8-mtp0", "depth": 32_000, "exact_match": False,
                 "field_accuracy": 0.0, "loop_detected": False, "truncated": False}]
        documents = {32_000: [{"questions": [{}, {}]}]}

        scores, incomplete = longctx_quality.aggregate_scores(
            rows, [], documents, (("q8q8", False),), (32_000,)
        )

        self.assertFalse(incomplete)
        self.assertEqual(scores[0]["expected"], 2)
        self.assertEqual(scores[0]["completed"], 2)
        self.assertTrue(scores[0]["complete"])
        self.assertEqual(scores[0]["missing"], 0)
        self.assertEqual(scores[0]["exact"], 0)
        self.assertEqual(scores[0]["exact_rate"], 0)
        self.assertEqual(scores[0]["truncated"], 1)

    def test_missing_expected_rows_make_matrix_exit_status_fail(self):
        documents = {32_000: [{"questions": [{}, {}]}]}
        scores, incomplete = longctx_quality.aggregate_scores(
            [{"variant": "q8q8-mtp0", "depth": 32_000, "exact_match": True,
              "field_accuracy": 1.0, "loop_detected": False, "truncated": False}],
            [], documents, (("q8q8", False),), (32_000,)
        )

        self.assertTrue(incomplete)
        self.assertEqual(scores[0]["expected"], 2)
        self.assertEqual(scores[0]["completed"], 1)
        self.assertEqual(scores[0]["missing"], 1)

    def test_incomplete_response_is_not_scored_as_a_quality_miss_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model = root / "model.gguf"
            server = root / "llama-server"
            model.touch()
            server.touch()

            questions = [
                {"prompt": f"question {index}", "expected": {"answer": index},
                 "needle_index": [index], "needle_token": [index], "question_ids": [f"id-{index}"]}
                for index in range(3)
            ]
            document = {"document_tokens": 32_000, "seed": 42, "document": "fixture",
                        "questions": questions}

            class FakeMonitor:
                def __init__(self, pid, file):
                    self.file = file
                    self.error = None
                    self.bad = {}
                    monitor_files.append(file)

                def start(self):
                    pass

                def set_phase(self, _phase):
                    pass

                def stop(self):
                    pass

            class FakeProcess:
                pid = 123

                def poll(self):
                    return None

                def wait(self, timeout=None):
                    self.waited = True
                    return 0

            monitor_files = []
            process = FakeProcess()
            runner = types.SimpleNamespace(
                MODEL=model,
                SERVER=server,
                PORT=8080,
                check_power_cap=lambda _depth: {},
                extra_argv=lambda _extra, _hardcoded: [],
                Monitor=FakeMonitor,
                wait_health=lambda _proc, _monitor: None,
                cool_down=lambda: None,
                http_json=lambda path, _payload: (
                    {"prompt": "rendered"} if path == "/apply-template" else {"tokens": [1, 2, 3]}
                ),
            )

            def stream_completion(_payload, events_path, _monitor):
                if events_path.parent.name.endswith("-q0"):
                    # A terminal output-cap response is a measured quality miss, not a transport failure.
                    return ({"stop": True, "truncated": True, "stop_type": "limit", "timings": {}}, "{}")
                if events_path.parent.name.endswith("-q1"):
                    # A missing terminal stop event means the requested measurement is incomplete.
                    return ({"stop": False, "truncated": False, "timings": {}}, "{}")
                raise TimeoutError("request timed out")

            runner.stream_completion = stream_completion
            args = types.SimpleNamespace(
                output=root / "out", tokenizer_url="http://127.0.0.1:18080", server=None,
                ctx=262_144, runner="depth_bench.py", extra="", mtp_n=2,
            )

            with (
                mock.patch.object(longctx_quality, "DEPTHS", (32_000,)),
                mock.patch.object(longctx_quality, "DOCS", 1),
                mock.patch.object(longctx_quality, "QUESTIONS_PER_DOC", 2),
                mock.patch.object(longctx_quality, "VARIANTS", (("q8q8", False),)),
                mock.patch.object(longctx_quality, "Tokenizer", return_value=object()),
                mock.patch.object(longctx_quality, "build_document", return_value=document),
                mock.patch.object(longctx_quality.subprocess, "Popen", return_value=process),
                mock.patch.object(longctx_quality.os, "killpg") as killpg,
            ):
                status = longctx_quality.run_matrix(args, runner)

            out = next((root / "out").glob("longctx-*"))
            score = json.loads((out / "scores.json").read_text())[0]
            rows = [json.loads(line) for line in (out / "summary.jsonl").read_text().splitlines()]
            self.assertEqual(status, 1)
            self.assertEqual(score["expected"], 3)
            self.assertEqual(score["completed"], 1)
            self.assertFalse(score["complete"])
            self.assertEqual(score["exact"], 0)
            self.assertEqual(score["exact_rate"], 0)
            self.assertEqual(score["failures"], 2)
            self.assertEqual(score["missing"], 0)
            self.assertEqual(score["truncated"], 1)
            self.assertEqual({row["failure_kind"] for row in rows if "failure" in row},
                             {"incomplete_response", "request_error"})
            self.assertTrue(process.waited)
            self.assertTrue(monitor_files[0].closed)
            killpg.assert_called_once_with(process.pid, longctx_quality.signal.SIGTERM)

    def test_main_propagates_partial_matrix_status(self):
        with (
            mock.patch.object(sys, "argv", ["longctx_quality.py", "--run", "--inhibitor-ok"]),
            mock.patch.dict("os.environ", {"IA_BENCH_INHIBITED": "1"}),
            mock.patch.object(longctx_quality, "run_matrix", return_value=1),
        ):
            self.assertEqual(longctx_quality.main(), 1)


def _notes(exc: BaseException) -> str:
    return "\n".join(getattr(exc, "__notes__", []))


class TestResolveMonitorAbort(unittest.TestCase):
    def test_no_original_exception_means_raise_the_abort(self):
        abort = RuntimeError("thermal abort")
        self.assertTrue(longctx_quality.resolve_monitor_abort(abort, None))

    def test_original_exception_present_means_do_not_raise(self):
        abort = RuntimeError("thermal abort")
        original = ValueError("question failed")
        self.assertFalse(longctx_quality.resolve_monitor_abort(abort, original))

    def test_original_exception_present_gets_the_abort_as_a_note(self):
        abort = RuntimeError("thermal abort")
        original = ValueError("question failed")
        longctx_quality.resolve_monitor_abort(abort, original)
        self.assertIn(repr(abort), _notes(original))

    def test_does_not_overwrite_an_existing_cause(self):
        # Regression: an earlier version unconditionally set original_exc.__cause__, silently
        # discarding a cause the run exception may already carry (e.g. from `raise X from Y`).
        abort = RuntimeError("thermal abort")
        wrapped = ValueError("tokenizer request failed")
        original = RuntimeError("question failed")
        original.__cause__ = wrapped
        longctx_quality.resolve_monitor_abort(abort, original)
        self.assertIs(original.__cause__, wrapped)
        self.assertIn(repr(abort), _notes(original))

    def test_matches_real_finally_block_propagation(self):
        # Reproduces the actual call shape: a try body raises, a finally block catches its own
        # secondary abort, and resolve_monitor_abort must let the original exception (not the
        # abort) be the one that ultimately propagates out of the function.
        abort = RuntimeError("thermal abort")

        def run():
            original = None
            try:
                raise ValueError("question failed")
            except Exception as e:
                original = e
                raise
            finally:
                if longctx_quality.resolve_monitor_abort(abort, original):
                    raise abort

        with self.assertRaises(ValueError) as ctx:
            run()
        self.assertIn(repr(abort), _notes(ctx.exception))


class TestResolveMonitorAbortControlFlowShape(unittest.TestCase):
    """Drives resolve_monitor_abort through the exact try/except/finally shape used in
    run_matrix's per-variant block: the try body's own exception is captured explicitly by an
    `except BaseException as e: run_exc = e; raise` clause (not read back from sys.exc_info() in
    `finally`, which can see the wrong exception if this ever runs nested inside another
    handler, and not `except Exception`, which would miss KeyboardInterrupt/SystemExit), and a
    monitor.stop() abort discovered in `finally` is resolved against that captured `run_exc`."""

    @staticmethod
    def _run_variant(monitor_stop_raises: BaseException | None, body_raises: BaseException | None):
        run_exc = None

        class FakeMonitor:
            def stop(self):
                if monitor_stop_raises:
                    raise monitor_stop_raises

        monitor = FakeMonitor()
        try:
            try:
                if body_raises:
                    raise body_raises
            except BaseException as e:
                run_exc = e
                raise
        finally:
            monitor_abort = None
            try:
                monitor.stop()
            except Exception as e:
                monitor_abort = e
            if monitor_abort is not None:
                if longctx_quality.resolve_monitor_abort(monitor_abort, run_exc):
                    raise monitor_abort

    def test_monitor_abort_alone_propagates_and_stops_the_matrix(self):
        # The try body completes cleanly (or a per-question handler swallowed its own failure
        # without re-raising) but the monitor found the GPU unsafe during cleanup: the abort
        # must still be raised directly, not dropped, so the matrix stops.
        abort = RuntimeError("thermal/memory: edge=97")
        with self.assertRaises(RuntimeError) as ctx:
            self._run_variant(monitor_stop_raises=abort, body_raises=None)
        self.assertIs(ctx.exception, abort)

    def test_body_exception_wins_but_carries_the_abort_as_a_note(self):
        # Both the run and the monitor failed: the original run exception (not the abort) is
        # what propagates, but the abort must stay visible on it instead of being swallowed.
        abort = RuntimeError("thermal/memory: edge=97")
        body_exc = ValueError("question failed")
        with self.assertRaises(ValueError) as ctx:
            self._run_variant(monitor_stop_raises=abort, body_raises=body_exc)
        self.assertIs(ctx.exception, body_exc)
        self.assertIn(repr(abort), _notes(ctx.exception))

    def test_no_monitor_abort_lets_the_body_exception_propagate_unchanged(self):
        body_exc = ValueError("question failed")
        with self.assertRaises(ValueError) as ctx:
            self._run_variant(monitor_stop_raises=None, body_raises=body_exc)
        self.assertIs(ctx.exception, body_exc)
        self.assertEqual(_notes(ctx.exception), "")

    def test_keyboard_interrupt_wins_over_a_concurrent_monitor_abort(self):
        # Regression: `except Exception` (instead of `except BaseException`) would miss
        # KeyboardInterrupt, leaving run_exc None; resolve_monitor_abort would then say "raise
        # monitor_abort", replacing the interrupt instead of letting it propagate with the abort
        # attached as a note.
        abort = RuntimeError("thermal/memory: edge=97")
        with self.assertRaises(KeyboardInterrupt) as ctx:
            self._run_variant(monitor_stop_raises=abort, body_raises=KeyboardInterrupt())
        self.assertIn(repr(abort), _notes(ctx.exception))

    def test_system_exit_wins_over_a_concurrent_monitor_abort(self):
        abort = RuntimeError("thermal/memory: edge=97")
        with self.assertRaises(SystemExit) as ctx:
            self._run_variant(monitor_stop_raises=abort, body_raises=SystemExit(1))
        self.assertIn(repr(abort), _notes(ctx.exception))


if __name__ == "__main__":
    unittest.main()
