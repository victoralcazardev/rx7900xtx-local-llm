"""Persistent, all-time ledger for tokens processed by the local llama-server.

`llama-server --metrics` exposes Prometheus counters at `/metrics` that reset to zero on every
restart. This script samples them, accumulates the delta into a small JSON file that survives
restarts, and reports it. No daemon here: a systemd user timer (`scripts/systemd/`) runs
`collect` periodically.

Tracked categories, taken straight from the llama-server Prometheus counters (verified against
`libllama-server-impl.so` strings, b11160):
    prompt_new   llamacpp:prompt_tokens_total         new prompt tokens processed (not cached)
    cache_read   llamacpp:prompt_tokens_cached_total  prompt tokens reused from the KV cache
    output       llamacpp:tokens_predicted_total      generated tokens

Subcommands:
    collect  Sample /metrics once, accumulate the delta into the ledger. Exits 0 quietly, with
             nothing written, if the server is down or `--metrics` isn't enabled.
    show     Print all-time totals (historical baseline + collected), today's numbers, and the
             last collection time.
    seed     Record a one-time historical baseline recovered from outside this ledger. Refuses
             to overwrite an existing baseline unless `--force`.

Environment variables:
    LLM_USAGE_DIR  overrides the ledger directory (default: ~/.local/share/llm-usage)

Usage: python3 scripts/token_ledger.py {collect|show [--json]|seed --prompt-new N --cache-read N
--output N --turns N --note TEXT [--force]}
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import datetime

REPO = pathlib.Path(__file__).resolve().parent.parent

# Ledger key -> Prometheus metric name (see module docstring).
METRIC_NAMES = {
    "prompt_new": "llamacpp:prompt_tokens_total",
    "cache_read": "llamacpp:prompt_tokens_cached_total",
    "output": "llamacpp:tokens_predicted_total",
}
CATEGORY_KEYS = tuple(METRIC_NAMES)
FETCH_TIMEOUT_S = 2.0


def _zero_totals() -> dict[str, int]:
    return {key: 0 for key in CATEGORY_KEYS}


def get_port(models_toml: pathlib.Path | None = None) -> int:
    """Port from `models.toml` `[defaults] port` (default: 8080)."""
    path = models_toml or (REPO / "models.toml")
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("defaults", {}).get("port", 8080)


def fetch_metrics(port: int, timeout: float = FETCH_TIMEOUT_S) -> str | None:
    """GET /metrics from the local server. None if it's down or unreachable in time."""
    url = f"http://127.0.0.1:{port}/metrics"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError):
        return None


def parse_metrics(text: str) -> dict[str, int]:
    """Prometheus exposition format -> {ledger key: counter value}, for the three tracked
    metrics only. Missing metrics (e.g. `--metrics` disabled) are simply absent from the
    result."""
    raw: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].split("{", 1)[0]
        try:
            raw[name] = float(parts[1])
        except ValueError:
            continue
    return {
        key: int(raw[metric_name])
        for key, metric_name in METRIC_NAMES.items()
        if metric_name in raw
    }


def ledger_dir() -> pathlib.Path:
    override = os.environ.get("LLM_USAGE_DIR")
    if override:
        return pathlib.Path(override)
    return pathlib.Path.home() / ".local" / "share" / "llm-usage"


def ledger_path() -> pathlib.Path:
    return ledger_dir() / "ledger.json"


def default_state() -> dict:
    return {
        "baseline": None,
        "totals": _zero_totals(),
        "last_sample": {},
        "last_collected_at": None,
        "daily": {},
    }


def load_state(path: pathlib.Path) -> dict:
    if not path.exists():
        return default_state()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: pathlib.Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def apply_sample(state: dict, sample: dict[str, int], now: datetime) -> dict:
    """Folds present counters into running totals and retains their last known baselines."""
    last = state.get("last_sample") or {}
    totals = state.setdefault("totals", _zero_totals())
    day_key = now.date().isoformat()
    day_totals = state.setdefault("daily", {}).setdefault(day_key, _zero_totals())

    for key in CATEGORY_KEYS:
        if key not in sample:
            continue
        new_val = sample[key]
        old_val = last.get(key, 0)
        delta = new_val if new_val < old_val else new_val - old_val
        totals[key] = totals.get(key, 0) + delta
        day_totals[key] = day_totals.get(key, 0) + delta

    state["last_sample"] = {**last, **sample}
    state["last_collected_at"] = now.isoformat(timespec="seconds")
    return state


def _sum_totals(*parts: dict) -> dict[str, int]:
    return {key: sum(p.get(key, 0) for p in parts if p) for key in CATEGORY_KEYS}


def cmd_collect(args: argparse.Namespace) -> int:
    port = get_port()
    text = fetch_metrics(port)
    if text is None:
        return 0  # server down or unreachable: nothing to do
    sample = parse_metrics(text)
    if not sample:
        return 0  # --metrics not enabled on the running server: nothing to do
    path = ledger_path()
    state = load_state(path)
    state = apply_sample(state, sample, datetime.now())
    save_state(path, state)
    return 0


def _format_row(label: str, totals: dict[str, int]) -> str:
    return (
        f"  {label:<24} prompt-new={totals.get('prompt_new', 0):,}  "
        f"cache-read={totals.get('cache_read', 0):,}  output={totals.get('output', 0):,}"
    )


def cmd_show(args: argparse.Namespace) -> int:
    state = load_state(ledger_path())
    baseline = state.get("baseline")
    collected = state.get("totals", _zero_totals())
    all_time = _sum_totals(baseline, collected)
    today_key = datetime.now().date().isoformat()
    today = state.get("daily", {}).get(today_key, _zero_totals())
    last_collected_at = state.get("last_collected_at")

    if args.json:
        print(json.dumps({
            "all_time": all_time,
            "baseline": baseline,
            "collected": collected,
            "today": today,
            "today_date": today_key,
            "last_collected_at": last_collected_at,
        }, indent=2, sort_keys=True))
        return 0

    print("llama.cpp token ledger")
    print(_format_row("all-time:", all_time))
    if baseline:
        print(_format_row("  historical baseline:", baseline))
        print(
            f"    turns={baseline.get('turns', 0)}  seeded_at={baseline.get('seeded_at', '')}"
            f"  note={baseline.get('note', '')}"
        )
    else:
        print("  historical baseline:    none seeded -- see: token_ledger.py seed --help")
    print(_format_row("  collected (ledger):", collected))
    print(_format_row(f"today ({today_key}):", today))
    print(f"  last collection:        {last_collected_at or 'never'}")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    path = ledger_path()
    state = load_state(path)
    if state.get("baseline") is not None and not args.force:
        print(
            "error: a baseline is already seeded; pass --force to overwrite it.",
            file=sys.stderr,
        )
        return 1
    state["baseline"] = {
        "prompt_new": args.prompt_new,
        "cache_read": args.cache_read,
        "output": args.output,
        "turns": args.turns,
        "note": args.note,
        "seeded_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(path, state)
    print(
        f"seeded baseline: prompt-new={args.prompt_new:,} cache-read={args.cache_read:,} "
        f"output={args.output:,} turns={args.turns}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persistent, all-time ledger for tokens processed by the local llama-server."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("collect", help="Sample /metrics once and accumulate the delta into the ledger.")

    show = sub.add_parser("show", help="Print all-time totals, baseline and today's numbers.")
    show.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of text.")

    seed = sub.add_parser("seed", help="Record a one-time historical baseline.")
    seed.add_argument("--prompt-new", type=int, required=True, dest="prompt_new",
                       help="Historical new (non-cached) prompt tokens.")
    seed.add_argument("--cache-read", type=int, required=True, dest="cache_read",
                       help="Historical prompt tokens reused from the cache.")
    seed.add_argument("--output", type=int, required=True, help="Historical generated tokens.")
    seed.add_argument("--turns", type=int, required=True, help="Historical number of turns.")
    seed.add_argument("--note", required=True, help="Free-text note describing the baseline's source.")
    seed.add_argument("--force", action="store_true", help="Overwrite an existing baseline.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return {"collect": cmd_collect, "show": cmd_show, "seed": cmd_seed}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
