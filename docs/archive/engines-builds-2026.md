# Engine build archive (2026): deleted and discarded builds

Build recipes, patches and hashes of the `hip-kvmix` builds deleted locally on 2026-10-30 or discarded, moved out of
[`docs/ENGINES.md`](../ENGINES.md) on 2026-11-23 so that file keeps the engines in use and the rollback; rebuild any of
these with `scripts/build_engine.py --ref <tag>` plus the listed patches. Frozen: verbatim from that move except
relative links re-based for this folder; the current engine is v0.9.0 and its rollback b11846, neither of them here.

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
([`results/20261006-b11454-engine-update/`](../../results/20261006-b11454-engine-update/README.md)).
**Prebuilt download**: GitHub release [`engine-b11454-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-b11454-rocm10-gfx1100-kvmix),
`llama-b11454-pr29509-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256 `60dafa459f7534069c3e15fc85f4bc6fd29537558603f61b86f7ecfaa3adbb46` (same layout as the b11371 asset plus
`pr29509-b3c2735.diff`; ROCm runtime not bundled). Rollback: `llama-b11371-pr29509-linux-rocm10-gfx1100-kvmix` (b11371 + the same
patch, local trial engine since 2026-10-04, see
[`ENGINES-EXPERIMENTS.md`](../ENGINES-EXPERIMENTS.md#llamacpp-pr-29509-local-trial-2026-10-04)).

### `llama-b11371-linux-rocm10-gfx1100-kvmix` (`hip-kvmix` engine adopted 2026-10-03, superseded)

llama.cpp b11371 (commit `99b9548`), built with the exact recipe of the b11160 build below (cmake
options unchanged; `GGML_CUDA_FA_QUANTS` is still honored). `--version`: `0.5.0-dev (build 71,
commit 99b9548)` (the build number comes from the local clone). Runtime: system ROCm 7.2.4, like the
b11160 build. `--help` vs. b11160 adds only `--rpc` and `--spec-draft-sampling` (default `greedy`);
no default changed for the `models.toml` flags. Speed, VRAM and generated tokens equal b11160
([`results/20261003-b11371-mtp-draft-sampling/`](../../results/20261003-b11371-mtp-draft-sampling/README.md));
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

