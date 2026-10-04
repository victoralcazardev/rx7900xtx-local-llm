"""Launches a model from the manifest with llama-server.

Usage:
    python3 scripts/launch.py [alias] [--profile P] [--backend vulkan|hip|cuda]
                               [--dry-run] [--background] [--manifest path.toml]

Without an alias, models.toml's [defaults] default_alias/default_profile is used (the
current best configuration -- see docs/STATUS.md). Without --profile, if the model has
only one profile that one is used; with several, they are listed and the script exits
with code 2. --backend overrides the one declared in models.toml (useful for pipeline
tests, e.g. --backend cuda).

Every launch writes the server log to _tmp/logs/<alias>-<profile>-<timestamp>.log and, on
Linux, a GPU thermal/VRAM CSV next to it (<log>.gpu.csv, scripts/gpu_watch.py).
Foreground (the default) also echoes it to the console, Ctrl+C to stop;
--background detaches the server and only writes the file.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import shutil
import subprocess
import shlex
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from manifest import (  # noqa: E402
    IS_WINDOWS, REPO, ManifestError, backend_for, build_argv, load,
    harness_entry, resolve, running_servers, server_executable, validate, free_vram_gib,
)

VRAM_MARGIN_GIB = 0.5  # over the profile's measured `vram_gib` (peak with a full context)


def _without_suspend(cmd: list[str]) -> list[str]:
    """Blocks suspend while the server runs: suspending with VRAM full has been observed to
    hang the machine on resume. Linux + systemd; no sudo needed."""
    if IS_WINDOWS or not shutil.which("systemd-inhibit"):
        return cmd
    return ["systemd-inhibit", "--what=sleep:idle", "--who=llama-server",
            "--why=Model loaded on the GPU: suspending may hang the machine",
            "--mode=block"] + cmd


def _start_gpu_watch(server_pid: int, log_path: pathlib.Path, port: int) -> None:
    """Passive sensor logger (read-only) that stops when the server process exits."""
    if IS_WINDOWS:
        return
    out = open(log_path.with_name(log_path.name + ".gpu.csv"), "w")
    subprocess.Popen([sys.executable, str(pathlib.Path(__file__).with_name("gpu_watch.py")),
                      "--pid", str(server_pid), "--port", str(port)],
                     stdout=out, stdin=subprocess.DEVNULL, start_new_session=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("alias", nargs="?",
                    help="model alias from models.toml; omit to use [defaults] default_alias")
    p.add_argument("--profile")
    p.add_argument("--backend", help="override the backend declared in the manifest")
    p.add_argument("--dry-run", action="store_true", help="only print the command")
    p.add_argument("--background", action="store_true", help="launch in the background with a log")
    p.add_argument("--manifest", type=pathlib.Path, help="alternate path to models.toml")
    args = p.parse_args()

    try:
        m = load(manifest=args.manifest)
        model, profile_name, profile = resolve(m, args.alias, args.profile)
    except ManifestError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if args.alias is None:
        print(f"no alias given, using default: {model.alias} / {profile_name}")

    backend = backend_for(model, profile, args.backend)

    try:
        validate(m, model, profile_name, profile, backend,
                 allow_low_context=m.allow_low_context)
    except ManifestError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    argv = build_argv(m, model, profile_name, profile, backend, port=m.default_port)
    entry = harness_entry(profile["context"]) or (
        "none (no harness entry wired for this context; only local-262k/262144 is wired)"
    )
    print(f"backend: {backend}")
    print("command:", shlex.join(["llama-server"] + argv))
    print(f"Harness provider: {entry}")

    needed = profile.get("vram_gib")
    free = free_vram_gib()
    if needed and free is not None:
        print(f"VRAM: {free:.1f} GiB free, this profile reaches {needed} GiB with a full context")
        if free < needed + VRAM_MARGIN_GIB:
            print(f"WARNING: less than {VRAM_MARGIN_GIB} GiB of margin. Close whatever else is "
                  "using the GPU (browser, games) or pick a smaller profile: with VRAM full the "
                  "server can crash mid-response.", file=sys.stderr)

    if args.dry_run:
        return 0

    try:
        exe = server_executable(m, backend)
    except ManifestError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    alive = running_servers()
    if alive is None:
        print("ERROR: could not detect running llama-server processes; aborting preflight.",
              file=sys.stderr)
        return 1
    if alive:
        print(f"ERROR: llama-server is already running (PID {alive}). Stop it first.",
              file=sys.stderr)
        return 1

    logs = REPO / "_tmp" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs / f"{model.alias}-{profile_name}-{stamp}.log"
    cmd = _without_suspend([str(exe)] + argv)

    if args.background:
        with open(log_path, "w") as log:
            proc = subprocess.Popen(cmd, cwd=str(exe.parent), stdout=log, stderr=log)
        _start_gpu_watch(proc.pid, log_path, m.default_port)
        print(f"launched in background, log: {log_path}")
        return 0

    print(f"log: {log_path}")
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(cmd, cwd=str(exe.parent),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        _start_gpu_watch(proc.pid, log_path, m.default_port)
        _tee(proc.stdout, sys.stdout.buffer, log)
        return proc.wait()


def _tee(src, *sinks) -> None:
    """Copy src to every sink until EOF. Ctrl+C also reaches the server (same process
    group), so keep copying its shutdown output instead of dying mid-stream."""
    while True:
        try:
            chunk = src.read1(65536)
        except KeyboardInterrupt:
            continue
        if not chunk:
            return
        for sink in sinks:
            sink.write(chunk)
            sink.flush()


if __name__ == "__main__":
    sys.exit(main())
