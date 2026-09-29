# Memory: VRAM breakdown and measurement method

## Current conclusion

- **The MTP draft's own KV defaults to f16 and should stay there.** Setting it to q8_0
  (`-ctkd q8_0 -ctvd q8_0`) *increases* total VRAM: the draft KV shrinks by 480 MiB but its compute
  buffer grows from 324 to 1,360 MiB, a net +426 MiB. **Kept at the f16 default.**
  MTP also triples the recurrent state (RS: 150 → 449 MiB).
  MTP's total cost at 262K (vs. no MTP, same primary KV): **~1.6 GiB** across draft KV, draft compute
  and RS.
- **Per-process fdinfo (`/proc/<pid>/fdinfo/<render-node-fd>`) is the correct margin metric**, not
  total system VRAM: the desktop's own VRAM use varies ~0.3-1.1 GiB within a session, which makes
  "total VRAM" readings incomparable across runs. fdinfo exposes `drm-memory-vram`,
  `drm-memory-gtt`, `amd-requested-vram` and `amd-evicted-vram` per process and doesn't depend on the
  desktop.
- **`-ub 256` on the current default, updated 2026-09-26** (`262k-q8q51-mtp`, MTP n=3, q8_0/q5_1,
  262K, 240K fill): `-ub 256` shows **no spill** — system GTT 662-678 MiB vs. 642-680 MiB with
  `-ub 512`, per-process GTT 8 MiB, 0 evicted, process VRAM 22,630 MiB vs. 22,980 MiB with
  `-ub 512` — see "`-ub 256`" below. This supersedes the 2026-09-24 reading in `depth.md`
  (Case E), which appeared to spill ~770 MiB more to GTT on the older MTP n=2 depth matrix, a
  different profile stage. `-ub 256` also lowers real process VRAM here (-350 MiB vs. the
  `-ub 512` default) with only a small prefill cost; this differs from the 2026-09-25 128K-fill
  screening (`speculative.md`) where `-ub 512` was optimal — the effect of `-ub` depends on
  profile and depth, re-measure rather than assume.
- No flag exists in b11160 to limit the MTP draft's own context or compute footprint. Smaller `-ub`
  reduces the declared compute buffers but doesn't consistently lower real VRAM use.
- **System VRAM headroom depends on the desktop's own usage, measured directly 2026-09-26**: total
  system VRAM (not just the process) left only 12-190 MiB free across every long-context
  configuration measured that day, with desktop idle usage at ~1.5 GiB (vs. ~0.8 GiB on other
  days) — see "`-ub 256`" below. The process itself was never evicted, but system-wide headroom is
  thin regardless of profile; close other heavy GPU applications before long-context work.

## VRAM breakdown at load (`-lv 4` log, 262K context, MiB)

| Variant | Weights | KV | RS | Compute | MTP KV | MTP compute | Process VRAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| V1 q8/q5_1 + MTP, MTP KV **f16** (default) | 11,160 | 7,424 | 449 | 1,360 | 1,024 | **324** | **22,073** |
| V2 q8/q5_1 + MTP, `-ctkd q8_0 -ctvd q8_0` | 11,160 | 7,424 | 449 | 1,360 | 544 | **1,360** | 22,499 |
| V3 q8/q8 + MTP, MTP KV q8 | 11,160 | 8,704 | 449 | 1,360 | 544 | 1,360 | 22,896 |
| V4 = V3 + `-ub 256` | 11,160 | 8,704 | 449 | 1,192 | 544 | 1,192 | 23,482 |
| V5 = V3 + `-ub 128` | 11,160 | 8,704 | 449 | 1,108 | 544 | 1,108 | 23,314 |
| V6 q8/q8, no MTP | 11,160 | 8,704 | 150 | 1,360 | — | — | 21,368 |

("Process VRAM" = total VRAM after load − total VRAM before load. Has some noise from the desktop.)

## Method: exact per-process memory via fdinfo

amdgpu exposes, per process, in `/proc/<pid>/fdinfo/<fd of the render node>`: `drm-memory-vram`,
`drm-memory-gtt`, `amd-requested-vram`, and **`amd-evicted-vram`** (what the kernel has pushed out of
VRAM). Verified against a live ROCm `llama-server` (works with KFD allocations). This is the correct
metric for margin and for detecting an overflow to system RAM, and it's independent of the desktop's
own usage.

Sampling notes from the instrumentation used for the depth measurements in `depth.md`: fdinfo
sampled every 0.2 s, deduplicated by `drm-client-id` (so one process's multiple DRM handles aren't
double-counted), raw KiB values converted to bytes. A short smoke test (2,048 input / 32 output
tokens, q8/q5_1+MTP2, 262,144 reserved) read: 63.56 tok/s (too short a sample to mean anything for
throughput), peak process VRAM 22,828.84 MiB, GTT 8.07 MiB, 0 evicted. Absence of a metric value
doesn't mean zero, and 0.2 s sampling can miss brief spikes.

## Total VRAM at the platform limit (context-full stress test)

Total VRAM including the desktop, on a 24,560 MiB card. See `depth.md` for the full stress-test
table and its conclusion (VRAM margin is the actual failure mode at 262K + MTP, not a driver bug).

## `-ub 256` on the 262K default, and system VRAM headroom (2026-09-26)

`bench/spec_depth_bench.py`, `262k-q8q51-mtp` (MTP n=3), 240K fill, essay/copy/code, temperature
0, 272 W. Raw data and exact commands:
[`../../results/20260926-ubatch256-262k/`](../../results/20260926-ubatch256-262k/).

| Variant | Peak process VRAM | pp |
|---|---:|---:|
| `-ub 512` (default) | 22,980 MiB | 400 |
| **`-ub 256`** | **22,630 MiB (-350)** | 380 (-5%) |

Generation tok/s was within noise (mean 23.3 vs. 23.4, see `speculative.md`). **Adopted**: the
VRAM saving is worth the small prefill cost.

System VRAM (all processes, `mem_info_vram_used`, 24,560 MiB total), peak:

| Configuration | Peak used | Free |
|---|---:|---:|
| 224K, n=2, `-ub 512` | 24,426 MiB | 134 MiB |
| 262K, n=2, `-ub 512` | 24,548 MiB | 12 MiB |
| 262K, n=3, `-ub 512` | 24,534 MiB | 26 MiB |
| 262K, n=3, `-ub 256` | 24,370 MiB | 190 MiB |

0 evicted throughout. Desktop idle VRAM this session was ~1.5 GiB (other days ~0.8 GiB) — the
**"~1.8 GiB system VRAM margin" figure for the 224K profile in `depth.md` was measured with a
lighter desktop and doesn't generalize**; actual headroom depends on what else is using the GPU at
the time, not just the profile.

## Prompt-cache reuse and context checkpoints (2026-09-29)

Log analysis of 7 `llama-server` logs (`scripts/launch.py --background`, `qwen38-iq3s-mtp` /
`262k-q8q51-mtp`, b11160 `hip-kvmix`, `-np 1 --ctx-checkpoints 4`, 2026-09-26 to 2026-09-28):
about 330 requests from a coding-agent harness (main agent plus subagents). Sessions reached up to
112,601 tokens (none reached 240K).

- **Prefix reuse works.** Slot selection by longest-common-prefix similarity logged `f_sim_best`
  0.95-0.999 on almost every request; a typical request re-processes only tens to a few thousand
  tokens.
- **Only 4 full re-processes of ~32K tokens** (the harness's base system prompt plus tool
  definitions). Three were the first request after a server start (unavoidable). One was a new
  context (compaction or a fresh subagent) whose prompt matched the cached one at
  `f_sim_best = 0.997`, `f_keep = 0.284` (the slot held 112,601 tokens), yet all 32,080 prompt
  tokens were re-processed: 42.2 s lost. In the largest log (228 requests, 334 s total prompt-eval
  time), 85 s were in its two full re-processes.
- **Root cause (read in b11160 `tools/server/server-context.cpp`, `create_checkpoint` around lines
  2309-2340 and checkpoint creation around 3615-3635).** Qwen3.8 is hybrid (48 Gated DeltaNet
  recurrent layers plus 16 full-attention layers). The recurrent state cannot be truncated back to
  an arbitrary position, so reusing a shorter prefix needs a context checkpoint at or before the
  match point. The server creates about one checkpoint per request (last user message / near the
  prompt end, otherwise only if more than `--checkpoint-min-step` (default 8192) past the last
  one). When the list is full it first thins checkpoints within `checkpoint_min_step` of an earlier
  one, then evicts the oldest (FIFO). With `--ctx-checkpoints 4` and checkpoints 8-12K tokens
  apart nothing is thinned, so FIFO evicts the oldest: logged evictions at n_tokens 30,708 /
  39,269 / 47,565 / 59,899 / 68,201 / 76,476. The checkpoint covering the ~32K base prompt (at
  30,707) was evicted about 5 minutes into the session; after that, any new context starting with
  the same base prompt re-processes it fully.
- **Checkpoint size grows with position** (host RAM): 270.3 MiB at 30,708 tokens, 303.9 MiB at
  39,269, 384.9 MiB at 59,899, 514.7 MiB at 92,907.
- **Decision: keep `--ctx-checkpoints 4`.** Keeping the base-prompt checkpoint alive to ~160K
  tokens would need about 16 checkpoints, several GiB more host RAM (per-checkpoint size grows with
  depth) on a 31 GiB host that also holds the default 8 GiB `--cache-ram`. The payoff is ~42 s per
  new context, seen once in a 2 h+ session. Re-open only if new contexts become frequent (for
  example heavy subagent use); then consider a larger `--ctx-checkpoints` after measuring RAM.

## Open questions

- fdinfo instrumentation was not yet wired into every benchmark script at the time of the earlier
  262K-target measurements (`depth.md`'s Case A-E table uses total VRAM, not per-process); later
  measurements (128K/240K repeats, 190K A/B) do use per-process fdinfo throughout.

## History

- **2026-09-24, night**: VRAM breakdown at load measured (V1-V6); MTP draft KV left at f16 after
  finding q8_0 makes total VRAM worse. fdinfo method identified as the correct margin metric but not
  yet used in all scripts.
- **2026-09-24/25**: fdinfo instrumentation adopted across the depth-measurement scripts (see
  `depth.md`'s 128K/240K and 190K results), replacing total-VRAM readings for anything used to judge
  margin.
- **2026-09-26**: `-ub 256` measured on the newly adopted `262k-q8q51-mtp` (MTP n=3) profile —
  -350 MiB process VRAM for a small pp cost, adopted. System VRAM (not just the process) measured
  directly across every long-context configuration that day: only 12-190 MiB free at the platform
  limit, correcting the earlier ~1.8 GiB margin figure that was measured with a lighter desktop.
