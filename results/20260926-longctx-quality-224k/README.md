# 2026-09-26 — long-context retrieval quality at 220K, `224k-q8q8-mtp`

**Measures**: whether retrieval quality holds at the real operating depth of the adopted
`224k-q8q8-mtp` profile (`-c 229376`, KV q8_0/q8_0, MTP n=2), closing the "no validation at the
real 220K depth" gap tracked in `docs/STATUS.md`. `bench/longctx_quality.py`: the same
Spanish-language multi-key retrieval corpus as the 2026-09-25 190K run (deliberately Spanish —
see the script's own docstring and [`../../docs/STYLE.md`](../../docs/STYLE.md) §1), 2 documents ×
4 questions, temperature 0.

**Conditions**: engine `hip-kvmix`, Qwen3.8-27B GSQ-RCO IQ3_S-mtp, `-c 229376`, KV `q8_0/q8_0`,
MTP `--spec-draft-n-max 2`, 272 W power cap, fill 220,000 tokens (prompt 220,109 exact).

**Command**: `bench/longctx_quality.py --run --inhibitor-ok --ctx 229376 --depths 220000 --docs 2
--variants q8q8-mtp1`.

**Files**: `summary.jsonl` / `metadata.json` — 2 documents, 4 questions each (8 total), matching
`docs/BENCHMARK-FORMAT.md`.

**Results**: **8/8 exact match, field accuracy 1.0, 0 loops, 0 truncated, 0 failures.** Cold
prefill 420.3 tok/s (~8.7 min). Follow-up questions reuse 219,593 cached tokens and process ~515
new tokens each; generation 25.1-26.1 tok/s (short JSON answers). Peak process VRAM 22,702 MiB,
GTT 8 MiB, 0 evicted, hotspot max 98°C. Run time 20.7 min.

**Conclusion**: closes the validation gap at the real 220K operating depth. Cumulative
long-context retrieval quality for q8/q8 KV + MTP n=2: **52/52 exact match from 32K to 220K**
(44/44 from the 2026-09-25 32K/128K/190K run, plus this 8/8). Anecdotal "q8 KV amnesia beyond
150K" claims ([`../../docs/SOURCES.md`](../../docs/SOURCES.md)) do not reproduce here.
