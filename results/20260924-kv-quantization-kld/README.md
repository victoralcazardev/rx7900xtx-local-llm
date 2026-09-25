# 2026-09-24 — KV cache quantization: KLD vs. f16

**Measures**: KL divergence between each KV cache quantization and an f16 reference, at 32K context.

**Command**:
```
# reference logits
llama-perplexity -m <model>.gguf -f wiki.test.raw -c 32768 --chunks 2 -fa on \
    -ctk f16 -ctv f16 --kl-divergence-base kld-f16.bin

# per KV type
llama-perplexity -m <model>.gguf -f wiki.test.raw -c 32768 --chunks 2 -fa on \
    -ctk q8_0 -ctv <v-type> --kl-divergence-base kld-f16.bin --kl-divergence
```
(`kld-kv.sh`, mapped to `bench/` — this exact sweep script wasn't ported, see `bench/README.md`).
Run on the own gfx1100 build (`hip-kvmix`, see `../../docs/measurements/engines.md`), because the
official binary ships no FlashAttention kernel for the mixed KV types.

**Files**: `summary.md` — extracted final KLD statistics per KV type (raw `llama-perplexity` logs
not published, see `../../docs/BENCHMARK-FORMAT.md`).

**Conclusion**: q8_0/q8_0 and q8_0/q5_1 are both safe; q4_0/q4_0 is discarded. See
[`../../docs/measurements/kv-quality.md`](../../docs/measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16).
