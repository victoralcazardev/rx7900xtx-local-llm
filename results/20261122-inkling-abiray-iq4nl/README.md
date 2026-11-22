# Inkling-2-Mini: Abiray uncensored IQ4_NL on the GodGMN fork (2026-11-22)

**What**: validate Abiray's `Inkling-2-Mini-Uncensored-IQ4_NL.gguf` (a GGUF of OpenUncensored/Inkling-2-Mini-Uncensored)
on the `hip-inkling` engine before it replaces AtomicChat AD-Q4_K. The user asked for no head-to-head ("serán muy
parecidos"); the AtomicChat rows below are from the [earlier run](../20261122-inkling-uncensored-ad-q4k/README.md) with
the same `llama-bench` command, and from [the DSpark run](../20261122-inkling-dspark-fork/README.md) with the same
request script.

**Conclusion**: **adopted**. Faster at every depth (decode 61.1 / 52.1 / 43.1 tok/s at 0 / 64K / 192K), 1.4 GiB less
memory at 262K, 0/8 keyword refusals on a gray-zone set. Its experts are all IQ4_NL, so `maya-ik2` can read the same file.

## Setup

| | |
|---|---|
| File | `Inkling-2-Mini-Uncensored-IQ4_NL.gguf`, 14,922,756,096 bytes, sha256 `e6680ab9f97c4aadee065273ec063124d543c66708c0a7d64849c424c3dbdace` (matches the Hugging Face LFS oid); `inkling2_loop`, 24 blocks, 48 expert tensors IQ4_NL, 0 scale tensors |
| mmproj | `mmproj-Inkling-2-Mini-Uncensored-BF16.gguf`, sha256 `887d47ddd19cc6582b681a9bf5b80734e2453dd02f705b58f27481274df3cb87` (not loaded: text-only profile) |
| Engine | `llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix` (`build 12606, commit cb0e46960`) |
| GPU | RX 7900 XTX, 272 W cap |

## Results

| | Abiray IQ4_NL | AtomicChat AD-Q4_K (earlier runs) |
|---|---|---|
| Plain decode, `run.sh` code / prose, temperature 0 | **59.9 / 59.8** tok/s | 50.0 / 50.0 |
| GPU memory in use at 262K `q8_0`/`q8_0` after load | **21,305 MiB** | 22,710 MiB |
| `llama-bench` pp4096 / tg128, depth 0 | 1,704.38 / **61.14** | 1,663.36 / 50.13 |
| same @ 65,536 | 909.40 / **52.08** | 888.96 / 45.53 |
| same @ 196,608 | 439.25 / **43.08** | 413.05 / 26.19 |
| `smoke.py inkling2-mini-unc` (wired profile, temperature 1.0) | 59.1 tok/s | 44.1 tok/s |
| Gray-zone refusals (8 prompts, keyword + manual read) | 0/8 by keyword; 7 full answers, 1 partial (paywall: legitimate routes only) | not run |

`llama-bench` command (both files): `llama-bench -m <gguf> -fa 1 -ngl 99 -ub 256 -ctk q8_0 -ctv q8_0 -p 4096 -n 128 -r 1
-d 0,65536,196608` (one repetition). Raw: `raw/llama-bench.md`, `raw/refusal-summary.txt` (answers not published),
`raw/refusal.py`; the request script is [`../20261122-inkling-dspark-fork/raw/run.sh`](../20261122-inkling-dspark-fork/raw/run.sh)
with `M=<gguf>`.

## Limits

- One repetition per cell; the AtomicChat column is from earlier sessions the same day.
- The refusal set is 8 gray-zone prompts, not a harmful-prompt benchmark; quality (MMLU, coding suite) not measured here.
- Why IQ4_NL decodes faster than AD-Q4_K on this fork is not analysed.
