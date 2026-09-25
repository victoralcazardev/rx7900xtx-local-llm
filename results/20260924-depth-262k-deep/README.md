# 2026-09-24, night — Depth matrix at 262K target (128K / 240K)

**Measures**: prompt processing and generation speed with the context filled to 128K and 240K real
tokens, for the 262K-context candidate profile (KV q8_0/q5_1 + MTP n=2) against a q8_0/q8_0
no-MTP reference, plus one `-ub 256` variant.

**Command**: `llama-server` started per case with the profile's exact flags, then a request with a
`wiki.train`-derived prompt padded to the target depth and a 400-token forced response
(`profundo.sh`, not ported to `bench/` as a standalone script — see `bench/README.md`; the
successor script is `bench/depth_bench.py`).

**Files**: `summary.md` — the final timing/VRAM line extracted per case (raw logs not published).

**Conclusion**: the 262K target clears 20 tok/s at 240K in this single-sample matrix (23.8 tok/s),
but this figure was later found to overstate MTP's contribution and was superseded — see
[`../../docs/measurements/depth.md`](../../docs/measurements/depth.md#depth-matrix-at-262k-target-128k--240k-llama-server-400-token-response)
and the `20260924-depth-128k-240k-fdinfo` folder for the corrected, fdinfo-instrumented repeat.
