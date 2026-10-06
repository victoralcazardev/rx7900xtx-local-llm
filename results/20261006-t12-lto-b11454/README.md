# 2026-10-06: `-DGGML_LTO=ON` build vs. the adopted b11454 build (T12)

Question: does link-time optimization (`-DGGML_LTO=ON`) speed up the b11454 `hip-kvmix` build? The
third-party claim is "+5-15%", with no A/B table published. Success rule, set before the run:
>= 2% on tg, or on pp at depth.

**Verdict: killed.** Every LTO delta is inside run-to-run spread (-0.6% to +0.1%), and the GPU
library is byte-identical to the control's.

## What LTO changes in b11454

- Variable: LTO only. Same source tree (b11454 `462524043` + the PR #29509 diff), same recipe as
  [`docs/ENGINES.md`](../../docs/ENGINES.md) with `-DGGML_LTO=ON` added.
- `-DGGML_LTO=ON` only sets `CMAKE_INTERPROCEDURAL_OPTIMIZATION` for the ggml targets
  (`ggml/src/CMakeLists.txt:58-66`). `-flto` appears in 34 `flags.make` files of the LTO build and
  in 0 of the control.
- `libggml-hip.so` is byte-identical in both builds (SHA256
  `7d1c9debd3899244ff803a0bd039c49e9df21112f98d9a00d5c9d59f6f6555c6`, the same as the adopted
  engine); `libggml-base.so` differs. LTO only changes host code.

## Command

Run in the order control, LTO, control again (ABA, to expose drift), 272 W cap:

```bash
llama-bench -m Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf -ngl 99 -fa 1 -ctk q8_0 -ctv q5_1 -ub 256 \
  -p 512 -n 128 -d 0,16384 -r 5 -o jsonl
```

## Results

tok/s, mean ± stddev over 5 reps. Delta: LTO vs. the mean of the two control runs.

| Test | Control | LTO | Control 2 | Delta |
|---|---|---|---|---|
| pp512, depth 0 | 919.23 ± 27.49 | 904.87 ± 26.24 | 901.27 ± 23.86 | -0.6% |
| tg128, depth 0 | 38.65 ± 0.05 | 38.60 ± 0.05 | 38.53 ± 0.05 | +0.0% |
| pp512, depth 16K | 787.78 ± 14.49 | 787.14 ± 15.79 | 784.21 ± 15.19 | +0.1% |
| tg128, depth 16K | 33.70 ± 0.12 | 33.64 ± 0.09 | 33.69 ± 0.05 | -0.2% |

## Decision

Not adopted. The planned 240K `bench/spec_depth_bench.py` follow-up was not run: the GPU library is
identical and the `llama-bench` delta is null.

**Raw data**: `ctl.jsonl`, `lto.jsonl`, `ctl2.jsonl` and their `.err` files (model and build paths
replaced with `~/models/...` and `~/src/...`).
