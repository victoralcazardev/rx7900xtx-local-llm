# SOP: upstream watch (find, triage and adopt what the sources changed)

Run this at the start of every session that aims to improve the inference setup, and before changing an engine,
a model file or a profile. Every source below can ship a new version, kernel, flag or file on any day; this list is
how nothing is missed and nothing is adopted without a measurement.

This file owns the **watch list and its "last checked" state**. It does not own claims or numbers: a third-party
claim goes to [`SOURCES.md`](../SOURCES.md), a measurement to `results/`, a decision to
[`DECISIONS.md`](../DECISIONS.md) (see [`STYLE.md`](../STYLE.md) §8). Individual PRs and issues to re-check live in
[`ENGINES-EXPERIMENTS.md`](../ENGINES-EXPERIMENTS.md#upstream-watchlist-2026-09-29) (engines) and the model docs'
resume triggers; this list points at them, it does not copy them.

## Routine

1. **Collect.** For each row of the watch list, list what is new since its "Last checked" ref with the command in
   [Commands](#commands): commits on the watched branch, releases, the state of the watched PRs and issues, new
   Hugging Face files. Many sources at once: give each scout a group of rows and the exact refs; a scout's summary
   is a hypothesis until its citations are read in the primary source (`AGENTS.md`, evidence discipline).
2. **Triage** each novelty into one of four outcomes:

   | Outcome | When | Where it goes |
   |---|---|---|
   | Ignore | Does not touch our GPU (gfx1100), our models, our engines or our flags | Nothing (the "last checked" update covers it) |
   | Note | Relevant claim, but no cheap test or no expected gain | One row in `SOURCES*.md` with its evidence status |
   | Test | Plausible gain for this setup and a test fits one session | A `results/` run following the matching SOP ([`update-engine.md`](update-engine.md), [`measure-backend.md`](measure-backend.md), [`new-model.md`](new-model.md)); check [`TRIED.md`](../TRIED.md) first, it may already have lost |
   | Adopt | A test on this machine is equal or better on every gate (speed at each depth, quality, VRAM, tool calls) | `models.toml` / `local.toml`, STATUS, DECISIONS, CHANGELOG, after the user's OK |

   Rank the "Test" items by expected gain per effort, as in the
   [2026-11-23 round](../../results/20261123-inkling-round/README.md#next-cheap-improvements-prioritized-scouts-2026-11-23-not-yet-measured-here).
3. **Record.** Update "Last checked" (date and ref) of every row you checked, in the same commit as the notes.
   A retest trigger that fired goes to the owner doc's open questions or straight into a test.

## Watch list

Last-checked refs are the newest the repository recorded; a row with only a date was reviewed, not pinned.

| Source | What to watch | Last checked | Why / retest trigger |
|---|---|---|---|
| [GodGMN/tintero](https://github.com/GodGMN/tintero) `main` (was `GodGMN/maya-inkling-mini` `hip-port`, renamed) | Commits on `src/ik2/`, `serve/`, `docs/HIP-PORT.md`, `docs/inkling2-mini/ik2-mini-gfx1100.json` | 2026-11-27: `main` at `dc52e6f` (v0.1.0 release, DFlash2 drafter PR #9, `thinking_budget` PR #10); fork of `alesha-pro/maya-inkling-mini`; trial done, not adopted ([results](../../results/20261127-tintero-dflash2/README.md), [sources](../SOURCES-community.md#tintero-strata-0221-0222-ista-gsq-rco-and-inkling-cyber-2026-11-27)) | Our Inkling engine. New `IK2_*` options, kernels, loop guard, drafter changes; rebuild in a separate dir and A/B ([ENGINES](../ENGINES.md)) |
| [alesha-pro/maya-inkling-mini](https://github.com/alesha-pro/maya-inkling-mini) `main` | Commits, README numbers | 2026-11-27, `27daec5` (docs only since `fcd523f`); its HIP build fails on gfx1100 (CUDA PTX in `ik2_kernels.cu`) | CUDA origin of fixes the port has not picked up (`IK2_SLOT_KEEP`, tool parser) |
| [mw00/project-maya](https://github.com/mw00/project-maya) | Releases, `CHANGELOG.md`, `src/ik2/`, `docs/AMD_MAYA.md`; issues #1108, #1163 | 2026-11-27, v1.1.83 `6382132`: `maya-ik2` builds for gfx1100 but reads only the `inkling2` looped layout (Maya-L NVFP4, 17.6 GB); not benchmarked (disk) ([sources](../SOURCES-community.md#tintero-strata-0221-0222-ista-gsq-rco-and-inkling-cyber-2026-11-27)) | Upstream of `maya-ik2`: DSpark drafter (still `hipblasSgemv` in the fold, needs the rocBLAS device pack), AMD support; retest when it reads an uncensored file or posts a gfx1100 drafting number |
| [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | Releases and the PR list in [`update-engine.md`](update-engine.md#re-validation-cycle-run-this-whenever-llamacpp-cuts-a-new-release); Inkling PRs #32773, #32695, #32883, #32898, #32948 | b12690 (2026-11-24); merged: #32740 compact FA bias 2026-11-23 (in b12670), #32218 Inkling DSpark 2026-11-24 20:11Z (no tag yet); #32752 closed unmerged | Our Qwen engine; Inkling triggers in [`inkling-2-mini.md`](../models/inkling-2-mini.md#status-parked-2026-11-22-resume-triggers) |
| [GodGMN/llama.cpp](https://github.com/GodGMN/llama.cpp) `inkling-rdna3` | Commits, `docs/inkling-rdna3.md` | `cb0e46960` (2026-11-22) | `hip-inkling` engine (fallback for Inkling) |
| [unslothai/llama.cpp](https://github.com/unslothai/llama.cpp) | PR #386 (banded-FA quantized KV) | 2026-11-22 | Inkling quantized KV upstream |
| [JakeATX/llamAmpere](https://github.com/JakeATX/llamAmpere) | Releases, Inkling presets (`24ink`), drafter notes, any HIP path | 2026-11-24, v0.7.4 (CUDA only; [review](../SOURCES-community.md#atomic-engine-and-llamampere-v074-inkling-posts-2026-11-24)) | CUDA reference for what an Inkling drafter gains (127-136 tok/s at 100K on a 3090); retest the `maya-ik2` drafter when the port replaces `hipblasSgemv` in the fold |
| [Niko1221/Strata](https://github.com/Niko1221/Strata) | Releases, `strata-inkling`, gfx11 issues (#6685, #6791) | 2026-11-27, v0.2.22 (AMD `strata-inkling` stays 0.1.67; IQ2/IQ3_S experts transcoded to SF4 until PR #6933); next release announced | Alternative engine; test once it reads our files or posts a gfx1100 Inkling number |
| llama.cpp forks in [`SOURCES-community.md`](../SOURCES-community.md#llamacpp-fork-survey-2026-10-02) (ik_llama.cpp, RDNA-FAST, rdna-boosts, beellama, turboquant, kvmem) | Commits touching HIP / FA / KV / MTP | 2026-10-02 to 2026-11-06 (reviewed) | Kernel ideas for gfx1100 |
| Hugging Face: [thinkingmachines/Inkling-2-Mini](https://huggingface.co/thinkingmachines/Inkling-2-Mini) card and `mtp.safetensors` | Card sampling, context, drafter revision | `mtp.safetensors` rev `b85c3cfa` | Card values win over GGUF metadata (`AGENTS.md`) |
| [Chromadera/nib](https://github.com/Chromadera/nib) | Commits; fixes for `nib bench` and the no-`--mtp` server crash; an unbounded-sampling fast path | 2026-11-27, v0.2.2 `859bf23` / `main` `4c92d73` (nib#1 closed 2026-11-26); trial [`results/20261127-nib-v022/`](../../results/20261127-nib-v022/) done: not adopted (upstream start-up crash); production `2e16cf0` + [thinking-cap patch](../../engine-patches/nib-reasoning-budget-2e16cf0.patch) | Inkling engine on trial: +13-25% decode to 33K, ~1.4-1.9x at 134K-258K with sparse attention; retest on new commits |
| [degenmeowster/Inkling-2-Mini-Nib-Pack](https://huggingface.co/degenmeowster/Inkling-2-Mini-Nib-Pack) | Re-uploads of the NVFP4-Mixed file (sha256 `304d4fe3…`) | 2026-11-24 | The only published Q8_0 + NVFP4 GGUF `nib` reads; base model, not uncensored |
| [nokeepai/Inkling-2-Mini-Unbound](https://huggingface.co/nokeepai/Inkling-2-Mini-Unbound) (+ `-GGUF`) | New versions after v2.1; which tensors they edit | 2026-11-24, v2.1 (120 attention tensors, experts untouched) | Our uncensored graft source for `nib` (`results/20261124-nib-trial/raw/graft_unbound_q8.py`); a new version needs a new graft + refusal check |
| Hugging Face quant survey (`base_model:quantized:thinkingmachines/Inkling-2-Mini`, `finetune:`) | New uncensored / abliterated / better quants (Abiray, bartowski Unbound, @SergioGMN abliterated, Unsloth, ggml-org) | 2026-11-27 ([re-survey](../models/inkling-2-mini.md#hugging-face-re-survey-2026-11-27)): no uncensored GSQ-RCO file; onemunanoyo Abliterated UD-Q4_K_XL is the next candidate (nib/tintero fit unverified) | Expert and head types must be ones `maya-ik2` reads; then bench + GSM8K + refusals vs. q8dense |
| [ISTA-DASLab/Inkling-2-Mini-GSQ-RCO-GGUF](https://huggingface.co/ISTA-DASLab/Inkling-2-Mini-GSQ-RCO-GGUF) | New files, an uncensored variant, engine support beyond llama.cpp | 2026-11-27 (last upload 2026-11-26) | Best size-for-quality Inkling quant; useful once `nib`, `tintero` or Strata (#6933) read its types, or as a llama.cpp graft base for Unbound v2.1 |
| Model and quant repos of the setups in use ([STATUS](../STATUS.md)) | New quants, card changes | per [`new-model.md`](new-model.md) | Setups |
| ROCm Python wheels, `https://stable.repo.amd.com/rocm/whl-next/` | New `rocm` / `rocm-sdk-*` versions (10.1.0, 10.2.0 listed on 2026-11-23); the per-arch `rocm-sdk-device-gfx1100` package | 2026-11-23 (we build with 10.0.0; `rocm-sdk-device-gfx1100` 10.0.0 used privately for the drafter test) | Build toolchain of every own engine; a newer SDK needs a rebuild and an A/B |
| CachyOS kernel, `linux-firmware`, Arch `rocm` / `rocblas` / `hip-runtime-amd` | Package versions | kernel 7.3.5-2, `rocblas` 10.1-2, `hip-runtime-amd` 10.1-2.1 (2026-11-23) | Runtime under every engine ([install](install.md#known-errors)) |
| Playbooks: [alesha-pro/inference-optimization-playbook](https://github.com/alesha-pro/inference-optimization-playbook) (local copy `.agents/skills/inference-optimization-playbook`), [sybil-solutions/inference-optimisation-skill](https://github.com/sybil-solutions/inference-optimisation-skill) | New chapters or verdicts | 2026-11-20 / 2026-11-22 | Hypotheses to test, never settings to copy |

Add a row when a session starts depending on a new source; drop a row (with a DECISIONS line) when we stop using what
it feeds.

## Commands

```bash
# git sources: fetch, then what is new since the last-checked ref (keep a clone per engine under the engines root)
git -C <clone> fetch --all --prune
git -C <clone> log --oneline <last-checked>..origin/<branch>
git -C <clone> diff --stat <last-checked> origin/<branch> -- src/ serve/ docs/   # where the change lands
# GitHub releases, PRs, issues
gh release list -R <owner/repo> --limit 5
gh pr view <n> -R <owner/repo> --json state,mergedAt,updatedAt,title
gh pr list -R <owner/repo> --search '<topic>' --state all --limit 10
# Hugging Face: quants of a base model, newest first
curl -s 'https://huggingface.co/api/models?filter=base_model:quantized:<org/model>&sort=lastModified&limit=30' \
  | python3 -c 'import json,sys;[print(m["lastModified"][:10],m["id"]) for m in json.load(sys.stdin)]'
# ROCm wheels available for gfx1100
curl -s https://stable.repo.amd.com/rocm/whl-next/rocm-sdk-device-gfx1100/ | grep -o 'rocm_sdk_device_gfx1100-[0-9.]*-py3-none-linux_x86_64.whl'
```

A closed PR is not always unmerged: maintainers sometimes merge locally (project-maya #1154 went into v1.1.75 as a
squash). Read the closing comment before treating it as rejected.
