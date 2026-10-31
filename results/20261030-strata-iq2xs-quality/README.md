# Strata v0.2.8 + Qwen3.8-Flash-Next IQ2_XS: coding suite and 240K retrieval (2026-10-30/31)

**What.** The two quality gates on the adopted IQ2_XS config: the six-task coding suite (agent loop with tool
calls, executable hidden tests) against the 27B baseline, and the Spanish multi-key retrieval test at 240K.

**Versions.** Strata `v0.2.8` (engine 0.1.54, no hipBLASLt linked), Qwen3.8-Flash-Next GSQ-RCO IQ2_XS (ISTA-DASLab
`ed59f920`), config = `models.toml` `[strata.iq2_xs]` at commit `91565a6`: mapped mode (`--mmap-experts`),
`--max-context 262144 --kv int8 --vram-reserve-mib 3072 --prefill auto --spec 4 --spec-min-p 0.5 --expert-cache
auto`, env `GPU_PINNED_MIN_XFER_SIZE=1048576`, `STRATA_HIPBLASLT_TUNING=""`, `STRATA_HIPBLASLT_TABLE=off`,
`STRATA_RESIDENT_HEADROOM_GIB=6`. 27B comparison arm: `scripts/launch.py` default (`qwen38-iq3s-mtp` /
`262k-q8q51-mtp`, llama.cpp b11846 + PR #30792 `hip-kvmix`). Coding suite v2 (`bench/coding_suite.py`).

**Machine.** RX 7900 XTX (272 W cap), Ryzen 7 5700X, 31.25 GiB RAM, zram with `vm.swappiness=150`,
`vm.min_free_kbytes=67584`, `vm.watermark_scale_factor=10` (the sysctl candidate was not applied).
`MemAvailable` 27.0-28.1 GiB and `/tmp` 159-471 MiB before each start; GPU junction max 98 °C (guard limit 100 °C,
never reached).

## Coding suite

```bash
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 python3 bench/coding_suite.py --run \
  --label strata-iq2xs --sampling temperature=1.0,top_p=0.95,top_k=20,min_p=0.0 \
  --output results/20261030-strata-iq2xs-quality/coding-suite
# the regression rule asked for seeds 2,3 of the failed tasks on both arms:
... --run --tasks CS3,CS5 --seeds 2,3 --label strata-iq2xs-cs35-s23 --sampling ...   # Strata
... --run --tasks CS3,CS5 --seeds 2,3 --label 27b-cs35-s23                         # 27B, launch.py default
python3 bench/coding_suite.py --compare results/20261018-coding-suite-baseline-27b,<27b-cs35-s23> \
  <strata-iq2xs>,<strata-iq2xs-cs35-s23>
```

| Task | IQ2_XS seed 1 (turns, wall s) | IQ2_XS seeds 2 / 3 | 27B seeds 1 / 2 / 3 |
|---|---|---|---|
| CS1 local bug fix | pass (16, 494) | — | pass / — / — |
| CS2 cross-file change | pass (25, 1,037) | — | pass / — / — |
| CS3 tool-error recovery | **fail** (2, 37) | **fail** (4, 73) / pass (16, 439) | pass / pass / pass |
| CS4 long context | pass (12, 1,304) | — | pass / — / — |
| CS5 post-compaction continuation | **fail** (1, 31) | pass (21, 661) / pass (10, 204) | pass / pass / pass |
| CS6 artifact in a bounded result | pass (33, 911) | — | pass / — / — |

`--compare` verdict: **candidate rejected (regression)**: CS3 1/3 against 3/3, CS5 2/3 against 3/3
("inconclusive: rerun with seeds 4,5,6", not run). 27B seed 1 is the
[2026-10-18 baseline](../20261018-coding-suite-baseline-27b/README.md).

**Tool calls.** IQ2_XS made 169 executed tool calls over the 10 episodes. In 11 responses it wrote a call as raw
text (`<tool_call><function=run_file>...` in `content`) to a tool that does not exist (`run_file` 10 times,
`read_path` once; the suite offers `read_file`, `write_file`, `edit_file`, `run_tests`). Strata's
`tool_call_recovery` turned 7 of them into a structured call, but to whatever existing tool it matched, e.g.
`run_file(path=bottle.py, offset, limit)` became `run_tests`. The other 4 came back as plain text with
`finish_reason: stop`, which the harness reads as "task finished": that is how all three failures ended (CS3 seed 1
at turn 2, CS3 seed 2 at turn 4, CS5 seed 1 at turn 1). The 27B wrote no raw tool-call text in its 4 new episodes
(the 2026-10-18 baseline kept no traces). That the invented name comes from the 2-bit quantization rather than the
model is an inference, not tested.

**Loops.** None: no episode reached the 40-turn cap or its timeout (most turns: 33), no repeated identical
call beyond normal `run_tests` reruns.

**Failures (run rules).** No `stall report`, watchdog kill or 503 in the engine and server logs. Kernel: 2 order-0
`page allocation failure` lines (22:27 from `omp`, 22:49 from `strata`), no `page allocation stall`. The suite's
thermal/VRAM monitor raised no abort in any run (its 25 MB of samples were not kept).

Wall times are temperature-1 episodes with different turn counts, not a speed comparison. Raw data per episode
(`trace.jsonl`, `result.json`, `model.diff`) in `coding-suite/<run>/CS*-s*/`.

## Retrieval at 240K

```bash
cd bench && python3 strata_longctx_quality.py --depths 240000 --docs 5 --output ../results/20261030-strata-iq2xs-quality
```

Temperature 0, thinking off, 5 documents of 240,000 tokens with 4 questions each (`strata-longctx-*/`).

**Partial: 12/12 exact** on the first 3 of 5 documents (every answer `finish_reason: stop`, 0 truncations,
0 failed requests). Cold read of each document: 370, 809 and 1,488 s; the 3 follow-up questions per document reused
229,376 cached tokens and took 58-300 s. The run was stopped during the 4th document's cold read at the user's
session time limit (2026-10-31 01:04), so `scores.json` was not written; raw rows in
`strata-longctx-20261030-233358/summary.jsonl` (documents not kept; the same seeds rebuild them). No stall; one
order-0 `page allocation failure` (23:40, `strata-host`).

## Conclusion

- **Coding suite: fails the gate** against the 27B (regression on CS3). The cause is invalid tool calls, not
  wrong code: when IQ2_XS called real tools, the tasks passed. Not fit for a harness session as the main agent
  until a later quant, Strata version or a stricter tool-call recovery changes this.
- **Retrieval at 240K: 12/12 on 3 of 5 documents**, no verdict on the full 20/20 bar yet (2 documents pending).
- The speed arms (`--conversation-cache-mib 4096`, `STRATA_PF_GEMM=1`, `STRATA_PF_FUSED=1`, resident mode with
  `GPU_PINNED_MIN_XFER_SIZE`, `STRATA_RAM_ADAPT=1`) were not run: the session ended at the user's time limit.
  `STRATA_RAM_ADAPT` needs the resident RAM copy (both code paths require `src.complement_ready()`,
  `src/program/generate.cpp` lines 16588 and 16661), so it has no effect in mapped mode (source-checked, not
  run).
