# rx7900xtx-local-llm

Run **Qwen3.8-27B with a 262K-token context** on a single **AMD Radeon RX 7900 XTX (24 GB)** with
`llama.cpp` — validated config, launcher and benchmark evidence.

[![License: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/docs%20license-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![CI](https://github.com/valcazar57/rx7900xtx-local-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/valcazar57/rx7900xtx-local-llm/actions/workflows/ci.yml)

## Headline results

`262k-q8q51-mtp` (`-c 262144`, KV `q8_0/q5_1`, MTP n=3, `-ub 256`), 272 W power cap:

| Metric | Value |
|---|---:|
| Generation at 240K fill — essay / copy / code | 24.4 / 26.9 / 18.6 tok/s |
| Prefill at 240K fill | 380 tok/s |
| Peak process VRAM at 240K fill | 22,630 MiB |
| Long-context retrieval quality | 60/60 exact, 32K-240K fill |
| Empty-context generation (single smoke sample) | ~61 tok/s |

Full evidence and method: [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md),
[`docs/measurements/`](docs/measurements/), [`docs/STATUS.md`](docs/STATUS.md).

## Tested setup

| Component | Spec |
|---|---|
| **GPU** | **AMD Radeon RX 7900 XTX, 24 GB (RDNA3, gfx1100)**, reference-class board, VBIOS `113-3E4710U-O4O` |
| **Power cap** | 272 W (stock 303 W) |
| CPU | AMD Ryzen 7 5700X (8C/16T) |
| RAM | 32 GB |
| Motherboard | Gigabyte B450 AORUS PRO |
| Model storage | NVMe (Kingston A2000 500 GB) |
| OS | CachyOS (Arch-based), kernel 7.2.7 |
| Graphics stack | Mesa 26.2.3, ROCm runtime 7.2.4 (distro packages) |
| Engine compiler | ROCm 10.0.0 (TheRock wheels) |
| Engine | llama.cpp b11160 (`70c4e1582`), built with FlashAttention kernels for K `q8_0` + V `q5_1` |
| Scripts | Python 3 stdlib only |

CPU and RAM barely matter here — every layer runs on the GPU; see `docs/hardware/gpu-7900xtx.md`
for the full spec breakdown and driver notes.

## Quick start

1. **Get the model.** Adopted model: Qwen3.8-27B GSQ-RCO IQ3_S-mtp — see "Quick start" details
   and SHA256 below.
2. **Build or download an engine.** Single-backend only (never Vulkan+HIP in the same build) —
   see [`docs/ENGINES.md`](docs/ENGINES.md).
3. **Cap the power to 272 W** — see [`docs/measurements/thermals-power.md`](docs/measurements/thermals-power.md)
   §"Making it permanent".
4. **Configure and launch**:
   ```bash
   cp local.example.toml local.toml   # then edit models_root and [engines] for this machine
   python3 scripts/check-sync.py       # validate the manifest
   python3 scripts/launch.py --dry-run # no alias: loads the current best config (262k-q8q51-mtp)
   python3 scripts/launch.py
   ```
5. **Connect any OpenAI-compatible client** to `http://127.0.0.1:8080`. Optional: an `ia` shell
   wrapper for a shorter command line, and wiring a coding-agent harness — see
   `docs/sop/launch-model.md`.

Requires **Python 3.11+** (stdlib only, no dependencies — `scripts/check-sync.py` and
`scripts/manifest.py` use `tomllib`). Every command above uses `python3`.

### Get the model

[`ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF)
(HF revision not pinned — download the file by name below and verify against the SHA256 here if
you need to confirm your copy matches the one this repository measured against):

| File | SHA256 (local copy) |
|---|---|
| `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` | `58fd826723939933dc86f45b7fe04545cbc2de1c70f6fe2cdd3858c87a98c12f` |
| `mmproj-Qwen3.8-27B-BF16.gguf` | `13cb7bebccbd04afc8f4090cb949ecf8937cdf7377c5799b1a0c594e7c0d3e16` |

These hashes are of this repository's own local copy, not the upstream repo's published checksum
(HF doesn't publish one for this file) — use them to confirm your download matches what this
repository measured against, not as an upstream-signed value.

Expected layout, under whatever `models_root` you set in `local.toml`:
`<models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/<gguf>` — one folder per model, matching the `gguf`
path in `models.toml` (`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf`, plus
`mmproj-Qwen3.8-27B-BF16.gguf` for vision, same folder).

See `docs/models/qwen38-27b-quants.md` for the other candidate quants (IQ3_S, IQ3_XXS-mtp, RVN)
and their provenance.

## The recommended configuration, briefly

- **KV `q8_0/q5_1`**: near-free quality loss and more context in 24 GB than `q8_0/q8_0`.
- **MTP n=3**: +9-11% mean tg over n=2 at the real 190K/240K operating depths.
- **`-ub 256`**: -350 MiB peak process VRAM for a small prefill cost, no generation-speed cost.
- **272 W power cap**: trades ~6% prefill speed for a comfortable thermal margin vs. the 303 W
  factory default.

Full reasoning and evidence: [`docs/STATUS.md`](docs/STATUS.md).

## Troubleshooting

<details>
<summary>Machine hangs on resume after suspend</summary>

Suspending with a model loaded (VRAM full) has been observed to hang the machine. `launch.py`
already wraps the server in `systemd-inhibit`; never suspend with a hand-started server. See
`docs/measurements/coexistence.md`.
</details>

<details>
<summary>Vulkan backend is 2-3.5x slower generating than ROCm</summary>

GPU memory clock drops to 772 MHz under Vulkan generation on this system, ROCm holds 1249 MHz.
Use `backend = "hip"` (default in `models.toml`). See `docs/measurements/engines.md`.
</details>

<details>
<summary>MTP silently disabled, or routed to the wrong device</summary>

A binary compiled with both Vulkan and HIP ([llama.cpp #23199](https://github.com/ggml-org/llama.cpp/issues/23199)).
Use a single-backend binary only — see `docs/ENGINES.md`.
</details>

<details>
<summary>Official ROCm binary rejects a K/V combination (q8_0/q5_1, q8_0/q4_1)</summary>

The official binary ships FlashAttention kernels only for symmetric K/V. Use the `hip-kvmix`
engine (own build with the extra kernels) — see `docs/ENGINES.md`.
</details>

<details>
<summary>OOM while generating at 262K + vision + MTP</summary>

Doesn't fit in 24 GB with q8/q8 KV. Disable vision, or use `q8_0/q5_1` KV — see
`docs/measurements/depth.md` and `docs/measurements/memory.md`.
</details>

<details>
<summary>Quality noticeably degrades at long context</summary>

KV `q4_0/q4_0` has 4x the KLD of q8/q8. Use `q8_0/q8_0` or `q8_0/q5_1` — see
`docs/measurements/kv-quality.md`.
</details>

<details>
<summary>400 exceed_context from your client</summary>

Your harness's provider entry doesn't match the launched profile's real context. Run
`python3 scripts/check-sync.py`; see `docs/sop/launch-model.md`.
</details>

<details>
<summary>The server silently falls back to CPU</summary>

Usually means the ROCm/HIP runtime libraries aren't on the library path for the engine you
configured. Run `llama-server --list-devices` and confirm the GPU is listed before assuming the
config is wrong.
</details>

<details>
<summary>Thin VRAM headroom / random eviction under load</summary>

System-wide VRAM margin depends on what else is using the GPU, not just the profile — close
GPU-heavy applications (video players, browsers with GPU video) before long-context work. See
`docs/measurements/memory.md`.
</details>

<details>
<summary>Official llama.cpp binaries reject q8_0/q5_1 or q8_0/q4_1 FlashAttention</summary>

The official CI binaries only ship FlashAttention kernels for symmetric K/V pairs. Build the
`hip-kvmix` engine yourself with the extra kernels — see `docs/ENGINES.md` for the exact build
flags.
</details>

## What this is (and is NOT)

- **IS**: a single-GPU, single-model local inference setup — one RX 7900 XTX, one `llama-server`
  process, long-context (128K-262K) usage with speculative decoding (MTP).
- **IS**: reproducible — pinned llama.cpp commit and build flags (`docs/ENGINES.md`), a real
  launch command per profile (`models.toml`), and every reported figure linked to its evidence
  (`docs/measurements/`, `results/`).
- **IS NOT** a multi-GPU or datacenter guide — everything here is measured on one card.
- **IS NOT a vLLM/Ollama guide** — this repository only uses `llama-server` from llama.cpp.
- **IS NOT an NVIDIA/CUDA guide** — this repository is 7900 XTX only; NVIDIA/CUDA is out of scope.
- **IS NOT a harness/agent-wiring guide** — connect any OpenAI-compatible client to the fixed
  local endpoint described in `AGENTS.md`; this repository doesn't assume a particular
  coding-agent tool.

## Token usage ledger (optional)

`--metrics` in `[defaults] flags` exposes Prometheus counters at `/metrics` that reset on every
server restart. `scripts/token_ledger.py` samples them on a systemd user timer and keeps an
all-time, restart-proof total in `~/.local/share/llm-usage/ledger.json`:

```bash
python3 scripts/token_ledger.py show
```

Install and details: `docs/sop/token-ledger.md`.

## Repository layout

```
rx7900xtx-local-llm/
├── models.toml              # models, profiles, sampling and flags (source of truth)
├── local.example.toml       # per-machine paths and engine binaries (copy to local.toml)
├── scripts/                 # launcher, manifest validation, repo hygiene, GGUF metadata
├── bench/                   # benchmark scripts (depth, quality, speculative decoding, concurrency)
├── tests/                   # stdlib unittest suite for the pure logic above
├── docs/
│   ├── STATUS.md            # current recommended profile, key figures, open questions
│   ├── DECISIONS.md         # append-only decision log with evidence links
│   ├── SOURCES.md           # external claims checked against this repo's own measurements
│   ├── ENGINES.md           # llama.cpp build inventory: commits, flags, SHA256
│   ├── BENCHMARK-FORMAT.md  # how every number in this repo was produced
│   ├── hardware/            # GPU specs, driver setup
│   ├── models/              # model table and quant provenance
│   ├── measurements/        # benchmark results and conclusions, by topic
│   └── sop/                 # step-by-step procedures (install, launch, add a model, ...)
└── results/                 # curated, small result folders — see results/INDEX.md
```

## Docs map

| Doc | What it has |
|---|---|
| `docs/STATUS.md` | Current recommended profile, key figures, open questions |
| `docs/DECISIONS.md` | Append-only decision log with evidence links |
| `docs/SOURCES.md` | External claims checked against this repository's own measurements |
| `docs/hardware/` | RX 7900 XTX specs, driver setup, install background |
| `docs/models/` | Model table and quant provenance |
| `docs/ENGINES.md` | llama.cpp build inventory: commits, flags, SHA256 |
| `docs/measurements/` | Benchmark results and conclusions, by topic (engines, kv-quality, memory, coexistence, depth, speculative, thermals-power, concurrency) |
| `docs/BENCHMARK-FORMAT.md` | How the numbers are produced and reported |
| `docs/sop/` | Step-by-step procedures: install, launch, add a model, update the engine, token ledger |
| `bench/` | Benchmark scripts that reproduce the numbers in `docs/measurements/` |
| `results/` | Curated, small result folders — see `results/INDEX.md` |
| `scripts/check-repo.py` | Repo hygiene check (broken links, oversized files, personal paths, secrets, Spanish leftovers) — run before every push |
| `tests/` | Stdlib `unittest` unit tests for the launcher's pure logic — `python3 -m unittest discover -s tests -v` |
| `CONTRIBUTING.md` | How to report issues and contribute reproducible results |
| `.github/` | CI workflow and issue/PR templates |

## Contributing & feedback

Issues and pull requests are welcome — whether that's a bug in the scripts, a docs improvement,
or a new result from the same or a similar GPU. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how
to report an issue or contribute a reproducible measurement, and the
[share-results issue form](.github/ISSUE_TEMPLATE/share_results.yml) for a guided way to submit
one.

## Author

Built by **Victor Alcazar** — <https://victoralcazar.com>.

## License

Code (`scripts/`, `bench/`) is MIT licensed. Docs, measurement reports and prose are CC BY 4.0.
See [`LICENSE`](LICENSE).
