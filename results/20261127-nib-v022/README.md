# Nib `v0.2.2` vs. `2e16cf0` on the RX 7900 XTX (2026-11-27)

**What**: production Nib (`2e16cf0` + this repo's `--reasoning-budget` patch) against upstream tag `v0.2.2` (`859bf23`) carrying the same patch ported onto it, plus the
unpatched `v0.2.2` build for a start-only A/B. Three speed arms at 7.8K-258K (A old, card sampling + `top_k 256`; B new, same; C new, card as written, no `top_k`), a greedy
parity gate and a start-up reliability loop. Engine, model and server flags are identical between builds.

**Status: not adoptable.** `v0.2.2` dies at start-up as `bdc9307` did: 13 of 25 start attempts ended in SIGSEGV inside the ROCm runtime, 9 at the previous trial's call
site (`hipGraphInstantiate` while capturing DSpark draft graphs), and 3 more hung (exit 137). The unpatched `v0.2.2` crashed the same way, so the fault is upstream, not the
local patch. Production stays `2e16cf0` + the thinking-cap patch; retest when upstream fixes the start-up crash, on an idle GPU.

**Caveat — host load**: the user's video pipeline ran throughout (`parakeet-cli` on a Vulkan `whisper.cpp` build, i.e. the same GPU; Remotion renders; `ffmpeg` jobs;
`pytest`), load average ~40-44, 1 GiB RAM free, and `rocm-smi` showed 31% GPU use at ~18:05 with no Nib process alive. The exit-137 hangs (one of them production, in the
A/B) and the speed arms may be affected by that load.

## Startup crashes (the blocker)

Every SIGSEGV is a general protection fault in `libamdhip64.so.7.16.0-4f6d503`: the kernel logs 14 `traps: nib` lines between 17:13 and 17:56, all at
the same instruction offset there. Frames 0-9 are anonymous frames inside it; representative stacks in
[`raw/coredump-backtraces.txt`](raw/coredump-backtraces.txt):

```text
# patched v0.2.2, 9 cores, 17:13:15-17:42:55 (loop, greedy, GSM8K starts)
#10 hipGraphInstantiate ()
#11 inkling::DSparkDrafter::capture_draft_graphs()
#12 inkling::DSparkDrafter::init(...)
#13 (anonymous namespace)::mtp_session_init(...)
#14 main ()

# patched v0.2.2, 4 cores, 17:51, the cap step (11 MiB cores, not 33 MiB)
#5 hipStreamCreate ()
#6 inkling::InklingEngine::init(...)
#7 main ()

# plain v0.2.2, 17:56:53, same stack as the nine above
#10 hipGraphInstantiate ()
```

| Step | Attempts | Up | SIGSEGV | exit 137 |
|---|---:|---:|---:|---:|
| start loop, 17:13-17:21 | 10 | 5 | 4 | 1 |
| speed arms A/B/C, 17:26-17:39 | 3 | 3 | 0 | 0 |
| greedy parity, 17:40-17:41 | 4 | 1 | 3 | 0 |
| GSM8K + tool call, 17:42-17:51 | 4 | 0 | 2 | 2 |
| cap 256, 17:51 | 4 | 0 | 4 | 0 |
| **total** | **25** | **9** | **13** | **3** |

A start counts as up once `/v1/models` answers; one that neither answers nor exits is the exit-137 row. Counts and retry log:
[`raw/startup-crashes.txt`](raw/startup-crashes.txt), [`raw/start-loop.txt`](raw/start-loop.txt); server logs in the git-ignored `_tmp/nib-v022/`.

**Start-only A/B, upstream or the patch?** `raw/start-ab.sh` interleaves production starts with unpatched `v0.2.2` starts on the production flags; seven
attempts are recorded before the run was stopped by hand (the eighth was killed mid-wait, [`raw/start-ab.txt`](raw/start-ab.txt)). Production: 4
attempts, 2 up, 0 SIGSEGV, 2 hangs. Plain `v0.2.2`: 1 up, 1 SIGSEGV (17:56:53, the stack above), 1 hang, 1 killed by hand — so the unpatched build dies
in the same `hipGraphInstantiate` call and the crash is upstream. The two production hangs are what makes that A/B inconclusive: under this load, exit
137 says nothing about either build.

## Speed by depth

Decode tok/s, median of 2 repeats, median prefill in parentheses (rounded); prompts are unique per request (a nonce line first), uncached, 256-token cap, and every reply reached 256 tokens.

| Prompt tokens (A/B/C) | A old, card + `top_k 256` | B new, card + `top_k 256` | C new, card, no `top_k` |
|---:|---:|---:|---:|
| 7,824 / 7,823 / 7,823 | 121.2 (pp 3,582) | 130.3 (pp 3,468) | 120.9 (pp 3,467) |
| 33,142 / 33,142 / 33,142 | 120.8 (pp 3,433) | 112.5 (pp 3,396) | 110.4 (pp 3,387) |
| 134,187 / 134,206 / 134,206 | 108.0 (pp 3,030) | 117.8 (pp 3,043) | 110.8 (pp 3,013) |
| 258,129 / 258,260 / 258,260 | 106.9 (pp 2,961) | 108.5 (pp 2,959) | 103.0 (pp 2,933) |

Per-repeat tg (`tg_all`), same order: A 123.6 / 118.7, 111.4 / 130.2, 99.8 / 116.2, 110.4 / 103.4; B 123.7 / 136.8, 113.2 / 111.8, 118.4 / 117.3,
110.0 / 107.0; C 122.5 / 119.3, 110.9 / 109.9, 110.8 / 110.8, 105.6 / 100.3.

Sampling: A and B `{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}` (the Unbound v2.1 card plus production's `top_k`, the deviation
`2e16cf0` needed); C `{"temperature":0.6,"top_p":0.95,"min_p":0.0}` (the card as written; server default `top_k 0`, upstream's new default). Every
request also sends `reasoning_effort: "none"` at the top level, so all arms run at the minimum thinking effort.

**C does not collapse**: 103-121 tok/s with `top_k 0`, against ~31 tok/s on `2e16cf0` in the 2026-11-24 trial (short prompt, no `top_k`) — not like for like, that figure is a
historical short-prompt measurement at other sampling. `v0.2.2`'s `top_p` pre-filter (its release note names "optimize top_p sampling") removes the reason for production's `top_k 256` deviation from the card, once the build starts reliably.

**Read the columns as "no difference".** Two repeats of one arm differ by up to 17% (A at 33K, 111.4 vs. 130.2), and the 258K row is 19% under the same build's 2026-11-25
reading (106.9 vs. 131.9, there at temperature 1.0); under this load no arm-to-arm difference here clears that band. Raw: [`raw/speed.jsonl`](raw/speed.jsonl) (12 rows), one git-ignored server log per start.

## Greedy parity gate

`raw/greedy-run.sh new-v022` → `raw/greedy_parity.py` runs the previous trial's three prompts (`temperature 0` only, 256 tokens, same server flags);
`raw/greedy_compare.py` diffs them against [`raw/greedy-old-2e16cf0.jsonl`](../20261125-nib-bdc9307/raw/greedy-old-2e16cf0.jsonl):

| Prompt | Old → new | First difference |
|---|---|---|
| prose | identical, 1,031 chars / 256 tokens | none |
| code | identical, 884 chars / 256 tokens | none |
| 33K | different | char 4 (572 vs. 909 chars) |

Neither build returns token ids, so this is a decoded-text comparison; the two short prompts are constants in an unchanged script, so their parity is meaningful. The 33K arm is a
different prompt, not a parity failure: the harness builds it from the live `docs/` corpus truncated to 95,027 characters (`--chars-per-token 2.9`), which covers
`docs/BENCHMARK-FORMAT.md`, `docs/DECISIONS.md` and part of `docs/ENGINES-EXPERIMENTS.md` — and `DECISIONS.md` changed after the 2026-11-25 run. The prompt token counts differ
(33,165 old, 33,116 new). Upstream's `v0.2.0` pre-tokenization fix (`fba1dd5`) would also change that count; this run cannot separate the two, so the 33K arm proves nothing
either way. [`raw/greedy-parity.txt`](raw/greedy-parity.txt), [`raw/greedy-new-v022.jsonl`](raw/greedy-new-v022.jsonl).

## Setup

| | |
|---|---|
| Dates / GPU | 2026-11-27 17:09-18:06 local (WET), RX 7900 XTX 24 GB (gfx1100) |
| OS / runtime | CachyOS, kernel 7.3.6-1-cachyos, ROCm in `/opt/rocm` (`hipconfig` 7.16.0-4f6d503, the library in every crash) |
| Build A (current) | `~/IA/Motores/src/nib-thinkcap`: `Chromadera/nib` `2e16cf0` + `engine-patches/nib-reasoning-budget-2e16cf0.patch`, `build/nib` 2026-11-25 20:40, sha256 `79aec4a96629100a…` |
| Build B/C (new), D (plain) | `~/IA/Motores/src/nib-v022`: tag `v0.2.2` (`859bf23`) + the same patch ported (3 trivial conflicts in `src/main.cpp`, `src/server.cpp`, `src/server.hpp`: kept upstream's `top_k 0` defaults and help text, added `reasoning_budget`), `nib 0.2.2 (built: gfx1100, runtime: gfx1100 [AMD Radeon RX 7900 XTX], git 859bf23)`, `cmake -DCMAKE_BUILD_TYPE=Release -DROCM_PATH=/opt/rocm -DGPU_TARGET=gfx1100`, `build/nib` 17:09, sha256 `3c899f2106b6bd9f…`. D: `~/IA/Motores/src/nib-v022-plain`, `v0.2.2` unpatched (no `--reasoning-budget` in its help), `build/nib` 17:53, sha256 `8aa7842257e8c799…` |
| Model | `Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf` 17,627,963,360 B + `mtp.safetensors` 635,801,416 B |
| Server flags (all) | `serve -m <gguf> --mtp mtp.safetensors --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 --default-min-p 0.0 --host 127.0.0.1 --port 4444` |
| Harness | `raw/depth_http.py … --depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9` via `raw/speed-run.sh`, one start per arm; `raw/run.sh` for the whole sequence |

## Not measured

- GSM8K 192 and the tool call: the quality start never came up (4 attempts: 2 SIGSEGV, 2 hangs).
- The 256-token thinking cap: 4 starts, 4 SIGSEGV, no request sent.
- Anything at the old trial's arm-C sampling (`temp 1.0, top_p 1.0, top_k 0`): these arms follow the card, to test the `top_k` deviation, not the sampler.
- What fixes the crash: no code change was attempted; the Nib checkouts are out of scope for this run.

## Raw files

`run.sh` (whole sequence), `start-ab.sh` (start-only A/B), `start-loop.txt` and `startup-crashes.txt` (start counts and retry log), `start-ab.txt`, `speed.jsonl` (12 rows),
`greedy-new-v022.jsonl`, `greedy-parity.txt`, `coredump-backtraces.txt` (added after the run: three stacks, host and build paths redacted), `depth_http.py`, `speed-run.sh`,
`serve-lib.sh`, `greedy_parity.py`, `greedy_compare.py`, `greedy-run.sh`, `quality-run.sh`, `gsm8k_http.py`, `tool_check.py`, `capreq.py`. The scripts that matter are
byte-identical to the 2026-11-25 trial's copies apart from their result and log paths.
