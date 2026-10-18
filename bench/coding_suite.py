#!/usr/bin/env python3
"""Fixed six-task coding suite: an agent loop over /v1/chat/completions with streaming tool calls.

Design and gate policy: docs/ENGINES-EXPERIMENTS.md#coding-suite-design-b1a-2026-10-18.
Tasks, pinned repos, patches and hidden tests: bench/coding_suite_tasks/. Standard library only.

Attaches to the engine already serving the URL (llama-server via scripts/launch.py, or Strata);
it never starts an engine. Each (task, seed) runs in a fresh `git worktree` of a cached clone.

  python3 bench/coding_suite.py --verify-fixtures        # no server: bug fails, reference passes
  python3 bench/coding_suite.py --smoke                  # no server: built-in fake model, full loop
  systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \\
      python3 bench/coding_suite.py --freeze-pack        # once, against the 27B: CS4 file lists
  systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 BENCH_EXPECT_POWER_CAP_W=272 \\
      python3 bench/coding_suite.py --run --label 27b    # 6 tasks x seeds 1,2,3
  python3 bench/coding_suite.py --rescore <run dir>      # re-score saved diffs; must match
  python3 bench/coding_suite.py --compare <base run> <candidate run>
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.client
import http.server
import json
import os
import pathlib
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
TASKS_DIR = HERE / "coding_suite_tasks"
CACHE = ROOT / "_tmp" / "coding-suite" / "repos"
OUTPUT = HERE / "res" / "coding_suite"

MAX_TURNS = 40
MAX_TOKENS = 32768
TEST_TIMEOUT_S = 300
READ_MAX_LINES = 2000
READ_MAX_BYTES = 64 * 1024
TESTS_TAIL_CHARS = 4000
BAD_TOOL_CALL_LIMIT = 3
SEEDS = (1, 2, 3)
EXCLUDES = "__pycache__/\n*.pyc\n.suite/\n"
GIT_ID = ["-c", "user.name=coding-suite", "-c", "user.email=coding-suite@localhost"]
PACK_PREAMBLE = "Read these files from the repository first; the task follows after them."

TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a text file (or list a directory) in the repository. Returns at most "
                       f"{READ_MAX_LINES} lines per call; use offset (1-based line) to continue.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path relative to the repository root"},
            "offset": {"type": "integer", "description": "First line to return, 1-based"},
            "limit": {"type": "integer", "description": "Maximum number of lines"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write the complete content of a file in the repository, replacing it.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path relative to the repository root"},
            "content": {"type": "string", "description": "The whole new file content"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_tests",
        "description": "Run the repository's test suite and return the exit code and the end of the output.",
        "parameters": {"type": "object", "properties": {}}}},
]


class ToolError(Exception):
    pass


# --- suite data -----------------------------------------------------------------------------

def load_suite() -> dict:
    return json.loads((TASKS_DIR / "tasks.json").read_text())


def select_tasks(suite: dict, ids: str | None) -> list[dict]:
    tasks = suite["tasks"]
    if not ids:
        return tasks
    wanted = [i.strip().upper() for i in ids.split(",") if i.strip()]
    known = {t["id"] for t in tasks}
    bad = [i for i in wanted if i not in known]
    if bad:
        raise SystemExit(f"unknown task id(s): {', '.join(bad)} (known: {', '.join(sorted(known))})")
    return [t for t in tasks if t["id"] in wanted]


def load_sampling(alias: str | None, override: str | None) -> tuple[str | None, dict]:
    """Request sampling keys: --sampling replaces the alias table entirely (engines not in models.toml)."""
    if override is not None:
        out = {}
        for item in filter(None, (s.strip() for s in override.split(","))):
            key, _, raw = item.partition("=")
            if not raw:
                raise SystemExit(f"--sampling expects key=value pairs, got {item!r}")
            out[key.strip()] = float(raw) if "." in raw else int(raw)
        return None, {("temperature" if k == "temp" else k): v for k, v in out.items()}
    manifest = tomllib.loads((ROOT / "models.toml").read_text())
    alias = alias or manifest["defaults"]["default_alias"]
    if alias not in manifest.get("models", {}):
        raise SystemExit(f"alias {alias!r} is not in models.toml; use --sampling for other engines")
    table = manifest["models"][alias].get("sampling", {})
    return alias, {("temperature" if k == "temp" else k): v for k, v in table.items()}


# --- git ------------------------------------------------------------------------------------

def git(cwd, *args, check=True, input_text=None) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, input=input_text)
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {p.stderr.strip()}")
    return p.stdout


def ensure_repo(name: str, spec: dict, cache: pathlib.Path = CACHE) -> pathlib.Path:
    path = cache / name
    if not (path / ".git").exists():
        cache.mkdir(parents=True, exist_ok=True)
        git(cache, "clone", "-q", "--no-checkout", spec["url"], name)
    if subprocess.run(["git", "cat-file", "-e", spec["commit"] + "^{commit}"], cwd=path,
                      capture_output=True).returncode:
        git(path, "fetch", "-q", "origin", spec["commit"])
    exclude = path / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    if EXCLUDES not in (exclude.read_text() if exclude.exists() else ""):
        with exclude.open("a") as f:
            f.write("\n" + EXCLUDES)
    return path


def setup_worktree(repo: pathlib.Path, commit: str, task: dict, dest: pathlib.Path) -> None:
    """Pinned commit + the task's bug patch, committed, so `git diff HEAD` is the model's work."""
    git(repo, "worktree", "add", "-q", "--detach", str(dest), commit)
    try:
        if git(dest, "rev-parse", "HEAD").strip() != commit:
            raise RuntimeError(f"worktree {dest} is not at {commit}")
        if task.get("bug_patch"):
            git(dest, "apply", str(TASKS_DIR / task["bug_patch"]))
        git(dest, *GIT_ID, "commit", "-q", "--allow-empty", "-am", f"coding-suite setup {task['id']}")
    except BaseException:
        remove_worktree(repo, dest)
        raise


def remove_worktree(repo: pathlib.Path, dest: pathlib.Path) -> None:
    git(repo, "worktree", "remove", "--force", str(dest), check=False)
    shutil.rmtree(dest, ignore_errors=True)
    git(repo, "worktree", "prune", check=False)


def apply_reference(dest: pathlib.Path, task: dict) -> None:
    if task.get("fix_patch"):
        git(dest, "apply", str(TASKS_DIR / task["fix_patch"]))
    else:
        git(dest, "apply", "-R", str(TASKS_DIR / task["bug_patch"]))


def model_diff(dest: pathlib.Path) -> str:
    git(dest, "add", "-A")
    return git(dest, "diff", "--cached", "--binary", "HEAD")


# --- commands and tools ---------------------------------------------------------------------

def run_cmd(cmd: str, cwd: pathlib.Path, hidden_dir: pathlib.Path | None, timeout=TEST_TIMEOUT_S):
    """Run in its own process group, so a timeout kills every descendant, not only bash."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = cmd.replace("{hidden_dir}", str(hidden_dir or "")).replace("{worktree}", str(cwd.resolve()))
    p = subprocess.Popen(["bash", "-c", cmd], cwd=cwd, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
    try:
        out, _ = p.communicate(timeout=max(1, timeout))
        return p.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        return 124, out + f"\n[timed out after {timeout:.0f} s]"


def resolve_in(root: pathlib.Path, rel: str) -> pathlib.Path:
    if not isinstance(rel, str) or not rel:
        raise ToolError("path must be a non-empty string")
    root = root.resolve()
    path = (root / rel).resolve()
    if path != root and root not in path.parents:
        raise ToolError(f"path {rel!r} is outside the repository")
    if ".git" in path.relative_to(root).parts:
        raise ToolError("the .git directory is not accessible")
    return path


class Tools:
    """The fixed tool set. Every error result starts with "error: "."""

    def __init__(self, worktree: pathlib.Path, task: dict, hidden_dir: pathlib.Path | None):
        self.root, self.task, self.hidden_dir = worktree, task, hidden_dir
        self.calls: dict[str, int] = {}
        self.deadline: float | None = None  # run_tests never outlives the episode

    def call(self, name: str, args: dict) -> str:
        self.calls[name] = self.calls.get(name, 0) + 1
        fault = self.task.get("faults", {}).get(name, {}).get(str(self.calls[name]))
        if fault:
            return f"error: {fault}"
        try:
            if name == "read_file":
                return self.read_file(**args)
            if name == "write_file":
                return self.write_file(**args)
            if name == "run_tests":
                return self.run_tests()
            return f"error: unknown tool {name!r}"
        except ToolError as e:
            return f"error: {e}"
        except TypeError as e:
            return f"error: bad arguments for {name}: {e}"
        except (OSError, ValueError) as e:  # e.g. an over-long or NUL-containing path
            return f"error: {name} failed: {e}"

    def read_file(self, path, offset=1, limit=READ_MAX_LINES, whole=False):
        target = resolve_in(self.root, path)
        if target.is_dir():
            names = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir() if p.name != ".git")
            return "\n".join(names) if names else "(empty directory)"
        if not target.is_file():
            raise ToolError(f"no such file: {path}")
        lines = target.read_text(errors="replace").splitlines(keepends=True)
        if whole:
            return "".join(lines)
        try:
            offset, limit = max(1, int(offset)), max(1, min(int(limit), READ_MAX_LINES))
        except (TypeError, ValueError):
            raise ToolError("offset and limit must be integers") from None
        chunk, size, end = [], 0, offset - 1
        for line in lines[offset - 1:offset - 1 + limit]:
            if size + len(line.encode()) > READ_MAX_BYTES and chunk:
                break
            chunk.append(line)
            size += len(line.encode())
            end += 1
        text = "".join(chunk)
        if offset > 1 or end < len(lines):
            text += f"\n[lines {offset}-{end} of {len(lines)}; call read_file with offset={end + 1} to continue]"
        return text

    def write_file(self, path, content):
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        target = resolve_in(self.root, path)
        if target.is_dir():
            raise ToolError(f"{path} is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content.encode())} bytes to {path}"

    def run_tests(self):
        timeout = TEST_TIMEOUT_S
        if self.deadline is not None:
            timeout = min(timeout, self.deadline - time.monotonic())
        rc, out = run_cmd(self.task["tests_cmd"], self.root, self.hidden_dir, timeout)
        n = self.calls["run_tests"]
        tail_lines = self.task.get("run_tests_tail_lines")
        if tail_lines:
            log = self.root / ".suite" / f"run-{n}.log"
            log.parent.mkdir(exist_ok=True)
            log.write_text(out)
            tail = "\n".join(out.rstrip("\n").splitlines()[-tail_lines:])
            return f"exit code: {rc}\n{tail}\n[output truncated; full log: .suite/run-{n}.log]"
        tail = out[-TESTS_TAIL_CHARS:]
        prefix = "[output truncated to the last 4,000 characters]\n" if len(out) > TESTS_TAIL_CHARS else ""
        return f"exit code: {rc}\n{prefix}{tail}"


def score(worktree: pathlib.Path, task: dict, commit: str, hidden_dir: pathlib.Path | None) -> dict:
    """Replace the visible test tree with the pinned one (model-added files go too), then run the
    score command; hidden tests run from hidden_dir, which the model cannot write."""
    shutil.rmtree(worktree / task["test_dir"], ignore_errors=True)
    git(worktree, "checkout", commit, "--", task["test_dir"])
    rc, out = run_cmd(task["score_cmd"], worktree, hidden_dir)
    return {"tests": rc == 0, "rc": rc, "output_tail": out[-TESTS_TAIL_CHARS:]}


def make_hidden_dir(task: dict, parent: pathlib.Path) -> pathlib.Path | None:
    if not task.get("hidden"):
        return None
    d = parent / "hidden"
    d.mkdir()
    shutil.copy(TASKS_DIR / task["hidden"], d / pathlib.Path(task["hidden"]).name)
    return d


# --- streaming client ---------------------------------------------------------------------

def parse_sse(lines) -> dict:
    """Assemble one streamed chat completion: text, reasoning, tool calls by index, finish reason."""
    content, reasoning, calls = [], [], {}
    finish, usage, timings = None, None, None
    for raw in lines:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        if "error" in chunk:
            raise RuntimeError(f"server error: {chunk['error']}")
        usage = chunk.get("usage") or usage
        timings = chunk.get("timings") or timings
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                content.append(delta["content"])
            if delta.get("reasoning_content"):
                reasoning.append(delta["reasoning_content"])
            for tc in delta.get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", 0), {"id": None, "name": "", "arguments": ""})
                slot["id"] = tc.get("id") or slot["id"]
                fn = tc.get("function") or {}
                slot["name"] += fn.get("name") or ""
                slot["arguments"] += fn.get("arguments") or ""
            finish = choice.get("finish_reason") or finish
    return {"content": "".join(content), "reasoning": "".join(reasoning),
            "tool_calls": [calls[i] for i in sorted(calls)], "finish_reason": finish,
            "usage": usage, "timings": timings}


class EpisodeTimeout(Exception):
    pass


class MonitorAbort(Exception):
    """GPU thermal/VRAM guard tripped: stops the whole run, never scored as an episode outcome."""


def monitor_failure(monitor) -> str | None:
    if monitor is None:
        return None
    if monitor.bad:
        return monitor.bad.get("abort_reason", "monitor abort")
    return f"monitor stopped: {monitor.error}" if monitor.error else None


def http_json(url: str, payload: dict | None = None, timeout: float = 60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def chat(url: str, body: dict, deadline: float, monitor=None) -> dict:
    """One streamed request. A watcher thread shuts the socket at the episode deadline or on a
    monitor abort, so neither a long prefill nor a stalled stream can outlive them."""
    if time.monotonic() >= deadline:
        raise EpisodeTimeout()
    u = urllib.parse.urlsplit(url)
    cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    conn = cls(u.hostname, u.port, timeout=deadline - time.monotonic())
    stop, why, sock = threading.Event(), [], []  # sock: kept because getresponse() may drop conn.sock

    def watch():
        while not stop.wait(0.5):
            failure = monitor_failure(monitor)
            if failure or time.monotonic() >= deadline:
                why.append(failure or "timeout")
                for s in sock:
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                return

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    out, error = None, None
    try:
        conn.connect()
        sock.append(conn.sock)
        conn.request("POST", u.path.rstrip("/") + "/v1/chat/completions", body=json.dumps(body),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {resp.read()[:500]!r}")
        out = parse_sse(resp)
    except (OSError, http.client.HTTPException, ValueError, RuntimeError) as e:
        error = e
    finally:
        stop.set()
        watcher.join()
        conn.close()
    if why:
        if why[0] == "timeout":
            raise EpisodeTimeout()
        raise MonitorAbort(why[0])
    if error is not None:
        raise error
    return out


def server_model(url: str) -> str:
    models = http_json(url.rstrip("/") + "/v1/models")
    data = models.get("data") or models.get("models") or []
    name = (data[0].get("id") or data[0].get("name")) if data else "local"
    return pathlib.PurePath(name).name  # llama-server reports the GGUF path; keep only the file name


# --- episode ------------------------------------------------------------------------------

def pack_messages(worktree: pathlib.Path, files: list[str], tools: Tools) -> list[dict]:
    calls, results = [], []
    for i, rel in enumerate(files):
        cid = f"pack_{i}"
        calls.append({"id": cid, "type": "function",
                      "function": {"name": "read_file", "arguments": json.dumps({"path": rel})}})
        results.append({"role": "tool", "tool_call_id": cid, "content": tools.read_file(rel, whole=True)})
    return [{"role": "user", "content": PACK_PREAMBLE},
            {"role": "assistant", "content": "", "tool_calls": calls}, *results]


def initial_messages(suite: dict, task: dict, worktree: pathlib.Path, tools: Tools,
                     pack_files: list[str] | None) -> list[dict]:
    msgs = [{"role": "system", "content": suite["system_prompt"].replace("{repo}", task["repo"])}]
    if task.get("pack"):
        msgs += pack_messages(worktree, pack_files or [], tools)
    if task.get("summary"):
        msgs.append({"role": "user", "content": task["summary"]})
    msgs.append({"role": "user", "content": task["prompt"]})
    return msgs


def run_episode(*, suite, task, seed, url, model, sampling, out_dir: pathlib.Path,
                pack_files=None, monitor=None, cache=CACHE) -> dict:
    spec = suite["repos"][task["repo"]]
    repo = ensure_repo(task["repo"], spec, cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"coding-suite-{task['id']}-") as tmp:
        tmp = pathlib.Path(tmp)
        worktree = tmp / "wt"
        setup_worktree(repo, spec["commit"], task, worktree)
        try:
            hidden_dir = make_hidden_dir(task, tmp)
            tools = Tools(worktree, task, hidden_dir)
            messages = initial_messages(suite, task, worktree, tools, pack_files)
            tools.calls.clear()
            result = _loop(task, seed, url, model, sampling, messages, tools, out_dir, monitor)
            diff = model_diff(worktree)
            (out_dir / "model.diff").write_text(diff)
            scored = score(worktree, task, spec["commit"], hidden_dir)
        finally:
            remove_worktree(repo, worktree)
    (out_dir / "score.txt").write_text(f"rc={scored['rc']}\n{scored['output_tail']}")
    result.update(tests=scored["tests"], score_rc=scored["rc"])
    result["pass"] = result["completed"] and result["tests"]
    if not result["pass"] and result["reason"] is None:
        result["reason"] = "tests"
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def _loop(task, seed, url, model, sampling, messages, tools, out_dir, monitor) -> dict:
    t0 = time.monotonic()
    deadline = t0 + task["timeout_s"]
    tools.deadline = deadline
    reason, completed, turns, bad_streak = None, False, 0, 0
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    with (out_dir / "trace.jsonl").open("w") as trace:
        def log(**row):
            trace.write(json.dumps({"t": round(time.monotonic() - t0, 3), **row}) + "\n")
            trace.flush()
        log(type="start", task=task["id"], seed=seed, n_initial_messages=len(messages),
            initial_messages=[m for m in messages if m["role"] != "tool"])
        while True:
            failure = monitor_failure(monitor)
            if failure:
                raise MonitorAbort(failure)
            if turns >= MAX_TURNS:
                reason = "turn-limit"
                break
            body = {"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto",
                    "stream": True, "stream_options": {"include_usage": True},
                    "max_tokens": MAX_TOKENS, "seed": seed, **sampling}
            turns += 1
            try:
                resp = chat(url, body, deadline, monitor)
            except EpisodeTimeout:
                reason = "timeout"
                break
            except MonitorAbort:
                raise
            except (urllib.error.URLError, http.client.HTTPException, RuntimeError, ValueError, OSError) as e:
                log(type="api-error", error=str(e))
                reason = "api-error"
                break
            for k in usage_total:
                usage_total[k] += (resp.get("usage") or {}).get(k, 0) or 0
            log(type="response", turn=turns, **resp)
            msg = {"role": "assistant", "content": resp["content"]}
            if resp["reasoning"]:  # the chat template keeps reasoning inside a tool loop
                msg["reasoning_content"] = resp["reasoning"]
            calls = [dict(c, id=c["id"] or f"call_{turns}_{i}") for i, c in enumerate(resp["tool_calls"])]
            if calls:
                msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                      "function": {"name": c["name"], "arguments": c["arguments"]}}
                                     for c in calls]
            messages.append(msg)
            if resp["finish_reason"] == "length":
                reason = "length"
                break
            if not calls:
                if resp["finish_reason"] != "stop":  # stream ended without a terminal event
                    log(type="api-error", error=f"no tool call and finish_reason={resp['finish_reason']!r}")
                    reason = "api-error"
                    break
                completed = time.monotonic() <= deadline
                reason = None if completed else "timeout"
                break
            for c in calls:
                if time.monotonic() > deadline:
                    break
                try:
                    args = json.loads(c["arguments"] or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be a JSON object")
                    known = c["name"] in {t["function"]["name"] for t in TOOLS}
                except ValueError as e:
                    args, known = None, False
                    out = f"error: tool arguments are not valid JSON: {e}"
                if args is not None:
                    out = tools.call(c["name"], args)
                bad_streak = 0 if known and args is not None else bad_streak + 1
                log(type="tool", name=c["name"], arguments=c["arguments"], result=out)
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": out})
            if bad_streak >= BAD_TOOL_CALL_LIMIT:
                reason = "bad-tool-call"
                break
            if time.monotonic() > deadline:
                reason = "timeout"
                break
        log(type="end", reason=reason, completed=completed, turns=turns)
    return {"task": task["id"], "seed": seed, "completed": completed, "reason": reason,
            "turns": turns, "wall_s": round(time.monotonic() - t0, 1), "usage": usage_total,
            "tool_calls": dict(tools.calls)}


# --- CS4 pack -----------------------------------------------------------------------------

def pack_candidates(worktree: pathlib.Path, pack: dict) -> list[str]:
    ordered, seen = [], set()
    for rel in pack["first"]:
        ordered.append(rel)
        seen.add(rel)
    for pattern in pack["globs"]:
        for p in sorted(worktree.glob(pattern)):
            rel = p.relative_to(worktree).as_posix()
            if p.is_file() and rel not in seen and "__pycache__" not in rel:
                ordered.append(rel)
                seen.add(rel)
    return ordered


def load_pack(task: dict, depth: str) -> list[str]:
    frozen = TASKS_DIR / task["pack"]["frozen"]
    if not frozen.exists():
        raise SystemExit(f"{frozen} is missing: run --freeze-pack once against the reference model")
    return json.loads(frozen.read_text())[depth]["files"]


def count_tokens(url: str, messages: list[dict]) -> int:
    prompt = http_json(url.rstrip("/") + "/apply-template", {"messages": messages, "tools": TOOLS},
                       timeout=600)["prompt"]
    return len(http_json(url.rstrip("/") + "/tokenize", {"content": prompt, "add_special": False},
                         timeout=600)["tokens"])


def freeze_pack(url: str, suite: dict) -> dict:
    task = next(t for t in suite["tasks"] if t.get("pack"))
    spec = suite["repos"][task["repo"]]
    repo = ensure_repo(task["repo"], spec)
    result = {"model": server_model(url), "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "method": "/apply-template with tools + /tokenize on the initial request"}
    with tempfile.TemporaryDirectory(prefix="coding-suite-pack-") as tmp:
        worktree = pathlib.Path(tmp) / "wt"
        setup_worktree(repo, spec["commit"], task, worktree)
        try:
            tools = Tools(worktree, task, None)
            candidates = pack_candidates(worktree, task["pack"])
            for depth, target in task["pack"]["targets"].items():
                lo, hi = 0, len(candidates)  # largest prefix whose initial request fits the target
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    n = count_tokens(url, initial_messages(suite, task, worktree, tools, candidates[:mid]))
                    lo, hi = (mid, hi) if n <= target else (lo, mid - 1)
                files = candidates[:lo]
                tokens = count_tokens(url, initial_messages(suite, task, worktree, tools, files))
                result[depth] = {"target_tokens": target, "tokens": tokens, "files": files,
                                 "characters": sum(len(tools.read_file(f, whole=True)) for f in files)}
                print(f"{depth}: {len(files)} files, {tokens} tokens (target {target})")
        finally:
            remove_worktree(repo, worktree)
    return result


# --- fake server for --smoke ----------------------------------------------------------------

def reference_plan(suite: dict, task: dict, cache=CACHE) -> list[tuple[str, dict]]:
    """Tool calls that apply the task's reference fix: what a correct agent would do."""
    spec = suite["repos"][task["repo"]]
    repo = ensure_repo(task["repo"], spec, cache)
    with tempfile.TemporaryDirectory(prefix="coding-suite-ref-") as tmp:
        worktree = pathlib.Path(tmp) / "wt"
        setup_worktree(repo, spec["commit"], task, worktree)
        try:
            apply_reference(worktree, task)
            changed = git(worktree, "diff", "--name-only", "HEAD").split()
            plan = [("read_file", {"path": changed[0]})]
            plan += [("write_file", {"path": p, "content": (worktree / p).read_text()}) for p in changed]
        finally:
            remove_worktree(repo, worktree)
    return plan + [("run_tests", {})]


class FakeModel:
    """Stateless scripted model: the next step is the first plan call without a successful result."""

    def __init__(self, plan: list):
        self.plan = plan

    def respond(self, body: dict) -> list[dict]:
        msgs = body["messages"]
        last_user = max(i for i, m in enumerate(msgs) if m["role"] == "user")
        done = sum(1 for m in msgs[last_user:] if m["role"] == "tool" and not m["content"].startswith("error: "))
        plan = self.plan
        chunks = [{"choices": [{"delta": {"reasoning_content": "Planning the next step."}}]}]
        if done < len(plan):
            name, args = plan[done]
            text = json.dumps(args)
            cut = len(text) // 2
            chunks += [
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": f"fake_{len(msgs)}",
                                                        "function": {"name": name, "arguments": text[:cut]}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": text[cut:]}}]}}]},
                {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}]
        else:
            chunks += [{"choices": [{"delta": {"content": "Fixed; the test suite passes."}}]},
                       {"choices": [{"delta": {}, "finish_reason": "stop"}]}]
        chunks.append({"choices": [], "usage": {"prompt_tokens": len(json.dumps(msgs)) // 4,
                                                "completion_tokens": 10}})
        return chunks


def start_fake_server(model: FakeModel):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps({"data": [{"id": "fake"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for chunk in model.respond(req):
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


# --- commands -----------------------------------------------------------------------------

def verify_fixtures(suite: dict, tasks: list[dict]) -> int:
    failures = 0
    for task in tasks:
        spec = suite["repos"][task["repo"]]
        repo = ensure_repo(task["repo"], spec)
        with tempfile.TemporaryDirectory(prefix="coding-suite-verify-") as tmp:
            tmp = pathlib.Path(tmp)
            worktree = tmp / "wt"
            setup_worktree(repo, spec["commit"], task, worktree)
            try:
                hidden_dir = make_hidden_dir(task, tmp)
                bug = score(worktree, task, spec["commit"], hidden_dir)["tests"]
                apply_reference(worktree, task)
                ref = score(worktree, task, spec["commit"], hidden_dir)["tests"]
            finally:
                remove_worktree(repo, worktree)
        ok = (not bug) and ref
        failures += not ok
        print(f"{task['id']}: with bug {'pass' if bug else 'fail'}, reference {'pass' if ref else 'fail'}"
              f" -> {'OK' if ok else 'BAD'}")
    return 1 if failures else 0


def run_dir_name(label: str) -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{label}" if label else "")


def summarize(results: list[dict]) -> dict:
    by_task: dict[str, dict] = {}
    for r in results:
        t = by_task.setdefault(r["task"], {"tests": 0, "completed": 0, "pass": 0, "seeds": []})
        t["tests"] += r["tests"]
        t["completed"] += r["completed"]
        t["pass"] += r["pass"]
        t["seeds"].append({k: r[k] for k in ("seed", "tests", "completed", "pass", "reason", "turns", "wall_s")})
    return by_task


def run_suite(args, suite, tasks, url, model, sampling, meta, monitor=None, cache=CACHE) -> list[dict]:
    out = args.output / run_dir_name(args.label)
    out.mkdir(parents=True)
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    results = []
    for task in tasks:
        pack = None
        if task.get("pack"):
            pack = task["pack"]["first"] if args.smoke else load_pack(task, args.cs4_depth)
        for seed in args.seeds:
            r = run_episode(suite=suite, task=task, seed=seed, url=url, model=model, sampling=sampling,
                            out_dir=out / f"{task['id']}-s{seed}", pack_files=pack, monitor=monitor,
                            cache=cache)
            results.append(r)
            print(f"{task['id']} seed {seed}: {'PASS' if r['pass'] else 'FAIL'} tests={r['tests']} "
                  f"completed={r['completed']} reason={r['reason']} turns={r['turns']} {r['wall_s']} s",
                  flush=True)
    summary = {"run": out.name, "tasks": summarize(results)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"results: {out}")
    return results


def rescore(run: pathlib.Path) -> int:
    suite = load_suite()
    tasks = {t["id"]: t for t in suite["tasks"]}
    mismatches = 0
    for result_file in sorted(run.glob("CS*-s*/result.json")):
        saved = json.loads(result_file.read_text())
        task = tasks[saved["task"]]
        spec = suite["repos"][task["repo"]]
        repo = ensure_repo(task["repo"], spec)
        with tempfile.TemporaryDirectory(prefix="coding-suite-rescore-") as tmp:
            tmp = pathlib.Path(tmp)
            worktree = tmp / "wt"
            setup_worktree(repo, spec["commit"], task, worktree)
            try:
                diff = (result_file.parent / "model.diff").read_text()
                if diff.strip():
                    git(worktree, "apply", "--binary", "-", input_text=diff)
                tests = score(worktree, task, spec["commit"], make_hidden_dir(task, tmp))["tests"]
            finally:
                remove_worktree(repo, worktree)
        same = tests == saved["tests"]
        mismatches += not same
        print(f"{result_file.parent.name}: saved tests={saved['tests']} rescored={tests} {'OK' if same else 'MISMATCH'}")
    return 1 if mismatches else 0


def compare_task(base: dict[int, bool], cand: dict[int, bool]) -> str:
    """Predeclared rule on the `tests` column (design doc): seeds 1-3, or 1-6 after an
    inconclusive result, on both arms."""
    if set(base) not in ({1, 2, 3}, {1, 2, 3, 4, 5, 6}) or set(base) != set(cand):
        return "incomplete: both arms need seeds 1-3 (or 1-6) for this task"
    drop = sum(base.values()) - sum(cand.values())
    if drop >= 2:
        return "regression"
    if drop == 1 and len(base) < 6:
        return "inconclusive: rerun this task with seeds 4,5,6 on both arms"
    return "ok"


def load_tests_by_seed(run: pathlib.Path) -> dict[str, dict[int, bool]]:
    out: dict[str, dict[int, bool]] = {}
    for f in sorted(run.glob("CS*-s*/result.json")):
        r = json.loads(f.read_text())
        out.setdefault(r["task"], {})[r["seed"]] = r["tests"]
    return out


def compare(base_runs: list[pathlib.Path], cand_runs: list[pathlib.Path]) -> int:
    def merged(runs):
        out: dict[str, dict[int, bool]] = {}
        for run in runs:
            for task, seeds in load_tests_by_seed(run).items():
                out.setdefault(task, {}).update(seeds)
        return out
    base, cand = merged(base_runs), merged(cand_runs)
    tasks = sorted(set(base) | set(cand))
    if not tasks:
        print("verdict: incomplete (no results found)")
        return 3
    verdicts = {t: compare_task(base.get(t, {}), cand.get(t, {})) for t in tasks}
    for task, verdict in verdicts.items():
        b, c = base.get(task, {}), cand.get(task, {})
        print(f"{task}: base {sum(b.values())}/{len(b)}, candidate {sum(c.values())}/{len(c)}: {verdict}")
    if any(v == "regression" for v in verdicts.values()):
        print("verdict: candidate rejected (regression)")
        return 1
    if any(v.startswith("incomplete") for v in verdicts.values()):
        print("verdict: incomplete")
        return 3
    if any(v.startswith("inconclusive") for v in verdicts.values()):
        print("verdict: inconclusive")
        return 2
    print("verdict: no regression")
    return 0


def find_listen_pid(port: int) -> int | None:
    p = subprocess.run(["ss", "-Hltnp", f"sport = :{port}"], capture_output=True, text=True)
    m = re.search(r"pid=(\d+)", p.stdout)
    return int(m.group(1)) if m else None


def run_meta(args, url, model, alias, sampling) -> dict:
    meta = {"started": dt.datetime.now(dt.timezone.utc).isoformat(), "argv": sys.argv,
            "url": url, "model": model, "alias": alias, "sampling_sent": sampling,
            "controls_sent": {"seed": list(args.seeds), "max_tokens": MAX_TOKENS, "max_turns": MAX_TURNS},
            "cs4_depth": args.cs4_depth, "python": platform.python_version(),
            "suite_version": load_suite()["suite_version"],
            "repo_commit": git(ROOT, "rev-parse", "HEAD", check=False).strip()}
    for path in ("/v1/models", "/props"):
        try:
            meta[path] = http_json(url.rstrip("/") + path, timeout=10)
        except (urllib.error.URLError, ValueError, OSError) as e:
            meta[path] = f"unavailable: {e}"
    return meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true", help="run the suite against --url (needs IA_BENCH_INHIBITED=1)")
    mode.add_argument("--smoke", action="store_true", help="full loop against a built-in fake model; no server")
    mode.add_argument("--verify-fixtures", action="store_true", help="bug fails and reference passes, per task")
    mode.add_argument("--freeze-pack", action="store_true", help="measure and write the CS4 file lists (needs a server)")
    mode.add_argument("--rescore", type=pathlib.Path, metavar="RUN_DIR", help="re-score saved diffs of a run")
    mode.add_argument("--compare", nargs=2, metavar=("BASE", "CANDIDATE"),
                      help="apply the regression rule; comma-separate several run dirs per arm")
    ap.add_argument("--tasks", help="comma-separated task ids (default: all)")
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)), help="comma-separated seeds (default 1,2,3)")
    ap.add_argument("--url", default=None, help="server URL (default http://127.0.0.1:<[defaults].port>)")
    ap.add_argument("--alias", help="models.toml alias for sampling (default: [defaults].default_alias)")
    ap.add_argument("--sampling", help="key=value,... sent instead of the alias table (e.g. for Strata)")
    ap.add_argument("--cs4-depth", choices=("default", "deep"), default="default")
    ap.add_argument("--label", default="", help="suffix of the run directory name")
    ap.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    ap.add_argument("--no-monitor", action="store_true",
                    help="run without the GPU thermal/VRAM monitor (only if the server PID cannot be found)")
    args = ap.parse_args(argv)
    args.seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    suite = load_suite()
    tasks = select_tasks(suite, args.tasks)

    if args.verify_fixtures:
        return verify_fixtures(suite, tasks)
    if args.rescore:
        return rescore(args.rescore)
    if args.compare:
        return compare([pathlib.Path(p) for p in args.compare[0].split(",")],
                       [pathlib.Path(p) for p in args.compare[1].split(",")])
    if args.smoke:  # one fake server per task, scripted with that task's reference fix
        results = []
        for task in tasks:
            server, url = start_fake_server(FakeModel(reference_plan(suite, task)))
            try:
                one = argparse.Namespace(**{**vars(args), "seeds": args.seeds[:1],
                                            "label": f"smoke-{task['id']}"})
                results += run_suite(one, suite, [task], url, "fake", {"temperature": 1.0}, {"smoke": True})
            finally:
                server.shutdown()
        bad = [r for r in results if not r["pass"]]
        print("smoke: OK" if not bad else f"smoke: FAILED {[r['task'] for r in bad]}")
        return 1 if bad else 0

    manifest = tomllib.loads((ROOT / "models.toml").read_text())
    url = args.url or f"http://127.0.0.1:{manifest['defaults'].get('port', 8080)}"
    if os.environ.get("IA_BENCH_INHIBITED") != "1":
        ap.error("requires systemd-inhibit and IA_BENCH_INHIBITED=1; see the docstring")
    if args.freeze_pack:
        result = freeze_pack(url, suite)
        task = next(t for t in suite["tasks"] if t.get("pack"))
        (TASKS_DIR / task["pack"]["frozen"]).write_text(json.dumps(result, indent=2) + "\n")
        return 0

    alias, sampling = load_sampling(args.alias, args.sampling)
    model = server_model(url)
    sys.path.insert(0, str(HERE))
    import depth_bench  # GPU telemetry and the power-cap helpers shared by every bench

    expect = depth_bench.resolve_expect_power_cap_w(os.environ)
    for w in depth_bench.power_cap_warnings(depth_bench.power_cap_snapshot()["cards"], 1, expect, deep_threshold=0):
        print(w, file=sys.stderr)
    meta = run_meta(args, url, model, alias, sampling)
    meta["power_cap"] = depth_bench.power_cap_snapshot()
    monitor = None
    port = int(url.rsplit(":", 1)[1].split("/")[0])
    pid = find_listen_pid(port)
    if pid is None and not args.no_monitor:
        ap.error(f"no process found listening on port {port}; start the engine or pass --no-monitor")
    args.output.mkdir(parents=True, exist_ok=True)
    mon_file = None
    if pid is not None:
        mon_file = (args.output / f"monitor-{run_dir_name(args.label)}.jsonl").open("w")
        monitor = depth_bench.Monitor(pid, mon_file)
        monitor.set_phase("coding-suite")
        monitor.start()
    try:
        run_suite(args, suite, tasks, url, model, sampling, meta, monitor)
    finally:
        if monitor is not None:
            monitor.stop()
            mon_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
