# Inkling-2-Mini DSpark drafter on the GodGMN fork (2026-11-22)

**What**: can the GodGMN `inkling-rdna3` fork (`cb0e46960`, the `hip-inkling` engine) use Inkling's official
speculative drafter, and what is the plain-decode baseline with the wired profile? Asked by the user as
"comprobar el MTP": Inkling has no MTP head; its checkpoint ships a 3-layer DSpark block drafter
(`mtp.safetensors`), which Unsloth converts to GGUF.

**Conclusion**: **the drafter does not load.** The fork lists `draft-dspark` in `--spec-type`, but its loader
rejects Unsloth's drafter (`markov_w1.weight` is 256 x 201,024, the loader expects 256 x 200,058). Inkling DSpark
support lives in ggml-org PR #32218 (open, draft, changes requested on 2026-11-22) and in Unsloth's fork, not in
b12600 + the fork's commits. Plain decode with the wired flags: **50.0 tok/s** on code and prose, 22,710 MiB in use.

## Setup

| | |
|---|---|
| Engine | `llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix` (`1.0.0-dev (build 12606, commit cb0e46960)`) |
| Target | AtomicChat `Inkling-2-Mini-Uncensored-AD-Q4_K.gguf` (sha256 `36e99f1f…`) |
| Drafter | `unsloth/Inkling-2-Mini-GGUF` `dspark-Inkling-2-Mini-Q8_0.gguf`, 402,278,560 bytes, sha256 `2ec78510da837e8fc3be54a14757a0c5fbd2d8d9e85a0d92853fafdf674f3773` |
| Flags | `-c 262144 -ctk q8_0 -ctv q8_0 -fa on -np 1 --ctx-checkpoints 10 -ngl all` (the `262k-q8q8` profile minus sampling and `--metrics`); drafter arm adds `-md <drafter> --spec-type draft-dspark --spec-draft-n-max 3 -ngld all` (Unsloth's card command) |
| Requests | temperature 0, `reasoning_effort: low`, `max_tokens` 768; one code prompt (LRU cache module + tests) and one prose prompt (300-word story), two repeats each, fresh server per arm |
| GPU | RX 7900 XTX, power cap 272 W |

Command: `raw/run.sh <label> [extra args]` (home path normalised to `~`).

## Results

| Arm | Code tg (tok/s) | Prose tg (tok/s) | VRAM in use (MiB) |
|---|---|---|---|
| plain | 50.0 / 50.0 | 50.0 / 50.0 | 22,710 |
| DSpark n=3 | did not start | did not start | — |

Raw lines: `raw/results.txt`; load error: `raw/dspark-load-error.log`.

## Notes

- The 50.0 tok/s here vs. 42.0 in the [262K smoke](../20261122-inkling-uncensored-ad-q4k/README.md): different
  prompts and output lengths (768 vs. a short answer); both are near-empty context.
- Retest when PR #32218 (or a port of Unsloth's DSpark loader) lands in an engine that also holds 262K; the
  drafter costs ~0.4 GB of VRAM, inside the ~1.8 GiB left at 262K `q8_0`/`q8_0` (24,560 - 22,710 MiB).
