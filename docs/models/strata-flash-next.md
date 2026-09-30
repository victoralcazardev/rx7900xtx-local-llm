# Qwen3.8-Flash-Next via Strata: evaluation note (2026-09-29)

**Status: not adopted, not measured on this hardware.** A desk review of upstream claims against
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
- **Disk**: shard 2 of the GGUF, a 28.8 GB n-gram/PLE lookup table, "read a few rows per token
  through the OS cache" (Strata `docs/DETAILS.md`). An NVMe SSD is strongly recommended upstream.

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
  comes from the page cache or disk; that page cache is shared with the 28.8 GB n-gram table.
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
- The hipBLASLt table is calibrated for Strata's own dense shapes; its effect on llama.cpp is
  untested.

## Decision criterion for an on-hardware trial

The current 27B profile already does **68.9 tok/s at empty context** and **23.3 tok/s at 240K
fill** (see [`STATUS.md`](../STATUS.md)). Upstream's best AMD figure for Flash-Next (55-59 tok/s,
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
