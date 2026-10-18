# 2026-10-18: coding suite baseline, Qwen3.8-27B (seed 1)

**Question**: does the 27B production profile on b11718 solve the six coding-suite tasks? This is the
baseline that engine updates and other models are compared against with `--compare`.

**Scope, reduced by the user's request** ("quiero que sea mucho menos"): one seed per task. The planned
B1c calibration (two full runs plus a `q4_0`/`q4_0` KV weaker arm, ~7 h of GPU) was cut, so flakiness
and the ceiling risk are not measured ([`docs/ENGINES-EXPERIMENTS.md`](../../docs/ENGINES-EXPERIMENTS.md#coding-suite-design-b1a-2026-10-18)).

## Setup

- Model `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf`, profile `262k-q8q51-mtp` launched by `scripts/launch.py`
  on the `hip-kvmix` engine b11718 (`~/engines/llama-b11718-linux-rocm10-gfx1100-kvmix`).
- `bench/coding_suite.py --run`, suite version 2 (commit `4597d93`), seed 1, sampling sent per request:
  temperature 1.0, top_p 0.95, top_k 20, min_p 0.0. 272 W cap, `systemd-inhibit`, Brave closed.
- Two runs of the same build: CS1-CS2 from the first one (stopped when the calibration was cut),
  CS3-CS6 from the second. `meta.json` is the second run's.
- Per task: `result.json` (outcome, turns, wall time, tokens) and `model.diff` (the final change).

## Results

|Task|tests|completed|Turns|Wall s|Completion tokens|
|---|---|---|---|---|---|
|CS1 local bug fix|pass|yes|13|73.1|3,479|
|CS2 cross-file change|pass|yes|15|261.3|5,629|
|CS3 tool-error recovery|pass|yes|10|63.8|2,000|
|CS4 long context (114,229 tokens)|pass|yes|3|324.5|3,471|
|CS5 post-compaction continuation|pass|yes|22|138.8|4,970|
|CS6 artifact in a bounded result|pass|yes|15|43.0|1,473|

6/6 pass, 15 min of episodes in total.

## What it found before the baseline

Suite version 1 only had whole-file writes. On the first calibration run, CS2 (3/3 seeds) and CS3 (2/2)
ended with `finish_reason: length`: the model rewrote `more.py` (~4,900 lines) or `bottle.py`
(~4,500 lines) whole and hit `max_tokens` 32768. That is a limit failure, not a quality one. Version 2
adds `edit_file` (one exact, unique replacement); CS3's injected write error now hits the first write of
either kind. CS1 passed 3/3 on that run with whole-file writes (tomli's parser is ~700 lines).

## Limits

- One seed: a pass may be lucky and a task at 6/6 may be too easy to show a regression.
- A task the baseline passes and a candidate fails at seed 1 reruns with seeds 2-3 on both arms
  (`--compare` says so); a single-seed loss is not a regression on its own.
