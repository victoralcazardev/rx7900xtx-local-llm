# SOP: update the llama.cpp engine (Vulkan/HIP)

Reminder from `AGENTS.md`: **never a binary with both Vulkan and HIP compiled in**
(llama.cpp issue #23199: with both backends present, MTP gets routed to ROCm and silently
disabled). One single-backend binary per download/build.

## Re-validation cycle (run this whenever llama.cpp cuts a new release)

1. **Check the upstream diff** between the pinned commit (`docs/ENGINES.md`) and the new release:
   `https://github.com/ggml-org/llama.cpp/compare/b<current>...b<latest>`, filtered on
   `hip|rocm|gfx11|rdna|fattn|mtp|spec|draft|kv-cache`. Record the check in `docs/DECISIONS.md`
   even if nothing relevant changed (see the 2026-09-25 entry for the format). Live checks (states
   confirmed 2026-10-23; #28102, #29393 and #27796 are settled and already in the b11718 baseline):
   - [PR #28391](https://github.com/ggml-org/llama.cpp/pull/28391), open: ngram-mod on by default
     (additive `--spec-type`). If merged, the MTP profile silently becomes MTP + ngram-mod: re-measure
     ([`speculative.md`](../measurements/speculative.md)).
   - [PR #30792](https://github.com/ggml-org/llama.cpp/pull/30792), open: native q8_0 KV in the
     FlashAttention TILE kernel (author: gfx1151 tg +19..+62%); it excludes our q5_1 V. The engine in
     use carries it plus a local q5_1 V loader
     ([results](../../results/20261023-d1-pr30792q51-240k/README.md)): any newer base needs the patch
     rebased. If merged, check whether the K q8_0 + V q5_1 pair is covered; drop the local patch only
     if the 240K A/B matches.
   - [PR #31234](https://github.com/ggml-org/llama.cpp/pull/31234), open (checked 2026-11-11): native quantized
     KV in `flash_attn_tile` for CUDA/HIP, the form a maintainer asked for instead of #30792 (PR #30803).
     Measured on RDNA4 only (qwen35 27B q8_0/q8_0, tg at 131K x1.60); the table shows q4_0/q4_0 and q8_0/q8_0,
     not K q8_0 / V q5_1. It compiles "q4_0, q4_1, q5_0, q5_1, q8_0 and bf16 ... in any K/V combination",
     but "A shape runs natively only if the GPU has a config row for it, and so far only gfx1201 has
     rows": on gfx1100 it needs a row before it can replace the patch. If it merges with a gfx1100 row
     covering that pair, test it against `pr30792-q5_1.patch` and drop the patch.
   - [PR #30885](https://github.com/ggml-org/llama.cpp/pull/30885), merged 2026-10-23 (after b11840):
     bf16 WMMA operand type for gfx11/gfx12, fixes the HIP build on LLVM 23. Needed only when the
     build toolchain moves past ROCm 10.0.0's LLVM.
   - [PR #30573](https://github.com/ggml-org/llama.cpp/pull/30573), merged 2026-10-19: syncwarp fix in
     `flash_attn_ext_vec`, which our decode path uses. Check it is in the build; include a deep-depth
     case in the A/B.
   - [#28867](https://github.com/ggml-org/llama.cpp/issues/28867), open, gfx1201-only (WMMA dispatch):
     not our GPU; re-check only if the diff touches that dispatch.
   - `fattn.cu`/`fattn-common.cuh`: a GQA-folding (`ncols2`) or quantized-KV TILE change could remove
     the attention-bandwidth bottleneck in
     [`depth.md`](../measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4).
2. **Only if something relevant changed**: build the new engine following "Build a new engine"
   below ([`scripts/build_engine.py`](../../scripts/build_engine.py) runs the whole recipe in one
   command). The custom `GGML_CUDA_FA_QUANTS` build flags are still required for this build — the
   official binaries don't ship K q8_0 + V q5_1/q4_1 FlashAttention kernels.
3. **One quick A/B at 240K** (~30 min under `systemd-inhibit`, nothing else using the GPU): run
   `bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 1 --extra "-ub 256"`
   once with the new build and once with the current one (`BENCH_SERVER`), back to back. 240K
   exercises the deep FlashAttention + MTP path the profile depends on; temperature 0 makes the
   text comparable. Within an arm, cached reps agree within 1% and give the same text
   ([2026-10-18](../../results/20261018-engine-b11718-vs-b11454-240k/README.md)), so one rep after
   the warm-up is enough. **Adopt** when tg is within 2% per task, or when a task whose greedy text
   differs is slower only by its lower MTP acceptance (cost per step unchanged, as on 2026-10-18).
   **Then** run the coding suite once on the new build (`bench/coding_suite.py --run`) and compare
   it with the last baseline (`--compare`); keep the current build on a regression. No 190K or
   retrieval run unless step 1 found a FlashAttention/KV change.
4. **Adopt or discard**: record the outcome in `docs/DECISIONS.md` and, if adopted, update
   `docs/ENGINES.md` (commit, flags, SHA256) and `models.toml`. Keep the A/B run's output under
   `results/` -- immutable, never overwritten in place (see `docs/STYLE.md` §7).

## Build a new engine

The `hip-kvmix` engine (K `q8_0` + V `q5_1` FlashAttention kernels) is built by one command; the
recipe — configure flags, targets, post-build checks — lives in
[`scripts/build_engine.py`](../../scripts/build_engine.py), not outside this repository. Released
binaries stay an option for every other backend, or when the local patches are not needed.

### Own `hip-kvmix` build: `scripts/build_engine.py`

```bash
python3 scripts/build_engine.py --ref b12633 \
  --patch engine-patches/tests-kvmix-cases-b12633.patch \
  --patch engine-patches/pr30792-q5_1-b12633.patch --dry-run   # print every command, run nothing
```

Drop `--dry-run` to build. What it does, in order:

1. **Toolchain**: builds with the ROCm toolchain already on `PATH` (`hipconfig`, `ROCM_PATH`,
   `CMAKE_PREFIX_PATH`). Activate it first when it is not the system ROCm install: the
   `build-env.sh` of [`docs/ENGINES.md`](../ENGINES.md#llama-b11160-linux-rocm10-gfx1100-kvmix-previous-hip-kvmix-engine)
   exports those for the ROCm 10.0 TheRock venv. The toolchain in use goes into `BUILD.txt`.
2. **Source**: `<src_root>/llama.cpp-<ref>`, cloned blobless when missing and reused only when it
   sits at exactly that ref with no local changes. A dirty checkout is refused, not reset.
3. **Patches**: `engine-patches/` (see its [README](../../engine-patches/README.md)) apply in the
   order given, with `git apply` and no fuzz. A patch that does not apply stops the build naming
   the patch and its files: rebase it onto the new base in a scratch worktree, export the result
   with `git diff`, add it to `engine-patches/` — a human job, never an automatic merge.
4. **Engine folder**: `<engines_root>/llama-<ref>[-<patch-tag>]-linux-rocm-gfx1100-kvmix`; the tag
   comes from the patches that change a kernel (a `tests/`-only patch adds none). An existing
   engine folder is **refused**, so a published build always stays as the rollback.
5. **Runtime symlink**: when `[build] hip_runtime_lib` is set in `local.toml`, it is symlinked into
   the new folder as `libamdhip64.so.7` and `ldd libggml-hip.so` must resolve it inside the folder
   (the CachyOS ROCm 10.1 workaround,
   [`install.md`](install.md#known-errors)).
6. **Checks**: `llama-server --version`, HIP only (no `libggml-vulkan`/`libggml-cuda`),
   `test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=q8_0'` with its pass/fail
   count, and the SHA256 of `llama-server` and `libggml-hip.so`. All of it, plus the ref, commit,
   toolchain and patch hashes, is written to the engine's `BUILD.txt`. A failed check leaves the
   folder and `BUILD.txt` in place (evidence) and exits non-zero.
7. **Adopt**: point `[engines] hip-kvmix` in `local.toml` at the new folder, then run the two steps
   below. An engine folder from a discarded build is deleted by hand.

Exit codes: `0` built and every check passed, `1` build or check failed, `2` configuration error
or refused (existing engine folder, missing patch, patch that does not apply).

### Alternative: a released binary

1. **Download the right asset** from the `ggml-org/llama.cpp` release (see
   `docs/ENGINES.md` for the recipe and the SHA256 of each engine in this repository):
   - Linux ROCm/HIP: `llama-bNNNNN-bin-ubuntu-rocm-10.0-x64.tar.gz`
   - Linux Vulkan: `llama-bNNNNN-bin-ubuntu-vulkan-x64.tar.gz`
   - Windows Vulkan: `llama-bNNNNN-bin-win-vulkan-x64.zip`
   - Windows ROCm/HIP: `llama-bNNNNN-bin-win-rocm-10.0-x64.zip`

2. **Extract into its own folder** under wherever you keep engines (see `local.example.toml`), one
   folder per build — never overwrite an existing engine folder, so you can roll back if the new
   build regresses something. The ROCm 10.1 runtime symlink of step 5 above applies here too.

3. **Update `local.toml`** (`[engines]`) with the new path for that backend.

### Either way: re-check the flags and smoke-test

4. **Re-check every default flag against the new binary's real `--help`** before assuming
   `[defaults].flags` in `models.toml` still apply (a default can change between versions or
   backends):
   ```
   <new-engine>/llama-server --help
   ```
   Compare each `[defaults]` flag against the real default. If one no longer changes anything, drop
   it from the TOML (rule: "a flag only if it changes something relative to the default").

5. **Smoke-test one representative model** per architecture in use:
   ```
   python3 scripts/smoke.py qwen38-iq3s-mtp --profile 262k-q8q51-mtp --backend hip-kvmix
   ```

## How to verify

- `python3 scripts/check-sync.py` reports no new PROBLEM (the "engine pending" WARNING disappears
  for the backend you just updated).
- The engine's `BUILD.txt` holds the commit, the patches with their SHA256, the flags, the
  toolchain and the FlashAttention op-test counts.
- The smoke test of step 5 returns real content and tok/s.

## Known errors

- **K/V mixes that used to work now fall back to CPU**: if the new build changes
  `GGML_CUDA_FA_QUANTS` (HIP) without it showing in `--help`, check the server log ("no FA kernel
  found for this combination" is silent — it shows up as a tok/s drop with no explicit error).
  Compare tok/s against the previous measurement in `docs/measurements/`.
- **Missing rocblas/hipblas DLLs** in Windows HIP builds: the server fails to start with a DLL
  error. Check this before assuming the whole config is broken.
