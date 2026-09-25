# 2026-09-24, night — VRAM breakdown at load, 262K

**Measures**: per-component VRAM (weights, KV, recurrent state, compute buffers, MTP draft KV, MTP
draft compute) at model load, for 6 configuration variants at 262K context.

**Command**: `llama-server -m <model>.gguf -c 262144 -lv 4 <variant-specific flags>`, reading the
`common_memory_breakdown_print` line from the log after load (`memoria.sh`, not ported to `bench/`
as a standalone script — see `bench/README.md`).

**Files**: `summary.md` — the breakdown line extracted per variant (raw logs not published).

**Conclusion**: MTP's draft KV should stay at its f16 default — quantizing it to q8_0 grows the
draft's compute buffer more than its KV shrinks, a net VRAM loss. See
[`../../docs/measurements/memory.md`](../../docs/measurements/memory.md#vram-breakdown-at-load--lv-4-log-262k-context-mib).
