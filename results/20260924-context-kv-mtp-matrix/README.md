# 2026-09-24 — Context/KV/MTP matrix (empty-context baseline)

**Measures**: generation speed, VRAM and MTP acceptance across context size (128K/262K), KV type
(q8_0/q8_0, q4_0/q4_0), vision on/off, and MTP draft length (n=0..5), with an empty context.

**Command**: `llama-server` started per case with the matching flags, then a 1024-token response
requested to a short prompt (`escalera.py`, superseded name for the sweep script; ported as
`bench/ladder_bench.py`, see `bench/README.md`).

**Files**: `ladder.jsonl` — one JSON line per case: backend, case identifier (context:KV:MTP-n),
load time, VRAM (GiB), tok/s, MTP acceptance, peak VRAM.

**Conclusion**: q4_0 KV is discarded on quality grounds (see `kv-quality.md`); MTP n=2 is the sweet
spot for acceptance/speed at 128K; 262K+MTP+q8/q8 hits an OOM while generating. See
[`../../docs/measurements/depth.md`](../../docs/measurements/depth.md#context-kv-and-mtp-server-real-matrix-empty-context-baseline).
