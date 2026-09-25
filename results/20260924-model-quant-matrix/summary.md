# Perplexity summary (extracted from `llama-perplexity` logs, not copied raw)

`llama-perplexity -f wiki.test.raw -c 512 --chunks 150 -fa on` (wikitext-2-raw), one run per
quantization. The raw logs (`*.ppl.log`) are console output and are not published here (see
`../../docs/BENCHMARK-FORMAT.md`); these are the final statistics from each.

| Model | Perplexity ± |
|---|---:|
| GSQ-RCO IQ3_XXS-mtp | 6.948 ± 0.087 |
| GSQ-RCO IQ3_S | 6.734 ± 0.084 |
| GSQ-RCO IQ3_S-mtp | 6.734 ± 0.084 |
| HauhauCS Aggressive IQ4_XS (finetune) | 6.823 ± 0.086 |
| RVN Q4_K_M-mtp (finetune) | 6.710 ± 0.084 |
| Q4_K_M | 6.639 ± 0.083 |

See [`../../docs/measurements/kv-quality.md`](../../docs/measurements/kv-quality.md#weight-quantization-matrix-perplexity-toks)
for the combined table with tok/s and file size, and the discussion.
