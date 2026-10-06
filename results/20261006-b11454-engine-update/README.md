# 2026-10-06: llama.cpp b11454 (+ PR #29509) vs. b11371 (+ PR #29509) on the adopted profile

Question: is llama.cpp b11454 (`462524043`), carrying the same
[PR #29509](https://github.com/ggml-org/llama.cpp/pull/29509) patch as the engine in use, clearly
worse than b11371 (`99b9548`) + PR #29509 at 240K depth? Adoption rule (2026-10-06): adopt the
newest upstream build unless it is clearly worse.

## Setup

- Engines (same `kvmix` recipe and toolchain, [`docs/ENGINES.md`](../../docs/ENGINES.md)):
  - `llama-b11371-pr29509-linux-rocm10-gfx1100-kvmix`: b11371 (`99b9548`) + PR #29509 (engine in use
    since 2026-10-04).
  - `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix`: b11454 (`462524043`, `--version`
    `0.6.0-dev (build 154, commit 462524043)`) + PR #29509 head
    `b3c27359975ea4fb0f400785de3fc2729a35708a` (still open upstream; the diff applies cleanly).
- `llama-server --help` is identical on both builds: no default changed, `models.toml` flags
  unchanged.
- Model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`, adopted profile flags (KV `q8_0`/`q5_1`, MTP n=3 +
  `ngram-map-k4v`, `-ub 256`), temperature 0, 272 W cap, `systemd-inhibit`, one arm at a time.
- Measured binary: the b11454 arm ran `llama-server` from the build tree (`build-rocm10/bin`, source
  tree = b11454 + the PR #29509 diff), before it was copied into the engine folder. `llama-server`,
  `libggml-hip.so`, `libllama-server-impl.so`, `libllama.so.0.6.0` and `libggml-base.so.0.26.0` have
  the same SHA256 in both places, so the run measured the adopted engine's bytes.
- Thermal start: `cooldown_s` differs (b11371 ~0.05 s, b11454 ~30.2 s) because `cool_down()`
  (`bench/depth_bench.py`) waits until the GPU edge is <= 55 C before each case; b11454 ran right
  after b11371 and had to wait, b11371 started from idle. Both arms started at or below the same
  threshold (b11371 cooler, which if anything favors it), and decode is measured after a ~10 min
  prefill at the 272 W cap.

## Upstream range b11371 -> b11454

83 commits. None of the watchlist PRs is in range (#28102, #29393, #28391, #26038, #27282, #28433,
#27140). Relevant to this setup:
[#29435](https://github.com/ggml-org/llama.cpp/pull/29435) (CUDA whole-tile FA scheduling in
`fattn-common.cuh`/`fattn-mma-f16.cuh`; its new path targets NVIDIA DGX Spark only),
[#30020](https://github.com/ggml-org/llama.cpp/pull/30020) (re-reserve the scheduler when the nextn
extraction flags change), [#29633](https://github.com/ggml-org/llama.cpp/pull/29633) (MMVF for thin
f16/bf16 `mul_mat` at small batch).

## Commands

```bash
# 240K fill, 3 reps after a cold-prefill warm-up, once per engine
python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 3 --extra "-ub 256"
# parity, wikitext-2, both engines
llama-perplexity -m <model> -f wiki.test.raw -c 4096 --chunks 16 -ngl 99 -fa on -ctk q8_0 -ctv q5_1 -ub 256
# new engine, 262K profile
python3 scripts/smoke.py qwen38-iq3s-mtp
python3 scripts/check-sync.py
```

## Results

240K depth, median tg tok/s over 3 warm reps:

| Task | b11371 + #29509 | b11454 + #29509 | Delta | Output hash |
|---|---|---|---|---|
| essay | 25.14 | 25.94 | +3.2% | differs |
| copy | 45.60 | 45.94 | +0.7% | identical |
| code | 19.12 | 19.33 | +1.1% | differs |

- Cold prefill (239,983 tokens, essay warm-up): 393.3 vs. 391.4 tok/s (-0.5%).
- Peak process VRAM (`drm-memory-vram`, max over each arm's telemetry samples): 23,731,634,176 vs.
  23,740,391,424 bytes (22,632 vs. 22,641 MiB).
- Greedy output: essay diverges at the first generated token (b11371 starts its reasoning in
  Spanish, "El usuario me pide...", b11454 in English, "We need answer in Spanish..."); code
  diverges at character 573. Both outputs are coherent. Read as a near-tie flip from upstream
  numeric changes, not a degradation: the parity check below is identical.
- Parity: wikitext-2 PPL 6.2132 +/- 0.08276 on both engines (identical to 4 decimals). Scope: this
  run uses `-c 4096` without speculation, so it shows the kernels agree at short context; it does
  not by itself prove equal quality at 240K with MTP, where only the coherence of the outputs above
  was checked.
- Smoke on b11454, 262K profile: OK, 71.8 tok/s, coherent content. `check-sync.py`: OK.

## Decision

Adopt `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix` as the `hip-kvmix` engine: not worse on any
measured axis (speed +0.7..+3.2%, prefill and VRAM within noise, same PPL). Rollback =
`llama-b11371-pr29509-linux-rocm10-gfx1100-kvmix`. Published afterwards as the GitHub release
`engine-b11454-rocm10-gfx1100-kvmix` (`llama-b11454-pr29509-rocm10-gfx1100-kvmix-linux-x64.tar.gz`, sha256 `60dafa459f7534069c3e15fc85f4bc6fd29537558603f61b86f7ecfaa3adbb46`).

**Raw data**: `depth240k-b11371-pr29509-summary.jsonl`, `depth240k-b11454-pr29509-summary.jsonl`
(server paths replaced with placeholders), `ppl-wikitext2.txt` ("Final estimate" lines). SSE streams,
`--help` dumps and server logs stay local (`_tmp/`, git-ignored).
