# 2026-09-30 — KVMem trial, round 2 and final round: block size, crash repro, candidate

**Measures**: follow-up to [round 1](../20260930-kvmem-trial/README.md). Does a smaller
`--kvmem-block-tokens` (or a larger budget) fix the round-1 retrieval miss at budget 28,672, is the
budget 49,152 crash reproducible, and does the resulting candidate (budget 28,672, block 32) keep
its decode speed and exactness at 190K-240K. Criteria:
[`docs/ENGINES-EXPERIMENTS.md`](../../docs/ENGINES-EXPERIMENTS.md#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted).

## Method delta vs. round 1

Same model file, same KVMem source (`abe72b38256d` plus [`rocm-build-fix.patch`](../20260930-kvmem-trial/rocm-build-fix.patch)),
same harness and prompts, same hardware and power cap (272 W), one sample per cell. Changes:

- `--kvmem-block-tokens 32` (round 1: 128) and, in one arm, budget 36,864.
- [`kvmem_depth.py`](kvmem_depth.py) now kills the server on `Memory access fault` in its log (a
  faulted server hangs in state `I<sl` and ignores SIGTERM);
  [`kvmem_quality.py`](kvmem_quality.py) uses a 1 h request timeout (round 1: 4 h). Both copies here
  are the versions used.
- Flags common to all KVMem runs (full argv in [`commands/`](commands/)):
  `--device ROCm0 -ngl 99 -c 262144 -b 512 -n 16384 --kvmem --kvmem-gen-reserve 16384
  --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --kvmem-mtp-state replay --spec-type draft-mtp
  --spec-draft-n-max 2`. Quality: temperature 0, thinking off. Speed: temperature 1.0, top-p 0.95,
  top-k 20, min-p 0.0, `--reasoning-effort medium --enable-thinking`, 1,500 output tokens.
- Scripts: [`scripts/run-r2.sh`](scripts/run-r2.sh), [`scripts/run-final.sh`](scripts/run-final.sh)
  (run from `<repo>/_tmp/`; adjust `<repo>` and `~` paths to rerun).

Documents (git-ignored, regenerable with `bench/longctx_quality.py` and its seeds):

| Document | Run | sha256 |
|---|---|---|
| `d240000-n00.json`, `d240000-n01.json` | `longctx-20260926-145634` | see [round 1](../20260930-kvmem-trial/README.md#method) |
| `d190000-n00.json` | `longctx-20260925-170146` | `85cfd5d4740c8f9f807af445676ec70f0c4e1f9a4403251b5a71ef8e495034bb` |
| `d220000-n00.json` | `longctx-20260926-095911` | `95638e9cfcd95e95ea8d7a7c663372a255e748f2c1c9c414cc25d1f1fee72924` |

## Results: round 2 retrieval (temperature 0, thinking off)

| Budget | Block | Documents | Exact match | Notes |
|---:|---:|---|---:|---|
| 28,672 | 32 | `d240000-n00`, `d240000-n01` (240K) | **8/8** | Includes the former miss `PLANO-01-03-469` (1,677) |
| 36,864 | 128 | `d240000-n01` (240K) | 3/4 | Same `PLANO-01-03-469` miss (`null`) |

Block size, not budget, fixes the miss: a 28% larger budget at block 128 still misses, block 32 at
the smaller budget does not. Raw rows: [`quality/r2-b28k-bt32.jsonl`](quality/r2-b28k-bt32.jsonl),
[`quality/r2-b36k-bt128.jsonl`](quality/r2-b36k-bt128.jsonl).

## Results: budget 49,152 crash reproduced

Budget 49,152, block 128, 190K target: `Memory access fault by GPU node-1 ... Reason: Page not present
or supervisor privilege` at the end of prefill (prefill at 100% progress, 192,000 tokens, ~565 tok/s). Together
with round 1 that is 2 of 2 attempts, so it is deterministic at this configuration. The faulted
server does not exit on SIGTERM and needs SIGKILL. Log tail:
[`crash-b49k-190k-repro.log`](crash-b49k-190k-repro.log). Not traced (`--kvmem-trace` not run).

## Results: final round, candidate = budget 28,672, block 32

Retrieval:

| Documents | Exact match | Cold prefill | Follow-ups (cached tokens) |
|---|---:|---:|---|
| `d190000-n00` (190K) | 4/4 | 319 s | 4.0-4.4 s (189.6K) |
| `d220000-n00` (220K) | 4/4 | 351 s | 4.3-4.6 s (219.6K) |

Raw rows: [`quality/final-b28k-bt32.jsonl`](quality/final-b28k-bt32.jsonl). A llama.cpp build ran on
the CPU concurrently during this step: it does not affect exactness, but the prefill times are not
speed numbers.

Decode at 244,353 prompt tokens (1,500 output tokens, finish `length`, thinking on):

| Arm | pp tok/s | tg tok/s | Peak VRAM MiB | Peak RSS GiB | Min MemAvailable GiB | Hotspot °C |
|---|---:|---:|---:|---:|---:|---:|
| Candidate (budget 28,672, block 32) | 630.1 | 45.5 | 15,125 | 13.67 | 10.15 | 99 |
| Round 1, budget 28,672, block 128 | 626 | 48.6 | 15,127 | 9.39 | 6.51 | 98 |
| Baseline `262k-q8q51-mtp` (round 1) | 380 | 20.8 | 22,638 | 6.40 | 12.39 | 100 |

The candidate decodes 2.2x the baseline at 244K. Block 32 costs ~6% tg versus block 128 (single
samples) and more host RAM (RSS 13.67 vs. 9.39 GiB). Raw: [`depth-summary.jsonl`](depth-summary.jsonl),
[`commands/`](commands/).

Candidate exact retrieval by depth: 128K 8/8 (round 1, block 128, not re-run at block 32), 190K
4/4, 220K 4/4, 240K 8/8.

## Conclusion

The candidate meets 3 of the 4 go/no-go criteria: decode 2.2x at 240K (criterion ~1.3x), 8/8 exact
at 240K, at least ~4 GiB host RAM free (minimum 10.15 GiB). The real agent run (T6) is outstanding,
so the candidate is still not adopted; next step is T6. Budget 49,152 is unusable (deterministic GPU
fault at 190K).

## llama.cpp b11301 build (A/B not run)

b11301 (commit `2149c00`) was built from source with the kvmix FA-quants recipe (cmake line in
[`scripts/run-final.sh`](scripts/run-final.sh), `BUILD_EXIT=0`, `--version` `0.5.0-dev (build 1,
commit 2149c00)`, sha256 in [`sha256-b11301.txt`](sha256-b11301.txt)). The 128K A/B against b11160
was started and cancelled by the session time box: no numbers. `--help` differs from b11160 only by
a new `--rpc` option, so there is no relevant default change for the `models.toml` flags.

## Caveats

- Single sample per cell; the speed comparison against the baseline also differs in KV types, MTP n
  and `-ub` (see round 1).
- The quality step for the candidate shared the host with a concurrent CPU build.
- 128K was not re-run at block 32; candidate speed at 128K/190K was not measured.
- Not done: MTP n=3 on KVMem; traced crash run; quality on the remaining documents; the T6 agent
  run; the 16,384-token per-turn output cap remains a risk. The ROCm build fix and the budget
  49,152 crash are not reported upstream.
- The mid-band miss is one needle in one document; "block size fixes it" rests on that case.

**Raw data**: `depth-summary.jsonl`, `commands/`, `quality/`, `crash-b49k-190k-repro.log`,
`sha256-b11301.txt`. Full responses and server logs stay local (`_tmp/`, git-ignored). Personal
paths are replaced with placeholders, as in [`../INDEX.md`](../INDEX.md).
