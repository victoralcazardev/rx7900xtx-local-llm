# 2026-09-24 — Context-full stress test

**Measures**: whether 128K and 262K profiles survive a fully-loaded context (real tokens, not
padding), and the VRAM margin at that point.

**Command**: `llama-server` started per case, context filled with a `wiki.train`-derived prompt to
the exact target depth, one response requested; VRAM sampled every second via `nvidia-smi`-equivalent
sysfs reads (`estres.sh` + `estres.py`, not ported to `bench/` as standalone scripts — see
`bench/README.md`; the successor is `bench/oom_probe.py`).

**Files**: `summary.md` — the per-case outcome and peak VRAM (raw logs not published).

**Conclusion**: the 262K + MTP failure is a VRAM-margin problem, not a driver bug —
`LLAMA_ATTN_ROT_DISABLE` doesn't fix it, having enough free VRAM does. See
[`../../docs/measurements/depth.md`](../../docs/measurements/depth.md#context-full-stress-test-total-vram-including-desktop-24560-mib).
