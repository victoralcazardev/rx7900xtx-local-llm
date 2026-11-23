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
| `llama-v0.9.0-pr30792q51-linux-rocm10-gfx1100-kvmix` | **Current** (`hip-kvmix` in `local.toml`, since 2026-11-05, operator choice against a -4.6% decode screen at 64K, [results](../results/20261105-huihui-iq3s-262k/README.md)); published release below | v0.9.0 / `cd959ba` + local `pr30792-q5_1.patch`, own build (recipe below) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `523395ca9d4af53609d2a443c302b1e33e2a41560f5f0fdc8cdd4f2dffb47f63`) |
| `llama-b12633-pr30792q51-linux-rocm10-gfx1100-kvmix` | **Candidate, not adopted** (built 2026-11-22; no 240K A/B and no coding suite: the user deferred the A/B to Qwen4, [DECISIONS](DECISIONS.md) 2026-11-22; FA rerun pending, see [results](../results/20261122-engine-b12633/README.md)) | b12633 / `9c10c94e1` + local `pr30792-q5_1.patch` rebased, own build (recipe below) | `fefb558933a11198a35e4a4ec592b243a3d96df0dd56914c1e938b08ace7ae77` (launcher; `libllama-server-impl.so` `9edc270e068cee19d2f28a28b2aa5a54d5da60166fa7ac4afd73b010a7c697dc`) |
| `llama-b11846-pr30792q51-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (rollback; 2026-10-24 to 2026-11-05; 240K A/B vs. b11820 + the same patch and coding suite in [`results/20261024-engine-b11846-240k/`](../results/20261024-engine-b11846-240k/README.md)) | b11846 / `1a24df1` + local `pr30792-q5_1.patch` kernel hunks, own build (recipe below) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `6ae92a82ad656b4d02ce9ef621a8034d384f496846bc9134cbefecbbebbf3878`) |
| `llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (rollback; 2026-10-23 to 2026-10-24; 240K A/B vs. plain b11820 and coding suite in [`results/20261023-d1-pr30792q51-240k/`](../results/20261023-d1-pr30792q51-240k/README.md)) | b11820 / `d77256999f21` + local `pr30792-q5_1.patch`, own build (recipe below) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `ea6b95ef53e991f3ee49faff2f9b3590ad856500f547c7fc806b005c46301caf`) |
| `llama-b11820-linux-rocm10-gfx1100-kvmix` | Control arm of the 2026-10-23 A/B (neutral vs. b11718); not used; deleted locally 2026-10-30 | b11820 / `d77256999f21`, own build | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher) |
| `llama-b11718-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (2026-10-18 to 2026-10-23; 240K check vs. b11454 + PR #29509 in [`results/20261018-engine-b11718-vs-b11454-240k/`](../results/20261018-engine-b11718-vs-b11454-240k/README.md)); deleted locally 2026-10-30, [recipe](archive/engines-builds-2026.md#llama-b11718-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine-2026-10-18-to-2026-10-23) | b11718 / `547208dca`, own build (b11160 recipe, no patch; [archived](archive/engines-builds-2026.md#llama-b11160-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine)) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `0c21f1486ccdfd97b63678eb45087501a575c0aecc318a63300a78b3dc0a7eac`) |
| `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (2026-10-06 to 2026-10-18); deleted locally 2026-10-30, release asset and [recipe](archive/engines-builds-2026.md#llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix-hip-kvmix-engine-2026-10-06-to-2026-10-18-rollback) | b11454 / `462524043` + PR #29509, own build (b11160 recipe; [archived](archive/engines-builds-2026.md#llama-b11160-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine)) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `1cf9a51f5cf92a302f306e74752bbc456a54228e43e2262fd1a9f5a5e7d8d575`) |
| `llama-b11371-pr29509-linux-rocm10-gfx1100-kvmix` | Previous `hip-kvmix` (local trial engine 2026-10-04 to 2026-10-06, see `docs/ENGINES-EXPERIMENTS.md`); deleted locally 2026-10-30, [recipe](archive/engines-builds-2026.md#llama-b11371-linux-rocm10-gfx1100-kvmix-hip-kvmix-engine-adopted-2026-10-03-superseded) | b11371 / `99b9548` + PR #29509, own build | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `f494e4021a8814bc77cacb2333ba44b40a1ce34a63c2eb0c229d20ae7a153ae7`) |
| `llama-b11371-linux-rocm10-gfx1100-kvmix` | Superseded `hip-kvmix` (adopted 2026-10-03; replaced by the PR #29509 trial build on 2026-10-04; its release `engine-b11371-rocm10-gfx1100-kvmix` stays downloadable; it lacks PR #29509, so the measured rollback is the local b11371 + PR #29509 build above; [recipe](archive/engines-builds-2026.md#llama-b11371-linux-rocm10-gfx1100-kvmix-hip-kvmix-engine-adopted-2026-10-03-superseded)) | b11371 / `99b9548`, own build (b11160 recipe; [archived](archive/engines-builds-2026.md#llama-b11160-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine)) | `410a809bcd04ffaa46100dd68b29eb5d6d0fb12b84d25bc3c543ce18c7968ac6` (launcher; `libllama-server-impl.so` `98ee4acd09bb15ff97994790148c0593fb7a63ac617dec3d517b9d2a73a38557`) |
| `llama-b11160-linux-rocm10-gfx1100-kvmix` | Older `hip-kvmix` (adopted until 2026-10-03; release still downloadable, pinned by the local-ai-registry recipe; [recipe](archive/engines-builds-2026.md#llama-b11160-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine)) | b11160 / `70c4e1582`, own build | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` |
| `llama-b11160-linux-rocm10-gfx1100-kvmix-vec4` | Discarded, [recipe](archive/engines-builds-2026.md#llama-b11160-linux-rocm10-gfx1100-kvmix-vec4-discarded) (+20% ms/step at depth vs. `kvmix`, see `docs/measurements/speculative.md`) | b11160 / `70c4e1582` + 1-line patch | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` (same front-end; patch is in `libggml-hip.so`) |
| `llama-b11160-linux-rocm-gfx1100-kvmix` | Discarded, [recipe](archive/engines-builds-2026.md#llama-b11160-linux-rocm-gfx1100-kvmix-discarded) (~9% slower than the ROCm-10-toolchain build, see `docs/measurements/engines.md`) | b11160 / `70c4e1582`, own build, older ROCm 7.2.4 system toolchain | `7c27f7fd7c0398075b2837a531c98cc6c57766ff107d671c1c7b06c18d6cd1b2` |
| `llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100` | Experimental, not adopted, [recipe](archive/engines-builds-2026.md#llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100-experimental) (only -2.5% ms/step at depth; not worth maintaining a fork, see `docs/measurements/speculative.md`) | `stew675/llama-cpp-rdna-boosts` v16-`ebbb18522`-r13, 16 patches on llama.cpp `ebbb18522` | `3d8565952bcd74cd4e0d3be3a56221619c25da6176d3716972b75b1cc0a34128` (same front-end) |
| `maya-inkling-mini-hip` (`build-ik2/maya-ik2`, not a llama.cpp build) | **Experimental, Inkling-2-Mini only** (built 2026-11-22; `launch.py` backend `maya`, profile `inkling2-mini-unc/262k-maya`; [results](../results/20261122-inkling-maya-vs-fork/README.md)). **In use since 2026-11-23: `hip-port` `f472e94`** in the worktree `maya-inkling-mini-hip-f472e94` ([round 3](../results/20261123-inkling-round/README.md#round-3-2026-11-23-evening-hip-port-f472e94-dspark-loads-ik2_kvfp4-global)); the `2b31ffeaa` checkout stays as rollback | `GodGMN/maya-inkling-mini` branch `hip-port` `f472e94` (was `2b31ffeaa`) + local cherry-pick of `alesha-pro/maya-inkling-mini` `549d734` (tool-call parser, `serve/` only) | `a064a1e059191d8ff8cafd9d9cc0354a3fa784fc55529d69d1b946d7649e92f0` (`maya-ik2` `f472e94`); rollback `e142adbb4d7fdee7b9ee7037498936e986bf8beecf62dee461b871d5808b0a92` (`2b31ffeaa`) |
| `llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix` | **Current `hip-inkling`, Inkling-2-Mini only** (built and wired 2026-11-22; the only engine measured at 262K with that model, [results](../results/20261122-inkling-rdna3-fork/BUILD.md)). Do not point the Qwen setup at it: its q8_1 cache and fusion matchers touch every model | `GodGMN/llama.cpp` branch `inkling-rdna3` `cb0e46960` (tag `b12600` + 6 commits), built as published (no local patch) | `fefb558933a11198a35e4a4ec592b243a3d96df0dd56914c1e938b08ace7ae77` (same front end as b12633; `libggml-hip.so` `0734ce9771709d07b75473095cccd93c0b8e549766d0819ebc8aa2dc94367096`) |

## Build recipes

The own `hip-kvmix` recipes below are what [`scripts/build_engine.py`](../scripts/build_engine.py)
runs in one command: clone a ref, apply the versioned patches of
[`engine-patches/`](../engine-patches/README.md), configure and build with these flags, copy the
result into a new engine folder, add the `libamdhip64.so.7` symlink and run the op tests
([`sop/update-engine.md`](sop/update-engine.md#build-a-new-engine)). The script is the current
source of the flags; the sections below record each build's history and the flags that build used.

### Official binaries (`bin-ubuntu-rocm-10.0-x64`, `bin-ubuntu-vulkan-x64`)

Prebuilt CI artifacts from the `ggml-org/llama.cpp` GitHub release for build `b11160`. No local
build recipe — downloaded as-is. Runtime dependency: the ROCm binary uses the system's installed
ROCm runtime libraries (ROCm 7.2.4 packages until 2026-11-17, 10.1 since) unless a newer runtime is
provided on the library path. Since 2026-11-22 the `kvmix` engine folders carry a `libamdhip64.so.7`
symlink to Arch's generic 10.1 build: CachyOS's x86-64-v3 build crashes every HIP engine at start
([`sop/install.md`](sop/install.md#known-errors)). Own builds use the system toolchain via
`hipconfig` (ROCm 10.1 since 2026-11-17).

### `llama-b12633-pr30792q51-linux-rocm10-gfx1100-kvmix` (candidate, 2026-11-22, not adopted)

llama.cpp tag `b12633` (`9c10c94e16ebc4f3ed7c06264a93bf7e019c3f26`, `--version` `1.0.0-dev (build 12633)`),
523 commits after v0.9.0 and the first release past the v1.0.0 tag. Same recipe and patches as the
v0.9.0 build; the v1.0.0 FA symbol rename did not break the patch, and exactly one hunk (`flash_attn_tile`,
mask base pointer now includes the per-head offset) was rebased by hand. Build 6 min 21 s.
`--help`: 336 → 343 long options, nothing `models.toml` uses changed its default; added
`--moe-cache-cpu-share`, `--ple`/`--shard`, media/tool privacy flags; removed `-dt, --defrag-thold`;
`--spec-type` gains `draft-dflash2` and `draft-lilicorr`. FA Qwen-shape cases 30/30 on four runs, then
intermittent `SIGSEGV` inside the system ROCm runtime (pre-existing: pristine b12633 and v0.9.0 die the
same way, `MUL_MAT_ID` 1077/1077 passes) — the [backend-op tests](../results/20261122-engine-b12633/README.md#backend-op-tests)
section says what to rerun before trusting it. Inkling-2-Mini at 262K does not fit this build (12,765 MiB of
compute buffer).
**Not adopted**: no 240K A/B and no coding suite (deferred to Qwen4); the engine in use stays v0.9.0.

### `llama-v0.9.0-pr30792q51-linux-rocm10-gfx1100-kvmix` (current `hip-kvmix` engine, 2026-11-05)

llama.cpp tag v0.9.0 (commit `cd959ba`, `--version` `0.9.0-dev (build 1)`), 313 commits after b11846, same
recipe and patches as b11846 below (`tests-kvmix-cases.patch` offsets 325 and 410; `pr30792-q5_1.patch`
clean; PR #30792 still open). `--help` adds only `--models-memory-margin`. FA Qwen-shape cases 30/30 OK.
At 64K fill: decode -4.6% on identical greedy text, prefill -2.2%, same VRAM
([results](../results/20261105-huihui-iq3s-262k/README.md)). Adopted by operator choice as the latest release despite that screen.

**Prebuilt download** (published 2026-11-23): GitHub release
[`engine-v0.9.0-rocm10-gfx1100-kvmix`](https://github.com/victoralcazardev/rx7900xtx-local-llm/releases/tag/engine-v0.9.0-rocm10-gfx1100-kvmix),
`llama-v0.9.0-pr30792q51-sigterm-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256
`a24c7aa6c472db89f9815aeb304488b74ff3189cc1d5d523991ab0e441983de0` (`libggml-hip.so`
`f8370f3271403eaf7759d7f585d2c944048dae90762487572ff9984464528304`, `libllama-server-impl.so`
`6abd77ae452cb9bddd8b2725ce046d59129dcb93bf85cdf455a7fd25da06cb85`). The archive adds the local
`server-sigterm-watchdog.patch` (alarm(15) after the first SIGINT/SIGTERM, `_exit` on the second),
which is why `libllama-server-impl.so` was rebuilt on 2026-11-08 after a shutdown hang; not
separately measured. The `libllama-server-impl.so` hash in the table above is that pre-patch build,
so a local folder and the release asset differ only in that library. Not in v0.9.0: #30137 (ref-counted checkpoints) and #31660 (MTP conv snapshots), both
merged on 2026-11-05 after the tag; #30141 (MTP hidden state save/restore) is in.

### `llama-b11846-pr30792q51-linux-rocm10-gfx1100-kvmix` (`hip-kvmix` engine 2026-10-24 to 2026-11-05, rollback)

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

llama.cpp b11820 (commit `d77256999f21`, `--version` `0.7.0-dev`), the b11718 recipe
([`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-b11718-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine-2026-10-18-to-2026-10-23)) unchanged
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

### Deleted and discarded builds (recipes moved)

Build recipes and hashes of the builds deleted locally on 2026-10-30 or discarded are frozen in
[`archive/engines-builds-2026.md`](archive/engines-builds-2026.md); the inventory rows above link their section and
`scripts/build_engine.py --ref <tag>` plus the patches in `engine-patches/` rebuilds any of them. The current
engine is v0.9.0 and its rollback is b11846, not any of these.

### `llama-b11718-linux-rocm10-gfx1100-kvmix` (previous `hip-kvmix` engine, 2026-10-18 to 2026-10-23)

Moved to [`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-b11718-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine-2026-10-18-to-2026-10-23).

### `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix` (`hip-kvmix` engine 2026-10-06 to 2026-10-18, rollback)

Moved to [`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix-hip-kvmix-engine-2026-10-06-to-2026-10-18-rollback).

### `llama-b11371-linux-rocm10-gfx1100-kvmix` (`hip-kvmix` engine adopted 2026-10-03, superseded)

Moved to [`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-b11371-linux-rocm10-gfx1100-kvmix-hip-kvmix-engine-adopted-2026-10-03-superseded).

### `llama-b11160-linux-rocm10-gfx1100-kvmix` (previous `hip-kvmix` engine)

Moved to [`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-b11160-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine).

### `llama-b11160-linux-rocm10-gfx1100-kvmix-vec4` (discarded)

Moved to [`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-b11160-linux-rocm10-gfx1100-kvmix-vec4-discarded).

### `llama-b11160-linux-rocm-gfx1100-kvmix` (discarded)

Moved to [`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-b11160-linux-rocm-gfx1100-kvmix-discarded).

### `llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100` (experimental)

Moved to [`archive/engines-builds-2026.md`](archive/engines-builds-2026.md#llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100-experimental).

### `llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix` (experimental, Inkling-2-Mini only)

`GodGMN/llama.cpp` branch `inkling-rdna3` at `cb0e469607c19b63b3d06a8b654fcebdd76fb889` (2026-11-21): tag
`b12600` plus an upstream #32704 backport and 5 commits adding an in-kernel relative-bias attention path
(`GGML_OP_INK_REL_BIAS`, `INK_FA_REL_BIAS`) and fused Inkling HIP kernels (`clip`, `situ`, `conv`, `mix`).
Built as published with the recipe above and **without** the local `q5_1` patch (8 min 01 s). Checks: 9/9
`INK_REL_BIAS`, 859/859 `FLASH_ATTN_EXT hsk=128`, 63/63 of the fork's own op cases, `test-ink-rel-bias`
`PASSED` (196,608 cells identical to the unfused chain). Scope, from the branch's own docs: every model on
every card can hit the q8_1 input cache (`GGML_CUDA_NO_Q8_CACHE=1` disables it) and the fusion matchers
(`GGML_INK_NO_FUSE=1`); the mmvq table change is RDNA3-only. It is the only engine measured at 262K with
Inkling-2-Mini (42.0 tok/s, 22,423 MiB) and it is not a candidate for the Qwen setup. Details and the
author's own speed claims: [`results/20261122-inkling-rdna3-fork/BUILD.md`](../results/20261122-inkling-rdna3-fork/BUILD.md).

### `maya-inkling-mini-hip` (`maya-ik2`, experimental, Inkling-2-Mini only)

Not llama.cpp: Project Maya's Inkling-only engine (`alesha-pro/maya-inkling-mini`, CUDA) as ported to gfx1100 by
`GodGMN/maya-inkling-mini` branch `hip-port`, commit `2b31ffeaa802414a14032a4fdf43b93cf871a20d` (2026-11-22). Built in
`~/IA/Motores/src/maya-inkling-mini-hip` with our ROCm 10 TheRock venv instead of the author's ROCm 7.2.1 container
(41 s, no errors):

```bash
git clone --branch hip-port https://github.com/GodGMN/maya-inkling-mini.git maya-inkling-mini-hip
curl -fLsS https://codeload.github.com/ggml-org/llama.cpp/tar.gz/3cf03257f219afbe7334045ff7c6a06ac68c627d | tar xz
source build-env.sh            # ROCm 10 TheRock venv, as for the llama.cpp builds
cmake -S maya-inkling-mini-hip -B maya-inkling-mini-hip/build-ik2 -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSTRATA_ENABLE_HIP=ON -DSTRATA_PREFILL_MMQ=ON -DSTRATA_BUILD_TESTS=ON \
  -DCMAKE_HIP_COMPILER=$ROCM_PATH/llvm/bin/clang++ -DCMAKE_PREFIX_PATH="$CMAKE_PREFIX_PATH;$ROCM_PATH" \
  -DCMAKE_HIP_ARCHITECTURES=gfx1100 -DGPU_TARGETS=gfx1100 \
  -DSTRATA_GGML_DIR=$PWD/llama.cpp-3cf03257f219afbe7334045ff7c6a06ac68c627d
cmake --build maya-inkling-mini-hip/build-ik2 -j14 --target maya-ik2 ik2_kernels_test ik2_host_ref_test
```

- **Runtime**: `maya-ik2` links the venv's `libamdhip64`/`hipBLAS`/`rocBLAS` through its RUNPATH, not the system's
  CachyOS 10.1 build ([install](sop/install.md#known-errors)). **Gotcha**: the venv's rocBLAS has no gfx1100 Tensile
  files, so the engine dies on the first GEMM (`Cannot read .../rocblas/library/TensileLibrary.dat ... for GPU arch :
  gfx1100`, exit -14); `ROCBLAS_TENSILE_LIBPATH=/opt/rocm/lib/rocblas/library` (system rocBLAS 10.1, 150 gfx1100
  files) fixes it.
- **rocBLAS has no GPU code of its own here**: the venv's `librocblas.so.5` ships its kernels in a separate per-arch
  package (`.hip_fatbin` empty, `.rocm_kpack_ref` -> `../.kpack/blas_lib_gfx1100.kpack`, wheel `rocm-sdk-device-gfx1100`),
  so any non-Tensile rocBLAS call (the DSpark drafter's `Sgemv`) fails with `hipErrorInvalidImage`. `LD_LIBRARY_PATH`
  cannot swap it (`libhipblas` uses `DT_RPATH`); `LD_PRELOAD` of a copy with the `.kpack` beside it works
  ([round 3](../results/20261123-inkling-round/README.md#dspark-drafter-the-hiperrorinvalidimage-cause-fixed-slower-on-this-card)). Plain decode does not need it.
- **2026-11-23 update to `f472e94`**: `git worktree add --detach ../maya-inkling-mini-hip-f472e94 f472e94`, the
  production checkout's local diff applied, `ik2/` tokenizer and `ik2-abiray-paged.json` copied, `.venv` symlinked,
  then the same `cmake` lines with that source and build dir (45 s); `local.toml` `engines.maya` points at the worktree.
  Same speed, GSM8K and VRAM; the server's loop guard now handles reasoning segments ([round 3](../results/20261123-inkling-round/README.md#round-3-2026-11-23-evening-hip-port-f472e94-dspark-loads-ik2_kvfp4-global)).
- **Published release** (2026-11-23): GitHub release tag `maya-ik2-f472e94-rocm10-gfx1100`, asset
  `maya-ik2-f472e94-rocm10-gfx1100-linux-x64.tar.gz` (the `maya-ik2` binary, our local `serve/` patch, LICENSE and
  BUILD.txt; no ROCm runtime, no model; decode 104.5 / 90.0 tok/s at 512 / 32K vs. 105.9 / 89.9 for the production
  build), sha256
  `2d23cd5151ce8c39c89ee7446643157e63ad4feef9d26325a70a009efe2c9401`. Same day as adoption, per [`sop/update-engine.md`](sop/update-engine.md#publish-a-release).
  The packaged `maya-ik2` was rebuilt without a RUNPATH
  (`7ca635e47ca07d88ff5dafcf54e3b5789b4ea644ce40a799be67a35cb99a50c2`), so its notes carry the
  release's `LD_LIBRARY_PATH` line.
- **Python side**: `serve/` and `tools/` need `numpy jinja2 regex pyyaml tqdm requests pillow psutil
  "jsonschema>=4.18,<5"` (a `.venv` in the checkout); the tokenizer is exported from the GGUF with
  `tools/strata_tokenizer.py --gguf <gguf> --out ik2 --chat-template tools/ik2/chat_template.jinja --check`
  (vocab 200,058, 16/16 round trips).
- **Checks**: `ik2_kernels_test` all passed (31 s, including the 393K attention cases); `ik2_host_ref_test` needs
  a fixture from the author's oracle environment and was not run.
- **Python 3.14**: `tests/ik2_retrieval.py` fails at argparse setup (`badly formed help string`: a bare `%` in the
  `--inventory` help); escape it as `%%` locally before running the retrieval check.
- **Tuned run config** (2026-11-22, [run](../results/20261122-inkling-maya-vs-fork/README.md)): the radeon preset
  plus `IK2_PAGED_KV=1` and `--chunk 2048` (decode +29% and prefill +13% at 262K); `IK2_FLASH_WAVES` 2 or 8 and
  `--chunk 1024` measured no better.
- **Server defaults**: a request without `temperature` decodes greedily unless the run config has a `sampling`
  block; `launch.py` writes the model's `[sampling]` there (vendor `temperature 1.0`, `min_p 0.0`).
- **Launcher wiring**: `local.toml` `engines.maya` points at the checkout (with `build-ik2/` and `.venv/`).
  `launch.py` writes `_tmp/maya/<alias>.maya.json` from the port's own preset
  (`docs/inkling2-mini/ik2-mini-gfx1100.json`, so preset updates arrive with `git pull`) plus the profile's
  `context`, `kv` (-> `IK2_KV`), `chunk` and `env`, then runs `.venv/bin/python serve/server.py --engine maya`
  on `[defaults].port`: an OpenAI and Anthropic API, so the `local-262k` harness provider works unchanged. The
  preset's `reasoning_effort` is dropped (vendor default, as on llama-server). Stop it with Ctrl+C in the
  foreground, or `pkill -INT -f 'serve/server.py --engine maya'` after `--background`: the engine takes up to
  ~50 s to exit (the server then stops it); `pgrep -x maya-ik2` empty means the VRAM is free, and is what
  `launch.py` checks before starting. Verified 2026-11-22: launch, a Gentle-Shell-shaped streaming tool call
  (`model: local-262k`, `bash {"command":"ls -la"}`), stop, and `smoke.py` (96.5 tok/s, no engine left behind).
- **Updating**: `git -C <checkout> fetch origin && git -C <checkout> log --oneline HEAD..origin/hip-port`, read
  the new commits, then `git pull`, re-apply the local edits if they conflict (`git stash` first: the
  `549d734` tool-call fix and the `%%` retrieval fix), rebuild with the `cmake --build` line above, run
  `ik2_kernels_test`, and re-run `python3 scripts/smoke.py inkling2-mini-unc --profile 262k-maya`. Before
  keeping a speed change, repeat `tools/ik2_bench.py` on the same tokens
  ([run](../results/20261122-inkling-maya-vs-fork/README.md)) and the paired GSM8K. Compare with alesha-pro's
  CUDA `main` (`git fetch alesha`) for fixes the port has not picked up yet.
- Reads only IQ4_NL, NVFP4 or Q8_0 experts ([why](models/inkling-2-mini.md#engine-and-variant-review-2026-11-22-second-pass)).

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
