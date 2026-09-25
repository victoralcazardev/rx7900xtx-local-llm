# 2026-09-25 — multi-agent concurrency: 1 vs. 2 vs. 4 slots, MTP on/off

**Measures**: per-slot and aggregate generation speed when several requests share one
`llama-server` process (`-np` slots), with and without MTP, at a fixed per-slot prompt size — the
scenario of several terminals/agents sharing one server (see
`../../docs/measurements/concurrency.md`).

**Conditions**: engine `hip-kvmix` (own ROCm 10 build), model Qwen3.8-27B GSQ-RCO IQ3_S-mtp,
`-c 204800`, KV `q8_0/q8_0`, `--kv-unified`, MTP `--spec-draft-n-max 2` where noted, one 32,000-token
prompt per slot (`wiki.train`-derived), 300 forced output tokens per slot, temperature 1 (vendor
sampling), power cap 272 W (this card's driver minimum; factory default is 303 W — see
`../../docs/measurements/thermals-power.md`). One run per case (single sample, not repeated).

**Command**: `bench/concurrency_bench.py` — starts the server once per case with the given `-np`,
fires one request per slot concurrently, and records per-slot `timings` plus fdinfo-based VRAM/GTT
and hwmon temperature peaks for the whole run.

**Files** (personal machine paths replaced with placeholders: model path with `~/models/...`,
engine binary path with `~/engines/<build-dir>/llama-server`; per-request prompt/SSE files are not
published — see `docs/BENCHMARK-FORMAT.md` "How `results/` is laid out"):

- `summary-s1-mtp.jsonl` / `command-s1-mtp.json` — 1 slot, MTP n=2 (`-np 1`).
- `summary-s2-mtp.jsonl` / `command-s2-mtp.json` — 2 slots, MTP n=2 (`-np 2`).
- `summary-s2-nomtp.jsonl` / `command-s2-nomtp.json` — 2 slots, no MTP (`-np 2`).
- `summary-s4-nomtp.jsonl` / `command-s4-nomtp.json` — 4 slots, no MTP (`-np 4`).

**Results — end-to-end wall time vs. queuing through 1 slot** (the `s1-mtp` case is the only
single-slot measurement: 300 tokens, including a 32K prefill, in 49.9 s; queuing *N* requests
through 1 slot is estimated as *N* × 49.9 s):

| Case | Slots | MTP | Requests | Wall time (measured) | Wall time queued via 1 slot+MTP (estimated) | Overhead |
|---|---:|---|---:|---:|---:|---:|
| s1-mtp | 1 | yes | 1 | 49.9 s | 49.9 s (baseline) | — |
| s2-mtp | 2 | yes | 2 | 108.4 s | ~99.9 s | 8.6% worse |
| s2-nomtp | 2 | no | 2 | 105.9 s | ~99.9 s | 6.0% worse |
| s4-nomtp | 4 | no | 4 | 250.9 s | ~199.8 s | 25.6% worse |

The no-MTP overhead figures reuse the `s1-mtp` baseline (no no-MTP single-slot case was
measured); the true, slower no-MTP baseline would shrink the computed overhead, so 6.0% and
25.6% are an **upper bound**, not a lower one.

**Per-slot decode rate** (`predicted_per_second`, tok/s — a per-slot diagnostic, not summed into
an aggregate):

| Case | Slots | MTP | Per-slot tok/s | Peak process VRAM | Peak hotspot |
|---|---:|---|---|---:|---:|
| s1-mtp | 1 | yes | 49.6 | 21,646 MiB | 96°C |
| s2-mtp | 2 | yes | 5.7, 26.4 | 22,126 MiB | 97°C |
| s2-nomtp | 2 | no | 5.7, 23.0 | 19,529 MiB | 95°C |
| s4-nomtp | 4 | no | 1.5, 2.1, 3.6, 12.8 | 20,135 MiB | 98°C |

GTT stayed at 8.1 MiB and evicted at 0 MiB in every case — no VRAM spill.

**Conclusion**: parallel slots are not free on this GPU — a slot that is already generating is
starved by another slot's concurrent prefill (the slot that *finishes its own prefill first*
decodes slowest, not the slot still prefilling), and end-to-end wall time to serve several
requests is higher with more slots than queuing them through 1 slot: 8.6% worse at 2 slots+MTP,
6.0% worse at 2 slots without MTP, 25.6% worse at 4 slots. For multi-agent use (several
terminals/agents sharing one server), keep **1 slot + MTP** and let requests queue rather than
adding slots — concurrent slots also add an interactive latency penalty (an already-generating
agent can drop from ~50 to ~6-13 tok/s while another agent's prompt prefills). See
[`../../docs/measurements/concurrency.md`](../../docs/measurements/concurrency.md) for the full
conclusion, the prefill/decode ordering evidence and caveats (single run, prefill-heavy 32K-token
workload; `aggregate_tok_s` in the raw summaries is exactly the quantity behind the wall-time
comparison above — it should not be read as per-request generation speed; use per-slot
`predicted_per_second` for that, as done above).
