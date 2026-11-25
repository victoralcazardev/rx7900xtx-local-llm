# Inkling-2-Mini on the Nib engine with the NVFP4-Mixed Nib-Pack (2026-11-24/25)

**What**: an isolated trial of [Chromadera/nib](https://github.com/Chromadera/nib), a new HIP engine written only for
Inkling-2-Mini on gfx1100, with [degenmeowster/Inkling-2-Mini-Nib-Pack](https://huggingface.co/degenmeowster/Inkling-2-Mini-Nib-Pack)
(experts of layers 0-19 back in the native NVFP4, everything else Q8_0), against the production `maya-ik2` /
`inkling2-mini-unc-q8d` setup. Asked by the user: "Probar Nib aislado ... mismo bench/GSM8K/retrieval que maya-ik2,
con y sin --sparse-pages; maya-ik2 sigue intacto". Plan and log: `odd/tasks/nib-trial-2026-11-24.md` (local only).

**Status: adopted (2026-11-25).** The Unbound v2.1 graft is the default `inkling2-mini-unbound-nib` / `262k-nib`
([`DECISIONS.md`](../../docs/DECISIONS.md)); `maya-ik2` stays wired as the fallback. Retrieval at a true ~250K is
not measured (two attempts landed at ~184K and ~148K).

**Conclusion so far**: with its DSpark drafter and Quest sparse attention (`--sparse-pages 224`), Nib decodes
**+13-25% faster than `maya-ik2` up to 33K and about 1.4-1.9x faster at 134K-258K** (97-104 vs. 69 / 54 tok/s), and
reads 258K prompts 2.3x faster (2,982 vs. 1,298 tok/s). Sparse attention is where the long-context gain comes from
(without it: 78 / 60 tok/s at 134K / 258K) and it missed 1 of 36 needles (at ~184K) where dense attention found 36/36.
GSM8K is at parity: 186/192 (base pack) and 187/192 (Unbound graft) vs. 187/192 on `maya-ik2`.
The publisher's 186.8 tok/s is not reproduced in real requests (100-125 tok/s). Under the card's sampling
(temperature 1.0 and no top-k) the server leaves the drafter's fast path and decodes ~31 tok/s.

## Setup

| | |
|---|---|
| Dates | 2026-11-24 23:00 to 2026-11-25 |
| GPU | RX 7900 XTX 24 GB (gfx1100), 272 W cap (`power1_cap` 272000000) |
| OS / runtime | CachyOS, kernel 7.3.5-2-cachyos, ROCm in `/opt/rocm` (`hipconfig` 7.16.0-4f6d503) |
| Engine | `Chromadera/nib` `2e16cf0b824a3d22eceecc2a4502cb922e285b7f` (repo created 2026-11-24T21:23Z; Apache-2.0 `LICENSE`; no outbound network calls in `src/`), `cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 12`: 38 s, 0 warnings |
| Model | `Inkling-2-Mini-NVFP4-Mixed.gguf` 17,627,963,360 B, sha256 `304d4fe3…a48` (matches the card); `mtp.safetensors` `7c3b6513…` (the official DSpark drafter, same hash as the port's); `draft_shortlist.bin` `6ce69b27…`; `mmproj-Inkling-2-Mini-Q8_0.gguf` `23328727…` |
| Loader | accepts only GGUF Q8_0 (8) and NVFP4 (40) plus F32; experts of layers 0-19 NVFP4 with F32 `.scale` companions (`src/gguf_loader.cpp:101-102,348,365`) |
| Server | `nib serve --mtp mtp.safetensors --slots 1 -c 262848 --kv-type q8_0 --sparse-pages 224|0 --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 --default-min-p 0.0` (`--no-vision` for the speed and quality runs); scripts in `raw/` |
| Baseline | `maya-ik2` numbers from [`20261123-inkling-round`](../20261123-inkling-round/README.md) (port's `ik2_bench.py`, token-ID input, 129 generated tokens) |

## Smoke

- Starts at 262,848 context with Q8_0 KV, drafter and vision: 21.50 GiB reported by the engine (weights 16.34 GiB).
- Tool call and second turn (`agent_check.py`, 12,150-token system prompt): valid `read_file` call, 12,214 of
  12,254 prompt tokens reused, correct answer ([`raw/agent-base-sparse224.txt`](raw/agent-base-sparse224.txt)).

## Sampling and the drafter's fast path

600-token code answer, short prompt, sparse 224, drafter on (tok/s): temperature 1.0 with no top-k (card) **31.1 /
31.6**; `top_k 256` 150.8; `top_k 200` 156.4; `top_k 40` 155.9; `min_p 0.01` 138.9; greedy 165.4. The fused MTP
verifier works on a bounded candidate set (`MTP_VERIFY_TOPK = 256`, `include/kernels_mtp_verify.h:44`); an unbounded
tail takes the exact fallback. All speed rows below use `{"temperature":1.0,"top_k":256}`, a deviation from the card
that is a policy decision, not adopted.

## Speed by depth (HTTP, server timings, median of 2, 256-token cap)

`raw/depth_http.py`: a unique first line, then this repository's `docs/*.md` text to the depth, uncached.

| Prompt tokens | Nib sparse 224 decode | Nib dense decode | `maya-ik2` decode | Nib sparse 224 prefill | Nib dense prefill | `maya-ik2` prefill |
|---:|---:|---:|---:|---:|---:|---:|
| ~450-526 | 119.6 (calibration run) | 116.8 | 106.1 | 3,193 | 3,679 | 2,276 |
| 7,824 | **122.6** | 110.5 | 98.2 (8K) | 3,620 | 3,632 | 3,429 |
| 33,150 | **102.2** | 99.2 | 90.0 (32K) | 3,399 | 3,415 | 2,960 |
| 133,953 | **97.3** | 78.4 | 68.9 (128K) | 3,041 | 2,685 | 1,929 |
| 258,037 | **104.2** (97.5 / 111.0; one reply stopped at 27 tokens) | 59.7 (replies of 118 / 16 tokens) | 53.6 (262K) | **2,982** | 2,100 | 1,298 |

Raw: [`raw/speed.jsonl`](raw/speed.jsonl), calibration [`raw/speed-calib-cpt3.4.jsonl`](raw/speed-calib-cpt3.4.jsonl).
Different harness from `maya-ik2`'s (HTTP chat with sampling and drafter vs. token IDs, greedy, no drafter), so the
ratios are indicative; the like-for-like A/B is the same harness on both engines, not run.

## Retrieval (multi-needle, greedy, thinking off)

`raw/needle_http.py`: GSM8K questions as distractors, 4 seeded "access code" facts per prompt, all asked at once;
3 cases per depth, byte-identical prompts for both modes.

| Prompt tokens | sparse 224 | dense |
|---:|---:|---:|
| ~24.5K | 12/12 | 12/12 |
| ~98K | 12/12 | 12/12 |
| ~183.5K | 11/12 | 12/12 |
| **Total** | **35/36** | **36/36** |

Raw: [`raw/needle-base-sp224.jsonl`](raw/needle-base-sp224.jsonl), [`raw/needle-base-sp0.jsonl`](raw/needle-base-sp0.jsonl).
The 240K target came out at ~184K (chars-per-token misestimate); a true ~250K case is pending.

## GSM8K

The chat endpoint run scored 168/192 ([`raw/gsm-base-sp224.jsonl`](raw/gsm-base-sp224.jsonl)) and is **not a valid
comparison**: with thinking off and no tools Nib's chat template primes the text channel
(`<|message_model|><|content_text|>`, `src/server.cpp:1168-1173`), so most failures are 4-8-token direct answers,
while maya's prompt has no model prefix and the model reasons in text (median 221 tokens). The rerun sends maya's exact
rendered prompt to `/v1/completions` (`gsm8k_http.py --raw`): **186/192** base pack, sparse 224
([`raw/gsm-raw-base-sp224.jsonl`](raw/gsm-raw-base-sp224.jsonl)); **187/192** Unbound graft
([`raw/gsm-raw-unbound.jsonl`](raw/gsm-raw-unbound.jsonl)); `maya-ik2` 187/192.

## Engine defects seen (2e16cf0)

- `nib bench ... --sparse-pages 224` segfaults right after loading (exit 139); with `--sparse-pages 0` it ran 50 min at
  100% GPU without printing the depth-0 row and was killed ([`raw/bench-sp224.txt`](raw/bench-sp224.txt),
  [`raw/bench-sp0.txt`](raw/bench-sp0.txt)).
- `nib serve` without `--mtp` dies silently during "warming up HIP graphs" (sparse 224).

## Uncensored file

`raw/graft_unbound_q8.py` copies the Nib-Pack and overwrites its 120 Q8_0 attention tensors
(`blk.N.attn_{q,k,v,output,gate}.weight`) with the same tensors of `nokeepai/Inkling-2-Mini-Unbound-GGUF`
`Inkling-2-Mini-Unbound-v2.1-Q8_0.gguf`, read with HTTP range requests (631.1 MiB; shapes and types checked first).
All 120 differed; experts stay byte-identical NVFP4. Output sha256 `2384c91c74efedb50515a241581125058036953d93194a181825ee32c009b54f`.

- GSM8K 187/192 (above). Gray-zone refusals (the 8 prompts of `results/20261123-inkling-round/raw/refusal-q8dense.json`,
  temperature 0, 4,096 cap, `refusal_one.py`): **0/8** keyword refusals; prompt 4 hit the cap with empty content
  ([`raw/refusal-unbound.json`](raw/refusal-unbound.json)). The base pack also gave 0/8
  ([`raw/refusal-base.json`](raw/refusal-base.json)), so these prompts do not separate the two files; the edit's
  strength rests on its card (not re-measured here).

## Production check (2026-11-25, `launch.py` default, `:8080`)

- `python3 scripts/launch.py` starts `nib serve ... --mmproj ... -c 262144 --kv-type q8_0 --sparse-pages 224
  --default-temp 1.0 --default-top-k 256 --default-min-p 0.0`; ready with vision, 21.49 GiB.
- A request without sampling fields (600-token code answer): 178.4 tok/s, 3.1 tokens per drafter round, so the
  server-side `top_k 256` default applies.
- `_tmp/maya/r23/agent_check.py 8080`: valid `read_file` call, 196 of 236 prompt tokens reused, correct answer.
