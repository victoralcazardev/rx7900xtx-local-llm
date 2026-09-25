# KLD summary (extracted from `llama-perplexity --kl-divergence` logs, not copied raw)

`llama-perplexity -c 32768 --chunks 2` over `wiki.test.raw`, IQ3_S-mtp weights, one KV type per run.
Logits saved once with KV f16 (`--kl-divergence-base`), then compared per type
(`--kl-divergence`). Raw logs are console output and are not published here (see
`../../docs/BENCHMARK-FORMAT.md`); this is the final statistics block from each.

| KV K/V | Mean KLD | KLD p99 | KLD p99.9 | Max KLD | Same top-1 | PPL(Q)/PPL(f16) |
|---|---:|---:|---:|---:|---:|---:|
| q8_0/q8_0 | 0.000587 | 0.0046 | 0.0172 | 0.074 | 98.76% | 1.00017 |
| q8_0/q5_1 | 0.000744 | 0.0056 | 0.0185 | 0.145 | 98.55% | 1.00093 |
| q8_0/q4_1 | 0.001244 | 0.0086 | 0.0264 | 0.626 | 98.23% | 1.00100 |
| q4_0/q4_0 | 0.002450 | 0.0183 | 0.0465 | 0.147 | 97.38% | 1.00109 |

See [`../../docs/measurements/kv-quality.md`](../../docs/measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16)
for the conclusion.
