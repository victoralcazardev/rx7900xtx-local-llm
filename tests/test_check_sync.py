"""Unit tests for scripts/check-sync.py (stdlib unittest only).

The module lives at a hyphenated filename, so it can't be `import`-ed normally;
it's loaded via importlib.util.spec_from_file_location, same as the module
itself does for depth_bench.py in bench/longctx_quality.py.

Covers the pure port/localhost matching logic: `_is_local` and
`validate_harness` (both take plain data in and return data/booleans out, no
network or filesystem access).
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

_spec = importlib.util.spec_from_file_location("check_sync", SCRIPTS_DIR / "check-sync.py")
check_sync = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules["check_sync"] = check_sync  # let dataclasses/pickle-style introspection resolve
_spec.loader.exec_module(check_sync)


class TestIsLocal(unittest.TestCase):
    def test_127_0_0_1_is_local(self):
        self.assertTrue(check_sync._is_local("http://127.0.0.1:8080/v1"))

    def test_localhost_is_local(self):
        self.assertTrue(check_sync._is_local("http://localhost:8080"))

    def test_remote_host_is_not_local(self):
        self.assertFalse(check_sync._is_local("https://api.openai.com/v1"))

    def test_empty_or_none_is_not_local(self):
        self.assertFalse(check_sync._is_local(""))
        self.assertFalse(check_sync._is_local(None))


class TestValidateHarness(unittest.TestCase):
    def _entries(self, *rows):
        # row: (provider_id, model_id, contextWindow, baseUrl)
        return list(rows)

    def test_exact_match_has_no_problems(self):
        entries = self._entries(
            ("p1", "local-128k", 131072, "http://127.0.0.1:8080/v1"),
            ("p1", "local-224k", 229376, "http://127.0.0.1:8080/v1"),
        )
        self.assertEqual(check_sync.validate_harness("t", entries), [])

    def test_remote_entries_are_ignored(self):
        entries = self._entries(
            ("p1", "local-128k", 131072, "http://127.0.0.1:8080/v1"),
            ("p1", "local-224k", 229376, "http://127.0.0.1:8080/v1"),
            ("p2", "gpt-4", 128000, "https://api.openai.com/v1"),
        )
        self.assertEqual(check_sync.validate_harness("t", entries), [])

    def test_missing_provider_reported(self):
        entries = self._entries(
            ("p1", "local-128k", 131072, "http://127.0.0.1:8080/v1"),
        )
        problems = check_sync.validate_harness("t", entries)
        self.assertEqual(len(problems), 1)
        self.assertIn("missing local provider 'local-224k'", problems[0])

    def test_wrong_port_reported(self):
        entries = self._entries(
            ("p1", "local-128k", 131072, "http://127.0.0.1:9999/v1"),
            ("p1", "local-224k", 229376, "http://127.0.0.1:8080/v1"),
        )
        problems = check_sync.validate_harness("t", entries)
        self.assertEqual(len(problems), 1)
        self.assertIn("expected port :8080", problems[0])

    def test_wrong_context_window_reported(self):
        entries = self._entries(
            ("p1", "local-128k", 8192, "http://127.0.0.1:8080/v1"),
            ("p1", "local-224k", 229376, "http://127.0.0.1:8080/v1"),
        )
        problems = check_sync.validate_harness("t", entries)
        self.assertEqual(len(problems), 1)
        self.assertIn("contextWindow=8192, expected 131072", problems[0])

    def test_orphaned_local_provider_reported(self):
        entries = self._entries(
            ("p1", "local-128k", 131072, "http://127.0.0.1:8080/v1"),
            ("p1", "local-224k", 229376, "http://127.0.0.1:8080/v1"),
            ("p1", "old-local-model", 131072, "http://127.0.0.1:8080/v1"),
        )
        problems = check_sync.validate_harness("t", entries)
        self.assertEqual(len(problems), 1)
        self.assertIn("orphaned local provider 'old-local-model'", problems[0])

    def test_port_in_middle_of_url_accepted(self):
        entries = self._entries(
            ("p1", "local-128k", 131072, "http://127.0.0.1:8080/some/path"),
            ("p1", "local-224k", 229376, "http://127.0.0.1:8080/some/path"),
        )
        self.assertEqual(check_sync.validate_harness("t", entries), [])


class TestHarnessEntries(unittest.TestCase):
    """_harness_entries reads one JSON config file: covered with a temp file,
    no network access."""

    def test_reads_json_target(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "models.json"
            path.write_text(json.dumps({
                "providers": {
                    "p1": {
                        "baseUrl": "http://127.0.0.1:8080/v1",
                        "models": [
                            {"id": "local-128k", "contextWindow": 131072},
                            {"id": "local-224k", "contextWindow": 229376},
                        ],
                    }
                }
            }))
            target = {"name": "t", "path": str(path), "format": "json", "root": []}
            entries, error = check_sync._harness_entries(target)
            self.assertIsNone(error)
            self.assertEqual(len(entries), 2)
            self.assertEqual(check_sync.validate_harness("t", entries), [])

    def test_missing_file_reports_error(self):
        target = {"name": "t", "path": "/no/such/file.json", "format": "json", "root": []}
        entries, error = check_sync._harness_entries(target)
        self.assertIsNone(entries)
        self.assertIn("does not exist", error)


if __name__ == "__main__":
    unittest.main()
