# engine Inkling RDNA3 fork: GodGMN/llama.cpp `inkling-rdna3` (`cb0e46960`) for ROCm/gfx1100

Build and backend-op check of the third-party experimental fork
https://github.com/GodGMN/llama.cpp, branch `inkling-rdna3`, as the engine side of task T5
(`odd/tasks/engine-b12633-inkling.md`, specs S1 and S5): Inkling-2-Mini support and its fused HIP
kernels live only in that fork, so it is built and verified as published, **without** the local
`pr30792-q5_1` patch, before any model is loaded. **No model was run with this engine and no
performance number is claimed here**: the fork's own speed/context claims are quoted below and
attributed to its author. The 262K fit and the smoke test are the parent's work.

## Result

| | |
|---|---|
| Engine folder | `~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix` |
| Fork / branch | `GodGMN/llama.cpp` @ `inkling-rdna3` (not an upstream PR) |
| Commit | `cb0e469607c19b63b3d06a8b654fcebdd76fb889` (2026-11-21 18:59 +0100), short `cb0e46960` |
| Base | tag `b12600` = `29b52d398b294509746ec0a3f28948a3107c0213`, plus 6 commits: `711dc932f` (upstream #32704 backport) and the 5 fork commits (`raw/commits.txt`) |
| `--version` | `1.0.0-dev (build 12606, commit cb0e46960)` |
| Backends in folder | `libggml-hip.so` only (no Vulkan, no CUDA) + 14 `libggml-cpu-*` variants |
| Devices | `ROCm0: AMD Radeon RX 7900 XTX (24560 MiB)`; CPU not listed as a compute device by the server |
| Local patch | none: the fork is built exactly as published (no `pr30792-q5_1`, no `tests-kvmix-cases`) |
| `INK_REL_BIAS` op tests | **9/9 passed** |
| `FLASH_ATTN_EXT -p 'hsk=128'` | **859/859 passed** (2/2 backends) |
| Every case the fork adds (`-o 'INK_.*'`) | **63/63 passed** (`INK_REL_BIAS` 9, `INK_FA_REL_BIAS` 24, Inkling graph patterns 23, `INK_REVIEW` 7, plus its own `test-ink-rel-bias` target `PASSED`) |

SHA256 (whole table in `raw/sha256.txt`):

| File | SHA256 |
|---|---|
| `llama-server` | `fefb558933a11198a35e4a4ec592b243a3d96df0dd56914c1e938b08ace7ae77` |
| `libggml-hip.so` | `0734ce9771709d07b75473095cccd93c0b8e549766d0819ebc8aa2dc94367096` |
| `libllama-server-impl.so` | `4882f85ec1413b163935724a9f32b2186010e174b79f4c900faddda8962b22d1` |
| `libggml-base.so.1.0.0` | `42aee20da0ae6dc205b783fe02f09094e8d77422dbe721f5eb33a7f026d19749` |
| `test-backend-ops` | `d2d7f0f770e47718ee0bb5598592f4319a975aa3f2f731271fbf040f69a1a2fb` |
| `test-ink-rel-bias` | `07b47c29ad65b04d1146d48e5a3b29931ebb313a32ff3a072c5e962970134ee8` |

`llama-server` is the thin `GGML_BACKEND_DL` front end: its hash is identical to the
[`b12633` engine](../20261122-engine-b12633/README.md)'s because the fork's changes land in
`libggml-hip.so` / `libllama.so`, not in the front-end code. The whole HIP/FA code difference
against b12633 is in this `libggml-hip.so` (`0734ce97…` here vs. `8c80878f…` there).
`libllama-server-impl.so` differs between any two builds (the web UI is downloaded at configure
time).

## Build

Source: ordinary clone of the fork with the branch checked out, then the unchanged recipe script
(`~/IA/Motores/src/build.sh`, same file as the b11820/b11846/b12633/v0.9.0 builds):

```bash
cd ~/IA/Motores/src
git clone --branch inkling-rdna3 https://github.com/GodGMN/llama.cpp.git llama.cpp-inkling-rdna3
./build.sh llama.cpp-inkling-rdna3            # configure + build into <src>/build-rocm10
cp -a llama.cpp-inkling-rdna3/build-rocm10/bin/. \
      ~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix/
```

`build.sh` sources `build-env.sh` (ROCm 10.0.0 TheRock venv, `rocm-sdk path` exports; **HIP compiler
Clang 23.0.0**) and configures exactly the recipe of `docs/ENGINES.md`:

```
-DCMAKE_HIP_COMPILER="$(hipconfig -l)/clang" -DCMAKE_BUILD_TYPE=Release -DGGML_BACKEND_DL=ON
-DGGML_NATIVE=OFF -DCMAKE_INSTALL_RPATH='$ORIGIN' -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
-DGGML_CPU_ALL_VARIANTS=ON -DGPU_TARGETS=gfx1100 -DGGML_HIP=ON -DHIP_PLATFORM=amd
-DGGML_CUDA_FA_QUANTS="f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0"
```

Build wall time **8 min 01 s** (`-j 14`, targets `llama-server llama-bench llama-perplexity
test-backend-ops`), log `~/IA/Motores/src/logs/build-inkling-rdna3.log`. The fork's own
oracle was built separately from the same configured tree, so the configure flags above are not
modified by it:

```bash
cd ~/IA/Motores/src/llama.cpp-inkling-rdna3
cmake --build build-rocm10 -j 14 --target test-ink-rel-bias      # 1.7 s
```

No compile errors. 19 warnings, **all** the tree's existing
`-Wdeprecated-enum-enum-conversion` (`ggml_scale_mode` vs. `ggml_scale_flag`) in
`tools/mtmd/**` and `tests/test-backend-ops.cpp`; none from the fork's `ggml-cuda/inkling.*`,
`mmvq.*` or `fattn-*` changes.

### Runtime fix (ROCm 10.1 from CachyOS crashes every HIP program)

As for the other `kvmix` engines, the runtime `libamdhip64.so.7` is Arch's generic 10.1 build,
symlinked into the engine folder where the build's `$ORIGIN` RUNPATH finds it:

```bash
ln -sfn ~/IA/Motores/rocm-10.1-arch-hip/pkg/opt/rocm/lib/libamdhip64.so.7.16.0-0000000 \
        ~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix/libamdhip64.so.7
ldd ~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix/libggml-hip.so | grep amdhip
```

It prints `libamdhip64.so.7 =>` the engine folder's own copy of that symlink (`$ORIGIN`), not
`/opt/rocm/lib`.

No run today hit the intermittent `SIGSEGV` inside `libamdhip64` that the b12633 build suffered on
2026-11-22 (`test-backend-ops`, `hsk=128` included, completed on the first attempt).

## Backend-op tests

Run from the engine folder (the `libamdhip64.so.7` symlink above resolves there), GPU otherwise
idle, no `llama-server` running, ~0.9 GB VRAM used by the desktop:

| Command | Result |
|---|---|
| `./test-backend-ops test -b ROCm0 -o INK_REL_BIAS` | **9/9 tests passed** (`raw/test-ink-rel-bias-op.log`): `type_mask` f16/f32 × `type_dst` f16/f32, `n_rel=1025`, `n_head=24`, `n_kv` 256/512/1280, `n_tokens` 1/4/6/8, 1-2 streams, strided indices and out-of-band indices |
| `./test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=128'` | **859/859 tests passed**, 2/2 backends (`raw/test-fa-hsk128.log`): every supported K/V type combination at `hsk=128` (the `head_dim` of Inkling-2-Mini), including 11 `type_K=q8_0` cases and both `f8_e4m3`/`f8_e4m3` ones; 19 of the 878 selected cases report `not supported` and are not counted (K types this `GGML_CUDA_FA_QUANTS` build does not compile: `q1_0`, `q2_0`, `q5_0`, `q5_1`, `iq4_nl`, `f32`, and three unpaired `q8_0`/`f16` mixes) |
| `./test-backend-ops test -b ROCm0 -o 'INK_.*'` | **63/63 tests passed** (`raw/test-ink-all.log`): the fork's whole new case set — `INK_REL_BIAS` 9, `INK_FA_REL_BIAS` 24 (f16/q8_0/q4_0, T=1..64, head offsets), `INK_clip`/`clip_scaled`/`situ`/`ctrl`/`mix`/`mix1`/`conv`/`dconv` 23 (the fused decode patterns, each against the unfused chain on the CPU backend), `INK_REVIEW` 7 |
| `./test-ink-rel-bias` | **PASSED** (`raw/test-ink-rel-bias-bin.log`): 4 oracle cases of the fused op against the original unfused chain (CPU), cells up to position 1048000; then FA-with-bias parity for f16/`q8_0`/`q4_0` FA at T=1/7/64 on `ROCm0` and CPU — `0 of 196608 differ` on GPU, i.e. the GPU kernel matches the unfused chain bit for bit |

Not exercised by these runs: the `q8_0` K + `q5_1` V pair, which this build compiles in
(`GGML_CUDA_FA_QUANTS` above) but the fork's and upstream's test case list never generates
(`q5_1` does not appear in `tests/test-backend-ops.cpp`; our own `tests-kvmix-cases.patch` was
deliberately not applied). Any `q5_1` V claim needs that patch or a model run.

## What the fork author claims (not our measurements)

Quoted from the branch's `docs/inkling-rdna3.md` (commit `cb0e46960`), **these are the fork
author's numbers, reproduced here only so the parent can decide what to A/B**:

> Tested only on: RX 7900 XTX (gfx1100, 24 GB), ROCm 7.2.1, Ubuntu 24.04 container,
> `ggml-org/Inkling-2-Mini-GGUF` IQ4_NL with `mmproj-F16`. **Not tested on NVIDIA** or on
> any other AMD card.

| (author's) | b12600 | this branch |
|---|---|---|
| `llama-bench` tg128 | 31.9 t/s | 64.0 t/s |
| tg128 at 16k depth | 30.9 | 63.5 |
| pp4096 | 854 | 1802 |
| pp4096 at 16k depth | 492 | 1467 |
| Largest context that fit with the vision projector | 131072 (q8_0 K/V) | 393216 (q4_0 K/V) |
| wikitext-2 PPL (ctx 2048, q8_0 K/V) | 5.9465 | 5.9472 |

> At 393216 context with q4_0 K/V, a 382k-token prompt with five 4K images at the end
> retrieved 10 of 10 facts spread through the text, at a 23.2 GB VRAM peak.

> 4. Tests: `test-backend-ops` cases for every new kernel and fused path (CPU vs GPU),
> plus `test-ink-rel-bias`, which compares the bias bit for bit against the original
> unfused chain up to positions past 1M. 10,000+ cases pass on gfx1100.

The author's own environment is ROCm **7.2.1** with IQ4_NL; this machine runs the fork on the
Arch 10.1 runtime with `IQ4_NL`/AD-Q4_K untested so far, so none of the numbers above transfers
without our own run.

## Scope warnings (the fork's own, and they are binding for any model we load)

Quoted verbatim from `docs/inkling-rdna3.md` § "Scope: what can affect other models or cards":

> - Inkling only: the model code, `GGML_OP_INK_REL_BIAS`, and the flash-attention bias
>   path, which is only taken when an op carries the bias.
> - RDNA3 only: the mmvq table change, limited to Q8_0/IQ4_NL weights and single-token
>   matvecs.
> - **Every model, every CUDA/HIP card:** the q8_1 input cache on single-token matvecs.
>   Disable it with `GGML_CUDA_NO_Q8_CACHE=1`.
> - **Any model whose graph matches the patterns:** the fusion matchers. They are shaped
>   for Inkling but run on every graph. Disable them with `GGML_INK_NO_FUSE=1`.

Both escape hatches exist in the built binary: `GGML_CUDA_NO_Q8_CACHE` at
`ggml/src/ggml-cuda/mmvq.cu:1562`, `GGML_INK_NO_FUSE` at `ggml/src/ggml-cuda/ggml-cuda.cu:4507`.
Consequence for us: this engine is a **fork-scope** build — do not point the Qwen default
profile at it, and if it is ever measured against the default model, run both arms with
`GGML_CUDA_NO_Q8_CACHE=1 GGML_INK_NO_FUSE=1` to isolate the Inkling-only kernels.

## Not done here (out of this task)

- Any `llama-server` run, model load, 262K fit, smoke test, PPL or benchmark (parent's work).
- The local `pr30792-q5_1` patch: deliberately not applied, per the task.
- `docs/ENGINES.md`, `docs/ENGINES-EXPERIMENTS.md`, `docs/DECISIONS.md`, `results/INDEX.md` and
  `CHANGELOG.md` rows: outside this task's edit surface.

## Files

| File | Content |
|---|---|
| `raw/commits.txt` | the 6 commits on top of tag `b12600` |
| `raw/version.txt`, `raw/devices.txt` | `--version` and `--list-devices` of the built server |
| `raw/sha256.txt` | SHA256 of every binary and shared library in the engine folder |
| `raw/test-*.log` | the four test runs above, ANSI escapes stripped |
| `raw/README.txt` | which command produced each raw file |
