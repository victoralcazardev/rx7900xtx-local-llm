"""Unit tests for launcher command rendering and safe smoke preflight."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import pathlib
import sys
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _load_script(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


launch = _load_script("launch_test", "launch.py")
smoke = _load_script("smoke_test", "smoke.py")


class TestLauncherAndSmoke(unittest.TestCase):
    def test_launch_command_quotes_arguments_with_spaces(self):
        model = object()
        profile = {"context": 262144}
        m = mock.Mock(default_port=8080, allow_low_context=False)
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["launch.py", "demo", "--dry-run"]), \
             mock.patch.object(launch, "load", return_value=m), \
             mock.patch.object(launch, "resolve", return_value=(model, "default", profile)), \
             mock.patch.object(launch, "backend_for", return_value="vulkan"), \
             mock.patch.object(launch, "validate"), \
             mock.patch.object(launch, "harness_entry", return_value="local-262k"), \
             mock.patch.object(launch, "build_argv", return_value=["--model", "/models/a model.gguf"]), \
             mock.patch.object(launch, "free_vram_gib", return_value=None), \
             contextlib.redirect_stdout(output):
            self.assertEqual(launch.main(), 0)
        self.assertIn("'/models/a model.gguf'", output.getvalue())

    def test_dry_run_warns_only_when_free_vram_is_below_profile_need_plus_margin(self):
        profile = {"context": 262144, "vram_gib": 22.0}
        # free < needed + VRAM_MARGIN_GIB (0.5) warns; the boundary itself does not.
        for free, warns in ((21.9, True), (22.4, True), (22.5, False), (24.0, False)):
            m = mock.Mock(default_port=8080, allow_low_context=False)
            out, err = io.StringIO(), io.StringIO()
            with self.subTest(free=free), \
                 mock.patch.object(sys, "argv", ["launch.py", "demo", "--dry-run"]), \
                 mock.patch.object(launch, "load", return_value=m), \
                 mock.patch.object(launch, "resolve", return_value=(object(), "default", profile)), \
                 mock.patch.object(launch, "backend_for", return_value="vulkan"), \
                 mock.patch.object(launch, "validate"), \
                 mock.patch.object(launch, "harness_entry", return_value="local-262k"), \
                 mock.patch.object(launch, "build_argv", return_value=[]), \
                 mock.patch.object(launch, "free_vram_gib", return_value=free), \
                 contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(launch.main(), 0)  # a warning never blocks the launch
                self.assertIn(f"VRAM: {free:.1f} GiB free", out.getvalue())
                self.assertEqual("WARNING: less than 0.5 GiB of margin" in err.getvalue(), warns)

    def test_tee_copies_server_output_to_console_and_log(self):
        src = io.BufferedReader(io.BytesIO(b"line 1\nline 2\n"))
        console, log = io.BytesIO(), io.BytesIO()
        launch._tee(src, console, log)
        self.assertEqual(console.getvalue(), b"line 1\nline 2\n")
        self.assertEqual(log.getvalue(), b"line 1\nline 2\n")

    def test_smoke_aborts_when_process_detection_fails(self):
        model = object()
        profile = {"context": 131072}
        m = mock.Mock(allow_low_context=False)
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["smoke.py", "demo"]), \
             mock.patch.object(smoke, "load", return_value=m), \
             mock.patch.object(smoke, "resolve", return_value=(model, "default", profile)), \
             mock.patch.object(smoke, "backend_for", return_value="vulkan"), \
             mock.patch.object(smoke, "validate"), \
             mock.patch.object(smoke, "server_executable", return_value=pathlib.Path("server")), \
             mock.patch.object(smoke, "running_servers", return_value=None), \
             contextlib.redirect_stdout(output):
            self.assertEqual(smoke.main(), 2)
        self.assertIn("could not detect running llama-server", output.getvalue())


if __name__ == "__main__":
    unittest.main()
