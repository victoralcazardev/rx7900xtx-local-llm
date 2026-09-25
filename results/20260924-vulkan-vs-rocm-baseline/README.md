# 2026-09-24 — Vulkan vs. ROCm baseline

**Measures**: generation and prompt-processing speed for Qwen3.8-27B GSQ-RCO IQ3_S-mtp on Vulkan vs.
ROCm/HIP, at three context depths and three KV type combinations.

**Command** (`bench/depth_bench.py`, historical name `validacion262.py` used `llama-bench` directly
for this run):
```
llama-bench -m <model>.gguf -ngl 999 -fa 1 -ctk f16,q8_0 -ctv f16,q8_0 -p 512 -n 128 \
    -d 0,4096,16384 -r 3
```
run once against the Vulkan binary and once against the ROCm binary (llama.cpp b11160,
commit `70c4e1582`).

**Files**:
- `vulkan.md` — raw `llama-bench` markdown table, Vulkan backend.
- `rocm.md` — raw `llama-bench` markdown table, ROCm backend.

**Conclusion**: ROCm is 2-3.5x faster than Vulkan for generation on this GPU/model, because Vulkan's
memory clock drops to 772 MHz while generating (ROCm holds 1249 MHz). See
[`../../docs/measurements/engines.md`](../../docs/measurements/engines.md#vulkan-vs-rocm-generation-and-prompt-processing).
