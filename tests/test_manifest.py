"""Unit tests for scripts/manifest.py (stdlib unittest only).

Covers manifest loading, profile resolution, and validation rules against small
TOML fixtures written to a temp directory, plus a check that the repository's
real models.toml loads and validates cleanly (file existence is stubbed so this
never touches actual GGUF weights or the GPU).
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import manifest  # noqa: E402


def _write(path: pathlib.Path, content: str) -> pathlib.Path:
    path.write_text(content)
    return path


MODELS_TOML_MINIMAL = """
[defaults]
port = 8080
flags = ["-fa", "on"]

[models.solo]
gguf = "solo/solo.gguf"
backend = "hip"

[models.solo.profiles.default]
context = 131072
kv = ["q8_0", "q8_0"]

[models.multi]
gguf = "multi/multi.gguf"
backend = "vulkan"

[models.multi.profiles.a]
context = 131072
kv = ["f16", "f16"]

[models.multi.profiles.b]
context = 204800
kv = ["f16", "f16"]
"""

LOCAL_TOML_MINIMAL = """
models_root = "{root}"

[engines]
vulkan = "{root}/engines/vulkan"
hip = "{root}/engines/hip"
"""


class ManifestFixture(unittest.TestCase):
    """Builds a temp models.toml + local.toml pair, mirroring the real layout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.models_path = _write(self.root / "models.toml", MODELS_TOML_MINIMAL)
        # as_posix(): the temp path goes into a TOML basic (double-quoted) string, where a
        # Windows backslash would be read as an escape sequence.
        self.local_path = _write(
            self.root / "local.toml", LOCAL_TOML_MINIMAL.format(root=self.root.as_posix())
        )

    def load(self, models_toml: str | None = None) -> manifest.Manifest:
        models_path = self.models_path
        if models_toml is not None:
            models_path = _write(self.root / "models-alt.toml", models_toml)
        return manifest.load(manifest=models_path, local=self.local_path)


class TestLoad(ManifestFixture):
    def test_loads_defaults_and_models(self):
        m = self.load()
        self.assertEqual(m.default_port, 8080)
        self.assertEqual(m.default_flags, ["-fa", "on"])
        self.assertEqual(m.models_root, self.root)
        self.assertEqual(set(m.models), {"solo", "multi"})
        self.assertFalse(m.allow_low_context)

    def test_engines_parsed_and_empty_values_dropped(self):
        # as_posix(): avoid a Windows backslash being read as a TOML escape sequence.
        root = self.root.as_posix()
        local_toml = f"""
models_root = "{root}"

[engines]
vulkan = "{root}/engines/vulkan"
hip = ""
"""
        local_path = _write(self.root / "local2.toml", local_toml)
        m = manifest.load(manifest=self.models_path, local=local_path)
        self.assertEqual(set(m.engines), {"vulkan"})

    def test_missing_local_toml_raises(self):
        missing = self.root / "does-not-exist.toml"
        with self.assertRaises(manifest.ManifestError):
            manifest.load(manifest=self.models_path, local=missing)

    def test_model_without_profiles_raises(self):
        bad = MODELS_TOML_MINIMAL + "\n[models.empty]\ngguf = \"empty/e.gguf\"\nbackend = \"hip\"\n"
        with self.assertRaises(manifest.ManifestError):
            self.load(models_toml=bad)

    def test_allow_low_context_flag_read(self):
        bad = "allow_low_context = true\n" + MODELS_TOML_MINIMAL
        m = self.load(models_toml=bad)
        self.assertTrue(m.allow_low_context)

    def test_env_var_overrides_used_when_no_explicit_path(self):
        with mock.patch.dict(
            "os.environ",
            {"MODELS_MANIFEST": str(self.models_path), "LOCAL_MANIFEST": str(self.local_path)},
        ):
            m = manifest.load()
        self.assertEqual(set(m.models), {"solo", "multi"})

    def test_no_defaults_means_no_default_alias(self):
        m = self.load()
        self.assertIsNone(m.default_alias)
        self.assertIsNone(m.default_profile)

    def test_default_alias_and_profile_read(self):
        toml = MODELS_TOML_MINIMAL.replace(
            "[defaults]\nport = 8080",
            '[defaults]\nport = 8080\ndefault_alias = "multi"\ndefault_profile = "b"',
        )
        m = self.load(models_toml=toml)
        self.assertEqual(m.default_alias, "multi")
        self.assertEqual(m.default_profile, "b")

    def test_default_alias_must_resolve(self):
        toml = MODELS_TOML_MINIMAL.replace(
            "[defaults]\nport = 8080",
            '[defaults]\nport = 8080\ndefault_alias = "nope"\ndefault_profile = "b"',
        )
        with self.assertRaises(manifest.ManifestError):
            self.load(models_toml=toml)

    def test_default_alias_without_default_profile_raises(self):
        toml = MODELS_TOML_MINIMAL.replace(
            "[defaults]\nport = 8080",
            '[defaults]\nport = 8080\ndefault_alias = "multi"',
        )
        with self.assertRaises(manifest.ManifestError):
            self.load(models_toml=toml)


class TestResolve(ManifestFixture):
    def test_unknown_alias_raises(self):
        m = self.load()
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.resolve(m, "nope", None)
        self.assertIn("unknown model", str(ctx.exception))

    def test_single_profile_auto_selected(self):
        m = self.load()
        model, profile_name, profile = manifest.resolve(m, "solo", None)
        self.assertEqual(profile_name, "default")
        self.assertEqual(profile["context"], 131072)

    def test_multi_profile_requires_explicit_choice(self):
        m = self.load()
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.resolve(m, "multi", None)
        self.assertIn("pick one with --profile", str(ctx.exception))

    def test_multi_profile_explicit_choice_resolves(self):
        m = self.load()
        model, profile_name, profile = manifest.resolve(m, "multi", "b")
        self.assertEqual(profile_name, "b")
        self.assertEqual(profile["context"], 204800)

    def test_unknown_profile_raises(self):
        m = self.load()
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.resolve(m, "multi", "nope")
        self.assertIn("no profile 'nope'", str(ctx.exception))

    def test_no_alias_uses_default_alias_and_profile(self):
        toml = MODELS_TOML_MINIMAL.replace(
            "[defaults]\nport = 8080",
            '[defaults]\nport = 8080\ndefault_alias = "multi"\ndefault_profile = "b"',
        )
        m = self.load(models_toml=toml)
        model, profile_name, profile = manifest.resolve(m, None, None)
        self.assertEqual(model.alias, "multi")
        self.assertEqual(profile_name, "b")
        self.assertEqual(profile["context"], 204800)

    def test_no_alias_with_explicit_profile_overrides_default_profile(self):
        toml = MODELS_TOML_MINIMAL.replace(
            "[defaults]\nport = 8080",
            '[defaults]\nport = 8080\ndefault_alias = "multi"\ndefault_profile = "b"',
        )
        m = self.load(models_toml=toml)
        model, profile_name, profile = manifest.resolve(m, None, "a")
        self.assertEqual(model.alias, "multi")
        self.assertEqual(profile_name, "a")

    def test_no_alias_without_defaults_raises(self):
        m = self.load()
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.resolve(m, None, None)
        self.assertIn("no alias given", str(ctx.exception))


class TestHarnessEntry(unittest.TestCase):
    def test_at_or_above_224k_context(self):
        self.assertEqual(manifest.harness_entry(manifest.LOCAL_224K_CONTEXT), "local-224k")
        self.assertEqual(manifest.harness_entry(manifest.LOCAL_224K_CONTEXT + 1), "local-224k")

    def test_between_128k_and_224k(self):
        self.assertEqual(manifest.harness_entry(manifest.MIN_CONTEXT), "local-128k")
        self.assertEqual(
            manifest.harness_entry(manifest.LOCAL_224K_CONTEXT - 1), "local-128k"
        )

    def test_below_min_context_raises(self):
        with self.assertRaises(manifest.ManifestError):
            manifest.harness_entry(manifest.MIN_CONTEXT - 1)


class TestBackendFor(unittest.TestCase):
    def _model(self, backend: str) -> manifest.Model:
        return manifest.Model(
            alias="m", gguf=pathlib.Path("m.gguf"), backend=backend, mtp=False,
            sampling={}, mmproj=None, profiles={},
        )

    def test_override_wins(self):
        model = self._model("hip")
        self.assertEqual(manifest.backend_for(model, {"backend": "vulkan"}, "hip-kvmix"), "hip-kvmix")

    def test_profile_backend_wins_over_model(self):
        model = self._model("hip")
        self.assertEqual(manifest.backend_for(model, {"backend": "vulkan"}), "vulkan")

    def test_falls_back_to_model_backend(self):
        model = self._model("hip")
        self.assertEqual(manifest.backend_for(model, {}), "hip")


class TestUsesVision(unittest.TestCase):
    def _model(self, mmproj) -> manifest.Model:
        return manifest.Model(
            alias="m", gguf=pathlib.Path("m.gguf"), backend="hip", mtp=False,
            sampling={}, mmproj=mmproj, profiles={},
        )

    def test_no_mmproj_means_no_vision(self):
        model = self._model(None)
        self.assertFalse(manifest.uses_vision(model, {}))

    def test_mmproj_defaults_to_true(self):
        model = self._model(pathlib.Path("mmproj.gguf"))
        self.assertTrue(manifest.uses_vision(model, {}))

    def test_profile_can_disable_vision(self):
        model = self._model(pathlib.Path("mmproj.gguf"))
        self.assertFalse(manifest.uses_vision(model, {"vision": False}))


class TestValidate(unittest.TestCase):
    """Uses real (empty) temp files so gguf.exists()/mmproj.exists() checks pass."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.gguf = self.root / "model.gguf"
        self.gguf.write_bytes(b"")
        self.mmproj = self.root / "mmproj.gguf"
        self.mmproj.write_bytes(b"")
        self.m = manifest.Manifest(
            default_port=8080, default_flags=[], models_root=self.root,
            engines={}, models={}, allow_low_context=False,
        )

    def _model(self, mmproj=None) -> manifest.Model:
        return manifest.Model(
            alias="m", gguf=self.gguf, backend="hip", mtp=False, sampling={},
            mmproj=mmproj, profiles={},
        )

    def test_valid_profile_passes(self):
        model = self._model()
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"]}
        manifest.validate(self.m, model, "p", profile, "hip")  # no raise

    def test_missing_gguf_raises(self):
        model = self._model()
        model.gguf = self.root / "missing.gguf"
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"]}
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(self.m, model, "p", profile, "hip")

    def test_missing_mmproj_raises_when_vision_used(self):
        model = self._model(mmproj=self.root / "missing-mmproj.gguf")
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"]}
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(self.m, model, "p", profile, "hip")

    def test_vision_false_skips_mmproj_check(self):
        model = self._model(mmproj=self.root / "missing-mmproj.gguf")
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"], "vision": False}
        manifest.validate(self.m, model, "p", profile, "hip")  # no raise

    def test_context_below_min_raises_by_default(self):
        model = self._model()
        profile = {"context": 4096, "kv": ["q8_0", "q8_0"]}
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.validate(self.m, model, "p", profile, "hip")
        self.assertIn("128K", str(ctx.exception))

    def test_context_below_min_allowed_with_flag(self):
        model = self._model()
        profile = {"context": 4096, "kv": ["q8_0", "q8_0"]}
        manifest.validate(self.m, model, "p", profile, "hip", allow_low_context=True)

    def test_invalid_kv_type_raises(self):
        model = self._model()
        profile = {"context": 131072, "kv": ["bogus", "q8_0"]}
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(self.m, model, "p", profile, "hip")

    def test_hip_rejects_unsupported_kv_combo(self):
        model = self._model()
        profile = {"context": 131072, "kv": ["q8_0", "q5_1"]}
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(self.m, model, "p", profile, "hip")

    def test_hip_kvmix_accepts_q8_q5_1(self):
        model = self._model()
        profile = {"context": 131072, "kv": ["q8_0", "q5_1"]}
        manifest.validate(self.m, model, "p", profile, "hip-kvmix")  # no raise

    def test_hip_kv_types_still_enforced_under_kvmix(self):
        model = self._model()
        profile = {"context": 131072, "kv": ["q4_0", "q5_1"]}
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(self.m, model, "p", profile, "hip-kvmix")

    def test_vulkan_rejects_mixed_bf16(self):
        model = self._model()
        profile = {"context": 131072, "kv": ["bf16", "q8_0"]}
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(self.m, model, "p", profile, "vulkan")

    def test_vulkan_accepts_matching_bf16(self):
        model = self._model()
        profile = {"context": 131072, "kv": ["bf16", "bf16"]}
        manifest.validate(self.m, model, "p", profile, "vulkan")  # no raise


class TestBuildArgv(unittest.TestCase):
    def _manifest_and_model(self):
        m = manifest.Manifest(
            default_port=8080, default_flags=["-fa", "on"], models_root=pathlib.Path("/root"),
            engines={}, models={}, allow_low_context=False,
        )
        model = manifest.Model(
            alias="m", gguf=pathlib.Path("/root/m.gguf"), backend="hip", mtp=False,
            sampling={"temp": 0.7, "min_p": 0.0}, mmproj=None, profiles={},
        )
        return m, model

    def test_basic_argv_assembly(self):
        m, model = self._manifest_and_model()
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"]}
        argv = manifest.build_argv(m, model, "p", profile, backend="hip")
        self.assertEqual(argv[:6], ["-m", str(model.gguf), "--port", "8080", "-c", "131072"])
        self.assertIn("-ctk", argv)
        self.assertIn("q8_0", argv)
        self.assertIn("--temp", argv)
        self.assertIn("0.7", argv)
        self.assertIn("--min-p", argv)
        self.assertNotIn("--top-p", argv)
        self.assertIn("-fa", argv)

    def test_port_override(self):
        m, model = self._manifest_and_model()
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"]}
        argv = manifest.build_argv(m, model, "p", profile, backend="hip", port=9999)
        self.assertIn("9999", argv)
        self.assertNotIn("8080", argv)

    def test_spec_n_max_adds_mtp_flags(self):
        m, model = self._manifest_and_model()
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"], "spec_n_max": 2}
        argv = manifest.build_argv(m, model, "p", profile, backend="hip")
        self.assertIn("--spec-type", argv)
        self.assertIn("draft-mtp", argv)
        self.assertIn("--spec-draft-n-max", argv)
        self.assertIn("2", argv)

    def test_profile_flags_appended(self):
        m, model = self._manifest_and_model()
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"], "flags": ["--extra", "1"]}
        argv = manifest.build_argv(m, model, "p", profile, backend="hip")
        self.assertEqual(argv[-2:], ["--extra", "1"])

    def test_mmproj_included_when_vision_used(self):
        m, model = self._manifest_and_model()
        model.mmproj = pathlib.Path("/root/mmproj.gguf")
        profile = {"context": 131072, "kv": ["q8_0", "q8_0"]}
        argv = manifest.build_argv(m, model, "p", profile, backend="hip")
        self.assertIn("--mmproj", argv)
        self.assertIn(str(model.mmproj), argv)


class TestServerExecutable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def test_unconfigured_backend_raises(self):
        m = manifest.Manifest(
            default_port=8080, default_flags=[], models_root=self.root,
            engines={}, models={}, allow_low_context=False,
        )
        with self.assertRaises(manifest.ManifestError):
            manifest.server_executable(m, "hip")

    def test_missing_binary_raises(self):
        engine_dir = self.root / "engine"
        engine_dir.mkdir()
        m = manifest.Manifest(
            default_port=8080, default_flags=[], models_root=self.root,
            engines={"hip": engine_dir}, models={}, allow_low_context=False,
        )
        with self.assertRaises(manifest.ManifestError):
            manifest.server_executable(m, "hip")

    def test_existing_binary_returns_path(self):
        engine_dir = self.root / "engine"
        engine_dir.mkdir()
        exe_name = "llama-server.exe" if manifest.IS_WINDOWS else "llama-server"
        (engine_dir / exe_name).write_bytes(b"")
        m = manifest.Manifest(
            default_port=8080, default_flags=[], models_root=self.root,
            engines={"hip": engine_dir}, models={}, allow_low_context=False,
        )
        self.assertEqual(manifest.server_executable(m, "hip"), engine_dir / exe_name)


class TestRealModelsToml(unittest.TestCase):
    """The real models.toml, loaded and schema-validated without touching real GGUF
    files: pathlib.Path.exists is stubbed so this never needs actual weights or a GPU."""

    def test_real_manifest_loads_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            # as_posix(): avoid a Windows backslash being read as a TOML escape sequence.
            root_posix = root.as_posix()
            local_path = _write(
                root / "local.toml",
                f'models_root = "{root_posix}"\n\n'
                "[engines]\n"
                f'vulkan = "{root_posix}/vulkan"\n'
                f'hip = "{root_posix}/hip"\n'
                f'hip-kvmix = "{root_posix}/hip-kvmix"\n',
            )
            with mock.patch.object(pathlib.Path, "exists", return_value=True):
                # Pass the repo's models.toml explicitly: manifest.load() falls back to the
                # MODELS_MANIFEST env var when no path is given, which would make this test
                # depend on whatever the environment happens to have set.
                m = manifest.load(manifest=REPO_ROOT / "models.toml", local=local_path)
                self.assertTrue(m.models, "real models.toml should declare at least one model")
                for alias, model in m.models.items():
                    for profile_name, profile in model.profiles.items():
                        backend = manifest.backend_for(model, profile)
                        manifest.validate(
                            m, model, profile_name, profile, backend,
                            allow_low_context=m.allow_low_context,
                        )


if __name__ == "__main__":
    unittest.main()
