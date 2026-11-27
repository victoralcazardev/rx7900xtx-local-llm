# Strata 0.2.23 with ISTA's Inkling GSQ-RCO IQ3_S on the RX 7900 XTX (2026-11-27)

**What**: the first Strata release that reads ISTA's GSQ-RCO Inkling quants — Terminal 0.2.23 launching its own Inkling
engine (`strata-inkling` `0.1.70`, `linux-x86_64-hip-rx7900` package with the bundled ROCm runtime) on
`ISTA-DASLab/Inkling-2-Mini-GSQ-RCO-GGUF` IQ3_S at 262,144 tokens, one `strata launch` command, no llama.cpp beside it.
Decode and prefill at 7.8K/33K/134K/258K with the same harness and sampling as the day's [Nib](../20261127-nib-v022/README.md)
and [tintero](../20261127-tintero-dflash2/README.md) rounds, plus GSM8K 192.

**Status: not adopted.** The engine now decodes ISTA's per-tensor mixed experts natively — no SF4 transcode — but it
runs at 57.8/44.3/25.0/17.6 tok/s, about half Nib's decode at 8K and a sixth of it at 258K, with prefill 2.0-3.5x below
Nib and a depth slope Nib does not have (-70% from 8K to 258K against -12%). The file it ran is 11.4 GB: it fits this
card outright, so there was nothing for Strata's expert paging to win. Production stays `2e16cf0` + the thinking-cap
patch; Strata stays the candidate for models whose experts do not fit VRAM.

## What changed since 0.2.22: the IQ3_S experts are read as they are

The 0.2.22 engine (`0.1.67`) repacked IQ2_*/IQ3_S gate-up and Q2_0 down experts to SF4 at load, and the native HIP
decoders were an open PR (#6933). The engine's own startup line settles it:

```text
[ink-hip] native lossless GGUF_RAW GPU kernels active for 3072/3072 experts (zero S_K transcode)
```

That is the whole engine log besides its command line (494 B, `~/.local/state/strata/launch/gsq-rco-iq3_s-256k.engine.log`).
The Terminal downloaded the Inkling engine package at launch (97 MB), verified the package signature and every file,
test-started it, then started it detached:

```text
strata launch --model-path <dir> --model gsq-rco-iq3_s --family inkling-2-mini --context 256k --vision off \
  --parallel 1 --tune skip --access local --port 4445 --yes --no-tui
```

`--tune skip` means no Strata tuning pass, so these are its untuned defaults. `strata launch` returned 0 at 19:40:27,
`/health` answered at once and the launch log records `Loading the model… 15 s`; the engine process itself was started
as `strata-inkling --serve --native <dir>/Inkling-2-Mini-GSQ-RCO-IQ3_S.gguf --max-context 262144 --vram-experts-gb 11.99
--draft off` ([`raw/processes.txt`](raw/processes.txt)).

**No drafter.** The ISTA folder held the GGUF only, so Strata launched with `--draft off`. 0.2.23 takes the DFlash2
drafter as a sidecar file next to the model (its own settings note: "DFlash 2 is the only drafter on CUDA since 0.2.23
(sidecar beside the model)"); there was no `dflash2.safetensors` there, and none was fetched for this run.

## Speed by depth

Decode tok/s, median of 2 repeats, median prefill in parentheses; prompts unique per request (a nonce line first),
uncached, 256-token cap, 256 tokens generated except where noted. VRAM at 262,144 tokens: 86%. Raw:
[`raw/speed.jsonl`](raw/speed.jsonl) (4 rows).

| Prompt tokens | Strata 0.2.23 + IQ3_S | Nib `sp=224` (nib-v022 A) | Nib `sp=0` (this afternoon) | Tintero sparse (this afternoon) |
|---:|---:|---:|---:|---:|
| 7,823 | 57.8 (1,764) | 121.2 (3,582) | 143.1 (3,695) | 98.3 (3,284) |
| 33,142 | 44.3 (1,555) | 120.8 (3,433) | 106.4 (3,444) | 92.2 (2,874) |
| 134,456 | 25.0 (1,083) | 108.0 (3,030) | 86.9 (2,691) | 78.6 (1,669) |
| 258,569 | 17.6 (846) | 106.9 (2,961) | 66.5 (2,115) | 90.5 (1,171) |

Per-repeat `tg_all`: 57.9/57.7, 45.1/43.4, 26.9/23.0 (one reply stopped at 104 tokens), 16.9/18.3. Against Nib's
production arm Strata is 2.1x/2.7x/4.3x/6.1x slower and prefills 2.0x/2.2x/2.8x/3.5x slower; against the afternoon's
tintero sparse arm it is 1.7x/2.1x/3.2x/5.1x slower. Nib's two arms come from different runs on differently loaded
hosts, so the Nib-vs-Nib pair is a direction only; tintero's sparse 134K cell is likewise the midpoint of an
88.8/68.4 spread measured on a loaded host. No ordering in the table depends on those caveats.

**The depth slope is the bigger problem than the 8K number.** Strata loses 70% of its decode between 8K and 258K while
Nib's sparse arm loses 12% and tintero's sparse arm 8%. At 7.8K, Strata is at 48% of Nib and at 258K at 16%: whatever
makes depth cheap on the other two engines (paged or sparse attention over distant KV) is not what this launch was
doing. This run does not isolate the cause: it varied none of the launch settings that could affect attention, so the
slope is the engine's default behaviour on this card.

## GSM8K

**176/192 correct (91.7%)**, 16 wrong, 2 hit the 4096-token cap (questions 116 and 119, `finish: length`), 190 stopped
on their own; 628 s of generation for the 192 questions. This is **not the same harness** as Nib's 187/192: this run
went through `/v1/chat/completions` without the harness's `--raw` mode, whereas the Nib figure
([2026-11-25](../20261125-nib-bdc9307/README.md)) used the raw prompt path, which pins the prompt to the model's own
chat template with `reasoning_effort="none"` and no tools. The two numbers therefore do not measure the same prompt
format and give **no quality verdict on IQ3_S versus Nib's pack** — a chat-path figure has never been collected for
Nib either. Per-question rows: [`raw/gsm-strata-iq3s.jsonl`](raw/gsm-strata-iq3s.jsonl).

## Setup

| | |
|---|---|
| Dates / GPU | 2026-11-27 19:40-20:18 local (WET), RX 7900 XTX 24 GB (gfx1100), CachyOS, kernel 7.3.6-1-cachyos |
| Start condition | load 8.40, GPU use 2%, no other engine running ([`raw/conditions.txt`](raw/conditions.txt)) |
| Strata | Terminal 0.2.23, installed by the signed `install.sh` into `~/.local` as the user (no root); the bundle reports `strata-control` `0.1.70`, commit `4560d03`; `~/.local/bin/strata` → `~/.local/share/strata/terminal/current/bin/strata` |
| Engine | `strata-inkling` `0.1.70-linux-x86_64-hip-rx7900` from `~/.local/share/strata/components/shapes/inkling2/engine/`, bundled ROCm runtime, signature checked at install |
| Model | `ISTA-DASLab/Inkling-2-Mini-GSQ-RCO-GGUF` rev `f0da1097`, IQ3_S 11,425,259,648 B, sha256 `8a351537…` (matched the repo's LFS pointer when it was fetched); deleted after the run for disk space, so it cannot be re-hashed now |
| Launch flags | `--context 256k --vision off --parallel 1 --tune skip --access local --port 4445 --yes --no-tui`; engine line as quoted above (`--vram-experts-gb 11.99 --draft off`) |
| Harness | `depth_http.py 4445 --depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9 --sampling '{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}'`, then `gsm8k_http.py` (both borrowed unchanged from the nib-v022 run); every request sends `reasoning_effort: "none"` |
| Sequence | [`raw/run.sh`](raw/run.sh) — it waits for the day's other benchmarks to finish before launching |

One operational wrinkle: the scripted stop failed. `strata runtime stop` requires `--profile` (usage error, log not kept),
so the `strata runtime cleanup` fallback ran, and the `pgrep` right after it ([`raw/processes.txt`](raw/processes.txt))
still listed the engine; it was no longer running when the machine was
checked later, so nothing Strata held the GPU past the session.

## Not measured

- Nib on the same chat-path GSM8K harness, which is what would turn the two quality numbers into a comparison.
- Strata with `--tune` (Strata's own tuning pass) and with `--vram-experts-gb` above 11.99, which is what the launch
  wrote: at 86% VRAM there is headroom left.
- A DFlash2 sidecar beside the model, and `--parallel` above 1.
- Any model that does not fit VRAM, which is the case Strata is built for. This run only answers "does it read ISTA's
  mixed IQ3_S natively, and what does it cost on a file that already fits".

## Raw files

[`raw/run.sh`](raw/run.sh) · [`raw/speed.jsonl`](raw/speed.jsonl) (4 rows) · [`raw/conditions.txt`](raw/conditions.txt) ·
[`raw/processes.txt`](raw/processes.txt) · [`raw/gsm-strata-iq3s.jsonl`](raw/gsm-strata-iq3s.jsonl) (192 questions) ·
[`raw/gsm-summary.txt`](raw/gsm-summary.txt). The launch, stop and engine logs stay in the git-ignored
`_tmp/strata-iq3s/` and `~/.local/state/strata/launch/`; the engine log (two lines, quoted above) is the only place the
no-transcode claim comes from.
