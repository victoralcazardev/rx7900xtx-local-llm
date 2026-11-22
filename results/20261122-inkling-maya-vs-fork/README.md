# Inkling-2-Mini: `maya-ik2` HIP port vs. the GodGMN llama.cpp fork (2026-11-22)

**What**: the same file (Abiray uncensored IQ4_NL), the same token IDs and the same measuring script on both engines,
at the 272 W cap. Asked by the user: "intentemos aprovechar https://github.com/GodGMN/maya-inkling-mini".

**Conclusion**: `maya-ik2` is faster at every depth: decode +63% at 512, +45% at 32K, +24% at 128K and +5% at
262K; prefill 1.6-1.9x (at 262K, 1,138 vs. 599 tok/s: 3.8 vs. 7.3 minutes for a cold 262K prompt). It stays below
the author's 117 tok/s at 512 (here 94, at 272 W). Tuned (paged KV, `--chunk 2048`, below) it reaches 51.1 tok/s decode and 1,292 prefill at 262K, and scores 95/96 on paired GSM8K against the fork's 93/96.

## Setup

| | |
|---|---|
| File | Abiray `Inkling-2-Mini-Uncensored-IQ4_NL.gguf`, sha256 `e6680ab9…` ([validation](../20261122-inkling-abiray-iq4nl/README.md)) |
| `maya-ik2` | `GodGMN/maya-inkling-mini` `hip-port` `2b31ffeaa`, built with ROCm 10 ([build](../../docs/ENGINES.md#maya-inkling-mini-hip-maya-ik2-experimental-inkling-2-mini-only)); author's Radeon preset env (`docs/inkling2-mini/ik2-mini-gfx1100.json`: `IK2_KV=fp8`, WMMA prefill, `IK2_RESIDENT_ONLY=1`, ...) plus `ROCBLAS_TENSILE_LIBPATH=/opt/rocm/lib/rocblas/library`; `--ctx 393216 --chunk 1024`; log: every expert resident, KV 6.2 GiB |
| Fork | `llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix`, `-c 270336 -ctk q8_0 -ctv q8_0 -fa on -np 1 --ctx-checkpoints 10 -ngl all` (262,144 + the 129 generated tokens) |
| Script | the port's `tools/ik2_bench.py` (`--engine` for Maya, `--llama-url` for the fork's `/completion`): uncached prompt, greedy, 129 generated tokens (128 timed decode steps), 2 repeats, prompt start alternated between repeats |
| Tokens | 50,206 token IDs of this repository's `docs/ENGINES.md`, `docs/DECISIONS.md`, `docs/TRIED.md` and `docs/models/inkling-2-mini.md` (English prose and tables), cycled to each depth |
| GPU | RX 7900 XTX, 272 W cap (`power1_cap` 272000000) |

## Results (mean of 2 repeats; tok/s)

| Depth | Fork prefill | Fork decode | Maya prefill | Maya decode | Maya / fork decode |
|---:|---:|---:|---:|---:|---:|
| 512 | 1,380 | 57.6 | 2,265 (repeat 2; repeat 1 includes warm-up) | 94.1 | 1.63x |
| 8,192 | 1,641 | 56.4 | 2,931 | 89.8 | 1.59x |
| 32,768 | 1,436 | 54.2 | 2,517 | 78.6 | 1.45x |
| 131,072 | 882 | 44.5 | 1,668 | 55.1 | 1.24x |
| 262,144 | 599 | 37.8 | 1,138 | 39.6 | 1.05x |

Raw: `raw/maya.jsonl`, `raw/fork.jsonl` (one JSON line per request).

## Maya tuning sweep (one repeat per cell; tok/s, prefill / decode)

One knob changed per variant against the radeon preset (`IK2_KV=fp8`, `IK2_FLASH_WAVES=4`), same tokens, script and
272 W cap. `raw/maya-sweep.jsonl`, commands `raw/sweep-run.sh`, `raw/sweep-run2.sh`.

| Variant | 512 | 8,192 / 32,768 | 131,072 | 262,144 |
|---|---|---|---|---|
| baseline above (`--chunk 1024`, token-major KV) | 2,265 / 94.1 | 2,931 / 89.8 (8K) | 1,668 / 55.1 | 1,138 / 39.6 |
| `--chunk 2048` | warm-up / 68.2 | 3,210 / 89.4 (8K) | 1,782 / 54.9 | 1,157 / 39.5 |
| **`--chunk 2048` + `IK2_PAGED_KV=1`** | 1,191 / 95.0 | 3,356 / 88.0 (8K) | **1,894 / 63.6** | **1,292 / 51.1** |
| same, repeated | 994 / 94.7 | 2,922 / 80.9 (32K) | 1,889 / 63.2 | 1,286 / 51.0 |
| paged + `IK2_FLASH_WAVES=8` | 1,099 / 95.5 | 2,903 / 81.8 (32K) | 1,852 / 63.9 | 1,201 / 51.1 |
| paged + `IK2_FLASH_WAVES=2` | 1,113 / 94.9 | 2,741 / 81.8 (32K) | 1,659 / 63.8 | 1,006 / 50.5 |
| paged + `--chunk 1024` | 1,036 / 95.0 | 2,596 / 40.8 (32K, outlier) | 1,588 / 63.6 | 1,214 / 51.1 |

Prefill at 512 is the first request of each engine start (warm-up included). **Chosen: `--chunk 2048` +
`IK2_PAGED_KV=1`, four waves**: decode +15% at 128K and +29% at 262K over token-major KV, prefill +13%; against the
fork at 262K, decode 51.1 vs. 37.8 (+35%) and prefill 1,292 vs. 599 (2.2x). KV stays 6.23 GiB (16-token global pages)
and every expert stays in VRAM. The port's author reports page-layout parity (mean KL 0.0022 vs. an FP64 reference,
207/256 MMLU; `docs/HIP-PORT.md`, not re-measured here).

## Agent checks on the Maya server (paged config)

`serve/server.py --engine maya` with the chosen config (`--max-context 262144 --chunk 2048`, `IK2_PAGED_KV=1`), the
alesha-pro `549d734` tool-call parse fix applied:

- Gray-zone refusals (the 8 prompts of [the Abiray run](../20261122-inkling-abiray-iq4nl/README.md), temperature 0,
  `reasoning_effort: low`): 0/8 keyword refusals, all 8 answered (the "dirty jokes" answer is mild, as on the fork).
  `raw/refusal-maya-paged.json`.
- Tool call + second turn (`raw/agent_check.py`, a 12,152-token system prompt, temperature 1.0): turn 1 returned a
  valid `read_file {"path":"src/app.py"}` call (`finish_reason: tool_calls`, 4.5 s); turn 2 after the tool result
  reused 12,216 of 12,253 prompt tokens (`cached_tokens`) and answered correctly in 2.9 s.

## Paired GSM8K (quality gate)

First 96 questions of the OpenAI GSM8K test set (pinned commit `3101c7d5`), the port's `tests/ik2_gsm8k.py`: the same
token IDs for both engines, greedy, 4,096-token cap. Maya: `--serve-ik2 --ctx 8192 --chunk 2048` with the chosen
paged config; fork: `llama-server -c 8192 -ctk q8_0 -ctv q8_0 -fa on -np 1 -ngl all` scored through `--llama-url`.

| Engine | Correct | Truncated | Generated tokens | Decode (tok/s, all answers) | Wall |
|---|---:|---:|---:|---:|---:|
| `maya-ik2` paged | **95 / 96** | 0 | 28,794 | 95.5 | 319 s |
| GodGMN fork | 93 / 96 | 0 | 30,263 | 56.3 | - |

Both miss question 93; the fork also misses 12 and 40. A two-question gap on 96 is inside noise: the gate shows
no quality loss from Maya's E4M3 paged KV against the fork's `q8_0` KV, not a gain. Raw:
`raw/gsm8k-maya.jsonl`, `raw/gsm8k-fork.jsonl`, `raw/gsm8k-run.sh`.

## 262K retrieval

The port's `tests/ik2_retrieval.py` (local `%%` fix for Python 3.14): a seeded four-word phrase at 5%, 50% and
95% of a 261,888-token prompt of GSM8K distractor questions, `--direct-answer`, greedy, the same token IDs for both
engines. Maya: `--serve-ik2 --ctx 262144 --chunk 2048`, paged config; fork: `-c 262144 -ctk q8_0 -ctv q8_0 -fa on`.

| Engine | 5% | 50% | 95% | Cold prefill (s) |
|---|---|---|---|---|
| `maya-ik2` paged | exact | exact | exact | 203 / 204 / 233 |
| GodGMN fork | exact | exact | exact | ~430-437 |

Raw: `raw/retrieval-262k.jsonl`, `raw/retrieval-run.sh`.

## Limits

- Quality: GSM8K 96, 8 refusal prompts and one tool-call exchange only; one 262K retrieval per position; the coding suite is not run on `maya-ik2` yet.
- Two repeats per cell; the fork's 131,072 repeats differ by 8% (927.8 / 835.8 prefill).
- The author's 117 tok/s used ggml-org IQ4_NL (Q8_0 experts in layers 20-23) and an unstated power cap.
