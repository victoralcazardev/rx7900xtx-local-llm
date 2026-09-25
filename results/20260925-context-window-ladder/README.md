# 2026-09-25 — context-window ladder: 224K and 240K, `-c` q8/q8 + MTP n=2 (272 W cap)

**Measures**: how far the 200K `qwen38-iq3s-mtp` profile can grow in context while still fitting
in 24 GiB and generating above ~18 tok/s at depth, stepping the ladder 224K → 240K (fill =
window − 8K) under the 272 W power cap. Stops on the first failure to fit; 262K (`q8_0/q5_1`) was
not reached — the chain was stopped by the operator after 240K. See
[`../../docs/measurements/depth.md`](../../docs/measurements/depth.md).

**Conditions**: engine `hip-kvmix` (own ROCm 10 build), Qwen3.8-27B GSQ-RCO IQ3_S-mtp, KV
`q8_0/q8_0`, MTP `--spec-draft-n-max 2`, `-np 1`, no vision, power cap 272 W (this card's driver
minimum — see `../../docs/measurements/thermals-power.md`). Three task types (essay, literal
copy, code), temperature 1 (vendor sampling), 400 forced output tokens, 2 repetitions per task
(rep 1 cold prefill, rep 2 warm cache).

**Command**: `bench/spec_depth_bench.py --ctx 229376 --depth 221167 --kv q8_0 --variants n2` (and
the same with `--ctx 245760 --depth 237551` for the 240K case).

**Files** (personal machine paths replaced with placeholders; per-request SSE streams are not
published):

- `summary-224k.jsonl` / `command-224k.json` — `-c 229376`, fill 221,167.
- `summary-240k.jsonl` / `command-240k.json` — `-c 245760`, fill 237,551.

**Results** (tg = mean of the two repetitions; accept = sum accepted ÷ sum proposed across both
repetitions and all three tasks; pp = cold prefill on the first, cache-empty request; system VRAM
= total including desktop and any other GPU client):

| Case | Fill | pp | tg essay | tg copy | tg code | Accept | Process VRAM peak | System VRAM | Hotspot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 224K | 221,167 | 422 | 22.3 | 25.1 | 18.7 | 79/94/57% | 22,700 MiB | 23.5 / 24.5 GiB (~1.8 GiB margin) | 98°C |
| 240K | 237,551 | 410 | 22.5 | 24.4 | 18.7 | 84/95/62% | 23,407 MiB | 24.2 / 24.6 GiB (~0.3 GiB margin) | 101°C |

GTT stayed at 8 MiB and evicted at 0 MiB in both cases (no spill). The 224K run had another GPU
client (a video player, ~0.8 GiB) open throughout; the 240K run had it closed partway through.

**Conclusion**: both configurations fit and generate above 18 tok/s on every task. **224K is
adopted as the recommended daily long-context default** (`224k-q8q8-mtp`, `scripts/launch.py`'s
default with no alias) — ~1.8 GiB of system VRAM margin even with another light GPU client
running. **240K is the measured maximum on this card** (`240k-q8q8-mtp`) — only ~0.3 GiB of margin
left, so close other GPU applications before using it. 262K (`q8_0/q5_1`, no MTP headroom left for
q8/q8) was not attempted in this ladder — see `../../docs/measurements/depth.md`'s existing
`262k-q8q8`/`262k-q8q51-mtp` profiles for that end of the range.
