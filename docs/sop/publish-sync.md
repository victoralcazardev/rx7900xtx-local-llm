# SOP: keep the GitHub-facing surfaces in sync (after every release and push)

Mandatory after **every release** and **every push to `main` that changes what the README shows**:
the setups table, the "Tested setup" engines, the "Credits" table, a headline number, or the model
list. Skip it only for changes that touch none of those.

The repository's public surfaces drift from the docs unless they are checked together. The
repository documents several setups side by side and recommends none of them: no surface may call
one model or setup the default, main or recommended.

## Surfaces and their owner

| Surface | Must match | Check |
|---|---|---|
| README "Setups", "Tested setup" | `docs/STATUS.md`, plus the owner doc of each setup row | Compare the tables line by line; every setup listed without ranking |
| README "Credits" | The engines, ports, quants and models actually in use (`docs/ENGINES.md`, `docs/models/*.md`, `docs/SOURCES*.md`) | Every row still used, every new upstream source added |
| Repo description (About) | README "Setups" (speed, engine, power) | `gh repo view --json description --jq .description` |
| Repo topics | Hardware, engines, models and techniques actually used | `gh repo view --json repositoryTopics` |
| Latest release | An engine of a documented setup in STATUS and `docs/ENGINES.md` | `gh release list -L 3` |
| `CHANGELOG.md` | One line per user-visible change | `git log --oneline` since the last entry |

## Procedure

1. Read the README "Setups", "Tested setup" and "Credits" tables and the `docs/STATUS.md` numbers.
   They are the source.
2. Rewrite the About text so every number in it appears in those tables, listing the setups in use
   without ranking them. Pattern: `262K-context local LLMs on one RX 7900 XTX (gfx1100, 272 W):
   <model> on <engine> (<headline numbers>), <model> on <engine> (<numbers>). Several setups side by
   side. Configs, launcher, benchmarks.` GitHub caps the description at 350 characters.
   `gh repo edit --description "<text>"`
3. Update the "Credits" table: add a row for every engine, port, quant or model this change borrows
   from, keep the rows still in use, and verify each link against `docs/ENGINES.md`, the model docs
   and `docs/SOURCES*.md`. No attribution the docs do not support.
4. Confirm the release tagged `Latest` is the engine of a setup this repository documents, and that
   the release notes say which one. If the engine changed, publish it first
   ([`update-engine.md`](update-engine.md#publish-a-release)); releases for the other engines stay
   un-marked (`gh release edit <tag> --latest=false`), since no engine is the default.
5. Upstream contributions are not listed in the README; record them in `CHANGELOG.md` only.
6. Run `python3 scripts/check-repo.py` and `python3 -m unittest discover -s tests`, and commit the
   README/CHANGELOG fix together with the change that caused it.

## Known stale-number traps

- Recall: the About text once kept `60/60` after the pooled total became `68/68`
  ([`depth.md`](../measurements/depth.md)). Always use the pooled total from the row's owner doc.
- Rounded speeds: round the README range (`22.5-33.2`) outward-neutral (`23-33`), never reuse an
  older run's value.
- No setup is primary: after 2026-11-23 no table heading, About text or credits row may present one
  setup as the main one; the launcher's no-alias fallback is a technical detail, not a ranking.
