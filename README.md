# rx7900xtx-local-llm

**262K-context local LLMs on a single AMD Radeon RX 7900 XTX (24 GB, gfx1100)**: validated configs,
a launcher and benchmark evidence for one card and one serving process at a time, with every
number reproducible. Not a multi-GPU, NVIDIA/CUDA, vLLM/Ollama or harness-wiring guide.

[![License: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/docs%20license-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![CI](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml)

## Models

| Model | Engine | Status | Context | Speed (empty / deep fill) | Setup |
|---|---|---|---|---|---|
| Qwen3.8-27B GSQ-RCO `IQ3_S-mtp` | llama.cpp `hip-kvmix` (ROCm) | **Default** | 262K | 76.3 / 22.5-33.2 tok/s at 240K | [`STATUS.md`](docs/STATUS.md) |
| Qwen4 | — | Planned when released; 27B tuning paused until then | — | — | [`DECISIONS.md`](docs/DECISIONS.md) |
| Nemotron 3.5 Bolt 74B-A9B (24 GB GGUF) | llama.cpp (needs b11718+) | Candidate, not tried | — | — | [`SOURCES.md`](docs/SOURCES.md#ideas-for-future-moe-models-not-pursued-2026-09-29) |

Only one engine serves `:8080` at a time; each needs nearly all of the 24 GB. The Strata Coder is
parked, not installed: [`strata-flash-next.md`](docs/models/strata-flash-next.md#parked-state-2026-10-21).

## Default profile

| | |
|---|---|
| Profile | `qwen38-iq3s-mtp` / `262k-q8q51-mtp` (IQ3_S-mtp, KV `q8_0`/`q5_1`, MTP n=3 + `ngram-map-k4v`) |
| Context | 262,144 tokens (native, no YaRN) |
| Speed at 240K fill | 22.5-33.2 tok/s, copy 54.7 (n-gram), prefill 395 tok/s |
| Speed, empty context | 76.3 tok/s (39.1 without MTP) |
| VRAM | 22,645 MiB peak process VRAM at 240K fill |
| Quality | Retrieval only: 68/68 pooled (32K-240K); 40/40 at 190K/240K; real-history recall holds at 80K/176K |
| Power | 272 W cap (this card's driver minimum; stock 303 W) |

Launch command, flags, open questions: [`docs/STATUS.md`](docs/STATUS.md). Evidence:
[`docs/measurements/`](docs/measurements/), method [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md),
planned trials [`docs/ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md).

## Tested setup

| Component | Spec |
|---|---|
| GPU | AMD Radeon RX 7900 XTX, 24 GB (RDNA3, gfx1100), Sapphire PULSE (PCI `1da2:471e`), VBIOS `113-3E4710U-O4O` |
| CPU / RAM | Ryzen 7 5700X (8C/16T), 32 GiB (31.25 GiB usable) plus zram swap |
| Board / storage | Gigabyte B450 AORUS PRO, NVMe (Kingston A2000 500 GB) |
| OS / drivers | CachyOS (Arch-based), kernel 7.2.11-1-cachyos, Mesa 26.2.4, ROCm runtime 7.2.4 |
| Engine | llama.cpp b11846 + native `q8_0`/`q5_1` TILE FlashAttention patch (`hip-kvmix`), ROCm 10.0.0 compiler; 240K numbers on this page are this build, empty-context numbers b11820 + the same patch ([`docs/ENGINES.md`](docs/ENGINES.md)) |

The default profile runs every layer on the GPU, so CPU and RAM barely matter. GPU and driver notes: [`docs/hardware/gpu-7900xtx.md`](docs/hardware/gpu-7900xtx.md).

## Quick start

Requires **Python 3.11+**; `scripts/` use only the standard library.

1. **Engine (required).** Official llama.cpp binaries lack the FlashAttention kernels for K `q8_0`
   + V `q5_1`. Download the prebuilt `hip-kvmix` build from the
   [`engine-b11846-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11846-rocm10-gfx1100-kvmix)
   release (`llama-b11846-pr30792q51-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256
   `4811e9ff7b02cbfa21e8993f964c5e71c1f0fab6fe4b5631f2e5a6223cc83c76`; the ROCm runtime is not
   bundled), or build it (ROCm only, never Vulkan+HIP in one build): [`docs/ENGINES.md`](docs/ENGINES.md).
2. **Model.** Download `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` (12.1 GB) from
   [`ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF)
   (revision not pinned) into `<models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/`, plus the optional
   `mmproj-Qwen3.8-27B-BF16.gguf` for vision. SHA256s of this repository's copies (HF publishes none):

   | File | SHA256 |
   |---|---|
   | `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` | `58fd826723939933dc86f45b7fe04545cbc2de1c70f6fe2cdd3858c87a98c12f` |
   | `mmproj-Qwen3.8-27B-BF16.gguf` | `13cb7bebccbd04afc8f4090cb949ecf8937cdf7377c5799b1a0c594e7c0d3e16` |

   Other candidate quants and provenance: [`docs/models/qwen38-27b-quants.md`](docs/models/qwen38-27b-quants.md).
3. **Configure.** `cp local.example.toml local.toml`, then set `models_root` and `[engines]`.
4. **Validate and preview.** `python3 scripts/check-sync.py`, then
   `python3 scripts/launch.py --dry-run` (no alias: loads the default profile).
5. **Launch.** `python3 scripts/launch.py`, and point any OpenAI-compatible client at
   `http://127.0.0.1:8080`. Details: [`docs/sop/launch-model.md`](docs/sop/launch-model.md).
6. **Optional, recommended.** Cap power to 272 W ([`docs/sop/power-cap.md`](docs/sop/power-cap.md))
   and close GPU-heavy apps: the 240K-fill run left 190 MiB VRAM free
   ([`docs/measurements/memory.md`](docs/measurements/memory.md)).

## Troubleshooting

<details>
<summary>Machine hangs on resume after suspend</summary>

Suspending with a model loaded (VRAM full) has hung the machine. `launch.py` wraps the server in
`systemd-inhibit`; never suspend with a hand-started server.
[`coexistence.md`](docs/measurements/coexistence.md)
</details>

<details>
<summary>Desktop freezes or drops to the login screen with a model loaded</summary>

The model card also drives the display. When a GPU client can't allocate, the journal shows `Not
enough memory for command submission!` and KWin may quit. Disable browser hardware acceleration and
avoid GPU-heavy apps.
[`coexistence.md`](docs/measurements/coexistence.md)
</details>

<details>
<summary>Generation is 2-3.5x slower than expected, or MTP is off</summary>

Vulkan generates 2-3.5x slower than ROCm here ([`engines.md`](docs/measurements/engines.md)). A
binary compiled with both Vulkan and HIP silently disables MTP
([llama.cpp #23199](https://github.com/ggml-org/llama.cpp/issues/23199)); use a single-backend
binary ([`ENGINES.md`](docs/ENGINES.md)).
</details>

<details>
<summary>Official binaries reject q8_0/q5_1 FlashAttention, or the server falls back to CPU</summary>

Official CI binaries only ship symmetric K/V FlashAttention kernels: use the `hip-kvmix` build.
For CPU fallback, the ROCm/HIP libraries are usually missing from the library path; run
`llama-server --list-devices` and confirm the GPU is listed.
</details>

<details>
<summary>400 exceed_context from your client</summary>

Your harness's provider entry doesn't match the launched context. Run `python3 scripts/check-sync.py`;
see [`docs/sop/launch-model.md`](docs/sop/launch-model.md).
</details>

## Repository layout

```
models.toml           # models, profiles, sampling and flags (source of truth)
local.example.toml    # per-machine paths and engines (copy to git-ignored local.toml)
scripts/  bench/  tests/   # launcher and validation, benchmarks, stdlib unittest suite
docs/                 # see the map below
results/              # curated result folders, see results/INDEX.md
```

## Docs map

| Doc | What it has |
|---|---|
| [`docs/STATUS.md`](docs/STATUS.md) | Current profile, launch command, headline numbers, flag rationale, open questions |
| [`docs/TRIED.md`](docs/TRIED.md) | Everything tried and not adopted, with numbers and evidence |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Append-only decision log |
| [`docs/SOURCES.md`](docs/SOURCES.md) | External claims checked against this repository's measurements |
| [`docs/measurements/`](docs/measurements/) | Benchmark results by topic |
| [`docs/ENGINES.md`](docs/ENGINES.md), [`docs/ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md), [`docs/hardware/`](docs/hardware/), [`docs/models/`](docs/models/) | Engine builds, engine trials and watchlist, GPU/driver specs, model and quant provenance |
| [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md) | How every number was produced |
| [`docs/sop/`](docs/sop/) | Procedures: install, launch, add a model, update the engine, measure, and more |
| [`docs/STYLE.md`](docs/STYLE.md) | Language, units, naming, evidence rules |
| `scripts/check-repo.py`, `tests/`, [`CONTRIBUTING.md`](CONTRIBUTING.md), `.github/` | Hygiene check, unittest suite, contributing guide, CI and templates |

## Contributing

Issues and pull requests are welcome: script bugs, docs fixes, or reproducible results from a
similar GPU ([`CONTRIBUTING.md`](CONTRIBUTING.md), or the
[share-results form](.github/ISSUE_TEMPLATE/share_results.yml)).

Built by **Victor Alcazar** — <https://victoralcazar.com>. Code (`scripts/`, `bench/`) is MIT;
docs, measurement reports and prose are CC BY 4.0 — see [`LICENSE`](LICENSE).
