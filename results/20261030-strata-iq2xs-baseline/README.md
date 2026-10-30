# Strata v0.2.8 + Qwen3.8-Flash-Next IQ2_XS: memory modes, the long-prompt stall and prefill arms (2026-10-30)

**What.** First runs of IQ2_XS on this machine: short decode and a ~120K/~240K cold prompt in three memory modes,
then mapped mode with ROCclr's pinned-copy threshold raised, then two prefill arms (hipBLASLt table, a larger
prompt chunk) and a 128K retrieval check. Goal: a configuration that survives a long prompt, then the fastest one.

**Versions.** Strata `v0.2.8` (engine 0.1.54, built by setup from source, ROCm 7.2.4 in `/opt/rocm`, no hipBLASLt
linked), Qwen3.8-Flash-Next GSQ-RCO IQ2_XS (ISTA-DASLab revision `ed59f920`, shard 1 sha256 `92cee27a…`), pack
`experts.bin` 33.02 GiB, MTP layer from setup. Common engine options: `--max-context 262144 --kv int8 --spec 4
--spec-min-p 0.5 --expert-cache auto --prefill auto --vram-reserve-mib 3072`, `STRATA_RESIDENT_HEADROOM_GIB=6`.

**Machine.** RX 7900 XTX (272 W cap), Ryzen 7 5700X (AVX2, no AVX-512), 31.25 GiB RAM, zram swap with
`vm.swappiness=150`, Kingston A2000 NVMe (btrfs, 97% full after the install). Brave, Zoom and Telegram closed;
`MemAvailable` 24.8-27.7 GiB before each start.

**Commands.**

```bash
./setup.sh --setup --family qwen --model IQ2_XS --gguf-dir <dir with both shards> --backend hip --vision no \
  --no-browser --yes --no-start --context 262144 --kv int8 --vram-reserve-mib 3072 [--low-ram mmap]
python3 scripts/strata.py apply && qwen-flash start
STRATA_DIR=<strata clone at v0.2.8> python3 strata_bench.py --out <arm>.jsonl --label <arm> --fresh 120000 240000
```

`strata_bench.py` (this folder): temperature 0, 800 generated tokens, a unique first line per deep prompt (no prefix
reuse), one JSON line per request, and a 2 s memory watcher (`<arm>.mem.jsonl`).

## Results

| Arm | Memory mode | short gen (tok/s, #1 / #2) | ~120K cold prompt (121,709 tokens) |
|---|---|---|---|
| A | resident, automatic copy 18.53 GiB | 60.5 / 63.0 | **failed**: stalled at 56,320; 8.6 GiB of the engine in zram; kernel `page allocation stall`, `svm_range_restore_work`; engine restarted by its 60 s watchdog |
| B | resident, `--resident-budget-gib 14` | 45.8 / 50.9 | **failed** twice: stalled at 18,432 with threads in `folio_wait`; watchdog exit -6 |
| C | mapped (`--low-ram mmap`) | 35.7 / 55.9 | **failed**: stalled at 24,576; server silence kill after 300 s |
| D | C + `GPU_PINNED_MIN_XFER_SIZE=1048576` | 44.2 / 59.1 | **passed**: 672 tok/s prefill (199 s wall), 44.9 tok/s gen, drafts 425/582, min `MemAvailable` 25.7 GiB, no kernel warning |

D at ~240K (245,002-token cold prompt): **passed**, but slow: 158.7 tok/s prefill (1,566 s wall), 36.7 tok/s gen,
drafts 405/529, min `MemAvailable` 23.2 GiB, zram up to 6.5 GiB with 3.37 M pages swapped in, no kernel warning,
GPU junction max 93 °C. The Coder (all experts in RAM or VRAM) read ~250K at 739 tok/s on 2026-10-16; IQ2_XS in
mapped mode streams the experts the GPU does not hold from `experts.bin` on every 8192-token chunk.

- The first short request after a start is the slowest in every arm (cold expert caches); the second is the warm figure.
- Cause of A-C (source-checked in Strata `src/program/generate.cpp` near line 2890 and `docs/AMD_HIP.md`): ROCclr
  locks a pageable copy source of 1 MiB or more as a GPU userptr; expert blobs are 1.1-1.5 MB, so every copy from
  `experts.bin` or the pageable RAM copy is locked, and page reclaim suspends the GPU queues.
- Server output was discarded by the start wrapper during A and the first B run; from the second B run on it is in
  `strata-iq2_xs.log.server.out` (prompt progress, exit codes).
- Text SHAs differ between runs at temperature 0 (upstream #4673), so they are recorded but not compared.

## hipBLASLt tuning table (arm G)

The setup-built engine had no hipBLASLt (`build-hip/CMakeCache.txt`: `hipblaslt_DIR-NOTFOUND`, set before `pacman -S
hipblaslt` 7.2.4). Rebuilt with `cmake -U 'hipblaslt*' build-hip && cmake --build build-hip --target strata -j8`
(41 s; `ldd` shows `libhipblaslt.so.1`), then `STRATA_HIPBLASLT_TABLE=on` (gfx1100 is not in the table's auto list):
the log says `hipBLASLt tuning enabled (26 rows, gfx1100, version 100202)`. Same config as D otherwise, interleaved
with D on the old binary (`engine/strata.nohipblaslt`):

| Run (121,709-token cold prompt) | prefill tok/s | gen tok/s at ~120K | short gen #2 |
|---|---|---|---|
| D run 1 / run 2 (no hipBLASLt) | 672.4 / 552.4 | 44.9 / 43.1 | 59.1 / 65.1 |
| G run 1 / run 2 (hipBLASLt table) | 945.7 / 944.0 | 33.8 / 36.4 | 60.7 / 59.4 |

Prefill +41% to +71%, but decode at ~120K -16% to -25% in both pairs. With `STRATA_HIPBLASLT_VERBOSE=1` the log shows
the table's large-T solutions also chosen for small calls (`T=1` to `T=41`, `N=2560 K=640`, solution 1147): the
table is matched by shape without a minimum T (`src/prefill/gemm.cu` `try_hipblaslt`), which is the likely cause
(inference, not isolated). Not adopted: decode dominates agent time here. Two transient kernel `page allocation
failure` lines (order 0, no stall) appeared during D run 2 and G run 2.

## Larger prompt chunk (arm H)

D with `--prefill 16384` in `user_args` (explicit N keeps the chunk; `--prefill auto:32768` was first tried and the
host-aware plan cut it to 4096-token chunks, so it was not benched): 121,709-token prompt read at **331.0 tok/s**
(392 s wall) against 552-672 for D, gen 33.3 tok/s at ~120K, short #2 66.6. Not adopted: a bigger chunk lends more
GPU slots whose experts then stream from `experts.bin` (the opposite of #4683's CUDA result, where the set fits RAM).

## Retrieval at 128K (output sanity)

`cd bench && python3 strata_longctx_quality.py --depths 128000 --docs 2 --output <folder>` on config D (temperature 0,
thinking off): **8/8 exact**, 0 loops, 0 truncations, every answer `finish_reason: stop`. Each question re-read its
~128K document (71-507 s per question). Raw scores in `quality-128k/` (documents not kept; the same seeds rebuild
them). 240K retrieval (5 documents) was not run: at ~159 tok/s each cold 240K read takes ~26 min.

## Conclusion

- Adopted config (`models.toml` `[strata.iq2_xs]`): mapped mode, 262K, KV int8, `--vram-reserve-mib 3072`,
  `--prefill auto`, `GPU_PINNED_MIN_XFER_SIZE=1048576`, no hipBLASLt table.
- Without `GPU_PINNED_MIN_XFER_SIZE` no memory mode survives a 120K cold prompt on this host; with it mapped mode
  passes 120K and 240K, and 128K retrieval is 8/8.
- Warm short decode 59-65 tok/s (above the Coder's 52-57); ~120K decode 43-45 tok/s, ~240K 36.7 tok/s; cold
  prefill 552-672 tok/s at 120K but only ~159 at 240K, so a cache miss or compaction deep in a session costs minutes.
- Not measured: the resident mode with the fix (its warm short decode, 60.5 / 63.0, was not better than D's, and it
  left ~6 GiB free with zram swapping), `STRATA_PF_GEMM`/`STRATA_PF_FUSED`, `--calibrate`, the coding suite, 240K
  retrieval, a real harness session.
