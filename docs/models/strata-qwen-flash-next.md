# Qwen3.8-Flash-Next via Strata

Flash-Next runs on one 24 GB card with Strata: the MoE experts are streamed from host RAM and SSD, and upstream
publishes many quants (including pruned coding variants) plus its own recommended settings. This doc is the record
of what we measured on one 32 GiB host, where the experts did not all fit RAM: our last two sets read them from the
SSD and decoded 2.6-12.8 tok/s, below the 15 tok/s floor, so the numbers below mostly measure that limit rather than
the engine. The one set that did fit host RAM (ISTA IQ2_XS on v0.2.8) reached 59-65 tok/s warm short but failed the
coding suite. For a new attempt start from [Strata](https://github.com/Niko1221/Strata): its latest release, quant
list and recommended settings.

## Current state (2026-11-05)

- **Tuning guide**: how Strata places experts on this card and which switches matter (gfx1100 defaults vs. a tuned
  7900 XTX at 87-100 tok/s): [`strata-tuning-gfx1100.md`](strata-tuning-gfx1100.md).
- **Role**: optional second engine on `:8080`, never the default; one of the repository's focus models with
  the 27B and Qwen4 ([`DECISIONS.md`](../DECISIONS.md), 2026-10-29).
- **Installed but rejected on speed (2026-11-22): the abliterated SC117 IQ2_XS set on v0.2.19 + engine 0.1.65.**
  Clone at **v0.2.19** (`c6f6427d9`), engine **0.1.65** built from the checkout, pack and `experts.bin` (35.45 GB) on
  the NVMe, no `[strata.*]` table, run config left in `~/IA/Motores/Strata/terminal/strata-iq2_xs.json`. Measured
  **5.8-12.8 tok/s decode** (short requests), **324.2 tok/s prefill and 12.8 tok/s decode at a 69.7K fill** — below
  the 15 tok/s floor and 5-10x under the 2026-10-30 v0.2.8 short decode. Storage-bound, not kernel-bound:
  `0.0 GiB RAM copy`, file tier 20.3 GiB against a 14.8-18.7 GiB page cache, `page cache held 0.0 MB`, 39-191 GB read
  per request, and `drive 0.15 GB/s` because the `--native` shard is on the rotational HDD
  ([section](#2026-11-22-sc117-on-v0219-measured-below-the-floor),
  [results](../../results/20261122-strata-0219-sc117/README.md)). Procedure: [`../sop/strata.md`](../sop/strata.md).
- **Last trial (2026-11-05)**: Unsloth UD-IQ2_XS rejected for speed — short decode 2.6-8.2 tok/s, 7.1-10.8 with
  the squeeze arm (131K context, 14 GiB RAM copy), against the user's 15 tok/s floor, with a file tier of 20.2 GiB (base) /
  11.5 GiB (squeeze) that the page cache could not hold: the OS read 24-51 GB (base) / 25-28 GB (squeeze) from the
  drive per request
  ([trial](#unsloth-ud-iq2_xs-on-v0211-2026-11-05),
  [results](../../results/20261105-strata-unsloth-ud-iq2xs/README.md)).
- **Last faster Strata set** (ISTA IQ2_XS on v0.2.8, measured 2026-10-30, deleted 2026-11-05): 59-65 tok/s warm
  short, 43-45 at ~120K, 36.7 at 240K, 128K retrieval 8/8, but the coding suite failed against the 27B
  ([IQ2_XS on v0.2.8](#iq2_xs-on-v028-2026-10-30), [quality gates](#quality-gates-2026-10-3031)).
- **Check first for any future model on this PC**: the experts *off* the GPU must fit the host room. Both numbers
  are in the start log's `prefill plan inputs` line (`N GiB experts, M GiB in the GPU caches, K GiB RAM copy ...,
  file tier F GiB; P GiB available for the page cache`). F is capacity, not traffic: when F is larger than P the
  page cache cannot hold the file tier and requests read from the drive (here 24-51 GB per request; the `file tier
  I/O this request` line has the measured bytes). Here 39.4 GiB of experts against an 11-14 GiB GPU cache left F at
  20.2 GiB against P 12.5 GiB, and warm decode at 8.2 tok/s.
- **Unsloth sets share tables**: each Unsloth Dynamic set's last shard is the same 28.8 GB n-gram/PLE table
  (UD-IQ2_XS shard 3, sha256 `05716382…`; UD-IQ1_M and UD-Q2_0 identical), so only a set's own shards download.
- **Limit on this machine**: RAM (31.25 GiB usable), not VRAM.
- **Best known setup (2026-11-07, not installed)**: ISTA IQ2_XS (GSQ-RCO, ~68 GB + ~6 GB MTP layer) on Strata v0.2.12
  or newer, with the 2026-10-30 run config (mapped mode, 262K, KV int8, `--vram-reserve-mib 3072`, `--prefill auto`,
  `GPU_PINNED_MIN_XFER_SIZE=1048576`; [IQ2_XS on v0.2.8](#iq2_xs-on-v028-2026-10-30)) plus `undeclared_tool_calls:
  "call"` and `--ram-keep-gib` when a browser stays open. It is the only Flash-Next set measured fast here (59-65 tok/s
  warm short, 36.7 at 240K). Its open question is the coding suite on v0.2.12, where the tool-call parser fixes may
  change the 2026-10-31 failure. Retest with Qwen4, new quants or a new Strata version
  ([switches](strata-tuning-gfx1100.md#other-switches-worth-an-arm)).
- **Zero SSD expert reads (2026-11-20)**: only resident mode avoids them; it stalled here on v0.2.8 and on another
  RX 7900 XTX + 32 GB on v0.2.9, and it is proven with 32 GB only on CUDA. Retest arm, not run:
  [review 2026-11-20](#review-2026-11-20-resident-mode-on-32-gb-ram-v0217).
- **v0.2.19's RDNA3 claims are unmeasured here (2026-11-22)**: the run that reached the server was storage-bound
  (dense shard on an HDD, nothing resident, 39-191 GB read per request), so it says nothing about 0.1.65's claimed
  1.44-2.10x prefill / +17-22% decode. A fair A/B needs the dense shard on the NVMe and the file tier inside the page
  cache. The Arch `libamdhip64` is now applied through the run config's `lib_dirs`
  ([section](#2026-11-22-sc117-on-v0219-measured-below-the-floor)).
- **Agent quality floor (2026-11-07)**: 2-bit sets fit this machine, but no 2-bit set has an agentic evaluation and the
  field evidence puts the floor for agents at IQ3_S, which does not fit 32 GB without SSD reads
  ([sources](../SOURCES-community.md#flash-next-low-bit-quants-for-agents-2026-11-07)).

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
  Later evidence: resident stalled here on v0.2.8 ([IQ2_XS on v0.2.8](#iq2_xs-on-v028-2026-10-30)), and the quoted
  sentence is no longer in `DETAILS.md` ([review 2026-11-20](#review-2026-11-20-resident-mode-on-32-gb-ram-v0217)).
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

## History

Dated sections from 2026-09-29 to 2026-11-05 (the desk reviews, the Coder runs, the IQ2_XS install and the
Unsloth trial) are frozen in [`archive/strata-2026.md`](../archive/strata-2026.md). Each heading below is a pointer
to its section there, so the anchors other docs use keep resolving ([STYLE §8](../STYLE.md#8-documentation-workflow));
the 2026-11-14, 11-20 and 11-22 reviews after this block are still live.

### Current state (2026-10-30)

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#current-state-2026-10-30).

### Parked state (2026-10-21, ended 2026-10-24)

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#parked-state-2026-10-21-ended-2026-10-24).

### Review 2026-10-06: v0.1.40 and the xyzzing gfx1100 fork

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#review-2026-10-06-v0140-and-the-xyzzing-gfx1100-fork).

### Review 2026-10-08: releases, AMD notes, and RAM budget

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#review-2026-10-08-releases-amd-notes-and-ram-budget).

### First run 2026-10-15: v0.1.44.1, Coder IQ1_M

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#first-run-2026-10-15-v01441-coder-iq1_m).

### Next iteration (goal: the longest context that keeps quality)

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#next-iteration-goal-the-longest-context-that-keeps-quality).

### Tuning plan 2026-10-16 (not run)

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#tuning-plan-2026-10-16-not-run).

### Review 2026-10-24: v0.2.4.2, the 2026-10-19 Coder and the 27B

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#review-2026-10-24-v0242-the-2026-10-19-coder-and-the-27b).

### Review 2026-10-30: a community Windows IQ3_XXS run config

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#review-2026-10-30-a-community-windows-iq3_xxs-run-config).

### Fit check 2026-10-30: IQ2_XS and IQ3_XXS without SSD reads

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#fit-check-2026-10-30-iq2_xs-and-iq3_xxs-without-ssd-reads).

### IQ2_XS on v0.2.8 (2026-10-30)

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#iq2_xs-on-v028-2026-10-30).

### Quality gates 2026-10-30/31

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#quality-gates-2026-10-3031).

### Review 2026-10-31: the xyzzing gfx1100 fork's `refresh-0145` branch

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#review-2026-10-31-the-xyzzing-gfx1100-forks-refresh-0145-branch).

### Unsloth UD-IQ2_XS on v0.2.11 (2026-11-05)

Moved to [`archive/strata-2026.md`](../archive/strata-2026.md#unsloth-ud-iq2_xs-on-v0211-2026-11-05).

## Review 2026-11-14: abliterated Flash-Next GGUFs (control vector vs. weight transplant)

Desk review of two community abliterated builds of the ISTA GSQ-RCO set; cards read 2026-11-14 via the Hugging
Face API and README (`source-checked`), nothing run here. alesha-pro, `lastModified` 2026-10-04,
SC117 at revision `90a3350c`, 2026-10-24.

| | [alesha-pro](https://huggingface.co/alesha-pro/Qwen3.8-Flash-Next-abliterated-GSQ-RCO-Strata-GGUF) | [SC117](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF) |
|---|---|---|
| Weights | Q2_0, IQ2_XS, IQ3_XXS and IQ3_S copied byte for byte from ISTA `ed59f920` (card's `SHA256SUMS`, not re-hashed here) | 144 residual-writing tensors transplanted from the OrcaRouter uncensored set; the other 1,079 byte-identical (per-tensor blake2b) |
| Abliteration | 480 KB refusal direction from Huihui, applied at run time over layers 4-44 (`--control-vector-scaled <path>:1.0 --cvec-mode project --cvec-dir per-layer`) | Written into the weights |
| Engines | Strata only: stock llama.cpp `--control-vector` adds instead of projecting, so the files behave as the original model | Stock llama.cpp and Strata |
| Shard 1 (GB) | ISTA's, unchanged (the vector is a separate file) | IQ2_XS 39.67, IQ3_XXS 47.34, IQ3_S 55.06, Q2_0 38.02 (+0.25-0.44 vs. upstream); shard 2 (28.8 GB table) byte-identical across tiers |
| Evidence | Author, one RTX 3090, Strata 0.1.38, 10 refusal prompts: 0/10 refusals on IQ3_S and IQ2_XS (original 9-10/10); KL to BF16 Huihui 0.0738 / 0.1923, top-1 93% / 87%; 59 / 87 tok/s at a 32K prompt. Q2_0 and IQ3_XXS not run | A single-prompt spot check |
| License | "other" = Qwen Community License 1.0 | Claims apache-2.0 over a Qwen Community License 1.0 base (discrepancy) |

Conclusion: the alesha-pro route keeps the ISTA weights untouched but works only inside Strata; SC117 is
engine-independent but carries weaker evidence (~4.12M downloads and ~1k likes are the user's listing, not re-read
here). Neither has run on the RX 7900 XTX: no Strata set is installed here since 2026-11-05
([`STATUS.md`](../STATUS.md)), and per the
[2026-10-30 fit check](#fit-check-2026-10-30-iq2_xs-and-iq3_xxs-without-ssd-reads) only IQ2_XS comes close.
Status: open, not locally tested.

## Review 2026-11-20: resident mode on 32 GB RAM (v0.2.17)

Question: can ISTA IQ2_XS run on this PC with no expert read from the SSD (the shard-2 table is always read, a few
rows per token)? Only resident mode (`--resident-experts`, or `--resident-cpu-experts`) does that; mapped mode, the
2026-10-30 config, reads cold experts from the file. Desk review, nothing run.

| Evidence | Status | What it says |
|---|---|---|
| [PR #834](https://github.com/Niko1221/Strata/pull/834), RTX 4090 + 32 GB, IQ2_XS, engine 0.1.39, 2026-10-04 | source-checked | `--resident-experts` up to a 476,820-token prompt, 122.0 tok/s decode; "with the default resident headroom, 0.1.39 left 1.41 GiB `MemAvailable` at 477K. `STRATA_RESIDENT_HEADROOM_GIB=6` left 3.53 GiB". CUDA with a page-locked copy; says nothing about ROCm |
| [#4849](https://github.com/Niko1221/Strata/issues/4849), RX 7900 XTX + 32 GB, CachyOS, Q2_0, v0.2.9 (engine 0.1.55), headroom 4, `STRATA_RESIDENT_PIN=0`, 2026-10-31 | source-checked | Automatic resident "stalled on two independent starts" on 22-38K prompts with multi-GiB process swap (resident copy 16.6-17.5 GiB); a local patch plus `STRATA_FILE_CACHE_OLD_RULE=1` passed 24/24, "not proof that all ROCm stalls have the same cause" |
| [#467](https://github.com/Niko1221/Strata/issues/467), gfx1100 + 32 GB, 2026-10-02 | unverified (scout) | Setup's resident mode never engaged and fell back to mmap ("resident complement 16.20 GiB exceeds available RAM") |
| Strata `main` at v0.2.17 (released 2026-11-20, engine 0.1.63) | unverified (scout read the source, not re-checked) | The 32 GB sentence quoted [above](#fit-on-a-24-gb-rx-7900-xtx-with-32-gib-ram-3125-gib-usable) left `docs/DETAILS.md` (it survives in a 2026-10-06 bench fixture); `docs/MODELS.md` now places 32 GB + 24 GB under the mapped mode. Since v0.2.12 the engine's automatic RAM copy honours `STRATA_RESIDENT_PIN=0` (it was page-locked whatever the variable said), a new guard targets a 30 GB `--resident-experts` stall on 38-47K prompts, setup suggests headroom 6 on PCs with 48 GB or less, and `docs/AMD_HIP_PERFORMANCE.md` recommends the pageable `--resident-cpu-experts` on HIP |
| Tool-call recovery in v0.2.12 (`undeclared_tool_calls`) and more in v0.2.16 | user-stated | Justifies rerunning the coding suite; it does not guarantee a pass, since the 2026-10-31 failure was the model inventing `run_file` |

Conclusion: with 32 GB, zero SSD expert reads are proven only on CUDA, with headroom tuned; on this card resident
failed here (v0.2.8, 120K) and in #4849 (v0.2.9, 22-38K), and no AMD report shows it above 100K. The fixes since
v0.2.12 make a retest reasonable. RAM is the constraint: an ~17.3-18.5 GiB copy + 6 GiB headroom + a ~10 GiB desktop
exceeds 31.25 GiB usable, so the arm needs a lean desktop or a smaller context (in Strata a smaller KV leaves more VRAM
to the expert cache, so less goes to RAM).

Retest arm (not run): v0.2.17 + ISTA IQ2_XS, resident pageable (`STRATA_RESIDENT_PIN=0`),
`STRATA_RESIDENT_HEADROOM_GIB=6`, the 2026-10-30 prompts (22K, 38K, 120K); pass = `blob reads from the file` 0, no
stall, no multi-GiB swap; then the coding suite against the 27B. Mapped mode stays the fallback. Status: open.

Field reports from the same window, relevant to that arm (titles and quotes read by a research subagent; #6429 state
and title source-checked 2026-11-20):

- [#6392](https://github.com/Niko1221/Strata/issues/6392), RX 7900 XTX + 32 GB, Linux HIP, IQ2_XS low-RAM, engines
  0.1.62 and 0.1.63: the engine hangs within 4-10 min of sustained serving; "the graphics driver paused the GPU for
  100-3,000 ms ... while Linux moved memory the GPU uses"; setup defaults left 10 GB in swap. Healthy speed 72-83
  tok/s decode. This is this PC's configuration: the retest arm must serve for more than 10 min, not only 3 prompts.
- [#6429](https://github.com/Niko1221/Strata/issues/6429) (open, no maintainer decision): `STRATA_HIPBLASLT_TABLE=on`
  on gfx1100 IQ3_S reads 4K+ prompts 1.33-1.89x as fast (32K 957 → 1,808 tok/s), decode unchanged, needles 9/9 both
  arms. [#6378](https://github.com/Niko1221/Strata/issues/6378): with a hipBLASLt version other than the table's
  (100200), the switch silently does nothing or makes 110K cold prefill ~25% slower. Try it only with a matching
  library.
- v0.2.16 (engine 0.1.62) replaced the ggml/llama.cpp matrix kernels with Strata's own and lists the RX 7000 changes
  as "Not tested"; [#6067](https://github.com/Niko1221/Strata/issues/6067) (closed) reported gfx1100 cold prefill ~40%
  slower than 0.1.59. A/B before trusting 0.1.63 numbers.
- Strata still lists no Inkling model; Qwen4 is groundwork only (`strata --geometry`, v0.2.13). *(Superseded
  by v0.2.19, 2026-11-22: `strata-inkling` 0.1.65 ships Inkling-2-Mini packs.)*

## Review 2026-11-22: v0.2.18 and v0.2.19

Desk review of the two releases after the last reviewed version (v0.2.17, [review 2026-11-20](#review-2026-11-20-resident-mode-on-32-gb-ram-v0217)).
Release notes read from the GitHub API on 2026-11-22; nothing installed, nothing run, no model downloaded.

### v0.2.18 (2026-11-21): Hy4-Flash, nothing for this PC's RAM

- App/terminal 0.2.18; `strata-engine` and the new `strata-hy4` shape engine at **0.1.64**; Control 0.1.64;
  update feeds 130/126. New 15-package set in `shape_engines`, Linux `hip-rx7900` covers `gfx1100`-`gfx1150`.
- Adds **Tencent Hy4-Flash** (`strata-hy4` 0.1.64): 220B parameters, 12B active, a 64B Engram lookup, up to
  1M context, text + vision, with `DFly2` speculative decoding built in.
- Three packs, all sized for far more RAM than this PC has: **SQ-64 129.61 GB** on disk including
  `Engram-Q8`, "runs from 64 GiB of RAM with an 8, 12, or 16 GiB GPU"; SQ-96 157.16 GB for 96 GiB systems;
  SQ-128 181.23 GB ("0.0879 reasoning mean KL") for 128 GiB+. AMD numbers quoted: 62 tok/s on R9700 /
  RX 9070 XT, 51-60 tok/s on a 128 GB Strix Halo.
- **Verdict**: no action here. 64 GiB of RAM is twice this machine's 31.25 GiB usable, and the release changes
  nothing for Qwen3.8-Flash-Next.

### v0.2.19 (2026-11-22): the RDNA3 Flash-Next release, plus native Inkling

- App/terminal 0.2.19; **`strata-engine`, the new `strata-inkling` and the SYCL `strata-hy4` all at 0.1.65**;
  Control 0.1.65; feeds 131/127.
- **`strata-engine` 0.1.65, AMD RDNA3 (`gfx1100`-`gfx1151`)**: NVFP4 Wave32 FP16 WMMA prefill ("42-44x lower
  approximation error"), `native_h11p_kernel` (`PF_F16=2`), discrete `moe_p1a` `FL=3`, `IQ2_XS` and NVFP4
  single-launch bitwise-exact LDS decode (`em0=8`), `3.10x` Wave32 WMMA `DFlash2`, WDDM coherent host
  staging, OCuLink `PcieAuto`, Windows `gfx1151` defaults — the release note's claim is **"1.44x-2.10x faster
  prefill and +17%..+22% faster decode (97.9 tok/s, peak 103.7 tok/s) on RX 7900 XT"**, with "zero
  environment variables needed".
- **`strata-inkling` 0.1.65**: native Inkling 2 Mini (26.4B, 3.4B active / 5.4B looped-active across 48
  virtual layer visits, 1M context, text + image), loading Strata packs, official `safetensors` (+ `mtp.safetensors`)
  or community `.gguf`, with `--gpus 2` expert parallelism and built-in `W=4` DSpark decoding:
  - **SQ-10** 10.47 GB (9.75 GiB): 100% in VRAM on 12 GiB cards; **SQ-15** 14.35 GB (13.36 GiB): 16 GiB cards,
    96.68% top-1 agreement / 0.00889 test KL; **SQ-20** 19.35 GB (18.02 GiB): "bit-exact lossless native
    `SF4+MX8`" for **24 GiB+ GPUs**, 100.00% top-1 / 0.00000 KL. Vision pack 0.64 GB BF16.
  - Published speed is CUDA/Metal/Intel plus **Radeon AI PRO R9700 (99.0-106.5 tok/s)** and Strix Halo; **no
    RX 7900 XTX or XT figure for Inkling is published** (the 97.9 tok/s line is for Flash-Next).
  - Linux `hip-rx7900` package for `strata-inkling` 0.1.65 is 95,697,377 bytes, i.e. a 96 MB engine download,
    and the packs are separate.
- Unchanged assets stay on their old releases: `strata-hy4` 0.1.64 on 0.2.18, the two DFlash2 drafter packs on
  0.2.16, the frozen DeepSeek 0.1.59 engines on 0.2.13.

### What it changes here

1. **Flash-Next: this is the retest trigger.** A claimed 97.9 tok/s decode on an RX 7900 XT (a smaller card than
   this XTX) is well above the 59-65 tok/s short-prompt / 36.7 tok/s at 240K measured on v0.2.8, and above the
   27B profile's 33.2 tok/s at 240K. The claim names no context, KV type or quant, so it is a hypothesis until
   our arm runs. "Zero environment variables" would also retire the 2026-10-30 `GPU_PINNED_MIN_XFER_SIZE=1048576`
   workaround, which must be checked first (drop it and confirm a 120K prompt does not stall).
2. **Inkling on Strata is now possible but unmeasured**: SQ-20 at 18.02 GiB fits a 24 GiB card on paper, leaving
   about 4-5 GiB for KV, and no gfx1100 latency exists. The measured llama.cpp path (GodGMN fork, 41-42 tok/s at
   262K) is the number a Strata arm would have to beat; the model is parked
   ([owner](inkling-2-mini.md#status-parked-2026-11-22-resume-triggers)), so this is not a reason to install anything.
3. **Hy4-Flash is out of reach** (64 GiB of RAM minimum).

### Next step (planned, not run; attempted 2026-11-22 and stopped at the disk check)

Per the user's choice: **retest the abliterated SC117 Flash-Next set on Strata 0.2.19**, in this order —
F0 (update/install 0.2.19 + engine 0.1.65, re-check every flag of the 2026-10-30 run config against that
version, confirm whether the ROCm xfer-size workaround is still needed); confirm the SC117 IQ2_XS file is
still on disk (the 2026-11-05 cleanup deleted every Flash-Next set, so a ~68 GB download may be required);
then 262K int8, `--vram-reserve-mib 3072`, `undeclared_tool_calls: "call"`, the 2026-10-30 prompts, a serving
run of more than 10 minutes ([#6392](https://github.com/Niko1221/Strata/issues/6392)), the coding suite against
the 27B, and finally the abliteration check (refusal prompts, because a control vector that is not applied
silently gives the original model). Because v0.2.16 replaced the matrix kernels and early reports had gfx1100
cold prefill slower ([#6067](https://github.com/Niko1221/Strata/issues/6067)), the arm compares against the
v0.2.8 numbers above, not against v0.2.11.

Status 2026-11-22: F0 is done and the arm ran; it is below the speed floor and storage-bound, so the rest of the
list (240K, retrieval, coding suite, refusal check) was not run — see the next section.

## 2026-11-22: SC117 on v0.2.19, measured below the floor

Measurement and full record: [`results/20261122-strata-0219-sc117/`](../../results/20261122-strata-0219-sc117/README.md).

- **Install, and the disk rule it settled**: v0.2.19's mapped mode writes one `experts.bin` of the whole expert arena
  (`arena_gb + 1` = 36.5 GB for `IQ2_XS`; 35.45 GB written here, 33.02 GiB), and the first session had only 21.96 GB
  free on `/home`, so setup refused (`not enough free disk space for the low-RAM copy of the experts in
  …/Strata-data/packs/iq2_xs: it needs about 36 GB and 22 GB are free there.`). The workaround used then: with the set on the rotational HDD and `--gguf-dir` pointing there, setup wrote the pack to
  the NVMe and exited 0. It left shard 1 on the HDD, which made the numbers below a measure of the HDD; the rule since
  2026-11-23 is every file on the NVMe ([SOP](../sop/strata.md)).
- **Two sessions, one finding each**:
  - Without `GPU_PINNED_MIN_XFER_SIZE=1048576` the engine died on the first long answer:
    `Unrecoverable native verification failure: verify: timed out at layer 28; its GPU waits were released but the GPU
    did not finish within 5 s (#267)` (exit `-15`, next request `HTTP 503`). 0.1.65's "zero environment variables
    needed" does not hold here in mapped mode; the 2026-10-30 ROCclr workaround is still required.
  - With it, 4/4 requests finished: **5.8 / 6.6 / 9.8 tok/s decode** on empty-context requests (800-token cap,
    temperature 0, 86-92% expert-cache hit) and **324.2 tok/s prefill + 12.8 tok/s decode at a 69,698-token prompt**.
    All four hit `finish_reason: length` while still thinking.
- **Why that is 5-10x under v0.2.8's 59-65 tok/s, from the engine's own lines**: `prefill plan inputs: 33.0 GiB
  experts, 12.7 GiB in the GPU caches, 0.0 GiB RAM copy, file tier 20.3 GiB; 14.8 GiB available for the page cache;
  drive 0.15 GB/s (sda is a rotational disk)`; every request reports `page cache held 0.0 MB at the read` and
  39.0-191.2 GB read from storage (298,105 major faults on the 69.7K prompt), with 13-15 GiB in zram and 0.4-4.0M
  `pswpin` pages per request. The dense `--native` shard is still on the HDD and the engine prices the whole drive from
  it; mapped mode keeps no RAM copy, so the 20.3 GiB file tier never fits 14.8-18.7 GiB of page cache.
- **Verdict**: rejected on speed against the 15 tok/s floor; no `[strata.*]` table, no harness wiring. The run says
  nothing about 0.1.65's kernels — it measures the storage path. To make a kernel A/B meaningful the dense shard must
  be on the NVMe (41 GB) and the file tier must fit the page cache (a resident copy needs 18-20 GiB, which does not
  coexist with the desktop on 31 GiB).
- **Not run**: 240K fill, 240K retrieval, the coding suite against the 27B (6/6 baseline), the abliteration refusal
  check.
- **History (kept)**: the first session's block was the disk check above; the all-in-RAM alternative installed but
  could not serve (36 GB of experts on 31.25 GiB) and its config was removed. `scripts/strata.py update` still calls
  the `update.sh` that v0.2.19 deleted, and `local.linux.toml`'s `strata_dir` still points above `terminal/`; both are
  listed as open follow-ups in [`../sop/strata.md`](../sop/strata.md#update-strata).
