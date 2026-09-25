# 2026-09-24/25, night — 128K and 240K with per-process fdinfo

**Measures**: generation speed, warm-cache reuse, and per-process VRAM (fdinfo) for the 262K target
profile at 128K and (twice, reproducibility check) at 240K depth.

**Command**: `llama-server` started per case with the profile's flags, a `wiki.train`-derived prompt
padded to the exact target depth, 1,500 forced output tokens, then a warm second turn on the same
server (`validacion262.py`, superseded name; the fdinfo/warm-turn/telemetry design carried forward
into `bench/depth_bench.py`, see `bench/README.md`).

**Files**: `summary.md` — the per-case timing and fdinfo peaks (raw telemetry/server logs not
published).

**Conclusion**: 240K settles at 18.4 tok/s (below the >20 tok/s target), reproducible across two
runs; this supersedes the earlier single-sample 23.8 tok/s figure in `../20260924-depth-262k-deep/`,
which used a different output length and an unusually high MTP acceptance rate. See
[`../../docs/measurements/depth.md`](../../docs/measurements/depth.md#240k-with-fdinfo-repeated-q8q5_1--mtp-n2-262144-reserved).
