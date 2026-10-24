# 2026-10-24: KV q8_0/q8_0 at 240K on the native q8_0/q5_1 TILE engine (E2)

**Question**: the engine adopted on 2026-10-23 ([D1](../20261023-d1-pr30792q51-240k/README.md))
dequantizes both `q8_0` and `q5_1` V inside the TILE kernel. Is KV `q8_0`/`q8_0` (21% less KLD than
`q8_0`/`q5_1`, [kv-quality.md](../../docs/measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16))
now worth its extra VRAM, and how much context does it leave?

## Setup

- Engine `llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix`, model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`,
  production flags except `-ctv q8_0` and `-c 245760` (`q8_0`/`q8_0` did not fit 262K on b11160);
  argv in `command-q8q8.json`.
- `bench/spec_depth_bench.py --run --depth 240000 --variants n3-map --reps 3 --kv q8_0 --ctx 245760 --extra "-ub 256"`,
  under `systemd-inhibit`, 272 W cap, temperature 0, same session as D1 (Brave closed).
- Reference: D1 arm B (`q8_0`/`q5_1`, `-c 262144`), same engine.

## Results

Mean of cached reps 2-4. Two references with the same `q8_0`/`q5_1` engine and flags: D1 arm B
(2026-10-23 23:17) and a rerun of it 30 minutes after this run (2026-10-24 00:33, arm A of the
[b11846 check](../20261024-engine-b11846-240k/README.md)); both give the same greedy text, yet essay
differs by 6.5% between them.

| Task | q8/q5_1 D1-B (tok/s) | q8/q5_1 rerun (tok/s) | q8/q8 @245,760 (tok/s) | q8/q8 vs. rerun | Acceptance q8q51 / q8q8 | Greedy text vs. q8/q5_1 |
|---|---|---|---|---|---|---|
| essay | 31.11 | 33.12 | 33.15 | +0.1% | 0.798 / 0.798 | differs |
| copy | 53.78 | 54.41 | 54.39 | -0.0% | 0.91 / 0.91 | identical |
| code | 22.39 | 22.49 | 23.84 | +6.0% | 0.435 / 0.481 | differs |

| Metric | q8/q5_1 @262K | q8/q8 @245,760 |
|---|---|---|
| Cold 240K prefill (tok/s) | 393.6 | 393.6 |
| Peak process VRAM (MiB) | 22,646 | 23,237 |
| Peak card VRAM used (MiB, of 24,560) | — | 24,117 |

## Conclusion

- Against the rerun reference, `q8_0`/`q8_0` decodes at the same speed on essay and copy. Code is +6%,
  but its greedy text differs and its MTP acceptance is higher (0.481 vs. 0.435), which alone predicts
  (1 + 3 × 0.481) / (1 + 3 × 0.435) = +5.8%, so the cost per step is unchanged. **No speed gain**; the
  first reading of +6.5% on essay was session-to-session variance in the D1 reference.
- What `q8_0`/`q8_0` buys is 21% less KV KLD (0.000587 vs. 0.000744,
  [kv-quality.md](../../docs/measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16)), for 591 MiB
  more VRAM at 16K less context, leaving ~440 MiB free on the card with the desktop running.
- Not adopted: the harness contract is a 262,144-token window (`AGENTS.md`), and 440 MiB of headroom
  is below what a browser or chat app has taken before ([coexistence.md](../../docs/measurements/coexistence.md)).
  It remains the quality-first alternative for a session that stays under 240K with a quiet desktop.
