# Strata v0.2.19 + engine 0.1.65 with the abliterated SC117 IQ2_XS: installed, served, below the floor (2026-11-22)

Arm (task `engine-b12633-inkling`, T9, spec S7): run the abliterated
[SC117 Qwen3.8-Flash-Next GSQ-RCO-IQ2_XS](../../docs/models/strata-qwen-flash-next.md#review-2026-11-14-abliterated-flash-next-ggufs-control-vector-vs-weight-transplant)
set on Strata **v0.2.19** with `strata-engine` **0.1.65** (its RDNA3 release), against the 2026-10-30 ISTA IQ2_XS
baselines.

**Outcome: installed and served, 5.8-12.8 tok/s decode — below the 15 tok/s floor and 5-10x under the 2026-10-30
short decode (59-65 tok/s).** The binding constraint is the storage path, not the new kernels: the pack (33.0 GiB of
experts) plus the page cache cannot hold the file tier, the mapped path reports `page cache held 0.0 MB`, and 39-191 GB
is read per request; on top of that the engine priced its drive at **0.15 GB/s** because the `--native` dense shard
still lives on the rotational HDD. 240K, retrieval and the coding suite were not run (the arm was already below the
floor, and the time box).

Two sessions of the same arm are in `raw/`: the first had no `GPU_PINNED_MIN_XFER_SIZE` and the engine died on
`verify: timed out at layer 28`; the second, with the value set, completed 4/4 requests. Numbers below are the second
session unless stated.

## Versions

| What | Value |
|---|---|
| Strata clone | `v0.2.19` (`c6f6427d9`), runnable tree in `~/IA/Motores/Strata/terminal/` |
| Engine | **0.1.65** `local-hip` (built from the checkout, `llama.cpp 3cf0325`), `archs: [gfx1100]`, `src 3412d539bcdc7ff5` |
| ROCm workaround | `lib_dirs` = `["~/IA/Motores/rocm-10.1-arch-hip/pkg/opt/rocm/lib", "/opt/rocm/lib"]`; `ldd` then resolves `libamdhip64.so.7` to Arch's `libamdhip64.so.7.16.0-0000000` (sha256 `4c34b4b5…`), while rocBLAS/hipBLAS/hipBLASLt still come from `/opt/rocm` (system `hip-runtime-amd 10.1-2.1`, CachyOS) |
| Model | SC117 `Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ2_XS`, revision `90a3350c`; shard 1 39,665,015,072 B (`4acc3ebb…`), shard 2 28,800,138,432 B (`316b46f3…`, the shared n-gram/PLE table) |
| Where the files are | pack + `experts.bin` on the NVMe (`~/IA/Motores/Strata-data/packs/iq2_xs`, 35,454,976,000 B); **PLE shard 2 copied to the NVMe** (`~/IA/Modelos/…-SC117/`, 28.8 GB, 3m30s from the HDD, sha256 of the copy verified); `--native` dense shard 1 read from `<hdd>/IA/Modelos/…-SC117/` (NTFS, rotational) |
| Run config | 262144 context, KV int8, `--mmap-experts`, `--prefill auto`, `--expert-cache auto`, `--vram-reserve-mib 3072`, `env: GPU_PINNED_MIN_XFER_SIZE=1048576`, `STRATA_HIPBLASLT_TUNING=…/gfx1100-hipblaslt-100401.txt`; DFlash2 picked by the server (`--spec 6 --draft-conf 0.7 --draft-fallback none`) |
| Start | ready in ~30 s (first session) / ~115 s (second), GPU expert cache 9472 experts = 12.68 GiB VRAM, 3278 MiB VRAM free while loading, `mapping the experts from the model files (about 40 GB, --mmap-experts)` |

## Numbers

Conditions: RX 7900 XTX 24 GB, Ryzen 7 5700X, 31 GB RAM, desktop open, `temperature 0`, `max_tokens 800`, prompts
from `strata_bench.py` (the clone's C/C++ source as filler, `STRATA_DIR=~/IA/Motores/Strata/engine`).

| Request | prefill tok/s | decode tok/s | expert-cache hit | wall | min `MemAvailable` | max swap | `pswpin` Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| short#1 (82 new tokens) | 3.5 (82 tokens, meaningless) | **5.8** | 86.1% | 162.5 s | 13.16 GiB | 14.09 GiB | 1,693,457 pages |
| short#2 (5 new, 77 cached) | 1.9 | **6.6** | 90.9% | 123.4 s | 13.87 GiB | 14.75 GiB | 772,901 |
| short#3 (95 new) | 4.5 | **9.8** | 91.8% | 102.5 s | 16.33 GiB | 14.56 GiB | 1,058,280 |
| **deep 69,698-token prompt** | **324.2** | **12.8** | 92.3% | 278.1 s | 17.46 GiB | 14.79 GiB | 4,006,593 |

All four ended `finish_reason: length` at the 800-token cap while still thinking (the server printed its thinking-budget
tip); no request returned an empty `content` before the cap with `stop`.

First session (no `GPU_PINNED_MIN_XFER_SIZE`), same config otherwise: smoke `finish_reason: stop` at 16.3 tok/s
(cold, 40 tokens); bench short#1 11.4 tok/s with 88.7% cache hit; short#2 died at 398 tokens —
`Unrecoverable native verification failure: verify: timed out at layer 28; its GPU waits were released but the GPU did
not finish within 5 s (#267)`, engine exit `-15`, next request `HTTP 503`. That is the 2026-10-30 stall class, so the
release note's "zero environment variables needed" does not hold on this host in mapped mode.

### Against the baselines

| Reference | Decode |
|---|---|
| **This arm** (v0.2.19 / 0.1.65, SC117 IQ2_XS, mapped, shards split HDD/NVMe) | **5.8-12.8 tok/s short, 12.8 at a 69.7K fill, prefill 324.2 tok/s** |
| ISTA IQ2_XS, v0.2.8, 2026-10-30 (both shards NVMe) | 59-65 warm short, 43-45 at ~120K, 36.7 at 240K, prefill 159 tok/s at 240K |
| User's floor for a Flash-Next set | 15 tok/s |
| `strata-engine` 0.1.65 release note (RX 7900 XT, conditions unstated) | 97.9 tok/s, peak 103.7 |
| Unsloth UD-IQ2_XS, v0.2.11, 2026-11-05 (rejected) | 2.6-8.2 short, 10.8 best at 131K |

**Verdict: rejected for now, on speed — below the floor.** The 0.1.65 claim is not reproduced under these conditions,
and the 2026-10-30 numbers are not reachable from this file layout. The SC117 weights additionally lack the evidence
the ISTA set has (the 2026-11-14 review), and this run cannot separate quant from storage.

## Why it was storage-bound (engine's own numbers)

```
prefill plan inputs: 33.0 GiB experts, 12.7 GiB in the GPU caches, 0.0 GiB RAM copy (0 lend slots kept),
  file tier 20.3 GiB; 14.8 GiB available for the page cache; PCIe 14.0 GB/s; drive 0.15 GB/s
  (sda is a rotational disk); a 32768-token prompt
prefill plan: ... about 67.5 GB read from the drive per 32768-token prompt, 482 s
```

- **`0.0 GiB RAM copy`**: mapped mode keeps nothing resident, so 20.3 GiB of experts is the file tier against 14.8-18.7
  GiB of page cache — it cannot fit.
- **`page cache held 0.0 MB at the read`** on every request (decode-gate line): the mapped path re-reads blobs instead of
  hitting the OS cache. Measured storage reads per request: **87.1, 43.9, 39.0 and 191.2 GB** (the last one the 69.7K
  prompt), 79,094 major faults on the short requests and 298,105 on the deep one.
- **`drive 0.15 GB/s (sda is a rotational disk)`**: the engine priced the drive from the `--native` shard's mount, and
  that shard is on the NTFS HDD. Its reads are on the per-token path for the tensors the pack does not carry
  (`dense.bin` is only 1.54 GB of roughly 4 GB of non-expert weights).
- **Swap**: 13-15 GiB in zram and 0.4-4.0M `pswpin` pages per request (this host runs swappiness 150), so part of the
  cost is the desktop being pushed out while the file tier streams.

None of these is a 0.1.65 kernel statement: the run measures the storage path. A fair kernel A/B needs the dense shard
on the NVMe and the file tier reduced (a resident RAM copy, or a smaller size), which does not fit here (see below).

## Disk, and the road here

| Point | `/home` free (1e9) |
|---|---|
| Session 1: before any work | 21.96 GB |
| Session 1: after the clone update to v0.2.19 | 21.90 GB |
| Session 1: after the all-in-RAM engine build + small pack + DFlash2 | 20.20 GB |
| Session 2: start (NVMe copy of SC117 deleted by the parent; the model stayed on `<hdd>`) | 89.23 GB |
| Session 2: after `--low-ram mmap` built `experts.bin` (35.45 GB) | 56.99 GB |
| Session 2: after copying shard 2 to the NVMe | 27.39 GB |
| Session 2: end (server stopped, logs written) | 26.45 GB |

**The block that cost session 1 (kept as history):** the mapped install writes one `experts.bin` of the whole expert
arena (`arena_gb + 1` = 36.5 GB for IQ2_XS) and `/home` had 21.96 GB. Setup refused exactly as documented in
`docs/sop/strata.md`: `not enough free disk space for the low-RAM copy of the experts in
…/Strata-data/packs/iq2_xs: it needs about 36 GB and 22 GB are free there.` **Fix that worked:** the model GGUFs do not
need to be on the NVMe; they only need to be *readable* while the pack is built. With the set on `<hdd>` and
`--gguf-dir` pointing there, setup wrote the pack to the NVMe and exited 0. Only the pack, and the n-gram table's shard
(random per-token reads), have to live on the NVMe.

## Commands

```bash
# install (session 2): GGUF source on the HDD, pack and experts.bin on the NVMe
cd ~/IA/Motores/Strata && ./setup.sh --setup --family qwen --model IQ2_XS \
  --gguf-dir <hdd>/IA/Modelos/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ2_XS-SC117 \
  --backend hip --vision no --no-browser --yes --no-start \
  --context 262144 --kv int8 --vram-reserve-mib 3072 --low-ram mmap
# the ROCm 10.1 workaround (Arch's generic lib first on the engine's search path)
#   run config: "lib_dirs": ["~/IA/Motores/rocm-10.1-arch-hip/pkg/opt/rocm/lib", "/opt/rocm/lib"]
cp <hdd>/…-00002-of-00002.gguf ~/IA/Modelos/…-SC117/    # PLE shard on the NVMe; --ple-gguf repointed
#   run config: env GPU_PINNED_MIN_XFER_SIZE=1048576 (without it the engine timed out at layer 28)
./run-iq2_xs.sh                                          # ready in 30-115 s
STRATA_DIR=~/IA/Motores/Strata/engine python3 strata_bench.py --out <file.jsonl> 2 65536   # after 2 shorts
```

Logs: [`raw/setup-sc117-mmap.log`](raw/setup-sc117-mmap.log) (the install that worked),
[`raw/bench-0219-sc117.jsonl`](raw/bench-0219-sc117.jsonl) (session 1, engine death),
[`raw/bench-0219-sc117-pin.jsonl`](raw/bench-0219-sc117-pin.jsonl) (session 2, 4 requests),
[`raw/engine-0219-sc117.log`](raw/engine-0219-sc117.log) (engine start, plan, per-request file-tier I/O),
[`raw/plan-and-io.txt`](raw/plan-and-io.txt), [`raw/strata-iq2_xs.json`](raw/strata-iq2_xs.json),
[`raw/run-iq2_xs.sh`](raw/run-iq2_xs.sh), plus the session-1 files (`setup-sc117-attempt.log`,
`setup-sc117-all-in-ram.log`, `engine-0.1.65-probe.log`, `disk-before.txt`, `disk-after.txt`).

## Not run, and what would change the verdict

- **Not run**: 240K fill (the page-cache arithmetic is worse: 20.3 GiB file tier against 14.8 GiB, and 191 GB read for
  69.7K), 240K retrieval, the coding suite (`bench/coding_suite.py --run`, 6/6 baseline on the 27B), the abliteration
  refusal mini-check, and `strata.py apply` (no `[strata.*]` table was added: the arm fails the speed bar).
- **What would make the next arm meaningful**: the dense shard on the NVMe (41.2 GB for the 39.7 GB file, against
  27 GB free — or copy only the tensors the pack lacks), and a lower file tier, i.e. a resident RAM copy (18-20 GiB,
  which does not coexist with a 14-15 GiB desktop and swap on 31 GiB) or a smaller quant. Until then, 0.1.65's
  prefill/decode claims remain unmeasured on this hardware.
