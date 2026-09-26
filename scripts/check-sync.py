"""Validates the manifest and, optionally, a coding-agent harness wiring.

Two independent checks:
  1. Every model/profile in models.toml validates without launching anything
     (GGUF exists, context >= 128K, K/V combination allowed by the backend).
     A backend with no engine in local.toml is only a WARNING (not installed
     yet) -- it does not fail the check.
  2. If local.toml has a `[harness]` table with `targets`, each target's
     config file is checked for EXACTLY the 2 local providers (local-128k,
     local-262k) with the right port and contextWindow, and no other
     provider pointing at 127.0.0.1 (an orphan from an earlier setup).
     This check is off by default -- see local.example.toml.

Usage: python scripts/check-sync.py
Exit: 0 = all OK (pending-engine warnings don't count) - 1 = problems found.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tomllib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from manifest import LOCAL_262K_CONTEXT, MIN_CONTEXT, ManifestError, backend_for, load, validate  # noqa: E402

EXPECTED_ENTRIES = {
    "local-128k": MIN_CONTEXT,
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
    base_url = base_url or ""
    return "127.0.0.1" in base_url or "localhost" in base_url


def validate_harness(name: str, entries) -> list[str]:
    problems = []
    local = [e for e in entries if _is_local(e[3])]
    seen = {e[1] for e in local}

    for expected_id, expected_ctx in EXPECTED_ENTRIES.items():
        matches = [e for e in local if e[1] == expected_id]
        if not matches:
            problems.append(f"{name}: missing local provider '{expected_id}'.")
            continue
        for pid, mid, ctx, base in matches:
            port_suffix = f":{EXPECTED_PORT}"
            if not ((base or "").endswith(port_suffix) or f"{port_suffix}/" in (base or "")):
                problems.append(
                    f"{name}: '{mid}' (provider {pid}) points at {base}, "
                    f"expected port :{EXPECTED_PORT}."
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
    """Reads local.toml directly (not through manifest.load) so a missing local.toml doesn't
    also break the manifest check above."""
    local_path = pathlib.Path(
        os.environ.get("LOCAL_MANIFEST") or (pathlib.Path(__file__).resolve().parent.parent / "local.toml")
    )
    if not local_path.exists():
        return None
    with open(local_path, "rb") as f:
        data = tomllib.load(f)
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
    targets = _harness_targets()
    if targets is None:
        print("  disabled (set harness.enabled = true and harness.targets in local.toml to check).")
    elif not targets:
        print("  harness.enabled = true but harness.targets is empty: nothing to check.")
    else:
        for target in targets:
            entries, error = _harness_entries(target)
            if error:
                print(f"  WARNING: {error} (skipped)")
                continue
            probs = validate_harness(target["name"], entries)
            if probs:
                harness_problems.extend(probs)
                for p in probs:
                    print(f"  PROBLEM: {p}")
            else:
                print(f"  OK: {target['name']} has exactly local-128k and local-262k on :{EXPECTED_PORT}.")

    if manifest_problems or harness_problems:
        return 1
    print("\nOK: manifest (and harness, if enabled) are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
