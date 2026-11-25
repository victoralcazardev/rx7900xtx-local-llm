# Nib agent levers: cache retention, `--slots 2`, drafter rounds (2026-11-25)

**What**: three questions about how the production Nib profile (`inkling2-mini-unbound-nib` / `262k-nib`, Nib
`2e16cf0`) serves coding agents. (1) How much of a real agent session is prompt reading, and how much of that comes
from full re-reads? (2) Does `--slots 2` keep a second agent's prefix, so A→B→A stops re-reading? (3) What does one
DSpark ("MTP") round cost at agent depths?

**Status: measured, no profile change.** Re-reads cost real time (about 20 s per switch at 63K), `--slots 2` does
not fix them on this Nib build, and the drafter round is cheap and keeps its acceptance to 65K. Turning the drafter off per request
(`mtp: false`) is a trap: decode falls to 6.7-10.2 tok/s on a short prompt and to ~0.4 tok/s at 8K.

## 1. Agent traffic (two real sessions)

[`raw/agent_traffic.py`](raw/agent_traffic.py) over the two production logs of the morning (60 agent turns, prompts
above 5,000 tokens; [`raw/agent-traffic.txt`](raw/agent-traffic.txt)):

| | Value |
|---|---|
| Prompt tokens served from cache | 88.8% (3,094,189 of 3,484,376) |
| Prompt reading / generation | 125 s / 412 s (280 s of it in the two reasoning loops at the cap) |
| Reading share of server time | 23.2%; 48.5% without the two loops |
| Turns re-reading >10K new tokens | 9, together 106 s of the 125 s of reading |
| Median agent turn | 300 ms reading, 257 tokens in 1.6 s |

Seven of the nine turns re-read the whole prompt (`cached 0`) at 32-72K: 9.5-23.1 s each. The pattern matches a
second prompt (a subagent, a compaction or a title request) evicting the main agent's prefix from the single slot.

## 2. `--slots 2` and A→B→A

[`raw/slots-run.sh`](raw/slots-run.sh) starts the production command (without `--mmproj`, `--no-vision`) once with `--slots 1` and once with
`--slots 2` on port 4444 and runs [`raw/abab.py`](raw/abab.py): two distinct ~63K prompts alternated A, B, A, B, A,
then a 163K prompt and A, B again (`temperature 0`, 64 tokens). Raw rows: [`raw/abab.jsonl`](raw/abab.jsonl);
server configs: [`raw/slots-config.txt`](raw/slots-config.txt).

| | `--slots 1` | `--slots 2` |
|---|---|---|
| Server config | `slots=1(262144/slot, solo)` | `slots=2(131072/slot, req_max=262144, elastic)` |
| VRAM reported | 21.17 GiB | 21.30 GiB |
| Cached tokens, all 8 requests | 0 | 0 |
| Slot used, all 8 requests | 0 | 0 |
| 63K request, wall | 20.3-20.8 s | same |
| 163K request, wall | 54.0 s | same |
| Decode | 127-136 tok/s | 128-136 tok/s |

With `--slots 2` every request still went to slot 0 and re-read from scratch, so the second slot kept nothing for
sequential alternation. The run has no A→A control, so it does not show whether an identical repeat would hit; the
real sessions above show prefix extension does hit (88.8%). Whether Nib can route by prefix (or by a client slot
id) needs a source read of `src/server.cpp` and possibly an upstream request; nothing here changes the profile.

## 3. Drafter rounds by depth

[`raw/drafter_rounds.py`](raw/drafter_rounds.py) against the production server (shipped sampling: temp 0.6,
top_p 0.95, top_k 256; thinking at the server default), a coding request over repository docs, 512 tokens, three
repeats. Values are the server's own per-response `timings`
([`raw/drafter-rounds.jsonl`](raw/drafter-rounds.jsonl)). The first request (8K, repeat 0) ran on a cold server:
27.6 tok/s with 97.6 ms verify per round, left out below.

| Depth (prompt tokens) | tok/s | Tokens per round | Draft ms/round | Verify ms/round |
|---|---|---|---|---|
| 7,840 (2 runs) | 144.8-168.0 | 2.89-2.95 | 1.60-1.62 | 15.6-17.9 |
| 33,212 (3 runs) | 142.2-150.0 | 2.76-3.01 | 1.58-1.61 | 16.6-17.2 |
| 68,018 (3 runs) | 136.3-162.1 | 2.59-3.63 | 1.60-1.64 | 16.6-20.2 |

Drafting costs about 1.6 ms of a ~18 ms round (under 10%); the round is the target model's verify pass. Acceptance
does not fall with depth to 68K. Two replies stopped early (8K: 150 tokens; 68K: 98 tokens), and the 162.1 tok/s at
68K is the 98-token one.

## 4. Drafter off per request

The same server with `"mtp": false` in the request ([`raw/drafter-off.txt`](raw/drafter-off.txt), server log lines):

| Request | Decode |
|---|---|
| 31-token prompt, 64 tokens, drafter on, shipped sampling | 131.0 tok/s |
| same, `mtp: false`, `temperature 0` | 10.2 tok/s |
| same, `mtp: false`, shipped sampling | 6.7 tok/s |
| 8K coding request, `mtp: false`, shipped sampling | 370 tokens after 904 s (~0.4 tok/s), client timed out |

On `2e16cf0` the drafter-off path is not a plain decode at the same speed minus speculation: it is 13-20x slower
at a short prompt and much worse at 8K, so the drafter's net gain cannot be read as "MTP vs. no MTP" from this
build. Never send `mtp: false` to this server. A first attempt at the 8K run, while `whisper-cli` large-v3 shared
the GPU, ran at 333 tokens in 375 s; the clean rerun above shows the slowness is the path, not the shared VRAM.
Why the path is slow (no decode graph, CPU sampling or something else) was not traced in the source.

## Not measured

- Concurrent requests with `--slots 2` (only sequential alternation was run).
- A→A control for the slot test.

## Reproduce

Production server up on `:8080` for parts 1 and 3; nothing else on the GPU (Nib reserves ~21.2 GiB of the 24 GiB):

```
python3 raw/agent_traffic.py _tmp/logs/<nib-log>...
python3 raw/drafter_rounds.py 8080 --depths 8192 32768 65536 --gen 512 --repeats 3   # --no-mtp: see part 4
bash raw/slots-run.sh        # stops production, uses port 4444, assumes the author's ~/IA layout
```
