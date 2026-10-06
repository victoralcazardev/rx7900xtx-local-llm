# Tried and not adopted

Everything measured on this card (RX 7900 XTX, RDNA3, gfx1100) that was compared against the
adopted profile and either lost or was set aside. Dates and reasoning per decision are in
[`DECISIONS.md`](DECISIONS.md); the current recommendation is in [`STATUS.md`](STATUS.md). Each
row: what was tried, the key numbers, where the evidence is.

## Flags and server settings

| Item | Result | Evidence |
|---|---|---|
| `-ub 1024` / `-ub 2048` | No speed gain at depth. 1024: +590 MiB VRAM. 2048: +1.8 GiB, pp -1.7%, code tg -3.6% (128K fill). `-ub 256` is adopted at 262K (-350 MiB, pp -5%, same tg); default 512 stays best at 128K fill. `-ub 384` never measured. | [speculative.md](measurements/speculative.md#-ub-and-mtp-screening-at-128k-fill-272-w-2026-09-25), [memory.md](measurements/memory.md) |
| `--spec-draft-n-max 4` (and 5) | At 240K on the adopted flags: 21.4 tok/s at 66% acceptance vs. n=3's 23.3 at 71% (-8%). At 128K empty context: 45.8 tok/s at 31% vs. 60.6 at 56%. n=3 is +9-11% mean tg over n=2 at 190K/240K. Measured with upstream b11160 draft cost; a fork claims n=4/6 pays on an RTX 3090 ([SOURCES](SOURCES.md#cafe-llamacpp-fork-and-the-quimedesu-x-thread-2026-10-02)). | [speculative.md](measurements/speculative.md#n4-checked-again-at-240k-exact-adopted-flags--ub-256-2026-09-26) |
| `--spec-draft-p-min` 0.3 / 0.6 / 0.75 / 0.8 | 0.3 (n=2, 128K): within noise. 0.8 (n=3, 190K): acceptance 67% to 96%, speed unchanged. 0.60/0.75 (n=3, empty context, community `probe.py`): 68.9 to 66.2/59.8 tok/s. 0.5 and `--spec-draft-n-min` never measured. | [speculative.md](measurements/speculative.md) |
| `-ctkd q8_0 -ctvd q8_0` (quantized MTP draft KV) | Draft KV -480 MiB but its compute buffer +1,036 MiB: net +426 MiB VRAM. Kept at f16. | [memory.md](measurements/memory.md) |
| `-np` > 1 (extra slots) | A slot's prefill starves generation on the others. Vs. queuing through 1 slot: 2 slots + MTP 8.6% slower wall time, 2 slots without MTP 6.0% slower, 4 slots 25.6% slower. | [concurrency.md](measurements/concurrency.md#1-vs-2-vs-4-slots-mtp-onoff-2026-09-25) |
| `--ctx-checkpoints` default (32) vs. 4 | Warm-turn reuse is the same either way (189,467 of 190,000 tokens reused across a task switch). Kept at 4 to bound RAM. | [memory.md](measurements/memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29), [agent-traffic.md](measurements/agent-traffic.md) |
| Vision (`mmproj`) at 200K+ | VRAM/context cost not worth it; off by default at 262K. | [DECISIONS.md](DECISIONS.md) |
| Power: 303 W cap | 272 W (driver minimum) costs prefill -6% (487 to 459 tok/s at 190K) and tg128 ~-3.4% at empty context (39.35 to 38.0 tok/s, single uncontrolled sample), for a hotspot of 99°C vs. 100-106°C. 272 W adopted. Undervolt/further power tuning deferred; 290/303 W not pursued (303 W exceeds the 104°C bench ceiling). | [thermals-power.md](measurements/thermals-power.md), [results/20260925-longctx-quality-200k/](../results/20260925-longctx-quality-200k/) |

## Backend, toolchain and engines

| Item | Result | Evidence |
|---|---|---|
| Vulkan (b11160) | ROCm 39 tok/s vs. Vulkan 11-23 (2-3.5x). Vulkan's memory clock drops to 456-772 MHz while generating vs. ROCm's 1249 MHz. Re-tested with the clock pinned (2026-09-29): HIP still +63% tg at depth 0 and +18% at 64K. Reference only. | [engines.md](measurements/engines.md) |
| ROCm 7.2.4 compiler | tg 33.9 at 16K (-7.5%) vs. the ROCm 10 compiler build (36.8-36.9). ROCm 10.0.0 compiler adopted. | [engines.md](measurements/engines.md) |
| ROCm 10.0.0 runtime (TheRock, compiler kept at ROCm 10) | -1..-2% tg, ~-5% pp, much higher variance vs. the system 7.2.4 runtime. System runtime kept. | [engines.md](measurements/engines.md), [results/20260926-rocm-runtime-ab/](../results/20260926-rocm-runtime-ab/) |
| BeeLlama v0.4.7 + KVarN | KVarN KLD ~0.0020-0.0022, ~2.7x q8/q8 at every bit width; BeeLlama itself -18-22% tg vs. `hip-kvmix`. Speed screen (2026-10-03): kvarn5/kvarn4 tg64 @128K 10.53 vs. 16.64 tok/s (-37%), prefill 92.5 vs. 383.3. Side finding: `q8_0/q6_0` near-lossless, but BeeLlama-only. | [kv-quality.md](measurements/kv-quality.md#beellama-kvarn-kld-2026-09-26), [screen](../results/20261003-kvarn-beellama-screen/README.md) |
| `kvmix-vec4` patch | +20% ms/step vs. plain `kvmix` (worse). | [speculative.md](measurements/speculative.md) |
| `stew675/llama-cpp-rdna-boosts` (native q8 KV) | Only -2.5% ms/step; not worth maintaining a fork. | [ENGINES.md](ENGINES.md), [SOURCES.md](SOURCES.md) |
| PR #29827 port (chunked FA convert) | 240K: -0.39 GiB VRAM, code -2.9%, non-deterministic. | [results](../results/20261006-pr29827-port-b11454/README.md) |
| Lemonade b1331/b1332 | Its build does not enable the FA quant kernels K `q8_0` + V `q5_1` needs; A/B dropped. | [ENGINES.md](ENGINES.md) |
| `nasone32/llama.cpp-RDNA3-7900xtx-opt` | Older snapshot than b11160, no binaries; patches target RDNA3.5/RDNA4 or prefill, sparse attention is for another architecture. Discarded. | [ENGINES.md](ENGINES.md) |
| exllamav3-rocm (+ patched TabbyAPI) | Read-only audit found no code or license blocker; deprioritized: 15.3 GB EXL3 model leaves less VRAM headroom, author's numbers not comparable. | [ENGINES.md](ENGINES.md), [SOURCES.md](SOURCES.md) |
| vLLM (ROCm) and HyperQwen (CUDA) | Not run. HyperQwen's kernels are CUDA only. Mainline vLLM supports no 4-bit format on AMD; the one 7900 XTX number is 29.1 tok/s (27B INT4, 2K, no MTP) vs. 68.9 here; 262K on 24 GB needs unmerged KV code. | [SOURCES.md](SOURCES.md#vllm-on-rocm-and-hyperqwen-2026-10-03) |
| `GGML_CUDA_GRAPH_OPT=1` (b11160, MTP n=3) | -1.5% at empty context, -3.6..-3.9% at 240K, identical tokens. Rejected 2026-10-03. | [results/20261003-graph-opt-mtp/](../results/20261003-graph-opt-mtp/README.md) |
| rdna-boosts GQA-6 FA band on gfx1100 | Dropped without building: the fork's author measured it on a 7900 XTX (fork commit `b5278a5`): plain decode -12%, MTP n3 +8.6% / n7 +11.1% at ~42K, decode/verify not bit-identical; it also needs K and V of one type, so it never engages with `q8_0`/`q5_1`. | [ENGINES-EXPERIMENTS.md](ENGINES-EXPERIMENTS.md#status-after-the-2026-10-03-test-session-annotations-to-this-review) |
| vLLM ROCm forks/plugins (Paiton, vllm-radiance) and ROCmFPX | Not run. Paiton and vllm-radiance are qualified on RDNA4 (gfx1201) only, with FP8/FP4 paths (Paiton's runtime is closed); ROCmFPX lists gfx1100 as "results vary", no published numbers. | [SOURCES.md](SOURCES.md#vllm-rocm-forks-and-low-bit-llamacpp-forks-2026-10-03) |
| Unmeasured speed candidates (2026-09-26, each <5% or blocked by VRAM/context) | llama.cpp PR #29393 outside a regular engine update; fork adaptive MTP (`draft-mtp-adaptive`; upstream PR #27210's author advises against it below draft depth 7); building ik_llama.cpp; `-DGGML_LTO=ON` (third-party claim, [ENGINES-EXPERIMENTS.md](ENGINES-EXPERIMENTS.md#candidates-from-third-party-repositories-2026-10-02-not-run)). | [depth.md](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4) |
| KVMem (kvmem-llama.cpp) | Candidate: budget 28,672, block 32: 45.5 tok/s at 244K vs. 20.8 (2.2x), 8/8 at 240K. Budget 49,152 crashes. Not adopted; agent run (T6) outstanding. | [measurements/kvmem.md](measurements/kvmem.md), [results/20260930-kvmem-trial-round2/](../results/20260930-kvmem-trial-round2/) |

## Models, quantization and speculative alternatives

| Item | Result | Evidence |
|---|---|---|
| Weight quants | PPL: IQ3_XXS-mtp 6.948, IQ3_S 6.734, **IQ3_S-mtp 6.734**, HauhauCS IQ4_XS 6.823, RVN Q4_K_M-mtp 6.710, Q4_K_M 6.639. MTP tg (accept): IQ3_XXS-mtp 56.3 (50%), IQ3_S-mtp 62.2 (62%), RVN 48.2 (55%). `IQ3_S-mtp` adopted as best PPL/MTP trade-off in its size class; the HauhauCS and RVN finetunes are larger and slower per byte. | [kv-quality.md](measurements/kv-quality.md#weight-quantization-matrix-perplexity-toks) |
| KV `q4_0/q4_0` | KLD 0.002450, 4x `q8_0/q8_0`'s 0.000587; the only mix below 98% same-top-1 token. Discarded. (`q8_0/q4_1`: 0.001244, 2x.) | [kv-quality.md](measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16) |
| KV `q8_0/q5_1` vs. `q8_0/q8_0` | +27% KLD (0.000744 vs. 0.000587, still near-lossless), but fits the full 262K where `q8/q8` tops out at 240K. `q8_0/q5_1` adopted. Ladder: 224K 22.3-25.1 tok/s at 22,700 MiB; 240K 22.5-24.4 at 23,407 MiB; 262K 18.6-26.9 at 22,630 MiB. | [depth.md](measurements/depth.md#context-window-ladder-224k-and-240k-272-w-2026-09-25) |
| DFlash2 speculative decoding | Mostly loses to MTP at 190K (n=5) and 240K (n=7: -36%, -53%, +6%); more VRAM. | [speculative.md](measurements/speculative.md) |
| n-gram speculation | Alone, does not beat MTP. Stacked on MTP n=3 (2026-10-03): `ngram-map-k4v` adopted; `ngram-mod` not adopted (cross-request pool skews the bench, editing -1..-7%), only via a real session replay. | [results/20261003-ngram-mtp-stacking/](../results/20261003-ngram-mtp-stacking/README.md) |
| `--spec-draft-sampling probabilistic` (b11371, PR #27694) | Empty context, temperature 1: -5% median tg despite acceptance 75.7% to 77.5%. 240K, temperature 1: code +12.4%, copy -2.7%, essay -4.6%, total wall -2.1%. Not adopted, pending a real coding-session replay. | [results/20261003-b11371-mtp-draft-sampling/](../results/20261003-b11371-mtp-draft-sampling/README.md) |
| MTP vs. none (the adopted baseline) | n=3: +109% at 240K fill (23.3 vs. 11.2 tok/s), +85% at empty context (68.9 vs. 37.2). | [speculative.md](measurements/speculative.md) |
