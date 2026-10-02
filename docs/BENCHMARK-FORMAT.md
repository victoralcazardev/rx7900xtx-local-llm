# Benchmark format

How the numbers in `docs/measurements/` are produced and reported, and how `results/` is laid out.
Loosely inspired by the shape (not the content — different hardware, different engine) of
[SergiioB's Intel Arc Pro B70 inference cookbook](https://github.com/SergiioB/intel-arc-pro-b70-inference-cookbook):
control what's cached, use real tokens, report by phase, keep failed runs as evidence instead of
deleting them.

## Metric definitions

- **pp (prompt processing)**: prompt tokens processed per second during the prefill phase. Reported
  as `pp512` (llama-bench's fixed 512-token prompt probe) or as "mean pp" for a real prompt of N
  tokens (total prefill time / N).
- **tg (text generation)**: output tokens generated per second during decode. Reported as `tg128`
  (llama-bench's fixed 128-token probe) or as measured tg for a real response.
- **Depth**: the number of tokens already in context (prompt + prior turns) at the point generation
  is measured. `tg128 @16K` means: fill the context to 16K tokens, then measure generating 128 more.
  This matters because both pp and tg change as the KV cache grows — a number without a stated depth
  is only the empty-context case.
- **Cold cache**: the KV cache does not contain the current prompt's prefix; the server must
  reprocess it from scratch. **Warm cache**: a prior turn's prefix is still in the KV cache and gets
  reused; only the new tokens are processed. `timings.prompt_n` (new tokens processed) and
  `timings.cache_n` (tokens reused from cache) distinguish the two in llama-server's response.
- **Acceptance rate (MTP / speculative decoding)**: accepted draft tokens ÷ proposed draft tokens
  (`draft_n_accepted / draft_n` in llama-server's timings). Depends heavily on content — a single
  number without stating the task type and context depth is not comparable across runs.
- **MTP n (`--spec-draft-n-max`)**: how many draft tokens the MTP head proposes per step before
  verification. Larger n means more to gain if accepted, more to lose if rejected, and (per
  `docs/measurements/speculative.md`) can change which FlashAttention kernel gets used.
- **KLD (KL divergence)**: `llama-perplexity --kl-divergence`, measures how far a quantized
  configuration's output-token probability distribution is from an f16/BF16 reference over the same
  text. Reported as mean, percentiles (p99, p99.9), max, "same top-1" (% of tokens where the
  highest-probability token is unchanged), and `PPL(Q)/PPL(base)`. Lower KLD and a `PPL` ratio closer
  to 1.0 is better. See `docs/measurements/kv-quality.md` for how this is used to compare KV cache
  and weight quantizations.
- **VRAM: MiB vs. GiB**: MiB (2^20 bytes) is used for exact measured values, matching what
  `fdinfo`/`llama-server`'s memory breakdown report. GiB is used for round, human-scale figures (a
  24 GiB card, a "~20 GiB" estimate). Always binary units — see `docs/STYLE.md` §2. A figure quoted
  as "process VRAM" is a per-process `fdinfo` reading (see below); a figure quoted as "total VRAM"
  includes the desktop and other GPU clients, and is noisier.
- **Temperature**: °C, from the card's hwmon sensors (edge, junction/hotspot, memory). "Sustained
  load" means the reading after temperatures have stopped climbing under continuous generation, not
  an instantaneous sample.
- **n (repetitions)**: how many independent samples back a number. Most figures in
  `docs/measurements/` are explicitly marked when they come from a single sample — treat those as a
  data point, not a stable average, until repeated. A "reproduces" note means two runs with the
  *same* input (e.g. same seed) gave the same result — that confirms determinism, it is still not two
  independent samples.

## Method

- **Speed** (`llama-bench`): `-ngl 999 -fa 1 -ctk q8_0 -ctv q8_0 -p 512 -n 128 -d 0,16384 -r 2` as a
  baseline sweep; add more `-d` points, more `-ctk`/`-ctv` combinations (comma-separated — llama-bench
  runs every combination in one invocation), or more repetitions (`-r`) as needed. `-d` matters:
  the Vulkan/ROCm gap and the MTP depth penalty are not constant across depths, so measure at the
  depth you care about instead of extrapolating from `-d 0`.
- **Quality (perplexity/KLD)** (`llama-perplexity`): `-f wiki.test.raw -c 512 --chunks 150 -fa on`
  (wikitext-2-raw, ggml-org's CI corpus) as a relative ranking between quantizations of the *same*
  base model. On a finetuned model, this mixes the finetune's effect with the quantization's effect
  — don't compare perplexity across different base models or finetunes as if it were an absolute
  quality score.
- **Real server** (`llama-server`): the exact flags from `models.toml`, a 1024-token response to a
  fixed prompt. Read `timings.predicted_per_second` and `draft_n_accepted/draft_n` from the response.
  VRAM: `mem_info_vram_used` is system-wide and includes the desktop and other GPU clients; report
  its remaining headroom directly when that is the metric of interest. Do not subtract a fixed
  desktop estimate. Use per-process `fdinfo` (below) for the server's own allocation.
- **Context-full stress test**: fill the context with N real tokens (from a real corpus, e.g.
  `wiki.train.raw`) and request a real response; sample VRAM every second throughout. This is the
  only way to see failures that only appear with a full context, because the KV cache is reserved at
  startup but compute buffers grow with use.
- **Per-process memory** (`fdinfo`): read `/proc/<pid>/fdinfo/<render-node-fd>` for
  `drm-memory-vram`, `drm-memory-gtt`, `amd-requested-vram` and `amd-evicted-vram`. This is
  independent of what the desktop or other GPU clients are doing, and is the metric to trust for
  margin and for detecting a silent spill to system RAM. See `docs/measurements/memory.md`.
- Every method above is implemented by a script in `bench/` — see `bench/README.md` for the mapping
  from old to new script names and what each one measures.

## Cold/warm cache and repetition, for a server measurement

1. Start a fresh server (cold KV cache) for the first measured request.
2. For a warm-cache measurement, send a second request on the *same* server that reuses the prior
   turn's history plus a short new question, and check `timings.cache_n` to confirm how much was
   actually reused (a partial reuse is common at a document boundary — a checkpoint may only cover
   part of the prior prompt).
3. Where a result is reported as a single sample, that is stated explicitly in
   `docs/measurements/*.md` — treat it accordingly rather than as a settled average.

## Immutable evidence

Once a result is published, it is never rewritten in place. A new measurement that contradicts an
earlier conclusion supersedes it: the "Current conclusion" block at the top of the relevant
`docs/measurements/*.md` file is updated, and the previous conclusion moves to that file's dated
"History" section with a link to the new evidence. The old data point stays visible and dated — it
is superseded, never deleted. A result folder under `results/` is likewise never edited after the
fact; a corrected or repeated measurement gets a new dated folder, and the older one stays as-is,
referenced from the newer one's `README.md` if relevant.

## How `results/` is laid out

```text
results/
  INDEX.md                        date · test · folder · script · conclusion · link
  YYYYMMDD-topic-variant/
    README.md                     what it measures, exact command, conclusion, link back to
                                   the docs/measurements/*.md section that cites it
    summary.md / summary.jsonl    the small, extracted numbers (never a full raw log)
    command.json                  the exact argv used, when available
    metadata.json                 run metadata (model/engine identity, sha256, timestamp), when small
```

Only small, valuable files are kept: extracted summaries and small structured JSON. Raw per-request
logs, SSE streams, full telemetry traces, and anything over 1 MB are **not** published here — where
only a raw log exists, the key numbers are extracted by hand into `summary.md` instead, with a link
to the `docs/measurements/*.md` table that already reports them. See `results/INDEX.md` for the full
list of published result folders and `bench/README.md` for the scripts that produced them.
