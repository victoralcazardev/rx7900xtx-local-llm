# 2026-09-25 — DFlash2 and the "native q8 KV" fork, at 190K

**Measures**: generation speed and VRAM at 190K depth for two alternatives to the `kvmix` + MTP n=2
reference measured in `../20260925-depth-190k-kvmix-vs-vec4/`: DFlash2 as the draft model, and an
experimental fork that reads q8_0 KV natively in the TILE/MMA FlashAttention kernel instead of
converting it to f16.

**Command**: same method as the kvmix-vs-vec4 A/B (190K document, 3 tasks, temperature 0, 400 tokens
max) — see that folder's README (`mtpprof262.py`, superseded name; ported as
`bench/spec_depth_bench.py`, see `bench/README.md`).

**Files** (personal machine paths replaced with placeholders: model paths with `~/models/...`,
engine binary paths with `~/engines/<build-dir>/llama-server`):
- `summary-dflash2-q4-n5.jsonl` / `command-dflash2-q4-n5.json` — DFlash2 Q4_K_M draft, n=5,
  `--spec-draft-p-min 0.4`, on the `kvmix` engine (no MTP head, DFlash2 uses its own draft GGUF).
- `summary-rdna-native-q8q8.jsonl` / `command-rdna-native-q8q8.json` — MTP n=2 on the
  `llama-rdnaboosts-v16-ebbb18522-rocm10-gfx1100` fork ("native q8" KV path, auto-enabled).

The `kvmix` + MTP n=2 reference these are compared against is in
`../20260925-depth-190k-kvmix-vs-vec4/summary-kvmix-q8q8.jsonl`.

**Conclusion**: neither alternative is adopted — DFlash2 is slower or ties MTP and costs more VRAM;
the native-q8 fork only improves the per-step cost by ~2.5% while costing more prefill VRAM. See
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md#dflash2-and-the-native-q8-kv-fork-at-190k).
