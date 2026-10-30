"""Keeps a Strata install (docs/sop/strata.md) on the settings tracked in models.toml across Strata updates.

Strata is not llama-server: it has its own clone, setup and run config (`<strata_dir>/strata-<model>.json`).
`models.toml` holds this repo's settings for each installed Strata model in a `[strata.<model>]` table;
`local.toml` holds `strata_dir`. Each key of the table except `config` replaces the same key of the run config,
except `env`, which is merged (setup writes its own env keys). `user_args` is Strata's own list of hand-set
engine options, re-applied by every setup run and start on top of the generated `args`.

  python3 scripts/strata.py status            # local vs. upstream version, settings drift
  python3 scripts/strata.py apply [--dry-run] # write the tracked settings into the run configs
  python3 scripts/strata.py update [-- ARGS]  # back up configs, ./update.sh ARGS, apply, show what changed

Exit: 0 = OK (status: no drift), 1 = drift or failure, 2 = configuration error or Strata running.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from manifest import ManifestError, local_manifest_path, models_manifest_path, read_toml  # noqa: E402


def overlay(cfg: dict, tracked: dict) -> dict:
    """The run config with the tracked settings applied: keys replaced, `env` merged."""
    new = dict(cfg)
    for key, value in tracked.items():
        if key == "config":
            continue
        if key == "env":
            new["env"] = {**(cfg.get("env") or {}), **{k: str(v) for k, v in value.items()}}
        else:
            new[key] = value
    return new


def changes(old: dict, new: dict) -> list[str]:
    """One line per top-level key that differs, `env` per variable."""
    out = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a == b:
            continue
        if key == "env" and isinstance(a, dict) and isinstance(b, dict):
            out += [f"env.{k}: {a.get(k)!r} -> {b.get(k)!r}" for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
        else:
            out.append(f"{key}: {a!r} -> {b!r}")
    return out


def load_settings(models: pathlib.Path | None = None, local: pathlib.Path | None = None) -> tuple[pathlib.Path, dict]:
    """(strata_dir, {model: tracked table}) from local.toml and models.toml."""
    local_path = local_manifest_path(local)
    tables = read_toml(models_manifest_path(models), "models manifest").get("strata", {})
    loc = read_toml(local_path, "machine config")
    if not loc.get("strata_dir"):
        raise ManifestError(f"{local_path} has no strata_dir (see local.example.toml)")
    for name, t in tables.items():
        if not isinstance(t.get("config"), str):
            raise ManifestError(f"[strata.{name}] needs config = \"strata-<model>.json\"")
    return pathlib.Path(loc["strata_dir"]).expanduser().resolve(), tables


def git(strata: pathlib.Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(strata), *args], capture_output=True, text=True).stdout.strip()


def running(strata: pathlib.Path) -> bool:
    # setup writes the resolved clone path into its launcher; pgrep -f takes a regex
    return subprocess.run(["pgrep", "-f", re.escape(str(strata / "serve" / "server.py"))],
                          capture_output=True).returncode == 0


def apply_all(strata: pathlib.Path, tables: dict, dry_run: bool) -> tuple[int, int]:
    """Applies every table; returns (configs that differed, configs missing). A missing config is not created."""
    differed = missing = 0
    for name, tracked in tables.items():
        path = strata / tracked["config"]
        if not path.is_file():
            print(f"[strata.{name}] {path} does not exist: install the model with setup first (docs/sop/strata.md)")
            missing += 1
            continue
        cfg = json.loads(path.read_text())
        new = overlay(cfg, tracked)
        diff = changes(cfg, new)
        print(f"[strata.{name}] {path.name}: " + ("matches models.toml" if not diff else f"{len(diff)} change(s)"))
        for line in diff:
            print("  " + line)
        if diff:
            differed += 1
            if not dry_run:
                tmp = path.with_name(path.name + ".tmp")
                tmp.write_text(json.dumps(new, indent=1) + "\n")
                tmp.replace(path)
    return differed, missing


def cmd_status(strata: pathlib.Path, tables: dict) -> int:
    subprocess.run(["git", "-C", str(strata), "fetch", "-q", "--tags", "origin"], check=False)
    print(f"local:    {git(strata, 'describe', '--tags')}")
    print(f"upstream: {git(strata, 'describe', '--tags', 'origin/main')}"
          f" ({git(strata, 'rev-list', '--count', 'HEAD..origin/main')} commits ahead of local)")
    print("server:   " + ("running" if running(strata) else "stopped"))
    return 1 if any(apply_all(strata, tables, dry_run=True)) else 0


def cmd_update(strata: pathlib.Path, tables: dict, extra: list[str]) -> int:
    if running(strata):
        print("Strata is running: stop it first (qwen-flash stop).")
        return 2
    before, before_rev = git(strata, "describe", "--tags"), git(strata, "rev-parse", "HEAD")
    backup = strata.parent / "strata-backups" / f"{before}-{time.strftime('%Y%m%d-%H%M%S')}"
    backup.mkdir(parents=True)
    configs = sorted(strata.glob("strata-*.json")) + sorted(strata.glob("run-*.sh"))
    for f in configs:
        shutil.copy2(f, backup / f.name)
    print(f"backed up {len(configs)} file(s) to {backup}")
    if subprocess.run(["./update.sh", *extra], cwd=strata).returncode != 0:
        print(f"./update.sh failed; configs are unchanged or restorable from {backup}")
        return 1
    print(f"\n{before} -> {git(strata, 'describe', '--tags')}")
    notes = git(strata, "diff", "--name-only", before_rev, "HEAD", "--", "docs/release-notes-*.md")
    print("release notes to read:" + ("".join(f"\n  {strata / n}" for n in notes.splitlines()) or " none"))
    for f in sorted(backup.glob("strata-*.json")):
        now = strata / f.name
        if now.is_file():
            diff = changes(json.loads(f.read_text()), json.loads(now.read_text()))
            print(f"{f.name} changed by the update: " + ("nothing" if not diff else ""))
            for line in diff:
                print("  " + line)
    if apply_all(strata, tables, dry_run=False)[1]:
        print("Updated, but a tracked run config is missing (see above): install that model before starting it.")
        return 1
    print("Next: start it (qwen-flash) and run the update checks in docs/sop/strata.md.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="versions, server state, settings drift")
    p = sub.add_parser("apply", help="write the models.toml [strata.*] settings into the run configs")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("update", help="back up, ./update.sh, apply; arguments after -- go to update.sh")
    p.add_argument("extra", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    try:
        strata, tables = load_settings()
    except ManifestError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not (strata / "update.sh").is_file():
        print(f"error: {strata} is not a Strata clone", file=sys.stderr)
        return 2
    if a.cmd == "status":
        return cmd_status(strata, tables)
    if a.cmd == "apply":
        differed, missing = apply_all(strata, tables, a.dry_run)
        return 1 if missing or (a.dry_run and differed) else 0
    return cmd_update(strata, tables, [x for x in a.extra if x != "--"])


if __name__ == "__main__":
    sys.exit(main())
