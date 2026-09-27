# Status

## Current profile

`qwen38-iq3s-mtp` / `262k-q8q51-mtp` — **default** (`scripts/launch.py`'s `[defaults]` when no
alias is given, i.e. `ia` with no arguments).

```
python scripts/launch.py
# equivalent, explicit form:
python scripts/launch.py qwen38-iq3s-mtp --profile 262k-q8q51-mtp
```

Engine `hip-kvmix`, `-c 262144`, KV `q8_0/q5_1`, MTP `--spec-draft-n-max 3`, `-ub 256`, vision
disabled, measured under a 272 W power cap (this card's driver minimum, now the permanent
setting — see `measurements/thermals-power.md`).

`models.toml` ships this single model/profile by design (2026-09-26, `docs/DECISIONS.md`): one
best default, no overlapping alternatives.

## Headline numbers

- **240K fill, essay/copy/code**: 24.4 / 26.9 / 18.6 tok/s, mean 23.3, prefill 380 tok/s, peak
  process VRAM **22,630 MiB**, 0 evicted. See
  [`measurements/speculative.md`](measurements/speculative.md) and
  [`measurements/memory.md`](measurements/memory.md).
- **Empty-context generation**: 68.9 tok/s (37.2 without MTP, +85%), community `probe.py`, three
  passes per arm. See
  [`measurements/speculative.md`](measurements/speculative.md#community-probe-ab-at-262k-empty-context-2026-09-27).
- **Without MTP at 240K fill** (same flags): 11.2 tok/s, so MTP n=3 is **+109%** at the operating
  depth. See
  [`measurements/speculative.md`](measurements/speculative.md#mtp-vs-spec-off-at-240k-fill-adopted-profile-2026-09-27).
- **Quality**: **68/68 exact match, 0 loop detections** on a RULER-style multi-key retrieval test,
  32K-240K fill (`bench/longctx_quality.py`), including 8/8 on the exact adopted server flags
  (MTP n=3, `-ub 256`) at 240K. See
  [`measurements/depth.md`](measurements/depth.md#quality-ruler-style-200k-q8q8-mtp).
- **Power**: 272 W permanent cap (this card's driver minimum) — ~6% slower prefill than the
  factory 303 W default, with the hotspot 7-8°C cooler. See
  [`measurements/thermals-power.md`](measurements/thermals-power.md).

## Why this configuration

- **KV `q8_0/q5_1`**: `q8_0/q8_0` is effectively free (KLD 0.000587 vs. f16); `q8_0/q5_1` costs
  27% more KLD but doesn't show up as a retrieval-quality loss at 240K, and buys more context in
  24 GB than `q8_0/q8_0`. `q4_0/q4_0` discarded (4x KLD). See
  [`measurements/kv-quality.md`](measurements/kv-quality.md).
- **MTP `--spec-draft-n-max 3`**: confirmed at the real long-context operating depths (190K and
  240K fill), +9-11% mean tg over n=2 across essay/copy/code — unlike a shallower 128K-fill
  screening that only favored n=3 on literal copy. Against no speculation it is +109% at 240K fill
  and +85% at empty context (2026-09-27). See
  [`measurements/speculative.md`](measurements/speculative.md).
- **`-ub 256`**: -350 MiB peak process VRAM for a small prefill cost (-5%), no generation-speed
  cost. See [`measurements/memory.md`](measurements/memory.md).
- **272 W power cap**: the factory 303 W default pushed the hotspot to 106°C during a deep
  prefill; 272 W (the card's driver minimum) trades ~6% prefill speed for a comfortable thermal
  margin. See [`measurements/thermals-power.md`](measurements/thermals-power.md).

## Open questions

- **Vulkan re-test with the GPU memory clock pinned**: a 2026-09-26 depth screen reproduced the
  clock-throttling behavior (456 MHz in 93 of 118 samples) but was inconclusive for decode at
  depth — Vulkan's prefill collapses ~5x at `-ub 256` and the run was stopped before 128K depth. A
  fair re-test needs `-ub >= 512` and the clock pinned at the root, and is currently blocked by the
  profile's thin VRAM headroom (190 MiB). See
  [`measurements/engines.md`](measurements/engines.md#vulkan-depth-screen-2026-09-26).
- **MTP acceptance with real agent traffic at temperature 1**: depth numbers here use a synthetic
  prompt at temperature 0; third-party reports with real tool-call traffic range 64-93%
  acceptance. See `docs/SOURCES.md`.
- **Broader quality sample**: the current retrieval-quality runs are small at the edges — 190K has
  1 of 5 planned documents, 240K has 2 of 5 — not blocking, since every depth measured so far is
  exact match. See `measurements/depth.md`.
- **Upstream llama.cpp issues to re-check on the next engine update** (see
  [`sop/update-engine.md`](sop/update-engine.md) and `SOURCES.md`): issue
  [#26648](https://github.com/ggml-org/llama.cpp/issues/26648) (MTP sampler assert at long context
  on HIP); issues [#26038](https://github.com/ggml-org/llama.cpp/issues/26038),
  [#27282](https://github.com/ggml-org/llama.cpp/issues/27282) and
  [#28433](https://github.com/ggml-org/llama.cpp/issues/28433) (MTP compute/draft-ctx sizing on
  HIP), open as of b11178; [halo-box/strix-llama.cpp#56](https://github.com/halo-box/strix-llama.cpp/pull/56)
  (RDNA3 IQ2/IQ3 MMVQ scale-multiply change); the
  [BuffedMod IQ3_S quant](https://huggingface.co/tooltd/Qwen3.8-27B-GSQ-RCO-BuffedMod-GGUF)
  (upcasts `output.weight`, untested here).

## Tried and not adopted

- **ROCm 10.0.0 runtime libraries** (TheRock, compiler kept at ROCm 10) — 1-2% slower tg, ~5%
  slower pp, higher variance vs. the system ROCm 7.2.4 runtime. See
  [`measurements/engines.md`](measurements/engines.md).
- **BeeLlama v0.4.7 + KVarN KV cache** — KVarN's KLD is ~2.7x q8/q8's at every bit width; BeeLlama
  itself is ~18-22% slower than `hip-kvmix`. See
  [`measurements/kv-quality.md`](measurements/kv-quality.md).
- **DFlash2 speculative decoding** — slower than MTP n=2 at 190K on most task types, and uses more
  VRAM. See [`measurements/speculative.md`](measurements/speculative.md).
- **KV `q4_0/q4_0`** — 4x the KLD of q8/q8, the only mix below 98% same-top-1 token.
- **`kvmix-vec4` patch** — +20% ms/step at depth vs. plain `kvmix`.
- **`stew675/llama-cpp-rdna-boosts` fork** — only -2.5% ms/step, not worth maintaining a fork.
- **More than 1 concurrent slot** — a slot's long prefill starves generation on the others; 1 slot
  + MTP with request queuing beats adding `-np` slots end-to-end. See
  [`measurements/concurrency.md`](measurements/concurrency.md).
- **MTP n=4** and **`--spec-draft-p-min`** — n=4 loses acceptance vs. n=2/n=3; p-min raises
  acceptance but not speed at any depth measured, and at empty context 0.60/0.75 lower it
  (68.9 → 66.2/59.8 tok/s at n=3).
- **`-ub 1024`/`-ub 2048`** — no speed gain at depth, cost 590 MiB/1.8 GiB more VRAM.
- **Vision at 200K+ context** — VRAM/context cost not worth it at this depth.
- **exllamav3-rocm** (+ patched TabbyAPI) — not pursued: a read-only audit found no code or
  license blocker, but lower priority than the other candidates and the 15.3 GB EXL3 model leaves
  less VRAM headroom. See `docs/ENGINES.md`/`docs/SOURCES.md`.
- **GPU power-limit/undervolt tuning beyond the permanent 272 W cap** — deprioritized. See
  `docs/DECISIONS.md`.
- **Round 4 speed-research candidates, gains <5% or blocked by VRAM/context** (2026-09-26, no
  measurement run for any of these): cherry-picking llama.cpp PR #29393 outside a regular engine
  update; `--spec-draft-p-min 0.5` / `--spec-draft-n-min`; the fork's adaptive MTP
  (`draft-mtp-adaptive` — upstream PR #27210's author advises against adaptive below draft depth
  7); `-ub 384`; a 290/303 W power cap (303 W pushes the deep-prefill hotspot to 100-106°C, over
  the 104°C bench ceiling); Vulkan with the memory clock pinned; building ik_llama.cpp. See
  [`measurements/depth.md`](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4).

## Next steps

1. Vulkan re-test with the GPU memory clock pinned — blocked by VRAM headroom, see "Open
   questions" above.
2. Next engine update: pick up llama.cpp PR #29393 (RMS_NORM+SCALE fusion) and watch upstream for
   a GQA-folding FlashAttention fix for RDNA3 or removal of the TILE f16 KV conversion — see
   `docs/sop/update-engine.md` and `measurements/depth.md`.
3. GPU care beyond the permanent 272 W cap (undervolt) — deferred.
