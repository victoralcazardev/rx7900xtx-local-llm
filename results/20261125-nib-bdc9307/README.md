# Nib `bdc9307` vs. `2e16cf0` on the RX 7900 XTX (2026-11-25)

**What**: the same speed, quality and greedy-parity gate on the production Nib checkout (`2e16cf0`) and on
upstream `bdc9307`, which contains `aa394af` "Fix uninitialized VRAM / sparse OOB faults and add exact GPU
unbounded sampler (#1)". Arm C tests that sampler's claim (unbounded sampling, `top_k 0` / `top_p 1.0`, at the
claimed ~127-137 tok/s solo), arm D measures the sampling the agent harnesses actually send. Engine and model flags
are identical between builds; only the binary and the per-request sampling change.

**Status: not adoptable.** `bdc9307` segfaults on roughly one start in three, inside `hipGraphInstantiate` while
capturing the DSpark drafter graphs. The sampler and parity claims hold, but a build that dies on a third of its
starts cannot replace `2e16cf0`, which produced no core in this run.

## Startup crashes (the blocker)

The new build dies with SIGSEGV during startup, at an address in `libamdhip64.so.7.16.0-4f6d503` after a general
protection fault. The main-thread stack of every `serve` core ends the same way
([`raw/coredump-854424.txt`](raw/coredump-854424.txt)):

```
#10 hipGraphInstantiate (libamdhip64.so.7)
#11 inkling::DSparkDrafter::capture_draft_graphs()
#12 inkling::DSparkDrafter::init(...)
#13 mtp_session_init(...)
#14 main
```

In the logs the crash always lands between `[InklingEngine] Ready! …` and `[dspark] captured N static draft HIP
graphs` ([`raw/crash-new-build.txt`](raw/crash-new-build.txt)): the exact region `aa394af` rewrote (the drafter now
zeroes its allocations with stream-ordered `hipMemsetAsync`). One earlier core (11:36) instead crashed inside
`inkling::InklingEngine::init`, so the fault is not confined to the graph-capture call. The kernel log for the same
window also shows a `comp_1.3.0 ring reset` at 11:42, a GPU ring timeout the old build never produced here.

| Build | `serve` starts | SIGSEGV | `selftest` runs | SIGSEGV |
|---|---:|---:|---:|---:|
| A `2e16cf0` (current) | 5 | **0** | not run | — |
| B/C/D `bdc9307` (new) | 9 | **3** | 4 | **2** |

`coredumpctl list` agrees with the logs: five SIGSEGV of `nib-main/build/nib` at 11:36:04, 11:38:09, 11:58:39,
12:02:52 and 12:03:11 — my two crashed `selftest` runs, the first arm-B start and two of the three startup attempts
in a dedicated reliability loop. No core of `nib/build/nib` was written during this run; the three old-build cores
in the same list (2026-11-24 23:05 SIGABRT, 23:13 and 2026-11-25 00:17 SIGSEGV) date from the previous trial.
Counts and the retry log: [`raw/startup-crashes.txt`](raw/startup-crashes.txt).

Arm scripts therefore retry a dead start up to four times (`raw/serve-lib.sh`) rather than skipping an arm; every
start after that helper was added came up on attempt 1, so the numbers below are single-start numbers.

## What does hold

- **The unbounded sampler is fixed**: with `top_k 0` the new build decodes 156.6 tok/s at 8K and 113-117 tok/s at
  33K-258K, against ~31 tok/s for the same sampling on `2e16cf0` (previous trial, short prompt). The sampling the
  model card asks for no longer costs 4x throughput.
- **Greedy output is bit-identical**: three 256-token greedy prompts (prose, code, 33K) are identical to the
  character, and the 192 GSM8K generations have identical predicted values *and* identical token counts. GSM8K
  stays at 187/192 with the same five failures. The tool-call path still works.
- **No decode or prefill gain on the bounded path**: arm B (`top_k 256`) is 102-114% of arm A per depth and prefill
  is unchanged (2,964-3,614 vs. 2,989-3,576 tok/s). That spread is noise, not a win — see the method note.

## Setup

| | |
|---|---|
| Dates | 2026-11-25 11:35-12:45 (local) |
| GPU | RX 7900 XTX 24 GB (gfx1100), 272 W cap |
| OS / runtime | CachyOS, kernel 7.3.5-2-cachyos, ROCm in `/opt/rocm` (`hipconfig` 7.16.0-4f6d503, the library in the crash) |
| Build A (current) | `Chromadera/nib` `2e16cf0`, `build/nib` 2026-11-24 23:05, sha256 `f96889f4b0f6d2f6…` |
| Build B/C/D (new) | `Chromadera/nib` `bdc9307` (contains `aa394af`, `2d23530`, `57adf55`, `419d833`), `build/nib` 2026-11-25 11:34, `nib 0.1.0 (gfx1100, git bdc9307)`, 0 warnings, sha256 `d4f84e7ce1e41ff5…` |
| Model | `Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf` 17,627,963,360 B + `mtp.safetensors` (DSpark drafter) |
| Server flags (both builds) | `serve -m <gguf> --mtp mtp.safetensors --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 --default-min-p 0.0 --host 127.0.0.1 --port 4444` |
| Harness | `raw/depth_http.py` (previous trial's script plus the `mtp_avg_accepted` field), `--depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9`, one server start per arm; `raw/speed-run.sh <label> <nib-dir> <sampling>` |
| Production | stopped for the run with `python3 scripts/launch.py --stop`, restarted with `--background` afterwards; `/health` answered, 21.49 GiB, vision on, `temp=0.60` ([`raw/production-health.json`](raw/production-health.json)) |

Neither Nib tree was built, patched or checked out during this run.

## Selftest (new build)

`./build/nib selftest -m <gguf> --kv-type q8_0 --sparse-pages 224 --mtp mtp.safetensors` — exit 0,
[`raw/selftest.txt`](raw/selftest.txt). Sampler gates pass (20,000-draw chi-squared 67.4 and 74.4 under the 133.4
gate at dof 65, `min_p` kept set exact, 4x heterogeneous batch with 0 mismatches), prefill/decode cos_sim
0.9999949, verify `m=2/4/8` bit-identical to sequential decode, rollback exact for every commit, 64-token greedy
parity non-MTP vs. MTP `[ok]`, 85.96 tok/s at 1.09 tok/round. Of four invocations, two died as described above.

## Speed by depth

Decode tok/s, median of 2, with the median prefill in parentheses. Prompts are unique per request (a nonce line
first), uncached, 256-token cap.

| Prompt tokens | A old, `top_k 256` | B new, `top_k 256` | C new, unbounded | D new, shipped |
|---:|---:|---:|---:|---:|
| 7,824 | 121.4 (pp 3,576) | 124.1 (pp 3,614) | **156.6** (pp 3,591) | 133.6 (pp 3,595) |
| 33,191 | 117.3 (pp 3,414) | 132.3 (pp 3,443) | 115.4 (pp 3,418) | 123.2 (pp 3,411) |
| 134,222 | 108.7 (pp 3,050) | 124.4 (pp 3,069) | 113.0 (pp 3,057) | 108.6 (pp 3,037) |
| 258,126 | 131.9 (pp 2,989) | 115.1 (pp 2,976) | 116.6 (pp 2,971) | 115.7 (pp 2,964) |

Sampling per arm: A `{"temperature":1.0,"top_k":256}`; B the same; C `{"temperature":1.0,"top_p":1.0,"top_k":0,"min_p":0.0}`
(the model card); D `{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}` (what production sends).

**Method note — these numbers are noisy, read them as "no regression".** Each cell is a median of two sampled
runs, and the two runs do not decode the same text: accepted draft tokens per drafter round range from 0.68 to
2.24 across cells and repeats (A `0.99/0.72`, `1.03/0.85`, `0.83/0.77`, `1.26/1.39`; B `0.83/0.94`, `1.51/1.17`,
`0.98/1.20`, `0.89/0.96`; C `1.24/2.24`, `0.85/1.07`, `0.80/0.79`, `0.72/1.00`; D `0.80/1.49`, `1.06/1.58`,
`1.01/0.68`, `0.96/0.93`), and four replies stopped early (`gen` of 103, 31, 85, 222 in `raw/speed.jsonl`). The
spread between two repeats of one arm reaches ±10-15% and is as large as any difference between arms (C: 141.9 vs.
171.4 at 7,824 tokens). Only the arm-C gap at 8K is far outside that band.

Raw: [`raw/speed.jsonl`](raw/speed.jsonl); one server log per start, `raw/serve-<arm>.log`.

## Greedy parity gate

`raw/greedy-run.sh <label> <nib-dir>` → `raw/greedy_parity.py` posts three prompts to `/v1/completions` with
`temperature 0` only, 256 tokens, same server flags: a prose request, a code request, and the 33,165-token depth
prompt.

| Prompt | Old → new | First difference |
|---|---|---|
| prose | identical, 1,031 chars / 256 tokens | none |
| code | identical, 884 chars / 256 tokens | none |
| 33,165 tokens | identical, 572 chars / 256 tokens | none |

[`raw/greedy-parity.txt`](raw/greedy-parity.txt), inputs [`raw/greedy-old-2e16cf0.jsonl`](raw/greedy-old-2e16cf0.jsonl)
and [`raw/greedy-new-bdc9307.jsonl`](raw/greedy-new-bdc9307.jsonl). Neither build returns token ids or logprobs
from the endpoint, so parity is asserted on the generated text, which for one tokenizer implies the same token
sequence.

## GSM8K and tool calls (new build)

GSM8K ran exactly as in the previous trial: `raw/gsm8k_http.py 4444 <gsm8k-test.jsonl> --count 192 --raw
--max-tokens 4096`, i.e. maya's rendered prompt to `/v1/completions` (the trial used no sampling beyond
`temperature 0`, so arm C's sampling does not apply). Result **187/192, 0 truncated**
([`raw/gsm-raw-new-bdc9307.jsonl`](raw/gsm-raw-new-bdc9307.jsonl)), the same score as `2e16cf0` on the same graft:
the failing ids are identical (40, 93, 100, 119, 182), and all 192 predicted answers *and* generated token counts
match the previous trial's file one for one.

Tool calls (`raw/tool_check.py`, 129-token prompt, no system prompt): turn 1 `finish=tool_calls` with one
`read_file` call, arguments `{"path":"src/app.py"}`; turn 2 `finish=stop`, 191 of 191 prompt tokens reused, correct
answer, **PASS** ([`raw/tool-new-bdc9307.txt`](raw/tool-new-bdc9307.txt)).

## Not measured

- `2e16cf0` with unbounded sampling at these depths: the ~31 tok/s figure is the previous trial's 600-token
  short-prompt measurement, and the arms were fixed to A/B/C/D, so C is compared against that historical number
  rather than against an old-build run of the same harness. That is the one gap in the sampler claim.
- Multi-slot concurrency, vision, and the >262,144 positions the `pass1_end` clamp addresses.
- `--sparse-pages 0`: every arm used 224, the production value.
- What fixes the crash: no code change was attempted (the Nib checkouts are out of scope for this run).

## Raw files

`coredump-854424.txt` (coredumpctl list plus the arm-B backtrace), `startup-crashes.txt` (start counts and the
empty retry log), `crash-new-build.txt` (a crashed start, `Ready!` as its last line), `selftest.txt`,
`speed.jsonl` (16 rows), `serve-<arm>.log` (one per server start: A, B, C, D, both greedy runs, quality),
`greedy-*.jsonl`, `greedy-parity.txt`, `gsm-raw-new-bdc9307.jsonl`, `tool-new-bdc9307.txt`,
`production-health.json`, `depth_http.py`, `gsm8k_http.py`, `tool_check.py`, `greedy_parity.py`,
`greedy_compare.py`, `serve-lib.sh`, `speed-run.sh`, `greedy-run.sh`, `quality-run.sh`.
