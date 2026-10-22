# SOP: update the llama.cpp engine (Vulkan/HIP)

Reminder from `AGENTS.md`: **never a binary with both Vulkan and HIP compiled in**
(llama.cpp issue #23199: with both backends present, MTP gets routed to ROCm and silently
disabled). One single-backend binary per download/build.

## Re-validation cycle (run this whenever llama.cpp cuts a new release)

1. **Check the upstream diff** between the pinned commit (`docs/ENGINES.md`) and the new release:
   `https://github.com/ggml-org/llama.cpp/compare/b<current>...b<latest>`, filtered on
   `hip|rocm|gfx11|rdna|fattn|mtp|spec|draft|kv-cache`. Record the check in `docs/DECISIONS.md`
   even if nothing relevant changed (see the 2026-09-25 entry for the format). Live checks (states
   confirmed 2026-10-22; #28102, #29393 and #27796 are settled and already in the b11718 baseline):
   - [PR #28391](https://github.com/ggml-org/llama.cpp/pull/28391), open: ngram-mod on by default
     (additive `--spec-type`). If merged, the MTP profile silently becomes MTP + ngram-mod: re-measure
     ([`speculative.md`](../measurements/speculative.md)).
   - [PR #30792](https://github.com/ggml-org/llama.cpp/pull/30792), open: native q8_0 KV in the
     FlashAttention TILE kernel (author: gfx1151 tg +19..+62%); it excludes our q5_1 V. If merged,
     check whether the K q8_0 + V q5_1 pair is covered and re-run the 240K A/B.
   - [PR #30573](https://github.com/ggml-org/llama.cpp/pull/30573), merged 2026-10-19: syncwarp fix in
     `flash_attn_ext_vec`, which our decode path uses. Check it is in the build; include a deep-depth
     case in the A/B.
   - [#28867](https://github.com/ggml-org/llama.cpp/issues/28867), open, gfx1201-only (WMMA dispatch):
     not our GPU; re-check only if the diff touches that dispatch.
   - `fattn.cu`/`fattn-common.cuh`: a GQA-folding (`ncols2`) or quantized-KV TILE change could remove
     the attention-bandwidth bottleneck in
     [`depth.md`](../measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4).
2. **Only if something relevant changed**: build the new engine following "Build a new engine"
   below. The custom `GGML_CUDA_FA_QUANTS` build flags are still required for this build — the
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

1. **Download the right asset** from the `ggml-org/llama.cpp` release, or build it yourself (see
   `docs/ENGINES.md` for the exact recipe used for each engine currently in this repository):
   - Linux ROCm/HIP: `llama-bNNNNN-bin-ubuntu-rocm-10.0-x64.tar.gz`
   - Linux Vulkan: `llama-bNNNNN-bin-ubuntu-vulkan-x64.tar.gz`
   - Windows Vulkan: `llama-bNNNNN-bin-win-vulkan-x64.zip`
   - Windows ROCm/HIP: `llama-bNNNNN-bin-win-rocm-10.0-x64.zip`

2. **Extract into its own folder** under wherever you keep engines (see `local.example.toml`), one
   folder per build — never overwrite an existing engine folder, so you can roll back if the new
   build regresses something.

3. **Update `local.toml`** (`[engines]`) with the new path for that backend.

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
- The step-5 smoke test returns real content and tok/s.

## Known errors

- **K/V mixes that used to work now fall back to CPU**: if the new build changes
  `GGML_CUDA_FA_QUANTS` (HIP) without it showing in `--help`, check the server log ("no FA kernel
  found for this combination" is silent — it shows up as a tok/s drop with no explicit error).
  Compare tok/s against the previous measurement in `docs/measurements/`.
- **Missing rocblas/hipblas DLLs** in Windows HIP builds: the server fails to start with a DLL
  error. Check this before assuming the whole config is broken.
