# 2026-09-30 — KVMem trial, round 1: decode at depth and retrieval quality

**Measures**: whether [kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp) (completed KV
blocks live in host RAM; per step it retrieves the blocks relevant to the last user message into a
bounded GPU working set, the `--kvmem-budget`; attention covers only that window, so VRAM and
decode stay nearly flat with depth) decodes faster than the adopted `qwen38-iq3s-mtp` /
`262k-q8q51-mtp` profile at 128K-240K fill, and whether it keeps exact-match retrieval at 240K.
Protocol and go/no-go criteria: [`docs/ENGINES-EXPERIMENTS.md`](../../docs/ENGINES-EXPERIMENTS.md#kvmem-trial-round-1-run-2026-09-30-not-adopted).

## Environment

- RX 7900 XTX 24 GiB (gfx1100), power cap 272 W, 32 GiB host RAM, CachyOS Linux.
- KVMem source `kvmem/kvmem-llama.cpp` commit `abe72b38256d` (v0.17.0 source), llama.cpp submodule
  `7fe450e19305`. Upstream has one newer commit, `bc6b4e0` (CUDA fused GDN norm, not ROCm-related).
- Built with `python3 scripts/build-rocm.py --linux --gpu-targets gfx1100 --jobs 6` in the ROCm 10
  TheRock venv (HIP 7.15.26333, AMD clang 23.0.0git `8f497e0992fb`); `ctest` 18/18 pass, 1 skipped
  (`kvmem-mtp-kv-test` needs a model).
- Two ROCm compile errors at that commit, fixed locally with [`rocm-build-fix.patch`](rocm-build-fix.patch)
  (not reported upstream yet): `ggml-cuda.cu:4363` uses `cudaPeekAtLastError` (added by KVMem's
  `patches/cuda-graph-decode.patch`; fix: `#define cudaPeekAtLastError hipPeekAtLastError` in
  `ggml/src/ggml-cuda/vendors/hip.h`), and `src/adapter/llama-memory-kvmem-mtp.cpp:19` includes
  `cuda_runtime.h` (fix: include the fork's own `llama-kvmem-gpu.h`, as `llama-memory-kvmem.cpp` does).
- Model: `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf`, the same file as the baseline. Baseline engine:
  `hip-kvmix` (llama.cpp b11160, [`docs/ENGINES.md`](../../docs/ENGINES.md)).

## Why the repository benches were not used

`llama-kvmem-server` serves only `/health /props /slots /v1/models /v1/chat/completions
/v1/responses` (no `/tokenize`, `/apply-template`, `/completion`), so `bench/depth_bench.py` and
`bench/longctx_quality.py` cannot target it. Two throwaway scripts replace them. Other differences
from `llama-server`: thinking is off by default (`--enable-thinking` needed; `--reasoning-effort
medium` alone gives no thinking), no `--ctx-checkpoints`, `--metrics` or `--version`,
`--kvmem-budget` is in tokens, GPU KV = budget + gen-reserve, and one generation (thinking
included) cannot exceed `--kvmem-gen-reserve` (16,384). Timings report no MTP acceptance.

## Method

**Depth** ([`kvmem_depth.py`](kvmem_depth.py)): fresh server per case; wikitext-2 `wiki.train`
prompt plus the same Spanish essay instruction as `bench/depth_bench.py` (Spanish on purpose, as
there); depth calibrated from `usage.prompt_tokens` on a `~`-prefixed 64K probe, so real prompt
tokens overshoot the target by 1-1.8%; `max_tokens` 1,500 (every run hit `length`); thinking on;
card sampling (temperature 1.0, top-p 0.95, top-k 20, min-p 0); peak VRAM from fdinfo, peak RSS,
minimum `MemAvailable`, peak junction temperature. The baseline runs through the same harness.
One sample per cell.

KVMem common flags (full argv per case in [`commands/`](commands/)):

```bash
llama-kvmem-server -m ~/models/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
  --device ROCm0 -ngl 99 --host 127.0.0.1 --port 8080 -c 262144 -b 512 -n 16384 \
  --kvmem --kvmem-budget <28672|49152> --kvmem-gen-reserve 16384 --kvmem-block-tokens 128 \
  --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 2 \
  --kvmem-mtp-state replay --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --reasoning-effort medium --enable-thinking
```

Baseline: the adopted profile (`-c 262144 -ctk q8_0 -ctv q5_1 -fa on -np 1 --ctx-checkpoints 4
-ngl all --metrics --spec-type draft-mtp --spec-draft-n-max 3 -ub 256 --reasoning-effort medium`,
same sampling), `hip-kvmix` b11160. The arms differ in more than KVMem (KV q8/q8 vs. q8/q5_1, MTP
n=2 vs. n=3, `-ub`), so the ratios below are not a pure KVMem effect.

**Quality** ([`kvmem_quality.py`](kvmem_quality.py), launched by [`scripts/run2.sh`](scripts/run2.sh)
and [`scripts/run3.sh`](scripts/run3.sh)): replays saved `bench/longctx_quality.py` documents as
chat requests (server `--temp 0 --top-k 20 --min-p 0`, thinking off, `max_tokens` 200) and scores
them with that script's `evaluate()`. The scripts were run from `<repo>/_tmp/`; adjust the
`ROOT`/`_tmp` paths to rerun. Documents (in `bench/res/longctx_quality/`, git-ignored, regenerable
with `bench/longctx_quality.py` and its seeds):

| Document | Run | sha256 |
|---|---|---|
| `d240000-n00.json` | `longctx-20260926-145634` | `00e0648d6d2ff39327edca5fb5d739a5115334c0cca106d11fa43836c9dc4778` |
| `d240000-n01.json` | `longctx-20260926-145634` | `b5639b0db851bc6774d9759af1b10c2176fb764103f78cd73a65b39f1c1c6ef4` |
| `d128000-n00.json` | `longctx-20260925-170146` | `c4807ba2231aac313fed4c8e3f7978a2ff108d33b6a29c943d06620193c77854` |
| `d128000-n01.json` | `longctx-20260925-170146` | `57478a8322d73ecfdfe424cb99990588f282e66876bf2385053c8b8481bcf0a7` |

The 240K documents are the exact ones behind the baseline's 8/8 on the adopted flags
([`../20260926-longctx-quality-262k/`](../20260926-longctx-quality-262k/)).

## Results: decode at depth (1,500 output tokens, thinking on)

| Prompt tokens | Arm | pp tok/s | tg tok/s | Peak VRAM MiB | Peak RSS GiB | Min MemAvailable GiB | Hotspot °C |
|---:|---|---:|---:|---:|---:|---:|---:|
| 129,305 | KVMem n=2, budget 28,672 | 647 | 45.9 | 14,937 | 7.81 | 11.69 | 93 |
| 129,305 | Baseline | 520 | 30.8 | 22,665 | 5.58 | 14.96 | 97 |
| 192,767 | KVMem n=2, budget 28,672 | 637 | 48.1 | 14,933 | 8.83 | 11.36 | 97 |
| 192,767 | Baseline | 429 | 22.2 | 22,633 | 6.09 | 12.35 | 99 |
| 192,767 | KVMem n=2, budget 49,152 | crash | - | - | - | - | - |
| 244,353 | KVMem n=2, budget 28,672 | 626 | 48.6 | 15,127 | 9.39 | 6.51 | 98 |
| 244,353 | Baseline | 380 | 20.8 | 22,638 | 6.40 | 12.39 | 100 |
| 244,353 | KVMem n=2, budget 49,152 | 540 | 40.2 | 15,991 | 13.14 | 8.97 | 98 |

- At 244K: budget 28,672 is 2.34x the baseline's tg, budget 49,152 is 1.93x. Baseline MTP
  acceptance 60-62%; KVMem reports none.
- The 49,152 run at a 190K target crashed at the end of prefill (~191.5K tokens processed at ~561
  tok/s): `Memory access fault by GPU node-1 ... Reason: Page not present or supervisor privilege`
  ([`crash-b49k-190k.log`](crash-b49k-190k.log), last 40 lines). One occurrence, not yet reproduced.
- The 240K essay is coherent and grounded in the wiki articles. Smoke test at empty context: tg
  71.5 tok/s (336 tokens), VRAM 13.7 GiB.

## Results: retrieval quality (temperature 0, thinking off)

| Budget | Documents | Exact match | Notes |
|---|---|---:|---|
| 28,672 | `d240000-n00`, `d240000-n01` (240K) | 7/8 | Miss: `d240000-n01` q3, needle `PLANO-01-03-469` at token 40,302 answered `null` (not found, not the decoy); the other needle (`MUESTRA-01-12-858`, token 145,509) is correct |
| 28,672 (repeat) | `d240000-n01` | same miss | Identical miss, so deterministic, not a one-off |
| 28,672 | `d128000-n00`, `d128000-n01` (128K) | 8/8 | |
| 49,152 | `d240000-n00`, `d240000-n01` (240K) | 8/8 | Includes the former miss |

Raw rows: [`quality/`](quality/). Cold 240K prefill ~380-386 s (~630 tok/s); follow-up questions
reuse 239,584-239,590 cached tokens and take 4-6 s each.

## Conclusion

Promising, not adopted. Against the go/no-go criteria: decode at 160K+ of at least ~1.3x the
current profile is met at both budgets; 8/8 exact at 240K is met only at budget 49,152 (7/8 at
28,672); at least ~4 GiB host RAM free at 256K is met (minimum 6.51 GiB); the agent run (T6) is
not done. Blockers: reproduce the budget 49,152 crash, the real agent run, and the 16,384-token
per-turn output cap.

## Caveats

- Single sample per cell; arms differ in KV types, MTP n and `-ub` (see Method).
- The retrieval loss at budget 28,672 is one needle in one document; causes (budget, block size,
  mid-band position) are untested. Upstream [issue #4](https://github.com/kvmem/kvmem-llama.cpp/issues/4)
  reports a related mid-band retrieval collapse beyond ~210K.
- The paper's claim that a 32K active context is about lossless vs. 256K (arXiv:2609.04852,
  LongMemEval-S 85.6 vs. 86.6) is a third-party claim, see [`docs/SOURCES.md`](../../docs/SOURCES.md).
- Next round (not run): reproduce the 49,152 crash; budgets 36,864 and 40,960 at block 128;
  `--kvmem-block-tokens 32`; 3 repeats; MTP n=3; then the agent run.

**Raw data**: `depth-summary.jsonl` (one row per case), `commands/` (argv per case), `quality/`,
`crash-b49k-190k.log`. Full responses and server logs stay local (`_tmp/`, git-ignored). Personal
paths are replaced with placeholders, as in [`../INDEX.md`](../INDEX.md). Measurements doc:
[`docs/ENGINES-EXPERIMENTS.md`](../../docs/ENGINES-EXPERIMENTS.md#kvmem-trial-round-1-run-2026-09-30-not-adopted).
