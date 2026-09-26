# SOP: update the llama.cpp engine (Vulkan/HIP)

Reminder from `AGENTS.md`: **never a binary with both Vulkan and HIP compiled in**
(llama.cpp issue #23199: with both backends present, MTP gets routed to ROCm and silently
disabled). One single-backend binary per download/build.

## Re-validation cycle (run this whenever llama.cpp cuts a new release)

1. **Check the upstream diff** between the pinned commit (`docs/ENGINES.md`) and the new release:
   `https://github.com/ggml-org/llama.cpp/compare/b<current>...b<latest>`, filtered on
   `hip|rocm|gfx11|rdna|fattn|mtp|spec|draft|kv-cache`. Record the check in `docs/DECISIONS.md`
   even if nothing relevant changed (see the 2026-09-25 entry for the format). Specifically check
   whether the diff includes [PR #28102](https://github.com/ggml-org/llama.cpp/pull/28102)
   (FlashAttention tuning change that may regress gfx1100 deep-prefill performance) — if it does,
   the A/B below should include a deep-depth case, not just the default couple of depths (see
   `docs/SOURCES.md`). Also check whether the diff includes
   [PR #29393](https://github.com/ggml-org/llama.cpp/pull/29393) (RMS_NORM+SCALE fusion, author-
   measured +4.2-4.8% pp on CUDA with MTP) — if merged, re-measure prefill at depth on this
   profile — and check `fattn.cu`/`fattn-common.cuh` for a GQA-folding change (`ncols2`) or a
   quantized-KV TILE-path change that could remove the attention-bandwidth bottleneck described in
   [`docs/measurements/depth.md`](../measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4)
   (tracked upstream: [#27796](https://github.com/ggml-org/llama.cpp/issues/27796),
   [#28867](https://github.com/ggml-org/llama.cpp/issues/28867)).
2. **Only if something relevant changed**: build the new engine following "Build a new engine"
   below. The custom `GGML_CUDA_FA_QUANTS` build flags are still required for this build — the
   official binaries don't ship K q8_0 + V q5_1/q4_1 FlashAttention kernels.
3. **One A/B run** against the current reference profile (see `docs/STATUS.md`) at a couple of
   depths, ~15-20 minutes under `systemd-inhibit`: `bench/depth_bench.py`. Its hardcoded KV/MTP
   case list targets whichever profile it was last written for -- adjust `run_case`'s `kv`/`mtp`
   arguments if it no longer matches the current reference profile. Compare tok/s and MTP
   acceptance against the last recorded number in `docs/measurements/depth.md`.
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
   python scripts/smoke.py qwen38-iq3s-mtp --profile 262k-q8q51-mtp --backend hip-kvmix
   ```

## How to verify

- `python scripts/check-sync.py` reports no new PROBLEM (the "engine pending" WARNING disappears
  for the backend you just updated).
- The step-5 smoke test returns real content and tok/s.

## Known errors

- **K/V mixes that used to work now fall back to CPU**: if the new build changes
  `GGML_CUDA_FA_QUANTS` (HIP) without it showing in `--help`, check the server log ("no FA kernel
  found for this combination" is silent — it shows up as a tok/s drop with no explicit error).
  Compare tok/s against the previous measurement in `docs/measurements/`.
- **Missing rocblas/hipblas DLLs** in Windows HIP builds: the server fails to start with a DLL
  error. Check this before assuming the whole config is broken.
