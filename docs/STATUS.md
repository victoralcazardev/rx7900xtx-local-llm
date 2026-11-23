# Status

The setups documented side by side, their headline numbers, flag rationale and what is open. Other
docs link here instead of repeating them.

**Scope.** This file holds only the current state. Each open question or next step is one line
that links its owner; results, candidate lists, trial details, upstream watch lists and analysis
live in the owner doc ([`STYLE.md`](STYLE.md) §8), never here. Budget: 1,000 words. Tried and not
adopted: [`TRIED.md`](TRIED.md); planned engine trials:
[`ENGINES-EXPERIMENTS.md`](ENGINES-EXPERIMENTS.md).

## Setups in use

No setup is the recommended one; `scripts/launch.py` falls back to `inkling2-mini-unc-q8d` /
`315k-maya` (315,392 context; omp compacts it at 75%) — the setup last in use, not a recommendation ([`DECISIONS.md`](DECISIONS.md), 2026-11-23).

### Inkling-2-Mini uncensored on `maya-ik2` (`inkling2-mini-unc-q8d` / `262k-maya`)

- Model: Abiray Inkling-2-Mini-Uncensored `IQ4_NL` (13.90 GB, OpenUncensored edit) with its head
  and 176 non-expert attention/conv matrices re-typed to Q8_0: experts and `token_embd` unchanged,
  15.4 GB, rebuilt by `results/20261123-inkling-round/raw/retype_q8.py`. Cards, quants and the fork
  comparison: [`models/inkling-2-mini.md`](models/inkling-2-mini.md).
- Engine: `maya` = GodGMN `maya-inkling-mini` branch `hip-port` `f472e94` (rollback `2b31ffeaa`),
  the Inkling-only HIP port, not llama.cpp. Paged E4M3 KV, `--chunk 2048`, and the env
  `IK2_PAGED_KV=1` plus `ROCBLAS_TENSILE_LIBPATH=/opt/rocm/lib/rocblas/library`.
  [`ENGINES.md`](ENGINES.md).
- Sampling: vendor `temperature 1.0` (the card sets nothing else) and the reasoned `min_p 0.0`;
  `top_p`/`top_k` stay unset. Text only: the port takes no mmproj.
- Power: 272 W permanent cap (driver minimum; stock 303 W) — [`sop/power-cap.md`](sop/power-cap.md).
- Harness wiring, shared by every setup: one provider `local-262k` on `:8080` at the full 262144;
  every model compacts at ~35% of its window. `check-sync.py` checks provider, port and window when
  `local.toml` has `[harness] enabled = true`, not the compaction settings. Hermes profiles use the
  same endpoint, exposed to the tailnet by `tailscale serve` without a key
  ([`DECISIONS.md`](DECISIONS.md), 2026-10-23).

```bash
python3 scripts/launch.py            # launcher fallback; add --dry-run to print only
python3 scripts/launch.py inkling2-mini-unc-q8d --profile 315k-maya   # or 262k-maya
# the maya backend writes _tmp/maya/inkling2-mini-unc-q8d.maya.json from models.toml plus the
# port's gfx1100 preset and runs, in the f472e94 worktree:
#   .venv/bin/python serve/server.py --engine maya --config <that json> --port 8080 \
#     --tokenizer ik2/tokenizer
# context 262144, IK2_KV=fp8, IK2_PAGED_KV=1 (16-token pages), --chunk 2048, temp 1.0
```

### Qwen3.8-27B abliterated on llama.cpp `hip-kvmix` (`huihui-iq3s-mtp` / `262k-q8q51-mtp`)

`hip-kvmix` = llama.cpp v0.9.0 + the local `q8_0`/`q5_1` TILE patch. Huihui file: 22.12 GiB peak at
262K, 50.6 / 166.8 / 43.1 tok/s essay/copy/code at 64K fill (b11846; -4.6% on copy on v0.9.0), and no
240K or quality run: those belong to the stock GSQ-RCO quant, kept as the measured reference
(`qwen38-iq3s-mtp`), not a listed setup. Launch:
`python3 scripts/launch.py huihui-iq3s-mtp`; flags and numbers:
[`models/qwen38-27b.md`](models/qwen38-27b.md).

### Qwen3.8-Flash-Next on Strata (runs; no set installed here)

Flash-Next runs on one 24 GB card with Strata, experts streamed from host RAM/SSD, with many published
quants upstream. On this 32 GiB host the experts did not all fit, so our last sets read them from the SSD
at 2.6-12.8 tok/s: our numbers measure that limit, not Strata. Follow
[Strata](https://github.com/Niko1221/Strata)'s latest release, quants and recommended settings. No set
installed here: the 2026-11-22 SC117 run read its dense shard from the HDD, which is not a valid measurement (every
file must be on the NVMe, [SOP](sop/strata.md)) ([watch list](sop/upstream-watch.md),
[history](models/strata-qwen-flash-next.md#current-state-2026-11-05)).

## Headline numbers

Inkling-2-Mini on `maya-ik2`, the port's `tools/ik2_bench.py`: 50,206 token IDs of this repo's docs
cycled to each depth, uncached, 129 generated tokens, 3 repeats (2 at 262K), median, 272 W cap.

- **Decode**: 106.1 / 98.2 / 90.0 / 68.9 / 53.6 tok/s at 512 / 8K / 32K / 128K / 262K fill; prefill
  2,276 / 3,429 / 2,960 / 1,929 / 1,298 tok/s ([round](../results/20261123-inkling-round/README.md)).
- **VRAM**: 22,304 MiB device-wide serving 262K on the previous port build, 22,029 MiB on `f472e94`
  (`rocm-smi`); 3,498 MiB free before graph capture.
- **Quality**: GSM8K greedy **187/192** (the untyped file: 188/192); 0/8 keyword refusals (on
  `2b31ffeaa` the loop guard cut one answer; `f472e94` drops the repeats); a valid tool call and
  12,216 of 12,253 prompt tokens reused. 262K retrieval 3/3: untyped file only.
- **Comparison, same bench**: the untyped file decodes 95.7 / 88.2 / 82.3 / 64.2 tok/s (so the Q8_0
  re-type is the +7-11%) and the llama.cpp fork profile 57.6 / 44.5 / 37.8 at 512 / 128K / 262K
  ([owner](models/inkling-2-mini.md)).

## Flags and why

Settings of the `262k-maya` profile; the Qwen3.8-27B profile keeps its own table in
[`models/qwen38-27b.md`](models/qwen38-27b.md).

| Setting | Why |
|---|---|
| `-c 262144` | Native context (the port reserves 393,216 positions); matches `local-262k` |
| KV E4M3 paged (`IK2_KV=fp8`, `IK2_PAGED_KV=1`) | 16-token global pages: +29% decode and +13% prefill over token-major KV at 262K. `fp8-global` no gain, `fp4-global` -16/-34% at 32K/128K — [round](../results/20261123-inkling-round/README.md), [maya vs. fork](../results/20261122-inkling-maya-vs-fork/README.md) |
| `--chunk 2048` | Alone no gain (39.5 vs. 39.6 tok/s and 1,157 vs. 1,138 prefill at 262K); the paged-KV arm ran with it; `--chunk 1024` under paging no better |
| `ROCBLAS_TENSILE_LIBPATH` | The port's venv rocBLAS lacks the gfx1100 Tensile files; the first GEMM dies without the system library |
| `temp 1.0`, `min_p 0.0` | The vendor card sets temperature only; `min_p 0.0` overrides the binary's 0.05 ([`AGENTS.md`](../AGENTS.md)) |
| no `top_p`/`top_k`, no drafter | The card states neither, and DSpark decodes 4-17% slower on this build — [`models/inkling-2-mini.md`](models/inkling-2-mini.md) |

## Open questions

- **Inkling quality beyond GSM8K**: the six-task coding suite and the 68-case 240K retrieval set
  have not run on this model, so quality parity between the setups is unmeasured —
  [`models/inkling-2-mini.md`](models/inkling-2-mini.md#comparison-plan-open).
- **Full cache misses in long sessions**: cause found (speculative compaction on the single local
  slot), harness change in place, 2026-10-03/04 logs classified —
  [agent-traffic.md](measurements/agent-traffic.md#first-session-after-the-compaction-change-2026-10-03-evening-single-session).
- **Compaction threshold and presence penalty** A/B only after a fixed coding-task suite exists;
  checkpoints settled at 10 (2026-11-06) — [agent-traffic.md](measurements/agent-traffic.md#open-ab-tests).
- **KVMem**: not adopted until a real agent run —
  [ENGINES-EXPERIMENTS.md](ENGINES-EXPERIMENTS.md#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted).

## Next steps

Execution order, dependencies and gates: [current plan](ENGINES-EXPERIMENTS.md#current-plan-2026-10-18).
27B flag tuning stays paused until Qwen4; engine-level runs are allowed (2026-10-23, [`DECISIONS.md`](DECISIONS.md)).

1. Run the coding suite and the 68-case retrieval set on Inkling (quality question above).
2. A2: check the harness compaction change in the next real session —
   [agent-traffic.md](measurements/agent-traffic.md#root-cause-speculative-compaction-on-the-local-slot-2026-10-03).
3. C1: Qwen4 on day one, gated by the coding suite (27B baseline 6/6:
   [results](../results/20261023-d1-pr30792q51-240k/README.md)); checklist in
   [sop/new-model.md](sop/new-model.md#qwen4-day-one-checklist).

## Current profile

Renamed to [Setups in use](#setups-in-use) on 2026-11-23; this heading stays so older links resolve.
