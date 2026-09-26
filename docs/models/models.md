# Model table

**Source of truth: `models.toml`** (repo root). This table is a human-readable summary; if it
disagrees with the TOML, the TOML wins.

| Alias | GGUF | Backend | MTP | Profiles |
|---|---|---|---|---|
| `qwen38-iq3s-mtp` | `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` | hip-kvmix | yes | `262k-q8q51-mtp` |

Single model, single profile by design (2026-09-26, `docs/DECISIONS.md`): one best default, no
overlapping alternatives. Other GSQ-RCO/RVN quants that were evaluated and not kept in the
manifest are documented in `docs/models/qwen38-27b-quants.md` for provenance. Add a new
model/profile per `docs/sop/new-model.md`.

`qwen38-iq3s-mtp` uses `mmproj-Qwen3.8-27B-BF16.gguf` (vision projector, disabled in the default
profile) and the official Qwen3.8-27B sampling (`temp 1.0, top_p 0.95, top_k 20, min_p 0.0`) — see
`docs/models/qwen38-27b-quants.md` §2.

`hip-kvmix` is an own build of the official ROCm/HIP llama.cpp that additionally compiles
FlashAttention kernels for the K `q8_0` + V `q5_1`/`q4_1` mix, which the official ROCm binary
doesn't ship (see `docs/ENGINES.md`). ROCm/HIP measures 2-3.5x faster than Vulkan for generation on
this system (see `docs/measurements/engines.md`) — the opposite of what upstream documents for HIP
vs. Vulkan on RDNA in general, and specific to this setup's clock behavior. Vulkan supports every
K/V mix out of the box and stays as a reference/fallback backend.

## Recommended profile

`qwen38-iq3s-mtp` / `262k-q8q51-mtp` is the manifest's only model/profile and
`scripts/launch.py`'s `[defaults]` when no alias is given: fill 240K, quality 68/68 exact match
32K-240K (0 loops), KV q8_0/q5_1, MTP n=3, `-ub 256`, process VRAM peak 22,630 MiB, 0 evicted. See
`docs/STATUS.md` for the exact launch command and `docs/measurements/depth.md` for the full
matrix.

## Harness wiring

A coding-agent harness that reads an OpenAI-compatible provider list (any tool with a `baseUrl` +
`contextWindow` config) can point at one fixed local entry on `:8080`, regardless of which alias
is actually loaded there:

| Provider | contextWindow | When it applies |
|---|---|---|
| `local-262k` | 262144 | profiles with `context >= 262144` (the only wired context today) |

`scripts/launch.py` prints the harness provider for the chosen profile, or that none is wired if
its context isn't 262144. Verify wiring with `python scripts/check-sync.py` (only checked if
`local.toml` has `[harness] enabled = true` — see `AGENTS.md`).

## Operate

See `docs/sop/launch-model.md`, `docs/sop/new-model.md`, `docs/sop/update-engine.md`,
`docs/sop/measure-backend.md` and `docs/sop/install.md`.
