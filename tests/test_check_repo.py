"""Unit tests for scripts/check-repo.py (stdlib unittest only).

The module lives at a hyphenated filename, so it can't be `import`-ed normally;
it's loaded via importlib.util.spec_from_file_location, same pattern used in
tests/test_check_sync.py.

Covers the pure per-check functions with in-memory strings/paths -- no real
git repository or filesystem tree needed: `check_personal_paths` (including
the URL false-positive fix and the allowlist), `check_filename_spanish`, the
Spanish-content skip rules in `check_spanish` (marker, path allowlist, path
prefix), `strip_markdown_code`'s fence line-number alignment, and
`tracked_files`'s NUL-separated `git ls-files` parsing.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

_spec = importlib.util.spec_from_file_location("check_repo", SCRIPTS_DIR / "check-repo.py")
check_repo = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules["check_repo"] = check_repo
_spec.loader.exec_module(check_repo)


class TestCheckPersonalPaths(unittest.TestCase):
    def test_flags_home_path(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths("doc.md", "see /home/alice/project for details", problems)
        self.assertIn("doc.md", problems)

    def test_flags_mnt_path(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths("doc.md", "weights live at /mnt/hdd/models/foo.gguf", problems)
        self.assertIn("doc.md", problems)

    def test_flags_windows_users_path(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths("doc.md", r"copy from C:\Users\alice\models", problems)
        self.assertIn("doc.md", problems)

    def test_allowlisted_path_is_not_flagged(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths("doc.md", "mount point: /mnt/models", problems)
        self.assertNotIn("doc.md", problems)

    def test_url_media_path_is_not_flagged(self):
        # Regression for R3-personal-path-regex-overbroad: a URL whose path contains "/media/"
        # or "/srv/" must not be reported as a personal machine path.
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths(
            "doc.md", "see https://example.com/media/photo.jpg for the image", problems
        )
        self.assertNotIn("doc.md", problems)

    def test_url_srv_path_with_port_is_not_flagged(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths(
            "doc.md", "endpoint at host.example.com:8080/srv/api", problems
        )
        self.assertNotIn("doc.md", problems)

    def test_genuine_path_at_start_of_line_is_still_flagged(self):
        # The lookbehind must not blind the check to a real personal path just because it's
        # the first thing on the line.
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths("doc.md", "/mnt/hdd/IA/private-project", problems)
        self.assertIn("doc.md", problems)

    def test_path_directly_after_colon_is_still_flagged(self):
        # Regression: (?<![\w:]) also excluded ":" from the lookbehind, so a real path right
        # after a colon (an scp/rsync remote spec, a PATH-style list, a bind-mount spec) went
        # undetected. Only a word character right before "/" should suppress a match.
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths("doc.md", "rsync -a server:/mnt/hdd/x ./backup", problems)
        self.assertIn("doc.md", problems)

    def test_path_after_colon_in_path_style_list_is_still_flagged(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_personal_paths("doc.md", "PATH=/usr/bin:/mnt/hdd/tools/bin", problems)
        self.assertIn("doc.md", problems)


class TestSelfSecretPaths(unittest.TestCase):
    def test_check_repo_itself_is_exempt(self):
        # scripts/check-repo.py necessarily spells out one of the SECRET_PATTERNS labels as a
        # literal string, so it must stay exempt from check_secrets or it would flag itself.
        self.assertIn("scripts/check-repo.py", check_repo.SELF_SECRET_PATHS)

    def test_its_own_test_file_is_not_exempt(self):
        # tests/test_check_repo.py has no secret-pattern fixtures (only personal-path and
        # Spanish ones), so a real credential pasted into it later should still be caught.
        self.assertNotIn("tests/test_check_repo.py", check_repo.SELF_SECRET_PATHS)

    def test_check_secrets_still_flags_the_test_file(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_secrets("tests/test_check_repo.py", "token = sk-" + "a" * 24, problems)
        self.assertIn("tests/test_check_repo.py", problems)


class TestCheckFilenameSpanish(unittest.TestCase):
    def test_english_filename_is_clean(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_filename_spanish("docs/measurements/depth.md", problems)
        self.assertNotIn("docs/measurements/depth.md", problems)

    def test_spanish_word_in_filename_is_flagged(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_filename_spanish("docs/motores.md", problems)
        self.assertIn("docs/motores.md", problems)

    def test_spanish_accent_in_filename_is_flagged(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_filename_spanish("results/medición-kld.json", problems)
        self.assertIn("results/medición-kld.json", problems)


class TestCheckSpanish(unittest.TestCase):
    def test_flags_spanish_word_in_prose(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_spanish(
            "doc.md", pathlib.Path("doc.md"), "el perfil también cambia", problems
        )
        self.assertIn("doc.md", problems)

    def test_marker_skips_whole_file(self):
        problems: dict[str, list[str]] = {}
        text = "Deliberately Spanish (STYLE.md exception)\n\nel perfil también cambia"
        check_repo.check_spanish("bench/corpus.py", pathlib.Path("bench/corpus.py"), text, problems)
        self.assertNotIn("bench/corpus.py", problems)

    def test_exact_allowlisted_path_is_skipped(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_spanish(
            "docs/STYLE.md", pathlib.Path("docs/STYLE.md"), "perfil, motor, caché", problems
        )
        self.assertNotIn("docs/STYLE.md", problems)

    def test_results_prefix_is_skipped(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_spanish(
            "results/20260924-foo/summary.md",
            pathlib.Path("results/20260924-foo/summary.md"),
            "caso: perfil también",
            problems,
        )
        self.assertNotIn("results/20260924-foo/summary.md", problems)

    def test_spanish_inside_code_span_is_ignored_in_markdown(self):
        problems: dict[str, list[str]] = {}
        check_repo.check_spanish(
            "doc.md", pathlib.Path("doc.md"), "run `python motores.py` first", problems
        )
        self.assertNotIn("doc.md", problems)


class TestStripMarkdownCode(unittest.TestCase):
    def test_fenced_block_content_is_blanked_but_line_count_preserved(self):
        text = "line one\n```\nperfil\nmotor\n```\nline five"
        stripped = check_repo.strip_markdown_code(text)
        original_lines = text.splitlines()
        stripped_lines = stripped.splitlines()
        self.assertEqual(len(stripped_lines), len(original_lines))
        # The content inside the fence (including the fence markers themselves) is blanked...
        self.assertEqual(stripped_lines[1], "")
        self.assertEqual(stripped_lines[2], "")
        self.assertEqual(stripped_lines[3], "")
        self.assertEqual(stripped_lines[4], "")
        # ...while lines outside the fence are preserved, so line numbers reported against the
        # stripped text still point at the right line in the original file.
        self.assertEqual(stripped_lines[0], "line one")
        self.assertEqual(stripped_lines[5], "line five")

    def test_inline_code_span_is_removed_outside_fences(self):
        stripped = check_repo.strip_markdown_code("see `motores.py` here")
        self.assertNotIn("motores.py", stripped)


class TestTrackedFiles(unittest.TestCase):
    def test_parses_nul_separated_output(self):
        fake_result = mock.Mock()
        fake_result.stdout = "a.md\x00dir/b.py\x00"
        with mock.patch.object(check_repo.subprocess, "run", return_value=fake_result) as run:
            files = check_repo.tracked_files()
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][:2], ["git", "ls-files"])
        self.assertIn("-z", run.call_args.args[0])
        self.assertEqual(files, [check_repo.REPO / "a.md", check_repo.REPO / "dir/b.py"])

    def test_trailing_empty_segment_is_dropped(self):
        # git ls-files -z terminates every entry with NUL, so splitting on \0 always leaves one
        # trailing empty string that must not become a spurious empty-path entry.
        fake_result = mock.Mock()
        fake_result.stdout = "only.md\x00"
        with mock.patch.object(check_repo.subprocess, "run", return_value=fake_result):
            files = check_repo.tracked_files()
        self.assertEqual(files, [check_repo.REPO / "only.md"])


    def test_main_scans_shell_and_systemd_content(self):
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for suffix in (".sh", ".service", ".timer"):
                path = root / f"tracked{suffix}"
                path.write_text("secret = " + "sk" + "-" + "a" * 24 + "\npath=/mnt/hdd/private\n")
                output = io.StringIO()
                with mock.patch.object(check_repo, "REPO", root), \
                     mock.patch.object(check_repo, "tracked_files", return_value=[path]), \
                     contextlib.redirect_stdout(output):
                    self.assertEqual(check_repo.main(), 1)
                report = output.getvalue()
                self.assertIn("personal path", report)
                self.assertIn("looks like a", report)

if __name__ == "__main__":
    unittest.main()
