"""Builds one ROCm/HIP gfx1100 llama.cpp engine from an upstream ref plus the versioned patches.

The recipe lives here, not outside the repository: the flags, targets and toolchain documented in
`docs/ENGINES.md` (build recipes) and in `results/20261122-engine-b12633/README.md` are the
CONFIGURE_FLAGS and BUILD_TARGETS below. One command replaces the manual steps:

    python3 scripts/build_engine.py --ref b12633 \\
      --patch engine-patches/tests-kvmix-cases-b12633.patch \\
      --patch engine-patches/pr30792-q5_1-b12633.patch

It clones (or reuses) `<src_root>/llama.cpp-<ref>`, applies the patches in the given order with
`git apply` and no fuzz, configures and builds into `build-rocm10`, copies the build's `bin/` into
its own engine folder, adds the `libamdhip64.so.7` runtime symlink when `[build] hip_runtime_lib`
is set, and checks the result: `llama-server --version`, HIP-only libraries,
`ldd libggml-hip.so`, `test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=q8_0'`
and the SHA256 of the server and the HIP backend. Everything goes into the engine's `BUILD.txt`.

Machine paths come from local.toml (see local.example.toml) `[build]`:
    src_root         git checkouts, one per ref; default: `<engines_root>/src`
    engines_root     built engines; default: the parent folder of `[engines] hip-kvmix`
    hip_runtime_lib  symlinked into the new engine as `libamdhip64.so.7` (docs/sop/install.md
                     "Known errors": the CachyOS ROCm 10.1 runtime)

An existing engine folder is never overwritten (docs/STYLE.md §7: a published build stays), and a
patch that does not apply stops the build with the patch and its files: rebasing it onto a newer
base is a human job. The build uses the ROCm toolchain already on PATH (`hipconfig`, `ROCM_PATH`,
`CMAKE_PREFIX_PATH`), i.e. the `build-env.sh` of docs/ENGINES.md: activate that toolchain first
when it is not the system ROCm install. The toolchain in use is recorded in `BUILD.txt`.

`--dry-run` prints every command and changes nothing.

Exit: 0 = built and every check passed, 1 = build or check failed, 2 = configuration error or
refused (existing engine folder, missing patch, patch does not apply).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from manifest import ManifestError, local_manifest_path, read_toml  # noqa: E402

DEFAULT_REPO = "https://github.com/ggml-org/llama.cpp"
BUILD_DIR = "build-rocm10"
ENGINE_SUFFIX = "linux-rocm-gfx1100-kvmix"
BUILD_JOBS = 14

# The recipe, once. `-DCMAKE_HIP_COMPILER` is composed at build time from `hipconfig -l` of the
# toolchain in use, as the out-of-repo build script did; everything else is fixed.
CONFIGURE_FLAGS = (
    "-DCMAKE_BUILD_TYPE=Release",
    "-DGGML_BACKEND_DL=ON",
    "-DGGML_NATIVE=OFF",
    "-DCMAKE_INSTALL_RPATH=$ORIGIN",
    "-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON",
    "-DGGML_CPU_ALL_VARIANTS=ON",
    "-DGPU_TARGETS=gfx1100",
    "-DGGML_HIP=ON",
    "-DHIP_PLATFORM=amd",
    "-DGGML_CUDA_FA_QUANTS=f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0",
)
BUILD_TARGETS = ("llama-server", "llama-bench", "llama-perplexity", "test-backend-ops")

SERVER = "llama-server"
HIP_LIB = "libggml-hip.so"
HIP_LINK = "libamdhip64.so.7"
# Both backends in one binary route MTP to ROCm0 and silently disable it (llama.cpp #23199).
FORBIDDEN_LIB_PREFIXES = ("libggml-vulkan", "libggml-cuda")
FA_FILTER = "hsk=256.*type_K=q8_0"
FA_PASSED_RE = re.compile(r"(\d+)/(\d+) tests passed")
FA_FAILED_RE = re.compile(r"(\d+) tests failed")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class BuildError(Exception):
    """A step failed or the requested build is not acceptable; `code` is the process exit code."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class BuildConfig:
    """Machine paths from local.toml `[build]`, defaults already applied."""

    src_root: pathlib.Path
    engines_root: pathlib.Path
    hip_runtime_lib: pathlib.Path | None


def load_build_config(local: pathlib.Path | None = None) -> BuildConfig:
    """`[build]` of local.toml; `engines_root` falls back to the parent of `[engines] hip-kvmix`
    and `src_root` to `<engines_root>/src`, the layout the manual builds used."""
    path = local_manifest_path(local)
    loc = read_toml(path, "machine config")
    table = loc.get("build") or {}
    hip_kvmix = (loc.get("engines") or {}).get("hip-kvmix")
    engines_root = table.get("engines_root") or (
        str(pathlib.Path(hip_kvmix).parent) if hip_kvmix else None
    )
    if not engines_root:
        raise ManifestError(
            f"{path} needs a [build] engines_root, or an [engines] hip-kvmix to take its parent "
            "folder from (see local.example.toml)"
        )
    engines_root = pathlib.Path(engines_root).expanduser()
    src_root = pathlib.Path(table.get("src_root") or engines_root / "src").expanduser()
    hip_runtime_lib = table.get("hip_runtime_lib")
    return BuildConfig(
        src_root=src_root,
        engines_root=engines_root,
        hip_runtime_lib=pathlib.Path(hip_runtime_lib).expanduser() if hip_runtime_lib else None,
    )


def patch_files(patch: pathlib.Path) -> list[str]:
    """Paths a git patch changes, read from its own `diff --git a/x b/x` headers."""
    try:
        text = patch.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    files = []
    for line in text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4 and parts[3].startswith("b/"):
                files.append(parts[3][2:])
    return files


def patch_tag(patches: list[pathlib.Path], ref: str) -> str | None:
    """Compact tag of the patches that change more than test cases, for the engine folder name.

    `pr30792-q5_1-b12633.patch` on `b12633` becomes `pr30792q51`; a `-<ref>` suffix drops out. A
    patch that touches only `tests/` changes no kernel, so it adds no tag: the name points at what
    makes this build different."""
    tags = []
    for patch in patches:
        files = patch_files(patch)
        if files and all(name.startswith("tests/") for name in files):
            continue
        stem = patch.stem
        if stem.endswith(f"-{ref}"):
            stem = stem[: -(len(ref) + 1)]
        tag = re.sub(r"[^a-z0-9]+", "", stem.lower())
        if tag:
            tags.append(tag)
    return "-".join(tags) or None


def engine_name(ref: str, patches: list[pathlib.Path], name: str | None = None) -> str:
    """Default: `llama-<ref>[-<patch-tag>]-linux-rocm-gfx1100-kvmix`."""
    if name:
        return name
    tag = patch_tag(patches, ref)
    return f"llama-{ref}" + (f"-{tag}" if tag else "") + f"-{ENGINE_SUFFIX}"


@dataclass
class Build:
    """One requested build, validated: the paths it will touch, nothing executed yet."""

    ref: str
    repo: str
    patches: list[pathlib.Path]
    src_dir: pathlib.Path
    engine_dir: pathlib.Path

    @classmethod
    def from_args(cls, args: argparse.Namespace, cfg: BuildConfig) -> "Build":
        ref = args.ref.strip()
        if not ref:
            raise BuildError(2, "--ref is empty")
        patches = []
        for given in args.patch:
            patch = given.expanduser().resolve()
            if not patch.is_file():
                raise BuildError(
                    2, f"patch not found: {patch} (the versioned ones live in engine-patches/)"
                )
            if not patch_files(patch):
                raise BuildError(2, f"{patch} is not a git patch (no 'diff --git' header)")
            patches.append(patch)
        if args.name and not NAME_RE.match(args.name):
            raise BuildError(2, f"--name {args.name!r} is not a plain folder name")
        if not args.name and not NAME_RE.match(ref):
            raise BuildError(2, f"ref {ref!r} does not fit a folder name: pass --name")
        engine_dir = cfg.engines_root / engine_name(ref, patches, args.name)
        if engine_dir.exists():
            raise BuildError(
                2,
                f"engine folder already exists: {engine_dir} (a build never overwrites an engine: "
                "pass --name, or move the folder and keep it as the rollback)",
            )
        src_dir = cfg.src_root / f"llama.cpp-{ref.replace('/', '-')}"
        return cls(ref=ref, repo=args.repo, patches=patches, src_dir=src_dir, engine_dir=engine_dir)


class Runner:
    """Prints every step of the plan and runs it -- or, in `--dry-run`, prints it and does nothing."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.steps = 0
        # English subprocess output whatever the caller's locale is (docs/STYLE.md §1).
        self.env = {**os.environ, "LC_ALL": "C"}

    @staticmethod
    def cmdline(argv, cwd: pathlib.Path | None = None) -> str:
        line = shlex.join(str(arg) for arg in argv)
        return f"cd {shlex.quote(str(cwd))} && {line}" if cwd is not None else line

    def check(self, description: str) -> None:
        """A step that is not a command: a filesystem check, a hash, a written file."""
        print(f"+ {description}")
        self.steps += 1

    def run(
        self, argv, cwd: pathlib.Path | None = None, check: bool = True, stream: bool = False
    ) -> subprocess.CompletedProcess:
        """Run one command (`stream`: its output goes straight out, for the long configure and
        build steps; otherwise it is captured for the checks that parse it)."""
        line = self.cmdline(argv, cwd)
        print(f"+ {line}")
        self.steps += 1
        if self.dry_run:
            return subprocess.CompletedProcess([str(arg) for arg in argv], 0, "", "")
        try:
            result = subprocess.run(
                [str(arg) for arg in argv], cwd=cwd, env=self.env, text=True, errors="replace",
                **(dict() if stream else dict(capture_output=True)),
            )
        except OSError as e:
            raise BuildError(1, f"could not run {line}: {e}") from e
        if check and result.returncode != 0:
            detail = ((result.stderr or "") + (result.stdout or "")).strip()
            raise BuildError(
                1,
                f"{line} failed with exit code {result.returncode}"
                + (f":\n{detail}" if detail else ""),
            )
        return result

    def capture(self, argv, cwd: pathlib.Path | None = None, check: bool = True) -> str | None:
        """Stripped stdout of one command; None in `--dry-run`, where nothing runs."""
        result = self.run(argv, cwd=cwd, check=check)
        return None if self.dry_run else result.stdout.strip()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class Facts:
    """What `BUILD.txt` records; filled in as the build runs."""

    started: datetime.datetime
    commit: str | None = None
    toolchain: list[str] = field(default_factory=list)
    configure: str = ""
    build_cmd: str = ""
    build_seconds: float | None = None
    patch_hashes: list[tuple[pathlib.Path, str]] = field(default_factory=list)
    version: str | None = None
    forbidden: list[str] = field(default_factory=list)
    amdhip: str | None = None
    fa: str | None = None
    hashes: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def render_build_txt(build: Build, cfg: BuildConfig, facts: Facts) -> str:
    """`BUILD.txt` for the new engine: ref, commit, patches, flags, toolchain, test counts."""
    lines = [
        f"engine: {build.engine_dir.name}",
        f"folder: {build.engine_dir}",
        f"built: {facts.started.strftime('%Y-%m-%d %H:%M:%S')}",
        "recipe: scripts/build_engine.py (docs/sop/update-engine.md, docs/ENGINES.md)",
        f"repo: {build.repo}",
        f"ref: {build.ref}",
        f"commit: {facts.commit or 'unknown'}",
        "",
        "patches:",
    ]
    if facts.patch_hashes:
        lines += [f"  {path.name} sha256={digest}" for path, digest in facts.patch_hashes]
    else:
        lines.append("  none")
    lines += ["", f"configure: {facts.configure}", f"build: {facts.build_cmd}"]
    if facts.build_seconds is not None:
        lines.append(f"build time: {facts.build_seconds / 60:.1f} min (configure + build)")
    if facts.toolchain:
        lines += ["toolchain:", *[f"  {item}" for item in facts.toolchain]]
    else:
        lines.append("toolchain: not recorded")
    lines += [
        "",
        f"{SERVER} --version: {facts.version or 'unknown'}",
        "backends: "
        + (
            "HIP only (no libggml-vulkan/libggml-cuda)"
            if not facts.forbidden
            else "PROBLEM, both backends present: " + ", ".join(facts.forbidden)
        ),
        f"hip_runtime_lib: {cfg.hip_runtime_lib or 'not set'}",
        f"ldd {HIP_LIB} libamdhip64: {facts.amdhip or 'unknown'}",
        f"sha256 {SERVER}: {facts.hashes.get(SERVER, 'unknown')}",
        f"sha256 {HIP_LIB}: {facts.hashes.get(HIP_LIB, 'unknown')}",
        f"FLASH_ATTN_EXT -p '{FA_FILTER}': {facts.fa or 'not run'}",
    ]
    if facts.problems:
        lines += ["", "problems:"] + [f"  {problem}" for problem in facts.problems]
    return "\n".join(lines) + "\n"


def prepare_source(build: Build, runner: Runner) -> None:
    """Clone the source checkout, or reuse one that sits at exactly `--ref` with no local changes."""
    if not build.src_dir.exists():
        runner.run(["git", "clone", "--filter=blob:none", build.repo, str(build.src_dir)])
        runner.run(["git", "-C", str(build.src_dir), "checkout", build.ref])
        return
    head = runner.capture(["git", "-C", str(build.src_dir), "rev-parse", "HEAD"], check=False)
    want = runner.capture(
        ["git", "-C", str(build.src_dir), "rev-parse", f"{build.ref}^{{commit}}"], check=False
    )
    changes = runner.capture(
        ["git", "-C", str(build.src_dir), "status", "--porcelain"], check=False
    )
    if runner.dry_run:
        return
    if not want:
        raise BuildError(
            2,
            f"{build.src_dir} exists but is not a git checkout of {build.ref}: move it away, or "
            "pass the ref it really holds",
        )
    if head != want:
        raise BuildError(
            2,
            f"{build.src_dir} is at {head}, not at {build.ref} ({want}): pass another --ref, or "
            "move the folder",
        )
    if changes:
        raise BuildError(
            2,
            f"{build.src_dir} has local changes (patches from an earlier build?): clean it in a "
            "scratch copy, or build another --ref",
        )


def apply_patch(build: Build, patch: pathlib.Path, runner: Runner) -> None:
    """`git apply` one patch in the source checkout; a failure is a full stop, never a fuzz."""
    result = runner.run(["git", "-C", str(build.src_dir), "apply", str(patch)], check=False)
    if runner.dry_run or result.returncode == 0:
        return
    files = ", ".join(patch_files(patch)) or "unknown files"
    detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
    raise BuildError(
        2,
        "\n".join(
            [
                f"patch {patch} does not apply to {build.ref} (files it changes: {files})",
                f"git apply said: {detail}",
                "patches here apply exactly, never with fuzz: rebase this one on the new base in "
                "a scratch worktree and add the result to engine-patches/ "
                "(docs/sop/update-engine.md)",
            ]
        ),
    )


def toolchain_info(runner: Runner, hipconfig_dir: str | None) -> list[str]:
    """The toolchain in use, so a build can be traced back to it."""
    version = runner.capture(["hipconfig", "--version"], check=False)
    info = [
        f"hipconfig {version or 'unknown'} (-l {hipconfig_dir or '?'}, "
        f"HIP_PATH {os.environ.get('HIP_PATH', 'unset')})"
    ]
    if hipconfig_dir:
        clang = runner.capture([f"{hipconfig_dir}/clang", "--version"], check=False)
        info.append(f"{hipconfig_dir}/clang: {clang.splitlines()[0] if clang else 'unknown'}")
    cmake = runner.capture(["cmake", "--version"], check=False)
    if cmake:
        info.append(f"cmake: {cmake.splitlines()[0]}")
    return info


def install(build: Build, cfg: BuildConfig, runner: Runner) -> None:
    """Copy the build output into its own engine folder and add the runtime symlink."""
    if build.engine_dir.exists():
        raise BuildError(
            2, f"engine folder appeared while building: {build.engine_dir} (nothing overwritten)"
        )
    bin_dir = build.src_dir / BUILD_DIR / "bin"
    runner.run(["cp", "-a", f"{bin_dir}/.", str(build.engine_dir)])
    if cfg.hip_runtime_lib:
        runner.run(["ln", "-sfn", str(cfg.hip_runtime_lib), str(build.engine_dir / HIP_LINK)])


def check_engine(build: Build, cfg: BuildConfig, runner: Runner, facts: Facts) -> None:
    """Post-build checks: version, HIP only, runtime resolution, FA op tests, SHA256."""
    engine = build.engine_dir
    version = runner.run([str(engine / SERVER), "--version"], check=False)
    if not runner.dry_run:
        # llama-server prints the version on stderr.
        lines = [line.strip() for line in (version.stdout + version.stderr).splitlines() if line.strip()]
        facts.version = lines[0] if lines else None
        if version.returncode != 0:
            facts.problems.append(f"{SERVER} --version exited {version.returncode}")

    runner.check(f"check backends in {engine}: no libggml-vulkan/libggml-cuda")
    if not runner.dry_run:
        facts.forbidden = sorted(
            path.name for path in engine.iterdir() if path.name.startswith(FORBIDDEN_LIB_PREFIXES)
        )
        if facts.forbidden:
            facts.problems.append(
                "both backends in one folder, MTP would route to ROCm silently (llama.cpp "
                "#23199): " + ", ".join(facts.forbidden)
            )

    ldd = runner.run(["ldd", str(engine / HIP_LIB)], check=False)
    if not runner.dry_run:
        line = next((l for l in ldd.stdout.splitlines() if "libamdhip64" in l), None)
        if line is None:
            facts.problems.append(f"ldd {HIP_LIB} does not report libamdhip64")
        else:
            resolved = (
                line.split("=>", 1)[1].split(" (", 1)[0].strip() if "=>" in line else line.strip()
            )
            facts.amdhip = resolved
            if cfg.hip_runtime_lib and not resolved.startswith(str(engine)):
                facts.problems.append(
                    f"libamdhip64 resolves outside the engine folder ({resolved}): check the "
                    f"{HIP_LINK} symlink to {cfg.hip_runtime_lib}"
                )

    fa = runner.run(
        [str(engine / "test-backend-ops"), "test", "-b", "ROCm0", "-o", "FLASH_ATTN_EXT",
         "-p", FA_FILTER],
        cwd=engine,
        check=False,
    )
    if not runner.dry_run:
        output = fa.stdout + fa.stderr
        passed = FA_PASSED_RE.search(output)
        failed = FA_FAILED_RE.search(output)
        if failed:
            facts.fa = f"{failed.group(1)} failed (exit {fa.returncode})"
            facts.problems.append(f"FLASH_ATTN_EXT op tests: {facts.fa}")
        elif not passed:
            tail = [line for line in output.strip().splitlines() if line.strip()]
            facts.fa = f"no result, exit {fa.returncode}"
            facts.problems.append(
                "FLASH_ATTN_EXT op tests printed no summary (exit "
                f"{fa.returncode}{', last output: ' + tail[-1] if tail else ''})"
            )
        else:
            ok, total = int(passed.group(1)), int(passed.group(2))
            facts.fa = f"{ok}/{total} tests passed"
            if fa.returncode != 0 or ok != total:
                facts.problems.append(f"FLASH_ATTN_EXT op tests: {facts.fa} (exit {fa.returncode})")

    for name in (SERVER, HIP_LIB):
        runner.check(f"sha256 {engine / name}")
        if not runner.dry_run:
            path = engine / name
            if path.exists():
                facts.hashes[name] = sha256_file(path)
            else:
                facts.problems.append(f"{name} is missing from {engine}")


def execute(build: Build, cfg: BuildConfig, runner: Runner) -> int:
    facts = Facts(started=datetime.datetime.now())
    print(f"engine: {build.engine_dir}")
    print(f"source: {build.src_dir}")

    prepare_source(build, runner)
    facts.commit = runner.capture(["git", "-C", str(build.src_dir), "rev-parse", "HEAD"], check=False)
    for patch in build.patches:
        apply_patch(build, patch, runner)
        runner.check(f"sha256 {patch}")
        if not runner.dry_run:
            facts.patch_hashes.append((patch, sha256_file(patch)))

    hipconfig_dir = runner.capture(["hipconfig", "-l"])
    compiler = (
        f"-DCMAKE_HIP_COMPILER={hipconfig_dir}/clang"
        if hipconfig_dir
        else "-DCMAKE_HIP_COMPILER=$(hipconfig -l)/clang"
    )
    facts.toolchain = toolchain_info(runner, hipconfig_dir)
    configure = ["cmake", "-B", BUILD_DIR, "-S", ".", compiler, *CONFIGURE_FLAGS]
    build_cmd = [
        "cmake", "--build", BUILD_DIR, "-j", str(BUILD_JOBS), "--target", *BUILD_TARGETS
    ]
    facts.configure = Runner.cmdline(configure)
    facts.build_cmd = Runner.cmdline(build_cmd)
    started = time.monotonic()
    runner.run(configure, cwd=build.src_dir, stream=True)
    runner.run(build_cmd, cwd=build.src_dir, stream=True)
    facts.build_seconds = None if runner.dry_run else time.monotonic() - started

    install(build, cfg, runner)
    check_engine(build, cfg, runner, facts)

    build_txt = build.engine_dir / "BUILD.txt"
    runner.check(f"write {build_txt}")
    if runner.dry_run:
        print(f"dry run: {runner.steps} steps, nothing executed")
        return 0
    build_txt.write_text(render_build_txt(build, cfg, facts))

    print(f"{SERVER}: {facts.version or 'version unknown'}")
    print(f"HIP backend: {facts.hashes.get(HIP_LIB, 'unknown')}")
    print(f"FLASH_ATTN_EXT: {facts.fa or 'not run'}")
    print(f"BUILD.txt: {build_txt}")
    for problem in facts.problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if facts.problems else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ref", required=True, help="tag, branch or commit to build (e.g. b12633)")
    parser.add_argument(
        "--repo", default=DEFAULT_REPO, help=f"git URL to clone when the checkout is missing "
        f"(default: {DEFAULT_REPO})"
    )
    parser.add_argument(
        "--patch", action="append", default=[], type=pathlib.Path, metavar="FILE",
        help="versioned patch applied to the checkout, in the order given (repeatable)",
    )
    parser.add_argument(
        "--name", help=f"engine folder name (default: llama-<ref>[-<patch-tag>]-{ENGINE_SUFFIX})"
    )
    parser.add_argument("--dry-run", action="store_true", help="print every command, run nothing")
    parser.add_argument("--local", type=pathlib.Path, help="alternate path to local.toml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # A build runs for minutes: stream every step to the terminal or the nohup log.
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)
    runner = Runner(dry_run=args.dry_run)
    try:
        cfg = load_build_config(args.local)
        build = Build.from_args(args, cfg)
    except ManifestError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except BuildError as e:
        print(f"error: {e.message}", file=sys.stderr)
        return e.code
    try:
        return execute(build, cfg, runner)
    except BuildError as e:
        print(f"error: {e.message}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
