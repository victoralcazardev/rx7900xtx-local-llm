# 2026-09-24 — Running alongside another GPU process

**Measures**: what happens to the main inference server and to a second Vulkan GPU process when both
run at once and VRAM runs out.

**Command**: main `llama-server` started with a full context and a 3,000-token generation request;
25 s later, a second `llama-server` (Qwen3.5-2B Q8_0, 16K) starts and answers one request
(`convivencia.sh`, not ported to `bench/` — see `bench/README.md`). VRAM/GTT sampled every second via
sysfs, plus `journalctl -k`.

**Files**:
- `summary.md` — the per-case throughput/VRAM table.
- `gen-C1.json`, `gen-C2.json`, `gen-C3.json` — the second process's own generation result per case.

**Conclusion**: amdgpu/TTM spills the newcomer to GTT (system RAM) instead of failing either
process — whichever process arrives late is the one that slows down. See
[`../../docs/measurements/coexistence.md`](../../docs/measurements/coexistence.md#coexistence-test).
This folder also documents the same-day incident where suspending the machine with a model loaded
hung it — see the parent doc's "Incident" section.
