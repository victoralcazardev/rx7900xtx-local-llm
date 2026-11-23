# rx7900xtx-local-llm

**262K-context local LLMs on one AMD Radeon RX 7900 XTX (24 GB, gfx1100)**: validated configs, a
launcher and reproducible benchmark evidence for one card, one server. Several models, engines and
quants side by side. Not a multi-GPU, CUDA, vLLM/Ollama guide.

[![License: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/docs%20license-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![CI](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/victoralcazardev/rx7900xtx-local-llm/actions/workflows/ci.yml)

## Key findings

- **ROCm/HIP, not Vulkan:** generation is 2-3.5x faster here ([engines.md](docs/measurements/engines.md)).
- **262K fits in 24 GB** with quantized KV: paged E4M3 on `maya-ik2`, K `q8_0` + V `q5_1` on
  llama.cpp ([kv-quality.md](docs/measurements/kv-quality.md)).
- **Inkling-2-Mini at depth:** 106.1 / 90.0 / 68.9 tok/s at 512 / 32K / 128K fill, 53.6 at 262K
  ([results](results/20261123-inkling-round/README.md)).
- **Qwen3.8-27B speculation (stock GSQ-RCO quant):** MTP n=3 doubles decode at 240K (23.3 vs. 11.2
  tok/s); an n-gram drafter adds +62% on copying tasks ([speculative.md](docs/measurements/speculative.md)).
- **272 W cap:** ~6% prefill cost, hotspot 7-8°C cooler ([thermals-power.md](docs/measurements/thermals-power.md)).

## Setups

| Model | Quant | Engine | Status | Headline numbers | Owner doc |
|---|---|---|---|---|---|
| Inkling-2-Mini uncensored (Thinking Machines) | `IQ4_NL` experts, Q8_0 head/attention | `maya-ik2` HIP port `hip-port` `f472e94` | In use | 106.1 / 90.0 / 68.9 tok/s at 512 / 32K / 128K fill, 53.6 at 262K; GSM8K 187/192 | [`inkling-2-mini.md`](docs/models/inkling-2-mini.md) |
| Qwen3.8-27B abliterated (huihui-ai) | GSQ-RCO `IQ3_S-mtp` | llama.cpp `hip-kvmix` v0.9.0 + patch | Opt-in | 50.6 / 166.8 / 43.1 tok/s essay/copy/code at 64K fill, 22.12 GiB peak; the 240K, retrieval and coding-suite numbers are the stock quant's | [`qwen38-27b.md`](docs/models/qwen38-27b.md) |
| Qwen3.8-Flash-Next | many published Strata quants | Strata | Runs on one 24 GB card with experts streamed from host RAM/SSD; no set installed here since 2026-11-05 because our sets read the experts from the SSD on a 32 GiB host (2.6-12.8 tok/s), so follow [Strata](https://github.com/Niko1221/Strata)'s latest release, quant list and settings | 59-65 tok/s warm short, 36.7 at 240K (v0.2.8) | [`strata-qwen-flash-next.md`](docs/models/strata-qwen-flash-next.md) |

Pick the alias per task: `python3 scripts/launch.py <alias> --profile <profile>`; with no alias it
falls back to `inkling2-mini-unc-q8d` / `262k-maya`, the setup last in use (not a recommendation).
One engine serves `:8080` at a time. Flags, launch commands and evidence: each owner doc.

## Tested setup

| Component | Spec |
|---|---|
| GPU | AMD Radeon RX 7900 XTX, 24 GB (RDNA3, gfx1100) |
| CPU / RAM | Ryzen 7 5700X (8C/16T), 32 GiB |
| OS / runtime | CachyOS (Arch-based), kernel 7.3.5-2-cachyos, `hip-runtime-amd` 10.1-2.1 (ROCm 10.1 since 2026-11-17; 7.2.4 before); each write-up pins its own versions |
| Engines | `maya-ik2` (Inkling-only HIP port) and llama.cpp v0.9.0 + the `q8_0`/`q5_1` TILE patch (`hip-kvmix`); builds and SHA256 in [`ENGINES.md`](docs/ENGINES.md) |

Every layer runs on the GPU, so CPU and RAM barely matter ([`hardware/`](docs/hardware/gpu-7900xtx.md)).

## Quick start

Requires **Python 3.11+** (stdlib only) and the ROCm runtime. Pick an alias from [Setups](#setups),
then follow its subsection.

**Inkling-2-Mini (`maya-ik2`).** Use the
[`maya-ik2-f472e94-rocm10-gfx1100`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases)
release asset (no ROCm runtime bundled) or build it; tokenizer export and `serve/` requirements:
[`docs/ENGINES.md`](docs/ENGINES.md#maya-inkling-mini-hip-maya-ik2-experimental-inkling-2-mini-only).
Model: Abiray's uncensored `IQ4_NL`, then the Q8_0 re-type of head and non-expert attention (experts
unchanged; the script ships here):

```bash
d=/path/to/Models/Inkling-2-Mini-Uncensored-Abiray   # models_root/... as in local.toml
hf download Abiray/Inkling-2-Mini-Uncensored-GGUF Inkling-2-Mini-Uncensored-IQ4_NL.gguf --local-dir $d
python3 -I results/20261123-inkling-round/raw/retype_q8.py --src $d/Inkling-2-Mini-Uncensored-IQ4_NL.gguf \
  --dst $d-q8dense/Inkling-2-Mini-Uncensored-IQ4_NL-q8dense.gguf
```

**Qwen3.8-27B (`hip-kvmix`).** Take the
[`engine-v0.9.0-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-v0.9.0-rocm10-gfx1100-kvmix)
asset (sha256 in [`docs/ENGINES.md`](docs/ENGINES.md)) and the 12.1 GB abliterated GSQ-RCO GGUF from
[`huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF`](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF),
then `python3 scripts/launch.py huihui-iq3s-mtp --profile 262k-q8q51-mtp`
([`docs/models/qwen38-27b.md`](docs/models/qwen38-27b.md)).

**Configure, check, launch.** Set `models_root` and the `[engines]` folders you use in `local.toml`.

```bash
cp local.example.toml local.toml && $EDITOR local.toml
python3 scripts/check-sync.py          # validate models.toml + local.toml
python3 scripts/launch.py --dry-run    # print the command for the launcher fallback
python3 scripts/launch.py              # serve on http://127.0.0.1:8080 (OpenAI-compatible)
```

The 272 W cap ([`power-cap.md`](docs/sop/power-cap.md)) and no GPU-heavy apps; more in
[`launch-model.md`](docs/sop/launch-model.md).

## Troubleshooting

- **Hang on resume or a frozen desktop**: never suspend with a server running (`launch.py` uses
  `systemd-inhibit`); keep VRAM headroom ([`coexistence.md`](docs/measurements/coexistence.md)).
- **Generation far slower**: a Vulkan or dual-backend binary, or a CPU fallback
  ([`engines.md`](docs/measurements/engines.md), [llama.cpp #23199](https://github.com/ggml-org/llama.cpp/issues/23199)).
- **`400 exceed_context`**: provider and launched context disagree; run `python3 scripts/check-sync.py`
  ([`launch-model.md`](docs/sop/launch-model.md)).

## Credits

Upstream work used here:

| Project / person | Link | What this repository takes |
|---|---|---|
| ggml-org llama.cpp | [llama.cpp](https://github.com/ggml-org/llama.cpp) | Every `hip*` build; PR #30792's `q8_0` KV kernel (Woody-Hu) |
| Project Maya | [project-maya](https://github.com/mw00/project-maya) | `maya-ik2`'s engine family (MIT, "Peasant Smith and the Project Maya contributors") |
| alesha-pro | [maya-inkling-mini](https://github.com/alesha-pro/maya-inkling-mini) | The CUDA original of the port; its tool-call parser |
| GodGMN | [`hip-port`](https://github.com/GodGMN/maya-inkling-mini/tree/hip-port), [`inkling-rdna3`](https://github.com/GodGMN/llama.cpp) | The gfx1100 port; the Inkling-only llama.cpp fork |
| Niko1221 | [Strata](https://github.com/Niko1221/Strata) | The Flash-Next engine |
| ISTA-DASLab | [GSQ-RCO](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF) | GSQ-RCO quants and the RCO method |
| Abiray, OpenUncensored | [GGUF](https://huggingface.co/Abiray/Inkling-2-Mini-Uncensored-GGUF), [LoRA](https://huggingface.co/OpenUncensored/Inkling-2-Mini-Uncensored-LoRA) | The uncensored `IQ4_NL` file and its refusal edit |
| Thinking Machines | [Inkling-2-Mini](https://huggingface.co/thinkingmachines/Inkling-2-Mini) | The model, its card and the `mtp.safetensors` DSpark drafter (rev `b85c3cfa`) tested |
| Qwen | [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | The model and its card |
| huihui-ai | [abliterated](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF) | The Huihui setup's quant |
| Unsloth | [Qwen3.8-Flash-Next-GGUF](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF) | The UD-IQ2_XS Flash-Next set tried and deleted |
| AMD ROCm | [TheRock](https://github.com/ROCm/TheRock) | The ROCm 10 build toolchain |

## Repository layout

```
models.toml  local.example.toml   # models/profiles/flags; per-machine paths (copy to local.toml)
scripts/  bench/  tests/          # launcher, benchmarks, stdlib unittest suite
engine-patches/                  # local llama.cpp patches for scripts/build_engine.py
docs/  results/                   # map below; curated runs in results/INDEX.md
```

## Docs map

| Doc | What it has |
|---|---|
| [`docs/STATUS.md`](docs/STATUS.md) | Setups in use, launch, headline numbers, flags, open questions |
| [`docs/TRIED.md`](docs/TRIED.md), [`docs/DECISIONS.md`](docs/DECISIONS.md) | What was tried and rejected; append-only decision log |
| [`docs/SOURCES.md`](docs/SOURCES.md), [`docs/measurements/`](docs/measurements/) | External claims checked locally; benchmark results by topic |
| [`docs/ENGINES.md`](docs/ENGINES.md), [`docs/models/`](docs/models/), [`docs/hardware/`](docs/hardware/) | Engine builds, model and quant provenance, GPU specs |
| [`docs/BENCHMARK-FORMAT.md`](docs/BENCHMARK-FORMAT.md), [`docs/sop/`](docs/sop/), [`docs/STYLE.md`](docs/STYLE.md) | Method; procedures (launch, new model, engine update, release); rules |

## Contributing

Issues and PRs are welcome: script bugs, docs fixes, or reproducible results from a similar GPU
([`CONTRIBUTING.md`](CONTRIBUTING.md)). Built by **Victor Alcazar** — <https://victoralcazar.com>.
Code is MIT, docs CC BY 4.0 ([`LICENSE`](LICENSE)).
