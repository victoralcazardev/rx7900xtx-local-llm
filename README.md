# rx7900xtx-local-llm

**262K-context Qwen3.8-27B on a single AMD Radeon RX 7900 XTX (24 GB)** — `llama.cpp` on ROCm with
MTP speculative decoding. A validated config, launcher and benchmark evidence for one card, one
model and one `llama-server` process. Not a multi-GPU, NVIDIA/CUDA, vLLM/Ollama or harness-wiring
guide.

[![License: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/docs%20license-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![CI](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml)

## Headline

| | |
|---|---|
| Profile | `qwen38-iq3s-mtp` / `262k-q8q51-mtp` (IQ3_S-mtp, KV `q8_0`/`q5_1`, MTP n=3 + `ngram-map-k4v`) |
| Context | 262,144 tokens (native, no YaRN) |
| Speed at 240K fill | 18.6-26.9 tok/s MTP-only (copy 43.9 with n-gram), prefill 380 tok/s |
| Speed, empty context | 68.9 tok/s (37.2 without MTP) |
| VRAM | 22,630 MiB peak process VRAM at 240K fill |
| Quality | 68/68 pooled across configurations (32K-240K); 8/8 on exact adopted flags at 240K |
| Power | 272 W cap (this card's driver minimum; stock 303 W) |

Launch command, flag rationale and open questions: [`docs/STATUS.md`](docs/STATUS.md). Evidence:
[`docs/measurements/`](docs/measurements/), method in [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md).

## Tested setup

| Component | Spec |
|---|---|
| GPU | AMD Radeon RX 7900 XTX, 24 GB (RDNA3, gfx1100), Sapphire PULSE (PCI `1da2:471e`), VBIOS `113-3E4710U-O4O` |
| CPU / RAM | Ryzen 7 5700X (8C/16T), 32 GiB (31.25 GiB usable) plus zram swap |
| Board / storage | Gigabyte B450 AORUS PRO, NVMe (Kingston A2000 500 GB) |
| OS / drivers | CachyOS (Arch-based), kernel 7.2.7, Mesa 26.2.3, ROCm runtime 7.2.4 |
| Engine | llama.cpp b11371 (`99b9548`) `hip-kvmix`, ROCm 10.0.0 compiler (TheRock wheels) |

CPU and RAM barely matter (every layer runs on the GPU); GPU and driver notes:
[`docs/hardware/gpu-7900xtx.md`](docs/hardware/gpu-7900xtx.md).

## Quick start

Requires **Python 3.11+**; `scripts/` use only the standard library.

1. **Engine (required).** Official llama.cpp binaries lack the FlashAttention kernels for K `q8_0`
   + V `q5_1`. Download the prebuilt `hip-kvmix` build from the
   [`engine-b11371-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11371-rocm10-gfx1100-kvmix)
   release (`llama-b11371-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256
   `159d2be7538f0932ae41c787a2e14bf849a796b6597eb0d0e1416393b92a137b`; the ROCm runtime is not
   bundled), or build it (ROCm only, never Vulkan+HIP in one build): [`docs/ENGINES.md`](docs/ENGINES.md).
2. **Model.** Download `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` (12.1 GB) from
   [`ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF)
   (revision not pinned; the original upstream revision was not recorded) into
   `<models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/`, plus
   `mmproj-Qwen3.8-27B-BF16.gguf` in the same folder if you want vision. These are the SHA256s of
   this repository's own copies (HF publishes none), to confirm your download matches what was
   measured. They identify the local files, not an upstream HF revision; that revision cannot be
   recovered from the recorded hashes:

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
6. **Optional, recommended.** Cap power to 272 W permanently
   ([`docs/sop/power-cap.md`](docs/sop/power-cap.md)). System-wide VRAM headroom varies with other
   GPU use; the measured adopted 240K-fill run left 190 MiB free. See
   [`docs/measurements/memory.md`](docs/measurements/memory.md) and close GPU-heavy apps before
   long-context work.

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
avoid GPU-heavy apps; the full fix is a display-only second GPU.
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
<summary>OOM, low VRAM headroom, or degraded long-context quality</summary>

262K + vision + MTP doesn't fit with q8/q8 KV: disable vision or use `q8_0/q5_1`
([`memory.md`](docs/measurements/memory.md)). KV `q4_0/q4_0` has 4x the KLD of q8/q8
([`kv-quality.md`](docs/measurements/kv-quality.md)). Close GPU-heavy apps before long-context work.
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
| [`docs/STATUS.md`](docs/STATUS.md) | Current profile, launch command, headline numbers, flags and why, open questions |
| [`docs/TRIED.md`](docs/TRIED.md) | Everything tried and not adopted, with numbers and evidence |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Append-only decision log |
| [`docs/SOURCES.md`](docs/SOURCES.md) | External claims checked against this repository's measurements |
| [`docs/measurements/`](docs/measurements/) | Benchmark results by topic (engines, kv-quality, memory, coexistence, depth, speculative, thermals-power, concurrency, agent-traffic) |
| [`docs/ENGINES.md`](docs/ENGINES.md), [`docs/ENGINES-EXPERIMENTS.md`](docs/ENGINES-EXPERIMENTS.md), [`docs/hardware/`](docs/hardware/), [`docs/models/`](docs/models/) | Engine builds, prepared engine trials and upstream watchlist, GPU/driver specs (Linux and Windows), model and quant provenance |
| [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md) | How every number was produced |
| [`docs/sop/`](docs/sop/) | Procedures: install, launch, add a model, update the engine, measure a backend, power cap, token ledger |
| [`docs/STYLE.md`](docs/STYLE.md) | Language, units, naming and immutable-evidence rules |
| `scripts/check-repo.py`, `tests/` | Hygiene check and `python3 -m unittest discover -s tests -v` |
| [`CONTRIBUTING.md`](CONTRIBUTING.md), `.github/` | How to contribute, CI, issue and PR templates |

## Upstream

This card's results are also published in community projects:

- [local-ai-registry](https://github.com/0xSero/local-ai-registry) (merged): lab `count()` fix (#132) and the Qwen3.8-27B IQ3_S-mtp 262K recipe for this card, 6/6 gates (#133). Its host launch pins the b11160 build, see [`docs/ENGINES.md`](docs/ENGINES.md).
- [sudoingX/qwen38-mtp #88](https://github.com/sudoingX/qwen38-mtp/pull/88) (open): 262K `q8_0`/`q5_1` row, 37.2 to 68.9 tok/s (+85%) empty context, +109% at 240K fill.

## Contributing

Issues and pull requests are welcome: script bugs, docs fixes, or a reproducible result from the
same or a similar GPU ([`CONTRIBUTING.md`](CONTRIBUTING.md), or the
[share-results form](.github/ISSUE_TEMPLATE/share_results.yml)).

Built by **Victor Alcazar** — <https://victoralcazar.com>. Code (`scripts/`, `bench/`) is MIT;
docs, measurement reports and prose are CC BY 4.0 — see [`LICENSE`](LICENSE).
