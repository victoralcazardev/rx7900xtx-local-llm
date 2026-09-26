"""Loads models.toml + local.toml and builds the llama-server argv.

Uses a single TOML manifest (models.toml) plus a per-machine local.toml
(git-ignored) for machine-specific paths. `launch.py`, `check-sync.py` and
`smoke.py` import from here instead of duplicating the parsing.

Use as a library:
    from manifest import load, resolve, build_argv, harness_entry
    m = load()
    model, profile_name, profile = resolve(m, "qwen38-iq3s-mtp", "262k-q8q51-mtp")
    argv = build_argv(m, model, profile_name, profile, backend="vulkan")

Environment variables:
    MODELS_MANIFEST  alternate path to models.toml
    LOCAL_MANIFEST   alternate path to local.toml
"""
from __future__ import annotations

import os
import pathlib
import platform
import subprocess
import tomllib
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parent.parent
IS_WINDOWS = platform.system() == "Windows"

MIN_CONTEXT = 131072  # 128K: below this it isn't worth it for this batch (see AGENTS.md)
LOCAL_262K_CONTEXT = 262144  # single source of truth for the local-262k harness provider's
                              # contextWindow; scripts/check-sync.py imports this too

# HIP/ROCm: only these K/V combinations have a FlashAttention kernel compiled into the
# prebuilt binary (GGML_CUDA_FA_QUANTS in llama.cpp's CMakeLists.txt; see docs/measurements/).
_HIP_KV_VALID = {("q4_0", "q4_0"), ("q8_0", "q8_0"), ("f16", "f16"), ("bf16", "bf16")}
# "hip-kvmix" engine: a build compiled with -DGGML_CUDA_FA_QUANTS that adds K q8_0 + V q5_1/q4_1.
_HIP_KVMIX_VALID = _HIP_KV_VALID | {("q8_0", "q5_1"), ("q8_0", "q4_1")}


class ManifestError(Exception):
    """Manifest or requested-profile validation error."""


@dataclass
class Model:
    alias: str
    gguf: pathlib.Path
    backend: str
    mtp: bool
    sampling: dict
    mmproj: pathlib.Path | None
    profiles: dict[str, dict]


@dataclass
class Manifest:
    default_port: int
    default_flags: list[str]
    models_root: pathlib.Path
    engines: dict[str, pathlib.Path]
    models: dict[str, Model]
    # Only for TEST manifests: allows profiles below MIN_CONTEXT to exercise the
    # pipeline on hardware that doesn't reach 128K.
    allow_low_context: bool = False
    # What `launch.py` loads when called with no alias (models.toml [defaults]); either both
    # set or both None.
    default_alias: str | None = None
    default_profile: str | None = None


def _manifest_path(env_name: str, default: pathlib.Path, override: pathlib.Path | None) -> pathlib.Path:
    if override:
        return override
    env = os.environ.get(env_name)
    return pathlib.Path(env) if env else default


def load(manifest: pathlib.Path | None = None, local: pathlib.Path | None = None) -> Manifest:
    models_path = _manifest_path("MODELS_MANIFEST", REPO / "models.toml", manifest)
    local_path = _manifest_path("LOCAL_MANIFEST", REPO / "local.toml", local)

    with open(models_path, "rb") as f:
        data = tomllib.load(f)
    if not local_path.exists():
        raise ManifestError(
            f"{local_path} does not exist. Copy local.example.toml to local.toml and adjust the paths."
        )
    with open(local_path, "rb") as f:
        loc = tomllib.load(f)

    root = pathlib.Path(loc["models_root"])
    engines = {k: pathlib.Path(v) for k, v in loc.get("engines", {}).items() if v}

    defaults = data.get("defaults", {})
    models = {}
    for alias, m in data.get("models", {}).items():
        profiles = m.get("profiles", {})
        if not profiles:
            raise ManifestError(f"{alias}: has no profile in models.toml")
        models[alias] = Model(
            alias=alias,
            gguf=root / m["gguf"],
            backend=m["backend"],
            mtp=bool(m.get("mtp", False)),
            sampling=m.get("sampling", {}),
            mmproj=(root / m["mmproj"]) if m.get("mmproj") else None,
            profiles=profiles,
        )

    manifest = Manifest(
        default_port=defaults.get("port", 8080),
        default_flags=list(defaults.get("flags", [])),
        models_root=root,
        engines=engines,
        models=models,
        allow_low_context=bool(data.get("allow_low_context", False)),
        default_alias=defaults.get("default_alias"),
        default_profile=defaults.get("default_profile"),
    )
    if manifest.default_alias or manifest.default_profile:
        if not manifest.default_alias or not manifest.default_profile:
            raise ManifestError(
                "[defaults] must set both default_alias and default_profile, or neither"
            )
        resolve(manifest, manifest.default_alias, manifest.default_profile)
    return manifest


def resolve(m: Manifest, alias: str | None, profile: str | None) -> tuple[Model, str, dict]:
    """Returns (model, profile_name, profile) or raises ManifestError. alias=None uses the
    manifest's `[defaults] default_alias` (see `launch.py`), and if profile is also None,
    `default_profile` too; raises if the manifest declares neither default."""
    if alias is None:
        if not m.default_alias or not m.default_profile:
            raise ManifestError(
                "no alias given and models.toml has no [defaults] default_alias/default_profile"
            )
        alias = m.default_alias
        if profile is None:
            profile = m.default_profile
    if alias not in m.models:
        available = ", ".join(sorted(m.models))
        raise ManifestError(f"unknown model '{alias}'. Available: {available}")
    model = m.models[alias]
    names = list(model.profiles)
    if profile is None:
        if len(names) != 1:
            raise ManifestError(
                f"'{alias}' has {len(names)} profiles, pick one with --profile: "
                + ", ".join(names)
            )
        profile = names[0]
    if profile not in model.profiles:
        raise ManifestError(
            f"'{alias}' has no profile '{profile}'. Available: " + ", ".join(names)
        )
    return model, profile, model.profiles[profile]


def harness_entry(context: int) -> str | None:
    """Name of the fixed local provider entry for the given profile's context, or None if no
    harness entry is wired for it (see AGENTS.md: only the 262K default is wired)."""
    if context >= LOCAL_262K_CONTEXT:
        return "local-262k"
    return None


def backend_for(model: Model, profile: dict, override: str | None = None) -> str:
    """Effective backend: --backend > profile's `backend` > model's `backend`."""
    return override or profile.get("backend") or model.backend


def uses_vision(model: Model, profile: dict) -> bool:
    """A profile can turn off the mmproj with `vision = false` (e.g. long context + MTP)."""
    return bool(model.mmproj) and profile.get("vision", True)


def validate(m: Manifest, model: Model, profile_name: str, profile: dict, backend: str,
             allow_low_context: bool = False) -> None:
    if not model.gguf.exists():
        raise ManifestError(f"GGUF does not exist: {model.gguf}")
    if uses_vision(model, profile) and not model.mmproj.exists():
        raise ManifestError(f"mmproj does not exist: {model.mmproj}")

    context = profile["context"]
    if not allow_low_context and context < MIN_CONTEXT:
        raise ManifestError(
            f"{model.alias}/{profile_name}: context {context} < {MIN_CONTEXT} (128K). "
            "This batch is long-context only; for a pipeline test set allow_low_context=true "
            "in a test manifest."
        )

    k_type, v_type = profile["kv"]
    valid_types = {"f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"}
    if k_type not in valid_types or v_type not in valid_types:
        raise ManifestError(f"{model.alias}/{profile_name}: invalid K/V type ({k_type}/{v_type})")

    if backend in ("hip", "hip-kvmix"):
        valid = _HIP_KVMIX_VALID if backend == "hip-kvmix" else _HIP_KV_VALID
        if (k_type, v_type) not in valid:
            raise ManifestError(
                f"{model.alias}/{profile_name}: K/V combination {k_type}/{v_type} has no "
                f"FlashAttention kernel compiled into the '{backend}' engine (the prebuilt HIP "
                "binary only ships q4_0-q4_0, q8_0-q8_0, f16-f16, bf16-bf16 -- see "
                "docs/measurements/engines.md). For K q8_0 + V q5_1/q4_1 use backend = "
                '"hip-kvmix".'
            )
    elif backend == "vulkan":
        if "bf16" in (k_type, v_type) and k_type != v_type:
            raise ManifestError(
                f"{model.alias}/{profile_name}: Vulkan doesn't allow mixing bf16 with another "
                "type in K/V (see docs/measurements/engines.md)."
            )


def build_argv(m: Manifest, model: Model, profile_name: str, profile: dict,
                backend: str, port: int | None = None) -> list[str]:
    k_type, v_type = profile["kv"]
    argv = [
        "-m", str(model.gguf),
        "--port", str(port or m.default_port),
        "-c", str(profile["context"]),
        "-ctk", k_type,
        "-ctv", v_type,
    ]
    if uses_vision(model, profile):
        argv += ["--mmproj", str(model.mmproj)]
    for key, flag in (("temp", "--temp"), ("top_p", "--top-p"),
                       ("top_k", "--top-k"), ("min_p", "--min-p")):
        if key in model.sampling:
            argv += [flag, str(model.sampling[key])]
    argv += list(m.default_flags)
    if "spec_n_max" in profile:
        argv += ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(profile["spec_n_max"])]
    argv += list(profile.get("flags", []))
    return argv


def server_executable(m: Manifest, backend: str) -> pathlib.Path:
    engine = m.engines.get(backend)
    if not engine:
        raise ManifestError(
            f"no '{backend}' engine configured in local.toml (engines.{backend})"
        )
    exe = engine / ("llama-server.exe" if IS_WINDOWS else "llama-server")
    if not exe.exists():
        raise ManifestError(f"binary does not exist: {exe}")
    return exe


def free_vram_gib() -> float | None:
    """Free VRAM in GiB on the amdgpu device with the most VRAM (sysfs, Linux only), or None."""
    if IS_WINDOWS:
        return None
    best = None
    for dev in pathlib.Path("/sys/class/drm").glob("card*/device"):
        try:
            total = int((dev / "mem_info_vram_total").read_text())
            used = int((dev / "mem_info_vram_used").read_text())
        except (OSError, ValueError):
            continue
        if best is None or total > best[0]:
            best = (total, used)
    return (best[0] - best[1]) / 2**30 if best else None


def running_servers() -> list[int]:
    """PIDs of running llama-server processes (there can only be ONE, and for measuring: none)."""
    pids = []
    try:
        if IS_WINDOWS:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, errors="replace", timeout=20,
            )
            for line in out.stdout.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) > 1 and parts[1].isdigit():
                    pids.append(int(parts[1]))
        else:
            out = subprocess.run(["pgrep", "-x", "llama-server"],
                                 capture_output=True, text=True,
                                 errors="replace", timeout=20)
            pids = [int(p) for p in out.stdout.split()]
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return pids
