# 2026-10-04: recall on real agent history at 80K and 176K, production sampling

**Question**: does the production profile still recall facts from early in a real coding-agent
session when the context holds ~80K or ~176K tokens of that session, under the production sampling
and reasoning settings? The earlier 40/40 retrieval run
([`20261003-longctx-quality-190k-240k/`](../20261003-longctx-quality-190k-240k/README.md)) used a
synthetic corpus, temperature 0, thinking off and no n-gram map; this probe covers the 60-180K
range where agent sessions actually run, with the settings a session actually uses.

**Raw data is private.** The prefixes come from one private coding-agent session, so the prompts,
questions, expected answers, model outputs, runner scripts and logs are not published; this README
reports only aggregate counts, question IDs and token positions.

## Setup

- **Engine**: production `hip-kvmix` b11371 (`99b9548`, [`docs/ENGINES.md`](../../docs/ENGINES.md)),
  Qwen3.8-27B GSQ-RCO IQ3_S-mtp.
- **Server**: the production argv of `qwen38-iq3s-mtp` / `262k-q8q51-mtp` from
  `scripts/launch.py --dry-run`, only the port changed to a test port (18086):

  ```bash
  ~/engines/<build-dir>/llama-server -m ~/models/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
    --port 18086 -c 262144 -ctk q8_0 -ctv q5_1 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
    -fa on -np 1 --ctx-checkpoints 4 -ngl all --metrics --spec-type draft-mtp,ngram-map-k4v \
    --spec-draft-n-max 3 -ub 256 --reasoning-effort medium --cache-ram 12288
  ```

- **Prefixes**: the message history of one real session (user, assistant with its reasoning, and
  tool messages; the harness system prompt and tool schemas are not included), cut at two
  depths: **81,620** and **178,645** tokens after the chat template (measured by the server's
  `/apply-template` + `/tokenize`). The 80K prefix is a prefix of the 176K one.
- **Questions**: 16 per depth, frozen before the run. Each asks for one short fact stated at a
  known position in the prefix (positions are approximate token offsets from an
  offline render, within ~2% of the templated count); scored as a case-insensitive substring match of the expected
  string in the answer `content` (an answer found only in the reasoning counts as a miss).
  - 80K: A01-A12 (token positions 1,036-36,391) and T80a-T80d (67,467-79,688, the last ~20% of the
    80K prefix).
  - 176K: A01/A03/A05/A08/A10/A12, T80a-T80d (same facts and positions as at 80K, now at 38-45% of
    the prefix), B01/B02 (52,052 / 57,945) and U01-U04 (146,240-176,662, the tail).
- **Arms**: per depth, 3 seeds (1, 2, 3) at the production sampling (temperature 1.0, top-p 0.95,
  top-k 20, min-p 0), then a temperature-0 arm (t0). Thinking on at the server's medium effort,
  `max_tokens` 4096. 64 requests per depth.
- **Safety gate** (same as the E3 runs): start only below 90 °C junction / 95 °C memory; abort on
  3 consecutive readings above 104 °C junction / 105 °C memory, VRAM free <300 MiB, system swap
  growth >1 GiB, or server VmSwap >1 GiB.

## Results

All 128 requests ended with `finish_reason: stop`; no truncation, no empty answers. Max completion
898 tokens at 80K and 3,080 tokens at 176K.

| Depth | s1 | s2 | s3 | t0 | Seed mean (spread) |
|---|---:|---:|---:|---:|---|
| 80K | 16/16 | 15/16 | 15/16 | 15/16 | 15.33 (1) |
| 176K | 14/16 | 14/16 | 14/16 | 15/16 | 14.00 (0) |

Misses by question ID and position:

| ID | Position | 80K misses | 176K misses | Classification |
|---|---:|---|---|---|
| T80c | 79,184 | s2, s3, t0 | s1, s3 | Ambiguous question: the answer is a different value defined in the same passage (near distractor). Question-design defect |
| T80d | 79,688 | none | s1, s2, s3, t0 | The 176K prefix renames the same planned item twice after the 80K mark; the model answers with a later name. Supersession, not recall loss |
| A08 | 14,072 | none | s2 | The model ignored the question and continued the original session's task (off-task answer), once |

- Every other question was correct in every arm at both depths, including the early ones
  (A01-A12, 1K-36K), the middle (B01/B02, 52-58K) and the tail of the 176K prefix (U01-U04).
- **Excluding T80c and T80d**, 176K scores 14/14, 13/14, 14/14 and t0 14/14; 80K scores 14/14 in
  every arm.

## Prefix reuse and conditions

- One cold prefill per depth: 81,675 tokens in 133 s at 80K; 178,700 tokens in 400 s at 176K
  (~447 tok/s, under desktop load). Every following request processed only 57-80 new tokens, with
  `cache_n` 81,609 (80K) and 178,634 (176K); no full re-process.
- Max junction / memory 95 / 95 °C. The 80K results come from a server start whose following 176K
  pass was stopped by the safety gate; the 176K results come from a later, separate start that
  completed without a gate trip.
- Two earlier 176K attempts were stopped by the safety gate: one after 14 of 64 requests (12/14,
  misses T80c and T80d) when free VRAM fell to 122 MiB while another GPU application was open on
  the desktop (the step was not attributed), and one during the cold prefill when system swap grew
  by more than 1 GiB from concurrent desktop activity (the server's own VmSwap stayed below its
  limit). Both are excluded from the tables above.

## Conclusion

No position-dependent recall loss was observed up to ~178K tokens of real agent history at the
production sampling and reasoning settings: early, middle and tail facts were recalled in every arm
at both depths. The only depth-related difference is that the 176K history contains a later rename
of one fact, and the model answers with the latest version. The sample is small (16 questions per
depth, one session), and this is a retrieval/recall check, not a coding-quality result. T80c and
T80d must be reworded before the question sets are reused. See
[`docs/measurements/depth.md`](../../docs/measurements/depth.md#current-conclusion).
