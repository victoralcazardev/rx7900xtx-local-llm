# Huihui Qwen3.8-27B abliterated GSQ-RCO IQ3_S-mtp at 262K, and llama.cpp v0.9.0 vs. b11846 at 64K (2026-11-05)

**Conclusion:** the uncensored Huihui GSQ-RCO IQ3_S-mtp runs the default's 262K profile unchanged (process
peak 22.12 GiB, 0 evicted) and is added to `models.toml` as `huihui-iq3s-mtp` / `262k-q8q51-mtp`, opt-in.
llama.cpp v0.9.0 + the local q5_1 patch is **not adopted**: 4.6% slower decode on identical greedy text
(`copy`), 2.2% slower prefill, same VRAM. b11846 stays the `hip-kvmix` engine.

## Setup

- Model: [`huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF`](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF)
  file `Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf`, 12,120,016,416 bytes, sha256
  `eea0638e283433e27b0edbd409b552be467a75ecc777d91c51db554c0a644c19` (matches the Hugging Face `X-Linked-ETag`).
  GGUF: arch `qwen35`, 65 layers, native context 262144, NextN head, `<think>` template,
  `general.sampling` temp 1.0 / top_p 0.95 / top_k 20. The card states no sampling.
- Engines: A = `llama-b11846-pr30792q51-linux-rocm10-gfx1100-kvmix` (production). B =
  `llama-v0.9.0-pr30792q51-linux-rocm10-gfx1100-kvmix`: tag v0.9.0 (commit `cd959ba`, `--version`
  `0.9.0-dev (build 1)`), 313 commits after b11846, same recipe ([`docs/ENGINES.md`](../../docs/ENGINES.md)):
  `tests-kvmix-cases.patch` (offsets 325 and 410) and `pr30792-q5_1.patch` without its test hunk, both clean.
  `--help` adds only `--models-memory-margin` (router mode); no default changed.
- Correctness on B: `test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=q8_0'` 30/30 OK.
- Speed: `bench/spec_depth_bench.py --run --depth 64000 --ctx 262144 --variants n3-map --reps 1 --extra "-ub 256"`,
  A then B back to back, same model, under `systemd-inhibit`, 272 W cap, temperature 0. No 240K run (user
  request). Argv in `command-<engine>.json`, rows in `summary-<engine>.jsonl`.
- Launcher: `scripts/smoke.py huihui-iq3s-mtp` (production argv, engine A): real content, 76.8 tok/s.

## Results

Cached rep (rep 2), 64K fill:

| Task | A b11846 (tok/s) | B v0.9.0 (tok/s) | Change | Accepted / drafted A → B | Greedy text |
|---|---|---|---|---|---|
| essay | 50.60 | 47.04 | -7.0% | 260/413 → 248/448 | differs |
| copy | 166.79 | 159.18 | **-4.6%** | 374/384 → 374/384 | **identical** |
| code | 43.05 | 40.92 | -4.9% | 236/487 → 226/517 | differs |

Prefill (63,983 tokens): A 674.1 tok/s, B 659.5 tok/s (-2.2%). Process VRAM peak: A 22.116 GiB, B
22.122 GiB; 0 bytes evicted on both.

`copy` is the clean comparison: same text and same MTP acceptance, so the 4.6% is engine speed. `essay` and
`code` produce different greedy text with lower acceptance on B, so their gap mixes engine and draft effects.
One rep per arm: earlier engine A/Bs found reps within an arm agree within 1% on identical text
([`20261018-engine-b11718-vs-b11454-240k`](../20261018-engine-b11718-vs-b11454-240k/README.md)).

## Not run

Coding suite, retrieval, KV quality for the Huihui model; the 240K pair for the engine; where in the 313
commits the slowdown comes from.
