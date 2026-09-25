# Style guide

Rules for every tracked file in this repository: docs, code comments, CLI help, program
output, commit messages, identifiers, config keys and CLI flags.

## 1. Language

English only, everywhere, with one deliberate exception: test *content* that is Spanish on
purpose (for example a Spanish long-context retrieval corpus, or Spanish prompts used to
exercise a model's Spanish output). Mark that content with an English comment explaining why
it stays in Spanish instead of being translated.

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
