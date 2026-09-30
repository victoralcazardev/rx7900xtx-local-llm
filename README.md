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

<details>
<summary>Flags we tried and don't recommend</summary>

- **`-ub 1024`/`-ub 2048`** — no speed gain at depth; `-ub 1024` costs +590 MiB VRAM, `-ub 2048`
  costs +1.8 GiB and is strictly worse (pp -1.7%, code tg -3.6%) — measured at 128K fill, see
  [`docs/measurements/speculative.md`](docs/measurements/speculative.md#-ub-and-mtp-screening-at-128k-fill-272-w-2026-09-25).
- **`--spec-draft-n-max 4`** — at 240K fill, on the exact adopted flags (`-ub 256`): 21.4 tok/s
  mean vs. n=3's 23.3 (-8%), 66% vs. 71% acceptance; also loses at 128K empty-context (45.8 tok/s
  at 31% acceptance vs. n=3's 60.6 tok/s at 56%) — [`docs/measurements/speculative.md`](docs/measurements/speculative.md#n4-checked-again-at-240k-exact-adopted-flags--ub-256-2026-09-26).
- **`--spec-draft-p-min 0.3`** (n=2, 128K fill) — within noise of plain n=2; **`0.8`** (n=3, 190K)
  raises acceptance 67%→96% but not speed; **`0.60`/`0.75`** (n=3, empty context, community `probe.py`) lower speed 68.9→66.2/59.8 tok/s — none adopted — [`docs/measurements/speculative.md`](docs/measurements/speculative.md).
- **`-ctkd q8_0 -ctvd q8_0`** (quantizing the MTP draft's own KV) — shrinks the draft KV by
  480 MiB but grows its compute buffer by 1,036 MiB: a net +426 MiB more total VRAM. Kept at the
  f16 default — [`docs/measurements/memory.md`](docs/measurements/memory.md).
- **KV `q4_0/q4_0`** — 4x the KLD of `q8_0/q8_0`, the only mix below 98% same-top-1 token —
  [`docs/measurements/kv-quality.md`](docs/measurements/kv-quality.md).
- **`-np` > 1** (extra slots) — a slot's own prefill starves generation on the others; queuing
  through 1 slot beats 2 slots (6-9% faster wall time) and 4 slots (~26% faster) —
  [`docs/measurements/concurrency.md`](docs/measurements/concurrency.md).

</details>

## What we tested

- **Backend**: ROCm/HIP is 2-3.5x faster than Vulkan for generation on this system. Vulkan's GPU
  memory clock drops to 456-772 MHz while generating (ROCm holds 1249 MHz), which explains its
  collapse at depth, but not the whole gap: with the clock pinned HIP still leads tg +63% at
  depth 0 and +18% at 64K.
- **ROCm toolchain**: the ROCm 7.2.4 *compiler* costs -7.5% tg at 16K vs. the ROCm 10.0.0 compiler;
  the ROCm 10.0.0 *runtime* is 1-2% slower on tg and ~5% on pp (more variance) than the system's
  ROCm 7.2.4 runtime — kept ROCm 10 compiler + ROCm 7.2.4 runtime.
- **Weight quant**: `IQ3_S-mtp` (PPL 6.734) ties plain `IQ3_S` and beats `IQ3_XXS-mtp` (PPL 6.948)
  while accepting more MTP drafts; the HauhauCS and RVN finetunes are larger and slower per byte.
- **KV cache quant**: `q8_0/q5_1` costs 27% more KLD than `q8_0/q8_0` (still near-lossless) but
  fits the full 262K context where `q8_0/q8_0` tops out at 240K; `q4_0/q4_0` discarded (4x KLD).
- **Speculative decoding**: the built-in MTP head at n=3 wins across task types at the real
  190K/240K operating depths (+9-11% mean tg over n=2); n=4/n=5 lose acceptance, and DFlash2/n-gram
  alternatives don't beat it at depth.
- **Context ladder**: pushed from a 200K candidate through 224K/240K (KV `q8_0/q8_0`) to the full
  native 262K (KV `q8_0/q5_1`), which ended up fitting in less VRAM than 240K.
- **Concurrency**: 1 slot + MTP with request queuing beats adding `-np` slots — a concurrent slot's
  prefill starves generation on the others.
- **Power**: the 272 W cap (this card's driver minimum) costs ~6% prefill speed at depth for a
  7-8°C cooler hotspot; kept permanently via a systemd unit.

<details>
<summary>Full experiment log (verified against <code>docs/</code>, one row per area)</summary>

| Area | Variants tested | Result (key numbers) | Verdict | Evidence |
|---|---|---|---|---|
| Backend | ROCm/HIP vs. Vulkan (b11160) | ROCm 39 tok/s vs. Vulkan 11-23 tok/s (2-3.5x); Vulkan VRAM clock 772 MHz vs. ROCm 1249 MHz; with the clock pinned, HIP still +63% tg at depth 0, +18% at 64K | ROCm/HIP adopted; Vulkan re-tested with the clock pinned (2026-09-29), stays reference-only | [`docs/measurements/engines.md`](docs/measurements/engines.md) |
| ROCm toolchain — compiler | 7.2.4 vs. 10.0.0 (own build) | 7.2.4 compiler: tg 33.9 @16K (-7.5%) vs. the ROCm-10-compiler build (36.8-36.9) | ROCm 10.0.0 compiler adopted | [`docs/measurements/engines.md`](docs/measurements/engines.md) |
| ROCm toolchain — runtime | TheRock 10.0.0 vs. system 7.2.4 runtime (same compiler) | ROCm 10 runtime: -1..-2% tg, ~-5% pp, much higher variance | System 7.2.4 runtime kept | [`docs/measurements/engines.md`](docs/measurements/engines.md), [`results/20260926-rocm-runtime-ab/`](results/20260926-rocm-runtime-ab/) |
| Weight quant | IQ3_XXS-mtp, IQ3_S, **IQ3_S-mtp**, HauhauCS IQ4_XS, RVN Q4_K_M-mtp, Q4_K_M | PPL 6.948 / 6.734 / **6.734** / 6.823 / 6.710 / 6.639; MTP tg (accept) 56.3 (50%) / — / **62.2 (62%)** / — / 48.2 (55%) / — | `IQ3_S-mtp` adopted — best PPL/MTP trade-off in its size class | [`docs/measurements/kv-quality.md`](docs/measurements/kv-quality.md#weight-quantization-matrix-perplexity-toks) |
| KV cache quant | f16, q8/q8, q8/q5_1, q8/q4_1, q4_0/q4_0 (KLD vs. f16) | 0 / 0.000587 / 0.000744 (+27%) / 0.001244 (2x) / 0.002450 (4x) | `q8_0/q5_1` adopted at 262K; `q4_0` discarded | [`docs/measurements/kv-quality.md`](docs/measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16) |
| KVarN (BeeLlama v0.4.7) | q8/q8, q8/q6_0, q8/q5_1, kvarn8/8, kvarn6/6, kvarn5/5 | KLD ~0.0020-0.0022 for KVarN (~2.7x q8/q8 at every bit width); BeeLlama itself -18-22% tg vs. `hip-kvmix` | Rejected; `q8_0/q6_0` near-lossless as a side finding, but BeeLlama-only | [`docs/measurements/kv-quality.md`](docs/measurements/kv-quality.md#beellama-kvarn-kld-2026-09-26) |
| Context window ladder | 200K/224K/240K KV q8/q8, 262K KV q8_0/q5_1 | 224K: 22.3-25.1 tok/s @ 22,700 MiB; 240K: 22.5-24.4 @ 23,407 MiB; 262K: 18.6-26.9 @ 22,630 MiB | 262K `q8_0/q5_1` adopted — more context in less VRAM than 240K `q8/q8` | [`docs/measurements/depth.md`](docs/measurements/depth.md#context-window-ladder-224k-and-240k-272-w-2026-09-25) |
| Long-context retrieval quality | RULER-style Spanish multi-key retrieval, 32K-240K fill | **68/68 exact match**, 0 loops (44/44 to 190K + 8/8 @ 220K + 8/8 @ 240K + 8/8 @ 240K on the exact adopted flags) | Validated on the exact adopted profile flags (MTP n=3, `-ub 256`) | [`docs/measurements/depth.md`](docs/measurements/depth.md#quality-ruler-style-200k-q8q8-mtp) |
| Speculative decoding | none, MTP n=2/3/4/5, `--spec-draft-p-min` 0.3/0.6/0.75/0.8, DFlash2, n-gram stacking | n=3 vs. none: +109% at 240K fill (23.3 vs. 11.2), +85% at empty context (68.9 vs. 37.2); n=3 +9-11% mean tg over n=2 at 190K/240K; n=4 21.4 @ 66% accept vs. n=3's 23.3 @ 71% (240K, exact adopted flags), also 45.8 @ 31% vs. 60.6 @ 56% (128K); p-min 0.8 raises accept 67%→96% but not speed; DFlash2 slower on 2 of 3 tasks at 190K | MTP n=3 adopted | [`docs/measurements/speculative.md`](docs/measurements/speculative.md) |
| Physical batch | `-ub` 256/512/1024/2048 | 256: -350 MiB, pp -5%, same tg (262K profile); 1024: +590 MiB, no gain; 2048: +1.8 GiB, pp -1.7%, code tg -3.6% (128K screening) | `-ub 256` adopted at 262K; default (512) stays best at 128K fill | [`docs/measurements/memory.md`](docs/measurements/memory.md), [`docs/measurements/speculative.md`](docs/measurements/speculative.md#-ub-and-mtp-screening-at-128k-fill-272-w-2026-09-25) |
| Concurrency | 1/2/4 slots (`-np`) | vs. queuing through 1 slot: 2 slots +MTP 8.6% slower wall time, 2 slots no MTP 6.0% slower, 4 slots 25.6% slower | 1 slot + MTP + queue adopted | [`docs/measurements/concurrency.md`](docs/measurements/concurrency.md#1-vs-2-vs-4-slots-mtp-onoff-2026-09-25) |
| Power cap | 303 W vs. 272 W | Prefill -6% (487→459 tok/s) at 190K; hotspot 100-106°C→99°C; tg128 ~-3.4% at empty context (39.35→38.0, single uncontrolled sample) | 272 W adopted as the permanent cap | [`docs/measurements/thermals-power.md`](docs/measurements/thermals-power.md), [`results/20260925-longctx-quality-200k/`](results/20260925-longctx-quality-200k/) |
| Engine patches/forks | `kvmix-vec4`, `stew675/llama-cpp-rdna-boosts` (native q8 KV), Lemonade b1331/b1332, nasone32, exllamav3-rocm | vec4 +20% ms/step (worse); rdna-boosts -2.5% ms/step; Lemonade's build doesn't enable the FA quant kernels this needs; nasone32 targets a different arch/depth; exllamav3-rocm audited clean but deprioritized (15.3 GB model, less VRAM headroom, author's own numbers not comparable) | None adopted | [`docs/measurements/speculative.md`](docs/measurements/speculative.md), [`docs/ENGINES.md`](docs/ENGINES.md), [`docs/SOURCES.md`](docs/SOURCES.md) |
| Vision (`mmproj`) | on vs. off at long context | VRAM/context cost not worth it at 200K+ | Off by default at 262K | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Prompt-cache checkpoints | `--ctx-checkpoints` default (32) vs. 4 | Warm-turn reuse observed regardless (189,467 of 190,000 tokens reused across a task switch) | Kept at 4 — bounds RAM (270-515 MiB per checkpoint measured); prompt-cache log analysis found one 42 s miss mode, see [`memory.md`](docs/measurements/memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29) | [`docs/measurements/engines.md`](docs/measurements/engines.md), [`docs/measurements/speculative.md`](docs/measurements/speculative.md#ab-at-190k--c-204800-kv-q8q8-kvmix-vs-vec4-mtp-n2) |

</details>

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
2. **Build the engine (required).** The official llama.cpp binaries lack the FlashAttention kernels
   for K `q8_0` + V `q5_1`; the build recipe (ROCm-only, never Vulkan+HIP in one build) is in
   [`docs/ENGINES.md`](docs/ENGINES.md).
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
Use `backend = "hip"` (default in `models.toml`). See `docs/measurements/engines.md`.
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
