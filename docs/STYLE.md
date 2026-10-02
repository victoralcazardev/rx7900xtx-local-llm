# Style guide

Rules for every tracked file in this repository: docs, code comments, CLI help, program
output, commit messages, identifiers, config keys and CLI flags.

## 1. Language

English only, everywhere, with two deliberate exceptions: test *content* that is Spanish on
purpose (for example a Spanish long-context retrieval corpus, or Spanish prompts used to
exercise a model's Spanish output), and Spanish terms in the glossary in §4. Mark Spanish test
content with an English comment explaining why it stays in Spanish instead of being translated.

## 2. Units

- Memory: MiB/GiB (binary). Use MB/GB only when quoting a disk size or a figure straight from
  a vendor spec sheet.
- Throughput: tok/s.
- Temperature: °C.
- Power: W.

## 3. Numbers (critical)

Use the English convention: `.` for the decimal point, `,` for the thousands separator.

Spanish source material uses the opposite convention (`.` for thousands, `,` for decimals).
A literal copy-paste silently changes the value by 1000x or breaks the decimal part. Convert
every number by hand and re-check:

- `21.679 MiB` (Spanish) → `21,679 MiB` (English)
- `25,2 tok/s` (Spanish) → `25.2 tok/s` (English)
- `0,000587` (Spanish) → `0.000587` (English)

After writing or translating a file with numbers: grep for `\d\.\d{3}\b` (a Spanish thousands
separator that leaked through) and `\d,\d` (a Spanish decimal that leaked through), and compare
every table against its source, cell by cell.

## 4. Glossary

Fixed translations used throughout this repository:

| Spanish | English |
|---|---|
| prefill | prefill (pp) |
| generación | generation (tg) |
| aceptación | acceptance rate |
| borrador | draft |
| desalojada | evicted |
| traspaso | handoff |
| perfil | profile |
| motor | engine |
| caché caliente | warm cache |
| hipótesis (H) | hypothesis (H) |
| verificada (V) | verified (V) |

## 5. Naming

English, lowercase, hyphens (`kebab-case`) for files and folders. Result folders follow
`YYYYMMDD-topic-variant` (e.g. `20260925-depth-190k-kvmix-vs-vec4`). Every result folder has a
short `README.md`: what it measures, the exact command, and the conclusion with a link back
to the measurement doc that cites it.

## 6. Translating existing notes

Translation keeps meaning, numbers and links intact. Fold a review or audit annotation into the
surrounding prose (keep the finding and its evidence link) instead of preserving a bracketed
attribution mark — the finding matters, not who added it or when.

## 7. Immutable evidence

Once a result is published, it is never rewritten in place. A new measurement that
contradicts an earlier conclusion supersedes it: update the "current conclusion" block at the
top of the relevant doc, and move the previous conclusion to a dated history section below,
with a link to the new evidence. The old data point stays visible and dated — it is superseded,
not deleted.

## 8. Documentation workflow

Every fact has **one owner**: the single file where it is written in full. Other files link to the
owner instead of restating it. The README headline table is the only sanctioned mirror, of STATUS.

### Where new information goes

| What you have | Owner | Also update |
|---|---|---|
| A new measurement run | `results/YYYYMMDD-topic-variant/README.md` (what, exact command, versions, conclusion) plus raw data | One row in `results/INDEX.md`; the conclusion in the topic doc under `docs/measurements/` |
| A conclusion about a topic | `docs/measurements/<topic>.md` "Current conclusion" | STATUS only if the recommendation or a headline number changes |
| A change to the recommended profile or a policy | `models.toml` and `docs/STATUS.md` | One appended row in `docs/DECISIONS.md` |
| Something tried that lost or was set aside | One row in `docs/TRIED.md` (item, key numbers, evidence link) | One appended row in `docs/DECISIONS.md` |
| A third-party claim (issue, post, paper, model card) | One row in `docs/SOURCES.md` with its status: verified, hypothesis or refuted | The topic doc, if it changes a conclusion |
| An engine build | `docs/ENGINES.md` | STATUS if it becomes the adopted engine |
| A candidate or trial not yet adopted | `docs/ENGINES-EXPERIMENTS.md` (engines) or an open question in STATUS | — |
| A repeatable procedure | `docs/sop/<task>.md` | The README docs map, if it is new |
| A user-visible change | One line in `CHANGELOG.md` ending with the owner's path | — |
| Plans, scratch notes, task checklists | `odd/` (git-ignored) | — |

### Keeping docs small

- A "Current conclusion" block states only what is current, in at most ~10 bullets. When a newer
  result supersedes a bullet, move the bullet to that doc's dated "History" section (§7).
- "Open questions" lists only open items. When one is answered, remove it and link the answer
  from the owner doc.
- `docs/STATUS.md` holds only the current state: profile, headline numbers, flag rationale, and
  open questions and next steps as one line each that link their owner. Results, candidate
  lists, watch lists and analysis go to the owner doc, never to STATUS.
- Word budgets: `README.md` ≤ 1,000; `AGENTS.md` ≤ 900; `docs/STATUS.md` ≤ 1,000;
  `docs/TRIED.md` ≤ 1,200. A measurement doc that passes ~5,000 words gets split by sub-topic
  into a new doc, with a pointer section left under the old heading.
- Moving a section keeps its old heading as a one-line pointer, so existing anchors keep working.
- Before committing documentation, grep for the numbers you changed (`git grep -n "<number>"`)
  and fix or link every other copy.

