# SOP: persistent token ledger

`llama-server --metrics` (in `[defaults] flags`, `models.toml`) exposes Prometheus counters at
`/metrics` that reset to zero on every restart. `scripts/token_ledger.py` samples them
periodically and accumulates an all-time, restart-proof total in
`~/.local/share/llm-usage/ledger.json` (override with `LLM_USAGE_DIR`). No daemon: a systemd
user timer runs `token_ledger.py collect` every 60 s.

Tracked categories (verified against the running binary's Prometheus metric names):

| Ledger category | Prometheus metric |
|---|---|
| `prompt_new` | `llamacpp:prompt_tokens_total` (new, non-cached prompt tokens) |
| `cache_read` | `llamacpp:prompt_tokens_cached_total` (prompt tokens reused from the KV cache) |
| `output` | `llamacpp:tokens_predicted_total` (generated tokens) |

## Install the timer

```bash
mkdir -p ~/.config/systemd/user
sed "s#REPO_PATH#$(pwd)#" scripts/systemd/llm-token-ledger.service > ~/.config/systemd/user/llm-token-ledger.service
cp scripts/systemd/llm-token-ledger.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now llm-token-ledger.timer
```

Run this from the repository root so `$(pwd)` resolves to your clone's absolute path — same
placeholder-substitution convention as `local.example.toml`'s `models_root`. The installed
copies under `~/.config/systemd/user/` are outside this repository and not tracked by git.

## Seed a historical baseline (optional, one-time)

If you have usage from before the ledger existed (e.g. recovered from session logs), record it
once:

```bash
python3 scripts/token_ledger.py seed --prompt-new 393386 --cache-read 15076303 --output 111723 \
    --turns 195 --note "backfill from session logs up to 2026-09-25"
```

Refuses to overwrite an existing baseline; pass `--force` to replace it.

## Check it

```bash
python3 scripts/token_ledger.py show          # human-readable
python3 scripts/token_ledger.py show --json    # machine-readable
systemctl --user list-timers | grep llm-token
```

## How to verify

- `systemctl --user list-timers` lists `llm-token-ledger.timer` with a `NEXT`/`LEFT` time.
- `python3 scripts/token_ledger.py show` prints all-time totals, the seeded baseline (if any)
  separately, today's numbers, and the last collection time.
- `python3 -m unittest discover -s tests -v` covers the pure logic (metrics parsing, delta
  accumulation, restart handling, per-day bucket, seed refuse/force) with no network access.

## Known errors

- **`collect` exits 0 and writes nothing**: either the server is down, or it's running without
  `--metrics` (check `[defaults] flags` in `models.toml` and that the running server was
  launched *after* that flag was added — it only applies on the next `launch.py`, not to an
  already-running process).
- **Counter lower than the last sample**: the server restarted (Prometheus counters reset to 0).
  `collect` treats the new value itself as the delta instead of subtracting — no manual fixup
  needed.
