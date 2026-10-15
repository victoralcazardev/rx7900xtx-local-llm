# Strata v0.1.44.1 + Qwen3.8-Flash-Next Coder IQ1_M: first run on this machine (2026-10-15)

**What.** The first on-hardware run of Strata with the ISTA-DASLab Coder IQ1_M. Three configurations: context ×
KV type, short and deep coding requests. It is a setup smoke test, not the decision criterion's quality run
([`docs/models/strata-flash-next.md`](../../docs/models/strata-flash-next.md#decision-criterion-for-an-on-hardware-trial)).

**Versions.** Strata `v0.1.44.1` (`296b59d2`, `main`), engine compiled by `./setup.sh --backend hip` against
the system ROCm 7.2.4 (hipcc + hipBLAS, no hipBLASLt → plain hipBLAS prefill, no tuning table). llama.cpp
sources for gguf-py at `3cf0325` (Strata's pin). Model: `Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M-0000{1,2}-of-00002.gguf`
from [ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF)
(sizes 29,608,446,496 / 28,800,138,432 bytes, matching the HF API), on the NVMe. Vision off. MTP draft layer
from setup (Q2_0 experts), `--spec 4`. Low-RAM resident mode (`--resident-experts`, `STRATA_RESIDENT_PIN=0`).

**Machine.** RX 7900 XTX (gfx1100) at the 272 W cap, Ryzen 7 5700X, 31.25 GiB RAM with a KDE desktop and
several agent CLIs open (~13-14 GiB available before start), zram swap.

**Commands.**

```bash
./setup.sh --setup --family coder --model IQ1_M --gguf-dir <models>/Qwen3.8-Flash-Next-GSQ-RCO-Coder-IQ1_M \
  --backend hip --vision no --no-browser --yes --no-start --context <131072|262144> --kv <int8|k8v4>
./run-coder-iq1_m.sh                                   # serve on :8080
STRATA_DIR=<strata clone> python3 strata_bench.py 100000   # 2 short requests, then one ~95-100K-token prompt
```

Requests: temperature 0.6, `max_tokens` 800, thinking at the template default; every answer hit the cap inside
`reasoning_content`, so these are decode-speed numbers, not answer quality. Numbers are the server's `timings`.

## Results

| Context | KV | Short #1 gen | Short #2 gen (warm) | Deep prompt | Experts in RAM | Outcome |
|---|---|---|---|---|---|---|
| 128K | int8 | 67.4 tok/s | 77.6 tok/s | 94,934 tokens read at 844 tok/s, then 66.7 tok/s gen | 7.75 GiB | works |
| 262K | int8 | 41.2 tok/s | 27.8 tok/s | stalled 60 s at prefill layer 10, engine restarted, HTTP 503 | not logged | fails |
| 128K | k8v4 | 68.8 tok/s | 71.9 tok/s | kernel OOM killer at 17:03 (plasmashell, zapzap, Strata) | 10.45 GiB | fails, took the desktop down |

- Decode expert-cache hit rate on short requests: 96-97% (128K), 93-95% (262K).
- MTP acceptance on short requests: 400-450 of 541-604 drafts (~70-75%).
- 128K int8 at start: 614 MiB of VRAM free with everything loaded; 184 of the prompt path's 1,776 lendable
  slots kept in RAM, so "1592 of 1776 lendable slots (90%) will read their experts from the pack during a long
  prompt" (engine warning). The deep prompt still read at 844 tok/s.
- 262K stall report: 3,317 MiB in swap, 4.5 GiB RAM available, 0 threads waiting on the disk.
- k8v4 frees KV VRAM, so the GPU caches fewer experts and the resident RAM copy grows from 7.75 to 10.45 GiB;
  on this RAM that is what ran out. The upstream "+10%" for k8v4 is an RTX 3090 / enough-RAM result.

## Conclusion

On 31 GiB of RAM with a desktop open, only **128K + KV int8** serves a ~95K-token prompt. Its speed (67 tok/s
at ~95K fill, short requests 67-78 tok/s) already passes the trial bar of "more than 45 tok/s at 128K+ fill"
for speed; the quality half (`bench/longctx_quality.py`) is not run yet. 262K and k8v4 are not usable as is:
both are RAM-bound. Config kept: 128K, int8, `STRATA_RESIDENT_HEADROOM_GIB=6` (upstream tip #834 for 31 GB PCs;
not yet re-measured with a deep prompt).

Raw data: the server log lines quoted above; no JSON was kept (setup smoke test).
