# Model table

**Source of truth: `models.toml`** (repo root). This table is a human-readable summary; if it
disagrees with the TOML, the TOML wins.

| Alias | GGUF | Backend | MTP | Profiles |
|---|---|---|---|---|
| `qwen38-iq3s-mtp` | `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` | hip / hip-kvmix | yes | `128k-q8q8-mtp`, `262k-q8q8`, `262k-q8q51-mtp`, `224k-q8q8-mtp` |
| `qwen38-iq3s` | `Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf` | hip | no | `128k-q8q8`, `262k-q8q8` |
| `qwen38-iq3xxs-mtp` | `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` | hip | yes | `128k-q8q8`, `262k-q8q8-mtp` (unmeasured, may not fit) |
| `qwen38-rvn-mtp` | `RVN-Q4_K_M-multilingual-mtp.gguf` | hip | yes | `128k-q8q8`, `262k-q8q8-mtp` (unmeasured, may not fit) |

All four share `mmproj-Qwen3.8-27B-BF16.gguf` (vision projector) and the official Qwen3.8-27B
sampling (`temp 1.0, top_p 0.95, top_k 20, min_p 0.0`) — see `docs/models/qwen38-27b-quants.md` §2.

`backend = hip` (ROCm) is the current default: it measures 2-3.5x faster than Vulkan for generation
on this system (see `docs/measurements/engines.md`) — the opposite of what upstream documents for
HIP vs. Vulkan on RDNA in general, and specific to this setup's clock behavior. `hip-kvmix` is an
own build of the same llama.cpp version that additionally compiles FlashAttention kernels for the
K `q8_0` + V `q5_1`/`q4_1` mix, which the official ROCm binary doesn't ship (see `docs/ENGINES.md`).
Vulkan supports every K/V mix out of the box and stays as a reference/fallback backend.

## Recommended profile

`qwen38-iq3s-mtp` / `262k-q8q51-mtp` is the current daily-driver default (`scripts/launch.py`'s
`[defaults]` when no alias is given): fill 240K, quality 8/8 exact (0 loops), KV q8_0/q5_1, MTP
n=3, `-ub 256`, process VRAM peak 22,630 MiB, 0 evicted. `224k-q8q8-mtp` (KV q8_0/q8_0, MTP n=3,
`-ub 512` default) stays as the alternative — fill 221,167, process VRAM peak 22,883 MiB. See
`docs/STATUS.md` for the exact launch command and `docs/measurements/depth.md` for the full
matrix.

## Harness wiring

A coding-agent harness that reads an OpenAI-compatible provider list (any tool with a `baseUrl` +
`contextWindow` config) can point at two fixed local entries on `:8080`, regardless of which alias
is actually loaded there:

| Provider | contextWindow | When it applies |
|---|---|---|
| `local-128k` | 131072 | any profile with `context >= 131072` and `< 262144` |
| `local-262k` | 262144 | profiles with `context >= 262144` |

`scripts/launch.py` prints which of the two to use for the chosen profile. Verify wiring with
`python scripts/check-sync.py` (only checked if `local.toml` has `[harness] enabled = true` — see
`AGENTS.md`).

## Operate

See `docs/sop/launch-model.md`, `docs/sop/new-model.md`, `docs/sop/update-engine.md`,
`docs/sop/measure-backend.md` and `docs/sop/install-day.md`.
