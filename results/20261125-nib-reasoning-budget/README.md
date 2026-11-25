# Nib thinking cap (`--reasoning-budget`) and the start-up crash bisect (2026-11-25)

**What**: two production problems of the `262k-nib` profile (Nib `2e16cf0`, Inkling-2-Mini Unbound v2.1).
(1) Reasoning loops: two real agent turns spent the harness's `max_tokens` 32,768 on looping thinking (135 s and
145 s, no tool call), the second already at the Unbound card's `temp 0.6 / top_p 0.95`
([evidence](../../docs/models/inkling-2-mini.md)). The card asks for "a thinking cap" ("we used 4,096 tokens");
upstream Nib has none. (2) The `hipGraphInstantiate` start-up segfault that blocked upstream `bdc9307`
([record](../20261125-nib-bdc9307/README.md)).

**Status: thinking cap adopted** (`reasoning_budget = 4096` in the profile, engine built from
[`engine-patches/nib-reasoning-budget-2e16cf0.patch`](../../engine-patches/nib-reasoning-budget-2e16cf0.patch)).
Greedy output with the cap unset or at 4096 is byte-identical to production `2e16cf0`. Not yet observed on a real
looping agent turn. The start-up crash is **not caused by `aa394af`**: fresh builds of the production commit crash too.

Versions: Nib `2e16cf0` plus the patch, ROCm `hip-runtime-amd 10.1-2.1` (`libamdhip64.so.7.16.0-4f6d503`),
CachyOS kernel 7.3.5, RX 7900 XTX. Model and serve flags as `python3 scripts/launch.py --dry-run` prints, port 4444.

## 1. The patch

Server-side only (`src/server.cpp`, `src/main.cpp`, `src/server.hpp`, 137-line diff). `nib serve --reasoning-budget N`
(default `-1`, off) counts the tokens a reply spends inside `<|content_thinking|>`; once it reaches `N`, the next
token is replaced by `<|end_message|>`, so the model closes the thinking block and goes on to its answer or tool
call. The replacement only ever hits a token that is not in the KV yet (the sampled token that becomes `cur_tok`);
in the MTP path the accepted-draft loop is truncated at the cap exactly like the existing draft-EOS truncation, so
`verify_rollback` and the drafter commit stay consistent. A capped reply logs `think-cap` in its `[serve]` line,
and the `[nib] Config:` line prints `reasoning_budget=N`. Rebuild:

```bash
git -C <nib-checkout> checkout 2e16cf0
git -C <nib-checkout> apply engine-patches/nib-reasoning-budget-2e16cf0.patch
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 16   # in the checkout, 0 warnings
```

## 2. Checks

Server log lines: [`raw/serve-lines.txt`](raw/serve-lines.txt).

| Check | Command | Result |
|---|---|---|
| Cap fires, answer follows | `serve.sh … --reasoning-budget 256`, `capreq.py` (train timetable) | `finish stop`, 396 tokens, 171.3 tok/s with MTP, thinking cut mid-sentence, answer correct (15:33:15), log `think-cap` |
| Streaming with a tool, cap 256 | `toolreq.py` ×3 | thinking stayed under 256: 1 text reply, 2 `read_file` tool calls, no `think-cap` |
| Streaming with a tool, cap 32 | `toolreq.py` ×4 | `think-cap` on 4/4, then a text answer with no tool call (`finish stop`): a 32-token cap is too short for this prompt, as expected |
| Parity, cap unset | `parity.py`, greedy, 4 prompts, patched vs. production binary | byte-identical replies ([`raw/greedy-patched-unset.jsonl`](raw/greedy-patched-unset.jsonl) = [`raw/greedy-2e16cf0.jsonl`](raw/greedy-2e16cf0.jsonl)); speed 186.6 / 177.2 / 163.0 / 200.0 vs. 187.1 / 177.7 / 163.3 / 200.4 tok/s |
| Parity, cap 4096 | same, `--reasoning-budget 4096` (no prompt reaches it) | byte-identical ([`raw/greedy-patched-4096.jsonl`](raw/greedy-patched-4096.jsonl)) |

## 3. Start-up crash bisect

Every start: [`raw/startup-runs.txt`](raw/startup-runs.txt). [`raw/loop.sh`](raw/loop.sh) starts `serve` N times in a row (3 s after the previous exit), sends one chat request
per start and records the exit; [`raw/alt.sh`](raw/alt.sh) alternates two binaries. Every crash is SIGSEGV (exit
139) right after `[InklingEngine] Ready!`, in `hipGraphInstantiate` from `DSparkDrafter::capture_draft_graphs`.

| Binary | Mode | Starts | SIGSEGV |
|---|---|---:|---:|
| `bdc9307` with the five captures back to `hipStreamCaptureModeGlobal` | consecutive | 20 | 7 |
| `aa394af` (the fix commit alone) | consecutive | 20 | 4 |
| `2d23530` (before `aa394af`; changes only `src/server.cpp`) | consecutive | 20 | 2 |
| `2e16cf0`, production binary built 2026-11-24 | consecutive | 20 | **0** |
| `2e16cf0`, fresh build of the same commit and toolchain | consecutive | 20 | 2 |
| production / fresh `2e16cf0` | alternated | 15 + 15 | 0 + 0 |
| `2e16cf0` + this patch | consecutive | 20 | 1 |

Conclusions: the `ThreadLocal` capture mode of `aa394af` is not the cause (`Global` crashes as well), and neither is
the rest of `aa394af`, because `2d23530` and a fresh `2e16cf0` build crash too. No package changed since
2026-11-23 16:40, before the production build; the two `2e16cf0` binaries have the same size and differ in 298,435
bytes. With the production binary at 0 crashes in 50 starts (35 here, 15 in the [`bdc9307` record](../20261125-nib-bdc9307/README.md)), against
~10% for every fresh build, the fault looks like a latent host-side defect in Nib (uninitialized state or a race)
that the binary layout exposes or hides; root cause not found. It only ever hits start-up: a crashed start is
visible at once and is simply relaunched.
