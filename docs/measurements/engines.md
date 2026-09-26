# Engines: Vulkan vs ROCm/HIP on RX 7900 XTX (gfx1100)

## Current conclusion

- **ROCm/HIP is 2-3.5x faster than Vulkan for generation on Linux** (39 vs. 11-23 tok/s on the
  same model). Vulkan loses because the GPU memory clock drops to 772 MHz while generating; ROCm
  holds 1249 MHz. This is a Linux/RADV driver behavior, not a kernel P-state bug.
- **Engine in use**: the official llama.cpp `b11160` Ubuntu ROCm 10.0 binary, or an own build with
  the same ROCm 10 toolchain — it matches the official binary's speed and additionally supports the
  KV `q8_0`/`q5_1` mix the official binary doesn't ship kernels for. Building with the older ROCm
  7.2.4 (Arch's system package) is about 9% slower.
- This mirrors what upstream itself documented when closing
  [ggml-org/llama.cpp#20934](https://github.com/ggml-org/llama.cpp/issues/20934): the HIP backend
  is not expected to beat Vulkan on RDNA, because it shares CUDA-oriented kernels and loses
  RDNA's wave64 dual-issue FP32 path, which is only reachable through Vulkan. What we measure
  locally is the opposite direction (HIP ahead) because generation here is memory-bandwidth
  bound and Vulkan's clock behavior on this system erases its kernel-level advantage.
- **Single-backend binaries only** (one Vulkan build, one ROCm/HIP build, never both compiled into
  the same binary): with a dual-backend binary, MTP gets silently routed to the wrong device and
  disabled ([llama.cpp#23199](https://github.com/ggml-org/llama.cpp/issues/23199), closed
  `NOT_PLANNED`). This is a routing bug, not a Vulkan precision problem — no evidence was found for
  an MTP accuracy issue specific to Vulkan on RDNA3.

## Vulkan vs ROCm, generation and prompt processing

Model: Qwen3.8-27B GSQ-RCO IQ3_S-mtp, `-fa on`. Generation (`tg128`) in tok/s:

| KV K/V | Depth | Vulkan | ROCm |
|---|---|---:|---:|
| f16/f16 | 0 | 11.3 | **40.1** |
| f16/f16 | 4K | 23.6 | **38.9** |
| f16/f16 | 16K | 23.0 | **37.8** |
| q8_0/q8_0 | 0 | 11.2 | **39.1** |
| q8_0/q8_0 | 4K | 18.7 | **38.6** |
| q8_0/q8_0 | 16K | 23.1 | **36.5** |

Prompt processing (`pp512`) with q8_0/q8_0: Vulkan 855 / 795 / 537, ROCm **998 / 959 / 851** tok/s
(depths 0 / 4K / 16K).

**Why Vulkan loses**: `pp_dpm_mclk` was logged every 5 s. With Vulkan, GPU memory clock dropped to
**772 MHz** (power level 2) during generation. With ROCm it held **1249 MHz** in 47 of 48 samples.
Generation is memory-bandwidth bound, so this explains the gap, including the anomaly of Vulkan
being slower at depth 0 than at 16K. The GPU core did clock up to ~3000 MHz on both backends: **this
is not the kernel P-state bug** referenced elsewhere. Forcing
`power_dpm_force_performance_level`/`COMPUTE` profile on Vulkan was not tested, because ROCm already
reaches these numbers without touching power management.

## Flags checked against `llama-server --help` (b11160, ROCm)

| `models.toml` flag | b11160 default | Verdict |
|---|---|---|
| `-fa on` | `auto` | Kept: mandatory with quantized V, prevents silent disabling |
| `-np 1` | `-1` (auto = 4 slots) | Kept |
| `--ctx-checkpoints 4` | 32 | Kept: checkpoints live in RAM |
| `-ngl all` | `auto` | Kept |
| `--spec-draft-n-max 2` | 3 | Kept (see `speculative.md`) |
| `--metrics` | disabled | Kept: exposes `/metrics` for the persistent token ledger (`docs/sop/token-ledger.md`) |

Flags tested and **not** added, because they change nothing or are already the default:

- `-ub 1024/2048` (default 512): with `pp2048` at an **empty context**, stays within ±1% of default
  (noise) — but this doesn't hold at depth: measured at 128K fill under the 272 W power cap
  (`-ub`'s VRAM effect only shows clearly near a full context), `-ub 1024` gains nothing and costs
  590 MiB, `-ub 2048` is strictly worse (pp −1.7%, code tg −3.6%, +1.8 GiB VRAM). **This supersedes
  the pp2048-only reading above for any depth-relevant decision** — see
  [`speculative.md`](speculative.md#-ub-and-mtp-screening-at-128k-fill-272-w-2026-09-25) and
  [`../../results/20260925-ubatch-mtp-screening-128k/`](../../results/20260925-ubatch-mtp-screening-128k/).
  `-ub 512` (the default) is kept.
- `ROCBLAS_USE_HIPBLASLT=1`: pp2048 and tg128 stay within ±1% of default (noise); not re-tested at
  depth.
- `--no-kv-unified`: unified KV **only** activates when `-np` is auto. With `-np 1` it is already
  disabled.
- `--spec-ngram-map-k4v-size-n 12 / size-m 48 / min-hits 1`: already b11160's defaults.
- `LLAMA_ATTN_ROT_DISABLE=1`: see below.

## `LLAMA_ATTN_ROT_DISABLE`: not needed here

An external cookbook for a different fork claims this variable is "mandatory" with quantized KV on
HIP or the process crashes. **Not reproduced** with the official llama.cpp b11160 and KV q8/q8: both
128K and 262K work fine without the variable. Reading `src/llama-kv-cache.cpp` (master):
`attn_rot_k = !attn_rot_disable && ... && ggml_is_quantized(type_k) && head_dim % 64 == 0` — this is
the Hadamard rotation from PR #21038 (merged 2026-04-01) that **improves** quantized-KV precision,
and it self-activates. Disabling it is only needed on specific architectures (DeepSeek-V4, #25382);
Qwen3.x is not among them. **Confirmed: do not use it.**

## Own gfx1100 build and the compiler matters

The official ROCm binary only ships FlashAttention kernels for
`q4_0-q4_0;q8_0-q8_0;f16-f16;bf16-bf16`. To get the `q8_0`/`q5_1` mix, we compiled our own b11160
with `-DGGML_CUDA_FA_QUANTS="q8_0-q8_0;q8_0-q5_1;q8_0-q4_1"`. On Arch, `-DCMAKE_HIP_FLAGS="--rocm-path=/opt/rocm"`
is required, or the build fails with `'hip/hip_fp16.h' file not found`. Only the system ROCm install
is needed, no `sudo` beyond package install.

**Speed vs. the official binary** (IQ3_S-mtp, `llama-bench`, q8/q8):

| | pp512 | tg128 | pp512 @16K | tg128 @16K |
|---|---:|---:|---:|---:|
| Official `ubuntu-rocm-10.0` | 985 | **38.9** | 841 | **36.6** |
| Own gfx1100 build (ROCm 7.2.4 compiler) | 964 | 38.2 | 827 | 33.9 (−7.5%) |
| Own gfx1100 build, KV q8/q5_1 (ROCm 7.2.4 compiler) | 975 | 38.1 | 832 | 33.5 |

An own build compiled with the older **ROCm 7.2.4 toolchain** is slower — but this turned out to be
the compiler, not the source: see the corrected engine matrix below.

### Engine matrix, corrected (ROCm 10 toolchain)

| Engine | KV | tg128 | tg128 @16K | pp512 @16K |
|---|---|---:|---:|---:|
| Official `ubuntu-rocm-10.0` (system runtime 7.2.4) | q8/q8 | 39.7 | **37.2** | 859 |
| Own build, ROCm **7.2.4** compiler | q8/q8 | 38.2 | 33.9 | 827 |
| Own build, **ROCm 10.0.0** compiler, no kvmix | q8/q8 | 39.2 | 36.9 | 853 |
| Own build, **ROCm 10.0.0** compiler, kvmix | q8/q8 | 39.0 | **36.8** | 849 |
| Own build, **ROCm 10.0.0** compiler, kvmix | **q8/q5_1** | 38.6 | 33.8 | 849 |

- **The compiler matters**: with ROCm 10 (the same toolchain the official binary uses), the own
  build **matches the official binary**. With ROCm 7.2.4's clang it is 9% slower at 16K. This
  corrects the earlier "own build is 7.5% slower" reading above — that was the compiler, not the
  source.
- **V in q5_1 costs ~8% of tg at 16K** vs. q8 (measured with the ROCm 10 compiler). The first
  measurement above didn't show this because both builds used the slow ROCm 7.2.4 compiler.
- ROCm 10 installs as Python "TheRock" wheels in a venv, the same way the official CI does
  (`release.yml`, job `ubuntu-24-rocm`), without touching the system. Running against that venv's
  `LD_LIBRARY_PATH` at runtime **fails** with `rocBLAS error: Could not initialize Tensile host`
  (missing gfx1100 kernel package for rocBLAS) — not investigated further; every engine here uses
  the system's ROCm 7.2.4 runtime at run time, only the ROCm 10 toolchain at *compile* time.
- **Explicit compile-vs-runtime split** (2026-09-26): `hip-kvmix` is **compiled** against ROCm
  10.0.0 (the TheRock wheels above) but at **runtime** loads the system's ROCm 7.2.4 shared
  libraries — `libamdhip64.so.7`, `librocblas.so.5`, `libhipblas.so.3` and `libhsa-runtime64.so.1`
  from `/opt/rocm/lib`, provided by the distro packages `rocm-core`, `hip-runtime-amd`, `rocblas`
  and `hipblas` (all 7.2.4). Community advice to "use ROCm 7.x" therefore already applies to this
  engine's runtime; the untested parts are the *compiler* codegen (ROCm 7.2.4 vs. 10 — see the
  engine matrix above, ~9% slower with the 7.2.4 compiler) and the ROCm 10 *runtime* libraries
  (untested — the venv's `LD_LIBRARY_PATH` fails to load, see above). See `docs/ENGINES.md`'s
  "Candidate engines" for what this motivates.
- Current `hip-kvmix` engine = the ROCm-10-compiled build. The ROCm-7.2.4-compiled build is
  obsolete.

## Upstream research: build flags, feature parity, protocol

Read directly from `ggml-org/llama.cpp` source and docs (2026-09-22, before the GPU was installed;
cross-checked against local measurements above where noted).

- **`GPU_TARGETS` replaces `AMDGPU_TARGETS`.** Current `docs/build.md`:
  ```bash
  HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
      cmake -S . -B build -DGGML_HIP=ON -DGPU_TARGETS=gfx1100 -DCMAKE_BUILD_TYPE=Release \
      && cmake --build build --config Release -- -j 16
  ```
  `AMDGPU_TARGETS` is still accepted as a backward-compatible alias
  (`ggml/src/ggml-hip/CMakeLists.txt` forwards it), but the canonical name today is `GPU_TARGETS`.
  `GPU_TARGETS` is optional — omitting it compiles for every GPU detected on the system.
- **`GGML_HIP_ROCWMMA_FATTN` no longer exists.** The rocWMMA FlashAttention kernel
  (`fattn-wmma-f16.cu`) was removed in
  [PR #26046](https://github.com/ggml-org/llama.cpp/pull/26046) (merged 2026-07-24): "this kernel is
  now obsolete as all relevant AMD hardware can use the better kernel in `fattn-mma-f16.cuh`". Dead
  references to the flag were cleaned up later in
  [PR #26760](https://github.com/ggml-org/llama.cpp/pull/26760). FlashAttention on HIP uses the same
  MMA path as CUDA, no separate activation flag.
- **Vulkan build**: `cmake -B build -DGGML_VULKAN=ON && cmake --build build --config Release`.
- **No AUR package** for a stable `llama.cpp-vulkan`/`llama.cpp-hip` (checked against the AUR RPC
  API). `llama.cpp-vulkan-git`/`llama.cpp-hip-git` exist (dev branch); `llama.cpp-hip-gfx1151` is
  Strix Halo (APU) specific, not this discrete gfx1100 card. Building from source is the recommended
  path on Arch/CachyOS.

### KV cache types and FlashAttention, by backend

The rule "quantized V cache requires FlashAttention" lives in `src/llama-context.cpp`, not in a
specific backend — it applies identically to Vulkan and HIP. Valid `-ctk`/`-ctv` types
(`common/arg.cpp`, `kv_cache_types`): `f32`, `f16`, `bf16`, `q8_0`, `q4_0`, `q4_1`, `iq4_nl`, `q5_0`,
`q5_1`, chosen independently for K and V.

- **HIP (and CUDA)**: by default only compiles
  `GGML_CUDA_FA_QUANTS = "q4_0-q4_0;q8_0-q8_0;f16-f16;bf16-bf16"`. The HIP build reuses those CUDA
  kernel instances. An uncompiled K/V combination returns `nullptr` in `fattn.cu` and the op falls
  back to CPU (a heavy slowdown) — **check the log** before trusting a measurement. To use mixes
  like `q8_0`/`q5_1` on HIP, compile with `-DGGML_CUDA_FA_QUANTS="q8_0-q8_0;q8_0-q5_1;q8_0-q4_1"` (or
  `all`) — this is exactly what the own build above does.
- **Vulkan**: `ggml-vulkan.cpp` accepts K and V independently from
  `f32/f16/bf16/q8_0/q5_1/q5_0/q4_1/q4_0/iq4_nl`; the only restriction is not mixing `bf16` with
  another type. `q8_0`/`q5_1` and `q8_0`/`q4_1` are supported in the prebuilt Vulkan binary without
  recompiling.

**Practical rule**: with the prebuilt binaries, use `q8_0/q8_0` (or `q4_0/q4_0`) on HIP. K/V mixes
need Vulkan or an own HIP build.

### `--fit` and free-memory queries

`--fit`/`--fit-target` go through the generic `ggml_backend_dev_memory()` interface, implemented
natively per backend (`ggml_backend_vk_device_get_memory()` for Vulkan,
`cudaMemGetInfo()`/its HIP equivalent for HIP). Both expose a real free-VRAM query; this is not a
CUDA-only feature. Whether the resulting layer split is actually good in practice on this GPU is not
verified — measure it.

### Community Vulkan vs. HIP scoreboards (third-party GPUs/models, for context only)

- [`llama.cpp` discussion #10879](https://github.com/ggml-org/llama.cpp/discussions/10879) (Vulkan
  scoreboard) and [#15021](https://github.com/ggml-org/llama.cpp/discussions/15021) (ROCm/HIP
  scoreboard), both curated, same protocol, Llama 2 7B Q4_0: RX 7900 XTX Vulkan **182.63 tok/s**
  tg128 (no FA) / 190.92 (FA) vs. ROCm **167.11** (no FA) / 170.12 (FA) — Vulkan ~9-12% ahead on this
  smaller model, opposite direction from what we measure on Qwen3.8-27B above. The gap is
  model-dependent, not a fixed backend ranking.
- `@LithiumDevourer` (issue #20934, 2026-09-13, build `b10809`), Qwen3.8-27B-UD-Q4_K_XL, single RX
  7900 XTX: Vulkan 39.07 tok/s vs. ROCm 36.02 tok/s (~8.5% gap) — closer to our model class, still
  the opposite direction from the local ROCm-ahead result above. Reports `warp size: 64` under
  Vulkan vs. `Wave Size: 32` under ROCm on the same card, consistent with the maintainer explanation
  below. With 2 GPUs, ROCm `-sm tensor` wins (46.87 tok/s) — not applicable to a single-GPU setup.
- Maintainer `@IMbackK` closing #20934 (`COMPLETED`, same day, not because the gap was fixed):
  > "the hip backend is not expected to be faster than the vulkan backed. [...] The hip backend
  > shares its source and kernels with the cuda backend and the kernels there where mainly designed
  > with nvidia devices in mind. [...] on rdna3/rdna4 support packed fp32 math doubling throughput
  > in some instances, however, the compiler is rarely capable of optimizing these instructions in
  > wave32 mode. In wave64 dual issue is used frequently. Wave64 mode on RDNA is not available via
  > hip it is only available via vulkan [...] the CUDA/hip backend use vendor provided blas
  > libraries, vulkan dose not, unfortunately amd doesn't spend much time optimizing their blas
  > libraries for rdna."

This is the expected-by-design gap upstream describes for HIP vs. Vulkan on RDNA — our local
measurement showing ROCm *ahead* is explained by the Vulkan memory-clock throttling above, which is
a separate, additive effect on top of (or against) this kernel-level gap.

## Open questions

- Whether the Ubuntu Vulkan tarball runs unmodified on CachyOS (glibc/libstdc++/libvulkan
  compatibility) — not tested, building from source is used instead.
- Real tok/s of Vulkan vs. HIP across the full model lineup beyond what's measured above — the
  community scoreboards above are other models/GPUs of the same chip, order-of-magnitude reference
  only.
- Whether an LTS kernel is still needed to avoid the P-state bug referenced by
  `CachyOS/linux-cachyos#888`/`#1035` — not seen with kernel 7.2.7 during any of this session's
  measurements (GPU clocked normally throughout), not re-tested directly.

## History

- **2026-09-22**: upstream research pass (no GPU installed yet) — build flags, feature parity,
  measurement protocol, community scoreboards.
- **2026-09-24**: first local Vulkan-vs-ROCm measurement (§3 numbers above); own gfx1100 build
  compiled with the ROCm 7.2.4 toolchain, found slower than official (later corrected).
- **2026-09-24, night**: engine matrix repeated with the ROCm 10 toolchain — corrects the "own build
  is slower" reading; the compiler, not the source, explained the gap. Current `hip-kvmix` engine
  pinned to the ROCm-10-compiled build.
