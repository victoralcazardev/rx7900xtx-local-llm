# 2026-10-01: audit of a 5.8-hour coding-agent session

What the adopted profile did during one long real session driven by the omp harness, read from
the server's Prometheus counters and the harness session file. No benchmark, no GPU run of our
own: the server was serving the agent the whole time.

## Setup

- Engine: b11160 `hip-kvmix` (`docs/ENGINES.md`). Profile `qwen38-iq3s-mtp` / `262k-q8q51-mtp`,
  exact `docs/STATUS.md` command line (`--ctx-checkpoints 4`, `-ub 256`, MTP n=3,
  `--reasoning-effort medium`), launched in the foreground, so no server log file exists.
- Harness: omp, compaction at 75% (`thresholdPercent: 75`, `handoff`), main agent on the local
  model; the advisor ran on a cloud model and sent no requests to this server.
- Server uptime at the reading: 5 h 47 min (20,804 s), `-np 1`.

## Commands

```bash
curl -s localhost:8080/metrics | grep -v '^#'
grep -E 'drm-memory|amd-evicted|amd-requested' /proc/<server-pid>/fdinfo/*   # see memory.md
cat /sys/class/drm/card1/device/mem_info_vram_{total,used}
python3 session_misses.py <session.jsonl> --since-ms <server start, epoch ms>
```

## Server counters (whole uptime)

| Metric | Value |
|---|---|
| Generated tokens / time | 425,287 tok / 12,916 s = **32.9 tok/s** mean |
| Uncached prompt tokens / time | 3.03 M tok / 6,999 s = **433 tok/s** mean |
| Cached prompt tokens reused | 49.58 M (94.2% of all prompt tokens) |
| Busy share of uptime | 19,915 of 20,804 s = **96%** |
| Prefill share of busy time | **35%** (10.8% in the 2026-09-28 logs) |
| Deepest context | 201,519 tokens |
| MTP acceptance | 282,691 / 428,058 = **0.66**; per position 0.80 / 0.65 / 0.53 |
| Tokens per decode step | 2.91 |

## Harness session (main agent, since server start)

344 turns, 293,347 output tokens, 1,469,736 uncached and 37,718,653 cached input tokens,
3,539 s summed time to first token. Turns with more than 8,000 uncached tokens:

| Time | Uncached | Cache read | Previous depth | TTFT | Compaction before |
|---|---:|---:|---:|---:|---|
| 17:37 | 193,580 | 0 | 192,406 | 452 s | no |
| 17:46 | 37,270 | 0 | 196,803 | 52 s | yes |
| 18:38 | 172,561 | 0 | 171,820 | 381 s | no |
| 19:09 | 194,326 | 0 | 193,288 | 456 s | no |
| 19:18 | 41,673 | 0 | 195,894 | 59 s | yes |
| 19:59 | 8,545 | 161,518 | 161,522 | 28 s | no |
| 20:11 | 173,946 | 0 | 170,063 | 387 s | no |
| 20:41 | 193,345 | 0 | 192,168 | 453 s | no |
| 20:52 | 36,537 | 0 | 193,345 | 51 s | yes |
| 21:46 | 172,992 | 0 | 171,610 | 383 s | no |

## VRAM at the reading (context ~200K deep, desktop running)

| Reading | Value |
|---|---|
| Card total | 24,560 MiB |
| Card used (all processes) | 23,836 MiB |
| Free | **724 MiB** |
| `llama-server` VRAM (fdinfo) | 22,967 MiB |
| `llama-server` GTT / evicted | 8 MiB / 0 |
| Desktop and other processes | ~870 MiB |
| `llama-server` host RSS | 2.5 GiB; host RAM available 17.3 GiB of 31.3 GiB |

## Conclusion

- **Six full re-processes of 172K-194K tokens with no compaction before them** cost 2,512 s
  (42 min, 13% of server busy time). In each, the prompt was the previous one plus ~1K tokens, yet
  the server reused 0 cached tokens. They cluster at two depths per compaction epoch (~172K and
  ~193K). The three compactions themselves cost only 162 s of re-processing.
- **Cause not established.** The default-verbosity log that would show the divergence position
  was not captured (foreground launch). Hypotheses: (a) the harness rewrites a message older than
  the oldest of the 4 kept context checkpoints; (b) checkpoint placement: since llama.cpp PR
  [#22929](https://github.com/ggml-org/llama.cpp/pull/22929) (merged 2026-05-25, before b11160)
  the server checkpoints before the latest *user* message and otherwise keeps only checkpoints
  `--checkpoint-min-step` (default 8,192) apart, so 4 checkpoints cover a narrow window in a long
  tool loop.
- About 1.56 M of the server's 3.03 M uncached prompt tokens are not in the main session file
  (compaction summary requests and any other client); without a server log they can't be split.
- **Decode, MTP and memory match the documented profile**: 32.9 tok/s mean over a session that
  spent most turns above 100K; acceptance 0.66 as in `agent-traffic.md`; no eviction, no GTT spill.
- **VRAM headroom is thin but not exhausted**: 724 MiB free with the desktop at ~870 MiB. Not
  enough for a larger quant or a bigger compute buffer; enough that the process is not evicted.
