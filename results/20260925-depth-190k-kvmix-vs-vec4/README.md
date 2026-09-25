# 2026-09-25 — 190K A/B: kvmix vs. vec4, MTP n=2

**Measures**: generation speed and draft acceptance at 190K depth, KV q8_0/q8_0 (`-c 204800`), for
the current `kvmix` engine vs. the experimental `vec4` patch (see
`../../docs/measurements/speculative.md`).

**Command**: one server per engine variant; a 190,000-token `wiki.train`-derived document, then 3
tasks (essay, literal copy, code) at temperature 0, 400 tokens max, natural EOS. The first request
per task does the prefill (not counted), the second reuses the cache
(`mtpprof262.py`, superseded name; ported as `bench/spec_depth_bench.py`, see `bench/README.md`).

**Files** (personal machine paths replaced with placeholders: model paths with `~/models/...`,
engine binary paths with `~/engines/<build-dir>/llama-server`):
- `summary-kvmix-q8q8.jsonl` / `command-kvmix-q8q8.json` — current `hip-kvmix` engine.
- `summary-vec4-q8q8.jsonl` / `command-vec4-q8q8.json` — experimental `vec4` engine.

**Conclusion**: `kvmix` beats `vec4` by 14-17% at 190K — the vec4 patch is **not adopted**. See
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md#ab-at-190k--c-204800-kv-q8q8-kvmix-vs-vec4-mtp-n2).
