# Qwen3.8-27B GSQ-RCO IQ3_S-mtp (one of several setups)

Owns the Qwen3.8-27B long-context setup: model, engine, flags, sampling and every 240K number. It
was the launcher fallback from 2026-09-26 until 2026-11-23, when the repository stopped
recommending any setup and that fallback moved to Inkling-2-Mini ([`DECISIONS.md`](../DECISIONS.md));
the setup itself is unchanged, `262k-q8q51-mtp` on the `hip-kvmix` engine.

Other quants of this model, the architecture and what was rejected:
[`qwen38-27b-quants.md`](qwen38-27b-quants.md). The other setups: [`STATUS.md`](../STATUS.md).

## Model

`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp` (ISTA-DASLab GSQ-RCO quant of the Qwen card, native MTP head baked
in), 12.1 GB, PPL 6.734 ± 0.084. `mmproj-Qwen3.8-27B-BF16.gguf` is present but vision is disabled
in the 262K profile. Sampling is the Qwen3.8-27B card's own, also quoted in the quant repo's
README: `temp 1.0`, `top_p 0.95`, `top_k 20`, plus the repository's explicit `min_p 0.0` (the binary
default 0.05 is not what the vendor tested, [`AGENTS.md`](../../AGENTS.md)).

SHA256 of this repository's copies (Hugging Face publishes none):

| File | SHA256 |
|---|---|
| `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` | `58fd826723939933dc86f45b7fe04545cbc2de1c70f6fe2cdd3858c87a98c12f` |
| `mmproj-Qwen3.8-27B-BF16.gguf` (vision, off in the 262K profile) | `13cb7bebccbd04afc8f4090cb949ecf8937cdf7377c5799b1a0c594e7c0d3e16` |

## Launch

```bash
python3 scripts/launch.py qwen38-iq3s-mtp                      # profile 262k-q8q51-mtp
python3 scripts/launch.py qwen38-iq3s-mtp --dry-run            # print the command only
```

`launch.py` expands the profile into this `llama-server` command (`hip-kvmix` engine):

```bash
llama-server -m <models_root>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
  --port 8080 -c 262144 -ctk q8_0 -ctv q5_1 \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  -fa on -np 1 --ctx-checkpoints 10 -ngl all --metrics \
  --spec-type draft-mtp,ngram-map-k4v --spec-draft-n-max 3 -ub 256 --reasoning-effort medium \
  --cache-ram 12288
```

The harness provider `local-262k` on `:8080` advertises the full 262144;
`python3 scripts/check-sync.py` verifies it when `local.toml` has `[harness] enabled = true`.

## Flags and why

| Flag | Why |
|---|---|
| `-c 262144` | Full native context; matches the wired `local-262k` provider |
| `-ctk q8_0 -ctv q5_1` | `q8_0/q8_0` is near-free (KLD 0.000587 vs. f16); `q5_1` V costs +27% KLD but fits 262K in 24 GB; `q4_0/q4_0` has 4x KLD — [kv-quality.md](../measurements/kv-quality.md) |
| `-fa on` | Mandatory with a quantized V cache; avoids a silent slow-path fallback — [engines.md](../measurements/engines.md) |
| `--spec-type draft-mtp,ngram-map-k4v` | MTP head in the GGUF (no separate draft model) plus an n-gram drafter over the slot's own tokens: large gains when output copies context, lossless at temperature 0 — [speculative.md](../measurements/speculative.md) |
| `--spec-draft-n-max 3` | +9-11% mean tg over n=2 at the real 190K/240K depths; n=4 loses 9-23% at 240K — [speculative.md](../measurements/speculative.md), [`TRIED.md`](../TRIED.md) |
| `-ub 256` | -350 MiB peak VRAM vs. 512, -5% prefill, no generation cost — [memory.md](../measurements/memory.md) |
| `-np 1` | Single user; one slot + MTP with queuing beats more slots — [concurrency.md](../measurements/concurrency.md) |
| `--ctx-checkpoints 10` | The default 32 is wasteful; 4 evicted the system-prompt checkpoint before each ~35% compaction (48K re-processed, 70 s); 10 keeps it (20K, 33 s) at peak RssAnon 11.5 GiB — [replay](../../results/20261106-ctx-checkpoints-replay/README.md) |
| `--cache-ram 12288` | The 8192 default evicts a ~180K main state (7.7 GiB) when a side request is cached (412 s re-prefill); 12288 restores it in 1.8 s — [memory.md](../measurements/memory.md#host-prompt-cache-eviction-with-a-side-request-2026-10-03) |
| `-ngl all` | All layers on GPU, explicit rather than `auto` |
| `--reasoning-effort medium` | Template default `xhigh` injects "think carefully..." and overthinks; `medium` adds no instruction — `models.toml` |
| `--metrics` | Exposes `/metrics` for the token usage ledger — [token-ledger.md](../sop/token-ledger.md) |

## Measured numbers

Each number comes from the build that produced it: the 240K figures are b11846 (`1a24df1`) + the
`q5_1` patch, and the empty-context 76.3 tok/s is b11820 + the same patch. The engine in use since
2026-11-05 (v0.9.0, `cd959ba`) has no 240K run and measured -4.6% decode at 64K on identical text.
All at the 272 W cap, temperature 0 unless stated.

- **240K fill, essay/copy/code**: 33.2 / 54.7 / 22.5 tok/s, prefill 395 tok/s, peak process VRAM
  22,645 MiB — [results](../../results/20261024-engine-b11846-240k/README.md); the TILE patch adds
  18-27% ([D1](../../results/20261023-d1-pr30792q51-240k/README.md)); cross-session spread up to ~6%.
- **Empty context**: 76.3 tok/s with MTP n=3 (39.1 without), community `probe.py`, 3 passes —
  [results](../../results/20261024-probe-ab-262k-pr30792q51/README.md).
- **Without MTP at 240K fill** (b11160): 11.2 tok/s, so MTP n=3 is +109% at depth —
  [speculative.md](../measurements/speculative.md#mtp-vs-spec-off-at-240k-fill-adopted-profile-2026-09-27).
- **n-gram map on MTP**: copy at 240K 43.9 vs. 27.0 tok/s (+62%), other tasks -0-2%, temperature-0
  output identical — [results](../../results/20261003-ngram-mtp-stacking/README.md).
- **Quality (retrieval only)**: 68/68 pooled across configurations from 32K-240K (0 loops), plus
  40/40 at 190K and 240K on the adopted KV/MTP flags; real agent history at 80K/176K with
  production sampling: 15-16/16 and 14-15/16, no position-dependent loss —
  [depth.md](../measurements/depth.md#current-conclusion). The six-task coding suite last passed 6/6
  on b11846 + the patch ([results](../../results/20261024-engine-b11846-240k/README.md),
  [`DECISIONS.md`](../DECISIONS.md) 2026-10-24); it has not run on v0.9.0 (the 2026-11-05 switch was
  an operator choice with no engine A/B).

## Engine

`hip-kvmix` = llama.cpp v0.9.0 (`cd959ba`) + the local PR #30792 patch extended to V `q5_1`: an
own ROCm build whose FlashAttention TILE kernel dequantizes K `q8_0` + V `q5_1` natively. In use
since 2026-11-05 by operator choice (-4.6% decode at 64K vs. b11846, same VRAM); rollback b11846.
Build flags, SHA256, the published release and the runtime `libamdhip64` workaround:
[`ENGINES.md`](../ENGINES.md).

A newer build waits for an A/B: b12633 (the first release past the v1.0.0 tag, which renamed the
FlashAttention symbols) is built with the rebased patch and kept as a candidate, and the user
deferred its 240K pair and coding-suite run to Qwen4. The Qwen engine does not change until that
A/B exists ([`DECISIONS.md`](../DECISIONS.md), [`ENGINES.md`](../ENGINES.md)).

## Open

- Coding quality beyond the 6/6 suite and the 240K retrieval tests is not measured; the fixed
  coding suite with seeds and pass/fail criteria is the gate for any further 27B tuning
  ([`ENGINES-EXPERIMENTS.md`](../ENGINES-EXPERIMENTS.md)).
- 27B flag tuning stays paused until Qwen4; engine-level A/Bs are allowed
  ([`DECISIONS.md`](../DECISIONS.md), 2026-10-23).
