# Qwen3.8-Flash-Next via Strata: evaluation note (2026-09-29, reviewed again 2026-10-06 and 2026-10-08)

**Status (2026-10-15): installed as an optional second engine, not the default; quality not measured.** First
run and setup below ([first run](#first-run-2026-10-15-v01441-coder-iq1_m)). Before that: a desk review of upstream claims against
upstream's own docs and code, to decide whether an on-hardware trial is worth it. Nothing in
`models.toml` changes.

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

The current 27B profile already does **68.9 tok/s at empty context** and **25.9 / 45.9 / 19.3 tok/s
(essay/copy/code) at 240K fill** (b11454; see [`STATUS.md`](../STATUS.md)). Upstream's best AMD figure for Flash-Next (55-59 tok/s,
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

**Out of scope, with reason:** `--conversation-cache-mib` (costs RAM, the binding limit here); the hipBLASLt
table (needs another ROCm install, ~10 GB); `--kv-grow` (needs every expert in RAM, not the resident mode);
`STRATA_HIP_WMMA` (RDNA4 only); `--vram-reserve-later-mib` (layer-split later cards only).
