"""Loads models.toml + local.toml and builds the llama-server argv.

Uses a single TOML manifest (models.toml) plus a per-machine local.toml
(git-ignored) for machine-specific paths. `launch.py`, `check-sync.py` and
`smoke.py` import from here instead of duplicating the parsing.

Use as a library:
    from manifest import load, resolve, build_argv, harness_entry
    m = load()
    model, profile_name, profile = resolve(m, "qwen38-iq3s-mtp", "262k-q8q51-mtp")
    argv = build_argv(m, model, profile)

Environment variables:
    MODELS_MANIFEST  alternate path to models.toml
    LOCAL_MANIFEST   alternate path to local.toml
"""
from __future__ import annotations

import json
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
# "hip-inkling" engine: the GodGMN/llama.cpp `inkling-rdna3` fork (Inkling-2-Mini only), built with the
# same GGML_CUDA_FA_QUANTS list as hip-kvmix (results/20261122-inkling-rdna3-fork/BUILD.md).
_HIP_KV_BY_BACKEND = {"hip": _HIP_KV_VALID, "hip-kvmix": _HIP_KVMIX_VALID, "hip-inkling": _HIP_KVMIX_VALID}
# "maya" engine: a checkout of GodGMN/maya-inkling-mini `hip-port` (Inkling-2-Mini only, not llama.cpp; see
# docs/ENGINES.md). Its server reads a JSON run config built from the port's gfx1100 preset plus the profile;
# a profile's kv pair maps to IK2_KV (one cache type for K and V).
MAYA_PRESET = pathlib.Path("docs/inkling2-mini/ik2-mini-gfx1100.json")
_MAYA_KV = {("fp8", "fp8"): "fp8", ("f16", "f16"): "f16"}


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


def models_manifest_path(override: pathlib.Path | None = None) -> pathlib.Path:
    if override:
        return override
    env = os.environ.get("MODELS_MANIFEST")
    return pathlib.Path(env) if env else REPO / "models.toml"


def read_toml(path: pathlib.Path, what: str) -> dict:
    """Parses one TOML file; any read or parse failure becomes a ManifestError naming `what`."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ManifestError(f"failed to read {what} {path}: {e}") from e


def local_manifest_path(override: pathlib.Path | None) -> pathlib.Path:
    if override:
        return override
    env = os.environ.get("LOCAL_MANIFEST")
    if env:
        return pathlib.Path(env)
    default = REPO / "local.toml"
    if default.exists():
        return default
    candidates = sorted(p for p in REPO.glob("local.*.toml") if p.name != "local.example.toml")
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        preferred = REPO / ("local.windows.toml" if IS_WINDOWS else "local.linux.toml")
        if preferred in candidates:
            return preferred
        raise ManifestError(
            "multiple machine configs found; set LOCAL_MANIFEST or choose one of: "
            + ", ".join(str(p) for p in candidates)
        )
    return default


def load(manifest: pathlib.Path | None = None, local: pathlib.Path | None = None) -> Manifest:
    models_path = models_manifest_path(manifest)
    local_path = local_manifest_path(local)

    data = read_toml(models_path, "models manifest")
    if not local_path.exists():
        raise ManifestError(
            f"{local_path} does not exist. Copy local.example.toml to local.toml and adjust the paths."
        )
    loc = read_toml(local_path, "machine config")
    try:
        root = pathlib.Path(loc["models_root"])
        engines = {k: pathlib.Path(v) for k, v in loc["engines"].items() if v}

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
    except ManifestError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise ManifestError(f"invalid manifest configuration ({local_path} or {models_path}): {e}") from e


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
    if backend == "maya":
        if (k_type, v_type) not in _MAYA_KV:
            raise ManifestError(f"{model.alias}/{profile_name}: the maya engine takes kv = "
                                f"[\"fp8\", \"fp8\"] or [\"f16\", \"f16\"], not {k_type}/{v_type}")
        if uses_vision(model, profile):
            raise ManifestError(f"{model.alias}/{profile_name}: the maya backend is wired without vision; "
                                "set vision = false")
        return
    valid_types = {"f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"}
    if k_type not in valid_types or v_type not in valid_types:
        raise ManifestError(f"{model.alias}/{profile_name}: invalid K/V type ({k_type}/{v_type})")

    if backend in _HIP_KV_BY_BACKEND:
        valid = _HIP_KV_BY_BACKEND[backend]
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


def build_argv(m: Manifest, model: Model, profile: dict) -> list[str]:
    k_type, v_type = profile["kv"]
    argv = [
        "-m", str(model.gguf),
        "--port", str(m.default_port),
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
        argv += ["--spec-type", profile.get("spec_type", "draft-mtp"),
                 "--spec-draft-n-max", str(profile["spec_n_max"])]
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


def server_command(m: Manifest, model: Model, profile: dict, backend: str,
                   config_dir: pathlib.Path) -> tuple[list[str], pathlib.Path]:
    """(command, cwd) that serves `model`/`profile` on [defaults].port. llama.cpp backends: the binary plus
    build_argv. maya: writes <config_dir>/<alias>.maya.json and runs the port's OpenAI server on it."""
    if backend != "maya":
        exe = server_executable(m, backend)
        return [str(exe)] + build_argv(m, model, profile), exe.parent
    engine = m.engines.get("maya")
    if not engine:
        raise ManifestError("no 'maya' engine configured in local.toml (engines.maya)")
    python = engine / ".venv" / "bin" / "python"
    if not python.exists():
        raise ManifestError(f"{python} does not exist: create the port's venv (docs/ENGINES.md)")
    preset = json.loads(_read_text(engine / MAYA_PRESET))
    sampling = {name: model.sampling[key] for key, name in
                (("temp", "temperature"), ("top_p", "top_p"), ("top_k", "top_k"), ("min_p", "min_p"))
                if key in model.sampling}
    config = {
        "backend": preset["backend"], "exe": preset["exe"],
        "args": ["--model", str(model.gguf), "--max-context", str(profile["context"]),
                 "--chunk", str(profile.get("chunk", 1024))],
        "env": {**preset["env"], "IK2_KV": _MAYA_KV[tuple(profile["kv"])], **profile.get("env", {})},
        "tokenizer": preset["tokenizer"], "model_name": preset["model_name"],
        "sampling": sampling, "cwd": str(engine),
    }  # the preset's reasoning_effort is dropped: requests get the vendor default, as on llama-server
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / f"{model.alias}.maya.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    return [str(python), "serve/server.py", "--engine", "maya", "--config", str(path),
            "--port", str(m.default_port), "--tokenizer", config["tokenizer"]], engine


def _read_text(path: pathlib.Path) -> str:
    """Text of an engine-side file; a read failure becomes a ManifestError."""
    try:
        return path.read_text()
    except OSError as e:
        raise ManifestError(f"failed to read {path}: {e}") from e


def gpu_device(drm: pathlib.Path = pathlib.Path("/sys/class/drm")) -> pathlib.Path | None:
    """The amdgpu sysfs device dir (`<drm>/cardN/device`) with the most VRAM, or None (also off Linux).

    The single selection rule for every script: an iGPU or a second card never wins over the
    discrete card, whatever its `cardN` index."""
    best = None
    for dev in sorted(drm.glob("card*/device")):
        try:
            total = int((dev / "mem_info_vram_total").read_text())
        except (OSError, ValueError):
            continue
        if best is None or total > best[0]:
            best = (total, dev)
    return best[1] if best else None


def free_vram_gib() -> float | None:
    """Free VRAM in GiB on the `gpu_device()` card, or None when unknown."""
    dev = gpu_device()
    if dev is None:
        return None
    try:
        return (int((dev / "mem_info_vram_total").read_text())
                - int((dev / "mem_info_vram_used").read_text())) / 2**30
    except (OSError, ValueError):
        return None


def running_servers() -> list[int] | None:
    """PIDs of running llama-server or maya-ik2 processes; None means process detection failed."""
    try:
        if IS_WINDOWS:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, errors="replace", timeout=20,
            )
            if out.returncode != 0:
                return None
            pids = []
            saw_no_match = False
            for line in out.stdout.splitlines():
                if line.startswith("INFO: No tasks are running"):
                    saw_no_match = True
                    continue
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) > 1 and parts[1].isdigit():
                    pids.append(int(parts[1]))
                elif line.strip():
                    return None
            return pids if pids or saw_no_match else None
        out = subprocess.run(["pgrep", "-x", "llama-server|maya-ik2"],
                             capture_output=True, text=True,
                             errors="replace", timeout=20)
        if out.returncode == 1:
            return []
        if out.returncode != 0:
            return None
        return [int(p) for p in out.stdout.split()]
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
