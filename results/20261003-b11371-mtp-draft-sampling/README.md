# 2026-10-03: llama.cpp b11371 and probabilistic MTP drafting (PR #27694)

Question: does llama.cpp b11371 (`99b9548`) or its new `--spec-draft-sampling probabilistic`
(rejection-sampling verification, [PR #27694](https://github.com/ggml-org/llama.cpp/pull/27694))
beat the adopted b11160 engine on the adopted profile? The PR author reports +12-15% throughput
at temperature 0.6-1.0 on other hardware (256-token prompts, empty context).

## Setup

- Engines: `llama-b11160-linux-rocm10-gfx1100-kvmix` (adopted) and
  `llama-b11371-linux-rocm10-gfx1100-kvmix` (same recipe, `docs/ENGINES.md`). `--help` of b11371
  vs. b11160 adds only `--rpc` and `--spec-draft-sampling` (default `greedy`); no default changes.
- Model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp`, adopted flags (`-c 262144`, KV `q8_0`/`q5_1`, MTP n=3,
  `-ub 256`, `--ctx-checkpoints 4`, `-np 1`), 272 W cap.

## Commands

```bash
# empty context, temperature 1, 6 tasks x 3 seeds (variants mtp3 / mtp3-prob)
BENCH_SERVER=<b11160>/llama-server python3 bench/spec_bench.py --run --variants mtp3 --tag b11160
BENCH_SERVER=<b11371>/llama-server python3 bench/spec_bench.py --run --variants mtp3 mtp3-prob --tag b11371
# 240K fill, temperature 0 (see caveat), 3 reps after a prefill warm-up
python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3 --reps 3 --extra "-ub 256"
python3 bench/spec_depth_bench.py --run --depth 240000 --variants n3 n3-prob --reps 3 --extra "-ub 256"
# multi-turn prefix reuse, 4 chat turns, 32K context (turns.py in this folder)
BENCH_MODEL=... python3 turns.py <engine>/llama-server <tag>
```

All runs under `systemd-inhibit`, one GPU arm at a time.

## Results

Empty context, temperature 1 (median tok/s over 18 runs; MTP acceptance = accepted/drafted):

| Arm | Median tg | Acceptance |
|---|---|---|
| b11160 greedy | 72.4 | 75.8% (18,434/24,321) |
| b11371 greedy | 72.2 | 75.7% (18,416/24,321) |
| b11371 probabilistic | 68.6 | 77.5% (18,078/23,328) |

Probabilistic vs. greedy on b11371, per task (median tg): code -1.8%, editing -4.5%, spanish
+4.9%, extraction -1.2%, agent -1.8%, reasoning -6.8%. Higher acceptance does not pay for the
extra per-step sampling cost here.

240K fill, temperature 0 (median of 3 warm reps; output SHA identical across all arms):

| Arm | essay | copy | code |
|---|---|---|---|
| b11160 greedy | 24.55 | 26.92 | 18.71 |
| b11371 greedy | 24.64 | 27.03 | 18.71 |
| b11371 probabilistic | 24.14 | 26.45 | 18.35 |

Peak process VRAM 22,631-22,632 MiB in all three arms, GTT 8 MiB, 0 evicted.

Multi-turn prefix reuse: identical on both engines (`turns.jsonl`). Turn 2 reuses only 33 cached
tokens and re-processes the previous answer. **Cause: the test client.** `turns.py` sent back only
`content`, not `reasoning_content`, while both servers log "chat template supports preserving
reasoning, it is enabled by default"; the rendered history therefore differs from the cached one at
the previous assistant turn. This says nothing about the EOG-draft fix (PR #29638) or the harness;
a re-run that sends `reasoning_content` back (`turns.py <server> <tag> keep`, `turns-keep.jsonl`)
reuses the whole prefix on both engines: turns 2-4 process only 18-20 new tokens and read
854-2,731 tokens from the cache. With reasoning replayed (as omp does for local backends), prefix
reuse across chat turns works on b11160 and b11371 alike.

## Conclusion

- b11371 is speed- and VRAM-neutral against b11160 (same tokens, same acceptance, same tok/s):
  no reason to move the pinned engine.
- Probabilistic drafting loses at empty context at temperature 1 (median -5%).
- **Caveat**: the 240K rows used `temperature: 0` in the request (the depth bench's payload), where
  probabilistic drafting is token-identical to greedy by design; they measure its overhead only
  (-1.5 to -2%), not its possible gain. The temperature-1 re-run at depth is below.

## 240K at temperature 1 (S2c)

`spec_depth_bench.py --depth 240000 --variants n3 n3-prob --reps 3 --temperature 1 --extra "-ub 256"`
on b11371 (commit d529d65 adds `--temperature`; reps use seeds 9, 10, 11 in both arms, so pairs share
a seed). Effective request: temperature 1, top-k 20, min-p 0, server default top-p 0.95; the bench
renders the prompt through `/apply-template` with no `--reasoning-effort` on the server argv (the
template default), as in all earlier depth rows. Rep 1 is the cold-prefill warm-up and is excluded.
Every rep stopped at the 400-token limit.

| Task | greedy tg (acceptance) | probabilistic tg (acceptance) | Delta |
|---|---|---|---|
| code | 16.79 (0.41) | 18.87 (0.50) | +12.4%, faster on all 3 seeds |
| copy | 27.36 (0.91) | 26.61 (0.87) | -2.7% |
| essay | 24.83 (0.78) | 23.69 (0.75) | -4.6% |

Total wall time over the 9 pairs: 167.6 s greedy vs. 164.0 s probabilistic (-2.1%). At temperature
1, greedy drafting's acceptance on code drops from 0.50 (temperature 0) to 0.41; probabilistic
drafting restores it. Three seeds per task are a small sample.

**Decision: not adopted, pending.** The adoption rule (>= 5% at both depths) fails: -5% median at
empty context, about even at 240K. The code-task gain is the only positive signal; only a real
coding-session replay at depth could justify it.

**Raw data**: `empty-*-aggregate.json`, `depth240k-*-summary.jsonl` (`-temp1-` = S2c), `turns.jsonl`, `turns-keep.jsonl`, `turns.py`.
SSE streams and server logs stay local (`_tmp/`, git-ignored).
