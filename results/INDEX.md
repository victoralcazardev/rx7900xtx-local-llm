# Results index

Raw evidence files (`.json`/`.jsonl`) are never rewritten in place (`docs/STYLE.md` §7): they keep
the field names and values recorded at measurement time, some of which are Spanish. Personal
machine paths inside them are the one allowed exception and have been replaced with placeholders
(`~/models/...`, `~/engines/<build-dir>/llama-server`). Glossary for the Spanish keys/values still
present: `caso` = case, `carga_s` = load time (s), `mtp_acept` = MTP acceptance (accepted/proposed),
`etiqueta` = label, `codigo`/`razonamiento`/`edicion` = per-task columns (code/reasoning/edit),
`task: ensayo`/`copia`/`codigo` = task type (essay/copy/code).

| Date | Test | Folder | Script | Conclusion | Measurements doc |
|---|---|---|---|---|---|
| 2026-09-24 | Vulkan vs. ROCm baseline | [`20260924-vulkan-vs-rocm-baseline/`](20260924-vulkan-vs-rocm-baseline/) | `llama-bench` | ROCm 2-3.5x faster for generation on Linux | [`engines.md`](../docs/measurements/engines.md#vulkan-vs-rocm-generation-and-prompt-processing) |
| 2026-09-24 | Engine build comparison | [`20260924-engine-build-comparison/`](20260924-engine-build-comparison/) | `llama-bench` | Compiler toolchain (ROCm 10), not the source, explains own-build speed | [`engines.md`](../docs/measurements/engines.md#engine-matrix-corrected-rocm-10-toolchain) |
| 2026-09-24 | Weight quantization matrix | [`20260924-model-quant-matrix/`](20260924-model-quant-matrix/) | `llama-bench` + `llama-perplexity` | IQ3_S-mtp selected as the model | [`kv-quality.md`](../docs/measurements/kv-quality.md#weight-quantization-matrix-perplexity-toks) |
| 2026-09-24 | Context/KV/MTP matrix | [`20260924-context-kv-mtp-matrix/`](20260924-context-kv-mtp-matrix/) | `bench/ladder_bench.py` | MTP n=2 sweet spot at 128K; 262K+MTP+q8/q8 OOMs | [`depth.md`](../docs/measurements/depth.md#context-kv-and-mtp-server-real-matrix-empty-context-baseline) |
| 2026-09-24 | MTP vs. DFlash2 vs. n-gram | [`20260924-speculative-mtp-dflash-ngram/`](20260924-speculative-mtp-dflash-ngram/) | `bench/spec_bench.py` | MTP n=2 wins at empty context | [`speculative.md`](../docs/measurements/speculative.md#mtp-vs-dflash2-vs-n-gram-empty-context) |
| 2026-09-24 | KV cache quantization KLD | [`20260924-kv-quantization-kld/`](20260924-kv-quantization-kld/) | `llama-perplexity --kl-divergence` | q8/q8 and q8/q5_1 safe, q4_0 discarded | [`kv-quality.md`](../docs/measurements/kv-quality.md#kv-cache-quantization-kld-vs-f16) |
| 2026-09-24, night | VRAM breakdown at load, 262K | [`20260924-vram-breakdown-262k/`](20260924-vram-breakdown-262k/) | `llama-server -lv 4` | MTP draft KV stays at f16 default | [`memory.md`](../docs/measurements/memory.md#vram-breakdown-at-load--lv-4-log-262k-context-mib) |
| 2026-09-24, night | Depth matrix at 262K (128K/240K) | [`20260924-depth-262k-deep/`](20260924-depth-262k-deep/) | `bench/depth_bench.py` predecessor | 23.8 tok/s at 240K (superseded, see below) | [`depth.md`](../docs/measurements/depth.md#depth-matrix-at-262k-target-128k--240k-llama-server-400-token-response) |
| 2026-09-24 | Context-full stress test | [`20260924-context-stress-test/`](20260924-context-stress-test/) | `bench/oom_probe.py` predecessor | VRAM margin, not a driver bug, is the failure mode | [`depth.md`](../docs/measurements/depth.md#context-full-stress-test-total-vram-including-desktop-24560-mib) |
| 2026-09-24 | Coexistence with a 2nd GPU process | [`20260924-coexistence/`](20260924-coexistence/) | `convivencia.sh` (not ported) | Late arrival degrades, main server doesn't crash | [`coexistence.md`](../docs/measurements/coexistence.md#coexistence-test) |
| 2026-09-24/25, night | 128K/240K with fdinfo | [`20260924-depth-128k-240k-fdinfo/`](20260924-depth-128k-240k-fdinfo/) | `bench/depth_bench.py` predecessor | 240K settles at 18.4 tok/s, supersedes the earlier 23.8 reading | [`depth.md`](../docs/measurements/depth.md#240k-with-fdinfo-repeated-q8q5_1--mtp-n2-262144-reserved) |
| 2026-09-25 | 190K A/B: kvmix vs. vec4 | [`20260925-depth-190k-kvmix-vs-vec4/`](20260925-depth-190k-kvmix-vs-vec4/) | `bench/spec_depth_bench.py` | kvmix wins by 14-17%, vec4 not adopted | [`speculative.md`](../docs/measurements/speculative.md#ab-at-190k--c-204800-kv-q8q8-kvmix-vs-vec4-mtp-n2) |
| 2026-09-25 | DFlash2 and "native q8" fork at 190K | [`20260925-dflash2-native-q8-190k/`](20260925-dflash2-native-q8-190k/) | `bench/spec_depth_bench.py` | Neither adopted; MTP n=2 on kvmix stays the reference | [`speculative.md`](../docs/measurements/speculative.md#dflash2-and-the-native-q8-kv-fork-at-190k) |
| 2026-09-25 | Multi-agent concurrency: 1/2/4 slots, MTP on/off | [`20260925-concurrency-slots/`](20260925-concurrency-slots/) | `bench/concurrency_bench.py` | Aggregate throughput drops as slots increase; recommend 1 slot + MTP, queue | [`concurrency.md`](../docs/measurements/concurrency.md#1-vs-2-vs-4-slots-mtp-onoff-2026-09-25) |
| 2026-09-25 | `-ub` and MTP screening at 128K fill (272 W) | [`20260925-ubatch-mtp-screening-128k/`](20260925-ubatch-mtp-screening-128k/) | `bench/spec_depth_bench.py` | `-ub 512` stays optimal at depth; n=3 content-dependent, not adopted as default; p-min 0.3 within noise | [`speculative.md`](../docs/measurements/speculative.md#-ub-and-mtp-screening-at-128k-fill-272-w-2026-09-25), [`engines.md`](../docs/measurements/engines.md#flags-checked-against-llama-server---help-b11160-rocm) |
| 2026-09-25 | Context-window ladder: 224K and 240K (272 W) | [`20260925-context-window-ladder/`](20260925-context-window-ladder/) | `bench/spec_depth_bench.py` | Both fit; 224K adopted as the new default, 240K as the measured maximum | [`depth.md`](../docs/measurements/depth.md#context-window-ladder-224k-and-240k-272-w-2026-09-25) |
| 2026-09-25 | Long-context retrieval quality, `200k-q8q8-mtp` (32K/128K/190K) | [`20260925-longctx-quality-200k/`](20260925-longctx-quality-200k/) | `bench/longctx_quality.py` | 44/44 exact match, 0 loops, up to 190K fill (190K partial: 1 of 5 documents) | [`depth.md`](../docs/measurements/depth.md#quality-ruler-style-200k-q8q8-mtp) |
| 2026-09-26 | ROCm runtime A/B: TheRock 10.0.0 vs. system 7.2.4 | [`20260926-rocm-runtime-ab/`](20260926-rocm-runtime-ab/) | `llama-bench` | ROCm 10 runtime -1..-2% tg, -5% pp, higher variance — rejected | [`engines.md`](../docs/measurements/engines.md#rocm-runtime-ab-therock-1000-vs-system-724-2026-09-26) |
| 2026-09-26 | Long-context retrieval quality at 220K, `224k-q8q8-mtp` | [`20260926-longctx-quality-224k/`](20260926-longctx-quality-224k/) | `bench/longctx_quality.py` | 8/8 exact match; 52/52 cumulative 32K-220K | [`depth.md`](../docs/measurements/depth.md#quality-ruler-style-200k-q8q8-mtp) |
| 2026-09-26 | BeeLlama v0.4.7 + KVarN: parity and KLD | [`20260926-beellama-kvarn/`](20260926-beellama-kvarn/) | `llama-bench` + `llama-perplexity` | KVarN rejected (~2.7x KLD of q8/q8); BeeLlama -18-22% tg vs. our engine | [`kv-quality.md`](../docs/measurements/kv-quality.md#beellama-kvarn-kld-2026-09-26) |
| 2026-09-26 | Long-context retrieval quality at 240K, `262k-q8q51-mtp` (incl. exact adopted flags) | [`20260926-longctx-quality-262k/`](20260926-longctx-quality-262k/) | `bench/longctx_quality.py` | 8/8 + 8/8 exact match; 68/68 cumulative 32K-240K | [`depth.md`](../docs/measurements/depth.md#quality-ruler-style-200k-q8q8-mtp) |
| 2026-09-26 | MTP n=3 confirmed at depth (190K/240K fill) | [`20260926-mtp-n3-depth/`](20260926-mtp-n3-depth/) | `bench/spec_depth_bench.py` | n=3 wins by 9-11% mean tg on both profiles; adopted as the new default | [`speculative.md`](../docs/measurements/speculative.md#mtp-n3-confirmed-at-depth-190k-and-240k-fill-2026-09-26) |
| 2026-09-26 | `-ub 256` on `262k-q8q51-mtp` n=3, system VRAM headroom | [`20260926-ubatch256-262k/`](20260926-ubatch256-262k/) | `bench/spec_depth_bench.py` | `-ub 256` adopted (-350 MiB, +190 MiB system margin); corrects the 224K margin claim | [`memory.md`](../docs/measurements/memory.md#-ub-256-on-the-262k-default-and-system-vram-headroom-2026-09-26) |

## Not curated (skipped, kept only on disk, not published)

Runs with no standalone value (superseded by a later, better-instrumented run in the same
campaign; duplicate content; failed-setup noise; or files too large/raw to curate):

- The first 240K depth attempt (client timeout at 27% prefill, invalid result) — superseded by the
  fdinfo-instrumented repeat in `20260924-depth-128k-240k-fdinfo/`.
- `flags.md` (`-ub`/`ROCBLAS_USE_HIPBLASLT` micro-benchmark): all within noise of default, already
  fully stated as a one-line conclusion in `docs/measurements/engines.md` — no separate result
  folder adds value.
- The 190K quality-related raw request/response/telemetry files (multi-MB `.sse`/`.jsonl` per task,
  under `mtpprof-*/n2/` and `mtpprof-*/dfl5/`): only the small `summary.jsonl`/`command.json` per run
  were curated; the embedded full prompts and SSE streams are not published.
- The first 190K long-context-quality launch (`bench/res/longctx_quality/longctx-20260925-170119/`):
  empty result (0 rows) — the process was orphaned and killed before writing anything, restarted as
  the run curated in `20260925-longctx-quality-200k/`.
