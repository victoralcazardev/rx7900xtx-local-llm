# Strata Coder IQ1_M: 128K, 200K and 262K context with KV int8 on 31 GiB RAM (2026-10-15)

**What.** "Next iteration" steps 1-2 of
[`strata-flash-next.md`](../../docs/models/strata-flash-next.md#next-iteration-goal-the-longest-context-that-keeps-quality):
the same configuration at three context sizes, each with a deep coding prompt, with RAM freed first. It
re-tests the 262K int8 failure of [`20261015-strata-coder-first-run/`](../20261015-strata-coder-first-run/README.md),
which ran with 8 GiB of `/tmp` (tmpfs) renders in RAM ([`20261015-strata-coder-idle-oom/`](../20261015-strata-coder-idle-oom/README.md)).

**Versions.** Strata `v0.1.44.1` (`296b59d2`), same engine build and Coder IQ1_M pack as the first run.
`--kv int8 --resident-experts --spec 4`, `STRATA_RESIDENT_PIN=0`, `STRATA_RESIDENT_HEADROOM_GIB=6`; only
`--max-context` changes between rows. After each `setup.sh` run the config JSON differed from the previous one
in `--max-context` only (checked with `diff`).

**Machine.** RX 7900 XTX at the 272 W cap, Ryzen 7 5700X, 31.25 GiB RAM, KDE desktop and agent CLIs open,
browser closed, `/tmp` empty and capped at 4 GiB. `MemAvailable` before each start: 23.9 / 24.2 / 24.3 GiB.

**Commands.**

```bash
./setup.sh --setup --family coder --model IQ1_M --gguf-dir <models>/Qwen3.8-Flash-Next-GSQ-RCO-Coder-IQ1_M \
  --backend hip --vision no --no-browser --yes --no-start --context <131072|204800|262144> --kv int8
qwen-flash start
STRATA_DIR=<strata clone> python3 strata_bench.py 120000 [195000|250000]
```

`strata_bench.py` here cuts the filler to the requested size (the first run's version overshot: asked for
126K, it built a 171K-token prompt). Requests: temperature 0.6, `max_tokens` 800, thinking at the template
default; every answer hit the cap, so these are speed numbers. The second deep prompt shares its first
114,688 tokens with the first one, which Strata reuses from its prefix cache. RAM was sampled every 2 s
(`watch-ram.log`: `MemAvailable`, `GPUActive`, GTT, VRAM, zram, swap, `pswpin`).

## Results

| Context | Experts in RAM | GPU expert cache | Deep prompt 1 | Deep prompt 2 | Short gen (2 runs) | Min `MemAvailable` | Swap-in during run |
|---|---|---|---|---|---|---|---|
| 128K | 10.80 GiB | 8412 slots, VRAM 614 MiB free | 120,423 tokens at 820 tok/s, gen 62.2 tok/s | — | 69.2 / 70.2 tok/s | 11.0 GiB | 14 MiB |
| 200K | 11.87 GiB | 7852 slots (14.94 GiB), 614 MiB free | 120,423 at 851 tok/s, gen 62.7 | 197,503 (82,815 new) at 736 tok/s, gen 73.7 | 58.5 / 61.6 | 10.8 GiB | 463 MiB |
| 262K | 12.71 GiB | 7412 slots (14.11 GiB), 604 MiB free | 120,423 at 848 tok/s, gen 60.1 | 256,633 (141,945 new) at 733 tok/s, gen 63.4 | 56.0 / 65.0 | 9.7 GiB | 1.33 GiB |

- No `stall report`, no engine restart, 0 blob reads from the pack in all three; all lendable prompt slots kept
  their experts in RAM (1776-1779 of 1776-1779).
- `GPUActive` (amdgpu RAM) stayed at 1.07-1.21 GiB in every run.
- Swap was not flat at 200K and 262K: swap-ins came in bursts (up to 576 MiB in 2 s) while 10+ GiB stayed
  available, a pattern consistent with zram at swappiness 150 paging the pageable copy (`unverified`). Decode
  speed did not drop.

## Retrieval quality at 262K int8 (partial)

`bench/strata_longctx_quality.py` runs `bench/longctx_quality.py`'s Spanish multi-key retrieval test
(same seeds, needles, questions and scoring) against the running server: tokens counted with
`/v1/messages/count_tokens`, questions on `/v1/chat/completions`, temperature 0, thinking off
(`chat_template_kwargs.enable_thinking=false`, 0 reasoning characters in every answer), `max_tokens` 200.
Documents are built with Strata's tokenizer, so their text can differ slightly from the 27B runs; the
values, IDs and needle positions are the same.

```bash
cd bench && python3 strata_longctx_quality.py --depths 128000 190000 240000 --docs 5
```

| Depth | Strata Coder IQ1_M | 27B IQ3_S (reference) | Strata decode | Strata cold prefill | 27B cold prefill |
|---|---|---|---|---|---|
| 128K | 20/20 exact | 20/20 ([20260925](../20260925-longctx-quality-200k/README.md)) | 98.7-112.9 tok/s | 831-851 tok/s | 585 tok/s |
| 190K | 20/20 exact | 20/20 ([20261003](../20261003-longctx-quality-190k-240k/README.md)) | 90.3-108.8 | 811-820 | 429-434 |
| 240K | 4/4 exact (1 of 5 documents) | 20/20 ([20261003](../20261003-longctx-quality-190k-240k/README.md)) | 97.1-105.8 | 797 | 379 |

No loops, no truncation, every answer `finish_reason: stop`. Decode here is a ~60-token JSON answer with
MTP; it is not comparable with the 800-token speed rows above. The 240K row stopped at document 2 (next
section): its 4 recorded failures are lost connections, not wrong answers. Raw data: `quality-262k/`.

## Desktop crash when Slack opened (19:01:54)

Strata at 262K left 604 MiB of VRAM free. Opening Slack (an Electron app that draws with the GPU) made the
driver move GPU memory into system RAM: within 4 s GTT went from 1.08 to 15.22 GiB and `GPUActive` from 1.08
to 10.17 GiB, while VRAM use stayed at 23.9 GiB (`watch-slack-crash.log`). `MemAvailable` fell from 9.75 to
1.16 GiB, zram filled, and the kernel OOM killer took Slack, QtWebEngine and hermes; amdgpu then logged
`Not enough memory for command submission!` and the KDE session (kwin_wayland, plasmashell, Xwayland)
ended (`kernel-slack-crash.txt`). The 3 GiB watchdog killed Strata at once, too late to help.

This is the same failure as the idle OOM's 10.4 GiB of `gpu_active`: a full VRAM plus another GPU
client pushes GPU memory into RAM faster than anything can react.

With Strata stopped, the same apps need little VRAM: desktop 1,125 MiB, +111 MiB after starting Slack, +169
MiB more after Brave (1,405 MiB total, read 25 s after each start). So the 604 MiB left free was in principle
enough for Slack; why the driver still evicted GiBs is `unverified` (startup peak or fragmentation are guesses).

## Conclusion

On this machine, with RAM freed first, 262K + KV int8 works: the speed bar of more than 45 tok/s at 128K+ fill
passes at every depth (63.4 tok/s at 257K), and retrieval matches the 27B at 128K and 190K (20/20 each).
The first run's 262K stall is superseded: it ran with 8 GiB of tmpfs files in RAM. Open: the 240K row
(4 of 20 done), and the VRAM margin, because with ~600 MiB free a GPU app starting on the desktop takes it
down. Setup's own advice for a card that also drives the desktop is `./setup.sh --vram-reserve-mib 3072`
(~2.3 GB less expert cache, "a few %" of speed by its message; not measured here).
