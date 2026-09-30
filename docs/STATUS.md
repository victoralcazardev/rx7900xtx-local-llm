# Status

Single source of truth for the current profile, headline numbers and flags. Other docs link here
instead of repeating them. Tried and not adopted: [`TRIED.md`](TRIED.md).

## Current profile

`qwen38-iq3s-mtp` / `262k-q8q51-mtp` — the only model/profile in `models.toml` (one best default,
no overlapping alternatives, 2026-09-26, [`DECISIONS.md`](DECISIONS.md)) and `scripts/launch.py`'s
default when no alias is given.

- Model: Qwen3.8-27B GSQ-RCO `IQ3_S-mtp` (native MTP head baked in), 12.1 GB, PPL 6.734 ± 0.084;
  `mmproj-Qwen3.8-27B-BF16.gguf` present but vision disabled. Other quants:
  [`models/qwen38-27b-quants.md`](models/qwen38-27b-quants.md).
- Engine: llama.cpp b11160 `hip-kvmix` (own ROCm build with FlashAttention kernels for K `q8_0` +
  V `q5_1`); ROCm/HIP beats Vulkan 2-3.5x on generation here, Vulkan is reference-only.
  [`ENGINES.md`](ENGINES.md).
- Power: 272 W permanent cap (driver minimum; stock 303 W) — [`sop/power-cap.md`](sop/power-cap.md).
- Harness wiring: one fixed provider `local-262k` (contextWindow 262144) on `:8080`, verified by
  `python3 scripts/check-sync.py` when `local.toml` has `[harness] enabled = true`.

```bash
python3 scripts/launch.py            # default profile; add --dry-run to print the command
llama-server -m <models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
  --port 8080 -c 262144 -ctk q8_0 -ctv q5_1 \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  -fa on -np 1 --ctx-checkpoints 4 -ngl all --metrics \
  --spec-type draft-mtp --spec-draft-n-max 3 -ub 256 --reasoning-effort medium
```

## Headline numbers

- **240K fill, essay/copy/code**: 24.4 / 26.9 / 18.6 tok/s (mean 23.3), prefill 380 tok/s, peak
  process VRAM 22,630 MiB, 0 evicted —
  [speculative.md](measurements/speculative.md), [memory.md](measurements/memory.md).
- **Empty context**: 68.9 tok/s (37.2 without MTP, +85%), community `probe.py`, 3 passes —
  [speculative.md](measurements/speculative.md#community-probe-ab-at-262k-empty-context-2026-09-27).
- **Without MTP at 240K fill**: 11.2 tok/s, so MTP n=3 is +109% at depth —
  [speculative.md](measurements/speculative.md#mtp-vs-spec-off-at-240k-fill-adopted-profile-2026-09-27).
- **Quality**: 68/68 exact match, 0 loops, RULER-style retrieval, 32K-240K fill (8/8 on the exact
  adopted flags at 240K) —
  [depth.md](measurements/depth.md#quality-ruler-style-200k-q8q8-mtp).
- **Power**: 272 W costs ~6% prefill vs. 303 W and runs the hotspot 7-8°C cooler (303 W hit 106°C
  in a deep prefill) — [thermals-power.md](measurements/thermals-power.md).

## Flags and why

Sampling is the Qwen3.8-27B card's own; `--min-p 0.0` is set explicitly because the binary default
(0.05) isn't what the vendor tested ([`../AGENTS.md`](../AGENTS.md)).

| Flag | Why |
|---|---|
| `-c 262144` | Full native context; matches the wired `local-262k` provider |
| `-ctk q8_0 -ctv q5_1` | `q8_0/q8_0` is near-free (KLD 0.000587 vs. f16); `q5_1` V costs +27% KLD but fits 262K in 24 GB; `q4_0/q4_0` has 4x KLD — [kv-quality.md](measurements/kv-quality.md) |
| `-fa on` | Mandatory with a quantized V cache; avoids a silent slow-path fallback — [engines.md](measurements/engines.md) |
| `--spec-type draft-mtp` | Uses the MTP head in the GGUF, no separate draft model — [qwen38-27b-quants.md](models/qwen38-27b-quants.md) |
| `--spec-draft-n-max 3` | +9-11% mean tg over n=2 at the real 190K/240K depths (a 128K screening favored n=3 only on copy); n=4/5 lose acceptance — [speculative.md](measurements/speculative.md) |
| `-ub 256` | -350 MiB peak VRAM vs. 512, -5% prefill, no generation cost — [memory.md](measurements/memory.md) |
| `-np 1` | Single user; one slot + MTP with queuing beats more slots — [concurrency.md](measurements/concurrency.md) |
| `--ctx-checkpoints 4` | Default is 32; 4 bounds RAM (270-515 MiB each). Cost: one ~42 s re-process of the base prompt per new context (~14.5K tokens now); warm turns still reuse ~all KV — [memory.md](measurements/memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29), [TRIED.md](TRIED.md) |
| `-ngl all` | All layers on GPU, explicit rather than `auto` |
| `--reasoning-effort medium` | Template default `xhigh` injects "think carefully..." and overthinks; `medium` adds no instruction — `models.toml` |
| `--metrics` | Exposes `/metrics` for the token usage ledger — [token-ledger.md](sop/token-ledger.md) |

## Open questions

- **Qwen3.8-Flash-Next (MoE) trial**: Strata v0.1.30's resident low-RAM variant keeps the
  non-GPU experts in RAM (upstream: fits 32 GB RAM + 24 GB GPU for Q2_0, IQ2_XS, Coder); not
  measured. Compare tok/s at 128K+ and quality against the KVMem candidate —
  [strata-flash-next.md](models/strata-flash-next.md).
- **Compaction and presence penalty A/B**: real agent traffic is 89% generation, ~78% of output is
  reasoning; each compaction re-processes the kept context (median ~83 s). Open: harness compaction
  at 75% vs. 60%, `handoff`-first vs. `shake`-first, `--presence-penalty` 0 vs. 1.0 —
  [agent-traffic.md](measurements/agent-traffic.md#open-ab-tests).
- **KVMem trial** ([kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp)): rounds 1-2 (2026-09-30):
  candidate budget 28,672 + `--kvmem-block-tokens 32` gives 45.5 tok/s at 244K (baseline 20.8,
  2.2x) with ~15 GiB VRAM and 8/8 exact at 240K (4/4 at 190K and 220K); budget 49,152 faults
  deterministically at 190K. Not adopted; open: the real agent run (T6), the 16,384-token
  per-turn output cap —
  [ENGINES-EXPERIMENTS.md](ENGINES-EXPERIMENTS.md#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted),
  [results](../results/20260930-kvmem-trial-round2/README.md).
- **Broader quality sample**: 190K has 1 of 5 planned documents, 240K has 2 of 5; not blocking
  (every depth so far is exact match) — [depth.md](measurements/depth.md).
- **Upstream issues to re-check on the next engine update** ([update-engine.md](sop/update-engine.md),
  [SOURCES.md](SOURCES.md)): llama.cpp [#26648](https://github.com/ggml-org/llama.cpp/issues/26648)
  (MTP sampler assert at long context on HIP); [#26038](https://github.com/ggml-org/llama.cpp/issues/26038),
  [#27282](https://github.com/ggml-org/llama.cpp/issues/27282),
  [#28433](https://github.com/ggml-org/llama.cpp/issues/28433) (MTP compute/draft-ctx sizing on HIP,
  open as of b11178); [halo-box/strix-llama.cpp#56](https://github.com/halo-box/strix-llama.cpp/pull/56)
  (RDNA3 IQ2/IQ3 MMVQ change); the
  [BuffedMod IQ3_S quant](https://huggingface.co/tooltd/Qwen3.8-27B-GSQ-RCO-BuffedMod-GGUF)
  (upcasts `output.weight`, untested here).

## Speed levers at depth (2026-09-30)

| Lever | Expected gain | Cost | Status |
|---|---|---|---|
| `--reasoning-effort low` | Largest: ~78% of output is reasoning | Quality | Not pursued (quality first) |
| Earlier compaction / one session per plan phase | Keeps decode in the ~34 tok/s band instead of ~19 | More lossy compactions, ~5 min each | Harness threshold at 75% instead |
| KVMem (bounded active attention, full history in host RAM) | Decode at depth without dropping history | Retrieval may miss blocks; ROCm beta; ~+10 GiB host RAM | Trial: 2.2x decode at 244K, exact at 240K, awaiting agent run, not adopted — [ENGINES-EXPERIMENTS.md](ENGINES-EXPERIMENTS.md#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted) |
| Upstream RDNA3 FlashAttention GQA fix | Decode at depth (kernel at ~24% of memory bandwidth) | None | Waiting on llama.cpp |
| Server flags (MTP, `-ub`, KV, power cap) | <5% | — | Already measured |

Detail: [agent-traffic.md](measurements/agent-traffic.md).

## Next steps

1. Next engine update: pick up llama.cpp PR #29393 (RMS_NORM+SCALE fusion; expected to apply to the
   HIP build, prefill only, ~27 s on a cold 240K fill, not measured; not worth an update alone) and
   watch upstream for a GQA-folding FlashAttention fix for RDNA3 or removal of the TILE f16 KV
   conversion — [update-engine.md](sop/update-engine.md), [depth.md](measurements/depth.md).
2. GPU care beyond the permanent 272 W cap (undervolt) — deferred.
