# 2026-10-24: empty-context probe A/B on the native q8_0/q5_1 TILE engine (E3)

**Question**: what is the empty-context decode speed of the production profile on the engine
adopted 2026-10-23? The previous headline (68.9 tok/s MTP n=3, 37.2 spec off) was measured on b11160
([2026-09-27](../20260927-probe-ab-262k/README.md)).

## Method

Same instrument and contract as 2026-09-27: `bench/probe_ab.py` with the unmodified community `probe.py`
from [sudoingX/qwen38-mtp](https://github.com/sudoingX/qwen38-mtp) at commit `1e514a8` (sha256
`d9ea0c9fb10435937c774d4b182a6b5ac8481837e8b3d1aa23738eeb178dfd5f`), three passes per arm (each pass:
one warm-up + three prompts x three runs, 400 tokens, thinking off). Row = median of the three pass
medians.

```bash
systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \
  BENCH_SERVER=<engines>/llama-b11820-pr30792q51-linux-rocm10-gfx1100-kvmix/llama-server \
  BENCH_MODEL=<models>/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
  python3 bench/probe_ab.py --probe qwen38-mtp/probe.py none n3
```

`probe_ab.py`'s `n3` arm is MTP n=3 without the n-gram map (as in 2026-09-27), so the two dates compare
directly. 272 W cap, desktop at 473 MiB VRAM before load, Brave closed. Exact argv per arm and every
pass in [`summary.jsonl`](summary.jsonl).

## Results (tok/s)

| Arm | Pass medians | **Row** | Code / prose / Bash | vs. spec off | Acceptance (aggregate, warm-ups excluded) | b11160 row (2026-09-27) |
|---|---|---:|---|---:|---:|---:|
| spec off | 39.3 / 39.1 / 39.0 | **39.1** | 39.1 / 39.2 / 39.0 | — | — | 37.2 |
| n=3 | 75.3 / 76.3 / 77.7 | **76.3** | 88.7 / 57.6 / 76.3 | **+95%** | 0.708 (4887/6904), per request 0.38-0.96 | 68.9 |

System VRAM after load → after the passes: spec off 20,414 → 20,842 MiB; n=3 22,381 → 23,012 MiB.

## Conclusion

- Empty-context MTP n=3 is 76.3 tok/s vs. 68.9 on 2026-09-27, at the same acceptance (0.708 vs. 0.715);
  spec off is 39.1 vs. 37.2. Not like for like: the engine moved b11160 → b11820 + TILE patch (several
  builds in between) and the desktop used 473 MiB VRAM before load vs. ~1.1-1.2 GiB then. What this run
  measures cleanly is the same-session ratio: n=3 is +95% over spec off. The gain is not attributed to
  the TILE patch, whose `ne[1] <= 8` path should matter little at empty context [INFERENCE].
- Pass-to-pass spread on n=3 is ±1.5 tok/s, as on 2026-09-27.
