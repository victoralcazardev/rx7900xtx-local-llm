"""Validates the manifest and, optionally, a coding-agent harness wiring.

Two independent checks:
  1. Every model/profile in models.toml validates without launching anything
     (GGUF exists, context >= 128K, K/V combination allowed by the backend).
     A backend with no engine in your local machine config (local.toml) is
     only a WARNING (not installed yet) -- it does not fail the check.
  2. If your local machine config has a `[harness]` table with `targets`, each
     config file is checked for EXACTLY the local provider (local-262k) with
     the right port and contextWindow, and no other provider pointing at
     127.0.0.1 (an orphan from an earlier setup). This check is off by
     default -- see local.example.toml.

Usage: python3 scripts/check-sync.py
Exit: 0 = all OK (pending-engine warnings don't count) - 1 = problems found.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tomllib
from urllib.parse import urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from manifest import LOCAL_262K_CONTEXT, ManifestError, backend_for, load, local_manifest_path, validate  # noqa: E402

EXPECTED_ENTRIES = {
    "local-262k": LOCAL_262K_CONTEXT,
}
EXPECTED_PORT = 8080


def validate_manifest() -> tuple[list[str], list[str]]:
    """(problems, warnings)."""
    problems: list[str] = []
    warnings: list[str] = []
    try:
        m = load()
    except ManifestError as e:
        return [str(e)], []
    except Exception as e:
        return [f"models.toml/local.toml failed to load: {type(e).__name__}: {e}"], []

    try:
        backends_used = {backend_for(mod, profile) for mod in m.models.values()
                          for profile in mod.profiles.values()}
        for backend in sorted(backends_used):
            if backend not in m.engines:
                warnings.append(f"backend '{backend}' has no engine in local.toml (not installed yet).")

        # GGUF/mmproj existence is checked once per profile inside validate() below (it already
        # covers every model, since every model must have at least one profile) -- checking it
        # again here at the model level would report the same missing file once per model plus
        # once per profile.
        for alias, model in m.models.items():
            for profile_name, profile in model.profiles.items():
                try:
                    validate(m, model, profile_name, profile, backend_for(model, profile),
                             allow_low_context=m.allow_low_context)
                except ManifestError as e:
                    problems.append(str(e))
                except Exception as e:
                    problems.append(f"{alias}/{profile_name}: {type(e).__name__}: {e}")
    except Exception as e:
        problems.append(f"models.toml: {type(e).__name__}: {e}")
    return problems, warnings


def _load_config(path: pathlib.Path, fmt: str):
    text = path.read_text(encoding="utf-8")
    if fmt == "json":
        return json.loads(text)
    # PyYAML is only needed for non-json harness targets, which are off by default: import it
    # lazily so a machine without it can still run the core manifest check.
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError("PyYAML is required for non-json harness targets (pip install pyyaml)") from e
    return yaml.safe_load(text)


def _harness_entries(target: dict):
    """[(provider_id, model_id, contextWindow, baseUrl)] for one harness target, or (None, error)."""
    path = pathlib.Path(target["path"]).expanduser()
    name = target["name"]
    if not path.exists():
        return None, f"{name}: {path} does not exist"
    try:
        data = _load_config(path, target.get("format", "json")) or {}
    except Exception as e:
        return None, f"{name}: failed to load {path}: {type(e).__name__}: {e}"
    for key in target.get("root", []):
        data = (data.get(key) or {})
    base_url_key = target.get("base_url_key", "baseUrl")
    out = []
    for pid, prov in (data.get("providers") or {}).items():
        for mdl in prov.get("models", []):
            out.append((pid, mdl["id"], mdl.get("contextWindow"), prov.get(base_url_key, "")))
    return out, None


def _is_local(base_url: str) -> bool:
    try:
        return urlsplit(base_url or "").hostname in {"localhost", "127.0.0.1"}
    except ValueError:
        return False


def validate_harness(name: str, entries, expected_port: int = EXPECTED_PORT) -> list[str]:
    problems = []
    local = [e for e in entries if _is_local(e[3])]
    seen = {e[1] for e in local}

    for expected_id, expected_ctx in EXPECTED_ENTRIES.items():
        matches = [e for e in local if e[1] == expected_id]
        if not matches:
            problems.append(f"{name}: missing local provider '{expected_id}'.")
            continue
        if len(matches) > 1:
            problems.append(f"{name}: expected exactly one '{expected_id}' entry, found {len(matches)}.")
        for pid, mid, ctx, base in matches:
            try:
                actual_port = urlsplit(base or "").port
            except ValueError:
                actual_port = None
            if actual_port != expected_port:
                problems.append(
                    f"{name}: '{mid}' (provider {pid}) points at {base}, "
                    f"expected port :{expected_port}."
                )
            if ctx != expected_ctx:
                problems.append(
                    f"{name}: '{mid}' contextWindow={ctx}, expected {expected_ctx} "
                    "-> 400 exceed_context if it doesn't match -c."
                )

    orphans = seen - set(EXPECTED_ENTRIES)
    for o in orphans:
        problems.append(
            f"{name}: orphaned local provider '{o}' is still wired up "
            "-> connection refused when selected. Remove it."
        )
    return problems


def _harness_targets() -> list[dict] | None:
    """Reads the machine-local config with the same resolution as manifest.load
    (LOCAL_MANIFEST, then local.toml, then an auto-discovered local.*.toml)
    instead of manifest.load itself, so a missing config doesn't also break the
    manifest check above. Ambiguous resolution raises ManifestError, which
    main() reports as a problem."""
    local_path = local_manifest_path(None)
    if not local_path.exists():
        return None
    try:
        with open(local_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ManifestError(f"failed to read harness config {local_path}: {e}") from e
    harness = data.get("harness") or {}
    if not harness.get("enabled"):
        return None
    return harness.get("targets", [])




def main() -> int:
    manifest_problems, warnings = validate_manifest()
    print("== manifest (models.toml) ==")
    for w in warnings:
        print(f"  WARNING: {w}")
    if manifest_problems:
        for p in manifest_problems:
            print(f"  PROBLEM: {p}")
    else:
        print("  OK: every model/profile validates.")

    harness_problems: list[str] = []
    print("\n== harness ==")
    try:
        targets = _harness_targets()
    except ManifestError as e:
        targets = None
        harness_problems.append(str(e))
        print(f"  PROBLEM: {e}")
    try:
        port = load().default_port
    except ManifestError:
        port = EXPECTED_PORT
    if targets is None and not harness_problems:
        print("  disabled (set harness.enabled = true and harness.targets in your local config to check).")
    elif targets == []:
        print("  harness.enabled = true but harness.targets is empty: nothing to check.")
    elif targets:
        for target in targets:
            entries, error = _harness_entries(target)
            if error:
                print(f"  WARNING: {error} (skipped)")
                continue
            probs = validate_harness(target["name"], entries, expected_port=port)
            if probs:
                harness_problems.extend(probs)
                for p in probs:
                    print(f"  PROBLEM: {p}")
            else:
                print(f"  OK: {target['name']} has exactly local-262k on :{port}.")

    if manifest_problems or harness_problems:
        return 1
    print("\nOK: manifest (and harness, if enabled) are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
