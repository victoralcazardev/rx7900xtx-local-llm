# Inkling-2-Mini-Uncensored AD-Q4_K: first inference, upstream b12633 vs. the GodGMN RDNA3 fork

First real run of the uncensored Inkling-2-Mini file chosen in `odd/tasks/engine-b12633-inkling.md`
(T5/T6): does upstream llama.cpp fit it at 262K on this 24 GB card, and does the third-party
GodGMN fork? **Smoke only**: one short prompt per arm, no long-context fill, no quality suite, no
`llama-bench`, no PPL. The numbers below compare *fits*, not engines.

## Model

| | |
|---|---|
| Repo | [`AtomicChat/Inkling-2-Mini-Uncensored-GGUF`](https://huggingface.co/AtomicChat/Inkling-2-Mini-Uncensored-GGUF) |
| File | `Inkling-2-Mini-Uncensored-AD-Q4_K.gguf`, 16,525,559,776 bytes (15.39 GiB), downloaded 2026-11-22 |
| SHA256 | `36e99f1f56ca33cb356f19d7e3822938f65af1cde978ad13170238928d4c955f` (local `sha256sum`, matches the repo's list) |
| Vision | `mmproj-Inkling-2-Mini-Uncensored-F16.gguf`, 639,348,448 bytes, SHA256 `5a72e0b6e2bef13c3f455f4edb85df0c752b92ff76ab46af879eae088163efe6`; **not loaded** (vision off, as in the 27B profiles) |
| Layout (header read 2026-11-22) | `inkling2_loop`, 24 blocks, 0 per-expert scale tensors, so it loads on unpatched upstream since b12591 |

## Engines

| | Upstream | Fork |
|---|---|---|
| Engine | [`../20261122-engine-b12633/`](../20261122-engine-b12633/README.md) | [`../20261122-inkling-rdna3-fork/`](../20261122-inkling-rdna3-fork/BUILD.md) |
| Source | llama.cpp tag `b12633` = `9c10c94e1` + local `pr30792-q5_1` patch | `GodGMN/llama.cpp` branch `inkling-rdna3` = `cb0e46960` (tag `b12600` + 6 commits), unpatched |
| `--version` | `1.0.0-dev (build 12633, commit 9c10c94e1)` | `1.0.0-dev (build 12606, commit cb0e46960)` |
| `libggml-hip.so` | `8c80878fb2c3e652b3e5eecb0c6c921676ea22737d6568b787f73fe5c0f1bf23` | `0734ce9771709d07b75473095cccd93c0b8e549766d0819ebc8aa2dc94367096` |

Both are gfx1100 builds of the same recipe ([`../../docs/ENGINES.md`](../../docs/ENGINES.md)) and both
ran against Arch's generic `libamdhip64` 10.1 symlinked into the engine folder, because the CachyOS
10.1 build SIGSEGVs every HIP program ([`../../docs/DECISIONS.md`](../../docs/DECISIONS.md), row
2026-11-22). The fork adds an in-kernel relative-bias attention path (`INK_REL_BIAS`,
`INK_FA_REL_BIAS`) and fused Inkling HIP kernels; upstream builds a dense bias mask instead.

## Protocol

One request of 33 prompt tokens (a one-line "iterative Fibonacci, code only" ask), sent twice
back to back per arm so the second turn runs on a warm slot (29 of 33 tokens cached); the upstream
b12633 64K arm ran one turn only. Temperature 0 / greedy (sampler dump in
`raw/upstream-b12633-fit-262k-q8q51.log`: `temp = 0.000`, `top_k = 0`, `min_p = 0.000`). One run per
arm, one context setting per run, no warm-up repetition, GPU otherwise idle (no other HIP process).
The runner script was not kept; the flag set below is what the logs show (`n_ctx_slot`, KV types,
verbosity, and whether the `--fit` step ran), not a verbatim command line.

```text
<engine>/llama-server -m ~/IA/Modelos/Inkling-2-Mini-Uncensored-AD/Inkling-2-Mini-Uncensored-AD-Q4_K.gguf \
  -c 262144 -ctk q8_0 -ctv q5_1 -np 1 --port 8090            # upstream: the --fit step ran
<engine>/llama-server -m ... -c 65536 -ctk f16 -ctv f16 -np 1 --port 8090
# then: POST /v1/chat/completions, stream, temperature 0 (raw/*.json are the responses)
```

## Result 1: upstream b12633 does not fit 262K

`--fit` projection for `-c 262144` with KV `q8_0`/`q5_1`, before any offload
(`raw/upstream-b12633-fit-262k-q8q51.log`):

| Component | MiB |
|---|---|
| Model (49 layer parts, GPU) | 15,279 |
| Context (KV `q8_0`/`q5_1`, 262,144 cells) | 3,810 |
| **Compute buffer** | **12,765** |
| Projected total | 31,855 |
| Free device memory | 24,358 |
| Deficit vs. the 1,200 MiB free-memory target | 8,697 |

`--fit` then moved all MoE tensors to system memory and still found a 1,799 MiB deficit, so it
settled on 25 of 49 layer parts on the GPU (24 repeating layers), `CPU_Mapped model buffer
15,278.83 MiB`, host RAM ~17.6 GiB, and a KV cache split 1,856 MiB on the host + 1,856 MiB on the
device. Two earlier attempts that started at 262K without offload died at start:

```text
0.10.053.861 E graph_reserve: failed to allocate compute buffers
0.10.063.565 E srv  server_run_i: exiting due to model loading error
```

**The compute buffer, not the KV cache, is the wall**: 12,765 MiB against 3,810 MiB of KV. It is
the dense relative-bias attention mask upstream materializes per layer; the fork computes the bias
inside the kernel and has no such buffer. Measured KV for 262K `q8_0`/`q5_1` matches the arithmetic
in [`../../docs/models/inkling-2-mini.md`](../../docs/models/inkling-2-mini.md): K 2,176.00 MiB + V
1,536.00 MiB for the 8 global applications + 90.62 MiB of sliding-window cache (1,280 cells).

## Result 2: generation

| Engine | Context | KV (K/V) | Placement | Turn 1 tg | Turn 2 tg | pp (33 tok) | VRAM |
|---|---|---|---|---|---|---|---|
| upstream b12633 | 65,536 | f16 / f16 | all on GPU | 26.5 tok/s | — (one turn only) | 130.3 tok/s | 22,270 MiB |
| upstream b12633 | 262,144 | q8_0 / q5_1 | `--fit`: 25/49 layer parts on GPU, MoE in host RAM | 4.5 tok/s | — | 10.0 tok/s | 22,566 MiB (`--fit` self, host 17,577 MiB) |
| fork `cb0e46960` | 65,536 | f16 / f16 | all on GPU | 48.2 tok/s | 46.3 tok/s | 130.6 tok/s | 19,022 MiB |
| fork `cb0e46960` | 262,144 | q8_0 / q8_0 | all on GPU | 42.0 tok/s | 42.7 tok/s | 56.1 tok/s | 22,423 MiB |
| fork `cb0e46960` | 262,144 | q8_0 / q5_1 | all on GPU | 41.2 tok/s | 42.3 tok/s | 87.6 tok/s | 21,750 MiB |

- VRAM is what the runner reported after each run (device in use); the upstream 64K arm's 22,270 MiB
  against the fork's 19,022 MiB is consistent with the same dense-mask compute buffer at 64K.
- Every captured response implements an iterative `fibonacci`; five keep the `if n < 0: raise
  ValueError` guard and one (fork 64K f16, second turn) drops it, a different greedy reasoning path
  rather than a correctness failure. Responses: `raw/*.json` (reasoning included, 280-451 tokens);
  the upstream 262K `--fit` arm's text was not saved.
- Turn 2 is within ±2 tok/s of turn 1 in every arm (+0.7 for `q8_0`/`q8_0`, +1.1 for `q8_0`/`q5_1`,
  -1.9 for the 64K `f16` arm): the slot is warm, so this is run-to-run variation at this sample size,
  not a cache effect.

## Conclusion

1. **Upstream b12633 loads the file and runs it at 262K only by offloading MoE to the CPU**: 4.5
   tok/s generation and 10.0 tok/s prefill, far below any usable floor. Not a KV-quantization
   problem: the compute buffer alone is 12,765 MiB.
2. **The GodGMN `inkling-rdna3` fork fits 262K on the card** with both KV pairs (22,423 and 21,750
   MiB) at 41-42 tok/s, and is 1.8x faster at 64K f16 with 3.2 GiB less VRAM.
3. The model is parked without a `models.toml` entry: an experimental fork is not a licence to
   maintain a second engine for a model the user wants to wait on until Qwen4
   ([`../../docs/DECISIONS.md`](../../docs/DECISIONS.md), 2026-11-22). Owner doc, quant survey and
   resume triggers: [`../../docs/models/inkling-2-mini.md`](../../docs/models/inkling-2-mini.md).

## llama-bench

`llama-bench -fa 1 -ngl 99 -ub 256 -p 4096 -n 128 -r 1`, one repetition, same file:

| Engine | KV | Test | tok/s |
|---|---|---|---|
| GodGMN fork `cb0e46960` | q8_0/q8_0 | pp4096 / tg128 | 1663.36 / 50.13 |
| GodGMN fork | q8_0/q8_0 | pp4096 / tg128 @ d65536 | 888.96 / 45.53 |
| GodGMN fork | q8_0/q8_0 | pp4096 / tg128 @ d196608 | 413.05 / 26.19 |
| upstream b12633 | f16 | pp4096 / tg128 | 1054.18 / 26.74 |

At depth 0 the fork is 1.58x prefill and 1.87x decode; decode falls to 26.2 tok/s at 196,608 tokens.

## Not run

- Retrieval at depth, refusal checks, coding suite, PPL/KLD, vision (mmproj), MTP/DSpark
  drafters, and repeats (no per-arm repetition, so no variance estimate).
- Sampling above temperature 0 and the vendor's card sampling (`temp 1.0, top-p 1.0, top-k 0`); the
  smoke used greedy on purpose.

## Files

| File | Content |
|---|---|
| `raw/upstream-b12633-fit-262k-q8q51.log` | upstream `--fit` run at 262K: projection, offload decision, KV sizes, timings, memory breakdown (model-load and prompt-cache detail elided, marked inline) |
| `raw/upstream-b12633-fit-262k-q8q8-attempt.log`, `...-q8q51-attempt.log` | the two upstream 262K starts that died with `failed to allocate compute buffers` |
| `raw/upstream-b12633-64k-f16.log`, `.json` | upstream 64K f16 arm, server log and the response |
| `raw/fork-cb0e46960-64k-f16.log`, `.json` | fork 64K f16 arm |
| `raw/fork-cb0e46960-262k-q8q8.log`, `.json` | fork 262K `q8_0`/`q8_0` arm |
| `raw/fork-cb0e46960-262k-q8q51.log`, `.json` | fork 262K `q8_0`/`q5_1` arm |
| `raw/README.txt` | which command produced each file, and the path normalisation applied |

Personal paths in the raw files were replaced with `~` ([`../../docs/STYLE.md`](../../docs/STYLE.md) §7
allows that for raw evidence); the text is otherwise as recorded.
