# Coexistence test (extracted from telemetry, not copied raw)

Main server (IQ3_S-mtp) with a full context generating 3,000 tokens; a second Vulkan process
(Qwen3.5-2B Q8_0, 16K context) starts 25 s in and answers one request. VRAM/GTT sampled every second
(raw telemetry not published, see `../../docs/BENCHMARK-FORMAT.md`).

| Case | Full context | Main tg (alone to with 2nd) | 2nd process | Peak VRAM | Peak GTT | Errors |
|---|---:|---|---|---:|---:|---|
| C1: 262K q8/q5_1 + MTP, no vision | 182K | 25.4 to 21.5 | 10.6 tok/s (slow) | 24,463 MiB | 2,358 MiB | none |
| C2: 262K q8/q8, no MTP, no vision | 182K | 19.3 to 17.7 | 11.7 tok/s (slow) | 23,801 MiB | 2,204 MiB | none |
| C3: 128K q8/q8 + MTP + vision | 104K | 30.7 to 32.6 | 93.4 tok/s (normal) | 22,859 MiB | 1,246 MiB | none |

`gen-C1.json`/`gen-C2.json`/`gen-C3.json`: the second process's own generation summary
(`{"ok": true, "gen_tokens": 3000, "tg_tok_s": <value>}`).

See [`../../docs/measurements/coexistence.md`](../../docs/measurements/coexistence.md#coexistence-test)
for the conclusion (whoever arrives late degrades, the main server doesn't crash).
