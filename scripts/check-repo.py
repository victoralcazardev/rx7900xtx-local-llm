"""Checks every tracked file before pushing this public repo: broken relative Markdown links,
oversized files, personal absolute paths, secret-looking strings and Spanish-language leftovers.

Runs over `git ls-files` (only tracked files -- nothing git-ignored is scanned). Stdlib only,
no dependencies.

Usage: python3 scripts/check-repo.py
Exit: 0 = no problems, 1 = problems found. See AGENTS.md: "run before every push".
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
MAX_FILE_BYTES = 1_048_576  # 1 MiB

# Extensions (and extension-less dotfiles/LICENSE) scanned for content problems. Anything else
# tracked (there is none today -- no GGUF, no images) only gets the size check.
TEXT_EXTENSIONS = {".md", ".py", ".json", ".jsonl", ".toml", ".sh", ".service", ".timer", ""}

# (?<!\w) keeps a URL path segment from matching: right before the leading "/" there must not
# be a word character, as in "https://host.example/media/x" (a letter precedes "/media") or
# "host.example:8080/srv/x" (a digit precedes "/srv"). Any other character is accepted -- start
# of string, whitespace, a quote, a bracket, another "/", or a colon -- so a real path straight
# after a colon (e.g. "server:/mnt/hdd/x", "PATH=/usr:/mnt/models") is still flagged.
PERSONAL_PATH_RE = re.compile(
    r"(?<!\w)/(?:home|mnt|media|srv)/[^/\s'\"]+|[A-Za-z]:[\\/]Users[\\/][^\\/\s'\"]+"
)
# Absolute-path-looking strings that are deliberately generic (not a personal machine path) --
# e.g. an illustrative mount point in a docs page. One entry today: `/mnt/models`, the example
# fstab mount point in docs/hardware/gpu-7900xtx.md §4. Add another exact string only when a doc
# genuinely needs one under a prefix the check above flags.
PERSONAL_PATH_ALLOWLIST: set[str] = {"/mnt/models"}

SECRET_PATTERNS = [
    (re.compile(r"api_key\s*=", re.I), "api_key = ..."),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-... token"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_... GitHub token"),
    (re.compile(r"hf_[A-Za-z0-9]{20,}"), "hf_... Hugging Face token"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), "private key block"),
]
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Addresses that are deliberately public in this repo (e.g. a maintainer contact address).
# Empty by default: nothing has earned a place here yet.
EMAIL_ALLOWLIST: set[str] = set()

# Common Spanish words this project's own writing tends to leak (see docs/STYLE.md §1/§4).
SPANISH_WORDS = (
    "según", "también", "está", "medición", "caché", "perfil", "prueba",
    "conclusión", "traspaso", "modelo", "modelos", "motor", "motores",
)
SPANISH_WORD_RE = re.compile(r"\b(" + "|".join(SPANISH_WORDS) + r")\b", re.I)
SPANISH_ACCENTS_RE = re.compile(r"[áéíóúñ¿¡]", re.I)

# Allowlist for deliberate Spanish content (docs/STYLE.md §1). Two mechanisms:
#  - a marker comment already used throughout the codebase: any file containing it is skipped
#    entirely (it documents its own exception right next to the Spanish content).
#  - a path allowlist for content that can't easily carry that marker: the STYLE.md glossary
#    table (the left column lists the Spanish source terms on purpose) and results/ (immutable
#    evidence, STYLE.md §7 -- it reproduces raw request/response content verbatim, including
#    Spanish prompts and outputs from the deliberately-Spanish bench scripts).
SPANISH_ALLOW_MARKER = "Deliberately Spanish (STYLE.md exception)"
SPANISH_ALLOW_PATHS = {"docs/STYLE.md"}
SPANISH_ALLOW_PATH_PREFIXES = ("results/",)

# Inline code spans and fenced code blocks in Markdown prose usually cite a literal filename,
# path or command (some of them, like a private-project script name, unavoidably Spanish) --
# not prose the language rule is meant to catch.
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
FENCE_RE = re.compile(r"^\s*```")

MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")

# This script's own source necessarily contains the literal patterns/labels these checks look
# for (the personal-path regex spells out "/home/", the secret label spells out "api_key = ...",
# the Spanish word list and accent regex spell out Spanish words) -- exclude it from all three
# content checks so it doesn't flag itself. Its unit tests need the same personal-path and
# Spanish sample strings as fixtures, but no secret-pattern fixtures, so that file stays out of
# SELF_SECRET_PATHS and keeps getting scanned for secrets. Both are still fully covered by the
# size and link checks below.
SELF_PATHS = {"scripts/check-repo.py", "tests/test_check_repo.py"}
SELF_SECRET_PATHS = {"scripts/check-repo.py"}


def tracked_files() -> list[pathlib.Path]:
    # -z: NUL-separated, unquoted paths -- plain `git ls-files` C-quotes any path with
    # non-ASCII or special characters (core.quotePath=true by default), and that quoted form
    # never exists on disk, so it would silently be skipped as a "staged deletion" below.
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [REPO / p for p in out.stdout.split("\0") if p]


def strip_markdown_code(text: str) -> str:
    kept = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            kept.append("")  # keep line numbers aligned with the original text
            continue
        kept.append("" if in_fence else CODE_SPAN_RE.sub("", line))
    return "\n".join(kept)


def slugify(heading: str) -> str:
    """Best-effort GitHub-style heading slug: strip code-span backticks, lowercase, drop
    punctuation, each whitespace char (not each run) becomes its own hyphen -- GitHub's real
    slugger doesn't collapse runs, so "A / B" (a removed "/" leaves two spaces) slugs to
    "a--b", not "a-b"."""
    heading = re.sub(r"`([^`]*)`", r"\1", heading)
    heading = heading.strip().lower()
    heading = re.sub(r"[^\w\s-]", "", heading)
    heading = re.sub(r"\s", "-", heading)
    return heading


_slug_cache: dict[pathlib.Path, set[str]] = {}


def heading_slugs(path: pathlib.Path) -> set[str]:
    if path in _slug_cache:
        return _slug_cache[path]
    slugs: list[str] = []
    if path.exists() and path.suffix == ".md":
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = HEADING_RE.match(line)
            if m:
                slugs.append(slugify(m.group(2)))
    seen: dict[str, int] = {}
    out: set[str] = set()
    for s in slugs:
        n = seen.get(s, 0)
        out.add(s if n == 0 else f"{s}-{n}")
        seen[s] = n + 1
    _slug_cache[path] = out
    return out


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def check_size(path: pathlib.Path, rel: str, problems: dict[str, list[str]]) -> None:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        problems.setdefault(rel, []).append(f"file is {size:,} bytes (> {MAX_FILE_BYTES:,} = 1 MiB)")


def check_personal_paths(rel: str, text: str, problems: dict[str, list[str]]) -> None:
    for m in PERSONAL_PATH_RE.finditer(text):
        if m.group(0) in PERSONAL_PATH_ALLOWLIST:
            continue
        problems.setdefault(rel, []).append(f"line {line_of(text, m.start())}: personal path {m.group(0)!r}")


def check_secrets(rel: str, text: str, problems: dict[str, list[str]]) -> None:
    for pattern, label in SECRET_PATTERNS:
        for m in pattern.finditer(text):
            problems.setdefault(rel, []).append(f"line {line_of(text, m.start())}: looks like a {label}")
    for m in EMAIL_RE.finditer(text):
        addr = m.group(0)
        if addr in EMAIL_ALLOWLIST:
            continue
        problems.setdefault(rel, []).append(f"line {line_of(text, m.start())}: email address {addr!r}")


def check_filename_spanish(rel: str, problems: dict[str, list[str]]) -> None:
    """File/dir naming is English-only (docs/STYLE.md §5), with no immutable-evidence exception
    -- unlike file content, a path is never raw measurement data."""
    hits = {m.group(0) for m in SPANISH_WORD_RE.finditer(rel)}
    hits |= set(SPANISH_ACCENTS_RE.findall(rel))
    if hits:
        problems.setdefault(rel, []).append(
            f"file/dir name has a Spanish leftover ({', '.join(sorted(hits))})"
        )


def check_spanish(rel: str, path: pathlib.Path, text: str, problems: dict[str, list[str]]) -> None:
    if rel in SPANISH_ALLOW_PATHS or rel.startswith(SPANISH_ALLOW_PATH_PREFIXES):
        return
    if SPANISH_ALLOW_MARKER in text:
        return
    scan_text = strip_markdown_code(text) if path.suffix == ".md" else text
    for lineno, line in enumerate(scan_text.splitlines(), start=1):
        hits = {m.group(0) for m in SPANISH_WORD_RE.finditer(line)}
        hits |= set(SPANISH_ACCENTS_RE.findall(line))
        if hits:
            snippet = line.strip()[:100]
            problems.setdefault(rel, []).append(
                f"line {lineno}: Spanish leftover ({', '.join(sorted(hits))}): {snippet}"
            )


def check_links(path: pathlib.Path, rel: str, text: str, problems: dict[str, list[str]]) -> None:
    if path.suffix != ".md":
        return
    for m in MD_LINK_RE.finditer(text):
        target = m.group(2).strip()
        lineno = line_of(text, m.start())
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if target.startswith("#"):
            anchor = target[1:]
            if anchor and anchor not in heading_slugs(path):
                problems.setdefault(rel, []).append(f"line {lineno}: anchor {target!r} not found in this file")
            continue
        file_part, _, anchor = target.partition("#")
        target_path = (path.parent / file_part).resolve()
        if not target_path.exists():
            problems.setdefault(rel, []).append(f"line {lineno}: broken link -> {target}")
            continue
        if anchor and target_path.suffix == ".md" and anchor not in heading_slugs(target_path):
            problems.setdefault(rel, []).append(
                f"line {lineno}: anchor #{anchor} not found in {file_part}"
            )


def main() -> int:
    problems: dict[str, list[str]] = {}
    missing: list[str] = []
    for path in tracked_files():
        # rel uses as_posix() -- the allowlists above (SELF_PATHS, SPANISH_ALLOW_PATHS,
        # SPANISH_ALLOW_PATH_PREFIXES, "results/") are forward-slash literals, and this repo
        # supports Windows (see manifest.IS_WINDOWS), where relative_to() yields backslashes.
        rel = path.relative_to(REPO).as_posix()
        if not path.exists():  # staged deletion, nothing to check
            missing.append(rel)
            continue
        check_size(path, rel, problems)
        check_filename_spanish(rel, problems)
        if path.suffix not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            problems.setdefault(rel, []).append(f"could not read as UTF-8 text: {e}")
            continue
        if rel not in SELF_PATHS:
            check_personal_paths(rel, text, problems)
            check_spanish(rel, path, text, problems)
        if rel not in SELF_SECRET_PATHS:
            check_secrets(rel, text, problems)
        check_links(path, rel, text, problems)

    if missing:
        print(f"note: {len(missing)} tracked path(s) not found on disk (staged deletion?): "
              f"{', '.join(sorted(missing))}")

    if not problems:
        print("OK: no problems found.")
        return 0

    for rel in sorted(problems):
        print(f"{rel}:")
        for p in problems[rel]:
            print(f"  {p}")
    total = sum(len(v) for v in problems.values())
    print(f"\n{total} problem(s) in {len(problems)} file(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
