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
