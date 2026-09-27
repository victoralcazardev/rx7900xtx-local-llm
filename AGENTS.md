# rx7900xtx-local-llm

Config + docs for running long-context LLMs locally on an **AMD Radeon RX 7900 XTX (24 GB,
RDNA3, gfx1100)** via `llama-server`, on Linux (Vulkan/ROCm) and, where noted, on Windows.

**Reply in the user's language in chat; every file in this repository is written in English**
(code, comments, docs, CLI help, program output). See `docs/STYLE.md` for the full language
and number-format rules.

**Personal machine paths and one-off/exploratory material do not belong here.** Only content
another RX 7900 XTX owner can reuse or verify gets published: config, launcher, benchmark
scripts and measurement write-ups with pinned versions and reproducible commands.

- Requires **Python 3.11+**. The scripts otherwise use the standard library; exceptions:
  `scripts/gguf_info.py` requires the third-party `gguf` package (`python3 -m pip install gguf`),
  and PyYAML is optional for YAML-format harness targets in `scripts/check-sync.py`
  (`python3 -m pip install pyyaml`). `tomllib` is in the standard library starting with Python
  3.11. Every command below uses `python3`.
- `CLAUDE.md` is a symlink to `AGENTS.md`. Always edit `AGENTS.md`; never touch `CLAUDE.md`
  directly.
- `models.toml` (repo root) is the single source of truth for models, profiles, sampling and
  flags. `local.toml` (git-ignored, copy from `local.example.toml`) fixes `models_root` and
  the engine binary path per backend, for this machine.
- Weights are **not** in this repository (no GGUF is tracked). Point `models_root` in your
  `local.toml` at wherever you keep them.

## Operate

- **Launch a model**: `python3 scripts/launch.py <alias> [--profile P] [--dry-run]
  [--background]`. Prints the resulting command. Detail: `docs/sop/`.
- **Check the manifest is internally consistent**: `python3 scripts/check-sync.py`. Validates
  every model/profile in `models.toml` (GGUF path present, context ≥ 128K, K/V combination
  supported by the backend). A backend with no engine configured in `local.toml` is only a
  WARNING; anything else fails the exit code. Optionally, if `local.toml` has a `[harness]`
  table, it also checks that your own coding-agent harness has exactly one `local-262k` provider
  (contextWindow 262144) pointing at the configured `[defaults].port` (8080 if absent) — see below.
- **Smoke-test a model/profile**: `python3 scripts/smoke.py <alias> [--profile P]` — starts
  the server, waits for `/health`, sends one real chat request, and kills the server.
- **GGUF metadata**: `python3 scripts/gguf_info.py <path-or-folder>` — architecture, native
  context, KV cost per layer, vision/audio, MTP heads, thinking format, vendor-recommended
  sampling, read straight from the GGUF header (no tensors loaded).
- **Add a new model**: `docs/sop/new-model.md`.
- **Update the engine (Vulkan/ROCm) or decide a model's backend**:
  `docs/sop/update-engine.md` and `docs/sop/measure-backend.md`.
- **Single-backend engine builds only**: one Vulkan binary and one ROCm/HIP binary, **never
  one compiled with both** (upstream llama.cpp issue #23199: with both backends compiled in,
  MTP gets routed to ROCm0 and ends up disabled).
- **Repo hygiene, run before every push**: `python3 scripts/check-repo.py`. Stdlib only; checks
  every tracked file for broken relative Markdown links, files over 1 MiB, personal absolute
  paths, secret-looking strings and Spanish-language leftovers (see `docs/STYLE.md` §1 for the
  deliberate-Spanish exception it honors).
- **Unit tests**: `python3 -m unittest discover -s tests -v`. Uses stdlib `unittest`; covers
  `scripts/manifest.py` (loading/discovery/resolve/validate), `scripts/check-sync.py`
  (harness URL/port matching), `scripts/check-repo.py` (content scanning),
  `scripts/token_ledger.py` (metrics parsing, delta accumulation, persistence),
  `bench/depth_bench.py`, `bench/concurrency_bench.py`, and
  `bench/longctx_quality.py` (`--variants` parsing, monitor-abort exception handling). No server,
  GPU or network access.

## Coding-agent harness (optional)

If you drive this server from a coding-agent harness (any tool that reads an OpenAI-compatible
`baseUrl` + `contextWindow` provider list), wire it to exactly one fixed entry pointing at
the configured `[defaults].port` (8080 if absent) — `local-262k` (contextWindow 262144) — and let
`launch.py` decide which alias/profile is actually loaded there, instead of adding one entry per
model. `check-sync.py` can verify this
wiring, but it is off by default: this repository doesn't assume you use any particular harness.
Enable it locally with a `[harness]` table in your git-ignored `local.toml` (see
`local.example.toml`).

## What still holds, regardless of hardware

- **Always check the vendor's model card on Hugging Face before configuring a model**, even if
  another quant of the same model is already configured. That is where the recommended
  sampling, native context, thinking format and any variant-specific requirement (QAT/instruct/
  thinking) come from. **The vendor's sampling wins** over whatever is baked into the GGUF
  (`general.sampling.*`) and over copying it from another model — that has gone wrong twice.
  **What the vendor doesn't say, don't set.** If the card doesn't mention `top_p`, leave it
  unset (setting it to the binary's default would just be a default disguised as a
  recommendation). Reasoned exception: `--min-p 0.0`, because llama.cpp's default is `0.05` and
  almost no vendor tunes for min-p, so turning it off **is** a deliberate change from default
  that reflects what the vendor actually tested. If the card and the GGUF metadata disagree,
  the card wins; note the discrepancy in the config comment.
- **Only set a flag if it changes something relative to the binary's default.** Check the
  default in `llama-server --help` **of the exact binary you're about to run** — defaults
  drift between llama.cpp versions and between backends (Vulkan vs. ROCm/HIP), so re-verify
  per engine build, don't assume a value carries over.
- **Thinking: do not set `--reasoning-format`.** The default `auto` detects the template's
  format and already returns `reasoning_content` correctly for most models.
  **`--reasoning-budget` only with evidence**, never as a habit: set it where you've actually
  seen empty `content` with `finish_reason: length`, never by default.
- **`-c` must match the context window your harness (if any) expects for that provider.**
  There is no universal default: recompute per model with `--fit on --fit-target <N>` instead
  of guessing.
- **Quantized KV** (`q8_0`/`q4_0`, or the mixed K/V combinations your engine build supports) is
  the default policy; re-verify parity against `f16` per backend before trusting it blindly.
- **Never trust that a model "loads"** as proof a config is good: test real inference.
- **`--mlock`**: measure before using it. It has been reported to freeze a Windows host under
  memory pressure with a MoE model on a small-VRAM card; verify on your own hardware before
  relying on it.
- **Verify every flag against the real `--help` of the binary you're using** before using it —
  never copy a flag list from a different engine build or a different backend without
  re-checking.

## Lesson learned

**A research subagent's summary is a hypothesis, not a fact** — verify citations against the
primary source before writing them here as established. This has bitten us before: a research
agent attributed a specific claim to upstream llama.cpp issues that, on inspection, did not
say that.

## If something doesn't fit

If a measurement in `docs/` contradicts what you're seeing, re-measure before building on top
of it — a stale number has silently supported a wrong recommendation before. If a request
conflicts with a guardrail in this file, say so and propose the alternative; don't silently
work around it.

## Docs

See the "Docs map" table in `README.md` for what every doc has. A few pointers specific to working
as an agent in this repository: `scripts/check-repo.py` (run before every push, see "Operate"
above), `docs/sop/` (step-by-step procedures — launch, add a model, update the engine, install day),
and the "Lesson learned" and "If something doesn't fit" sections above.
