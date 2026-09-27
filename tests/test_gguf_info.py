"""Unit tests for scripts/gguf_info.py's dependency and per-file error paths."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("gguf_info", REPO_ROOT / "scripts" / "gguf_info.py")
gguf_info = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["gguf_info"] = gguf_info
SPEC.loader.exec_module(gguf_info)


class TestGgufInfoErrors(unittest.TestCase):
    def test_help_does_not_require_gguf_dependency(self):
        with self.assertRaises(SystemExit) as ctx:
            gguf_info.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_missing_path_returns_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                result = gguf_info.main([str(pathlib.Path(tmp) / "missing.gguf")])
        self.assertEqual(result, 1)
        self.assertIn("could not stat file", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_missing_gguf_package_has_install_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "model.gguf"
            path.touch()
            original_import = __import__

            def without_gguf(name, *args, **kwargs):
                if name == "gguf":
                    raise ImportError("not installed")
                return original_import(name, *args, **kwargs)

            output = io.StringIO()
            with mock.patch("builtins.__import__", side_effect=without_gguf), \
                 contextlib.redirect_stderr(output):
                self.assertFalse(gguf_info.describe(path))
            self.assertIn("python3 -m pip install gguf", output.getvalue())


if __name__ == "__main__":
    unittest.main()
