"""Unit tests for scripts/build_engine.py (stdlib unittest only).

Covers everything that needs no GPU, no compiler and no network: local.toml `[build]` parsing
(including both defaults), the engine folder-name derivation, the `--dry-run` command plan for a
ref with and without patches, the refusal to overwrite an existing engine folder, and the failure
message of a patch that does not apply (a real `git apply` in a temp checkout, no clone).

Every check goes through the command line where it can: exit codes and stdout/stderr of
`python3 scripts/build_engine.py …` with `LOCAL_MANIFEST` pointing at a temp local.toml.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPT = SCRIPTS_DIR / "build_engine.py"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_engine  # noqa: E402
import manifest  # noqa: E402

PATCH_TESTS = "engine-patches/tests-kvmix-cases-b12633.patch"
PATCH_KERNEL = "engine-patches/pr30792-q5_1-b12633.patch"
ENGINE_B12633 = "llama-b12633-linux-rocm-gfx1100-kvmix"
ENGINE_B12633_PATCHED = "llama-b12633-pr30792q51-linux-rocm-gfx1100-kvmix"


def _git(cwd: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    # user.name/user.email come from -c so the test never reads (or needs) a global git config.
    return subprocess.run(
        ["git", "-c", "user.name=check", "-c", "user.email=check", *args],
        cwd=cwd, capture_output=True, text=True,
    )


class BuildEngineFixture(unittest.TestCase):
    """A temp machine: an engines folder with the configured `hip-kvmix` engine inside it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.engines = self.root / "engines"
        self.engines.mkdir()
        self.hip_kvmix = self.engines / "llama-v0.9.0-linux-rocm-gfx1100-kvmix"
        self.hip_kvmix.mkdir()
        self.local_path = self.write_local("")

    def write_local(self, extra: str) -> pathlib.Path:
        """A local.toml with `[engines] hip-kvmix` set and `extra` (e.g. a `[build]` table) above it."""
        # as_posix(): a Windows backslash inside a TOML basic string is an escape sequence.
        path = pathlib.Path(tempfile.mkstemp(dir=self.root, suffix=".toml")[1])
        path.write_text(
            f'models_root = "{(self.root / "models").as_posix()}"\n'
            f"{extra}\n"
            "[engines]\n"
            f'hip-kvmix = "{self.hip_kvmix.as_posix()}"\n'
        )
        return path

    def run_cli(self, *args: str, local: pathlib.Path | None = None) -> subprocess.CompletedProcess:
        env = {**os.environ, "LOCAL_MANIFEST": str(local or self.local_path)}
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
        )

    def make_source_checkout(self) -> str:
        """A real git checkout at the default source root, with HEAD as the ref to build.

        The folder is renamed to `llama.cpp-<HEAD sha>` so the script finds a checkout of exactly
        the requested ref: no clone, no network.
        """
        work = self.root / "checkout"
        work.mkdir()
        _git(work, "init", "-q")
        (work / "a.txt").write_text("hello\n")
        _git(work, "add", "a.txt")
        _git(work, "commit", "-q", "-m", "base")
        head = _git(work, "rev-parse", "HEAD").stdout.strip()
        src_root = self.engines / "src"
        src_root.mkdir(exist_ok=True)
        work.rename(src_root / f"llama.cpp-{head}")
        return head


class TestBuildConfig(BuildEngineFixture):
    def test_parses_the_build_table(self):
        extra = (
            "[build]\n"
            f'src_root = "{(self.root / "checkouts").as_posix()}"\n'
            f'engines_root = "{(self.root / "built").as_posix()}"\n'
            f'hip_runtime_lib = "{(self.root / "lib" / "libamdhip64.so.7").as_posix()}"\n'
        )
        cfg = build_engine.load_build_config(self.write_local(extra))
        self.assertEqual(cfg.src_root, self.root / "checkouts")
        self.assertEqual(cfg.engines_root, self.root / "built")
        self.assertEqual(cfg.hip_runtime_lib, self.root / "lib" / "libamdhip64.so.7")

    def test_defaults_follow_the_configured_hip_kvmix_engine(self):
        cfg = build_engine.load_build_config(self.local_path)
        self.assertEqual(cfg.engines_root, self.engines)
        self.assertEqual(cfg.src_root, self.engines / "src")
        self.assertIsNone(cfg.hip_runtime_lib)

    def test_no_build_table_and_no_hip_kvmix_names_the_example_file(self):
        local = pathlib.Path(tempfile.mkstemp(dir=self.root, suffix=".toml")[1])
        local.write_text(f'models_root = "{(self.root / "models").as_posix()}"\n')
        with self.assertRaises(manifest.ManifestError) as ctx:
            build_engine.load_build_config(local)
        self.assertIn("local.example.toml", str(ctx.exception))


class TestEngineName(unittest.TestCase):
    def test_no_patch(self):
        self.assertEqual(build_engine.engine_name("b12633", []), ENGINE_B12633)

    def test_kernel_patch_names_the_engine(self):
        patches = [REPO_ROOT / PATCH_TESTS, REPO_ROOT / PATCH_KERNEL]
        self.assertEqual(build_engine.engine_name("b12633", patches), ENGINE_B12633_PATCHED)

    def test_test_only_patch_adds_no_tag(self):
        self.assertEqual(build_engine.engine_name("b12633", [REPO_ROOT / PATCH_TESTS]), ENGINE_B12633)

    def test_explicit_name_wins(self):
        self.assertEqual(
            build_engine.engine_name("b12633", [REPO_ROOT / PATCH_KERNEL], "check-build"),
            "check-build",
        )


class TestDryRun(BuildEngineFixture):
    def test_plan_without_patches_prints_commands_and_changes_nothing(self):
        r = self.run_cli("--ref", "b12633", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        src = self.engines / "src" / "llama.cpp-b12633"
        self.assertIn(f"+ git clone --filter=blob:none https://github.com/ggml-org/llama.cpp {src}", out)
        self.assertIn("checkout b12633", out)
        self.assertIn("-DCMAKE_BUILD_TYPE=Release", out)
        self.assertIn("-DGGML_BACKEND_DL=ON", out)
        self.assertIn("-DCMAKE_INSTALL_RPATH=$ORIGIN", out)
        self.assertIn("-DGGML_CPU_ALL_VARIANTS=ON", out)
        self.assertIn("-DGPU_TARGETS=gfx1100", out)
        self.assertIn("-DGGML_CUDA_FA_QUANTS=f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0", out)
        self.assertIn(
            "--target llama-server llama-bench llama-perplexity test-backend-ops", out
        )
        self.assertIn(str(self.engines / ENGINE_B12633), out)
        self.assertNotIn(" apply ", out)
        self.assertIn("dry run:", out)
        self.assertFalse((self.engines / ENGINE_B12633).exists())
        self.assertFalse((self.engines / "src").exists())

    def test_plan_with_patches_applies_them_in_the_given_order(self):
        r = self.run_cli(
            "--ref", "b12633", "--patch", PATCH_TESTS, "--patch", PATCH_KERNEL, "--dry-run"
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        applies = [line for line in r.stdout.splitlines() if " apply " in line]
        self.assertEqual(len(applies), 2, r.stdout)
        self.assertIn(PATCH_TESTS, applies[0])
        self.assertIn(PATCH_KERNEL, applies[1])
        self.assertIn(str(self.engines / ENGINE_B12633_PATCHED), r.stdout)
        self.assertTrue((REPO_ROOT / PATCH_TESTS).exists())

    def test_explicit_name_is_used_verbatim(self):
        r = self.run_cli("--ref", "b12633", "--name", "check-build", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(str(self.engines / "check-build"), r.stdout)

    def test_hip_runtime_lib_plans_the_symlink_and_the_ldd_check(self):
        lib = self.root / "rocm" / "lib" / "libamdhip64.so.7.16.0-000000000"
        local = self.write_local(f'[build]\nhip_runtime_lib = "{lib.as_posix()}"\n')
        r = self.run_cli("--ref", "b12633", "--dry-run", local=local)
        self.assertEqual(r.returncode, 0, r.stderr)
        engine = self.engines / ENGINE_B12633
        self.assertIn(f"+ ln -sfn {lib} {engine / 'libamdhip64.so.7'}", r.stdout)
        self.assertIn(f"ldd {engine / 'libggml-hip.so'}", r.stdout)

    def test_ref_with_a_slash_needs_a_name(self):
        r = self.run_cli("--ref", "feat/branch", "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--name", r.stderr)


class TestRefusal(BuildEngineFixture):
    def test_existing_engine_folder_is_refused(self):
        target = self.engines / ENGINE_B12633_PATCHED
        target.mkdir()
        (target / "keep.txt").write_text("an older build\n")
        r = self.run_cli("--ref", "b12633", "--patch", PATCH_KERNEL)
        self.assertEqual(r.returncode, 2)
        self.assertIn("already exists", r.stderr)
        self.assertIn(str(target), r.stderr)
        self.assertEqual([p.name for p in target.iterdir()], ["keep.txt"])

    def test_existing_engine_folder_is_refused_in_a_dry_run_too(self):
        (self.engines / ENGINE_B12633).mkdir()
        r = self.run_cli("--ref", "b12633", "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("already exists", r.stderr)
        self.assertNotIn("git clone", r.stdout)


class TestPatchFailure(BuildEngineFixture):
    def test_patch_that_does_not_apply_names_the_patch_and_its_files(self):
        ref = self.make_source_checkout()
        bad = self.root / "bad.patch"
        bad.write_text(
            "diff --git a/a.txt b/a.txt\n"
            "--- a/a.txt\n"
            "+++ b/a.txt\n"
            "@@ -1 +1 @@\n"
            "-goodbye\n"
            "+hello world\n"
        )
        r = self.run_cli("--ref", ref, "--patch", str(bad))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(str(bad), r.stderr)
        self.assertIn("does not apply", r.stderr)
        self.assertIn("a.txt", r.stderr)
        self.assertIn("rebase", r.stderr)
        self.assertFalse((self.engines / f"llama-{ref}-linux-rocm-gfx1100-kvmix").exists())

    def test_missing_patch_file_is_a_configuration_error(self):
        r = self.run_cli("--ref", "b12633", "--patch", "engine-patches/missing.patch", "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("missing.patch", r.stderr)


if __name__ == "__main__":
    unittest.main()
