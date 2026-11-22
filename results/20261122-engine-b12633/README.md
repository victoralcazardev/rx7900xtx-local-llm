# engine b12633: upstream llama.cpp b12633 for ROCm/gfx1100 with the q5_1 V patch rebased

Task T2 of `odd/tasks/engine-b12633-inkling.md` (specs S3 and S5): build the latest upstream
llama.cpp release, **b12633** (`9c10c94`, 2026-11-22), with the recipe of the current `hip-kvmix`
engine plus the local q5_1 V FlashAttention patch rebased, and check the new binary before any
A/B. No model was run with this engine and no performance number is claimed here: the 240K A/B and
the coding suite are task T4.

## Result

| | |
|---|---|
| Engine folder | `~/IA/Motores/llama-b12633-pr30792q51-linux-rocm10-gfx1100-kvmix` |
| Base | tag `b12633`, commit `9c10c94e16ebc4f3ed7c06264a93bf7e019c3f26` (2026-11-22) |
| Patch | `pr30792-q5_1-b12633.patch` (rebased) + `tests-kvmix-cases-b12633.patch` |
| `--version` | `1.0.0-dev (build 12633, commit 9c10c94e1)` |
| Backends in folder | `libggml-hip.so` only (no Vulkan, no CUDA) + 14 `libggml-cpu-*` variants |
| FlashAttention op tests | 30/30 passed on four completed runs (12 of them `q8_0`/`q5_1`); later runs of the same command SIGSEGV inside the system ROCm runtime before the first case — see [Backend-op tests](#backend-op-tests) |
| `MUL_MAT_ID` op tests | 1077/1077 passed |
| `--help` regressions for `models.toml` | none: every flag used by `[defaults]`/profiles keeps its default |

SHA256 (the three files the SOP asks for, plus `test-backend-ops` and `libggml-base`):

| File | SHA256 |
|---|---|
| `llama-server` | `fefb558933a11198a35e4a4ec592b243a3d96df0dd56914c1e938b08ace7ae77` |
| `libggml-hip.so` | `8c80878fb2c3e652b3e5eecb0c6c921676ea22737d6568b787f73fe5c0f1bf23` |
| `libllama-server-impl.so` | `9edc270e068cee19d2f28a28b2aa5a54d5da60166fa7ac4afd73b010a7c697dc` |
| `libggml-base.so.1.0.0` | `1a18d241f009edeb6378be2db58a76419e311ae73f70e1c0dda8bb56687f7f4d` |
| `test-backend-ops` | `cef3147aac27eee0b695994e2b5ba30a0d09dd4e7bdbc4525e4cf96efd0080a4` |

`llama-server` is the thin `GGML_BACKEND_DL` front end, as in every `kvmix` engine: the FA kernels
live in `libggml-hip.so` and the server body in `libllama-server-impl.so`. `b11846`, `b11820`,
`b11718`, `b11160` and v0.9.0 all share the same `llama-server` hash for that reason; this build's
front end is not byte-identical to v0.9.0's (523 upstream commits, including the CLI and server
refactors listed below).

## Build

Source: fresh blobless clone of `ggml-org/llama.cpp` in
`~/IA/Motores/src/llama.cpp-b12633-pr30792q51`, tag `b12633` checked out, patches applied
(below), then the unchanged recipe script:

```bash
cd ~/IA/Motores/src
./build.sh llama.cpp-b12633-pr30792q51      # configure + build into <src>/build-rocm10
cp -a llama.cpp-b12633-pr30792q51/build-rocm10/bin/. \
      ~/IA/Motores/llama-b12633-pr30792q51-linux-rocm10-gfx1100-kvmix/
```

`build.sh` (unchanged from the b11820/b11846/v0.9.0 builds) sources `build-env.sh` (ROCm 10.0.0
TheRock venv, `rocm-sdk path` exports) and configures with:

```
-DCMAKE_HIP_COMPILER="$(hipconfig -l)/clang" -DCMAKE_BUILD_TYPE=Release -DGGML_BACKEND_DL=ON
-DGGML_NATIVE=OFF -DCMAKE_INSTALL_RPATH='$ORIGIN' -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
-DGGML_CPU_ALL_VARIANTS=ON -DGPU_TARGETS=gfx1100 -DGGML_HIP=ON -DHIP_PLATFORM=amd
-DGGML_CUDA_FA_QUANTS="f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0"
```

Build wall time 6 min 21 s (`-j 14`, `llama-server llama-bench llama-perplexity test-backend-ops`),
log `~/IA/Motores/src/logs/build-b12633.log`. Compiler: ROCm 10.0.0 HIP/clang; runtime:
the system ROCm 7.2.4 libraries (`/opt/rocm/lib`), exactly like the other `kvmix` engines. No
compile errors and no compiler warnings beyond the ones the tree already emits.

## Patch rebase

Applied to the clean b12633 tree:

1. `patch -p1 --fuzz=3 < tests-kvmix-cases.patch` — the unchanged local case list (Qwen3.8-shape
   `q8_0`/`q5_1` and `q8_0`/`q8_0` eval cases, plus the two agent-depth perf sets). b12633 added
   `F8_E4M3` FA cases just above the insertion point, so the file hunks landed with fuzz 2 at
   offsets +1266 and +1527 lines. Inserted content is byte-identical to the v0.9.0 file.
2. `pr30792-q5_1.patch`'s two `ggml/src/ggml-cuda/` hunks, applied with `patch -p1 --fuzz=3`
   (the patch's own `tests/test-backend-ops.cpp` hunk is excluded, as in the b11846 and v0.9.0
   builds, because it conflicts with the local case list). 19 of 20 hunks applied mechanically.
3. **One hunk was rebased by hand**: `@@ flash_attn_tile` body (hunk 7, `K_h2`/`V_h2` →
   `K_c`/`V_c` and `stride_K2`/`stride_V2` → `int64_t stride_K`/`stride_V`). b12633 changed one
   context line only — the mask base pointer now also adds `nb32*(head0 % ne32)` for per-head
   masks — so the hunk could not match as text. The replacement applied is exactly the patch's own
   (no new behaviour, no extra logic).

Rebased patches exported from `git diff` on the patched tree:

| File | Content |
|---|---|
| `pr30792-q5_1-b12633.patch` | `ggml/src/ggml-cuda/fattn-tile.cuh` + `fattn.cu`: native `q8_0`/`q8_0`, `f16`/`q8_0` and `q8_0`/`q5_1` in the TILE kernel, `ne[1] <= 8` guard, no f16 scratch for those pairs |
| `tests-kvmix-cases-b12633.patch` | the same local test cases, re-exported against the b12633 test file |

Verification that the rebase is equivalent: the `+`/`-` line set of `pr30792-q5_1-b12633.patch`
equals the line set of `results/20261022-fa-native-q8q51-tile-op-level/pr30792-q5_1.patch` (282 vs
255 lines; the 27-line difference is exactly that patch's excluded test-file hunk). Line counts
changed in the same files and the same proportions as on v0.9.0 (`fattn-tile.cuh` 237 changed lines,
`fattn.cu` 18, tests 20).

The v1.0.0 FlashAttention symbol rename did **not** break the patch: `flash_attn_tile`,
`flash_attn_tile_iter`, `flash_attn_tile_iter_KQ`, `flash_attn_tile_load_tile`,
`launch_fattn_tile_switch_ncols1/2` and `ggml_cuda_flash_attn_ext_tile_case` all still exist with
the same signatures in b12633; the rename touched CI symbol names
([#32331](https://github.com/ggml-org/llama.cpp/pull/32331)) and the `launch_fattn` parameter list is
unchanged (`need_f16_K`, `need_f16_V`, `stream_k`, `use_sparse`, `warp_size`).

## Upstream diff v0.9.0 (`cd959ba`) .. b12633 (`9c10c94`)

`git rev-list --count cd959ba..b12633` = **523 commits**; the range contains the v1.0.0 tag
(`b1b770d`, 2026-11-13), and b12633 reports `1.0.0-dev`. 55 commits match
`hip|rocm|gfx11|rdna|fattn|flash|mtp|spec|draft|kv-cache|inkling|nvfp4`. The PRs the SOP watchlist
asks about are all still open — none of them is in b12633:

| PR | State (GitHub API, 2026-11-22) | Effect on this engine |
|---|---|---|
| [#30792](https://github.com/ggml-org/llama.cpp/pull/30792) native `q8_0` KV in the FA TILE kernel | **open**, not merged (head `40f0d07`, updated 2026-11-21) | still `q8_0`-only; the local patch (this one) stays needed for the V `q5_1` pair |
| [#31234](https://github.com/ggml-org/llama.cpp/pull/31234) native `q4_0`/`q8_0` KV in `flash_attn_tile` | **open**, not merged (head `e40ab5c`, updated 2026-11-20) | not merged, so no gfx1100 config row question yet; re-check if it lands |
| [#32201](https://github.com/ggml-org/llama.cpp/pull/32201) HIP D256 d-partitioned WMMA FA for RDNA3 | **open draft** (head `83d40be`, updated 2026-11-13) | not in b12633 |
| [#32455](https://github.com/ggml-org/llama.cpp/pull/32455) "fa split for gfx11" | **open** (head `1c6232a`, updated 2026-11-20) | not in b12633 |

Because #30792 and #31234 are unmerged, the "is K `q8_0` + V `q5_1` covered on gfx1100" check does
not apply; the rebased local patch is still the only way to get that pair.

Commits from the filtered list that matter here:

- **Inkling-2-Mini** (task T5 depends on these): `5c008e000` model support (#32217), `29b52d398`
  `Inkling 2 Mini` (#32694), `690b87d88` `inkling2_loop` loop-slot re-share after the scale pass
  (#32704), `8af68d486` attention-mask fixes (#32429), `4ddf2b947` chat parser (#32381),
  `d998c676f` mmproj conversion fix (#32430), `dd099a6bf` image-token placement (#32294).
- **FlashAttention / CUDA-HIP kernels**: `278a89cb7` `_sync` warp-primitive refactor (#31617),
  `77e2db8ca` sm70 FA config case (#27997), `9d7b2d739` FA MMA head sizes 40/72 (#30285),
  `202c1a229` FP8 KV-cache (#28392), `054a1babf` K/V read-order rotation (#32407), `7f24aacde` CPU
  FA accumulates V in F32 (#29810), `900f01ba0` CI FA symbol-name update (#32331).
- **HIP/ROCm**: `432433637` fixed BLAS workspace instead of one rocBLAS allocation per call (#31838),
  `2e53a0bab`/`b79696f1f` stream_k + GCN MMQ tuning (#30022, #30021), `05db09a4d` MoE regression fix
  on HIP (#32344), `2d8a32502` PAD_REFLECT_1D grid within the HIP limit (#32179),
  `8cb0d98cc` NVFP4 CDNA3 scale fix (#32790), `47fe13331` GDN mma on CDNA (#31327).
- **Speculative decoding / MTP**: `a8fad21e9` MTP reads target hidden states from a device buffer
  (#31927), `040ce199a` MTP conv snapshots in one `set_rows` (#31660), `a2b301831` no MoE cache for
  the draft model (#31497), `32bdc3a89` DFlash refactor (#32016), `7874988b4` `--spec-draft-p-min`
  warning (#31294), `359dc5858` spec-dec functionality test (#31027), `6b01a4767` CI spec-dec
  triggers (#32281).
- **KV cache / graph**: `e152332a1` reference-counted checkpoints (#30137), `202c1a229` FP8 KV.
- **RDNA-specific**: `e3c3f666a` RDNA1 MMVQ table (#32389), `c7518dbec` MMVQ `ne11` gate for
  RDNA3_5 (#32308), `a001af915` gfx1013 in rdna1 (#32236), Vulkan RDNA3/4 paths (#31323, #30280,
  #31804) — Vulkan only, not this build.

## `--help` diff against the v0.9.0 engine

Captured with `<engine>/llama-server --help` (no model, no server left running):
`help-v0.9.0.txt` (753 lines), `help-b12633.txt` (783 lines), full `diff -u` in `help-diff.txt`.
Long options: 336 → 343.

Flags used by `models.toml` `[defaults]` and by the profiles (from
`scripts/launch.py qwen38-iq3s-mtp --profile 262k-q8q51-mtp --dry-run` and the same for
`huihui-iq3s-mtp`): `-m --port -c -ctk -ctv --temp --top-p --top-k --min-p -fa -np
--ctx-checkpoints -ngl --metrics --spec-type --spec-draft-n-max -ub --reasoning-effort --cache-ram`.
**Every one of them has the same default in both binaries**:

| Flag | v0.9.0 | b12633 |
|---|---|---|
| `--port` | 9931 | 9931 |
| `-c` | 0 (from model) | 0 (from model) |
| `-ctk` / `-ctv` | f16 / f16 | f16 / f16 |
| `--temp` / `--top-p` / `--top-k` / `--min-p` | 0.80 / 0.95 / 40 / 0.05 | unchanged |
| `-fa` | auto | auto |
| `-np` | -1 (auto) | -1 (auto) |
| `--ctx-checkpoints` | 32 | 32 |
| `-ngl` | auto | auto |
| `--metrics` | disabled | disabled |
| `--spec-type` | none | none |
| `--spec-draft-n-max` | 3 | 3 |
| `-ub` | 512 | 512 |
| `--reasoning-effort` | default | default |
| `--cache-ram` | 8192 | 8192 |

Other changes in the CLI:

- **Added (8)**: `--allow-unauthenticated-tools`, `--media-allow-private-urls`,
  `--moe-cache-cpu-share`, `--ple` (alias `--shard`), `--tts-lang`, `--tts-voice`,
  `--ui-mcp-proxy-allow-private-urls`.
- **Removed (1)**: `-dt, --defrag-thold` (deprecated).
- **`--spec-type` values**: two new ones, `draft-dflash2` and `draft-lilicorr`; the existing names
  (including the production `draft-mtp,ngram-map-k4v`) and the `none` default are unchanged.

So no `models.toml` flag loses its effect in this build, and the launcher needs no change.

## Backend-op tests

The engine folder's own `test-backend-ops`, GPU otherwise idle (no `llama-server` running, 3 % VRAM
used by the desktop):

| Command | Result |
|---|---|
| `test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=q8_0'` | **30/30 tests passed** on four completed runs: the 12 local `q8_0`/`q5_1` cases (kv 1024 at nb 1, 2, 3, 4, 8, 9, 64; kv 113 at nb 1; kv 1025 at nb 4 with permuted KV; kv 1024 at nb 3 with logit softcap; kv 16384 at nb 1 and 4), the 7 local `q8_0`/`q8_0` comparison cases and 11 upstream `q8_0` cases (pristine b12633 reports 11/11 for the same filter) |
| `test-backend-ops test -b ROCm0 -o MUL_MAT_ID` | **1077/1077 tests passed** (`raw/test-mul-mat-id.log`) |
| `test-backend-ops support -b ROCm0 -o FLASH_ATTN_EXT` | every case `SUPPORTED`, 2/2 backends passed (`raw/test-flash-attn-support.log`) |
| `test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=128'` | **not obtained**: the process dies before the first case (below) |

### Blocker: SIGSEGV inside the system ROCm runtime before the first FA case

After those four completed runs, **every** FA run of this binary started dying with `SIGSEGV`
(exit 139) before the first test case printed, in `libamdhip64.so.7` (the system ROCm 7.2.4 runtime,
not the ROCm 10 build toolchain):

```
ggml_backend_cuda_buffer_init_tensor()
  -> cudaMemsetAsync(padding of a quantized tensor, hipStreamPerThread)   [first HIP memset in the process]
  -> hipMemsetAsync()/hipStreamCreateWithFlags()  -> SIGSEGV in libamdhip64.so.7
faulting instruction: vmovdqa %ymm1,0xc0(%rdi)   (host-side store in the runtime)
```

Backtraces and register dumps in `raw/gdb-backtrace.txt`, crash log in
`raw/test-flash-attn-hsk256-q8_0-crash.log`. Frequency, measured in the same time window and with
the same command:

| Binary | Runs that completed | Runs that SIGSEGV'd |
|---|---|---|
| this engine (b12633 + rebased patch) | 4, all 30/30, before ~17:00 (three with `GGML_CUDA_NO_PINNED=1`, one without any environment change) | 74 consecutive attempts after ~17:00, every one exit 139: 40 plain, 22 with `GGML_CUDA_NO_PINNED=1`, and the rest with `HSA_ENABLE_SDMA=0`, `setarch -R` and `-j 4` |
| **pristine b12633** (`llama.cpp-b12633-clean`, same recipe, no patch) | 2/3 and earlier 3/3 | 1/3 in the same window; 2/2 under gdb |
| **adopted v0.9.0 engine** (`llama-v0.9.0-pr30792q51-...-kvmix`) | 2/3 in the same window | 1/3 in the same window (earlier batches: 7/8 and 8/8 crashing) |

The crash is therefore **pre-existing in this machine's runtime/driver combination**: the adopted
engine and the unpatched b12633 both die the same way, intermittently, and `MUL_MAT_ID` (no FA
context, no quantized-KV padding memset) passes 1077/1077 at the same time. It is not a numerical
failure of the rebased kernels: the four runs that completed passed all 30 cases, including the 12
`q8_0`/`q5_1` ones, with the test tolerance. It is also extremely layout-sensitive — the same binary
flips between pass and SIGSEGV when a single environment variable is added or removed — which
points at the runtime's host/device pointer handling inside `hipMemsetAsync`, not at ggml code.
The crash rate of this build is higher than that of the pristine build in the same window; whether
that is only the larger `libggml-hip.so` shifting device addresses or something else could not be
separated before the correction budget ran out.

**Re-run before trusting the build**: `hsk=128` (Inkling-2-Mini `head_dim`) and the 30/30 FA set
have to be re-measured when the runtime stops crashing — for example after a graphics-session
restart, or with a ROCm 10 runtime on the library path. If FA runs still die with the pristine
b12633 binary at the same time, it is the environment; if only this build dies, the rebase needs
another look.

## Not done here (out of this task)

- The 240K A/B against the current engine, the coding suite and the smoke test (T4), and any
  `llama-server` run with a model.
- `hsk=128` FA counts (blocked above) and a rerun of the 30/30 set.
- `results/INDEX.md`, `docs/ENGINES.md`, `docs/DECISIONS.md` and `CHANGELOG.md` entries: outside
  this task's edit surface.

## Files

| File | Content |
|---|---|
| `pr30792-q5_1-b12633.patch` | rebased kernel patch (apply with `git apply` on tag b12633) |
| `tests-kvmix-cases-b12633.patch` | local FA test cases, re-exported for b12633 |
| `help-v0.9.0.txt`, `help-b12633.txt`, `help-diff.txt` | `llama-server --help` of both engines and their full diff |
| `raw/` | test logs (trimmed to head + summary), crash captures, gdb backtraces (see `raw/README.txt`) |
