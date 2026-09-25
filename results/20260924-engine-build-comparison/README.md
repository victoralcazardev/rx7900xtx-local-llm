# 2026-09-24 — Engine build comparison (official vs. own gfx1100 builds)

**Measures**: `llama-bench` speed for the official ROCm binary vs. own gfx1100 builds, isolating the
effect of the build toolchain (ROCm 7.2.4 vs. ROCm 10.0 compiler) from the system runtime (always
ROCm 7.2.4 at run time).

**Command**: `llama-bench -m <model>.gguf -ngl 999 -fa 1 -ctk <k> -ctv <v> -p 512 -n 128 -d 0,16384 -r 2`
against each engine binary in turn (same model, same flags, only the binary changes).

**Files** (two measurement passes, same day):

- `native-official.md` + `native-gfx1100-rocm7.2.4-toolchain.md` — **first pass**: official binary vs.
  an own build compiled with the **ROCm 7.2.4** toolchain. Read on its own, this made the own build
  look slower (up to 7.5% at 16K). **Superseded** by the second pass below, once the toolchain (not
  the source) was identified as the cause.
- `engines-second-pass.md` — **second pass, current**: official binary ("A") vs. own builds compiled with the
  **ROCm 10.0** toolchain, no-kvmix ("E"), with the kvmix FA_QUANTS patch ("F", q8_0/q8_0, and "C",
  q8_0/q5_1). A "B" (official binary linked against a ROCm 10 runtime) and "D" (own build + ROCm 10
  runtime) row were attempted but not completed — the ROCm 10 runtime failed to initialize
  (`rocBLAS error: Could not initialize Tensile host`, missing gfx1100 kernel package), so every
  engine here runs against the system's ROCm 7.2.4 runtime; only the compile-time toolchain differs.

**Conclusion**: with the same (ROCm 10) toolchain, the own build matches the official binary's
speed; V in q5_1 costs ~8% of tg at 16K vs. q8. See
[`../../docs/measurements/engines.md`](../../docs/measurements/engines.md#engine-matrix-corrected-rocm-10-toolchain)
(current) and its "Own gfx1100 build and the compiler matters" section (superseded first pass).
