# 2026-10-04: llama.cpp PR #29509 (no draft KV in prompt checkpoints), restore correctness

**Question**: does [ggml-org/llama.cpp#29509](https://github.com/ggml-org/llama.cpp/pull/29509)
keep context-checkpoint restores correct on gfx1100 with the production profile, and does it make
checkpoints constant-size? On b11371 every prompt checkpoint also serializes the MTP draft model's
KV cache, so its size grows with the context. The patch removes that one call (`pr29509.diff`,
one file, +9/-1). This is a correctness gate, not a speed test.

## Setup

- **Baseline**: production engine `hip-kvmix` b11371, commit `99b9548`
  ([`docs/ENGINES.md`](../../docs/ENGINES.md)).
- **Patch**: the same source and commit plus PR #29509 at head
  `b3c27359975ea4fb0f400785de3fc2729a35708a` (PR open and unreviewed on 2026-10-04), applied with
  `git apply` (one hunk, offset only) and built with the same `docs/ENGINES.md` recipe (ROCm 10
  toolchain). `CMakeCache.txt` matches the production build apart from paths; runtime libraries are
  the same.
- **Server**: the production argv of `qwen38-iq3s-mtp` / `262k-q8q51-mtp` from
  `scripts/launch.py --dry-run`, unchanged, plus a test port (18085) and `-lv 4` for checkpoint
  logging. Exact command in `arm.sh`.
- **Requests** (`requests/`, frozen; built from repository docs by `make_requests.py`): all at
  temperature 0 with first-token top-5 logprobs and `max_tokens` 48.
  - A: a 3-turn chat, 11,490 prompt tokens.
  - A′: A with one word changed ~100 tokens before the end of the last user message.
  - B: an unrelated prompt, 9,504 tokens.
  - A′ cold: A′ with `cache_prompt: false`.
- **Model**: Qwen3.8-27B GSQ-RCO IQ3_S-mtp.

## Procedure

Per arm, one fresh server, then `run_arm.py` sends 11 requests in this order:

1. **Resident edited-tail restore** (a1, a2): A, then A′. A′ diverges after the last checkpoint, so
   the server must restore an earlier checkpoint held in memory.
2. **RAM prompt-cache restore** (b1, b2): A, B, A′. B replaces the slot, so A′ must come back from
   the host prompt cache (`--cache-ram`) and then restore a checkpoint.
3. **Cold reference**: A′ with `cache_prompt: false`.

`arm.sh` waits for a start gate (junction <90 °C, memory <95 °C, no other `llama-server`) and aborts
on 3 consecutive readings above 104 °C junction / 105 °C memory, VRAM free <300 MiB, system swap
growth >1 GiB, or server VmSwap >1 GiB. No abort triggered. `compare.py` reads both
`*.results.json` files and writes `compare.txt`.

```bash
bash arm.sh baseline ~/engines/<b11371-build-dir>
bash arm.sh patch ~/engines/<b11371-pr29509-build-dir>
python3 compare.py > compare.txt
```

## Results

| Metric | Baseline (b11371) | Patch (b11371 + #29509) |
|---|---|---|
| Checkpoint restores on warm requests | 8/8 | 8/8 |
| First-token top-5 logprob difference vs. baseline | — | 0 (all 11 requests) |
| Generated text | — | identical (11/11) |
| `cache_n` / `prompt_n` per request | 11,230 / 260 on restores | identical |
| MTP + n-gram acceptance | 370/435 = 0.851 | 370/435 = 0.851 |
| Checkpoint size | 149.669-194.756 MiB, grows with tokens | **149.626 MiB constant** (26/26) |
| Host prompt-cache entry, A | 1,244.2 MiB | 1,120.5 MiB |
| Host prompt-cache entry, B | 980.4 MiB | 906.7 MiB |
| `ctx_dft pos_max` warnings | 0 | 0 |

- Every warm request restored the checkpoint at n−260 (11,230 tokens). The RAM-cache cases first
  logged `found better prompt with f_keep = 0.991`. B logged a full re-process, as expected for
  an unrelated prompt.
- Baseline sizes fit **149.6 MiB + ~4,120 B per token** (11,486 tokens → 194.756 MiB): the draft
  KV term. The patch removes it. At ~183K tokens the baseline term is ~720 MiB per checkpoint
  (extrapolated from the fit, not measured here).
- Warm vs. cold A′: top-1 matches within 2.3e-5; tail tokens near logprob −10 differ by up to
  0.29 nats, **identically in both arms**, so this comes from b11371 batch-shape numerics, not
  from the patch.
- Per-request detail: `compare.txt`; raw timings, top-5 logprobs, texts and the server log lines
  emitted per request: `baseline.results.json`, `patch.results.json`.

## Not measured

- Host RSS and checkpoint memory at deep context (~180K), where the saving per checkpoint is
  largest.
- Wall time and prefill/decode speed; partial-rejection stress beyond these 11 requests.

## Conclusion

PR #29509 passes the correctness gate on gfx1100: restores are bit-identical to b11371 on both the
resident and the host-prompt-cache paths, and checkpoints become a constant ~149.6 MiB instead of
growing ~4,120 B per token. It is in local trial use, not adopted as the published engine — see
[`docs/ENGINES-EXPERIMENTS.md`](../../docs/ENGINES-EXPERIMENTS.md#llamacpp-pr-29509-local-trial-2026-10-04)
and [`docs/measurements/memory.md`](../../docs/measurements/memory.md#current-conclusion).
