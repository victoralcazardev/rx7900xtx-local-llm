# SOP: sync GitHub-facing info after a push

The repository's public surfaces drift from the docs unless they are checked together. Run this
after every merge to `main` that changes a headline number, the adopted profile, the engine, or the
model list. Skip it for changes that touch none of those.

## Surfaces and their owner

| Surface | Must match | Check |
|---|---|---|
| Repo description (About) | README "Models" and "Default profile" tables (speed, recall, engine, power) | `gh repo view --json description --jq .description` |
| Repo topics | Hardware, engines and techniques actually used | `gh repo view --json repositoryTopics` |
| README "Models", "Default profile" and "Tested setup" | `docs/STATUS.md`, plus the Strata owner doc for its row | Compare the tables line by line |
| Latest release | Engine pinned in STATUS and `docs/ENGINES.md` | `gh release list -L 3` |
| `CHANGELOG.md` | One line per user-visible change | `git log --oneline` since the last entry |

## Procedure

1. Read the README "Models" and "Default profile" tables and `docs/STATUS.md` headline numbers.
   They are the source.
2. Rewrite the About text so every number in it appears in those tables. Pattern:
   `262K-context local LLMs on one RX 7900 XTX: Qwen3.8-27B on llama.cpp ROCm (<tok/s> at 240K fill, <recall> recall), <other engines>. Configs, launcher, benchmarks.`
   `gh repo edit --description "<text>"`
3. Upstream contributions are not listed in the README; record them in `CHANGELOG.md` only.
4. Confirm the release tagged `Latest` is the engine named in STATUS. If the engine changed,
   publish it first ([`update-engine.md`](update-engine.md)).
5. Run `python3 scripts/check-repo.py` and `python3 -m unittest discover -s tests`, then open a PR
   with any README/CHANGELOG fix.

## Known stale-number traps

- Recall: the About text once kept `60/60` after the pooled total became `68/68`
  ([`depth.md`](../measurements/depth.md)). Always use the pooled total from the headline table.
- Rounded speeds: round the README range (`18.6-26.9`) outward-neutral (`19-27`), never reuse an
  older run's value.
