# 2026-10-03: `GGML_CUDA_GRAPH_OPT=1` with MTP (T07)

Question: does `GGML_CUDA_GRAPH_OPT=1` (stream-level graph optimization, only active when HIP graphs
are on; `GGML_HIP_GRAPHS=ON` in the build) speed up the adopted profile? A third-party 7900 XTX
build guide reported +1-2% tg/pp at empty context without MTP.

## Setup and commands

Engine b11160 `hip-kvmix` (adopted), adopted flags, 272 W. The control is the same-day b11160 run in
[`20261003-b11371-mtp-draft-sampling/`](../20261003-b11371-mtp-draft-sampling/) (same binary, flags
and requests). Only the environment variable differs:

```bash
GGML_CUDA_GRAPH_OPT=1 BENCH_SERVER=<b11160>/llama-server python3 bench/spec_bench.py --run --variants mtp3 --tag graphopt
GGML_CUDA_GRAPH_OPT=1 python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3 --reps 3 --extra "-ub 256"
```

## Results

| Condition | Control | `GRAPH_OPT=1` | Delta |
|---|---|---|---|
| Empty context, temperature 1, median of 18 | 72.4 tok/s | 71.3 tok/s | -1.5% (per task -1.5% to +3.2%) |
| 240K essay (temperature 0, median of 3) | 24.55 | 23.65 | -3.7% |
| 240K copy | 26.92 | 25.95 | -3.6% |
| 240K code | 18.71 | 17.98 | -3.9% |

Generated tokens, MTP acceptance and output SHA are identical to the control; peak process VRAM
22,630 MiB (control 22,632).

## Conclusion

Not adopted: slower at depth on every task, no gain at empty context. Kill rule (< +2%) met.

**Raw data**: `empty-graphopt-aggregate.json`, `depth240k-graphopt-summary.jsonl`.
