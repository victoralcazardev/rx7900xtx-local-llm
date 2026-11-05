# Huihui Qwen3.8-27B abliterated UD-DW-Q4_K_M: context size and speed (2026-11-05)

**Conclusion:** with the production flags (KV `q8_0`/`q5_1`, MTP n=3 + `ngram-map-k4v`, `-ub 256`) this
Q4_K_M runs at **131,072 context (128K)** with a 22.84 GB process peak, leaving ~2.9 GB of the card's
25.75 GB for the desktop. 147,456 (144K) also runs, but leaves ~2.3 GB, the margin that has already cost
a KWin session with the default profile. 196,608 (192K) does not fit: it crashed the desktop.
Added to `models.toml` as `huihui-q4km-mtp` / `128k-q8q51-mtp`, opt-in; the IQ3_S stays the default.
**Update (same day):** the GGUF was deleted and the entry removed at the user's request; the GSQ-RCO
IQ3_S-mtp of the same model runs at 262K instead (`results/20261105-huihui-iq3s-262k/`).

## Setup

- Model: [`huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF`](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF)
  file `Huihui-Qwen3.8-27B-abliterated-UD-DW-Q4_K_M.gguf`, 16,551,316,384 bytes. Card: "UD-DW series come
  from unsloth/Qwen3.8-27B-GGUF. Only layers 22 to 52 (0-based indexing) have been ablated"; no sampling
  stated. GGUF (`scripts/gguf_info.py`): arch `qwen35`, 65 layers, native context 262144, NextN head
  present, `<think>` template with `reasoning_effort`, `general.sampling` temp 1.0 / top_p 0.95 / top_k 20.
- Engine: `hip-kvmix` b11846 + `pr30792-q5_1.patch` (the production engine; no new build needed, same
  architecture as the IQ3_S). 272 W power cap, temperature 0, desktop using ~0.6 GB VRAM at start.
- Speed: `bench/spec_depth_bench.py --run --depth <D> --ctx <C> --variants n3-map --reps 1 --extra "-ub 256"`
  under `systemd-inhibit`: D 115000 / C 131072 and D 130000 / C 147456. Argv in `command-<ctx>.json`, rows
  in `summary-<ctx>.jsonl`.
- Launcher check: `scripts/smoke.py huihui-q4km-mtp` with the full production argv
  (`--reasoning-effort medium`, `--cache-ram 12288`): real content, 62.2 tok/s at empty context.

## Memory

Load at `-c 131072`, KV `q8_0`/`q5_1` + MTP (`buffers-131k.txt`): weights 15,092 MiB on ROCm0 (+682 MiB
CPU-mapped), main KV 3,712 MiB, MTP KV 512 MiB, recurrent state 598.5 MiB, compute ~820 MiB.

| Context | Process VRAM peak (`amd-requested-vram`) | Left of 25.75 GB | Evicted | Outcome |
|---|---|---|---|---|
| 196,608 | 25.38 GB (23.64 GiB) during prefill | ~0.4 GB | 629 MB at ~80K tokens | Desktop crash (below); bench aborted |
| 147,456 | 23.47 GB (21.86 GiB) | ~2.3 GB | 0 | Passed |
| 131,072 | 22.84 GB (21.27 GiB) | ~2.9 GB | 0 | Passed, adopted |

Measured peaks grow ~38.5 KB per extra context token ((23.47 - 22.84 GB) / 16,384 and (25.38 - 22.84 GB) /
65,536); main KV + MTP KV alone account for 33.8 KB ((3,712 + 512 MiB) / 131,072).

**Desktop impact of the 192K run (18:41):** the kernel logged repeated `amdgpu: Not enough memory for
command submission`, Brave was killed, KWin stalled for a few seconds and the Plasma panel stopped
redrawing until `systemctl --user restart plasma-plasmashell`. Keep 2-3 GB of VRAM free for the desktop.

`--fit on` was not usable for this search: with `-ngl all` it aborts ("n_gpu_layers already set by
user"), and without it the `q8_0`/`q5_1` + MTP run crashed with a segmentation fault right after creating
the MTP draft context. Not investigated further.

## Speed

Cached rep (rep 2; rep 1 includes the prefill):

| Fill / context | Task | tg (tok/s) | MTP accepted / drafted |
|---|---|---|---|
| 115K / 131,072 | essay | 36.58 | 255 / 429 (0.59) |
| | copy | 102.26 | 362 / 387 (0.94) |
| | code | 31.95 | 235 / 491 (0.48) |
| 130K / 147,456 | essay | 37.46 | 266 / 398 (0.67) |
| | copy | 98.27 | 363 / 384 (0.95) |
| | code | 30.93 | 238 / 481 (0.49) |

Prefill: 551.6 tok/s for 114,983 tokens, 528.3 tok/s for 129,983 tokens. Not comparable to the IQ3_S's
240K numbers (different depth, different greedy text).

## Not run

Coding suite, KV quality (KLD), retrieval, any comparison against the IQ3_S at the same depth.

## Harness

Written before the compaction change of the same day: with the 70% threshold (~183K) a harness session could
overflow this 131,072 context. Since then the harness configs advertise a smaller window for `local-262k`
(omp 131072 x 70% = 91,750 tokens; Gentle Shell 108544 - 16384 = 92,160), so the harness compacts first;
91,750 + 32,768 `maxTokens` = 124,518 < 131,072.
