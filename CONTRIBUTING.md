# Contributing

Thanks for considering a contribution. This project stays intentionally small and
dependency-free (Python stdlib only) — please keep that in mind for scripts.

## Reporting an issue

Open a [GitHub issue](https://github.com/valcazar57/rx7900xtx-local-llm/issues). Use the
[bug report form](.github/ISSUE_TEMPLATE/bug_report.yml) for something broken, or the
[share your results form](.github/ISSUE_TEMPLATE/share_results.yml) if you want to contribute a
new measurement (see below for the full process).

## Contributing a reproducible result

New measurements on this or a similar GPU are welcome. Read
[`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md) first — it defines the metrics (pp/tg,
depth, cold/warm cache, acceptance rate, KLD) and the method for each benchmark type (speed,
quality, real server, stress test, per-process memory).

1. Reproduce your measurement with the scripts in [`bench/`](bench/) (see `bench/README.md`)
   rather than an ad hoc script — this keeps results comparable across contributors.
2. Report your environment in full:
   - GPU model, VRAM, and board (reference/custom)
   - GPU power cap (W)
   - Kernel version
   - Mesa version
   - ROCm runtime version **and** the compiler/toolchain used to build the engine (if different)
   - llama.cpp commit and build flags (or the official binary name)
   - Model file name and SHA256
   - The exact launch command
   - Context depth/fill, temperature, and number of repetitions
3. Add a result folder under `results/YYYYMMDD-topic-variant/` (see `docs/STYLE.md` §5 for the
   naming convention) with:
   - A short `README.md` following [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md): what
     it measures, the exact command, the conclusion, and a link back to the
     `docs/measurements/*.md` section it supports (or a new one, for a topic not yet covered).
   - A small `summary.md` or `summary.jsonl` and, when available, a `command.json` with the exact
     argv used.
   - Only small, valuable files — no raw per-request logs, SSE streams, or anything over 1 MiB
     (`scripts/check-repo.py` enforces this).
4. Add a row for the new folder to [`results/INDEX.md`](results/INDEX.md).

Evidence is immutable once published: a result folder is never edited after the fact. A
corrected or repeated measurement gets a new dated folder; the older one stays as-is
(`docs/STYLE.md` §7).

## Dev workflow

```bash
python3 -m unittest discover -s tests -v   # unit tests, no GPU/network needed
python3 scripts/check-repo.py               # repo hygiene: links, sizes, personal paths, secrets, language
```

- Every tracked file is written in English (code, comments, docs, CLI help, program output) —
  see [`docs/STYLE.md`](docs/STYLE.md) for the full language and number-format rules.
- `scripts/check-repo.py` must pass before opening a PR.
- Match the existing style; keep changes focused and don't fold in unrelated fixes.

## Pull request checklist

- [ ] `python3 -m unittest discover -s tests` passes
- [ ] `python3 scripts/check-repo.py` reports no problems
- [ ] All new/changed files are in English
- [ ] A new result folder follows `docs/BENCHMARK-FORMAT.md` and is listed in `results/INDEX.md`
- [ ] No personal machine paths, credentials, or secrets in tracked files
