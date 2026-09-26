# 2026-09-26 — long-context retrieval quality at 240K, `262k-q8q51-mtp`

**Measures**: whether retrieval quality holds at 240K fill on the 262K-context, KV q8_0/q5_1
profile — input to the 262K-vs-224K default decision (`docs/STATUS.md`). Same method as
the 2026-09-26 220K run: `bench/longctx_quality.py`, the Spanish-language multi-key retrieval
corpus (deliberately Spanish — see the script's own docstring and
[`../../docs/STYLE.md`](../../docs/STYLE.md) §1), 2 documents × 4 questions, temperature 0.

**Conditions**: engine `hip-kvmix`, Qwen3.8-27B GSQ-RCO IQ3_S-mtp, `-c 262144`, KV `q8_0/q5_1`,
MTP `--spec-draft-n-max 2`, 272 W power cap, fill 240,000 tokens (prompt 240,111 exact).

**Command**: `bench/longctx_quality.py --run --inhibitor-ok --ctx 262144 --depths 240000 --docs 2
--variants q8q51-mtp2`.

**Raw data**: `bench/res/longctx_quality/longctx-20260926-104551/` (local only, `bench/res` is
git-ignored).

**Results**: **8/8 exact match, 0 loops, 0 truncated.** Cold prefill 400 tok/s. Follow-up
questions reuse 239,595 cached tokens; generation 23.0-24.0 tok/s (short JSON answers). Peak
process VRAM 22,830 MiB, 0 evicted, hotspot max 98°C.

**Conclusion**: the +27% KLD of KV q8_0/q5_1 over q8_0/q8_0 (`kv-quality.md`) does not show up as
a retrieval error at 240K fill. Cumulative long-context retrieval quality: **60/60 exact match**
(52/52 q8_0/q8_0 from 32K-220K, `20260926-longctx-quality-224k/`, plus this 8/8 q8_0/q5_1 at
240K). This result cleared the quality bar for adopting `262k-q8q51-mtp` as the default profile
— see [`../../docs/DECISIONS.md`](../../docs/DECISIONS.md).

## Exact adopted config confirmation (MTP n=3, `-ub 256`), 2026-09-26

**Measures**: the run above used MTP `--spec-draft-n-max 2` and no `-ub 256` — not the exact
flags `262k-q8q51-mtp` ships with (MTP n=3, `-ub 256`, adopted after this folder's first run —
see `20260926-mtp-n3-depth/` and `20260926-ubatch256-262k/`). This run repeats the same corpus
and method on those exact flags.

**Conditions**: engine `hip-kvmix`, Qwen3.8-27B GSQ-RCO IQ3_S-mtp, `-c 262144`, KV `q8_0/q5_1`,
MTP `--spec-draft-n-max 3`, `-ub 256`, 272 W power cap, fill 240,000 tokens (prompts
240,105-240,111), 2 documents × 4 questions, temperature 0.

**Command**: `bench/longctx_quality.py --run --ctx 262144 --variants q8q51-mtp1 --depths 240000
--docs 2 --mtp-n 3 --extra "-ub 256"` (the `--mtp-n`/`--extra` flags, added in commit 17567ff, to
run the exact profile flags instead of only the fixed n=2 default).

**Raw data**: `bench/res/longctx_quality/` (local only, `bench/res` is git-ignored).

**Results**: **8/8 exact match, field accuracy 1.0, 0 loops, 0 truncated, 0 failures.** Cold
prefill 380-382 tok/s. Follow-up questions reuse 239,845-239,851 cached tokens and process
~255-262 new tokens at 142-152 tok/s; generation 27.9-29.7 tok/s (short JSON answers; the
n=2/no-`-ub 256` run above gave 23.0-24.0 tok/s). Peak process VRAM 22,628 MiB, GTT 8 MiB,
0 evicted, hotspot 99°C, system VRAM peak 24,432 of 24,560 MiB. Run time 23.9 min.

**Conclusion**: quality holds on the exact shipped flags (MTP n=3, `-ub 256`), not just the
n=2/no-`-ub 256` configuration measured above. Cumulative long-context retrieval quality:
**68/68 exact match** (60/60 above, plus this 8/8 on the exact adopted config).
