"""CPU-only regression coverage for the published KVMem rerun scripts."""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
KVMEM_RESULTS = (
    REPO / "results/20260930-kvmem-trial/kvmem_quality.py",
    REPO / "results/20260930-kvmem-trial-round2/kvmem_quality.py",
)
BUILD_CHECK = REPO / "results/20260930-kvmem-trial-round2/scripts/build-result.sh"
FINAL_RUN = REPO / "results/20260930-kvmem-trial-round2/scripts/run-final.sh"


class TestPublishedQualityHelpers(unittest.TestCase):
    def test_help_loads_evaluator_from_published_script_path_outside_repo(self):
        for script in KVMEM_RESULTS:
            with self.subTest(script=script.parent.name), tempfile.TemporaryDirectory() as cwd:
                result = subprocess.run(
                    [sys.executable, str(script), "--help"], cwd=cwd,
                    text=True, capture_output=True, check=False,
                )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage:", result.stdout.lower())


class TestBuildResultGuard(unittest.TestCase):
    def run_fixture(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", f'source "$1"; {script}', "build-result-test", str(BUILD_CHECK), *args],
            cwd=REPO, text=True, capture_output=True, check=False,
        )

    def test_run_final_checks_background_build_before_using_binary(self):
        source = FINAL_RUN.read_text()
        self.assertIn("check_build_result", source)

    def test_build_failure_is_not_hidden_by_an_existing_stale_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = pathlib.Path(tmp) / "llama-server"
            stale.write_text("stale build fixture\n")
            stale.chmod(0o755)
            result = self.run_fixture(
                ' (exit 17) & pid=$!; check_build_result "$pid" "$2"', str(stale)
            )
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertIn("BUILD_EXIT=17", result.stdout)

    def test_success_requires_the_new_binary_to_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = pathlib.Path(tmp) / "llama-server"
            result = self.run_fixture(
                ' (exit 0) & pid=$!; check_build_result "$pid" "$2"', str(missing)
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("NO_NEW_BINARY", result.stderr)

    def test_success_accepts_the_expected_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "llama-server"
            binary.write_text("fixture\n")
            binary.chmod(0o755)
            result = self.run_fixture(
                ' (exit 0) & pid=$!; check_build_result "$pid" "$2"', str(binary)
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BUILD_EXIT=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
