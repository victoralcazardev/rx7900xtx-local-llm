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
| `llama-b11160-bin-ubuntu-vulkan-x64` | Reference (2-3.5x slower on generation here; still 1.2-1.6x slower with the memory clock pinned, see `docs/measurements/engines.md`) | b11160 / `70c4e1582`, official CI | `ddb272c01521fc81c14ae430a944cd52d8db9c7d237e1b90f77d0b2f33a2c012` |
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

**Prebuilt download**: the exact build (the files above plus `BUILD.txt` and llama.cpp's MIT
`LICENSE`, ROCm runtime not bundled) is published as the GitHub release
[`engine-b11160-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11160-rocm10-gfx1100-kvmix):
`llama-b11160-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256
`f1cb8e2683c94cc5891a11af7876058d50e2c0556f0ffeb92d2451bf659fc3ec`. It is the artifact the
[local-ai-registry](https://github.com/0xSero/local-ai-registry) host launch for this profile pins.

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

**Compiled vs. runtime ROCm, explicit**: `hip-kvmix` is compiled with ROCm 10.0.0 (the venv above)
but at runtime resolves `libamdhip64.so.7`, `librocblas.so.5`, `libhipblas.so.3` and
`libhsa-runtime64.so.1` to the system's ROCm 7.2.4 install (`/opt/rocm/lib`, distro packages
`rocm-core`/`hip-runtime-amd`/`rocblas`/`hipblas`, all 7.2.4). Community advice to "use ROCm 7.x"
already applies to this runtime; what's untested is the *compiler* codegen (ROCm 7.2.4 vs. 10 —
see `llama-b11160-linux-rocm-gfx1100-kvmix` above, ~9% slower) and the ROCm 10 *runtime* libraries
(fails to load today, see `docs/measurements/engines.md`).

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

## Other engines evaluated (2026-09-26)

Community claims reviewed 2026-09-26 (`docs/SOURCES.md`) surfaced four candidates:

- **ROCm 10.0.0 runtime libraries** (TheRock, vs. the system ROCm 7.2.4 runtime, ROCm 10 compiler
  held constant) — **tested, rejected**: 1-2% slower tg, ~5% slower pp, higher variance. See
  `docs/measurements/engines.md`.
- **BeeLlama v0.4.7** (ROCm 7.2 prebuilt, `beellama-v0.4.7-bin-ubuntu-rocm-7.2-x64.tar.gz`, KVarN
  KV cache) — **tested, rejected**: KVarN's KLD is ~2.7x q8/q8's at every bit width; the binary
  itself is ~18-22% slower than `hip-kvmix`. See `docs/measurements/kv-quality.md`.
- **exllamav3-rocm** (+ patched TabbyAPI) — HIP port of ExLlamaV3, highest-risk candidate.
  **Deprioritized** after a read-only audit (fork of turboderp exllamav3 @6b84a21b, MIT, no
  CI, no security red flags; README numbers use synthetic prompts and random-token prefill, not
  comparable to ours) — lowest priority of the candidates, 15.3 GB EXL3 model leaves less VRAM
  headroom. See `docs/SOURCES.md`.
- **Vulkan re-test with the GPU memory clock pinned** — done 2026-09-29: pinning nearly doubles
  Vulkan decode at 64K depth but HIP still wins tg +63% at depth 0 and +18% at 64K, so Vulkan
  stays reference-only (see `docs/measurements/engines.md`). A latest-master Vulkan build is worth
  trying only if upstream shows a large Vulkan decode change.

## KVMem trial (prepared 2026-09-30, not run)

[kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp) (paper
[arXiv:2609.04852](https://arxiv.org/abs/2609.04852)) is a llama.cpp fork with its own
`llama-kvmem-server`. It keeps the full logical workspace (`-c 262144`) in host RAM and, for each
agent step, retrieves the relevant 128-token KV blocks into a bounded GPU working set
(`--kvmem-budget` + `--kvmem-gen-reserve`). Attention then runs over that set instead of the whole
history. It is the one candidate that could bound decode cost at depth, where the current profile
drops to ~19-23 tok/s (see `measurements/agent-traffic.md` and `measurements/depth.md`). Claims and
caveats are checked in [`SOURCES.md`](SOURCES.md#context-length-and-compaction-claims-reviewed-2026-09-30).

**Source pinned for the trial**: `kvmem/kvmem-llama.cpp` commit `abe72b38256d` (2026-09-30, source
version 0.17.0), llama.cpp submodule `7fe450e19305`. The prebuilt ROCm packages are older
(`rc3-rocm-beta2`, built on Ubuntu 24.04 against a ROCm 10 runtime), so build from source with the
same ROCm 10 venv toolchain as `hip-kvmix` (above):

```bash
git clone https://github.com/kvmem/kvmem-llama.cpp.git && cd kvmem-llama.cpp
git checkout abe72b38256d && git submodule update --init
source ~/src/rocm10-venv/bin/activate && export ROCM_PATH=$(rocm-sdk path --root)
python3 scripts/build-rocm.py --linux --gpu-targets gfx1100 --jobs 6   # output: build-hip-linux/
ctest --test-dir build-hip-linux --output-on-failure
```

Build only with the model server stopped: HIP kernel compilation needs several GiB of RAM per job,
and a loaded `llama-server` plus the desktop can leave as little as ~9 GiB available on this host.

**Known fit constraints (from the upstream README and ROCm guide, not yet verified here):**

- **KV types**: `f16`, `q8_0`, `q5_0`, `q4_0` only; there is **no `q5_1`**. The upstream IQ3 recipe
  uses `q8_0/q8_0`, which the bounded GPU working set makes affordable. Mixed pairs other than
  `q8_0/q4_0` have argument-parsing checks only, and "ROCm/Vulkan combinations have not been
  validated".
- **Per-turn output cap**: one generation can't exceed `--kvmem-gen-reserve` (16,384 tokens on the
  IQ3 recipe), thinking included. In the real agent traffic here, 4 of 1,303 turns went over 16,384
  output tokens. The upstream launcher also passes `--reasoning-budget 4096`; this repository sets
  a reasoning budget only with evidence (`AGENTS.md`), so the trial leaves it out and records any
  turn that hits the cap.
- **Retrieval anchor**: the IQ3 launchers use `--kvmem-query-policy user`, so retrieval is keyed
  on the last real user message. Tool results are not treated as user messages. The upstream
  query-replay report says the already-read suffix after that user message is kept rather than
  re-selected. In a harness session where one user message starts hours of tool calls, that
  suffix can exceed the GPU budget. How KVMem behaves there is the main open question for this
  workload, even though the paper's DeepSWE result (43.8% → 48.4%) is the same kind of
  single-task agent loop.
- **MTP**: the ROCm launcher uses MTP n=2 with `--kvmem-mtp-state replay`; the current profile uses
  n=3.
- **Host RAM**: the ROCm guide measures ~13-14 GiB of runtime host memory at 256K and recommends
  32 GiB of system RAM. This host has 32 GiB installed, 31.25 GiB usable (`MemTotal`; ~890 MiB is
  reserved by firmware and the kernel), plus zram swap. KVMem replaces `llama-server` (~3.5 GiB
  RSS with the current profile), so the net increase is ~10 GiB. With the desktop's current usage
  that should leave ~10 GiB available; the trial measures it.
- **GPU KV budget**: the ROCm launchers default to `KVMEM_GPU_KV_BUDGET=28672`, validated on a
  16 GiB card. This card has 24 GiB, so a larger budget is possible.

**Trial protocol** (GPU free, `llama-server` stopped):

1. Build and `ctest` as above; check `llama-kvmem-server --help` for every flag below before
   using it.
2. Smoke test on port 8080, text-only (no `--mmproj`), card sampling, with the upstream IQ3 KVMem
   flags: `-c 262144 --kvmem --kvmem-budget 28672 --kvmem-gen-reserve 16384
   --kvmem-block-tokens 128 --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --spec-type draft-mtp
   --spec-draft-n-max 2 --kvmem-mtp-state replay --reasoning-effort medium` (if supported).
3. Decode speed at depth: `BENCH_SERVER=.../llama-kvmem-server` with `bench/depth_bench.py
   --extra "<KVMem flags>"` at 128K/190K/240K fill; also MTP n=3 and a larger `--kvmem-budget`.
4. Long-context quality: `bench/longctx_quality.py --server .../llama-kvmem-server --variants
   <q8q8 MTP variant> --extra "<KVMem flags>"` at 128K and 240K. Exact-match retrieval is exactly
   what a bounded working set could lose.
5. Real agent run: 1-2 hours of the harness's local agent on a documented plan, then the same
   session analysis as `measurements/agent-traffic.md`: wall tok/s by depth, compactions, repeated
   tool calls, turns hitting the output cap.
6. Record peak process VRAM, host RSS, exact commands and commit hashes (upstream asks for the
   same).

**Go/no-go**: continue to a longer trial only if decode at 160K+ fill is at least ~1.3x the current
profile's (~19-23 tok/s), long-context retrieval matches the current 8/8 exact at 240K, at least
~4 GiB of host RAM stays free at 256K, and the agent run shows no output-cap failures and no loss
of task state. Otherwise record the numbers and drop it.

## Upstream watchlist (2026-09-29)

**Keep b11160 pinned: no replacement has been measured on this setup.** The official
[llama.cpp v0.5.0 release](https://github.com/ggml-org/llama.cpp/releases/tag/v0.5.0) lists nightly
b11146, older than this repository's b11160 baseline; its official ROCm binary also lacks the
`q8_0`/`q5_1` FlashAttention kernel required by the current profile. Keep the clock-pinned Vulkan
retest above pending; the upstream items below are monitoring candidates, not evidence to upgrade.

| Upstream item | State and relevance | Limit |
|---|---|---|
| [#27530](https://github.com/ggml-org/llama.cpp/pull/27530) | Merged; cleanup after failed K/V and recurrent/hybrid state restoration. A robustness candidate. | No measured Qwen throughput or quality gain established here. |
| [#29393](https://github.com/ggml-org/llama.cpp/pull/29393) | Merged; RMS_NORM+SCALE fusion, with a reported 4.2–4.8% MTP prefill gain. | Reported on CUDA hardware only; no local HIP/gfx1100 validation. The PR touches only `ggml/src/ggml-cuda/ggml-cuda.cu`, `norm.cu` and `norm.cuh`, which the HIP backend also compiles, so the fusion is expected to reach HIP builds (not measured). Expected impact here: prefill only (e.g. a cold 240K fill at ~380 tok/s, ~632 s → ~605 s, ~27 s saved); decode unaffected. Not worth an engine update alone; bundle with the next one (latest upstream release on 2026-09-29: b11255). |
| [#28003](https://github.com/ggml-org/llama.cpp/pull/28003) | Draft; RDNA3 gfx1100 single-token MMVQ fast path, with the author reporting a Q4_K GEMV result on an RX 7900 XTX. | Not our IQ3_S quant; no local validation. |

These items are watchlist candidates only; this document does not assert whether any is included in
the current b11160 binary. Reassess only after a compatible build is available and benchmarked on
the adopted Qwen profile.

## Not included here

Windows binaries (`*-bin-win-*`) and any NVIDIA/CUDA engine folder are out of scope for this
repository — see `AGENTS.md`.

## Source

Research behind these build flags (upstream `docs/build.md`, the `GPU_TARGETS` vs. `AMDGPU_TARGETS`
naming, why `GGML_HIP_ROCWMMA_FATTN` no longer exists, K/V FlashAttention kernel support per
backend) is in `docs/measurements/engines.md` and `docs/SOURCES.md`.
