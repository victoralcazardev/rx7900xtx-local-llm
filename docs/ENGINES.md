# Engines: llama.cpp builds for the RX 7900 XTX (gfx1100)

Inventory of llama.cpp `llama-server` builds used on this GPU, with pinned versions and SHA256 so
a build can be verified or reproduced. Windows engines and NVIDIA/CUDA engines are out of scope for
this repository — see `docs/measurements/engines.md` for the performance research behind these
choices (Vulkan vs. ROCm, why single-backend binaries only).

All builds are llama.cpp **`b11160`** (commit `70c4e1582`) unless noted otherwise. SHA256 is of the
`llama-server` executable itself. **Note on identical hashes**: these builds use
`-DGGML_BACKEND_DL=ON` — `llama-server` is a thin front-end that loads the actual backend
(`libggml-hip.so`, `libggml-cpu-*.so`, ...) at runtime. Builds that only differ in a backend-library
patch (e.g. `kvmix` vs. `kvmix-vec4`, which only touches `ggml/src/ggml-cuda/fattn.cu`) or in the
llama.cpp source tree but not the front-end code can therefore share the exact same `llama-server`
hash — the difference lives in the shared library, not the file hashed here.

| Engine folder | Status | Commit / build | SHA256 (`llama-server`) |
|---|---|---|---|
| `llama-b11160-bin-ubuntu-rocm-10.0-x64` | **Current** (`hip` in `local.toml`) | b11160 / `70c4e1582`, official CI | `8c98a329346088d0cdd03195ae5864e29c9a8b11fc293397a723f8730e9492dc` |
| `llama-b11160-bin-ubuntu-vulkan-x64` | Reference (2-3.5x slower on generation here, see `docs/measurements/engines.md`) | b11160 / `70c4e1582`, official CI | `ddb272c01521fc81c14ae430a944cd52d8db9c7d237e1b90f77d0b2f33a2c012` |
| `llama-b11160-linux-rocm10-gfx1100-kvmix` | **Current** (`hip-kvmix` in `local.toml`) | b11160 / `70c4e1582`, own build | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` |
| `llama-b11160-linux-rocm10-gfx1100-kvmix-vec4` | Discarded (+20% ms/step at depth vs. `kvmix`, see `docs/measurements/speculative.md`) | b11160 / `70c4e1582` + 1-line patch | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` (same front-end; patch is in `libggml-hip.so`) |
| `llama-b11160-linux-rocm-gfx1100-kvmix` | Discarded (~9% slower than the ROCm-10-toolchain build, see `docs/measurements/engines.md`) | b11160 / `70c4e1582`, own build, older ROCm 7.2.4 system toolchain | `7c27f7fd7c0398075b2837a531c98cc6c57766ff107d671c1c7b06c18d6cd1b2` |
| `llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100` | Experimental, not adopted (only -2.5% ms/step at depth; not worth maintaining a fork, see `docs/measurements/speculative.md`) | `stew675/llama-cpp-rdna-boosts` v16-`ebbb18522`-r13, 16 patches on llama.cpp `ebbb18522` | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` (same front-end) |

## Build recipes

### Official binaries (`bin-ubuntu-rocm-10.0-x64`, `bin-ubuntu-vulkan-x64`)

Prebuilt CI artifacts from the `ggml-org/llama.cpp` GitHub release for build `b11160`. No local
build recipe — downloaded as-is. Runtime dependency: the ROCm binary uses the system's installed
ROCm runtime libraries (ROCm 7.2.4 packages on this Arch-based system) unless a newer runtime is
provided on the library path.

### `llama-b11160-linux-rocm10-gfx1100-kvmix` (current `hip-kvmix` engine)

llama.cpp b11160 (commit `70c4e1582`), built locally with the **same toolchain and flags as the
official `ubuntu-rocm-10.0` CI binary** (`release.yml`, job `ubuntu-24-rocm`): ROCm 10.0.0 installed
as Python "TheRock" wheels in an isolated venv (does not touch the system):

```bash
uv venv --python 3.12 ~/src/rocm10-venv && source ~/src/rocm10-venv/bin/activate
uv pip install --index-url https://stable.repo.amd.com/rocm/whl-next/ "rocm[libraries,devel]==10.0.0"
export ROCM_PATH=$(rocm-sdk path --root) HIP_PATH=$ROCM_PATH \
       CMAKE_PREFIX_PATH=$(rocm-sdk path --cmake) PATH=$(rocm-sdk path --bin):$PATH

cmake -B build-rocm10 -S . -DCMAKE_HIP_COMPILER="$(hipconfig -l)/clang" -DCMAKE_BUILD_TYPE=Release \
  -DGGML_BACKEND_DL=ON -DGGML_NATIVE=OFF -DCMAKE_INSTALL_RPATH='$ORIGIN' \
  -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON -DGGML_CPU_ALL_VARIANTS=ON -DGPU_TARGETS=gfx1100 \
  -DGGML_HIP=ON -DHIP_PLATFORM=amd \
  -DGGML_CUDA_FA_QUANTS="f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0"
cmake --build build-rocm10 -j 14 --target llama-server llama-bench llama-perplexity
```

Differences from the official binary: `gfx1100` only (not a multi-architecture fat binary), and
FlashAttention kernels compiled for the K `q8_0` + V `q5_1`/`q4_1` mix, which the official binary
doesn't ship. At runtime it uses the system's ROCm 7.2.4 libraries by default
(`/opt/rocm/lib`) — the ROCm 10 venv above is a **build-time** toolchain only.

### `llama-b11160-linux-rocm10-gfx1100-kvmix-vec4` (discarded)

Same as `kvmix` above, plus a 1-line patch to `ggml/src/ggml-cuda/fattn.cu` (the AMD branch, no
MMA/MFMA): with quantized KV, the VEC kernel is used for up to 4 tokens per batch instead of 2. MTP
n=2/3 verifies 3-4 tokens per step; without the patch that routes through the TILE kernel, which
converts the KV cache to f16 on every layer, every step. Only `libggml-hip.so` differs from
`kvmix`. **Measured and discarded**: +20% ms/step at ~190K depth vs. plain `kvmix` — see
`docs/measurements/speculative.md`.

### `llama-b11160-linux-rocm-gfx1100-kvmix` (discarded)

llama.cpp b11160 (commit `70c4e1582`), built with the system's ROCm 7.2.4 (Arch packages
`hip-runtime-amd`, `rocblas`, `hipblas`; `rocm-llvm` clang 22) instead of the ROCm 10 venv toolchain:

```bash
PATH=/opt/rocm/bin:$PATH ROCM_PATH=/opt/rocm HIP_PATH=/opt/rocm HIPCXX=/opt/rocm/lib/llvm/bin/clang \
cmake -S . -B build-gfx1100 -DGGML_HIP=ON -DGPU_TARGETS=gfx1100 -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_HIP_FLAGS="--rocm-path=/opt/rocm" -DCMAKE_PREFIX_PATH=/opt/rocm \
  -DGGML_CUDA_FA_QUANTS="f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0"
cmake --build build-gfx1100 -j 14 --target llama-server llama-bench llama-perplexity
```

Same FA-kernel difference from the official binary as `kvmix` above, but built entirely against the
older ROCm 7.2.4 toolchain (not just the runtime). **Measured and discarded**: about 9% slower than
the `kvmix` build that uses the ROCm 10 toolchain — see `docs/measurements/engines.md`.

### `llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100` (experimental)

Fork `stew675/llama-cpp-rdna-boosts`, release `v16-ebbb18522-r13` (16 patches, `git am` on top of
llama.cpp `ebbb18522`; tree `bb7b6d07` matches the release's own `release.json`). Built with the
same ROCm 10 venv and flags as `kvmix` above, but with
`-DGGML_CUDA_FA_QUANTS="f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1"` (no `q8_0-q4_1`). Key runtime
environment variable: `GGML_CUDA_FA_KV_NATIVE` — unset means auto (native `q8_0` in FlashAttention,
no F16 copy); `=0` means the old F16 path. Verified with
`test-backend-ops -o FLASH_ATTN_EXT -p 'hsk=256.*q8_0'`: 10/10 passed. **Measured and not adopted**:
only -2.5% ms/step at ~190K depth vs. `kvmix` — not worth maintaining a separate fork for that gain.
See `docs/measurements/speculative.md`.

## Not included here

Windows binaries (`*-bin-win-*`) and any NVIDIA/CUDA engine folder are out of scope for this
repository — see `AGENTS.md`.

## Source

Research behind these build flags (upstream `docs/build.md`, the `GPU_TARGETS` vs. `AMDGPU_TARGETS`
naming, why `GGML_HIP_ROCWMMA_FATTN` no longer exists, K/V FlashAttention kernel support per
backend) is in `docs/measurements/engines.md` and `docs/SOURCES.md`.
