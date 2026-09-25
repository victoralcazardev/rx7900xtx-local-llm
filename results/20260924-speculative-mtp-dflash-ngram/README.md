# 2026-09-24 — MTP vs. DFlash2 vs. n-gram (empty context)

**Measures**: generation speed and draft-acceptance percentage for no-speculation, MTP n=2, MTP +
n-gram, and several DFlash2 draft-model configurations, across 3 content types (new code, reasoning,
edit given code), with an empty context.

**Command**: `llama-server` started per configuration with the matching `--spec-type`/
`--spec-draft-*` flags, then a 1500-token response requested per content type, seed 42, vendor Qwen
sampling (`spec.py`, superseded name; ported as `bench/spec_bench.py`, see `bench/README.md`).

**Files**: `spec.jsonl` — one JSON line per configuration: label, flags, per-task tok/s and
accepted/proposed draft counts, VRAM (GiB). Personal machine paths in the DFlash2 draft-model flags
were replaced with `~/models/...`.

**Conclusion**: MTP n=2 wins overall and uses the least VRAM at empty context — but see
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md#mtp-vs-dflash2-vs-n-gram-empty-context)
for why this ranking changes at depth (190K A/B in the `20260925-*` folders below).
