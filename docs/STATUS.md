# Status

## Current profile

`qwen38-iq3s-mtp` / `262k-q8q51-mtp` — **default** (`scripts/launch.py`'s `[defaults]` when no
alias is given, i.e. `ia` with no arguments).

```
python scripts/launch.py
# equivalent, explicit form:
python scripts/launch.py qwen38-iq3s-mtp --profile 262k-q8q51-mtp
```

Engine `hip-kvmix`, `-c 262144`, KV `q8_0/q5_1`, MTP `--spec-draft-n-max 3`, `-ub 256`, vision
disabled, measured under a 272 W power cap (this card's driver minimum, now the permanent
setting — see `measurements/thermals-power.md`).

`224k-q8q8-mtp` is the **alternative** long-context profile (`-c 229376`, KV `q8_0/q8_0`, MTP n=3,
`-ub 512` default):

```
python scripts/launch.py qwen38-iq3s-mtp --profile 224k-q8q8-mtp
```

## Key figures

- **262K default**: 18.6-26.9 tok/s at 240K fill across three task types (essay/copy/code),
  process VRAM peak **22,630 MiB**, 0 evicted. **224K alternative**: 21.4-32.2 tok/s at 190K fill,
  process VRAM peak **22,883 MiB**. See
  [`measurements/speculative.md`](measurements/speculative.md)'s "MTP n=3 confirmed at depth" and
  [`measurements/memory.md`](measurements/memory.md)'s "`-ub 256`" section.
- **128K daily-use profile** (`128k-q8q8-mtp`, vision on): ~58-69 tok/s empty context, ~31 tok/s at
  104K. VRAM 19.6 GiB. See [`measurements/depth.md`](measurements/depth.md).
- **262K official-binary profile** (`262k-q8q8`, no MTP): ~39 tok/s empty, ~19 tok/s at 182K. VRAM
  21.4 GiB.
- **MTP n=3 adopted as the default draft length (2026-09-26)**: confirmed at depth on both
  long-context profiles — +9% mean tg at 190K (224K profile), +11% at 240K (262K profile), across
  all three task types. This supersedes the 2026-09-25 128K-fill screening, which only found n=3
  favorable on literal copy at that shallower depth. `--spec-draft-p-min 0.8` raises acceptance but
  not speed — not adopted. See [`measurements/speculative.md`](measurements/speculative.md).
- **`-ub 256` adopted for the 262K default (2026-09-26)**: -350 MiB process VRAM for a small pp
  cost (-5%), no generation-speed cost. This differs from the 2026-09-25 128K-fill screening where
  `-ub 512` was optimal — the effect of `-ub` depends on profile and depth. See
  [`measurements/memory.md`](measurements/memory.md).
- **KV quality**: q8_0/q8_0 is effectively free (KLD 0.000587 vs. f16); q8_0/q5_1 costs 27% more but
  is still small and doesn't show up as a retrieval-quality loss at 240K (see "Quality validation"
  below). q4_0/q4_0 discarded (4x KLD). See
  [`measurements/kv-quality.md`](measurements/kv-quality.md).
- **System VRAM margin depends on the desktop's own usage, not just the profile (2026-09-26)**:
  total system VRAM left only 12-190 MiB free across every long-context configuration measured that
  day (desktop idle ~1.5 GiB, vs. ~0.8 GiB on other days) — corrects the earlier "~1.8 GiB margin"
  figure for the 224K profile, measured with a lighter desktop. Close heavy GPU applications
  (video players, browsers with GPU video) before long-context work, regardless of profile. See
  [`measurements/memory.md`](measurements/memory.md).
- **Thermals and power**: **272 W (this card's driver minimum) is now the permanent power cap**,
  applied via a systemd unit at boot, not just for deep-prefill tests — measured directly at 190K
  vs. the factory 303 W default: ~6% slower prefill (459 vs. 487 tok/s), but the hotspot peaks
  7-8°C cooler (99°C vs. 100-106°C). Older 303 W figures elsewhere in this doc and in
  `measurements/` are kept as historical data points (a different power policy, not a correction —
  see `docs/STYLE.md` §7). See [`measurements/thermals-power.md`](measurements/thermals-power.md).
- **Multi-agent concurrency**: parallel `-np` slots are not free — a slot's long prefill starves
  generation on the other slots, and end-to-end wall time to serve several requests is higher with
  more slots than queuing them through 1 slot + MTP (8.6% worse at 2 slots+MTP, 6.0% at 2 slots
  without MTP, 25.6% at 4 slots). Recommend 1 slot + MTP with request queuing over adding slots.
  See [`measurements/concurrency.md`](measurements/concurrency.md).

## Quality validation

**60/60 exact match, 0 loop detections**, up to 240K fill (`bench/longctx_quality.py`, RULER-style
multi-key retrieval): 32K 20/20, 128K 20/20, 190K 4/4 (one of five planned documents, partial,
parked by the user), 220K 8/8 (2026-09-26, the `224k-q8q8-mtp` operating depth), 240K 8/8
(2026-09-26, the adopted `262k-q8q51-mtp` operating depth, KV q8_0/q5_1). See
[`measurements/depth.md`](measurements/depth.md#quality-ruler-style-200k-q8q8-mtp).

## Open hypotheses to re-validate

- **A broader 190K quality sample** (remaining 4 of 5 documents, 16 of 20 questions) — parked by
  the user, not blocking. See `measurements/depth.md`.
- **Round-3 test queue** (2026-09-26 community-claims review, see `docs/SOURCES.md`'s "Community
  claims reviewed 2026-09-26"), priority order:
  1. **P1 ROCm toolchain/runtime A/B — done, rejected.** ROCm 10 runtime is 1-2% slower on tg, ~5%
     on pp, higher variance vs. the system ROCm 7.2.4 runtime. Current ROCm-10-compiler +
     ROCm-7.2.4-runtime combo stays. See `measurements/engines.md`.
  2. **P2 Quality at the real ~220K operating depth — done.** 8/8 exact match at 220K fill;
     cumulative 52/52 exact match 32K-220K. See `measurements/depth.md`.
  3. **P3 BeeLlama v0.4.7 + KVarN KV cache — done, rejected.** KVarN's KLD is ~2.7x q8/q8 at every
     bit width; BeeLlama itself is ~18-22% slower than `hip-kvmix`. See `measurements/kv-quality.md`.
  4. **P4 exllamav3-rocm** (+ TabbyAPI) — **parked by the user** (least interest of the candidates;
     read-only audit done, no code/license blocker found — see `docs/ENGINES.md`/`docs/SOURCES.md`).
  5. **P5/P5b/P5c 262K decision — done, adopted.** q8/q5_1 quality 8/8 exact at 240K fill (P5);
     MTP n=3 +11% mean tg at 240K, meeting the user's floor (P5b); `262k-q8q51-mtp` adopted as the
     new default profile, `224k-q8q8-mtp` kept as the alternative (P5c). See `measurements/depth.md`,
     `measurements/speculative.md`.
  6. **P6 MTP n=3 + `--spec-draft-p-min 0.8` — done.** n=3 wins at 190K depth (+9% mean tg,
     `224k-q8q8-mtp`); p-min 0.8 raises acceptance (67%→96%) but not speed — not adopted on its own.
     See `measurements/speculative.md`.
  7. **P7 Vulkan re-test with the GPU memory clock pinned** — **pending, needs sudo** (to pin
     `power_dpm_force_performance_level`, user present); our Vulkan loss coincided with the memory
     clock at 772 MHz vs. 1249 MHz on ROCm, not necessarily the backend itself — see
     [`measurements/engines.md`](measurements/engines.md).
  8. **P9 (later) Speed research at depth for the 262K profile** — open, user interest, not started.
  9. **P10 `-ub 256` on the 262K default — done, adopted.** -350 MiB process VRAM, small pp cost,
     no speed cost; also measured system VRAM headroom across configurations. See
     `measurements/memory.md`.
- **llama.cpp hypotheses to re-validate on the next engine update** (see
  [`sop/update-engine.md`](sop/update-engine.md) and `SOURCES.md`): PR
  [#28102](https://github.com/ggml-org/llama.cpp/pull/28102) targets gfx1201 (RDNA4) — a follow-up
  forced stream-K back on for gfx1100 after a regression, so this is resolved, not a re-validation
  item; issue
  [#26648](https://github.com/ggml-org/llama.cpp/issues/26648) is an MTP sampler assert at long
  context on HIP; [halo-box/strix-llama.cpp#56](https://github.com/halo-box/strix-llama.cpp/pull/56)
  is an RDNA3 IQ2/IQ3 MMVQ scale-multiply change; the
  [BuffedMod IQ3_S quant](https://huggingface.co/tooltd/Qwen3.8-27B-GSQ-RCO-BuffedMod-GGUF) upcasts
  `output.weight`, untested here; LACT has known RDNA3 power-reporting quirks
  ([ilya-zlobintsev/LACT#237](https://github.com/ilya-zlobintsev/LACT/issues/237)).
- **MTP acceptance at temperature 1 / real agent traffic**: depth numbers use a synthetic prompt;
  third-party reports with real tool-call traffic range 64-93% acceptance. See `docs/SOURCES.md`.
- **MTP overhead at depth**: upstream issues [#26038](https://github.com/ggml-org/llama.cpp/issues/26038),
  [#27282](https://github.com/ggml-org/llama.cpp/issues/27282) and
  [#28433](https://github.com/ggml-org/llama.cpp/issues/28433) (MTP compute/draft-ctx sizing on
  HIP) are open as of b11178. See [`sop/update-engine.md`](sop/update-engine.md).
- ~~MTP n=3 and `--spec-draft-p-min` at 190-240K depth: only measured at 128K fill so far~~ — done
  2026-09-26 (P6/P5b), n=3 adopted for both long-context profiles. See `measurements/speculative.md`.
- ~~262K with KV `q8_0/q5_1` was not attempted in the 224K/240K context-window ladder~~ — done
  2026-09-26 (P5), adopted as the new default (`262k-q8q51-mtp`). See `measurements/depth.md`.

## Discarded / not adopted

- Vulkan as primary backend — 2-3.5x slower generation than ROCm on this system (re-test pending,
  P7).
- KV `q4_0/q4_0` — 4x KLD of q8/q8, only mix below 98% same-top-1.
- `kvmix-vec4` patch — +20% ms/step at depth vs. plain `kvmix`.
- `stew675/llama-cpp-rdna-boosts` native-q8-KV fork — only -2.5% ms/step, not worth a fork.
- DFlash2 speculative decoding — slower than MTP n=2 at 190K on most task types, more VRAM.
- Vision at 200K/224K/240K/262K context — VRAM/context cost not worth it; deprioritized by the user.
- `-ub 1024`/`-ub 2048` — no speed gain at depth, cost 590 MiB/1.8 GiB more VRAM.
- MTP n=3 as the default at 128K fill — content-dependent at that shallower depth (only literal
  copy favored it); n=3 **is** adopted at the 190-240K operating depths of the long-context
  profiles (see "Key figures" above). `--spec-draft-p-min 0.3`/`0.8` — within noise of plain n=3 on
  speed at every depth measured (0.8 raises acceptance only).
- GPU power-limit / undervolt tuning beyond the permanent 272 W cap — deprioritized (see
  `docs/DECISIONS.md`).
- Third-party KV `q4_0` recipes (llm-bench.io guide, community posts) — matches this repo's own
  KLD result: `q4_0` costs ~4x the KLD of q8/q8. See `docs/SOURCES.md`.
- Lemonade-sdk/llamacpp-rocm and nasone32/llama.cpp-RDNA3-7900xtx-opt — re-checked 2026-09-26:
  Lemonade's latest build is just a current-master rebuild, nasone32 has no commits since
  ~2026-09-10. See `docs/SOURCES.md`.
- ROCm 10.0.0 runtime libraries (TheRock, ROCm 10 compiler kept) — 1-2% slower tg, ~5% slower pp,
  higher variance vs. the system ROCm 7.2.4 runtime. See `measurements/engines.md`.
- BeeLlama v0.4.7 + KVarN KV cache — KVarN's KLD is ~2.7x q8/q8's at every bit width (worse than
  q8/q5_1); BeeLlama itself is ~18-22% slower than `hip-kvmix`. See `measurements/kv-quality.md`.

## Next steps (priority order)

1. **P7** Vulkan re-test with the GPU memory clock pinned — needs sudo, user present.
2. **P9** Speed research at depth for the 262K profile — open, user interest.
3. GPU care beyond the permanent 272 W cap (undervolt) — deferred, see `docs/DECISIONS.md`.
