# 2026-09-26 — BeeLlama v0.4.7 + KVarN: parity and KLD

**Measures**: whether BeeLlama's KVarN KV cache quantization (per-head Hadamard rotation +
per-axis normalization over 128-token tiles) is worth adopting on this GPU — speed parity against
our engine first, then KLD of the standard and KVarN KV types.

**Engine**: BeeLlama v0.4.7 Linux ROCm 7.2 prebuilt (sha256
`ba0e3aec321f6bd4037287a0825e6c098409062c84304ff9ce7d11cb182e0521`), links the system ROCm 7.2.4,
ships gfx1100 kernels.

**Parity command**: `llama-bench -m <model>.gguf -ngl 999 -fa 1 -ctk q8_0 -ctv q8_0 -p 512 -n 128
-d 0,16384 -r 3` (same args and model as the ROCm runtime A/B in
[`../20260926-rocm-runtime-ab/`](../20260926-rocm-runtime-ab/)).

**Parity results** (tok/s):

| pp512 | tg128 | pp512 @d16384 | tg128 @d16384 |
|---:|---:|---:|---:|
| 912.60 ± 3.16 | 31.08 ± 0.06 | 663.10 ± 1.14 | 27.74 ± 0.01 |

vs. our `hip-kvmix` engine: **-18% tg, -22% tg @16K, -18% pp @16K**. Likely causes (hypothesis,
not isolated): ROCm 7.2 compiler, base ~b10830, upstream issue
[Anbeeld/beellama.cpp#111](https://github.com/Anbeeld/beellama.cpp/issues/111).

**KLD command**: `llama-perplexity -m <model>.gguf -f wiki.test.raw -c 32768 --chunks 2 -fa on
-ctk f16 -ctv f16 --kl-divergence-base kld-f16.bin`, then per KV type with `--kl-divergence`, same
BeeLlama binary throughout (base PPL 6.2628 ± 0.0815, f16 KV).

**Files**: `parity-summary.md`, `kld-summary.md`.

**KLD results**:

| K/V | Mean KLD | Max KLD | PPL(Q)/PPL(base) |
|---|---:|---:|---:|
| q8_0/q8_0 | 0.000754 | 0.131 | 1.00038 |
| q8_0/q6_0 | 0.000785 | 0.147 | 1.00038 |
| q8_0/q5_1 | 0.000905 | 0.273 | 1.00103 |
| kvarn8/kvarn8 | 0.002022 | 0.501 | 1.00006 |
| kvarn6/kvarn6 | 0.002041 | 0.556 | 1.00024 |
| kvarn5/kvarn5 | 0.002168 | 0.372 | 1.00048 |

Note: requesting `q8_0/kvarnN` logs "`--cache-type-v` uses KVarN but `--cache-type-k` is q8_0;
forcing K to kvarnN" — K/V mixes with KVarN are impossible; those runs equal kvarnN/kvarnN.
Runtime per run: ~109 s for standard KV types vs. ~180 s for KVarN.

**Conclusion**: **KVarN rejected on gfx1100 with this build** — ~2.7x the KLD of q8/q8 at every
bit width (an error floor independent of bits), worse than q8/q5_1; perplexity exercises the
prefill path, which is what writes nearly all KV in agent use; the fork is also ~20% slower even
with standard KV types. Depth tests skipped (kill criterion met at the parity/KLD stage). Side
finding: **q8_0/q6_0 is near-lossless (+4% KLD vs. q8/q8)** but q6_0 KV exists only in BeeLlama
(and ik_llama.cpp) — idea, not scheduled. Absolute KLD differs from this repo's own engine table
(q8/q8 0.000754 here vs. 0.000587 in
[`kv-quality.md`](../../docs/measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16)) because
base logits and kernels differ between engines — compare only within an engine.
