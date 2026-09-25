# Concurrency: multiple slots (`-np`) on one server

## Current conclusion

- **Parallel slots are not free on this GPU.** A slot's long prefill starves generation on the
  other slots (see the mechanism below), and end-to-end wall time to serve several requests is
  higher with more slots than with 1 slot + MTP and a queue: serving 2 requests took 8.6% longer
  with 2 slots + MTP and 6.0% longer with 2 slots without MTP than queuing them through 1 slot;
  serving 4 requests took 25.6% longer with 4 slots than queuing them through 1 slot. See the
  table below for the exact figures.
- **For multi-agent use** (several terminals/agents sharing one `llama-server` process): keep
  **1 slot + MTP** and let requests queue, instead of adding `-np` slots. The wall-time cost of
  concurrent slots is modest at 2 slots but grows at 4; concurrent slots also add an interactive
  latency penalty — an agent that is already generating drops from ~50 to ~6-13 tok/s whenever
  another agent's long prompt arrives (see below). See [`../DECISIONS.md`](../DECISIONS.md).
- This is measured with a **prefill-heavy workload** (a 32K-token prompt per slot, 300-token
  output) and a **single run per case** — see "Caveats" below before generalizing.

## 1 vs. 2 vs. 4 slots, MTP on/off (2026-09-25)

Engine `hip-kvmix` (own ROCm 10 build), Qwen3.8-27B GSQ-RCO IQ3_S-mtp, `-c 204800`, KV
`q8_0/q8_0`, `--kv-unified`, MTP `--spec-draft-n-max 2` where noted, one 32,000-token prompt per
slot, 300 forced output tokens per slot, temperature 1 (vendor sampling), power cap 272 W (this
card's driver minimum — see `thermals-power.md`). One run per case.

### End-to-end wall time vs. queuing through 1 slot

The only direct single-slot measurement is `s1-mtp`: 300 tokens (one request) in 49.9 s wall
time, including its 32K prefill. Queuing *N* such requests through 1 slot is estimated as
*N* × 49.9 s (no other single-slot case was measured — see the caveat below the table).

| Case | Slots | MTP | Requests | Wall time (measured) | Wall time queued via 1 slot+MTP (estimated) | Overhead |
|---|---:|---|---:|---:|---:|---:|
| s1-mtp | 1 | yes | 1 | 49.9 s | 49.9 s (baseline) | — |
| s2-mtp | 2 | yes | 2 | 108.4 s | ~99.9 s | **8.6% worse** |
| s2-nomtp | 2 | no | 2 | 105.9 s | ~99.9 s | **6.0% worse** |
| s4-nomtp | 4 | no | 4 | 250.9 s | ~199.8 s | **25.6% worse** |

- The queued estimate reuses the `s1-mtp` baseline (49.9 s) for every row, including the two
  no-MTP cases — the no-MTP single-slot time was not measured, and the true (slower) no-MTP
  baseline would shrink the computed overhead, so the no-MTP overhead figures above (6.0%,
  25.6%) are an **upper bound**, not a lower one.
- MTP raises the non-starved slot's own decode rate (26.4 vs. 23.0 tok/s, see the per-slot table
  below), but that did not translate into a faster 2-slot wall time in this single run (108.4 s
  with MTP vs. 105.9 s without — within the noise of a one-run measurement). The 1-slot MTP
  decode benefit itself is not in question here; see [`speculative.md`](speculative.md).
- Raw data and exact commands:
  [`../../results/20260925-concurrency-slots/`](../../results/20260925-concurrency-slots/).

### Per-slot decode rate (secondary — not an aggregate)

`timings.predicted_per_second` per slot. **This is a per-slot diagnostic only; do not sum it
across slots as an "aggregate throughput"** — see the end-to-end wall-time table above for that.

| Case | Slots | MTP | Per-slot tok/s | Peak process VRAM | Peak hotspot |
|---|---:|---|---|---:|---:|
| 1 slot | 1 | yes | 49.6 | 21,646 MiB | 96°C |
| 2 slots | 2 | yes | 5.7, 26.4 | 22,126 MiB | 97°C |
| 2 slots | 2 | no | 5.7, 23.0 | 19,529 MiB | 95°C |
| 4 slots | 4 | no | 1.5, 2.1, 3.6, 12.8 | 20,135 MiB | 98°C |

GTT stayed at 8.1 MiB and evicted at 0 MiB in every case (no VRAM spill).

- **Why the slowest slot is slow**: in every multi-slot case, the slot that *finishes its own
  prefill first* is the one that decodes slowest — not the slot still prefilling. In `s2-mtp`,
  slot 0 finishes its 32K prefill first (47.4 s) and then decodes at only 5.7 tok/s over the next
  52.3 s while slot 1 is still prefilling (92.5 s total); slot 1, once its own prefill is done,
  decodes at 26.4 tok/s essentially alone. The same inverse pattern holds in `s4-nomtp`: ordered
  by prefill-finish time, slot 1 finishes first (46.1 s) and has the slowest decode (1.5 tok/s),
  then slot 3 (63.3 s prefill, 2.1 tok/s decode), then slot 0 (72.8 s prefill, 3.6 tok/s decode),
  then slot 2 finishes last (223.0 s prefill) and has the fastest decode (12.8 tok/s). This
  matches llama.cpp's documented `-np`/`--kv-unified` behavior: slots share one compute stream,
  so a slot that is already generating is starved by another slot's *concurrent* prefill — not
  the reverse (a slot's own prefill wait cannot lower its own decode-only
  `predicted_per_second`). See the llama.cpp server README, `docs/SOURCES.md`.
- **Caveats**:
  - Single run per case, no repetition — treat as a data point, not a stable average
    (`docs/BENCHMARK-FORMAT.md` "n (repetitions)").
  - Prefill-heavy: every slot's prompt is a fresh 32K-token cold-cache prefill with only a
    300-token response. A workload with smaller prompts or more cache reuse between requests
    would be penalized less by concurrent prefill.
  - `aggregate_tok_s` in the raw `summary.jsonl` (total predicted tokens ÷ wall time including
    prefill) is exactly the quantity behind the end-to-end wall-time comparison above — it is the
    right metric for "how long to serve N requests", but do not read it as a per-request
    generation speed; for that, use per-slot `timings.predicted_per_second` (the table above).
  - Interactive-latency trade-off of queuing is not measured directly here: with 1 slot, a second
    queued agent waits for the first request to finish before its own prefill even starts (~50 s
    in this measurement); with 2 slots its prefill starts immediately and still completes in
    about the same time as the 1-slot case (47-92 s depending on which slot), but its subsequent
    generation can then stall to ~6 tok/s while the other slot's prefill runs.
  - Measured at 32K depth only, under a 272 W power cap (not the 303 W default) — not repeated at
    other depths or at the default power limit.

## History

- **2026-09-25**: first concurrency measurement (1/2/4 slots, MTP on/off, 32K depth); recommends
  1 slot + MTP with queuing for multi-agent use over adding slots.
