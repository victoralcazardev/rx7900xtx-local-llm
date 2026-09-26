# rx7900xtx-local-llm

Config, launcher and benchmark scripts for running long-context LLMs locally on a single **AMD
Radeon RX 7900 XTX (24 GB, RDNA3, gfx1100)**, on Linux with ROCm/HIP or Vulkan, via `llama-server`
(llama.cpp). Pinned engine builds, reproducible measurements, and a curated `results/` folder —
see `docs/BENCHMARK-FORMAT.md` for how every number here was produced.

Requires **Python 3.11+** (stdlib only, no dependencies — see `AGENTS.md`). Every command below
uses `python3`.

## What this is (and is NOT)

- **IS**: a single-GPU, single-model local inference setup — one RX 7900 XTX, one `llama-server`
  process, long-context (128K-262K) usage with speculative decoding (MTP).
- **IS**: reproducible — pinned llama.cpp commit and build flags (`docs/ENGINES.md`), a real launch
  command per profile (`models.toml`), and every reported figure linked to its evidence
  (`docs/measurements/`, `results/`).
- **IS NOT** a multi-GPU or datacenter guide — everything here is measured on one card.
- **IS NOT a vLLM/Ollama guide** — this repository only uses `llama-server` from llama.cpp.
- **IS NOT an NVIDIA/CUDA guide** — this repository is 7900 XTX only; NVIDIA/CUDA is out of scope.
- **IS NOT a harness/agent-wiring guide** — connect any OpenAI-compatible client to the fixed
  local endpoint described in `AGENTS.md`; this repository doesn't assume a particular coding-agent
  tool.

## The default profile

`models.toml` ships a single model and profile, `qwen38-iq3s-mtp` / `262k-q8q51-mtp` (the one
`scripts/launch.py` loads with no alias): 262,144 context, KV `q8_0/q5_1`, MTP n=3, `-ub 256`,
vision disabled — **18.6-26.9 tok/s at 240K fill**. See `docs/STATUS.md` for the exact command and
key figures, and [`measurements/depth.md`](docs/measurements/depth.md) for the full measurement.

## Quick start

### 1. Get the model

Adopted model: **Qwen3.8-27B GSQ-RCO IQ3_S-mtp**, from
[`ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF)
(HF revision not pinned — download the file by name below and verify against the SHA256 here if you
need to confirm your copy matches the one this repository measured against):

| File | SHA256 (local copy) |
|---|---|
| `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` | `58fd826723939933dc86f45b7fe04545cbc2de1c70f6fe2cdd3858c87a98c12f` |
| `mmproj-Qwen3.8-27B-BF16.gguf` | `13cb7bebccbd04afc8f4090cb949ecf8937cdf7377c5799b1a0c594e7c0d3e16` |

These hashes are of this repository's own local copy, not the upstream repo's published checksum
(HF doesn't publish one for this file) — use them to confirm your download matches what this
repository measured against, not as an upstream-signed value.

Expected layout, under whatever `models_root` you set in `local.toml` (see step 3):
`<models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/<gguf>` — one folder per model, matching the `gguf`
path in `models.toml` (`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf`, plus
`mmproj-Qwen3.8-27B-BF16.gguf` for vision, same folder).

See `docs/models/qwen38-27b-quants.md` for the other candidate quants (IQ3_S, IQ3_XXS-mtp, RVN) and
their provenance.

### 2. Get an engine

Build or download a **single-backend** llama.cpp binary (never Vulkan+HIP in the same build — see
`docs/ENGINES.md` for why). Pinned commits, build flags and SHA256 for every engine used in this
repository's measurements are in `docs/ENGINES.md`.

### 3. Cap the power to 272 W

Every headline number in this repository (tok/s, VRAM, thermals) was measured under a 272 W power
cap, not the card's factory 303 W default — at 303 W the same 190K-fill prefill runs about 6%
faster but the hotspot reaches up to 106°C, vs. 98-99°C at 272 W. Install the cap once, at boot, via
the systemd unit tracked in this repository: `docs/measurements/thermals-power.md` §"Making it
permanent".

### 4. Configure and launch

```bash
cp local.example.toml local.toml   # then edit models_root and [engines] for this machine
python3 scripts/check-sync.py       # validate the manifest
python3 scripts/launch.py --dry-run # no alias: loads the current best config (262k-q8q51-mtp)
python3 scripts/launch.py
```

Then connect any OpenAI-compatible client to `http://127.0.0.1:8080`. To load a different
model/profile instead of the default, pass them explicitly:
`python3 scripts/launch.py <alias> --profile <profile>` (see `docs/models/models.md` for what's
in the manifest). Full walkthrough: `docs/sop/launch-model.md`, which also covers the optional
`ia` shell wrapper for a shorter command line.

## Token usage ledger

`--metrics` in `[defaults] flags` exposes Prometheus counters at `/metrics` that reset on every
server restart. `scripts/token_ledger.py` samples them on a systemd user timer and keeps an
all-time, restart-proof total in `~/.local/share/llm-usage/ledger.json`:

```bash
python3 scripts/token_ledger.py show
```

Install and details: `docs/sop/token-ledger.md`.

## Failure cards

| Symptom | Cause | Fix |
|---|---|---|
| Machine hangs on resume after suspend | Suspending with a model loaded and VRAM full | `launch.py` already wraps the server in `systemd-inhibit`; never suspend with a hand-started server. See `docs/measurements/coexistence.md`. |
| Vulkan backend is 2-3.5x slower generating than ROCm | GPU memory clock drops to 772 MHz under Vulkan generation on this system, ROCm holds 1249 MHz | Use `backend = "hip"` (default in `models.toml`). See `docs/measurements/engines.md`. |
| MTP silently disabled, or routed to the wrong device | A binary compiled with both Vulkan and HIP ([llama.cpp #23199](https://github.com/ggml-org/llama.cpp/issues/23199)) | Use a single-backend binary only — see `docs/ENGINES.md`. |
| Official ROCm binary rejects a K/V combination (`q8_0/q5_1`, `q8_0/q4_1`) | The official binary ships FlashAttention kernels only for symmetric K/V | Use the `hip-kvmix` engine (own build with the extra kernels) — see `docs/ENGINES.md`. |
| OOM while generating at 262K + vision + MTP | Doesn't fit in 24 GB with q8/q8 KV | Disable vision, or use `q8_0/q5_1` KV — see `docs/measurements/depth.md` and `docs/measurements/memory.md`. |
| Quality noticeably degrades at long context | KV `q4_0/q4_0` (4x the KLD of q8/q8) | Use `q8_0/q8_0` or `q8_0/q5_1` — see `docs/measurements/kv-quality.md`. |
| `400 exceed_context` from your client | Your harness's provider entry doesn't match the launched profile's real context | Run `python3 scripts/check-sync.py`; see `docs/sop/launch-model.md`. |

## Contributing results

New measurements are welcome. Read `docs/BENCHMARK-FORMAT.md` first — it defines the metrics
(pp/tg, depth, cold/warm cache, acceptance rate, KLD) and the method for each benchmark type
(speed, quality, real server, stress test, per-process memory).

A curated result goes under `results/YYYYMMDD-topic-variant/` (see `docs/STYLE.md` §5 for the
naming convention): a short `README.md` (what it measures, the exact command, the conclusion,
a link back to the `docs/measurements/*.md` section that cites it), a small `summary.md` or
`summary.jsonl`, and a `command.json` with the exact argv when available. Only small, valuable
files are kept — no raw per-request logs, SSE streams, or anything over 1 MB. Add the new folder
to `results/INDEX.md`.

Evidence is immutable once published: a result folder is never edited after the fact. A corrected
or repeated measurement gets a new dated folder; the older one stays as-is and gets referenced
from the new one's `README.md` if relevant (`docs/BENCHMARK-FORMAT.md` "Immutable evidence").

## Docs map

| Doc | What it has |
|---|---|
| `docs/STATUS.md` | Current recommended profile, key figures, next steps |
| `docs/DECISIONS.md` | Append-only decision log with evidence links |
| `docs/SOURCES.md` | External claims checked against this repository's own measurements |
| `docs/hardware/` | RX 7900 XTX specs, driver setup, install background |
| `docs/models/` | Model table and quant provenance |
| `docs/ENGINES.md` | llama.cpp build inventory: commits, flags, SHA256 |
| `docs/measurements/` | Benchmark results and conclusions, by topic (engines, kv-quality, memory, coexistence, depth, speculative, thermals-power, concurrency) |
| `docs/BENCHMARK-FORMAT.md` | How the numbers are produced and reported |
| `docs/sop/` | Step-by-step procedures: launch, add a model, update the engine, install day, token ledger |
| `bench/` | Benchmark scripts that reproduce the numbers in `docs/measurements/` |
| `results/` | Curated, small result folders — see `results/INDEX.md` |
| `scripts/check-repo.py` | Repo hygiene check (broken links, oversized files, personal paths, secrets, Spanish leftovers) — run before every push |
| `tests/` | Stdlib `unittest` unit tests for the launcher's pure logic — `python3 -m unittest discover -s tests -v` |

## License

Code (`scripts/`, `bench/`) is MIT licensed. Docs, measurement reports and prose are CC BY 4.0.
See [`LICENSE`](LICENSE).
