"""Unit tests for bench/coding_suite.py (stdlib unittest only; needs `git`, no server, GPU or network).

Covers the SSE tool-call assembly, path containment, fault injection, the bounded `run_tests`
result with its saved log, scoring that ignores edited tests, the agent loop's stop reasons and
the predeclared regression rule.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

BENCH_DIR = pathlib.Path(__file__).resolve().parent.parent / "bench"
sys.path.insert(0, str(BENCH_DIR))

import coding_suite as cs  # noqa: E402


def sse(*chunks):
    return [f"data: {json.dumps(c)}\n".encode() for c in chunks] + [b"data: [DONE]\n"]


class TestParseSse(unittest.TestCase):
    def test_assembles_interleaved_tool_call_fragments(self):
        lines = sse(
            {"choices": [{"delta": {"reasoning_content": "think "}}]},
            {"choices": [{"delta": {"reasoning_content": "more"}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "a", "function": {"name": "read_file", "arguments": '{"pa'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "b", "function": {"name": "run_tests", "arguments": "{"}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'th": "x"}'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 1, "function": {"arguments": "}"}}]}}]},
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
            {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 3}},
        )
        out = cs.parse_sse([b": keep-alive\n"] + lines + sse({"choices": [{"delta": {"content": "late"}}]}))
        self.assertEqual(out["reasoning"], "think more")
        self.assertEqual(out["content"], "")
        self.assertEqual(out["tool_calls"], [{"id": "a", "name": "read_file", "arguments": '{"path": "x"}'},
                                             {"id": "b", "name": "run_tests", "arguments": "{}"}])
        self.assertEqual(out["finish_reason"], "tool_calls")
        self.assertEqual(out["usage"], {"prompt_tokens": 7, "completion_tokens": 3})

    def test_server_error_chunk_raises(self):
        with self.assertRaises(RuntimeError):
            cs.parse_sse(sse({"error": {"message": "context exceeded"}}))


class TestChatDeadline(unittest.TestCase):
    def test_stalled_stream_is_cut_at_the_episode_deadline(self):
        import http.server
        import threading
        import time

        class Stall(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'data: {"choices": [{"delta": {"content": "x"}}]}\n\n')
                self.wfile.flush()
                time.sleep(10)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stall)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        t0 = time.monotonic()
        with self.assertRaises(cs.EpisodeTimeout):
            cs.chat(f"http://127.0.0.1:{server.server_address[1]}", {}, t0 + 1.0)
        self.assertLess(time.monotonic() - t0, 3.0)


class WorkdirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class TestResolveIn(WorkdirCase):
    def test_rejects_escape_and_git_dir(self):
        (self.root / ".git").mkdir()
        for bad in ("../x", "/etc/passwd", ".git/config", "a/../../x", ""):
            with self.subTest(path=bad), self.assertRaises(cs.ToolError):
                cs.resolve_in(self.root, bad)

    def test_accepts_paths_inside(self):
        self.assertEqual(cs.resolve_in(self.root, "a/b.py"), (self.root / "a/b.py").resolve())


class TestTools(WorkdirCase):
    def test_injected_fault_only_on_listed_call_and_writes_nothing(self):
        task = {"tests_cmd": "true", "faults": {"write_file": {"1": "EAGAIN; file not modified"}}}
        tools = cs.Tools(self.root, task, None)
        first = tools.call("write_file", {"path": "f.txt", "content": "x"})
        self.assertEqual(first, "error: EAGAIN; file not modified")
        self.assertFalse((self.root / "f.txt").exists())
        self.assertEqual(tools.call("write_file", {"path": "f.txt", "content": "x"}), "wrote 1 bytes to f.txt")
        self.assertEqual((self.root / "f.txt").read_text(), "x")

    def test_edit_file_replaces_only_a_unique_match(self):
        (self.root / "f.txt").write_text("a = 1\nb = 1\n")
        tools = cs.Tools(self.root, {"tests_cmd": "true"}, None)
        self.assertEqual(tools.call("edit_file", {"path": "f.txt", "old_string": "b = 1", "new_string": "b = 2"}),
                         "edited f.txt")
        self.assertEqual((self.root / "f.txt").read_text(), "a = 1\nb = 2\n")
        for old, n in (("= ", 2), ("c = 3", 0)):
            r = tools.call("edit_file", {"path": "f.txt", "old_string": old, "new_string": "x"})
            self.assertEqual(r, f"error: old_string occurs {n} times in f.txt; it must occur exactly once")
        self.assertEqual((self.root / "f.txt").read_text(), "a = 1\nb = 2\n")

    def test_write_fault_also_hits_the_first_edit(self):
        (self.root / "f.txt").write_text("x")
        task = {"tests_cmd": "true", "faults": {"write_file": {"1": "EAGAIN; file not modified"}}}
        tools = cs.Tools(self.root, task, None)
        args = {"path": "f.txt", "old_string": "x", "new_string": "y"}
        self.assertEqual(tools.call("edit_file", args), "error: EAGAIN; file not modified")
        self.assertEqual((self.root / "f.txt").read_text(), "x")
        self.assertEqual(tools.call("edit_file", args), "edited f.txt")
        self.assertEqual((self.root / "f.txt").read_text(), "y")

    def test_bounded_run_tests_keeps_full_log_in_worktree(self):
        task = {"tests_cmd": "for i in 1 2 3 4 5 6; do echo line$i; done; exit 3", "run_tests_tail_lines": 3}
        out = cs.Tools(self.root, task, None).call("run_tests", {})
        self.assertEqual(out, "exit code: 3\nline4\nline5\nline6\n[output truncated; full log: .suite/run-1.log]")
        self.assertEqual((self.root / ".suite/run-1.log").read_text(), "".join(f"line{i}\n" for i in range(1, 7)))

    def test_default_run_tests_keeps_last_characters(self):
        task = {"tests_cmd": "python3 -c \"print('a' * 5000 + 'END')\""}
        out = cs.Tools(self.root, task, None).call("run_tests", {})
        self.assertTrue(out.startswith("exit code: 0\n[output truncated"))
        self.assertTrue(out.rstrip().endswith("END"))
        self.assertNotIn("a" * 4001, out)

    def test_read_file_pages_long_files(self):
        (self.root / "f.txt").write_text("".join(f"{i}\n" for i in range(1, 2501)))
        tools = cs.Tools(self.root, {}, None)
        first = tools.call("read_file", {"path": "f.txt"})
        self.assertIn("[lines 1-2000 of 2500; call read_file with offset=2001 to continue]", first)
        rest = tools.call("read_file", {"path": "f.txt", "offset": 2001})
        self.assertTrue(rest.startswith("2001\n"))
        self.assertIn("[lines 2001-2500 of 2500", rest)


class TestScore(WorkdirCase):
    """A local git project: a test edited by the model must not make the task pass."""

    def setUp(self):
        super().setUp()
        r = self.root
        (r / "tests").mkdir()
        (r / "mod.py").write_text("VALUE = 2\n")
        (r / "tests/__init__.py").write_text("")
        (r / "tests/test_mod.py").write_text(
            "import unittest, mod\nclass T(unittest.TestCase):\n"
            "    def test_value(self):\n        self.assertEqual(mod.VALUE, 1)\n")
        for args in (["init", "-q"], ["add", "-A"], [*cs.GIT_ID, "commit", "-qm", "base"]):
            subprocess.run(["git", *args], cwd=r, check=True, capture_output=True)
        self.commit = cs.git(r, "rev-parse", "HEAD").strip()
        self.task = {"test_dir": "tests", "score_cmd": "python3 -m unittest -q"}

    def test_edited_test_is_restored_before_scoring(self):
        (self.root / "tests/test_mod.py").write_text("import unittest\nclass T(unittest.TestCase):\n    pass\n")
        self.assertFalse(cs.score(self.root, self.task, self.commit, None)["tests"])

    def test_real_fix_passes(self):
        (self.root / "mod.py").write_text("VALUE = 1\n")
        self.assertTrue(cs.score(self.root, self.task, self.commit, None)["tests"])

    def test_model_added_test_file_is_removed_before_scoring(self):
        (self.root / "mod.py").write_text("VALUE = 1\n")
        (self.root / "tests/test_added.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.fail()\n")
        self.assertTrue(cs.score(self.root, self.task, self.commit, None)["tests"])
        self.assertFalse((self.root / "tests/test_added.py").exists())

    def test_worktree_file_cannot_shadow_the_hidden_test(self):
        hidden = self.root.parent / f"{self.root.name}-hidden"
        hidden.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(hidden))
        (hidden / "hidden_x.py").write_text(
            "import unittest, mod\nclass H(unittest.TestCase):\n"
            "    def test_value(self):\n        self.assertEqual(mod.VALUE, 1)\n")
        (self.root / "hidden_x.py").write_text("")  # an empty module would run zero tests and pass
        task = {"test_dir": "tests",
                "score_cmd": "cd {hidden_dir} && PYTHONPATH={worktree} python3 -m unittest -q hidden_x"}
        self.assertFalse(cs.score(self.root, task, self.commit, hidden)["tests"])
        (self.root / "mod.py").write_text("VALUE = 1\n")
        self.assertTrue(cs.score(self.root, task, self.commit, hidden)["tests"])


class TestLoop(WorkdirCase):
    def run_loop(self, responses, task=None):
        task = task or {"id": "T", "timeout_s": 60, "tests_cmd": "true"}
        with mock.patch.object(cs, "chat", side_effect=responses):
            return cs._loop(task, 1, "http://x", "m", {}, [{"role": "user", "content": "go"}],
                            cs.Tools(self.root, task, None), self.root, None)

    @staticmethod
    def call(name, arguments):
        return {"content": "", "reasoning": "", "finish_reason": "tool_calls", "usage": None, "timings": None,
                "tool_calls": [{"id": None, "name": name, "arguments": arguments}]}

    def test_final_message_completes(self):
        r = self.run_loop([self.call("run_tests", "{}"),
                           {"content": "done", "reasoning": "", "tool_calls": [], "finish_reason": "stop",
                            "usage": {"prompt_tokens": 5, "completion_tokens": 2}, "timings": None}])
        self.assertEqual((r["completed"], r["reason"], r["turns"]), (True, None, 2))
        self.assertEqual(r["tool_calls"], {"run_tests": 1})

    def test_three_unparseable_calls_stop_the_episode(self):
        r = self.run_loop([self.call("write_file", "{not json")] * 3)
        self.assertEqual((r["completed"], r["reason"], r["turns"]), (False, "bad-tool-call", 3))

    def test_length_stop_is_not_completed(self):
        r = self.run_loop([{"content": "partial", "reasoning": "", "tool_calls": [], "finish_reason": "length",
                            "usage": None, "timings": None}])
        self.assertEqual((r["completed"], r["reason"]), (False, "length"))

    def test_turn_limit(self):
        with mock.patch.object(cs, "MAX_TURNS", 2):
            r = self.run_loop([self.call("run_tests", "{}")] * 2)
        self.assertEqual((r["completed"], r["reason"], r["turns"]), (False, "turn-limit", 2))

    def test_timeout_is_recorded(self):
        r = self.run_loop(cs.EpisodeTimeout())
        self.assertEqual((r["completed"], r["reason"]), (False, "timeout"))

    def test_stream_without_terminal_event_is_not_completed(self):
        r = self.run_loop([{"content": "", "reasoning": "", "tool_calls": [], "finish_reason": None,
                            "usage": None, "timings": None}])
        self.assertEqual((r["completed"], r["reason"]), (False, "api-error"))

    def test_monitor_abort_stops_the_run_instead_of_scoring(self):
        monitor = mock.Mock(bad={"abort_reason": "evicted"}, error=None)
        task = {"id": "T", "timeout_s": 60, "tests_cmd": "true"}
        with self.assertRaises(cs.MonitorAbort):
            cs._loop(task, 1, "http://x", "m", {}, [{"role": "user", "content": "go"}],
                     cs.Tools(self.root, task, None), self.root, monitor)

    def test_reasoning_is_replayed_with_the_tool_call(self):
        first = dict(self.call("run_tests", "{}"), reasoning="check tests")
        final = {"content": "done", "reasoning": "", "tool_calls": [], "finish_reason": "stop",
                 "usage": None, "timings": None}
        seen = []

        def fake_chat(url, body, deadline, monitor=None):
            seen.append([dict(m) for m in body["messages"]])
            return [first, final][len(seen) - 1]
        task = {"id": "T", "timeout_s": 60, "tests_cmd": "true"}
        with mock.patch.object(cs, "chat", side_effect=fake_chat):
            cs._loop(task, 1, "http://x", "m", {}, [{"role": "user", "content": "go"}],
                     cs.Tools(self.root, task, None), self.root, None)
        self.assertEqual(seen[1][1]["reasoning_content"], "check tests")


class TestCompareRule(unittest.TestCase):
    def seeds(self, *passes):
        return {i + 1: p for i, p in enumerate(passes)}

    def test_rule(self):
        t, f = True, False
        cases = [
            (self.seeds(t, t, t), self.seeds(t, f, f), "regression"),
            (self.seeds(t, t, t), self.seeds(t, t, f), "inconclusive"),
            (self.seeds(t, t, f), self.seeds(t, t, t), "ok"),
            (self.seeds(t, t, t, t, t, t), self.seeds(t, t, f, t, t, t), "ok"),
            (self.seeds(t, t, t, t, t, t), self.seeds(t, t, f, t, f, t), "regression"),
        ]
        for base, cand, expected in cases:
            with self.subTest(base=base, cand=cand):
                self.assertTrue(cs.compare_task(base, cand).startswith(expected))

    def test_missing_seeds_or_tasks_are_incomplete(self):
        self.assertTrue(cs.compare_task(self.seeds(True, True, True), {}).startswith("incomplete"))
        self.assertTrue(cs.compare_task(self.seeds(True, True, True), {1: True}).startswith("incomplete"))
        self.assertTrue(cs.compare_task({1: True, 2: True}, {1: True, 2: True}).startswith("incomplete"))

    def test_seed_one_screen(self):
        for base, cand, expected in (({1: True}, {1: False}, "inconclusive: rerun this task with seeds 2,3"),
                                     ({1: True}, {1: True}, "ok"), ({1: False}, {1: False}, "ok"),
                                     ({1: False}, {1: True}, "ok")):
            with self.subTest(base=base, cand=cand):
                self.assertTrue(cs.compare_task(base, cand).startswith(expected))


if __name__ == "__main__":
    unittest.main()
