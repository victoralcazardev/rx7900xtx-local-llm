# Strata Coder IQ1_M at 128K int8: OOM with no request sent (2026-10-15)

**What.** A restart of the 128K int8 configuration from
[`20261015-strata-coder-first-run/`](../20261015-strata-coder-first-run/README.md), meant as step 1 of the
"Next iteration" plan ([`strata-qwen-flash-next.md`](../../docs/models/strata-qwen-flash-next.md#next-iteration-goal-the-longest-context-that-keeps-quality)).
The kernel OOM killer fired about 75 s after the start log, while the server was idle. No benchmark ran.

**Versions.** Strata `v0.1.44.1` (`296b59d2`), same engine build, model and config as the first run:
`--max-context 131072 --kv int8 --resident-experts`, `STRATA_RESIDENT_PIN=0`, `STRATA_RESIDENT_HEADROOM_GIB=6`.

**Machine state at start.** `MemAvailable` 16.3 GiB (Brave 5.5 GiB still open). zram already held 9.3 GiB
of data in 8.5 GiB of RAM. Almost all of it was `/tmp`, a tmpfs: 42 test renders (8.0 GiB of FFV1/H.264,
10-120 s each) left there by a video-editing agent session. Processes held only 0.18 GiB of swap (`VmSwap`).

**Command.** `qwen-flash start` (the wrapper from [`docs/sop/strata.md`](../../docs/sop/strata.md)).

**Observed** (excerpts: [`strata-start.txt`](strata-start.txt), [`kernel-oom.txt`](kernel-oom.txt)):

| Item | Value |
|---|---|
| Resident expert copy | 9.05 GiB (first run: 7.75 GiB); 863 of 1776 lendable slots in RAM |
| VRAM free with everything loaded | 614 MiB |
| OOM time | 17:29:26, no request sent |
| zram RAM use at OOM (`zspages`, DMA32 + Normal) | 18.5 GiB |
| `gpu_active` at OOM | 10.4 GiB |
| Free swap at OOM | 10.1 GiB of 31.3 GiB |
| Killed | `systemd-coredump` (3x), then `strata` (anon-rss 135 MB: its copy was already in zram) |
| amdgpu | `Not enough memory for command submission!` |

**Reading.**

- Strata sizes the copy as `MemAvailable` minus the headroom, so more free RAM at start gives a bigger copy,
  not more margin. `qwen-flash`'s 16 GiB floor is not a safe bound.
- zram does not help here: quantized expert weights and video files barely compress, so moving them to zram
  frees almost no RAM. The tmpfs renders could not be dropped either (no copy on disk).
- `gpu_active` (amdgpu TTM pages in system RAM) is not covered by the headroom. Where its 10.4 GiB comes from
  (host staging buffers or VRAM evicted to RAM) is `unverified`.

**Actions taken.** The 42 renders were deleted after checking: none matched a file on disk by size, none
longer than 120 s, the session that made them had committed its work. `MemAvailable` went to 23.3 GiB and
zram to 0.47 GiB. `qwen-flash` now refuses to start when `/tmp` (tmpfs) holds more than 2 GiB.

**Next.** Fix the copy size with the engine's `--resident-budget-gib N` (`src/program/generate.cpp`) instead
of relying on the headroom, and log `GPUActive` from `/proc/meminfo` during the re-run.
