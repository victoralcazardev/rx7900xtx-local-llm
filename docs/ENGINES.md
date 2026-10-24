# Engines: llama.cpp builds for the RX 7900 XTX (gfx1100)

Inventory of llama.cpp `llama-server` builds used on this GPU, with pinned versions and SHA256 so
a build can be verified or reproduced. Windows engines and NVIDIA/CUDA engines are not measured or
inventoried in this repository (Windows is documented best-effort: [`hardware/windows.md`](hardware/windows.md)) — see `docs/measurements/engines.md` for the performance research behind these
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
| `llama-b11846-pr30792q51-linux-rocm10-gfx1100-kvmix` | **Current** (`hip-kvmix` in `local.toml`, since 2026-10-24; 240K A/B vs. b11820 + the same patch and coding suite in [`results/20261024-engine-b11846-240k/`](../results/20261024-engine-b11846-240k/README.md)) | b11846 / `1a24df1` + local `pr30792-q5_1.patch` kernel hunks, own build (recipe below) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `6ae92a82ad656b4d02ce9ef621a8034d384f496846bc9134cbefecbbebbf3878`) |
| `llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (rollback; 2026-10-23 to 2026-10-24; 240K A/B vs. plain b11820 and coding suite in [`results/20261023-d1-pr30792q51-240k/`](../results/20261023-d1-pr30792q51-240k/README.md)) | b11820 / `d77256999f21` + local `pr30792-q5_1.patch`, own build (recipe below) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `ea6b95ef53e991f3ee49faff2f9b3590ad856500f547c7fc806b005c46301caf`) |
| `llama-b11820-linux-rocm10-gfx1100-kvmix` | Control arm of the 2026-10-23 A/B (neutral vs. b11718); not used | b11820 / `d77256999f21`, own build | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher) |
| `llama-b11718-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (rollback; 2026-10-18 to 2026-10-23; 240K check vs. b11454 + PR #29509 in [`results/20261018-engine-b11718-vs-b11454-240k/`](../results/20261018-engine-b11718-vs-b11454-240k/README.md)) | b11718 / `547208dca`, own build (same recipe as below, no patch) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `0c21f1486ccdfd97b63678eb45087501a575c0aecc318a63300a78b3dc0a7eac`) |
| `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (rollback; 2026-10-06 to 2026-10-18) | b11454 / `462524043` + PR #29509, own build (same recipe as below) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `1cf9a51f5cf92a302f306e74752bbc456a54228e43e2262fd1a9f5a5e7d8d575`) |
| `llama-b11371-pr29509-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (rollback; local trial engine 2026-10-04 to 2026-10-06, see `docs/ENGINES-EXPERIMENTS.md`) | b11371 / `99b9548` + PR #29509, own build | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `f494e4021a8814bc77cacb2333ba44b40a1ce34a63c2eb0c229d20ae7a153ae7`) |
| `llama-b11371-linux-rocm10-gfx1100-kvmix` | Superseded `hip-kvmix` (adopted 2026-10-03; replaced by the PR #29509 trial build on 2026-10-04; its release `engine-b11371-rocm10-gfx1100-kvmix` stays downloadable; it lacks PR #29509, so the measured rollback is the local b11371 + PR #29509 build above) | b11371 / `99b9548`, own build (same recipe as below) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `98ee4acd09bb15ff97994790148c0593fb7a63ac617dec3d517b9d2a73a38557`) |
| `llama-b11160-linux-rocm10-gfx1100-kvmix` | Older `hip-kvmix` (adopted until 2026-10-03; release still downloadable, pinned by the local-ai-registry recipe) | b11160 / `70c4e1582`, own build | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` |
| `llama-b11160-linux-rocm10-gfx1100-kvmix-vec4` | Discarded (+20% ms/step at depth vs. `kvmix`, see `docs/measurements/speculative.md`) | b11160 / `70c4e1582` + 1-line patch | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` (same front-end; patch is in `libggml-hip.so`) |
| `llama-b11160-linux-rocm-gfx1100-kvmix` | Discarded (~9% slower than the ROCm-10-toolchain build, see `docs/measurements/engines.md`) | b11160 / `70c4e1582`, own build, older ROCm 7.2.4 system toolchain | `7c27f7fd7c0398075b2837a531c98cc6c57766ff107d671c1c7b06c18d6cd1b2` |
| `llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100` | Experimental, not adopted (only -2.5% ms/step at depth; not worth maintaining a fork, see `docs/measurements/speculative.md`) | `stew675/llama-cpp-rdna-boosts` v16-`ebbb18522`-r13, 16 patches on llama.cpp `ebbb18522` | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` (same front-end) |

## Build recipes

### Official binaries (`bin-ubuntu-rocm-10.0-x64`, `bin-ubuntu-vulkan-x64`)

Prebuilt CI artifacts from the `ggml-org/llama.cpp` GitHub release for build `b11160`. No local
build recipe — downloaded as-is. Runtime dependency: the ROCm binary uses the system's installed
ROCm runtime libraries (ROCm 7.2.4 packages on this Arch-based system) unless a newer runtime is
provided on the library path.

### `llama-b11846-pr30792q51-linux-rocm10-gfx1100-kvmix` (current `hip-kvmix` engine, 2026-10-24)

llama.cpp b11846 (commit `1a24df1`, `--version` `0.7.0-dev (build 200)`), same recipe as b11820 below
(`build.sh`: ROCm 10.0.0 venv, `GPU_TARGETS=gfx1100`, same `GGML_CUDA_FA_QUANTS`). Source, from a clean
checkout of tag b11846: `patch -p1 --fuzz=3 < tests-kvmix-cases.patch` (two hunks, offsets 5 and 17), then
`git apply --exclude=tests/test-backend-ops.cpp pr30792-q5_1.patch` (its test hunk conflicts with the
Qwen-shape cases). `--help` identical to b11820. FlashAttention Qwen-shape cases
(`-p 'hsk=256.*type_K=q8_0'`) 30/30 OK, 12 of them `q8_0`/`q5_1`. At 240K within +0.5% of b11820
with the same patch and identical greedy text; coding suite 6/6
([results](../results/20261024-engine-b11846-240k/README.md)). SHA256: `libggml-hip.so`
`0be4c1a3fbf945965262e20d810b4c70dacf3370f8ecf35b44c988401679776b`.
**Prebuilt download**: GitHub release [`engine-b11846-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11846-rocm10-gfx1100-kvmix),
`llama-b11846-pr30792q51-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256
`4811e9ff7b02cbfa21e8993f964c5e71c1f0fab6fe4b5631f2e5a6223cc83c76` (adds `pr30792-q5_1.patch`,
`tests-kvmix-cases.patch` and `BUILD.txt`; ROCm runtime not bundled).

### `llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix` (`hip-kvmix` engine 2026-10-23 to 2026-10-24, rollback) and `llama-b11820-linux-rocm10-gfx1100-kvmix`

llama.cpp b11820 (commit `d77256999f21`, `--version` `0.7.0-dev`), the b11718 recipe below unchanged
(ROCm 10.0.0 venv, `GPU_TARGETS=gfx1100`, same `GGML_CUDA_FA_QUANTS`). `--help` vs. b11718 adds only
`--connect` / `--connect-code`; no default of a `models.toml` flag changed. The `pr30792q51` build adds
[`pr30792-q5_1.patch`](../results/20261022-fa-native-q8q51-tile-op-level/pr30792-q5_1.patch) (open PR
#30792 + a `q5_1` V TILE loader, native dequant only for `ne[1] <= 8`). At 240K on the production
profile it decodes 18-27% faster than plain b11820 with identical greedy text, the same VRAM and prefill,
and passes the coding suite 6/6 ([results](../results/20261023-d1-pr30792q51-240k/README.md); op level:
[results](../results/20261022-fa-native-q8q51-tile-op-level/README.md)). Rebuild from source: the patch
applies to b11820; a newer base needs a rebase until PR #30792 merges with `q5_1` V covered.

|File|b11820|b11820 + pr30792q51|
|---|---|---|
|`llama-server`|`410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6`|same|
|`libggml-hip.so`|`53a485ffb56317f69184ed7b8f05afc4664c25f00e647e94573bfb8d9f495650`|`96da7109b361e0b7547eafe3ae478b08140a727d47d9b5655b150d99af822389`|

`libllama-server-impl.so` differs between any two builds (the web UI is downloaded at configure time).

### `llama-b11718-linux-rocm10-gfx1100-kvmix` (previous `hip-kvmix` engine, 2026-10-18 to 2026-10-23)

llama.cpp b11718 (commit `547208dca`, `LLAMA_VERSION` 0.7), no patch: PR #29509 was closed
unmerged on 2026-10-15 and its fix landed upstream as
[#30514](https://github.com/ggml-org/llama.cpp/pull/30514) (kv-cache: honor PARTIAL_ONLY in the
plain KV cache). Same recipe and toolchain as the b11160 build below (ROCm 10.0.0 TheRock venv,
`gfx1100`, same `GGML_CUDA_FA_QUANTS`); runtime: system ROCm 7.2.4. `--version`:
`0.7.0-dev (build 1, commit 547208d)` (shallow clone). `--help` vs. b11454: new `--moe-cache-mib`
and `--spec-draft-n-ubatch`; `--port` default 8080 -> 9931 (the launcher always passes `--port`);
no default changed for the `models.toml` flags. SHA256: `libggml-hip.so`
`5c264baa7dd53ae821ba883d605688ac96de353dd381c8579f110ff9cc039cae`, `libllama-server-impl.so`
`0c21f1486ccdfd97b63678eb45087501a575c0aecc318a63300a78b3dc0a7eac`. **Measured only at 240K** (A/B
vs. b11454 + PR #29509, 2026-10-18, run after the switch): no kernel slowdown; PPL parity, other
depths and retrieval were not re-run, so the headline numbers in `STATUS.md` are still b11454's. No
release asset. Rollback:
`llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix`.

### `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix` (`hip-kvmix` engine 2026-10-06 to 2026-10-18, rollback)

llama.cpp b11454 (commit `462524043`, `LLAMA_VERSION` 0.6) plus
[PR #29509](https://github.com/ggml-org/llama.cpp/pull/29509) head
`b3c27359975ea4fb0f400785de3fc2729a35708a` (server: do not store the draft KV in context
checkpoints; still open upstream, the diff applies cleanly). Same recipe and toolchain as the
b11160 build below (ROCm 10.0.0 TheRock venv, `gfx1100`, same `GGML_CUDA_FA_QUANTS`); runtime:
system ROCm 7.2.4. `--version`: `0.6.0-dev (build 154, commit 462524043)`. `--help` is identical
to b11371: no default changed for the `models.toml` flags. SHA256: `libggml-hip.so`
`7d1c9debd3899244ff803a0bd039c49e9df21112f98d9a00d5c9d59f6f6555c6`, `libllama-server-impl.so`
`1cf9a51f5cf92a302f306e74752bbc456a54228e43e2262fd1a9f5a5e7d8d575` (the launcher hash equals
b11371's). At 240K on the adopted profile: tg +0.7..+3.2%, prefill and VRAM within noise, same
wikitext-2 PPL
([`results/20261006-b11454-engine-update/`](../results/20261006-b11454-engine-update/README.md)).
**Prebuilt download**: GitHub release [`engine-b11454-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11454-rocm10-gfx1100-kvmix),
`llama-b11454-pr29509-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256 `60dafa459f7534069c3e15fc85f4bc6fd29537558603f61b86f7ecfaa3adbb46` (same layout as the b11371 asset plus
`pr29509-b3c2735.diff`; ROCm runtime not bundled). Rollback: `llama-b11371-pr29509-linux-rocm10-gfx1100-kvmix` (b11371 + the same
patch, local trial engine since 2026-10-04, see
[`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md#llamacpp-pr-29509-local-trial-2026-10-04)).

### `llama-b11371-linux-rocm10-gfx1100-kvmix` (`hip-kvmix` engine adopted 2026-10-03, superseded)

llama.cpp b11371 (commit `99b9548`), built with the exact recipe of the b11160 build below (cmake
options unchanged; `GGML_CUDA_FA_QUANTS` is still honored). `--version`: `0.5.0-dev (build 71,
commit 99b9548)` (the build number comes from the local clone). Runtime: system ROCm 7.2.4, like the
b11160 build. `--help` vs. b11160 adds only `--rpc` and `--spec-draft-sampling` (default `greedy`);
no default changed for the `models.toml` flags. Speed, VRAM and generated tokens equal b11160
([`results/20261003-b11371-mtp-draft-sampling/`](../results/20261003-b11371-mtp-draft-sampling/README.md));
adopted as the newer base, not for speed. **Prebuilt download**: GitHub release
[`engine-b11371-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11371-rocm10-gfx1100-kvmix),
`llama-b11371-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256
`159d2be7538f0932ae41c787a2e14bf849a796b6597eb0d0e1416393b92a137b` (same layout as the b11160 asset;
ROCm runtime not bundled). The local-ai-registry recipe still pins the b11160 asset below.

### `llama-b11160-linux-rocm10-gfx1100-kvmix` (previous `hip-kvmix` engine)

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

Moved to [`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md#kvmem-trial-round-1-run-2026-09-30-not-adopted).

## Upstream watchlist (2026-09-29)

Moved to [`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md#upstream-watchlist-2026-09-29).

## Not included here

Windows binaries (`*-bin-win-*`) and any NVIDIA/CUDA engine folder are not inventoried or
measured here. Windows is documented best-effort, not measured
([`hardware/windows.md`](hardware/windows.md), [`sop/install.md`](sop/install.md)); CUDA is out of scope.

## Source

Research behind these build flags (upstream `docs/build.md`, the `GPU_TARGETS` vs. `AMDGPU_TARGETS`
naming, why `GGML_HIP_ROCWMMA_FATTN` no longer exists, K/V FlashAttention kernel support per
backend) is in `docs/measurements/engines.md` and `docs/SOURCES.md`.
