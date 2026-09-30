# Tried and not adopted

Everything measured on this card (RX 7900 XTX, RDNA3, gfx1100) that was compared against the
adopted profile and either lost or was set aside. Dates and reasoning per decision are in
[`DECISIONS.md`](DECISIONS.md); the current recommendation is in [`STATUS.md`](STATUS.md). Each
row: what was tried, the key numbers, where the evidence is.

## Flags and server settings

| Item | Result | Evidence |
|---|---|---|
| `-ub 1024` / `-ub 2048` | No speed gain at depth. 1024: +590 MiB VRAM. 2048: +1.8 GiB, pp -1.7%, code tg -3.6% (128K fill). `-ub 256` is adopted at 262K (-350 MiB, pp -5%, same tg); default 512 stays best at 128K fill. `-ub 384` never measured. | [speculative.md](measurements/speculative.md#-ub-and-mtp-screening-at-128k-fill-272-w-2026-09-25), [memory.md](measurements/memory.md) |
| `--spec-draft-n-max 4` (and 5) | At 240K on the adopted flags: 21.4 tok/s at 66% acceptance vs. n=3's 23.3 at 71% (-8%). At 128K empty context: 45.8 tok/s at 31% vs. 60.6 at 56%. n=3 is +9-11% mean tg over n=2 at 190K/240K. | [speculative.md](measurements/speculative.md#n4-checked-again-at-240k-exact-adopted-flags--ub-256-2026-09-26) |
| `--spec-draft-p-min` 0.3 / 0.6 / 0.75 / 0.8 | 0.3 (n=2, 128K): within noise. 0.8 (n=3, 190K): acceptance 67% to 96%, speed unchanged. 0.60/0.75 (n=3, empty context, community `probe.py`): 68.9 to 66.2/59.8 tok/s. 0.5 and `--spec-draft-n-min` never measured. | [speculative.md](measurements/speculative.md) |
| `-ctkd q8_0 -ctvd q8_0` (quantized MTP draft KV) | Draft KV -480 MiB but its compute buffer +1,036 MiB: net +426 MiB VRAM. Kept at f16. | [memory.md](measurements/memory.md) |
| `-np` > 1 (extra slots) | A slot's prefill starves generation on the others. Vs. queuing through 1 slot: 2 slots + MTP 8.6% slower wall time, 2 slots without MTP 6.0% slower, 4 slots 25.6% slower. | [concurrency.md](measurements/concurrency.md#1-vs-2-vs-4-slots-mtp-onoff-2026-09-25) |
| `--ctx-checkpoints` default (32) vs. 4 | Warm-turn reuse is the same either way (189,467 of 190,000 tokens reused across a task switch). Kept at 4 to bound RAM (270-515 MiB per checkpoint). The cost is one cold miss mode (~42 s at ~32K base prompt, ~14.5K tokens since a harness update). | [memory.md](measurements/memory.md#prompt-cache-reuse-and-context-checkpoints-2026-09-29), [agent-traffic.md](measurements/agent-traffic.md) |
| Vision (`mmproj`) at 200K+ | VRAM/context cost not worth it; off by default at 262K. | [DECISIONS.md](DECISIONS.md) |
| Power: 303 W cap | 272 W (driver minimum) costs prefill -6% (487 to 459 tok/s at 190K) and tg128 ~-3.4% at empty context (39.35 to 38.0 tok/s, single uncontrolled sample), for a hotspot of 99°C vs. 100-106°C. 272 W adopted. Undervolt/further power tuning deferred; 290/303 W not pursued (303 W exceeds the 104°C bench ceiling). | [thermals-power.md](measurements/thermals-power.md), [results/20260925-longctx-quality-200k/](../results/20260925-longctx-quality-200k/) |

## Backend, toolchain and engines

| Item | Result | Evidence |
|---|---|---|
| Vulkan (b11160) | ROCm 39 tok/s vs. Vulkan 11-23 (2-3.5x). Vulkan's memory clock drops to 456-772 MHz while generating vs. ROCm's 1249 MHz. Re-tested with the clock pinned (2026-09-29): HIP still +63% tg at depth 0 and +18% at 64K. Reference only. | [engines.md](measurements/engines.md) |
| ROCm 7.2.4 compiler | tg 33.9 at 16K (-7.5%) vs. the ROCm 10 compiler build (36.8-36.9). ROCm 10.0.0 compiler adopted. | [engines.md](measurements/engines.md) |
| ROCm 10.0.0 runtime (TheRock, compiler kept at ROCm 10) | -1..-2% tg, ~-5% pp, much higher variance vs. the system 7.2.4 runtime. System runtime kept. | [engines.md](measurements/engines.md), [results/20260926-rocm-runtime-ab/](../results/20260926-rocm-runtime-ab/) |
| BeeLlama v0.4.7 + KVarN | KVarN KLD ~0.0020-0.0022, ~2.7x q8/q8 at every bit width; BeeLlama itself -18-22% tg vs. `hip-kvmix`. Side finding: `q8_0/q6_0` near-lossless, but BeeLlama-only. | [kv-quality.md](measurements/kv-quality.md#beellama-kvarn-kld-2026-09-26) |
| `kvmix-vec4` patch | +20% ms/step vs. plain `kvmix` (worse). | [speculative.md](measurements/speculative.md) |
| `stew675/llama-cpp-rdna-boosts` (native q8 KV) | Only -2.5% ms/step; not worth maintaining a fork. | [ENGINES.md](ENGINES.md), [SOURCES.md](SOURCES.md) |
| Lemonade b1331/b1332 | Its build does not enable the FA quant kernels K `q8_0` + V `q5_1` needs; A/B dropped. | [ENGINES.md](ENGINES.md) |
| `nasone32/llama.cpp-RDNA3-7900xtx-opt` | Older snapshot than b11160, no binaries; patches target RDNA3.5/RDNA4 or prefill, sparse attention is for another architecture. Discarded. | [ENGINES.md](ENGINES.md) |
| exllamav3-rocm (+ patched TabbyAPI) | Read-only audit found no code or license blocker; deprioritized: 15.3 GB EXL3 model leaves less VRAM headroom, author's numbers not comparable. | [ENGINES.md](ENGINES.md), [SOURCES.md](SOURCES.md) |
| Unmeasured speed candidates (2026-09-26, each <5% or blocked by VRAM/context) | llama.cpp PR #29393 outside a regular engine update; fork adaptive MTP (`draft-mtp-adaptive`; upstream PR #27210's author advises against it below draft depth 7); building ik_llama.cpp. | [depth.md](measurements/depth.md#why-decode-slows-with-depth-attention-bandwidth-2026-09-26-round-4) |

## Models, quantization and speculative alternatives

| Item | Result | Evidence |
|---|---|---|
| Weight quants | PPL: IQ3_XXS-mtp 6.948, IQ3_S 6.734, **IQ3_S-mtp 6.734**, HauhauCS IQ4_XS 6.823, RVN Q4_K_M-mtp 6.710, Q4_K_M 6.639. MTP tg (accept): IQ3_XXS-mtp 56.3 (50%), IQ3_S-mtp 62.2 (62%), RVN 48.2 (55%). `IQ3_S-mtp` adopted as best PPL/MTP trade-off in its size class; the HauhauCS and RVN finetunes are larger and slower per byte. | [kv-quality.md](measurements/kv-quality.md#weight-quantization-matrix-perplexity-toks) |
| KV `q4_0/q4_0` | KLD 0.002450, 4x `q8_0/q8_0`'s 0.000587; the only mix below 98% same-top-1 token. Discarded. (`q8_0/q4_1`: 0.001244, 2x.) | [kv-quality.md](measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16) |
| KV `q8_0/q5_1` vs. `q8_0/q8_0` | +27% KLD (0.000744 vs. 0.000587, still near-lossless), but fits the full 262K where `q8/q8` tops out at 240K. `q8_0/q5_1` adopted. Ladder: 224K 22.3-25.1 tok/s at 22,700 MiB; 240K 22.5-24.4 at 23,407 MiB; 262K 18.6-26.9 at 22,630 MiB. | [depth.md](measurements/depth.md#context-window-ladder-224k-and-240k-272-w-2026-09-25) |
| DFlash2 speculative decoding | Slower than MTP n=2 on 2 of 3 tasks at 190K, and more VRAM. | [speculative.md](measurements/speculative.md) |
| n-gram speculation | Does not beat MTP at depth; stacking on MTP n=3 prepared, not run. | [speculative.md](measurements/speculative.md) |
| MTP vs. none (the adopted baseline) | n=3: +109% at 240K fill (23.3 vs. 11.2 tok/s), +85% at empty context (68.9 vs. 37.2). | [speculative.md](measurements/speculative.md) |
