# 2026-10-03: KVarN screen on BeeLlama v0.4.7 (gfx1100)

Question: KVarN (variance-normalized KV quantization; kvarn5 K / kvarn4 V would shrink this model's
262K KV from 7,424 MiB to ~4,992 MiB) could free VRAM, and a smaller KV read might speed decode at
depth. Is it fast enough on gfx1100 to be worth a quality study?

## Setup and command

BeeLlama v0.4.7 prebuilt (ROCm 7.2; already tested at shallow depth, see
[`engines.md`](../../docs/measurements/engines.md)), and the adopted `hip-kvmix` engine (b11371) as
the same-day control. `llama-bench`, plain decode (no MTP), 272 W:

```bash
llama-bench -m <IQ3_S-mtp.gguf> -ngl 999 -fa 1 -ub 256 -p 512 -n 64 -d 0,131072 -r 1 -o jsonl -ctk <K> -ctv <V>
```

Go rule (set before the run): kvarn5/kvarn4 tg64 at 128K must beat `hip-kvmix` q8_0/q5_1
(16.65 tok/s on 2026-09-26) and BeeLlama's own q8_0/q5_1.

## Results

| Engine, K/V | pp512 | tg64 | pp512 @128K | tg64 @128K |
|---|---|---|---|---|
| `hip-kvmix` b11371, q8_0/q5_1 | 853.9 | 38.44 | 383.3 | 16.64 |
| BeeLlama, q8_0/q5_1 | 858.6 | 31.08 | 167.1 | 13.12 |
| BeeLlama, kvarn5/kvarn4 | 674.9 | 32.00 | 92.5 | 10.53 |

## Conclusion

Rejected: kvarn5/kvarn4 decodes at 128K 37% slower than `hip-kvmix` and 20% slower than BeeLlama's
own q8_0/q5_1, with prefill at a quarter of `hip-kvmix`. No quality study needed. The control
reproduces the 2026-09-26 figure (16.64 vs. 16.65 tok/s).

**Raw data**: `kvmix-q8q51.jsonl`, `bee-q8q51.jsonl`, `bee-kvarn54.jsonl`.
