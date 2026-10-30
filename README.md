# rx7900xtx-local-llm

**262K-context local LLMs on a single AMD Radeon RX 7900 XTX (24 GB, gfx1100)**: validated configs,
a launcher and benchmark evidence for one card and one serving process at a time, with every
number reproducible. Not a multi-GPU, NVIDIA/CUDA, vLLM/Ollama or harness-wiring guide.

[![License: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/docs%20license-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![CI](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml)

## Key findings

- **ROCm/HIP, not Vulkan:** generation is 2-3.5x faster on ROCm here ([engines.md](docs/measurements/engines.md)).
- **MTP is the biggest lever at depth:** n=3 doubles decode at 240K fill (23.3 vs. 11.2 tok/s), and an
  n-gram drafter on top adds +62% when the output copies the context ([speculative.md](docs/measurements/speculative.md)).
- **262K fits in 24 GB with KV `q8_0`/`q5_1`:** near-lossless (KLD 0.000744 vs. `f16`); `q4_0`/`q4_0`
  has 4x the KLD ([kv-quality.md](docs/measurements/kv-quality.md)).
- **A native mixed-KV FlashAttention kernel:** +18-27% decode at 240K over stock llama.cpp, identical
  greedy text ([results](results/20261023-d1-pr30792q51-240k/README.md)).
- **272 W cap:** ~6% slower prefill, hotspot 7-8°C cooler ([thermals-power.md](docs/measurements/thermals-power.md)).

## Models

| Model | Engine | Status | Setup |
|---|---|---|---|
| Qwen3.8-27B GSQ-RCO `IQ3_S-mtp` | llama.cpp `hip-kvmix` (ROCm) | **Default**, numbers below | [`STATUS.md`](docs/STATUS.md) |
| Qwen3.8-Flash-Next IQ2_XS (Coder IQ1_M before 2026-10-30) | Strata v0.2.8 | Optional second engine; installed, coding quality not measured yet | [`strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md#current-state-2026-10-30) |
| Qwen4 | — | Planned when released; 27B tuning paused until then | [`DECISIONS.md`](docs/DECISIONS.md) |

Only one engine serves `:8080` at a time; each needs nearly all of the 24 GB.

## Default profile

| | |
|---|---|
| Profile | `qwen38-iq3s-mtp` / `262k-q8q51-mtp` (IQ3_S-mtp, KV `q8_0`/`q5_1`, MTP n=3 + `ngram-map-k4v`) |
| Context | 262,144 tokens (native, no YaRN) |
| Speed, empty context | **76.3 tok/s** (39.1 without MTP) |
| Speed at 240K fill | **22.5-33.2 tok/s**, copy 54.7 (n-gram), prefill 395 tok/s |
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

Requires **Python 3.11+** (`scripts/` use only the standard library) and the ROCm runtime.

**1. Engine.** Official llama.cpp binaries lack the FlashAttention kernels for K `q8_0` + V `q5_1`,
so use the prebuilt `hip-kvmix` build from the
[`engine-b11846-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11846-rocm10-gfx1100-kvmix)
release (ROCm runtime not bundled), or build it yourself, ROCm only: [`docs/ENGINES.md`](docs/ENGINES.md).

```bash
f=llama-b11846-pr30792q51-rocm10-gfx1100-kvmix-linux-x64.tar.gz
curl -LO https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/download/engine-b11846-rocm10-gfx1100-kvmix/$f
echo "4811e9ff7b02cbfa21e8993f964c5e71c1f0fab6fe4b5631f2e5a6223cc83c76  $f" | sha256sum -c
tar -xzf $f   # note the folder that holds llama-server
```

**2. Model** (12.1 GB, from
[`ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF),
revision not pinned; other quants: [`qwen38-27b-quants.md`](docs/models/qwen38-27b-quants.md)).

```bash
d=/path/to/Models/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp   # models_root/... as in local.toml
hf download ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf --local-dir $d
```

<details>
<summary>SHA256 of this repository's copies (HF publishes none), and the optional vision projector</summary>

| File | SHA256 |
|---|---|
| `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` | `58fd826723939933dc86f45b7fe04545cbc2de1c70f6fe2cdd3858c87a98c12f` |
| `mmproj-Qwen3.8-27B-BF16.gguf` (vision, off in the default profile) | `13cb7bebccbd04afc8f4090cb949ecf8937cdf7377c5799b1a0c594e7c0d3e16` |
</details>

**3. Configure, check, launch.** In `local.toml` set `models_root` and `[engines] hip-kvmix` to the
folder that holds `llama-server`.

```bash
cp local.example.toml local.toml && $EDITOR local.toml
python3 scripts/check-sync.py          # validate models.toml + local.toml
python3 scripts/launch.py --dry-run    # print the command for the default profile
python3 scripts/launch.py              # serve on http://127.0.0.1:8080 (OpenAI-compatible)
```

Details: [`docs/sop/launch-model.md`](docs/sop/launch-model.md). Recommended: cap power to 272 W
([`power-cap.md`](docs/sop/power-cap.md)) and close GPU-heavy apps; the 240K-fill run left 190 MiB
VRAM free ([`memory.md`](docs/measurements/memory.md)).

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
