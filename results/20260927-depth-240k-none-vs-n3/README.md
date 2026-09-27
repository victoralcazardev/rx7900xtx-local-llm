# 2026-09-27 — Spec-off vs. MTP n=3 at 240K fill, on the adopted 262K profile

**Measures**: the no-MTP reference at 240K fill on the exact adopted `262k-q8q51-mtp` flags
(engine `hip-kvmix`, KV q8_0/q5_1, `-ub 256`) — the comparison
[`docs/measurements/depth.md`](../../docs/measurements/depth.md) listed as missing — paired with
MTP n=3 on the same server flags, plus a spec-off KV q8_0/q8_0 control on the same engine to
explain the result.

## Method

- `bench/spec_depth_bench.py --run --depth 240000 --reps 3 --variants none n3 --extra "-ub 256"`
  (KV q8_0/q5_1 by default), then the control with `--variants none --kv q8_0`. Port overridden to
  18090 because another local process held the script's default port; nothing else changed.
- One server per variant, `-c 262144 -fa on -np 1 --ctx-checkpoints 4 -ngl all -ub 256`. Shared
  239,983-token document (wikitext-2), three tasks (essay / copy / code), temperature 0, seed 7,
  400 output tokens. Per task: one prefill warm-up request (discarded), then **three warm
  repetitions** reusing the cached prefix; figures are the medians of those three.
- Same environment and engine build as
  [`../20260927-probe-ab-262k/`](../20260927-probe-ab-262k/) (RX 7900 XTX, 272 W cap, llama.cpp
  b11160 `hip-kvmix`, ROCm 7.2.4 runtime, GSQ-RCO IQ3_S-mtp, desktop on the same card).
- Telemetry sanity check (spec-off q8_0/q5_1 run, warm phase): memory clock pinned at 1,249 MHz
  (maximum), 166-208 W against the 272 W cap, 0 evicted bytes, GTT growth ≤ 48 MiB — the low
  spec-off figure is not a clock, power or spill artifact.

## Results (generation tok/s at 240K fill)

| Variant | Essay | Copy | Code | **Mean** | vs. spec-off (same KV) | Acceptance | Prefill | Peak process VRAM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| spec off, KV q8_0/q5_1 | 11.1 | 11.2 | 11.2 | **11.2** | — | — | 402 | 20,102 MiB |
| **MTP n=3, KV q8_0/q5_1** (adopted) | 24.2 | 27.0 | 18.8 | **23.3** | **+109%** | 0.687 (2412/3510) | 386 | 22,631 MiB |
| spec off, KV q8_0/q8_0 (control) | 14.9 | 14.9 | 15.0 | **14.9** | — | — | 405 | 21,381 MiB |

Per-task acceptance for n=3: essay 0.77, copy 0.87, code 0.50. Warm-repetition spread ≤ 0.4 tok/s
in every cell. Hotspot peaked at 99-101°C, 0 evicted in all three runs. The copy task produced
byte-identical output with and without MTP (same sha256); essay and code diverge at temperature 0,
as already recorded in `speculative.md` (different verification batch sizes change the rounding).

## Conclusion

- **At the adopted configuration, MTP n=3 more than doubles decode speed at 240K fill (+109%)**,
  more than its empty-context gain on the same profile (+85%, measured with the community
  `probe.py` in `../20260927-probe-ab-262k/`; different prompts and sampling, so compare the two
  deltas as a shape, not to the decimal). This reverses the earlier "MTP's gain shrinks sharply at
  depth (+15-50%)" reading, which was measured against a KV **q8_0/q8_0** spec-off baseline
  (Case D in `depth.md`, 16.0 tok/s), not against the adopted q8_0/q5_1 KV.
- **The adopted V-cache type is what the spec-off path pays for**: spec-off with V q5_1 decodes
  25% slower than with V q8_0 at the same depth (11.2 vs. 14.9 tok/s), on the same engine and flags.
  Spec-off decode runs through the VEC FlashAttention kernel, which dequantizes K and V in place for
  every query row; MTP's 4-token verify batches run through TILE, which converts the KV cache to
  f16 per step and then reads f16. Hypothesis, not measured: most of the q5_1 dequant cost
  therefore does not reach the MTP path. MTP n=3 with KV q8_0/q8_0 at 240K was not measured
  (262K with MTP and KV q8_0/q8_0 is recorded as not reliable on this card: a `Memory access fault` at ~104K fill; see `depth.md`), so this run does
  not isolate how much V q5_1 costs *with* MTP.
- Against the q8_0/q8_0 spec-off control, the adopted profile (q8_0/q5_1 + MTP n=3) is still
  **+57%** at 240K, while fitting the full 262K window with MTP.
- The control's 14.9 tok/s is close to the older Case D figure (16.0, official b11160 binary,
  `-ub 512`, 2026-09-24), which is consistent; the ~7% gap is not investigated.

**Raw data**: per-variant server logs, SSE streams and telemetry in local `bench/res/` (git-ignored).
Curated here: [`summary.jsonl`](summary.jsonl) (none + n3), [`summary-q8q8-control.jsonl`](summary-q8q8-control.jsonl),
and the exact argv per variant in `command-*.json`. Measurements doc:
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md#mtp-vs-spec-off-at-240k-fill-adopted-profile-2026-09-27).
