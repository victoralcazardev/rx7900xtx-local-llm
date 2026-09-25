# 2026-09-24 — Weight quantization matrix

**Measures**: `llama-bench` speed and `llama-perplexity` quality for 6 quantizations of the same
base model (Qwen3.8-27B, various GGUF quants and two finetunes), ROCm, KV q8_0/q8_0.

**Command**:
```
llama-bench -m <model>.gguf -ngl 999 -fa 1 -ctk q8_0 -ctv q8_0 -p 512 -n 128 -d 0,16384 -r 2
llama-perplexity -m <model>.gguf -f wiki.test.raw -c 512 --chunks 150 -fa on
```
run once per quantization (`matriz.sh`, superseded name for the sweep script; the individual runs
are not part of the ported `bench/` scripts, see `bench/README.md`).

**Files**:
- `*.bench.md` — raw `llama-bench` markdown table per quantization (speed).
- `summary.md` — perplexity figures extracted from the (unpublished) raw `llama-perplexity` logs.

**Conclusion**: GSQ-RCO IQ3_S-mtp selected as the model — best perplexity for its size class, and the
MTP head adds no perplexity cost over the non-MTP IQ3_S file. See
[`../../docs/measurements/kv-quality.md`](../../docs/measurements/kv-quality.md#weight-quantization-matrix-perplexity-toks).
