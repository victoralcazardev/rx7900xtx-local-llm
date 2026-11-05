# Strata on gfx1100: how it uses memory and what to tune

How Strata (Niko1221/Strata) places a Qwen3.8-Flash-Next set on an RX 7900 XTX (24 GB) with 32 GB of RAM, and the
switches that matter, read from the v0.2.11 source (`v0.2.11-3-g9f7d977d`, engine 0.1.57) on 2026-11-05. Model history
and measurements: [`strata-qwen-flash-next.md`](strata-qwen-flash-next.md); procedure: [`../sop/strata.md`](../sop/strata.md).

Evidence labels: **source-checked** (read in the Strata source at the cited line, not run here), **community-measured**
(a third party's run, cited), **measured here** (a result folder in this repo). Paths are relative to the Strata clone. Line numbers come from a read-only review; `generate.cpp:813, 1044-1050, 2459, 3735-3743`, `drafting.py:47, 228-238`, `memory.hpp:73-78`, `expert_source.hpp:726`, `setup.py:486-508` and `AMD_HIP.md:772-774` were re-read for this page.

## Current conclusion

- **Fit first.** Decode speed is set by whether the experts the GPU cache does not hold fit in RAM. Read it from the start
  log's `prefill plan inputs` line: `experts - GPU caches` must be at most `RAM copy + page cache`. When it does not fit,
  every token waits on the NVMe: Unsloth UD-IQ2_XS left ~28 GiB off the GPU against ~20.5 GiB of room and decoded
  5.7-10.8 tok/s (measured here, [results](../../results/20261105-strata-unsloth-ud-iq2xs/README.md)); the ISTA IQ2_XS
  (33 GiB of experts) fit and decoded 59-65 (measured here, 2026-10-30).
- **gfx1100 runs without the decode push.** The route tail skip and the measured PCIe share are on for CUDA and gfx12
  only: "every other AMD part (gfx11, gfx906, ...) keeps its earlier behaviour" (`src/program/generate.cpp:2459`,
  source-checked). gfx1100 has no architecture defaults at all (`src/core/arch_defaults.cpp`).
- **A tuned 7900 XTX box gets ~45% more.** Same card, 30 GB DDR5, CachyOS, ROCm 7.2.4, ISTA IQ2_XS, Strata 0.1.45: chat
  decode 59.8 -> 87.3 tok/s, agent 75.5 -> 99.7, 4K prompt 339 -> 802 tok/s, "from the configuration changes ... not from
  a newer engine" ([PR #3665](https://github.com/Niko1221/Strata/pull/3665), community-measured). Its 59.8 default
  matches ours, so our earlier numbers were the gfx1100 defaults, not a broken setup. Recipe below.
- **The drafter barely changes memory.** MTP takes 1082 MiB of VRAM, DFlash2 890 (715 with the Q4_0 selector pack)
  (`strata_control/drafting.py:47`, source-checked); the ~5 GB MTP figure is the download. DFlash2 on gfx1100 is
  "untested" upstream (`drafting.py:96`).
- **The hipBLASLt table is prompt-only in the code.** It is read in `src/prefill/gemm.cu` (`Gemm::bf16`/`Gemm::f16`)
  and nowhere in `src/core` (decode/verify) (source-checked). The 2026-10-30 "decode -16-25% with the table" result needs
  a re-check; PR #3665 runs with `gfx1100-hipblaslt-100202.txt` on.
- **Direct (unbuffered) expert reads need a fast drive**: the engine picks them only at 4 GB/s or more
  (`include/strata/platform/memory.hpp:73-78`, source-checked). The PCIe 3 drive here reads 1.18 GB/s direct, so the
  page cache stays; `STRATA_UNBUFFERED_LOAD=1` forces direct but turns io prefetch off (`src/core/expert_source.cpp:1160`).

## How the expert tiers work

| Tier | What decides its size | Evidence |
|---|---|---|
| GPU expert cache | `--expert-cache auto`: VRAM left after dense weights, KV, drafter and `--vram-reserve-mib` (default 700), filled in expert-profile order | `generate.cpp:797`; `include/strata/core/expert_source.hpp:746-751` |
| Resident RAM copy (page-locked) | `--resident-budget-gib N`, clipped to `available - headroom - 0.25 GiB`; headroom `STRATA_RESIDENT_HEADROOM_GIB` (default 4) | `generate.cpp:3735-3743`; `expert_source.cpp:3584-3593` |
| File tier | the rest: `experts.bin` mapped, or (Unsloth sets without `experts.bin`) the GGUF shards read in place, three role slices per expert | `expert_source.hpp:726`; `expert_source.cpp:1698-1771` |
| Page cache | whatever RAM is left; Strata reads the file tier through it unless direct reads win (above) | `memory.hpp:73-78` |

Setup's rules on 31 GiB of RAM (`setup.py`, source-checked): every Unsloth v3.1 set gets the 8 GiB budget mode
(`budget = round(RAM) - 24 - KV`, minimum 8; full RAM copy only when RAM >= experts + 16 GiB, `setup.py:3650-3686`).
Expert sizes setup uses (`arena_gb`, GB; UD-IQ2_XS 42.3 GB = the engine's 39.4 GiB): UD-IQ1_M 34.8, UD-Q2_0 37.4, UD-IQ2_XS 42.3, UD-Q2_K_XL 46.0, UD-IQ3_XXS 50.3
(`setup.py:486-508`). With 64 GB, UD-IQ2_XS and smaller would fit in RAM entirely.

## The PR #3665 recipe (community-measured on a 7900 XTX, 30 GB)

Command line: `--expert-cache auto --prefill 4096 --spec 4 --spec-min-p 0.5 --mtp ... --max-context 65536 --kv int8
--resident-experts --vram-reserve-mib 3072 --pcie-frac 0 --pool-tasks 96 --adapt-swaps 0`. Each switch was measured by
its author with alternating A/B runs of 6 greedy prompts:

| Switch (gfx1100 default: off) | Effect there | Output change |
|---|---|---|
| `STRATA_ROUTE_TAIL_SKIP=7` (skip missed experts of rank >= 7 in verify windows) | decode +15% (84.1 -> 96.9) | **yes**: KL 0.036, top-1 93.95% (CUDA reports 0.003-0.006; larger here because half the experts are off the GPU) |
| `STRATA_FUSE_WAIT=1 FUSE_HITS=1 QFUSE_HC=1 GR_NORM_FAST=1 MTP_HIP_PRIO=1` (gfx12 decode set) | decode +3% mean / +4.5% median | no (same drafts accepted) |
| `STRATA_HC_Q8=1` | decode +2-4 tok/s | slight: KL 0.0018 |
| `STRATA_GDN_HEAD=1 GDN_PP=2 GDN_CONVL2=1 GDN_NOY=1 CVEC_FUSE=1 TOPK_REG_MIN_BLOCKS=4096` (gfx12/gfx1151 prompt set) | prompt +1.9% at 16K/32K | no |
| `STRATA_VERIFY_COHERENT=1 STRATA_DOORBELL_STORE=1` | stability: without either, 32K-56K prompts stalled under memory pressure | no |
| `--pcie-frac 0 --adapt-swaps 0` | stability: a PCIe share above 0 and adaptive swaps hung the GPU under memory pressure | — |

Also in its environment: `STRATA_HIP_WMMA=1 STRATA_SELECT_WMMA=1 STRATA_HIPBLASLT_TUNING=gfx1100-hipblaslt-100202.txt
STRATA_RESIDENT_PIN=0 STRATA_TSUM=1`, plus local engine patches (a gfx1100 defaults table). Its context is 64K, which
leaves about 2.6 GiB more VRAM for experts than 262K int8 (KV below).

## Other switches worth an arm

| Switch | Default here | Expected effect | Evidence |
|---|---|---|---|
| `--kv-resident 32768` (KV streaming) | off (setup wants ~53 GB RAM) | frees ~2.6 GiB VRAM at 262K int8 for experts; costs ~13.7 KB of pinned RAM per token | `generate.cpp:1048-1050`; `setup.py:6426-6455` (source-checked) |
| KV bytes per QSA layer per token | int8 | int8 1,056; k8v4 816; q4_0 576 (262K, 12 layers: 3.00 / 2.39 / 1.69 GiB); q4_0 +8-12% perplexity on long documents | `setup.py:273`; `DETAILS.md:234` (source-checked) |
| `--prefill auto:16384` / `auto:32768` | auto caps at 8192 off gfx12/NVIDIA | fewer passes over the streamed experts per long prompt; `auto:32768` +23% at 74K on a 7900 XTX with 50 GB RAM (v0.1.40.2) | `generate.cpp:813-816`; `AMD_HIP.md:774` |
| `STRATA_SCORES_THREAD=1` | off | long prompts +10-13% at ~131K, +22% at 240K (one 7900 XTX) | `AMD_HIP.md:351-365` |
| `--draft-conf` / `--spec` with DFlash2 | Auto: `--spec 6 --draft-conf 0.7` (by GPU slots: >=12000 0.35, >=7500 0.5, >=3000 0.7, else 0.8) | window length vs. verify cost; set in `user_args` so Auto keeps it | `drafting.py:217, 231, 835-838` |
| `drafting` key in the run config | auto (DFlash2 where the pack exists) | `mtp` / `dflash2` / `off`; a start never downloads the DFlash2 pack (`strata drafting fetch`) | `drafting.py:657-699`; `serve/server.py:3781` |
| `--expert-profile-save` / `tools/make_profile.py` | shipped `data/expert-profile.bin` | a profile learned from our own traffic orders the GPU and RAM tiers | `expert_source.hpp:746-751` |
| `STRATA_RAM_ADAPT=1`, `STRATA_ADAPT_OVERLAP_RESIDENT=1` | off | the RAM copy follows the conversation; needs the resident mode | `generate.cpp:18705-18720, 12689` |
| `STRATA_ROUTE_PRIOR` | 0 everywhere since 2026-10-29 | biases routing to resident experts; repetitions in long sessions | `include/strata/core/sm120_series.hpp:75-80` (last resort) |
| `GPU_PINNED_MIN_XFER_SIZE=1048576` | ours | fixed the 2026-10-30 mapped-mode stalls; no decode effect expected in resident mode | `generate.cpp:3299-3305`; `TROUBLESHOOTING.md:345` |

## Next round (when a new set or engine ships)

1. Pick a set whose experts fit: today UD-IQ1_M (setup 34.8 GB, ~32.4 GiB; same table file as UD-IQ2_XS, sha
   `05716382`) or the ISTA IQ2_XS; check `prefill plan inputs` on the first start.
2. Base run on stock settings, then the PR #3665 lossless sets one at a time (gfx12 decode set, `HC_Q8`, prompt set,
   `VERIFY_COHERENT`/`DOORBELL_STORE`, hipBLASLt table on), then context 262K vs. 128K vs. 64K.
3. DFlash2 vs. MTP vs. off on the winner (`drafting` key), then `--draft-conf` 0.35 / 0.7 / 0.8.
4. `STRATA_ROUTE_TAIL_SKIP=7` last and only with the coding suite, because it changes answers.
5. Same session, same desktop state, warm-up discarded; record the slot count and `VRAM free` line of every arm.
