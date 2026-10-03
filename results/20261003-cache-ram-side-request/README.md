# 2026-10-03: host prompt cache vs. a side request on the single slot (T26)

Question: with `-np 1`, an unrelated request (for example a harness compaction summary) replaces
the slot's KV. Does llama-server's host prompt cache (`--cache-ram`) bring the deep main
conversation back, and at what cap?

## Setup and command

Adopted profile flags (`-c 262144`, KV `q8_0`/`q5_1`, MTP n=3, `-ub 256`, `--ctx-checkpoints 4`,
`-np 1`), 272 W. `sidecache.py` (this folder) starts the server with a given `--cache-ram`, then
sends raw-token `/completion` requests (temperature 0, 32 output tokens):

1. `main-cold`: 180,000 wikitext tokens + question 1.
2. `main-warm`: the same 180,000 tokens + question 2.
3. `side`: 20,000 different tokens + "Summarize this conversation."
4. `main-after-side`: the 180,000 tokens + question 3.

```bash
BENCH_MODEL=... BENCH_WIKI=... python3 sidecache.py <engine>/llama-server <tag> <cache_ram_mib>
```

Arms: `--cache-ram 8192` (default) on b11160, `--cache-ram 12288` on b11371. A `0` arm was
cancelled: the 8192 arm already showed the failure.

## Results

| Step | 8192 MiB: cached / new tokens, prompt time | 12288 MiB: cached / new tokens, prompt time |
|---|---|---|
| main-cold | 0 / 180,009, 408.9 s | 0 / 180,009, 405.3 s |
| main-warm | 179,749 / 259, 2.6 s | 179,749 / 259, 1.4 s |
| side | 0 / 20,007, 26.4 s | 0 / 20,007, 25.8 s |
| **main-after-side** | **0 / 180,010, 412.4 s** | **179,749 / 261, 1.8 s** |

With 8192 MiB the server saved the main state as a 7,672.7 MiB host-cache entry when the side
request took the slot, then logged "making room for prompt cache entry, removing oldest entry
(size = 7672.678 MiB)" when it saved the side request's state: the main state was evicted and fully
re-processed. With 12288 MiB both entries fit and the main state was restored. Host `RssAnon` of
the server peaked at about 9.1 GiB in both arms during the side step.

## Conclusion

Adopted `--cache-ram 12288` in the profile. A ~180K state needs ~7.7 GiB of host cache, so the
8 GiB default holds it only while nothing else is cached. The entry is ~43.6 KB per token
(7,672.7 MiB / 180,009), so a 240K state needs ~10 GiB and a full 262K state ~11.2 GiB: 12 GiB
then holds the main state alone. With harness compaction at 70% (~183K), states stay near 8 GiB.
12 GiB is a compromise for a 32 GiB host. This complements the harness change that moves
compaction summaries off the local slot ([`agent-traffic.md`](../../docs/measurements/agent-traffic.md)).

**Raw data**: `sidecache.jsonl`, `sidecache.py`. Server logs stay local.
