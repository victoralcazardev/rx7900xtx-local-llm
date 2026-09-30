# rx7900xtx-local-llm

**262K-context Qwen3.8-27B on a single AMD Radeon RX 7900 XTX (24 GB)** — `llama.cpp` on ROCm,
IQ3_S-mtp + MTP n=3, KV `q8_0`/`q5_1`, `-ub 256`, 272 W power cap. 18.6-26.9 tok/s at 240K fill,
68/68 exact-match retrieval — validated config, launcher and benchmark evidence.

[![License: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/docs%20license-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![CI](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml)

## Final configuration

`qwen38-iq3s-mtp` / `262k-q8q51-mtp` — the single model/profile this repository ships (one best
default, no overlapping alternatives, see `docs/DECISIONS.md`):

| Component | Value |
|---|---|
| Model | Qwen3.8-27B, ISTA-DASLab GSQ-RCO |
| Weights | `IQ3_S-mtp` (native MTP head baked in), 12.1 GB, PPL 6.734 ± 0.084 |
| Context | 262,144 tokens (native, no YaRN) |
| KV cache | K `q8_0` / V `q5_1`, FlashAttention |
| Speculative decoding | Built-in MTP head, 3 draft tokens (`--spec-draft-n-max 3`) |
| Physical batch | `-ub 256` |
| Slots | 1 (`-np 1`) |
| Engine | llama.cpp b11160 `hip-kvmix` (ROCm 10.0.0 compiler, system ROCm 7.2.4 runtime, own FlashAttention kernels for K `q8_0` + V `q5_1`) |
| Power cap | 272 W (this card's driver minimum; factory default 303 W) |
| Sampling | `temp 1.0`, `top-p 0.95`, `top-k 20`, `min-p 0.0` — per the Qwen3.8-27B card |
| Reasoning effort | medium |

Exact launch command (`scripts/launch.py --dry-run`'s output for the default, model path replaced
with a placeholder):

```bash
llama-server -m <models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
  --port 8080 -c 262144 -ctk q8_0 -ctv q5_1 \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  -fa on -np 1 --ctx-checkpoints 4 -ngl all --metrics \
  --spec-type draft-mtp --spec-draft-n-max 3 -ub 256 --reasoning-effort medium
```

### Results at 240K fill

| Metric | Value |
|---|---:|
| Generation at 240K fill — essay / copy / code | 24.4 / 26.9 / 18.6 tok/s (mean 23.3) |
| Prefill at 240K fill | 380 tok/s |
| Peak process VRAM at 240K fill | 22,630 MiB |
| Long-context retrieval quality | 68/68 exact, 32K-240K fill |
| Empty-context generation (community `probe.py`, 3 passes) | 68.9 tok/s (37.2 without MTP) |
| Generation at 240K fill without MTP (same flags) | 11.2 tok/s (MTP n=3: +109%) |

Full evidence and method: [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md),
[`docs/measurements/`](docs/measurements/), [`docs/STATUS.md`](docs/STATUS.md).

### Flags explained

| Flag | Value | Why |
|---|---|---|
| `-c` | `262144` | Full native context of Qwen3.8-27B; matches the harness's wired `local-262k` provider — [`AGENTS.md`](AGENTS.md) |
| `-ctk` / `-ctv` | `q8_0` / `q5_1` | `q8_0/q8_0` is near-free (KLD 0.000587 vs. f16); `q5_1` on V costs +27% KLD but fits the full 262K in 24 GB — [`docs/measurements/kv-quality.md`](docs/measurements/kv-quality.md) |
| `-fa on` | on | Mandatory with a quantized V cache; also prevents a KV combo silently falling back to a slow path if a kernel is missing — [`docs/measurements/engines.md`](docs/measurements/engines.md) |
| `--spec-type draft-mtp` | `draft-mtp` | Uses the MTP head already baked into the GGUF instead of a separate draft model — [`docs/models/qwen38-27b-quants.md`](docs/models/qwen38-27b-quants.md) |
| `--spec-draft-n-max 3` | `3` | Wins across essay/copy/code at the real 190K/240K operating depths (+9-11% mean tg vs. n=2); n=4/n=5 lose acceptance — [`docs/measurements/speculative.md`](docs/measurements/speculative.md) |
| `-ub 256` | `256` | -350 MiB peak process VRAM vs. the 512 default, -5% prefill cost, no generation-speed cost — [`docs/measurements/memory.md`](docs/measurements/memory.md) |
| `-np 1` | `1` | Single user; 1 slot + MTP with request queuing beats adding `-np` slots end-to-end — [`docs/measurements/concurrency.md`](docs/measurements/concurrency.md) |
| `--ctx-checkpoints 4` | `4` | b11160 default is 32; kept at 4 to bound RAM (measured 270-515 MiB each at 31K-93K tokens; the oldest is evicted first, so a new context re-processes the harness base prompt once: ~42 s at ~32K tokens, ~14.5K tokens since a harness update, see [`docs/measurements/agent-traffic.md`](docs/measurements/agent-traffic.md)) — warm turns still reuse ~all KV in practice (e.g. 189,467 of 190,000 tokens on a task switch) — [`docs/measurements/memory.md`](docs/measurements/memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29), [`docs/measurements/engines.md`](docs/measurements/engines.md), [`docs/measurements/speculative.md`](docs/measurements/speculative.md) |
| `-ngl all` | `all` | All layers on GPU (explicit, not left to `auto`) |
| `--temp`/`--top-p`/`--top-k`/`--min-p` | `1.0`/`0.95`/`20`/`0.0` | The Qwen3.8-27B card's own recommended sampling — nothing invented, `min-p` set explicitly since the binary's default (0.05) isn't what the vendor tested — [`AGENTS.md`](AGENTS.md) |
| `--reasoning-effort medium` | `medium` | The card's template default is `xhigh`, which injects "think carefully, validate assumptions, consider alternatives" and tends to overthink; `medium` adds no extra instruction — `models.toml` |
| `--metrics` | on | Exposes `/metrics` for the persistent token usage ledger — `docs/sop/token-ledger.md` |

## What we tested

Backend (ROCm/HIP beats Vulkan 2-3.5x on generation), toolchain, weight and KV quantization,
speculative decoding, context ladder, concurrency, power cap and rejected flags/forks are all
listed with numbers and evidence links in [`docs/TRIED.md`](docs/TRIED.md).

## Tested setup

| Component | Spec |
|---|---|
| **GPU** | **AMD Radeon RX 7900 XTX, 24 GB (RDNA3, gfx1100)** — Sapphire PULSE (PCI `1da2:471e`), VBIOS `113-3E4710U-O4O` |
| **Power cap** | 272 W (stock 303 W) |
| CPU | AMD Ryzen 7 5700X (8C/16T) |
| RAM | 32 GiB (31.25 GiB usable after firmware/kernel reservations), plus zram swap |
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

1. **Get the model** (Qwen3.8-27B GSQ-RCO IQ3_S-mtp, 12.1 GB) — file, SHA256 and folder layout in
   [Get the model](#get-the-model) below.
2. **Get the engine (required).** The official llama.cpp binaries lack the FlashAttention kernels
   for K `q8_0` + V `q5_1`. Fast path: download the prebuilt `hip-kvmix` build from the
   [`engine-b11160-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11160-rocm10-gfx1100-kvmix)
   release (`llama-b11160-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256
   `f1cb8e2683c94cc5891a11af7876058d50e2c0556f0ffeb92d2451bf659fc3ec`; check with `sha256sum`;
   the ROCm runtime is not bundled). Or build it yourself (ROCm-only, never Vulkan+HIP in one
   build): recipe in [`docs/ENGINES.md`](docs/ENGINES.md).
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

## Tech stack

- **Inference engine**: [`llama.cpp`](https://github.com/ggml-org/llama.cpp)'s `llama-server`, an
  OpenAI-compatible API on `127.0.0.1:8080`.
- **GPU backend**: ROCm/HIP, with an own `hip-kvmix` build for the asymmetric KV FlashAttention
  kernels the official binary doesn't ship.
- **Speculative decoding**: MTP (multi-token prediction), the head baked into the GGUF — no
  separate draft model.
- **Weights and KV cache**: GGUF IQ-quants for the weights, quantized KV cache (`q8_0`/`q5_1`).
- **Scripts**: Python 3, standard library only (launcher, manifest validation, benchmarks).
- **Power and telemetry**: `systemd` (permanent power-cap unit, token-usage-ledger timer).
- **Clients**: any OpenAI-compatible coding-agent harness (e.g. `omp`, `pi`) — this repository
  doesn't assume a particular one.

## Troubleshooting

<details>
<summary>Machine hangs on resume after suspend</summary>

Suspending with a model loaded (VRAM full) has been observed to hang the machine. `launch.py`
already wraps the server in `systemd-inhibit`; never suspend with a hand-started server. See
`docs/measurements/coexistence.md`.
</details>

<details>
<summary>Desktop freezes or drops back to the login screen with a model loaded</summary>

The card that runs the model also drives the display. At 262K there is ~1.2 GiB of VRAM left for
the desktop; when a GPU client can't allocate, the journal shows `Not enough memory for command
submission!` and KWin may quit (`We are going to quit KWin now as it is broken`), ending the
session. Disable browser hardware acceleration and avoid GPU-heavy apps while the model is loaded;
the complete fix is a display-only second GPU. See `docs/measurements/coexistence.md`.
</details>

<details>
<summary>Vulkan backend is 2-3.5x slower generating than ROCm</summary>

GPU memory clock drops to 456-772 MHz under Vulkan generation on this system, ROCm holds 1249 MHz.
Pinning it fixes most of Vulkan's collapse at depth, but HIP still wins by 18-63% on tg.
Use HIP (the adopted profile uses the own `hip-kvmix` build). See `docs/measurements/engines.md`.
</details>

<details>
<summary>MTP silently disabled, or routed to the wrong device</summary>

A binary compiled with both Vulkan and HIP ([llama.cpp #23199](https://github.com/ggml-org/llama.cpp/issues/23199)).
Use a single-backend binary only — see `docs/ENGINES.md`.
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

<details>
<summary>What this is (and is NOT)</summary>

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
</details>

<details>
<summary>Token usage ledger (optional)</summary>

`--metrics` in `[defaults] flags` exposes Prometheus counters at `/metrics` that reset on every
server restart. `scripts/token_ledger.py` samples them on a systemd user timer and keeps an
all-time, restart-proof total in `~/.local/share/llm-usage/ledger.json`:

```bash
python3 scripts/token_ledger.py show
```

Install and details: `docs/sop/token-ledger.md`.
</details>

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
│   ├── models/               # model table and quant provenance
│   ├── measurements/        # benchmark results and conclusions, by topic
│   └── sop/                 # step-by-step procedures (install, launch, add a model, ...)
└── results/                 # curated, small result folders — see results/INDEX.md
```

## Docs map

| Doc | What it has |
|---|---|
| `docs/STATUS.md` | Current recommended profile, key figures, open questions |
| `docs/TRIED.md` | Everything tried and not adopted, with numbers and evidence links |
| `docs/DECISIONS.md` | Append-only decision log with evidence links |
| `docs/SOURCES.md` | External claims checked against this repository's own measurements |
| `docs/hardware/`, `docs/models/`, `docs/ENGINES.md` | GPU/driver specs, model/quant provenance, llama.cpp build inventory |
| `docs/measurements/` | Benchmark results and conclusions, by topic (engines, kv-quality, memory, coexistence, depth, speculative, thermals-power, concurrency, agent-traffic) |
| `docs/BENCHMARK-FORMAT.md` | How the numbers are produced and reported |
| `docs/STYLE.md` | English, units, naming, formatting, immutable-evidence rules, and documentation conventions |
| `docs/sop/` | Step-by-step procedures: install, launch, add a model, update the engine, measure a backend, token ledger |
| `scripts/check-repo.py`, `tests/` | Repo hygiene check and the stdlib `unittest` suite — `python3 -m unittest discover -s tests -v` |
| `CONTRIBUTING.md`, `.github/` | How to contribute, and the CI workflow / issue-PR templates |

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
