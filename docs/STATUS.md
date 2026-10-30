# Status

What runs today and why: the adopted profile, its headline numbers, flag rationale, and a short
list of what is open. Other docs link here instead of repeating them.

**Scope.** This file holds only the current state. Each open question or next step is one line
that links its owner; results, candidate lists, trial details, upstream watch lists and analysis
live in the owner doc ([`STYLE.md`](STYLE.md) §8), never here. When an item is answered or
started, remove it and record the outcome in its owner. Budget: 1,000 words. Tried and not
adopted: [`TRIED.md`](TRIED.md); planned engine trials:
[`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md).

## Current profile

`qwen38-iq3s-mtp` / `262k-q8q51-mtp` — the only model/profile in `models.toml` (one best default,
no overlapping alternatives, 2026-09-26, [`DECISIONS.md`](DECISIONS.md)) and `scripts/launch.py`'s
default when no alias is given.

- Model: Qwen3.8-27B GSQ-RCO `IQ3_S-mtp` (native MTP head baked in), 12.1 GB, PPL 6.734 ± 0.084;
  `mmproj-Qwen3.8-27B-BF16.gguf` present but vision disabled. Other quants:
  [`models/qwen38-27b-quants.md`](models/qwen38-27b-quants.md).
- Engine: llama.cpp b11846 + local PR #30792 patch extended to V `q5_1` (`hip-kvmix`, own ROCm build
  with FlashAttention kernels for K `q8_0` + V `q5_1`, dequantized natively in the TILE kernel), in use
  since 2026-10-24; rollback b11820 with the same patch. ROCm/HIP beats Vulkan 2-3.5x on generation
  here, Vulkan is reference-only. [`ENGINES.md`](ENGINES.md).
- Power: 272 W permanent cap (driver minimum; stock 303 W) — [`sop/power-cap.md`](sop/power-cap.md).
- Harness wiring: one fixed provider `local-262k` (contextWindow 262144) on `:8080`, verified by
  `python3 scripts/check-sync.py` when `local.toml` has `[harness] enabled = true`. Hermes profiles
  outside this repo use the same endpoint (not covered by `check-sync.py`), and `tailscale serve`
  exposes it to the tailnet without a key ([`DECISIONS.md`](DECISIONS.md), 2026-10-23).

```bash
python3 scripts/launch.py            # default profile; add --dry-run to print the command
llama-server -m <models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
  --port 8080 -c 262144 -ctk q8_0 -ctv q5_1 \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  -fa on -np 1 --ctx-checkpoints 4 -ngl all --metrics \
  --spec-type draft-mtp,ngram-map-k4v --spec-draft-n-max 3 -ub 256 --reasoning-effort medium \
  --cache-ram 12288
```

## Headline numbers

- **240K fill, adopted profile (temperature 0), essay/copy/code**: 33.2 / 54.7 / 22.5 tok/s, prefill
  395 tok/s, peak process VRAM 22,645 MiB —
  [results](../results/20261024-engine-b11846-240k/README.md); TILE patch +18-27%
  ([D1](../results/20261023-d1-pr30792q51-240k/README.md)); cross-session spread up to ~6%.
- **Empty context**: 76.3 tok/s MTP n=3 (39.1 without MTP), community `probe.py`, 3 passes —
  [results](../results/20261024-probe-ab-262k-pr30792q51/README.md).
- **Without MTP at 240K fill** (b11160): 11.2 tok/s, so MTP n=3 is +109% at depth —
  [speculative.md](measurements/speculative.md#mtp-vs-spec-off-at-240k-fill-adopted-profile-2026-09-27).
- **n-gram map on MTP**: copy at 240K 43.9 vs. 27.0 tok/s (+62%), agent/editing at empty context
  +55% / +36%, other tasks -0-2%, temperature-0 output identical —
  [results](../results/20261003-ngram-mtp-stacking/README.md).
- **Quality**: 68/68 pooled across configurations from 32K-240K (0 loops), plus 40/40 at 190K and
  240K on the adopted KV/MTP flags (b11160, temperature 0, thinking off, no n-gram map). Recall on
  real agent history at 80K/176K with production sampling: 15-16/16 and 14-15/16, no
  position-dependent loss. Retrieval only —
  [depth.md](measurements/depth.md#current-conclusion).
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
| `--spec-type draft-mtp,ngram-map-k4v` | MTP head in the GGUF (no separate draft model) plus an n-gram drafter over the slot's own tokens: large gains when output copies context, lossless at temperature 0 — [qwen38-27b-quants.md](models/qwen38-27b-quants.md), [speculative.md](measurements/speculative.md) |
| `--spec-draft-n-max 3` | +9-11% mean tg over n=2 at the real 190K/240K depths (a 128K screening favored n=3 only on copy); n=4 loses 9-23% at 240K, re-checked on the current engine — [speculative.md](measurements/speculative.md), [TRIED.md](TRIED.md) |
| `-ub 256` | -350 MiB peak VRAM vs. 512, -5% prefill, no generation cost — [memory.md](measurements/memory.md) |
| `-np 1` | Single user; one slot + MTP with queuing beats more slots — [concurrency.md](measurements/concurrency.md) |
| `--ctx-checkpoints 4` | Default is 32; 4 bounds RAM and warm turns still reuse ~all KV — [memory.md](measurements/memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29), [TRIED.md](TRIED.md) |
| `--cache-ram 12288` | The 8192 default evicts a ~180K main state (7.7 GiB) when a side request is cached (412 s re-prefill); 12288 restores it in 1.8 s; up to ~4 GiB more host RAM — [memory.md](measurements/memory.md#host-prompt-cache-eviction-with-a-side-request-2026-10-03) |
| `-ngl all` | All layers on GPU, explicit rather than `auto` |
| `--reasoning-effort medium` | Template default `xhigh` injects "think carefully..." and overthinks; `medium` adds no instruction — `models.toml` |
| `--metrics` | Exposes `/metrics` for the token usage ledger — [token-ledger.md](sop/token-ledger.md) |

## Open questions

- **Full cache misses in long sessions**: cause found (harness speculative compaction on the single
  local slot) and a harness compaction change is in place; the 2026-10-03/04 logs are classified,
  with one local compaction-summary fallback found —
  [agent-traffic.md](measurements/agent-traffic.md#first-session-after-the-compaction-change-2026-10-03-evening-single-session).
- **Compaction threshold, compaction method order and presence penalty** A/B only after a fixed
  coding-task suite with executable tests and pass/fail criteria exists; checkpoint count is
  conditional on a logged mid-context divergence; 60% (~157K) is the comparison arm —
  [agent-traffic.md](measurements/agent-traffic.md#open-ab-tests).
- **KVMem**: not adopted until a real agent run —
  [ENGINES-EXPERIMENTS.md](ENGINES-EXPERIMENTS.md#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted).
- **Qwen3.8-Flash-Next via Strata**: IQ2_XS on v0.2.8 installed and stable in mapped mode with
  `GPU_PINNED_MIN_XFER_SIZE` (59-65 tok/s short, 36.7 at 240K; 240K cold prefill ~26 min); coding quality and a
  real harness session open — [owner](models/strata-qwen-flash-next.md#current-state-2026-10-30).

## Next steps

Execution order, dependencies and gates: [current plan](ENGINES-EXPERIMENTS.md#current-plan-2026-10-18).
27B flag tuning stays paused until Qwen4; engine-level runs are allowed (2026-10-23, [`DECISIONS.md`](DECISIONS.md)).

1. A2: check the harness compaction change in the next real session —
   [agent-traffic.md](measurements/agent-traffic.md#root-cause-speculative-compaction-on-the-local-slot-2026-10-03).
2. C1: Qwen4 on day one, gated by the coding suite (27B baseline 6/6 on the current engine:
   [results](../results/20261023-d1-pr30792q51-240k/README.md)); day-one checklist in
   [sop/new-model.md](sop/new-model.md#qwen4-day-one-checklist).
