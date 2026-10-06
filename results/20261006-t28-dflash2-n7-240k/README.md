# 2026-10-06: DFlash2 `--spec-draft-n-max 7` vs. MTP at 240K depth (T28)

Question: does DFlash2 with the flags from a third-party tip beat the adopted MTP profile at 240K on
b11454? Success rule, set before the run: >= 5% median tg at depth and fits the 262K context.

## Origin and checks

- Tip (social media post, relayed by the user): `llama serve -hf ggml-org/Qwen3.8-27B-GGUF
  --spec-type draft-dflash --spec-draft-n-max 7`, "requires llama.cpp v0.6.0".
- b11454 reports `0.6.0-dev`; `--spec-type draft-dflash` already existed in b11160. The `llama serve`
  entry point was neither used nor verified (this repository uses `llama-server`).
- The `dflash-*` files in `ggml-org/Qwen3.8-27B-GGUF` are conversions of
  `incoai/Qwen3.8-27B-DFlash2` (rev `015e795`, 2026-09-17), which `z-lab/Qwen3.8-27B-DFlash2`
  mirrors: the same drafter measured before
  ([`speculative.md`](../../docs/measurements/speculative.md#mtp-vs-dflash2-vs-n-gram-empty-context)).
- `src/models/dflash.cpp` from b11160 to b11454 only received the
  [#29622](https://github.com/ggml-org/llama.cpp/pull/29622) batch refactor.

## Setup

- Engine `llama-b11454-pr29509-linux-rocm10-gfx1100-kvmix` (adopted), 262,144 context, KV
  `q8_0`/`q5_1`, `-ub 256`, temperature 0, 272 W cap.
- Base model without the MTP head: `Qwen3.8-27B-GSQ-RCO-IQ3_S`.
- Draft: `dflash-Qwen3.8-27B-Q4_0.gguf` from `ggml-org/Qwen3.8-27B-GGUF` (1,043.6 MiB, sha256
  `0a994382adf17c720c9e5d4292f57344f3b445f058d3e9d5b0f601ae7d6ca3c4`).
- Variant `dfl7` in `bench/spec_depth_bench.py`: `-md <draft> -ngld all --spec-type draft-dflash
  --spec-draft-n-max 7`, no `--spec-draft-p-min` (the tip's flags). Server log: `n_max=7`,
  `p_min=0.00`, `block_size=8`.
- Reference: MTP `n3-map` on the same engine, the b11454 arm of
  [`20261006-b11454-engine-update/`](../20261006-b11454-engine-update/README.md).

## Command

```bash
BENCH_DFLASH_MODEL=<draft.gguf> BENCH_MODEL_NO_MTP=<base-without-mtp.gguf> \
  python3 bench/spec_depth_bench.py --run --depth 240000 --variants dfl7 --reps 3 --extra "-ub 256"
```

## Results

240K depth, median tg tok/s over 3 warm reps (DFlash2 acceptance = accepted/drafted):

| Task | MTP n3-map | DFlash2 n7 | Delta | DFlash2 acceptance |
|---|---|---|---|---|
| essay | 25.94 | 16.67 | -36% | 25% |
| copy | 45.94 | 21.57 | -53% | 37% |
| code | 19.33 | 20.48 | +5.9% | 34% |

- Peak process VRAM 22,617 MiB; fits 262K (`n_ctx_slot` 262144).
- Cold prefill (essay warm-up): 400.6 tok/s.
- The copy output hash equals MTP's (`ff04a5f8`), consistent with lossless decoding.

## Decision

Not adopted. Only code clears +5%; essay and copy lose 36-53%, and the setup runs one default
profile. Consistent with the earlier finding that DFlash2 does not beat MTP at depth
([`speculative.md`](../../docs/measurements/speculative.md#dflash2-and-the-native-q8-kv-fork-at-190k)).

**Raw data**: `depth240k-dfl7-summary.jsonl` (server path replaced with a placeholder). SSE streams
and server logs stay local (`_tmp/`, git-ignored).
