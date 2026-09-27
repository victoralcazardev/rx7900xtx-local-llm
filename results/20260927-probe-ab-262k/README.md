# 2026-09-27 — Empty-context MTP A/B with the community `probe.py` (262K profile)

**Measures**: the empty-context decode gain of MTP on the adopted `262k-q8q51-mtp` profile,
using the exact instrument and contract of the
[sudoingX/qwen38-mtp](https://github.com/sudoingX/qwen38-mtp) community table, so the numbers
can be compared with (and contributed to) that table. Also sweeps `--spec-draft-n-max` 2/3/4
and `--spec-draft-p-min` 0.60/0.75 at n=3.

## Method

- Instrument: that repository's `probe.py`, **unmodified**, at commit `1e514a8` (sha256
  `d9ea0c9fb10435937c774d4b182a6b5ac8481837e8b3d1aa23738eeb178dfd5f`). Streaming chat
  requests, three prompts (Python code / prose / Bash) × three runs, 400 max tokens, thinking off
  (`enable_thinking: false`), one warm-up request per pass. It sends no sampling parameters, so
  the server's vendor sampling applies (temperature 1.0, top-p 0.95, top-k 20, min-p 0).
- Runner: [`bench/probe_ab.py`](../../bench/probe_ab.py). One server per arm, **three complete
  probe passes per arm**; the row figure is the median of the three pass medians. Both arms at
  `--parallel 1`; only the speculative flags differ.
- Serving flags (every arm): `-c 262144 -ctk q8_0 -ctv q5_1 -fa on -np 1 --ctx-checkpoints 4
  -ngl all -ub 256 --reasoning-effort medium` plus the vendor sampling above. Exact argv per
  arm in `summary.jsonl`.
- Acceptance: summed from the server log's `draft acceptance` lines, **warm-up requests
  excluded** (27 measured requests per arm).
- Environment: RX 7900 XTX 24 GB (reference board), 272 W power cap, Ryzen 7 5700X, CachyOS
  kernel 7.2.7, Mesa 26.2.3; engine `hip-kvmix` = llama.cpp b11160 (`70c4e1582`) built for
  gfx1100 with the ROCm 10.0.0 toolchain plus `GGML_CUDA_FA_QUANTS` including `q8_0-q5_1`
  (build recipe in [`docs/ENGINES.md`](../../docs/ENGINES.md)), running on the system ROCm 7.2.4
  runtime. Model: ISTA-DASLab `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` (12,120,016,960 B, sha256
  `58fd826723939933dc86f45b7fe04545cbc2de1c70f6fe2cdd3858c87a98c12f`), no mmproj loaded.
- **Not headless**: the desktop ran on the same card (~1.1-1.2 GiB VRAM before serve). System
  GTT stayed flat at ~530 MiB (the desktop's own baseline) in every arm, so no weights spilled
  to host memory (the community README's rule 7).

## Results (tok/s)

| Arm | Pass medians | **Row** | Code / prose / Bash | vs. spec-off | Acceptance (aggregate) | Per-request range |
|---|---|---:|---|---:|---:|---|
| spec off | 37.2 / 37.2 / 37.2 | **37.2** | 36.9 / 37.3 / 37.1 | — | — | — |
| n=2 | 67.9 / 68.6 / 69.3 | **68.6** | 76.5 / 59.3 / 68.6 | +84% | 0.796 (4793/6018) | 0.51-0.95 |
| **n=3** (adopted) | 68.9 / 70.9 / 67.3 | **68.9** | 82.1 / 51.9 / 68.9 | **+85%** | 0.715 (5059/7076) | 0.38-0.95 |
| n=4 | 64.8 / 66.9 / 67.3 | **66.9** | 87.1 / 46.3 / 66.9 | +80% | 0.624 (5287/8477) | 0.31-0.92 |
| n=3, p-min 0.60 | 66.2 / 65.2 / 66.5 | **66.2** | 78.2 / 46.7 / 66.2 | +78% | 0.848 (4713/5559) | 0.64-0.97 |
| n=3, p-min 0.75 | 59.8 / 59.4 / 61.0 | **59.8** | 79.2 / 45.1 / 59.8 | +61% | 0.912 (4832/5297) | 0.77-0.99 |

Per-prompt acceptance, n=2 / n=3 / n=4: code 0.92 / 0.91 / 0.86, prose 0.60 / 0.45 / 0.35,
Bash 0.79 / 0.71 / 0.59.

System VRAM (sysfs, includes the desktop) after load → after the three passes: spec off 21,062 →
21,519 MiB; n=2 22,891 → 23,627; n=3 23,081 → 23,741; n=4 23,270 → 23,901 MiB. Spec-on costs
~1.8-2.0 GiB over spec-off at 262K (MTP head, its draft context and compute buffers).

## Conclusion

- **n=2 and n=3 tie at empty context** (68.6 vs. 68.9, inside pass-to-pass noise of ±2 tok/s).
  n=3 stays the default because it wins at the profile's real operating depth (240K), where
  spec-off is also measured now: see
  [`../20260927-depth-240k-none-vs-n3/`](../20260927-depth-240k-none-vs-n3/).
- **n=4 is past the optimum**: code keeps climbing with depth (76.5 → 82.1 → 87.1) but prose
  falls at every extra slot (59.3 → 51.9 → 46.3) — the same shape every 24 GB row in the
  community table reports.
- **`--spec-draft-p-min` raises acceptance and lowers speed** on this card (0.715 → 0.912
  acceptance, 68.9 → 59.8 tok/s at 0.75). This matches that repository's "fast card" rule;
  not adopted.
- Relative to the other RX 7900 XTX rows in the community table (131K context, KV q4_0): this is
  the full 262K window with higher-precision KV (q8_0/q5_1) and a smaller IQ3_S quant, and its
  spec-off baseline (37.2) sits between the ROCm row (36.3) and the Windows/Vulkan row (41.0).

**Raw data**: per-arm server logs and probe outputs, local only (git-ignored). Summary with exact argv, pass-level runs and per-request acceptance:
[`summary.jsonl`](summary.jsonl). Measurements doc:
[`../../docs/measurements/speculative.md`](../../docs/measurements/speculative.md#community-probe-ab-at-262k-empty-context-2026-09-27).
