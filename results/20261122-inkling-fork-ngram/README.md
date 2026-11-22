# Inkling-2-Mini n-gram self-speculation on the GodGMN fork (2026-11-22)

**What**: does `--spec-type ngram-map-k4v` or `ngram-mod` (proposals copied from the slot's own tokens, checked by
the target) speed up Inkling on the `hip-inkling` engine? The inference-optimization playbook
(alesha-pro/inference-optimization-playbook `53868e2`, `cases/inkling-2-mini.md`) reports 488.9 tok/s on a
509-token Python edit with copy proposals on an RTX 3090 (`maya-ik2` CUDA; not in the HIP port).

**Conclusion (partial)**: at 32K, no arm slowed decode. `ngram-map-k4v` helped only on the copy task:
68.4 tok/s against 55.5 (mean of warm repeats 2-3). `ngram-mod` helped every task:
essay 67.7 vs. 55.1, copy 104.7 vs. 55.5, code 66.9 vs. 54.8. But its pool is shared across requests, so repeats
2-3 reuse repeat 1's output, the same bias that kept it out of the Qwen profile
([TRIED](../../docs/TRIED.md)). Not adopted yet: the 400 generated tokens were all reasoning (the model never
reached the copy), and temperature 0 is not deterministic on this engine (every repeat has a different output
hash, also without speculation), so losslessness cannot be checked by hash.

## Setup

| | |
|---|---|
| Engine | `llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix` |
| Model | Abiray `Inkling-2-Mini-Uncensored-IQ4_NL.gguf` (sha256 `e6680ab9…`) |
| Flags | `-c 262144 -ctk q8_0 -ctv q8_0 -fa on -np 1 --ctx-checkpoints 4 -ngl all` + the arm's `--spec-type` (defaults otherwise); `raw/*.command.json` |
| Bench | `bench/spec_depth_bench.py --depth 32000 --reps 2 --variants none --extra "--spec-type <arm>"`: essay / copy / code prompts after a ~31.5K wikitext document, 400 output tokens, temperature 0; repeat 1 is the prefill warm-up |
| GPU | RX 7900 XTX, power cap 272 W |

Command: `raw/run.sh` (home path normalised to `~`).

## Results (decode tok/s, repeats 2 / 3; drafts accepted / proposed)

| Arm | essay | copy | code |
|---|---|---|---|
| none | 55.16 / 55.03 | 55.58 / 55.39 | 54.67 / 54.97 |
| `ngram-map-k4v` | 55.16 / 55.03 (no drafts) | 64.32 / 72.56 (68/68, 122/168) | 55.04 / 55.15 (no drafts) |
| `ngram-mod` | 73.46 / 61.85 (143/256, 78/128) | 115.61 / 93.76 (261/276, 247/357) | 73.20 / 60.67 (132/192, 71/187) |

All 27 outputs are readable text (no all-`?` output, cf. llama.cpp #32778 on ggml-org IQ4_NL). Raw:
`raw/<arm>.summary.jsonl`.

## Next

Re-run on a real coding-agent session replay (multi-turn edits, where the model does copy code), not
single-shot prompts whose budget the reasoning consumes.
