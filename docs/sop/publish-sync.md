# SOP: sync GitHub-facing info after a push

The repository's public surfaces drift from the docs unless they are checked together. Run this
after every merge to `main` that changes a headline number, the adopted profile, the engine, or an
upstream contribution. Skip it for changes that touch none of those.

## Surfaces and their owner

| Surface | Must match | Check |
|---|---|---|
| Repo description (About) | README headline table (speed, recall, engine, power) | `gh repo view --json description --jq .description` |
| Repo topics | Hardware, engine and technique actually used | `gh repo view --json repositoryTopics` |
| README headline and "Tested setup" | `docs/STATUS.md` | Compare the two tables line by line |
| README "Upstream" section | State of each linked PR | `gh pr view <n> -R <owner/repo> --json state,mergedAt` |
| Latest release | Engine pinned in STATUS and `docs/ENGINES.md` | `gh release list -L 3` |
| `CHANGELOG.md` | One line per user-visible change | `git log --oneline` since the last entry |

## Procedure

1. Read the README headline table and `docs/STATUS.md` headline numbers. They are the source.
2. Rewrite the About text so every number in it appears in the headline table. Pattern:
   `262K-context Qwen3.8-27B on a single RX 7900 XTX: llama.cpp ROCm <build>, <profile>, <power>. <tok/s> at 240K fill, <recall> recall.`
   `gh repo edit --description "<text>"`
3. Check each upstream PR listed in README "Upstream"; update its state (open/merged/closed) and
   drop the link if it was closed unmerged. Look for new reviewer comments and answer them.
4. Confirm the release tagged `Latest` is the engine named in STATUS. If the engine changed,
   publish it first ([`update-engine.md`](update-engine.md)).
5. Run `python3 scripts/check-repo.py` and `python3 -m unittest discover -s tests`, then open a PR
   with any README/CHANGELOG fix.

## Known stale-number traps

- Recall: the About text once kept `60/60` after the pooled total became `68/68`
  ([`depth.md`](../measurements/depth.md)). Always use the pooled total from the headline table.
- Rounded speeds: round the README range (`18.6-26.9`) outward-neutral (`19-27`), never reuse an
  older run's value.
