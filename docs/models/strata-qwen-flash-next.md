# Qwen3.8-Flash-Next via Strata

## Current state (2026-10-30)

- **Role**: optional second engine on `:8080`, never the default; one of the repository's focus models with
  the 27B and Qwen4 ([`DECISIONS.md`](../DECISIONS.md), 2026-10-29).
- **Installed (2026-10-30)**: Strata v0.2.8 (engine 0.1.54, built from source against ROCm 7.2.4) with
  Qwen3.8-Flash-Next IQ2_XS in mapped mode, settings in `models.toml` `[strata.iq2_xs]`, procedure
  [`../sop/strata.md`](../sop/strata.md). The Coder IQ1_M entry stays for a re-download only (shard 1 deleted).
- **IQ2_XS measured (2026-10-30)**: warm short decode 59-65 tok/s; 121,709-token cold prompt 552-672 tok/s prefill,
  43-45 tok/s decode; 245,002 tokens 159 tok/s prefill (26 min), 36.7 tok/s decode; 128K retrieval 8/8. Requires
  `GPU_PINNED_MIN_XFER_SIZE=1048576`: without it every memory mode stalled on a 120K prompt. hipBLASLt table and
  `--prefill 16384` rejected ([IQ2_XS on v0.2.8](#iq2_xs-on-v028-2026-10-30),
  [results](../../results/20261030-strata-iq2xs-baseline/README.md)).
- **Last measured Coder** (older Strata build and the old shard, 2026-10-16): 52-57 tok/s from short prompts to
  a ~250K context, retrieval 20/20 at 240K, with `--vram-reserve-mib 3072`
  ([results](../../results/20261016-strata-coder-vram-reserve/README.md)).
- **Quality gates (2026-10-30/31)**: coding suite **fails** against the 27B (`--compare`: regression; CS3 1/3,
  CS5 2/3): IQ2_XS sometimes calls a tool that does not exist (`run_file`) as raw text, which ends the episode;
  240K retrieval 12/12 on 3 of 5 documents (partial) ([quality gates](#quality-gates-2026-10-3031),
  [results](../../results/20261030-strata-iq2xs-quality/README.md)).
- **Next**: the 2 missing 240K retrieval documents (the script has no resume: whole run again, ~1.5-3 h); the speed arms, one per run on the
  current config (`--conversation-cache-mib 4096`, `STRATA_PF_GEMM=1`,
  `STRATA_PF_FUSED=1`, resident mode with `GPU_PINNED_MIN_XFER_SIZE`, then `STRATA_RAM_ADAPT=1` on the resident
  mode only); `--calibrate`; the sysctl candidate (SOP). A harness session only after a fix for the invented tool
  calls.
- **Limit on this machine**: RAM (31.25 GiB usable), not VRAM.

The sections below are dated history, oldest first: a desk review (2026-09-29 to 2026-10-08), the first run
(2026-10-15), the tuning plan (2026-10-16), the 2026-10-24 review and the 2026-10-30 config review and fit check.

## Parked state (2026-10-21, ended 2026-10-24)

Decision 2026-10-21 (commit `475405c`): park Gyro-S/Strata testing until new models arrive. Coder shard 1
was deleted on 2026-10-19 (upstream replaced it; shard 2 kept), so the Coder is not installed. Last
measured config and numbers: the sections below (262K, KV int8, 3 GiB VRAM reserve, 52-57 tok/s, retrieval
20/20 to 240K). Version drift: upstream Strata is at v0.2.3 (2026-10-23, engine 0.1.48; ships a
`linux-x86_64-hip-rx7900` package the author has not run on real RX 7000 hardware); the last local
build was v0.2.0-beta-4. Nothing was tested on v0.2.x.

## Credits and upstream

- **Engine**: [Strata](https://github.com/Niko1221/Strata) by Niko1221 and the Strata
  contributors, MIT license. Reviewed at tag
  [`v0.1.25`](https://github.com/Niko1221/Strata/tree/8fc40dde5e8897a097ec0ea6ea27f9313d171268)
  (`8fc40dd`) and
  [`v0.1.26`](https://github.com/Niko1221/Strata/releases/tag/v0.1.26) (`ac8b251`).
- **AMD HIP backend**: merged from Strata PR #121 (Konstantinos Korres), superseding PR #94.
- **Model**: [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) (Qwen), and the
  expert-pruned coding variant
  [Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF)
  (ISTA-DASLab). Check each model card's license before redistributing anything.

If this is ever integrated, Strata stays the upstream: this repository would only add a launcher
profile and measurements, never a fork of the engine.

## What Strata is

Not llama.cpp. Its own engine for a large MoE model (24,576 experts, 10 per token) on a
consumer GPU plus system RAM:

- **VRAM**: attention/DeltaNet mixers, routers, shared experts, output head, MTP draft layer,
  KV cache, and an expert cache filled with the most-used experts.
- **RAM**: every expert, pinned; the CPU computes experts missing from VRAM in parallel with the
  GPU.
- **Disk**: shard 2 of the GGUF, a 28.8 GB n-gram/PLE lookup table, "a few rows per token, read
  unbuffered past the OS cache (`--ple-io direct`, the default ...)" (Strata `docs/DETAILS.md`, v0.1.41).
  An NVMe SSD is strongly recommended upstream.

It does **not** run in this repository's `llama-server` binaries. The GGUF alone is not enough:
Strata's setup also builds a native pack (`tools/iq_pack.py`), an MTP runtime and uses a
per-model expert profile. On AMD it is Linux-only, gfx1100 only (RX 7900 XT/XTX), one GPU, no
vision (`setup.py`: `AMD_ARCHS = ("gfx1100",)`).

## Upstream claims vs. upstream evidence

A post by the Strata author announced: "Run Qwen3.8-Flash-Next on 8GB+ AMD GPU. RX 7900 XTX runs
the model at a sustained 52-60 output tokens per second + 1250 prompt processing tokens per
second. Enable KV Cache - k8v4 for +10% boost in performance with no quality loss."

| Claim | Upstream evidence | Status |
|---|---|---|
| "8GB+ AMD GPU" | The AMD backend only accepts gfx1100 (RX 7900 XT 20 GB / XTX 24 GB). 8 GB is the NVIDIA minimum | Refuted (source read) |
| 52-60 tok/s output on an RX 7900 XTX | `docs/AMD_HIP_PERFORMANCE.md`: 55.5-59.2 tok/s. Conditions: 128-token output cap, temperature 0, reasoning disabled, 4,210/8,830-token prompts, OrcaRouter IQ3_XXS, 64 GiB RAM, Ryzen 9 7950X3D, 272 W cap | Verified (source read), narrow conditions |
| 1,250 tok/s prompt processing | Published table: 447.5-966.5 tok/s. Commit `e5dcc0c` claims +42-59% from a hipBLASLt 100200 tuning table, without a published re-run | Hypothesis (not in published data) |
| `--kv k8v4` (INT8 K + Hadamard-rotated Q4_0 V) gives +10% with no quality loss | Measured only on an RTX 3090, Coder IQ1_M, 198K: 85 → 99 tok/s, same needle results, prompts 2-5% slower. The gain comes from 23% less KV memory leaving room for more experts in VRAM, not from faster attention. Not measured on AMD. Disables KV streaming (default from 64K) | Hypothesis on AMD; quality evidence is needle tests only |

## Fit on a 24 GB RX 7900 XTX with 32 GiB RAM (31.25 GiB usable)

- **Before v0.1.25**: every expert pinned in RAM; RAM must hold shard 1 plus ~10 GB. Coder IQ1_M
  shard 1 is 29.6 GB, so it does not fit. Upstream: a bigger GPU "doesn't lower the RAM needed".
- **v0.1.26 low-RAM mode** (`--low-ram`, chosen automatically by setup): experts are memory-mapped
  from the pack's `experts.bin` (+23-50 GB of disk) instead of copied to RAM. Coder committed
  memory drops from 36 GB to ~13 GB, same answers. Near-normal speed is only claimed where the
  GPU holds all Coder experts (RTX 5090, 32 GB). With a smaller GPU "most experts come from the
  SSD and it is much slower".
- On a 24 GB card, non-expert weights and the KV cache also use VRAM, so part of the experts
  comes from the page cache or disk (the n-gram table bypasses the page cache, see above).
  **Not measured** by upstream for this combination.
- **Disk**: needs roughly 30 GB (shard 1) + 29 GB (shard 2) + 23 GB (`experts.bin`) + ~6 GB
  (MTP layer) on an **NVMe SSD**. A rotational HDD is ruled out: the access pattern is random
  reads every token. Reads do not meaningfully wear an SSD; writes are a one-time download and
  pack build.

- **v0.1.30 resident low-RAM variant** (`--resident-experts`, chosen by setup when it fits;
  `--low-ram resident|mmap` forces one): at start the engine copies the experts the GPU does not
  hold from `experts.bin` into RAM, so steady-state generation reads nothing from the SSD. Upstream
  [DETAILS.md](https://github.com/Niko1221/Strata/blob/main/docs/DETAILS.md): "a 32 GB PC with a
  24 GB GPU runs Q2_0, IQ2_XS and the Coder this way (~16-18 GB of experts in RAM, the GPU holds
  the other ~18 GB)"; IQ3_XXS stays mapped on 32 GB. The engine leaves 4 GB of free RAM
  (`STRATA_RESIDENT_HEADROOM_GIB`) and falls back to the mapped mode when the copy does not fit;
  the server log reports `resident RAM: ... blob reads from the file` (0 in steady use). On ROCm
  setup keeps the copy pageable (`STRATA_RESIDENT_PIN=0`). This removes the disk-read objection
  above for Q2_0, IQ2_XS and the Coder. **Not measured** on this machine; with 31.25 GiB usable
  and ~16-18 GB of experts it is tight, so check the log line before trusting any speed.
- v0.1.30 also streams every expert from 1024-token prefill chunks (upstream: +17-28% on 1-4K
  prompts, same output). No new RX 7900 XTX generation figures were published.

v0.1.26 also batches the MTP draft layer's prompt pass (upstream: +13-19% prompts on the RX 7900
XTX, 30/30 HIP tests passed). Generation speed is unchanged.

## Alternative without Strata: plain llama.cpp

Per the ISTA-DASLab model card, standard llama.cpp also runs these GGUFs, with
`-lm mmap --lazy-mode on` keeping shard 2 memory-mapped on disk and `--n-cpu-moe` offloading
experts to the CPU (see [`SOURCES.md`](../SOURCES.md#ideas-for-future-moe-models-not-pursued-2026-09-29);
flags seen in b11146's `--help`, re-check on the pinned engine). That path fits this repository's
existing launcher with no new engine, but has no adaptive expert cache or KV streaming, so it is
expected to be slower than Strata. Unmeasured either way; if a trial happens, measure both.

Update 2026-10-30 (scouted, PR source-checked): the GPU cache for host experts, `--moe-cache-mib`, merged on
2026-10-07 ([PR #29887](https://github.com/ggml-org/llama.cpp/pull/29887)) and our b11846 has it, so the "no
adaptive expert cache" point above is outdated. Measured in that PR: Flash-Next Q4_0 RTX 4090 25.0 -> 40.7 tok/s,
RTX 5090 67.8; on AMD (R9700 32 GB, 32 GB RAM, Coder, Windows HIP) 27.6 tok/s warm but 14.2 after a 4.5K prompt.
Field: RTX 3090 Ti 15 tok/s at a 30K prompt (Unsloth discussion, not verified). Still below Strata's 32 GB figures;
early builds aborted with quantized KV on this model (PR #27742 comments, fix status not checked). Strata stays.

## Relevance to the current Qwen3.8-27B profile

None of this transfers to `qwen38-iq3s-mtp` / `262k-q8q51-mtp`:

- The k8v4 gain is an MoE expert-offload effect. The 27B is dense and fully in VRAM.
- The K 8-bit / V 4-bit idea is already applied here as KV `q8_0/q5_1`. Going to V 4-bit
  (`q8_0/q4_1`) doubles KLD over q8/q8 with peaks up to 0.63, and only frees VRAM — see
  [`measurements/kv-quality.md`](../measurements/kv-quality.md).
- The hipBLASLt table cannot be applied to llama.cpp: it is Strata's own file format
  (`STRATA_HIPBLASLT_TUNING_V1`, read by `src/prefill/gemm.cu`), not a hipBLASLt override. See
  the 2026-10-06 review below.

## Decision criterion for an on-hardware trial

The current 27B profile does **76.3 tok/s at empty context** and **33.2 / 54.7 / 22.5 tok/s
(essay/copy/code) at 240K fill** (native TILE engine, 2026-10-24; see [`STATUS.md`](../STATUS.md)); this
section was written against the b11454 numbers (68.9; 25.9 / 45.9 / 19.3). Upstream's best AMD figure for Flash-Next (55-59 tok/s,
4-9K prompts, 64 GiB RAM) is below the 27B's empty-context speed. A trial is only worth
integrating if, on this hardware, the Coder IQ1_M in low-RAM mode on NVMe:

1. sustains **more than 60 tok/s** of generation on real coding requests, and
2. holds a usable speed at long context (compare against the 27B at the same depth), and
3. passes the repository's own quality checks (`bench/longctx_quality.py`), not only upstream's
   needle tests.

Otherwise it is not worth the extra engine, disk footprint and RAM pressure.

**Revision 2026-09-30.** Criterion 1 compares against the 27B at empty context, but long agent
sessions run deep, where the 27B falls to ~20 tok/s and the KVMem candidate reaches 45.5 tok/s at
244K ([`ENGINES-EXPERIMENTS.md`](../ENGINES-EXPERIMENTS.md#kvmem-trial-round-2-and-final-round-2026-09-30-not-adopted)).
The planned trial therefore uses v0.1.30's resident variant with IQ2_XS or the Coder, confirms 0
file reads in the log, and measures generation tok/s at 128K+ fill plus `bench/longctx_quality.py`,
against both the current profile and the KVMem candidate at the same depths.

**Model choice for this machine (2026-09-30).** IQ2_XS is ruled out: shard 1 is 39.2 GB, so
~16-18 GB of experts must sit in RAM next to the engine's 4 GB headroom, ~1.7 GB of KV at 128K and
a desktop that already uses ~10 GiB, on 31.25 GiB usable; it would most likely fall back to the
mapped mode, and a trial would measure SSD reads rather than the resident variant. The Coder
IQ1_M (shard 1 29.6 GB, ~12 GB of experts in RAM) fits with margin and matches the coding-agent
workload. The pack needs ~90-100 GB on an NVMe drive (not the rotational HDD). Priority: the
KVMem agent run (T6) first; the Coder trial is plan B if T6 fails, with the bar set at more than
45 tok/s at 128K+ fill plus a `bench/longctx_quality.py` pass.

## Review 2026-10-06: v0.1.40 and the xyzzing gfx1100 fork

Desk review again, nothing measured here. Triggered by a community post for
[xyzzing/Strata v0.1.39-rocm.1](https://github.com/xyzzing/Strata/releases/tag/v0.1.39-rocm.1)
("+22.8% prefill WMMA arm, hipBLASLt table ... decode rates of above 100 t/s").

**The fork.** [xyzzing/Strata](https://github.com/xyzzing/Strata) is a GitHub fork of
Niko1221/Strata (MIT) that keeps a gfx1100 HIP line after upstream moved its HIP lead to RDNA4
(gfx1201). Its [`GFX1100.md`](https://github.com/xyzzing/Strata/blob/main/GFX1100.md) states the
work is produced by an AI engineering agent (GLM-5.3) under xyzzing's direction; the test machine
is an RX 7900 XTX, Ryzen 9 7900X, 96 GB RAM, ROCm 7.1.1 / 10.2 nightly, no power cap stated. The
release binary is "compile-validated in CI ... nothing here executed a model". Upstream merges
contributions by hand: fork PRs #755 and #786 were closed unmerged on 2026-10-06, and their
content shipped in upstream
[v0.1.40](https://github.com/Niko1221/Strata/releases/tag/v0.1.40) (gfx1100 hipBLASLt table for
100500; RDNA3 WMMA prompt attention behind `STRATA_HIP_WMMA=1`). A trial here would use upstream
v0.1.40, not the fork.

| Claim | Upstream evidence | Status |
|---|---|---|
| Decode above 100 tok/s on an RX 7900 XTX | Not found in the fork's docs, its releases or upstream docs. Highest primary figure: 88.4 tok/s ([PR #745](https://github.com/Niko1221/Strata/pull/745): warm, same ~61-token request repeated, 200 greedy tokens, 65K context, int8 KV, MTP, 96 GB RAM). Steady decode in `GFX1100.md`: 56.8-64.2 tok/s from 1K to 128K (greedy, 256 tokens, IQ3_S). The "~100 tok/s" in the v0.1.20-rocm.4 notes is prompt reading at ~500-token prompts | Not found; best primary figure 88.4 tok/s under narrow conditions |
| +22.8% prefill from the WMMA arm | [PR #786](https://github.com/Niko1221/Strata/pull/786): 128K, 5/5 pairs, 1,513.8 to 1,863.2 tok/s. Replaces an FP32 prompt-attention fallback without matrix cores; attention share of prefill drops from ~27% to ~10% | Verified (source read), 128K only |
| +82% prefill from the hipBLASLt table | Baseline was a ROCm nightly falling back to plain hipBLAS (926 tok/s); against the table-less ROCm 7.1.1 baseline (1,403 tok/s) the gain is ~+20% | Confounded baseline |

**Fit on this machine: unchanged.** The fork's numbers come from 96 GB RAM. Upstream's
`docs/AMD_HIP_PERFORMANCE.md` describes an 8 GiB RAM headroom guard for `--resident-cpu-experts`
on AMD, stricter than the 4 GiB above; with 31.25 GiB usable and ~10 GiB of desktop use this
makes the resident Coder IQ1_M plan tighter (reading, not tested). `GFX1100.md` also reports MTP
acceptance collapsing from 0.803 to 0.056 at 512K depth. The trial criterion and plan B above
stand.

**What transfers to the dense 27B on llama.cpp b11371: nothing directly.**

- hipBLASLt table: not loadable by llama.cpp (Strata's own format). In b11371,
  `ggml_cuda_should_use_mmq` (`ggml/src/ggml-cuda/mmq.cu`) sends every IQ type and Q4_K to MMQ on
  RDNA3 at any batch size; only Q2_K, IQ2_XS/IQ2_S and Q6_K use dequantize plus hipBLAS above 128
  tokens. In `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp` that is ~0.75 GiB (Q2_K 0.22, Q6_K 0.32, IQ2_XS
  0.21), about 6% of weight bytes. `ROCBLAS_USE_HIPBLASLT=1` was already noise at empty context
  ([engines.md](../measurements/engines.md)).
- WMMA prompt attention: llama.cpp already selects its MMA (WMMA) FlashAttention kernel for large
  batches on RDNA3 (`ggml/src/ggml-cuda/fattn.cu`). Strata's gain came from replacing a fallback
  llama.cpp does not have.
- k8v4 with Hadamard rotation: llama.cpp already rotates quantized K/V; V at 4 bit already lost on
  KLD ([TRIED.md](../TRIED.md)).
- `--spec-min-p 0.70`: the llama.cpp equivalent `--spec-draft-p-min` already lost
  ([TRIED.md](../TRIED.md)). `--spec 3` matches the adopted MTP n=3.
- The transferable lesson is the method: PR #786 found the gain by measuring the attention share
  of prefill time at depth. The same split has not been measured for this profile at 240K, where
  prefill runs at 380 tok/s.

## Review 2026-10-08: releases, AMD notes, and RAM budget

Desk review of upstream releases plus a local `/proc/meminfo` read. Nothing run on this machine.

**Upstream releases (Niko1221/Strata).** v0.1.40.1 (2026-10-06) narrows the tool-call rescue from
thinking; Python only. v0.1.40.2 adds Intel Arc and multi-GPU gains; its default answers are
byte-identical to v0.1.40. v0.1.40.3 fixes Intel and Windows AMD. v0.1.40.4 fixes Pascal decode.
v0.1.41 (2026-10-08, latest) targets multi-GPU, NVIDIA short prompts and Windows with low RAM. Its
release tables show no gfx1100 decode change; the one Radeon row is an R9700 with decode "equal".
Two defaults change in v0.1.41: `--batch` on a layer split runs one group per GPU, and short prompt
chunks on one NVIDIA GPU use the CPU for some experts, which changes the last bits of the output.

**AMD notes (`docs/AMD_HIP.md`, v0.1.41).** With `--resident-experts`, the start log prints how many
of the prompt path's lendable slots keep their experts in RAM (`N of M`). Uncovered experts are read
from the pack during the prompt. Reporter on an RX 7900 XTX (gfx1100, v0.1.40.2, 50 GB RAM), 74K
prompt: 2,583 tok/s with 6201 of 6201 covered; 1,810 tok/s with 5093 of 6202. The "925 to 2,503
tok/s" chain (`--resident-experts` is the 1,092 to 2,503 step) is the reporter's and is not re-measured
upstream. Status: hypothesis here.

**Fork (xyzzing/Strata).** Latest release is still v0.1.39-rocm.1 (2026-10-06); main has commits up
to 2026-10-07. `compare` against upstream v0.1.40 finds no common ancestor, so the fork is not rebased
and upstream fixes have to be ported by hand.

**RAM budget (corrected later on 2026-10-08).** Strata sizes the resident set from `MemAvailable` at
engine start minus `STRATA_RESIDENT_HEADROOM_GIB` (default 4 GiB; setup's tip is 6 GiB on PCs with 48 GB
of RAM or less): upstream `docs/AMD_HIP.md` (v0.1.41) and `setup.py` (`bench_tips`). A first draft of this
section used `MemTotal - AnonPages - Shmem` (16.0 GiB budget), which overstates it: `MemAvailable` also
excludes kernel memory and reserves. Measured 2026-10-08, desktop open, no `llama-server` running:

- `MemAvailable` 19,879,752 kB (18.96 GiB); `AnonPages` + `Shmem` 9.63 GiB, a 2.66 GiB gap to
  `MemTotal - MemAvailable`.
- Budget for experts in RAM: **14.96 GiB** at 4 GiB headroom, **12.96 GiB** at 6 GiB. It moves with
  whatever else runs (QtWebEngine alone was 3.2 GiB RSS at one check), so read it right before a start.

**RAM needed (upstream setup heuristic; computed, not measured).** The RAM copy holds the experts the GPU
cache does not. `setup.py` estimates the GPU share as VRAM - 5 GB (dense weights, buffers, 32K of KV) minus
the KV beyond 32K (13 layers x 1,056 B per token at int8; in the low-RAM mode the KV stays in VRAM). The
base is the pack's expert arena (`MODELS` in `setup.py`), not shard 1, which also holds non-expert weights;
the first draft's 18.2 GiB subtracted the GPU share from shard 1.

| Quant | Expert arena (setup, GB) | RAM need at 32K | at 128K | at 262K |
|---|---:|---:|---:|---:|
| Q2_0 | 34.0 | 14.0 GiB | 15.2 GiB | 16.9 GiB |
| IQ2_XS | 35.5 | 15.4 GiB | 16.6 GiB | 18.3 GiB |
| IQ3_XXS | 42.9 | 22.3 GiB | 23.5 GiB | 25.2 GiB |
| Coder IQ1_M | 23.4 | 4.1 GiB | 5.4 GiB | 7.0 GiB |

The table assumes Strata gets the whole 24 GB card. The desktop held 1.54 GiB of VRAM at the check and
upstream recommends `--vram-reserve-mib 3072` on a Linux desktop, which moves roughly 1.5-3 GB more into
RAM (hypothesis). Setup's own check (`ram >= rest + 10`) picks the resident variant for Q2_0 and IQ2_XS even
at 262K; the engine then falls back to the mapped mode at start when the budget is short, so only the start
log settles it.

Reading against the budget: Q2_0 fits at 32K only with 4 GiB headroom and not at 128K or deeper with the
desktop open; IQ2_XS is worse; IQ3_XXS never fits; the Coder fits at every depth with at least 5.9 GiB of
margin. This replaces the 2026-09-30 figure of "~12 GB of experts in RAM" for the Coder (taken from shard 1)
and its IQ2_XS exclusion reasoning (the conclusion for IQ2_XS stands).

**Host limits not covered by upstream's data.**

- **CPU**: Ryzen 7 5700X (Zen 3, AVX2, no AVX-512; AM4, so DDR4). Every upstream gfx1100 figure comes from
  Zen 4 AVX-512 hosts with 50-96 GB of RAM (Ryzen 9 7900X, 7950X3D). The CPU computes the experts missing
  from VRAM, so decode here can stay below upstream's 59-65 tok/s even when the model fits (hypothesis).
- **Pageable copy**: on ROCm setup writes `STRATA_RESIDENT_PIN=0` (`setup.py`), so the copy is ordinary
  anonymous memory. This machine has a 31.3 GiB zram swap at swappiness 150 (measured): under pressure the
  kernel can move resident experts to zram, which the `resident RAM: ... blob reads from the file` line does
  not count. `docs/AMD_HIP.md` also reports GPU queue stalls while the kernel reclaims host pages pinned
  through KFD userptr (one-machine reports, cause not confirmed).
- **PLE**: the n-gram table is read with `--ple-io direct` (the default, unbuffered past the OS cache,
  `docs/DETAILS.md`). It does not compete for page cache, but it reads the SSD every token by design, so
  "0 SSD reads" means 0 expert blob reads plus 0 swap-in, not zero disk I/O.
- **Quality bench**: `bench/longctx_quality.py` launches `llama-server` and uses `/tokenize`, `/completion`
  and `timings`. Strata's server exposes none of them (`/v1/chat/completions`, `/v1/messages`,
  `/v1/responses`), so a quality pass on Strata needs an adapter first.

**Trial plan (proposal, not adopted).** The comparison that matters is depth: Strata's decode is nearly flat
in context, while the 27B runs 25.9 / 45.9 / 19.3 tok/s (essay/copy/code) at 240K
([`STATUS.md`](../STATUS.md)). Model: the Coder IQ1_M, the only quant whose resident variant fits with
margin, so the trial measures the resident path and not the mapped fallback. Each step stops the trial on
failure:

1. Read `MemAvailable` and VRAM use with desktop applications closed (no download).
2. Strata v0.1.41 with the Coder: the start log shows the resident variant, `N of M` lendable slots with
   N = M, 0 blob reads per request; `pswpin` in `/proc/vmstat` does not move; no `verify: timed out`.
3. Decode on real coding requests at 4K, 128K and 240K, temperature 0: more than 60 tok/s at 4K, more than
   45 tok/s at 128K and deeper, and above the 27B's 19.3 tok/s code row at 240K.
4. Quality: adapt `bench/longctx_quality.py` to Strata's API and match the 27B's results.

## First run 2026-10-15: v0.1.44.1, Coder IQ1_M

Installed on request as a usable alternative to the 27B (procedure: [`../sop/strata.md`](../sop/strata.md)).
Evidence: [`results/20261015-strata-coder-first-run/`](../../results/20261015-strata-coder-first-run/README.md).

- **128K + KV int8 works**: short coding requests 67-78 tok/s, a ~95K-token prompt read at 844 tok/s and then
  66.7 tok/s of generation (2026-10-08 plan items 2-3: speed bar at 128K passed; 240K not reachable, see below).
- **262K + int8 fails** on 31 GiB: short requests drop to 28-41 tok/s and a ~100K prompt stalled 60 s at
  prefill (3.3 GiB in swap) until the engine restarted.
- **k8v4 is worse here, not better**: it frees KV VRAM, the GPU caches fewer experts, the RAM copy grows from
  7.75 to 10.45 GiB, and a deep prompt triggered the kernel OOM killer (desktop killed).
- RAM, not VRAM, is the limit on this machine: 13-14 GiB were available with the desktop and agent CLIs
  open. The 2026-10-08 plan's step 1 (measure with applications closed) was skipped and is what bit us.

### Next iteration (goal: the longest context that keeps quality)

1. Free RAM first (close browser/Electron apps/idle CLIs, empty `/tmp`, which is a tmpfs; `MemAvailable` ≥ 16
   GiB, ideally 20+), then re-run 128K int8 with a ~120K prompt; confirm no `stall report`, swap flat. The
   2026-10-15 restart OOM'd while idle ([`results/20261015-strata-coder-idle-oom/`](../../results/20261015-strata-coder-idle-oom/README.md)):
   the headroom sizes the copy from free RAM, so fix it with `--resident-budget-gib N` and log `GPUActive`.
   **Done 2026-10-15** ([`results/20261015-strata-coder-context-steps/`](../../results/20261015-strata-coder-context-steps/README.md)):
   128K, 200K and 262K int8 all pass the speed bar (63.4 tok/s at 257K fill, no stall, ≥9.7 GiB free); the
   first run's 262K stall is superseded (8 GiB of tmpfs files were in RAM). Retrieval (step 4's adapter,
   `bench/strata_longctx_quality.py`) 20/20 at 128K and 190K, like the 27B; 240K 4/4 when opening Slack
   crashed the desktop: with ~600 MiB VRAM free the driver pushed 10-15 GiB of GPU memory into RAM.
   Next: `./setup.sh --vram-reserve-mib 3072`, re-measure speed, finish the 240K row (documents 2-5).
   **Done 2026-10-16** ([`results/20261016-strata-coder-vram-reserve/`](../../results/20261016-strata-coder-vram-reserve/README.md)):
   ~1.4 GiB of VRAM stays free (0.6 GiB at the prefill peak) and a Slack launch costs 0.11 GiB with no
   eviction to RAM; gen 52.2-56.6 tok/s (single runs, -3% to -13%); 240K retrieval 20/20. The cost is a
   15.03 GiB RAM copy (was 12.71), so start with `MemAvailable` ≥ 21 GiB. This is the recommended Strata
   config: 262K, KV int8 (no 4-bit KV), 3 GiB VRAM reserve.
2. Step context up with RAM free: 200K (`--context 204800`, inside the trained 262K) int8, then 262K int8.
   Pass = no stall, `pswpin` flat, decode > 45 tok/s at 128K+ fill. Record `experts in RAM` and VRAM free.
3. Only if RAM allows: `--kv-streaming on` (upstream: ~1.8 GiB RAM at 128K, ~3.6 GiB at 262K) keeps the KV off
   the GPU so more experts fit in VRAM; measure it against step 2.
4. Quality gate before any wider use: adapt `bench/longctx_quality.py` to Strata's API (it is OpenAI-compatible)
   and compare with the 27B at the same depths; temperature 0, reasoning off.
5. Not tried yet: a hipBLASLt tuning table (system ROCm 7.2.4 ships no hipBLASLt; setup's TheRock wheels path
   would bring one, ~10 GB) for faster prefill. `--adapt-async 1` moved to the tuning plan below.

### Tuning plan 2026-10-16 (not run)

Config-only: flags, env vars and the run config JSON; Strata's source stays untouched so official updates apply
cleanly. Base: the 2026-10-16 config (262K, KV int8, `--vram-reserve-mib 3072`). One variable per phase; each
phase starts from the previous phase's adopted config. A candidate that misses its bar goes to
[`TRIED.md`](../TRIED.md). Paths: `<S>` = the Strata clone (`~/IA/Motores/Strata`), `<D>` = `~/IA/Motores/Strata-data`,
`<cfg>` = `<S>/strata-coder-iq1_m.json`.

**F0: refresh before running (every time this plan is picked up).** The plan outlives Strata releases, models
and quants. Before P0: `python3 scripts/strata.py status`; if upstream is ahead, `python3 scripts/strata.py
update` and record the new `describe`. Then re-check every flag and env var used below against that version's
`docs/DETAILS.md` (and `engine/strata --help`): drop a phase whose option was removed or became the default, and
note renamed ones here. If a new Qwen model or quant is the reason for picking this up, run it through
[`../sop/new-model.md`](../sop/new-model.md) (plan step C1) first; this plan then applies only if Strata stays in
use, re-based on that model's config.

**P0: preconditions (every phase).**

1. Record `git -C <S> describe --tags` and do not run `./update.sh` or `./setup.sh` until the plan ends: the bench
   filler is `<S>/src`, so an update changes the prompts, and setup can rewrite `<cfg>` args (see the SOP gotcha).
2. `cp <cfg> <cfg>.pre-<phase>` before each edit; rollback = copy it back and `qwen-flash stop && qwen-flash start`.
3. Same desktop state for every run: browser and Electron apps closed, `/tmp` under 2 GiB, `MemAvailable` ≥ 21 GiB
   (`qwen-flash start` refuses otherwise; never pass `--force` during the plan).
4. Keep each phase's tooling in its result folder, `results/<date>-strata-<phase>/`: copy
   `results/20261015-strata-coder-context-steps/strata_bench.py` there and add a RAM watcher script there (2 s
   samples: `MemAvailable`, `GPUActive`, GTT, VRAM used, zram, swap used, `pswpin`; GTT is
   `mem_info_gtt_used`, not `GPUReclaim`). Both are part of the evidence.

**F1: vendor sampling (quality, ~15 min).** Without a `sampling` block the server answers requests that send no
temperature greedily (Strata `serve/server.py:743-744`, `serve/runconfig.py:20-21`); the harness entry in the
omp `models.yml` sets none. The [Qwen3.8-Flash-Next card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) gives for
thinking mode `temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0,
repetition_penalty=1.0`; its SWE results use temperature 1.0.

1. Add to `<cfg>`: `"sampling": {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0}` (the penalties
   are the card's values already; `top_k` must be 1-64). Validate with `python3 -m json.tool <cfg>`.
2. Restart. Done when the server log shows `[strata] sampling defaults from the config: ...` with these four values.
3. Send the same prompt twice with no `temperature` field: the two answers differ (greedy would repeat them).
   Send it once with `"temperature": 0`: two such answers are identical (explicit values still win).
4. One short harness session on `local-flash-262k` ends with `finish_reason: stop` and no repetition loop.
5. Docs: install section of [`../sop/strata.md`](../sop/strata.md) (the block next to the headroom env), one
   `DECISIONS.md` row, `CHANGELOG.md`. Rollback: remove the block.

Whether omp sends its own temperature is unverified (the server log does not print request sampling); the block
is harmless either way, because a request's own values win.

**F2: adaptive expert swaps, interleaved A/B/C (speed, ~75 min).**

| Arm | Change in `<cfg>` | Bit-exact run to run |
|---|---|---|
| A | none (F1 config) | yes |
| B | `"--adapt-async", "1"` appended to `args` | no (`--help`) |
| C | `"STRATA_ADAPT_OVERLAP_RESIDENT": "1"` in `env` | yes; upstream comment: RTX A4000 +7.0%, RTX 3060 -2.6% where CPU experts and copies share RAM bandwidth (`src/program/generate.cpp:8746-8747`) |

1. Edit the phase copy of `strata_bench.py`: request `"temperature": 0` (instead of 0.6) so every arm decodes the
   same text and MTP acceptance is comparable, and print a SHA-256 of `content + reasoning_content` per request.
2. Order A B C, three times; a fresh `qwen-flash start` per run; `STRATA_DIR=<S> python3 strata_bench.py 120000
   250000` with the watcher running. Save each run's output, its engine start lines and the `expert tiers:` lines.
3. Checks per run: the start log for C says the adaptive overlap is on (A says
   `not in the resident RAM mode unless STRATA_ADAPT_OVERLAP_RESIDENT=1`); B and C exclude each other
   (`generate.cpp:8741`), so never set both; no `stall report`; `files 0 blobs`.
4. A and C must give the same SHA per request. A difference means C is not exact here: record it and judge C
   by B's rule.
5. Adopt an arm only if its median gen tok/s beats A by ≥ 5% at both ~120K and ~250K, it wins at least 2 of the 3
   A/arm pairs at each depth, there is no stall, and min `MemAvailable` stays > 5 GiB. B also needs 8/8 in
   `cd bench && python3 strata_longctx_quality.py --depths 190000 --docs 2`. If B and C both pass, take C.
6. Docs: result folder + `results/INDEX.md` row, outcome here, `DECISIONS.md` or `TRIED.md` row, SOP if adopted.

**F3: learned expert profile (cold-start speed, ~40 min, needs a real session).** Shipped profile:
`<S>/data/expert-profile-coder.bin` (the `--expert-profile` value in `<cfg>`).

1. Baseline: two fresh starts on the F2 config; on each, record short #1 and ~120K (phase bench, temperature 0)
   and the `expert tiers: GPU <N> hits` lines.
2. Add `"--expert-profile-save", "<D>/profile-coder-learned.bin"` to `args`; run at least 20 min of real
   harness coding work (the user's session). Do not train on `strata_bench.py`: it is the measurement workload,
   so the result would be circular. No real session = skip F3 and say so.
3. `qwen-flash stop` (the profile is written on quit); check the file exists and is non-empty.
4. Point `--expert-profile` at the learned file, remove `--expert-profile-save`, repeat step 1 twice.
5. Adopt if the first request is ≥ 5% faster at ~120K or the GPU hits per request rise, with no growth of the
   `experts in RAM` start line. Keep the shipped profile; after any Strata update, go back to it and re-learn
   (the pack or profile format can change). Risk: the profile is biased toward the traffic it learned from.

**F4: community-config candidates (speed, after F2; from the
[2026-10-30 review](#review-2026-10-30-a-community-windows-iq3_xxs-run-config)).** One arm per row, each an
interleaved A/arm pair on the adopted config with F2's bench, temperature 0, SHA per request:

| Arm | Change | Adopt if |
|---|---|---|
| F4a | `--spec-min-p 0.70` in `user_args` (now 0.5) | F2's speed rule (≥ 5% at ~120K and ~250K, 2 of 3 pairs, no stall); a draft-acceptance option, so text must match A or pass 8/8 retrieval at 190K |
| F4b | `--prefill auto:16384` in `user_args` (now `auto`) | Prefill tok/s ≥ 5% at ~120K with gen tok/s not below A, no stall, min `MemAvailable` > 5 GiB |
| F4c | `STRATA_PF_FUSED`, `STRATA_PREFILL_MMQ`, `STRATA_GDN_CHUNKED`, `STRATA_SPLIT_OVERLAP` = `1` in `env`, one per arm | Skip any that the start log or `DETAILS.md` shows already on by default on HIP; else F4b's rule plus the same SHA as A |
| F4d | `STRATA_RAM_ADAPT=1` in `env` with `--adapt-every` (mapped mode only: the RAM copy follows the conversation) | F2's speed rule plus a lower `blob reads from the file` count; upstream numbers are CUDA (RTX 3060), so HIP support is unverified |

Adopted values go to `models.toml` `[strata.coder-iq1_m]` and `scripts/strata.py apply`; losers to
[`TRIED.md`](../TRIED.md). Then the coding suite once on the final config (plan step C2's gate).

**Out of scope, with reason:** `--conversation-cache-mib` (costs RAM, the binding limit here); the hipBLASLt
table (needs another ROCm install, ~10 GB); `--kv-grow` (needs every expert in RAM, not the resident mode);
`STRATA_HIP_WMMA` (RDNA4 only); `--vram-reserve-later-mib` (layer-split later cards only).

## Review 2026-10-24: v0.2.4.2, the 2026-10-19 Coder and the 27B

Desk review; nothing measured yet on v0.2.4.2. Strata clone updated with `./update.sh` from v0.2.0-beta-4 to
`v0.2.4.2-6-g7dd5cf18`; Gyro-S data (81 GB) deleted at the user's choice.

**The Coder changed upstream.** ISTA-DASLab replaced shard 1 on 2026-10-19 (commits `d1d94679`, `6e7d7948`,
`bba88856`; shard 2 unchanged, sha256 `316b46f3…`). New shard 1: 29,608,446,496 bytes, LFS sha256 `bfa3644d…`.
Card: "looping is reduced and coding performance is higher, with SWE-bench Verified rising from 75.60 to
79.20 and LiveCodeBench v6 from 86.28 to 87.43" (source-checked, card text; not reproduced here).

**Setup v0.2.4.2 still pins the old shard 1** (source-checked, `setup.py` at `v0.2.4.2`): `HF_REVISIONS` pins the
Coder repo to `5348543e` (2026-09-29) and `CODER_FILES` to sha256 `e11083ba…`; the re-pin is upstream
[PR #3445](https://github.com/Niko1221/Strata/pull/3445) (open). A download gets the old shard. Files given with
`--gguf-dir` only get a whole-file check against their own tensor directory (finish mark `whole (checked against
its own tensor directory)`), so the new shard installs with an unmodified `setup.py`: verified 2026-10-24, setup
run twice (once with PR #3445 applied, once without), exit 0 both times, the mark never held the pinned SHA-256.
The new shard's SHA-256 was checked by hand against the HF LFS hash.

**The shipped expert profile is stale for the new shard** (upstream
[#3448](https://github.com/Niko1221/Strata/issues/3448), open; reporter-measured on an RTX 4070): the re-indexed
experts leave 2 of 12,288 profile pairs pointing at the same expert. The profile is only a tie-breaker after the
learned heat, and a rebuilt profile measured the same (43.6 vs. 44.8 tok/s, inside ±5%). Hypothesis here; the
tuning plan's F3 (learned profile) covers it.

**Run config keeps hand-set options** (source-checked, `strata_control/user_args.py`): `"user_args"` in
`strata-<model>.json` is re-applied on top of setup's generated `"args"` by every setup run and start, so
settings no longer get lost on `./update.sh` (the 2026-10-16 SOP gotcha). `serve/runconfig.py` also accepts a
`"sampling"` block (temperature, top_p, top_k 1-64, min_p) used for requests that send none.

**Coder vs. the 27B (vendor numbers, not measured here).** Qwen's
[Flash-Next card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) compares the full model with the 27B:

| Benchmark | Flash-Next (full) | Qwen3.8-27B |
|---|---|---|
| SWE-bench Pro | 62.5 | 61.7 |
| DeepSWE 1.1 | 58.7 | 42.2 |
| SWE-bench Multilingual | 81.0 | 73.8 |
| NL2Repo-Bench | 48.1 | 42.3 |
| LiveCodeBench v6 | 91.9 | 90.3 |
| GPQA Diamond | 91.7 | 89.2 |

The Coder keeps 256 of 512 experts, chosen on code data; ISTA reports 95.7% of BF16 on SWE-bench Verified
(79.20 vs. 82.80) and 100% on LiveCodeBench v6, at xhigh effort. Its BF16 LiveCodeBench (87.43) differs from
Qwen's 91.9, so the two tables use different setups and do not combine exactly. Applying 95.7% to SWE-bench Pro
gives ~60, level with the 27B (inference, not a measurement). Upstream Strata and ISTA both say the Coder is
weaker outside code and in languages other than English.

Speed is the measured difference (older engine and shard: [first run](#first-run-2026-10-15-v01441-coder-iq1_m)):
52-57 tok/s at every depth to 262K vs. the 27B's 22.5-33.2 at 240K; at empty context both are ~70-78 tok/s.
Coding quality on this machine is open until the coding suite runs on both (plan step B2).


**Installed 2026-10-24** (procedure: [`../sop/strata.md`](../sop/strata.md); settings: `[strata.coder-iq1_m]` in
`models.toml`). Setup recompiled the engine for gfx1100 and built the pack from the new shard (`experts.bin`
23.42 GiB). First start: ready in 33-39 s, `resident RAM mode: 15.06 GiB of experts in RAM`, expert cache 6,184
slots (11.76 GiB of VRAM), 3,014 MiB of VRAM free with everything loaded, adaptive overlap off (the default in
the resident mode). Smoke: two short coding requests ended `finish_reason: stop`; without a request temperature
they gave different text, so the tracked `sampling` block is in use. Speed, retrieval and the coding suite were
**not** measured on this version: the tuning plan's F2 A/B/C was stopped in its first run (user needed the GPU),
no numbers. Next: F2, then 240K retrieval, then the coding suite (plan step B2).

## Review 2026-10-30: a community Windows IQ3_XXS run config

Desk review of a Strata run config (Windows, IQ3_XXS, 1 GPU, 256K) a user shared, against this setup; nothing
run. Local clone `v0.2.4.2-6-g7dd5cf18`, upstream `v0.2.8` (727 commits ahead, `scripts/strata.py status`).
Every flag and `STRATA_*` variable in it exists in both versions (`git grep`, code outside `*.md`); whether their
meaning changed between the two was not checked.

**Not transferable:**

- **IQ3_XXS with `--mmap-experts --resident-budget-gib 22`**: upstream `DETAILS.md` says IQ3_XXS stays mapped
  on 32 GB, and the budget leaves 4 GiB of headroom on top; 31.25 GiB usable here (see the RAM-budget review).
- **`--kv k8v4`, `--vram-reserve-mib 1400`**: both already lost here (2026-10-15 OOM kill; 2026-10-16 reserve
  3072 after a Slack launch ended the KDE session; [`DECISIONS.md`](../DECISIONS.md)).
- **`--control-vector-scaled ...experimental-speed-projection.gguf:1.0`** (layers 4-44, `--cvec-mode project`):
  not a speed option. Upstream's own result (`bench/results/2026-09-27-esp/README.md`, source-checked) calls it
  a refusal-direction projection; on the same tokens it is 0.2-0.4% slower, code perplexity 2.594 -> 2.982,
  same top-1 92.8% on code. Its faster served tok/s came from different (more copied) text. Rejected for coding.
- **`--vision` with an elastic encoder**: per `DETAILS.md` the elastic encoder turns `--kv-grow` off, so the
  config contradicts itself; vision is unused here.
- **`HIP_PATH`/`ROCM_PATH` probe paths, `lib_dirs`, a Windows `STRATA_HIPBLASLT_TUNING` file**: Windows-only.
- **`--kv-grow`, `STRATA_HIP_WMMA`, the hipBLASLt table**: already out of scope in the
  [tuning plan](#tuning-plan-2026-10-16-not-run).

**Candidates, queued as the tuning plan's F4** (after F2): `--spec-min-p 0.70` (here 0.5), `--prefill
auto:16384` (here `auto`), and the env switches `STRATA_PF_FUSED`, `STRATA_PREFILL_MMQ`, `STRATA_GDN_CHUNKED`,
`STRATA_SPLIT_OVERLAP` (unverified whether Linux setup already sets them by default). `--adapt-async 1` is
already F2's arm B. Status: open.

## Fit check 2026-10-30: IQ2_XS and IQ3_XXS without SSD reads

Question: can either full-expert size keep every expert in VRAM or RAM, so no expert is read from the SSD (the
shard-2 lookup table is always read from the SSD, a few rows per token)? Arithmetic only, nothing run.

**Measured inputs** (Coder start log, 2026-10-24, 262K, KV int8, `--vram-reserve-mib 3072`): `23.4 GiB experts,
11.8 GiB in the GPU caches, 15.1 GiB RAM copy (1793 lend slots kept), file tier 0.0 GiB`; the prompt path borrows
1793 GPU slots (3.40 GiB), whose experts must also sit in RAM, so RAM copy = experts - GPU cache + lend
(23.42 - 11.76 + 3.40 = 15.06, matches). Memory guard at start with a cleaned desktop: 6.9 GiB in use,
`MemAvailable` 24.3 GiB; Strata keeps `STRATA_RESIDENT_HEADROOM_GIB` free (default 4, here 6).

**Expert sizes**: upstream `MODELS.md` "Experts in shard 1" (IQ2_XS 35.5, IQ3_XXS 43, Coder 23) as the upper
bound; shard 1 size minus the Coder's non-expert part (27.58 - 23.42 = 4.16 GiB) as the lower bound (HF sizes:
IQ2_XS 39.23 GB, IQ3_XXS 47.04 GB). Assumes the same VRAM budget for the expert cache as the Coder.

| Size | Experts (GiB) | RAM copy for zero file reads (GiB) | RAM copy that fits (24.3 - 4 headroom) | Read from the SSD |
|---|---:|---:|---:|---:|
| IQ2_XS | 32.4-35.5 | 24.0-27.1 | 20.3 | ~3.7-6.8 GiB |
| IQ3_XXS | 39.7-43.0 | 31.3-34.6 | 20.3 | ~11-14 GiB |

- **IQ3_XXS**: no. Its RAM copy alone is as large as the whole 31.25 GiB of RAM.
- **IQ2_XS**: no, by a few GiB. Levers and their limits: `--vram-reserve-mib 1400` gives ~1.6 GiB more GPU cache
  (the 3072 reserve exists because a Slack launch ended the KDE session); headroom 0.1 GiB (the community config's
  value) gives ~4 GiB, against the 2026-10-15 OOM kill of the desktop. Both together reach the low end only with
  an empty desktop. Not safe as a daily setup.
- Upstream supports this mapped mode for IQ2_XS on 32 GB + 24 GB GPU (`MODELS.md`), not for IQ3_XXS.
- Check on the first start: the `prefill plan inputs` line's `file tier` is the measured SSD share, and
  `resident RAM: ... blob reads from the file` counts reads per request.

Disk after deleting the Coder: 90 GiB free on `/home` at first, 106 GiB minutes later (btrfs released the space
late), 114 GiB after removing old engines, sources and caches (2026-10-30). IQ2_XS needs ~67 GiB (shard 1 36.5 +
pack ~31, pack estimated at the Coder's 85% of shard 1); IQ3_XXS ~81 GiB.

**Field evidence (scouted and source-checked 2026-10-30): SSD reads cost less than feared.**

- Upstream `DETAILS.md` (0.2.1 row, #3060; author-measured, not reproduced here): RTX 3060 12 GB, 32 GB RAM,
  Linux NVMe, 20.5 GiB of experts in RAM, both sizes read in place, 120 ShareGPT requests: IQ2_XS decode 48.71 ->
  51.40 tok/s, IQ3_XXS 33.07 -> 38.71 tok/s, without -> with `STRATA_RAM_ADAPT`; storage reads 408 -> 308 GB
  (IQ2_XS) and 1105 -> 717 GB (IQ3_XXS). A 24 GB card holds about twice the GPU experts, so both should read less
  from the SSD here (inference).
- `bench/results/2026-10-08-community-rtx4070-iq2-xs`: RTX 4070 12 GB, 32 GB DDR4, IQ2_XS, 20 GiB RAM copy,
  ~48 accepted tok/s at a 28,912-token prompt (modified engine, Windows).
- [#4167](https://github.com/Niko1221/Strata/issues/4167) (field, not a controlled A/B): RTX 5090, UD-IQ4_XS with
  parallel slots, 4.7 GiB file tier decoded 19-39 tok/s against 100-144 at 0.6 GiB. Keep `--parallel 1`.
- No RX 7900 XTX run on 32 GB RAM in mapped mode was found.
- SSD wear is not a cost of the mapped mode: decoding only reads the expert files, and swap here is zram (no disk
  swap). Writes happen once per install (~91 GB for IQ3_XXS: shard 1 47 + `experts.bin` ~44), about 0.03% of the
  `/home` drive's rating (Kingston A2000 500 GB, 350 TBW per
  [Kingston](https://www.kingston.com/en/company/press/article/56606)). The cost is speed: upstream's 32 GB run
  read 6-9 GB per request with IQ3_XXS against 2.5-3.5 GB with IQ2_XS. Sustained reads may heat the drive and
  slow it (no heatsink; not measured). Current wear: `sudo smartctl -a /dev/nvme1n1`, "Percentage Used".
- Quality: no SWE-bench, LiveCodeBench or HumanEval number exists for any full-expert size; upstream `GYRO.md`
  puts Gyro-M "against IQ3_XXS | KL 0.157, level". The Coder keeps half the experts "stored at 3.5 bpw" (ISTA card).
- v0.2.8 notes change nothing for the mapped mode (only the expert-cache reserve fix #4474 and a 16-row HIP batch
  window). gfx1100 risks: [#4556](https://github.com/Niko1221/Strata/issues/4556) (IQ3_S decode 60+ tok/s on
  0.1.3x vs. 34.8 on the 0.1.48 default engine; maintainer: "on our list for the next update") and
  [#3463](https://github.com/Niko1221/Strata/issues/3463) (machine restarts while serving; the reporter's fix is a
  ≤ 2000 MHz clock cap). Compare engine versions before blaming a model.

Effect: IQ3_XXS is a real candidate despite the SSD share; IQ2_XS is the one Strata's check keeps out of the SSD
(below). **Chosen 2026-10-30 (user): IQ2_XS next, not started yet**; IQ3_XXS stays the later quality option.

**Install plan for IQ2_XS (not started):**

1. Copy `<S>/engine/` aside (`scripts/strata.py update` backs up only configs), then `python3 scripts/strata.py
   update` to the current upstream; re-run `./setup.sh --check --backend hip` and re-check the F0 flag list.
2. Download shard 1 (39.23 GB, LFS sha256 `92cee27a…`) yourself, check the hash, and pass its folder plus the existing
   shard 2 with `--gguf-dir` (as for the Coder in [`../sop/strata.md`](../sop/strata.md)); `--vision no`; keep
   262K, KV int8, `--vram-reserve-mib 3072` and `STRATA_RESIDENT_HEADROOM_GIB` from `models.toml`.
3. First start, from the log: `file tier` (0 GiB = no SSD reads), `resident RAM: ... blob reads from the file`,
   `VRAM free with everything loaded` ≥ 3 GiB (the dense part differs from the Coder's), min `MemAvailable`.
   Also confirm `tool_call_recovery` is on (default from v0.2.8; upstream: 98.3% of 1,462 agent turns read as
   intended with it, 92.9% without) and count valid tool calls in the first real harness session: the worst
   report, [#2685](https://github.com/Niko1221/Strata/issues/2685) (IQ3_S, pre-0.2.8), completed 0/10 tasks.
4. Short-context smoke and decode, then speed at ~120K/~240K, 240K retrieval, the coding suite as a regression gate
   (six tasks cannot rank quants finely; Astra review 2026-10-30). If decode disappoints, A/B the saved engine
   against the new one on the same model before blaming the quant (#4556).
5. Then a `[strata.iq2_xs]` entry in `models.toml`, the tuning plan's F2/F4 re-based on it, and the docs
   (`DECISIONS.md`, STATUS, README, CHANGELOG).

Qwen4 (C1) pre-empts this plan if it ships: officially "in training" with no date (Alibaba, 2026-09-22, page not
opened); a "next week" date from 2026-10-29 is an unconfirmed attendee report.

**Strata's own check on this PC** (`./setup.sh --check --backend hip`, v0.2.4.2, 2026-10-30, read-only): IQ2_XS
"fits in the low-RAM mode (the GPU holds ~51% of its experts, the rest stays in RAM)"; IQ3_XXS "(the GPU holds
~42% ..., the rest is read from the SSD as needed)"; Gyro-M ~56% and Q2_0 ~53%, rest in RAM; IQ3_S does not fit.
Its GPU share is larger than the Coder's measured 11.8 GiB cache at 262K + 3 GiB reserve would give, so the arithmetic
above is the conservative bound; the first start's `file tier` settles it. Disk by `setup.py`'s own rule (missing
files + `experts.bin` of `arena_gb` + 1 + margin 2; shard 2 already present, `--vision no`): IQ3_XXS ~93 GB,
IQ2_XS ~78 GB, against ~96 GB free. `strata launch --plan` printed no RAM or disk figures and counts shard 2 again.

## IQ2_XS on v0.2.8 (2026-10-30)

Measured on this machine; raw data and commands:
[`results/20261030-strata-iq2xs-baseline/`](../../results/20261030-strata-iq2xs-baseline/).

- **Install**: shard 1 at ISTA revision `ed59f920` (sha256 `92cee27a…`, verified), shard 2 hardlinked from the Coder
  folder (identical file). `experts.bin` 33.02 GiB; `/home` was left with 14 GB free.
- **Fit**: setup's arithmetic picked the resident mode, but the engine found the 20.67 GiB complement did not fit
  and copied 18.53 GiB (GPU cache 9224 slots, 12.35 GiB; 2.1 GiB file tier; 0 of 2823 lent prompt slots
  covered). Setup does not subtract `--vram-reserve-mib` when it sizes the low-RAM mode (`setup.py:9576`,
  source-checked).
- **Stability**: a 121,709-token cold prompt failed with the automatic copy (stalled at 56,320 tokens, 8.6 GiB
  of the engine in zram), with `--resident-budget-gib 14` (stalled at 18,432, watchdog exit -6) and in mapped mode
  (stalled at 24,576, server silence kill). The cause is ROCclr's userptr lock on pageable copy sources
  (SOP, `GPU_PINNED_MIN_XFER_SIZE`). With it, mapped mode read the prompt at 672 tok/s.
- **v0.2.8 changes that matter here** (release notes, source-checked): `tool_call_recovery` on by default (a smoke
  tool call returned a valid `tool_calls`); HIP batch window 16 rows; expert-cache reserve fix #4474. gfx1100 has no
  architecture defaults (`src/core/arch_defaults.cpp`), so `STRATA_PF_GEMM`, `STRATA_PF_FUSED` and the hipBLASLt
  table (`STRATA_HIPBLASLT_TABLE`, auto only on gfx1151) are opt-in; `--prefill auto` never picks a chunk above
  8192 (#4683, open). T=0 text is not reproducible on this engine (#4673, open), so SHA equality is not a test.
- **UI**: no install. The server already serves a chat page at `http://127.0.0.1:8080/` and the checkout's CLI
  offers `strata monitor`. The desktop AppImage (v0.2.8) uses its own engine and model folders and binds only
  127.0.0.1 (repo read, not run), so it would duplicate ~70 GB and add RAM use on a RAM-bound machine.

## Quality gates 2026-10-30/31

Same config as above (`[strata.iq2_xs]` at `91565a6`); commands, raw data and per-task table:
[`results/20261030-strata-iq2xs-quality/`](../../results/20261030-strata-iq2xs-quality/README.md).

- **Coding suite: regression.** Seed 1: 4/6 (27B 6/6). The rule's reruns (seeds 2 and 3 of the failed tasks, both
  arms): CS3 1/3 against 3/3, CS5 2/3 against 3/3; `--compare` says "candidate rejected (regression)". In 11 of its
  responses IQ2_XS wrote a call to a tool that does not exist (`run_file`, once `read_path`) as raw `<tool_call>`
  text; v0.2.8's `tool_call_recovery` mapped 7 of them to some existing tool (`run_file` -> `run_tests`), and the
  other 4 came back as plain text with `finish_reason: stop`, which ends the episode: all three failures. No
  loops, no stall. When it called real tools, it solved the tasks.
- **Retrieval at 240K**: 12/12 exact on 3 of 5 documents (run stopped at the user's time limit; 2 documents pending).
- **Cold 240K reads in this test took 6-25 min** (370, 809 and 1,488 s for the first three documents) against
  26 min for the bench's 245,002-token C-source prompt: the expert set a prompt routes to, and so how much of it
  streams from `experts.bin`, depends on the text (inference from the spread, not isolated).
- **`STRATA_RAM_ADAPT`** moves experts in and out of the resident RAM copy; both code paths require that copy
  (`src.complement_ready()`, `src/program/generate.cpp` lines 16588 and 16661), so in mapped mode it does nothing.
  Test it only together with the resident mode. Source-checked, not run.
- Not run in this session (user's time limit): the speed arms and `--calibrate`. The sysctl candidate was not
  applied, so its before/after check is pending too.