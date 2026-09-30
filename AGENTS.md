# rx7900xtx-local-llm

Config + docs for running long-context LLMs locally on an **AMD Radeon RX 7900 XTX (24 GB,
RDNA3, gfx1100)** via `llama-server`, on Linux (Vulkan/ROCm) and, where noted, on Windows.

**Start here: read `docs/STATUS.md` for the current state** (profile, numbers, flags, open
questions). Doc map: `README.md`; tried and rejected: `docs/TRIED.md`.

**Reply in the user's language in chat; every file in this repository is written in English**
(code, comments, docs, CLI help, program output). See `docs/STYLE.md`.

**Personal machine paths and one-off/exploratory material do not belong here.** Only content
another RX 7900 XTX owner can reuse or verify gets published: config, launcher, benchmark
scripts and measurement write-ups with pinned versions and reproducible commands.

- Requires **Python 3.11+**; scripts use the standard library, except `scripts/gguf_info.py`
  (needs `gguf`) and optional PyYAML for YAML harness targets in `scripts/check-sync.py`.
  Use `python3` everywhere.
- `CLAUDE.md` is a symlink to `AGENTS.md`. Always edit `AGENTS.md`; never touch `CLAUDE.md`.
- `models.toml` is the single source of truth for models, profiles, sampling and flags.
  `local.toml` (git-ignored, from `local.example.toml`) sets `models_root` and per-backend engine
  binaries. Weights are not in the repository.

## Operate

- Launch: `python3 scripts/launch.py <alias> [--profile P] [--dry-run] [--background]` (`docs/sop/`).
- Consistency: `python3 scripts/check-sync.py` (manifest vs. GGUFs, context ≥ 128K, K/V support;
  a backend without an engine in `local.toml` is only a WARNING; an optional `[harness]` table
  also checks the `local-262k` provider).
- Smoke test: `python3 scripts/smoke.py <alias> [--profile P]`.
- GGUF metadata: `python3 scripts/gguf_info.py <path-or-folder>`.
- **Before every push**: `python3 scripts/check-repo.py` (links, files > 1 MiB, personal paths,
  secrets, Spanish leftovers).
- Tests: `python3 -m unittest discover -s tests -v` (stdlib, no GPU/server/network; CI also runs
  `check-repo.py` and `check-sync.py`; see `tests/`).
- New model: `docs/sop/new-model.md`. Engine update or backend choice:
  `docs/sop/update-engine.md`, `docs/sop/measure-backend.md`.
- **Single-backend engine builds only**: one Vulkan binary and one ROCm/HIP binary, **never one
  compiled with both** (llama.cpp #23199: with both, MTP is routed to ROCm0 and ends up disabled).

## Coding-agent harness (optional)

Any harness reading an OpenAI-compatible `baseUrl` + `contextWindow` list should have exactly one
fixed `local-262k` entry (contextWindow 262144) on the configured port (`[defaults].port`, 8080 if
absent); `launch.py` decides which alias is loaded. `check-sync.py` verifies this only when
`local.toml` has a `[harness]` table.

## What still holds, regardless of hardware

- **Always check the vendor's model card on Hugging Face before configuring a model**, even if
  another quant of the same model is already configured. That is where the recommended sampling,
  native context, thinking format and any variant-specific requirement (QAT/instruct/thinking)
  come from. **The vendor's sampling wins** over whatever is baked into the GGUF
  (`general.sampling.*`) and over copying it from another model — that has gone wrong twice.
  **What the vendor doesn't say, don't set.** If the card doesn't mention `top_p`, leave it
  unset (setting it to the binary's default would be a default disguised as a recommendation).
  Reasoned exception: `--min-p 0.0`, because llama.cpp's default is `0.05` and almost no vendor
  tunes for min-p, so turning it off **is** a deliberate change from default that reflects what
  the vendor tested. If the card and the GGUF metadata disagree, the card wins; note the
  discrepancy in the config comment.
- **Only set a flag if it changes something relative to the binary's default.** Check the default
  in `llama-server --help` **of the exact binary you're about to run** — defaults drift between
  llama.cpp versions and between backends (Vulkan vs. ROCm/HIP), so re-verify per engine build.
- **Thinking: do not set `--reasoning-format`.** The default `auto` detects the template's format
  and already returns `reasoning_content` correctly for most models. **`--reasoning-budget` only
  with evidence**, never as a habit: set it where you've actually seen empty `content` with
  `finish_reason: length`.
- **`-c` must match the context window your harness (if any) expects for that provider.** There
  is no universal default: recompute per model with `--fit on --fit-target <N>`, don't guess.
- **Quantized KV** (`q8_0`/`q4_0`, or the mixed K/V combinations your engine build supports) is
  the default policy; re-verify parity against `f16` per backend before trusting it blindly.
- **Never trust that a model "loads"** as proof a config is good: test real inference.
- **`--mlock`**: measure before using it. It has been reported to freeze a Windows host under
  memory pressure with a MoE model on a small-VRAM card; verify on your own hardware first.
- **Verify every flag against the real `--help` of the binary you're using** — never copy a flag
  list from a different engine build or backend without re-checking.

## Lesson learned

**A research subagent's summary is a hypothesis, not a fact** — verify citations against the
primary source before writing them here as established. This has bitten us before: a research
agent attributed a specific claim to upstream llama.cpp issues that, on inspection, did not say
that.

## If something doesn't fit

If a measurement in `docs/` contradicts what you're seeing, re-measure before building on top of
it — a stale number has silently supported a wrong recommendation before. If a request conflicts
with a guardrail in this file, say so and propose the alternative; don't silently work around it.
