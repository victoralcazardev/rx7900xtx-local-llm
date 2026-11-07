# `--ctx-checkpoints` 4 vs. 10 on a replayed compacting agent session (2026-11-06)

**Question:** after a harness compacts at ~35% of the window, does the server re-process the shared
system prompt because `--ctx-checkpoints 4` evicted its checkpoint, and does 10 fix it within the
host RAM budget?

**Answer:** yes and yes. With 4, every post-compaction request re-processed the whole 48,030-token
prompt (70-71 s); with 10, it re-processed only the 20,025 tokens after the 28K system prompt
(32.7 s). Peak `RssAnon` 13,044 MiB (4) and 11,530 MiB (10), both under the 16 GiB budget.

## Setup

- RX 7900 XTX, 31 GiB host RAM, Linux. Engine `hip-kvmix` = llama.cpp v0.9.0 `cd959ba` +
  `pr30792-q5_1.patch` ([`docs/ENGINES.md`](../../docs/ENGINES.md)).
- Model `huihui-iq3s-mtp`, profile `262k-q8q51-mtp` from `models.toml` (`-c 262144 -ctk q8_0
  -ctv q5_1`, MTP draft, `-np 1`, `--cache-ram 12288`). Arm 10 changed only `--ctx-checkpoints`
  (a temporary copy of `models.toml` passed with `--manifest`).
- Traffic: [`bench/compaction_replay.py`](../../bench/compaction_replay.py), identical in both arms:
  a 28K-token system prompt, +4K-token user turns with 32-token replies (thinking off), and a
  compaction to a 16K-token summary once the prompt passes 35% of 262,144; 4 epochs, 53 requests.
  A synthetic stand-in for the real sessions of 2026-11-05/06
  ([`agent-traffic.md`](../../docs/measurements/agent-traffic.md#sessions-of-2026-11-0506-host-cache-thrash-and-the-lost-shared-prefix-four-logs)),
  which show the same pattern (18 requests, 984,474 tokens, 1,575 s re-processed).

```
python3 scripts/launch.py huihui-iq3s-mtp --background            # arm 4
python3 bench/compaction_replay.py --epochs 4 > replay-ckpt4.csv
python3 scripts/cache_misses.py _tmp/logs/<server log> > cache-misses-ckpt4.txt
# arm 10: same, with a models.toml copy whose [defaults] flags say "--ctx-checkpoints", "10"
python3 scripts/launch.py huihui-iq3s-mtp --manifest <copy> --background
```

## Results

| Arm | Post-compaction prefill (each of 3) | Shared prefix lost | Prefill, all 53 requests | Turn prefill (49 warm turns) | Peak `rss_anon_mib` | Min VRAM free |
|---|---|---|---|---|---|---|
| `--ctx-checkpoints 4` | 48,030 tokens, 69.7-70.6 s | 3 | 663.6 s | 411.2 s | 13,044 MiB | 15 MiB |
| `--ctx-checkpoints 10` | 20,025 tokens, 32.7 s | 0 | 562.6 s | 421.7 s | 11,530 MiB | 566 MiB |

- Arm 4 logged `erasing old context checkpoint (pos_min = 28004` in every epoch before its
  compaction; arm 10 erased no checkpoint (the epochs end at ~92K, ~8 checkpoints).
- Warm turns differ by 2.6%, inside the ~6% cross-session spread; one run per arm.
- RSS and VRAM free include noise that is not the flag: the host prompt cache (`--cache-ram`) saved a
  4,631 MiB entry in arm 10, and VRAM free counts the desktop apps open at the time (both arms
  share the card with ~1.9 GiB of desktop). The real session 1106-144605 also reached 19 MiB free.
- Not covered: sessions that grow past ~110K before compacting (10 checkpoints ~8K apart reach
  about that far), and output quality: a restore
  replaces re-computation of the same tokens, and this run did not compare outputs.

## Deep sessions (compaction at ~184K)

Same replay with `--ctx 524288`, so the harness compacts at ~184K instead of ~92K. The owner's
harnesses (omp, Gentle Shell) compact at ~35% of 262K; only an occasional client grows this far.

| Arm | Post-compaction prefill | Checkpoint erasures | Peak `rss_anon_mib` | Min VRAM free |
|---|---|---|---|---|
| `--ctx-checkpoints 10` (1 compaction) | 48,030 tokens, 68.7 s (prefix lost) | 17 | 10,476 MiB | 575 MiB |
| `--ctx-checkpoints 32` (2 compactions) | 20,025 tokens, 32.8 s each | 0 | 16,678 MiB | 98 MiB |

32 (the upstream default) covers the deep case but passes the 16 GiB RssAnon budget, with zram swap
at 11.6 GiB used and MemAvailable 5.5 GiB after the run; rejected. A `--checkpoint-min-step 16384`
arm was started and stopped unfinished when the deep case turned out to be rare.

Raw data: `replay-ckpt*.csv` (per request: prompt tokens, prefill tokens and ms), `gpu-ckpt*.csv`
(`gpu_watch.py` every 5 s, with `rss_anon_mib`), `cache-misses-ckpt*.txt`.
