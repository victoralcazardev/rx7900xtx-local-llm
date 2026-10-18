# Strata Coder IQ1_M at 262K KV int8 with `--vram-reserve-mib 3072` (2026-10-16)

**What.** The 262K int8 configuration from
[`20261015-strata-coder-context-steps/`](../20261015-strata-coder-context-steps/README.md) with one change:
3 GiB of VRAM kept free for the desktop, so a GPU app starting next to the model no longer pushes GPU memory
into RAM. It also finishes that run's 240K retrieval row (4 of 20 there) and repeats the Slack launch that
crashed the desktop. Goal: the full 262K context with 8-bit KV, without filling the card.

**Versions.** Strata `v0.1.44.1` (`296b59d2`), same engine build, Coder IQ1_M pack and MTP layer as the
2026-10-15 runs. `--max-context 262144 --kv int8 --resident-experts --spec 4 --vram-reserve-mib 3072`,
`STRATA_RESIDENT_PIN=0`, `STRATA_RESIDENT_HEADROOM_GIB=6`. The config JSON differs from the 2026-10-15 262K
one only by `--vram-reserve-mib 3072` (checked with `diff`).

**Machine.** RX 7900 XTX at the 272 W cap, Ryzen 7 5700X, 31.25 GiB RAM. KDE desktop, agent CLIs **and Brave
open** (the 2026-10-15 run had the browser closed), `/tmp` 8 MiB. `MemAvailable` before start: 25.71 GiB.

**Commands.**

```bash
./setup.sh --setup --family coder --model IQ1_M --gguf-dir <models>/Qwen3.8-Flash-Next-GSQ-RCO-Coder-IQ1_M \
  --backend hip --vision no --no-browser --yes --no-start --context 262144 --kv int8 --vram-reserve-mib 3072
qwen-flash start
STRATA_DIR=<strata clone> python3 strata_bench.py 120000 250000   # script: ../20261015-strata-coder-context-steps/
cd bench && python3 strata_longctx_quality.py --depths 240000 --docs 5
slack &   # then strata_bench.py with no depth (two short requests)
```

`watch-ram.log` samples every 2 s: `MemAvailable`, `GPUActive`, `GPUReclaim`, GTT, card-wide VRAM used (desktop
included, of 23.98 GiB), zram, swap used, `pswpin`.

## Results

| | 2026-10-15 (no reserve) | 2026-10-16 (`--vram-reserve-mib 3072`) |
|---|---|---|
| GPU expert cache | 7412 slots, 14.11 GiB | 6200 slots, 11.79 GiB |
| Experts in RAM (pageable copy) | 12.71 GiB | 15.03 GiB |
| VRAM free, engine start line | 604 MiB | 2,986 MiB |
| Card VRAM used, mean while loaded (desktop included) | 23.94 GiB (~0.04 GiB free) | 22.56 GiB (~1.42 GiB free) |
| Card VRAM used, peak (240K cold prefill) | 23.95 GiB | 23.40 GiB (0.58 GiB free) |
| Short gen (2 runs) | 56.0 / 65.0 tok/s | 54.4 / 56.6 tok/s |
| Deep ~120K (120,423 tokens) | 848 tok/s prefill, 60.1 tok/s gen | 773 tok/s prefill, 52.2 tok/s gen |
| Deep ~250K (141,945 new + 114,688 cached) | 733 tok/s prefill, 63.4 tok/s gen | 739 tok/s prefill, 55.1 tok/s gen |
| Min `MemAvailable` | 9.7 GiB | 6.20 GiB |
| Swap-in during the session | 1.33 GiB | 1.32 GiB |
| Slack launch | GTT 1.08 → 15.22 GiB in 4 s, OOM killer, KDE session ended | VRAM +0.11 GiB, GTT 0.43 → 0.44 GiB, no kernel message; short gen 49.0 / 49.1 tok/s with Slack and Brave open |

- No `stall report`, no engine restart, 1792 of 1792 lendable prompt slots kept in RAM, 0 blob reads.
- MTP drafts accepted: 368/564 and 373/558 short, 395/558 at ~120K, 504/713 at ~250K.
- One run per row and Brave open today: the speed deltas (-3% to -13% on gen, -9% on the 120K prefill) are
  in line with setup's "a few % of speed" for 2.3 GiB less expert cache, but are not a controlled A/B.

## Retrieval at 240K (5 documents, 20 questions)

Same test as the 2026-10-15 run (`bench/strata_longctx_quality.py`, temperature 0, thinking off, same seeds):
**20/20 exact**, 0 loops, 0 truncations, every answer `finish_reason: stop`. Cold prefill of each 240,000-token
document: 768-791 tok/s (~310 s); answer decode 53.5-101.8 tok/s. This completes the 240K row: 128K, 190K and
240K are now 20/20 each, like the 27B. Raw data: `quality-240k/` (documents not kept; same seeds rebuild them).

## Conclusion

`--vram-reserve-mib 3072` is what makes 262K + KV int8 usable on a card that also drives the desktop: the
card keeps ~1.4 GiB free in steady use (0.6 GiB at the prefill peak), and the Slack launch that took the
session down yesterday now costs 0.11 GiB of VRAM and nothing else. The price is ~2.3 GiB more experts in RAM
(15.03 GiB copy, `MemAvailable` down to 6.2 GiB with Brave open) and a few to ~13% decode in single runs,
still above the 45 tok/s bar at every depth. Retrieval is 20/20 at 128K, 190K and 240K. Start only with
`MemAvailable` ≥ 21 GiB (15.03 GiB copy + 6 GiB headroom), or the engine cuts the copy and reads the rest from the
SSD.
