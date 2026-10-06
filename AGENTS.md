# rx7900xtx-local-llm

Config, launcher, benchmarks and measurement write-ups for running long-context LLMs on an **AMD
Radeon RX 7900 XTX (24 GB, RDNA3, gfx1100)** with `llama-server` (ROCm/HIP; Vulkan as reference).

## Start here

| Read | When |
|---|---|
| `docs/STATUS.md` | Every task: current profile, headline numbers, flag rationale, open questions |
| `docs/STYLE.md` §8 | Before writing or moving any doc, result or finding |
| `docs/TRIED.md` | Before proposing a flag, engine, quant or setting: it may already have lost |
| `docs/DECISIONS.md` | Before changing the profile, `models.toml` or a documented policy |
| `docs/sop/` | Launching, adding a model, updating the engine, measuring a backend, power cap, syncing GitHub info after a push |
| `docs/measurements/<topic>.md` | Detailed evidence behind a number in STATUS |

## Repository rules

- Chat replies follow the user's language; every file in this repository is English (code,
  comments, docs, CLI help, program output, commit messages).
- Publish only what another RX 7900 XTX owner can reuse or verify: config, launcher, benchmark
  scripts, and write-ups with pinned versions and reproducible commands. Personal machine paths
  and one-off notes stay local (`odd/`, `_tmp/` and `local*.toml` are git-ignored).
- `models.toml` is the single source of truth for models, profiles, sampling and flags;
  `local.toml` (from `local.example.toml`) holds `models_root` and the engine binaries.
- `CLAUDE.md` is a symlink: edit `AGENTS.md`.
- Python 3.11+, standard library only, except `scripts/gguf_info.py` (`gguf`) and optional PyYAML
  for YAML harness targets in `scripts/check-sync.py`. Use `python3`.
- Engine builds are single-backend: one Vulkan binary and one ROCm/HIP binary. A build with both
  routes MTP to ROCm0 and disables it (llama.cpp #23199).

## Commands

- Launch: `python3 scripts/launch.py [alias] [--profile P] [--dry-run] [--background]`. Every
  launch logs to `_tmp/logs/`; read the newest log before analyzing a session.
- Cache reuse per request: `python3 scripts/cache_misses.py _tmp/logs/<log>`.
- Manifest check: `python3 scripts/check-sync.py`. Smoke test: `python3 scripts/smoke.py <alias>`.
- GGUF metadata: `python3 scripts/gguf_info.py <path-or-folder>`.
- Done means both pass: `python3 scripts/check-repo.py` and
  `python3 -m unittest discover -s tests` (stdlib, no GPU, server or network). CI runs the same.

## Model and flag rules

- **Check the vendor's model card on Hugging Face before configuring a model**, even when another
  quant of it is already configured: sampling, native context, thinking format and variant
  requirements come from there. The card's sampling wins over `general.sampling.*` in the GGUF and
  over values copied from another model (that has gone wrong twice). If card and GGUF disagree,
  follow the card and note the discrepancy in the config comment.
- Set only what the vendor states. A key the card doesn't mention (e.g. `top_p`) stays unset.
  Reasoned exception: `--min-p 0.0`, because llama.cpp defaults to `0.05` and vendors test
  without min-p.
- A flag belongs in the config only if it changes the default of **the exact binary you will
  run**: check its `--help` (defaults drift between llama.cpp versions and between backends), and
  verify every flag there before copying it from another build.
- Thinking: leave `--reasoning-format` at its default `auto`. Add `--reasoning-budget` only after
  observing empty `content` with `finish_reason: length`.
- `-c` matches the context window the harness expects for that provider; recompute per model with
  `--fit on --fit-target <N>`.
- Quantized KV (`q8_0`, `q4_0` or the mixed pairs the engine supports) is the default policy;
  re-verify parity against `f16` per backend.
- A config is good when real inference works, not when the model loads.
- Measure `--mlock` before using it: it has been reported to freeze a Windows host under memory
  pressure (MoE model, small-VRAM card).

## Evidence discipline

- A research subagent's summary is a hypothesis. Verify each citation against the primary source
  before recording it as established; an agent once attributed claims to llama.cpp issues that
  did not say them.
- If a measurement in `docs/` contradicts what you observe, re-measure before building on it; a
  stale number has supported a wrong recommendation before.
- If a request conflicts with a rule here, say so and propose the alternative.
- When the user corrects a behavior that a rule should have prevented, fix the rule here or in
  `docs/STYLE.md` in the same change.
- When compacting context, keep: the task file path, commands run with their results, and every
  measured number with its unit and conditions.

## Coding-agent harness (optional)

Wire a harness to exactly one `local-262k` provider (contextWindow 262144) on `[defaults].port`
(8080 if absent); `launch.py` decides which alias is loaded. `check-sync.py` checks this wiring
only when `local.toml` has a `[harness]` table.
