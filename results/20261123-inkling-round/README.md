# Inkling-2-Mini on `maya-ik2`: baseline re-check, DSpark drafter and a Q8_0-dense re-type (2026-11-23)

**What**: the 2026-11-23 optimization round on the `inkling2-mini-unc` / `262k-maya` setup. Asked by the user:
"seguir mejorando nuestro setup de inferencia para ese modelo pudiendo probar de todo lo que tenga sentido y pueda
servirnos, pero de forma priorizada". Plan and log: `odd/tasks/inkling-tuning-2026-11-23.md` (local only).

**Conclusion**: re-typing the Abiray file's output head and its 176 non-expert attention/conv matrices from IQ4_NL /
Q6_K to Q8_0 (experts byte-identical, so the uncensored edit is untouched) makes `maya-ik2` take its planar Q8
decode path: **decode +7-11%** (106.1 / 98.2 / 90.0 / 68.9 tok/s at 512 / 8K / 32K / 128K), prefill +2-3%, for
1.3 GiB more VRAM, with GSM8K 187/192 vs. 188/192, 0/8 refusals and working tool calls. Wired as
`inkling2-mini-unc-q8d` / `262k-maya`. The official DSpark drafter still does not run: the original file fails the
head check, the re-typed one fails inside rocBLAS (`hipErrorInvalidImage`).

## Setup

| | |
|---|---|
| Date | 2026-11-23 |
| GPU | RX 7900 XTX 24 GB (gfx1100), 272 W cap (`power1_cap` 272000000) |
| OS / runtime | CachyOS, kernel 7.3.5-2-cachyos, `hip-runtime-amd` 10.1-2.1 (Arch `libamdhip64` workaround), `rocblas` 10.1-2; the engine links the ROCm 10.0 pip SDK's `librocblas.so.5` |
| Engine | `GodGMN/maya-inkling-mini` `hip-port` `2b31ffeaa` (`build-ik2/maya-ik2`), production env `ik2-abiray-paged.json` (port preset + `IK2_PAGED_KV=1`, `ROCBLAS_TENSILE_LIBPATH=/opt/rocm/lib/rocblas/library`), `--chunk 2048`, KV E4M3 |
| Model A | Abiray `Inkling-2-Mini-Uncensored-IQ4_NL.gguf` (13.90 GB, sha256 `e6680ab9…`): 225 IQ4_NL, 1 Q6_K (`output.weight`), 478 F32 |
| Model B | A re-typed by `raw/retype_q8.py`: 177 Q8_0 (head + non-expert 2-D IQ4_NL), 49 IQ4_NL (experts, `token_embd`), 478 F32; 15,357,929,856 bytes, sha256 `375eea1b81c0512ee8c891527de595ec0ce8048527bde69ca72f6b45ddc5f888`; head max abs dequant diff 0.38% of max abs |
| Drafter | `thinkingmachines/Inkling-2-Mini` `mtp.safetensors` rev `b85c3cfa`, sha256 `7c3b6513…` (matches the port's `docs/HIP-PORT.md`) |
| Bench | the port's `tools/ik2_bench.py` via `raw/bench.sh` / `raw/bench_m.sh`: 50,206 token IDs of this repo's docs cycled to each depth, uncached, 129 generated tokens, 3 repeats (2 at 262K), median |

## Results (tok/s, median; all repeats in `raw/bench.jsonl`)

| Depth | A decode | A prefill | B decode | B prefill | B / A decode |
|---:|---:|---:|---:|---:|---:|
| 512 | 95.74 | 2,207 | 106.05 | 2,276 | +10.8% |
| 8,192 | 88.15 | 3,367 | 98.23 | 3,429 | +11.4% |
| 32,768 | 82.26 | 2,864 | 90.01 | 2,960 | +9.4% |
| 131,072 | 64.22 | 1,873 | 68.85 | 1,929 | +7.2% |
| 262,144 (mean of 2) | 51.21 | 1,302 (repeat 2) | 53.61 | 1,298 (repeat 2) | +4.7% |

At 262,144 the first repeat of each start includes warm-up (prefill 857 / 884), so prefill is the second repeat.
A at temperature 1.0 (`plain-t1`): 94.74 / 87.79 / 81.01 / 63.84, so greedy numbers stand for production sampling.
A's figures match the 2026-11-22 tuned run (95.0 / 63.6 at 512 / 128K). Outliers: one 32K repeat at 28.4 (A, t=1)
and 81.1 (B); medians unaffected.

VRAM (engine log, 262,144 reserved): A dense 0.7 GiB, 4,824 MiB free before graph capture; B dense 1.1 GiB,
3,498 MiB free. Serving B through `serve/server.py` at 262K: 22,304 MiB device-wide (rocm-smi).

## Quality (B vs. A)

- GSM8K greedy, 4,096 cap, the port's `tests/ik2_gsm8k.py`: questions 0-95 A 95 / B 94 (B also misses 40);
  questions 96-191 (`raw/gsm8k-pair.sh`) A 93 / B 93 with the same wrong set {100, 119, 161}. Total **A 188/192,
  B 187/192**.
- Gray-zone refusals (the 8 prompts of the 2026-11-22 round, temperature 0): **0/8** keyword refusals; prompt 5's
  answer was cut by the server's loop guard ("a 15-token block 6 times ... at token 462"), which A did not hit. One
  sample, cause not separated from run-to-run variance.
- Tool call + second turn (`agent_check.py`, 12,152-token system prompt): valid `read_file` call, 12,216 / 12,253
  prompt tokens reused, correct answer.

## DSpark drafter (not working)

- A + `--draft mtp.safetensors` (`IK2_DRAFT_CTX=65536`): exits before ready with `--draft: the output head is
  neither FP16 nor planar Q8_0` (`src/ik2/ik2_main.cu:5065`; A's head is Q6_K).
- B + `--draft`: passes that check, then `rocBLAS error from hip error code: 'hipErrorInvalidImage':200` /
  `maya-ik2: drafter: fold b: cuBLAS 6` (`cublasSgemv` at `src/ik2/ik2_draft.cu:438`). Same with the system
  `librocblas.so.5` 10.1 preloaded (`LD_LIBRARY_PATH`). Not a VRAM fit (18.0 GiB free after the dense upload).
- Even when it loads, serving needs block verification (`ik2_main.cu:5383-5393`: planar Q8 attention + head, all
  experts resident); B satisfies the type part. The author measured 117.2 -> 137.5 tok/s at 512 and a story 116 ->
  89.5 with it (`docs/HIP-PORT.md:364`).
- Next: rebuild `maya-ik2` against a rocBLAS that ships gfx1100 kernels for that GEMV (or patch the fold to the
  engine's own kernel), then rerun `bench_m.sh ... --draft`.

## Commands

```bash
python3 -I results/20261123-inkling-round/raw/retype_q8.py           # A -> B, with self-check asserts
results/20261123-inkling-round/raw/bench.sh plain-c2048 2048 262144 512,8192,32768,131072 3
MODEL=<B> results/20261123-inkling-round/raw/bench_m.sh q8d-plain 2048 262144 512,8192,32768,131072 3
MODEL=<B> IK2_DRAFT_CTX=65536 results/20261123-inkling-round/raw/bench_m.sh q8d-draft 2048 262144 512,8192,32768,131072 3 \
  --draft <models_root>/Inkling-2-Mini-dspark/mtp.safetensors
LABEL=B results/20261123-inkling-round/raw/gsm8k-pair.sh <B> 96 <out-dir> 96
python3 scripts/launch.py inkling2-mini-unc-q8d --profile 262k-maya
```

## Not run, with reason

- Strata v0.2.20 `strata-inkling` 0.1.66 (rx7900 HIP tarball): reads UD-Q4_K_XL / Q8_0 / UD-IQ* only, not IQ4_NL;
  an uncensored test needs a 17.6 GB download (onemunanoyo Balanced v2, NVFP4 experts) and no gfx1100 Inkling number
  exists to beat 106 tok/s. Deferred.
- llama.cpp b12651: the two changes that matter (#32752 chunked mask, #32740 FA compact bias) are still open PRs.
- Side-request state keeping: alesha-pro `IK2_SLOT_KEEP` (merged 2026-11-23) does not merge cleanly into the HIP
  port (conflicts in 6 files); the port's `IK2_CACHE_SLOTS` divides the reserved context evenly (2 x 131K at 262K).

## Candidate: bartowski `nokeepai_Inkling-2-Mini-Unbound-IQ4_NL` (not adopted)

The best-rated uncensored file the engine can almost read (Hugging Face survey in
[`inkling-2-mini.md`](../../docs/models/inkling-2-mini.md#hugging-face-survey-2026-11-23)): Unbound v1.0 edit, head and
attention already Q8_0. File 16.11 GB, sha256 `06a81628ae3dea0e5b2275adf770d86d620f488bc31578addf7da132f42a7215`.

- As published it does not load: `maya-ik2: blk.0.ffn_gate_up_exps.weight: a row is not whole Q6_K blocks`
  (`gate_up` of layers 0-4 are Q6_K / Q5_K). `retype_q8.py` now also re-types K-quant expert tensors to Q8_0:
  17,293,833,632 bytes, sha256 `420b084a69993955c566620091eb15d0b00ba3dfca2caccc8c60d73c2ae078c8`; experts 14.4 GiB,
  **1,886 MiB free before graph capture** at 262K (our q8dense: 3,498).
- Same bench, medians: decode 103.5 / 96.8 / 89.5 / 68.6 tok/s at 512 / 8K / 32K / 128K (q8dense 106.1 / 98.2 / 90.0 /
  68.9); prefill 1,454 / 3,090 / 2,295 / 1,206, with 128K repeats at 1,206 / 622 / 1,771 (q8dense 1,929, stable).
- GSM8K greedy: 93/96 (0-95) + 92/96 (96-191) = **185/192** (Abiray 188, q8dense 187).
- Verdict: no better on anything this repo measures, and prefill at depth is slower and unstable with little VRAM
  margin. Its advantage (useful answers 51.6/62.1% vs. 34.3/43.0%) is the publisher's own judge, not reproduced here.
  File kept on disk until the user decides.

## `IK2_SUFFIX` prompt lookup (q8dense, partial: prose regression not measured)

The engine proposes a continuation from the request's own tokens and verifies it with the target model (no drafter).
`raw/suffix-run.sh`: the port's `tests/ik2_copy_edit.py --direct-answer --repeats 3` (inventory copy and single edit;
`--workload python` renames one function and returns the whole file), production env, `--ctx 262144 --chunk 2048`,
q8dense file, greedy. Every answer was exact at every window. Median decode tok/s (all rows:
`raw/suffix-scores.jsonl`):

| Window | Inventory copy | Inventory edit | Python rename |
|---:|---:|---:|---:|
| 0 (off) | 104.35 | 104.19 | 103.55 |
| 64 | 605.84 | 463.75 | 469.75 |
| 128 (cap) | **849.42** | **533.46** | **501.13** |

Window 128 left 3,310 MiB free before graph capture at 262K (3,498 without). Not yet measured (bench stopped at
session close): decode on novel text with the window on, greedy and temperature 1.0, and the window through
`serve/server.py`. Next: `IK2_SUFFIX=128 bench_m.sh ... 512,8192,32768,131072 3` with and without
`--temperature 1.0`, then an HTTP copy/edit request; wire into `262k-maya` only if prose decode stays within noise.

## Round 2 (2026-11-23, afternoon)

Plan and log: `odd/tasks/inkling-round2-2026-11-23.md` (local only). Same machine, engine build (`2b31ffeaa`), env
and 272 W cap as above, unless a section says otherwise.

### `raw/suffix-run.sh` review fixes

- Default windows were `"${@:-0 8 64 128}"`, one word, so a call without windows ran a single invalid
  `IK2_SUFFIX="0 8 64 128"`; now an array `(0 8 64 128)`.
- The out dir is made absolute before the script `cd`s into the engine tree (a relative one wrote under the engine).
- A failed engine run or scoring now makes the script exit 1 (it reported nothing and exited 0).
- `raw/suffix-scores.jsonl` mixed `== window` headers and `grep` lines with the JSON rows; it is now 27 JSON objects
  with `window` and `args` (workload) fields, rewritten from the same rows (no number changed), and the script
  appends in that format.

### Upstream recheck (DSpark retest trigger): not triggered

Checked 2026-11-23 ~13:10 UTC.

- `mw00/project-maya#1154` (GGUF DSpark drafter, Q8_0 head fold in chunks): **open**, 18 commits, last update
  2026-11-23T10:38Z, not merged.
- `GodGMN/maya-inkling-mini` `hip-port`: 32 commits after our `2b31ffeaa`, head `4f2b2ff`. None touches
  `src/ik2/ik2_draft*` and no message mentions the drafter. Source changes (5 files, +292/-68): `IK2_KV=fp4-global`
  (E2M1 global KV, E4M3 sliding), `--lora` for GGUF attention-output adapters (`e5f1a1b`), multi-slot fixes, and the
  server loop guard now recognizes reasoning and tool segments (`fe01a42`, possibly the cause of the q8dense
  refusal-prompt-5 cut above; not tested).
- `alesha-pro/maya-inkling-mini` `main`: last commit `fcd523f` (2026-11-23, merge of `IK2_SLOT_KEEP`), nothing new
  on HIP.
- Two scout leads on our `hipErrorInvalidImage` ruled out locally: the Tensile library is flat (150 `gfx1100`
  files in `/opt/rocm/lib/rocblas/library`, no per-arch subfolder), and `rocminfo` shows only `gfx1100` (no iGPU to
  mask). A scout claim that mixed projection types drop `maya-ik2` off the resident path (project-maya #1173) does
  not apply here: every q8dense log says "tokens take the resident path, one graph replay per decode step".

So DSpark was not retested.

### `IK2_SUFFIX` on the generation bench: not neutral, not wired

**Hypothesis**: prompt lookup costs nothing when the continuation is not in the prompt, so window 128 could be on by
default. **Run** 2026-11-23 13:00-13:23 UTC, q8dense file, same session, in this order: plain greedy, plain t=1.0,
sfx128 greedy, sfx128 t=1.0, then sfx64 / sfx16 greedy and a closing plain greedy control (512 / 8K / 32K):

```bash
MODEL=<q8dense> raw/bench_m.sh r2-q8d-plain-g 2048 262144 512,8192,32768,131072 3 [--temperature 1.0]
MODEL=<q8dense> IK2_SUFFIX=128 raw/bench_m.sh r2-q8d-sfx128-g 2048 262144 512,8192,32768,131072 3 [--temperature 1.0]
MODEL=<q8dense> IK2_SUFFIX=64 raw/bench_m.sh r2-q8d-sfx64-g 2048 262144 512,8192,32768 3     # and IK2_SUFFIX=16
```

Median decode tok/s (3 repeats; all rows in `raw/bench.jsonl`, variants `r2-*`):

| Depth | plain | sfx128 | sfx64 | sfx16 | control | plain t=1 | sfx128 t=1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 512 | 107.02 | 159.01 | 159.60 | 117.65 | 106.14 | 105.18 | 105.70 |
| 8,192 | 98.31 | **90.46** | 90.91 | 90.65 | 97.78 | 96.82 | 94.05 |
| 32,768 | 90.08 | **78.34** | 78.72 | 79.50 | 90.01 | 89.20 | 100.63 |
| 131,072 | 68.93 | 707.18 | - | - | - | 68.38 | 490.42 |

- The controls agree within 1% (107.0 -> 106.1, 98.3 -> 97.8, 90.1 -> 90.0), so the deltas are not drift.
- Greedy at 8K and 32K loses 7-8% and 12-13% at every window: the cost does not come from the window width. The
  engine's own counters show proposals mostly rejected on that text (e.g. "accepted 1/30 proposals").
- 128K is not novel text: `docs.ids` holds 50,206 tokens, so the 128K prompt repeats the corpus and the continuation
  is in it (prompt prefill unchanged, decode 7x). 512 also gains, because the docs' tables and lists repeat.
  32K repeats vary 76.5-109.7 with the suffix on (one hit-rich repeat each).
- At temperature 1.0 (production sampling) 8K is -2.9%, 32K +12.8%: mixed, and greedy coding work would pay the
  8-13%.

**Conclusion**: not neutral on prose, so not added to `262k-maya` (S3 condition). Keep it opt-in for copy/edit-heavy
sessions: `IK2_SUFFIX=128 python3 scripts/launch.py inkling2-mini-unc-q8d --profile 262k-maya`.

### `IK2_SUFFIX=128` through `serve/server.py` (HTTP)

2026-11-23 ~13:26-13:32 UTC, `launch.py ... --background` with and without `IK2_SUFFIX=128` in the caller's
environment (the server copies `os.environ` into the engine's; checked in `/proc/<pid>/environ` and in every
response's `timings.draft_n`). Client `raw/http_copy_edit.py`: 40-line inventory, copy it and return it with one
line edited, `/v1/chat/completions`, temperature 0, `reasoning_effort: "none"`, 3 repeats; decode from the server's
`timings.predicted_per_second`. Rows: `raw/http-suffix.jsonl`.

| Case | sfx128 exact | sfx128 median tok/s | plain exact | plain median tok/s |
|---|---:|---:|---:|---:|
| copy (2,580 tokens) | 3/3 | 938.80 | 3/3 | 99.40 |
| one-line edit (2,581 tokens) | 3/3 | 948.30 | 3/3 | 100.90 |

Tool call (`results/20261122-inkling-maya-vs-fork/raw/agent_check.py`, 14,789-token prompt, t=1.0): both variants
produced a valid `read_file` call and a correct second turn with 14,853 prompt tokens cached (`raw/agent-*.txt`).
The engine's "suffix verification" startup line is not in the launcher log (the server only forwards tagged engine
lines), so check the variable in `/proc/<pid>/environ` or in `timings.draft_n`.

### `IK2_KV=fp8-global` (sliding layers FP16, global layers E4M3): no gain here, not adopted

**Hypothesis** (port author: GSM8K 188/192 vs. 184/192 with plain FP8, prefill -17% at 512): keeping the 40
sliding-window visits in FP16 improves quality at a small prefill cost. **Run** 2026-11-23 13:35-13:56 UTC, q8dense,
production env with `IK2_KV=fp8-global` in the caller's environment (engine log: "kv cache: fp8-global, 16-token
global pages"), then a closing plain control:

```bash
MODEL=<q8dense> IK2_KV=fp8-global raw/bench_m.sh r2-q8d-fp8g-g 2048 262144 512,8192,32768,131072 3
IK2_KV=fp8-global LABEL=F raw/gsm8k-pair.sh <q8dense> 0  <abs-out>/gsm-0  96   # reuses the q8dense request streams
IK2_KV=fp8-global LABEL=F raw/gsm8k-pair.sh <q8dense> 96 <abs-out>/gsm-96 96
MODEL=<q8dense> raw/bench_m.sh r2-q8d-plain-g-ctl2 2048 262144 512,8192,32768,131072 3
```

`gsm8k-pair.sh` used to overwrite the caller's variables with the preset's (`IK2_KV=fp8`); it now lets the caller's
win and prints `IK2_KV`, and the runs above printed `fp8-global`. The earlier rows did not set any preset variable
in the caller, so they are unaffected.

| | plain FP8 (first / closing control) | fp8-global |
|---|---:|---:|
| Decode 512 / 8K / 32K / 128K, tok/s | 107.02 / 98.31 / 90.08 / 68.93 and 105.79 / 97.41 / 89.82 / 68.78 | 108.02 / 98.92 / 91.17 / 69.26 |
| Prefill 512 / 8K / 32K / 128K, tok/s | 2,276 / 3,441 / 2,999 / 1,931 and 2,359 / 3,415 / 2,975 / 1,927 | **2,000** / 3,419 / 2,984 / 1,929 |
| K / V cache at 262,144 reserved | 4.2 GiB, 3,508 MiB free before graph capture | 4.5 GiB (4.47), 3,348 MiB free |
| GSM8K greedy 0-95 / 96-191 | 94 / 93 = 187, wrong {40, 93} / {100, 119, 161} | 94 / 93 = **187**, wrong {40, 93} / {119, 163, 182} |

Decode within ~1% of the controls, prefill -12 to -15% at 512 only (the author's direction), 160 MiB less free VRAM,
and the same GSM8K score with the same misses on the first half. The author's +4 questions did not reproduce on this
file. **Conclusion**: no measured benefit, so `262k-maya` keeps `IK2_KV=fp8`. Per-question rows:
`raw/gsm8k-fp8global-{0,96}.jsonl`.

### Next cheap improvements, prioritized (scouts 2026-11-23, not yet measured here)

Ranked by expected gain per effort for this setup. Scout claims are leads until fetched; the ones marked
"checked" were verified against the source or locally.

| # | Candidate | Expected gain | Effort | Evidence |
|---:|---|---|---|---|
| 1 | Opt-in `IK2_SUFFIX=128` for copy/edit-heavy agent sessions | ~9x decode on copied spans (measured above), -8 to -13% on novel greedy text | none (env var at launch) | measured |
| 2 | Rebuild `maya-ik2` at `hip-port` `4f2b2ff` in a separate build dir, rerun the round's bench + GSM8K | server loop guard that recognizes reasoning/tool segments (`fe01a42`, maybe the q8dense refusal-prompt cut), multi-slot fixes; speed unknown | one build + one bench session | checked (`git log`, 32 commits) |
| 3 | Uncensored edit as a `--lora` attention-output adapter on the stock ggml-org IQ4_NL (needs #2) | lets the vendor-like file run with the OpenUncensored edit and no re-type; quality vs. q8dense unknown | convert the 1 MB PEFT LoRA to GGUF | checked (`--lora` in `ik2_main.cu` at `4f2b2ff`); adapter conversion not tried |
| 4 | `IK2_KV=fp4-global` (needs #2) | more context or slots in the same VRAM; quality per the author's FP8-vs-FP4 tables | env var | checked (`docs/HIP-PORT.md` at `4f2b2ff`) |
| 5 | `IK2_RG_SLOTS` (short-prompt routing groups) | chat turn of 12 new tokens 118 -> 56 ms (project-maya SETTINGS.md, CUDA) | env var | scout, not fetched |
| 6 | GPU undervolt at the same 272 W cap | +3.3% decode in one field report (60.24 vs. 58.29 tok/s) | needs `amdgpu.ppfeaturemask` + reboot (user decision) | scout, not fetched |
| 7 | `pp_power_profile_mode` COMPUTE | low prior: single-card lanes gained nothing in the one published A/B | 2 sysfs writes | scout, not fetched |

Ruled out: per-arch Tensile folder (flat here), iGPU masking (none), the project-maya #1173 resident-path issue
(resident path confirmed), `HIP_FORCE_DEV_KERNARG` (already the default), `GPU_MAX_HW_QUEUES` > 4 (documented as
unpredictable), `IK2_BATCH_PREFILL` changes (AMD builds use their own batched path), DSpark until #1154 or a HIP fix.
