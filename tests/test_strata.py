"""Unit tests for scripts/strata.py: tracked settings applied to a Strata run config (no Strata, no GPU)."""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import strata  # noqa: E402
from manifest import ManifestError  # noqa: E402

GENERATED = {"exe": "engine/strata", "args": ["--kv", "int8"], "env": {"STRATA_RESIDENT_PIN": "0"}, "port": 8080}
TRACKED = {"config": "strata-x.json", "user_args": ["--vram-reserve-mib", "3072"],
           "env": {"STRATA_RESIDENT_HEADROOM_GIB": 6}, "sampling": {"temperature": 1.0}}


class OverlayTest(unittest.TestCase):
    def test_env_is_merged_and_other_keys_replaced(self):
        new = strata.overlay(GENERATED, TRACKED)
        self.assertEqual(new["env"], {"STRATA_RESIDENT_PIN": "0", "STRATA_RESIDENT_HEADROOM_GIB": "6"})
        self.assertEqual(new["user_args"], ["--vram-reserve-mib", "3072"])
        self.assertEqual(new["sampling"], {"temperature": 1.0})
        self.assertEqual(new["args"], ["--kv", "int8"])   # setup's generated args are left alone
        self.assertNotIn("config", new)
        self.assertEqual(GENERATED["env"], {"STRATA_RESIDENT_PIN": "0"})   # input not mutated

    def test_applying_twice_changes_nothing(self):
        once = strata.overlay(GENERATED, TRACKED)
        self.assertEqual(strata.changes(once, strata.overlay(once, TRACKED)), [])


class ApplyAllTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.cfg = self.dir / "strata-x.json"
        self.cfg.write_text(json.dumps(GENERATED))

    def run_apply(self, tables, dry_run):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            n = strata.apply_all(self.dir, tables, dry_run)
        return n, out.getvalue()

    def test_dry_run_reports_drift_without_writing(self):
        n, out = self.run_apply({"x": TRACKED}, dry_run=True)
        self.assertEqual(n, 1)
        self.assertIn("env.STRATA_RESIDENT_HEADROOM_GIB: None -> '6'", out)
        self.assertEqual(json.loads(self.cfg.read_text()), GENERATED)

    def test_apply_writes_then_reports_no_drift(self):
        self.run_apply({"x": TRACKED}, dry_run=False)
        self.assertEqual(json.loads(self.cfg.read_text()), strata.overlay(GENERATED, TRACKED))
        n, out = self.run_apply({"x": TRACKED}, dry_run=True)
        self.assertEqual(n, 0)
        self.assertIn("matches models.toml", out)

    def test_missing_config_is_reported_not_created(self):
        n, out = self.run_apply({"y": {**TRACKED, "config": "strata-y.json"}}, dry_run=False)
        self.assertEqual(n, 1)
        self.assertFalse((self.dir / "strata-y.json").exists())
        self.assertIn("does not exist", out)


class LoadSettingsTest(unittest.TestCase):
    def write(self, name, text):
        p = pathlib.Path(tempfile.mkdtemp()) / name
        p.write_text(text)
        return p

    def test_strata_dir_is_required(self):
        models = self.write("models.toml", '[strata.x]\nconfig = "strata-x.json"\n')
        local = self.write("local.toml", 'models_root = "/m"\n')
        with self.assertRaisesRegex(ManifestError, "strata_dir"):
            strata.load_settings(models, local)

    def test_table_without_config_is_rejected(self):
        models = self.write("models.toml", "[strata.x]\nuser_args = []\n")
        local = self.write("local.toml", 'strata_dir = "/s"\n')
        with self.assertRaisesRegex(ManifestError, "config"):
            strata.load_settings(models, local)

    def test_repository_models_toml_tables_are_valid(self):
        local = self.write("local.toml", 'strata_dir = "/s"\n')
        _, tables = strata.load_settings(REPO_ROOT / "models.toml", local)
        self.assertTrue(tables)


if __name__ == "__main__":
    unittest.main()
