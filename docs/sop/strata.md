# SOP: Strata with the Qwen3.8-Flash-Next Coder

Run [Strata](https://github.com/Niko1221/Strata) with the ISTA-DASLab Coder IQ1_M as an alternative to the
default llama.cpp profile, on the same port and harness wiring. Background, upstream claims and the trial
criterion: [`../models/strata-flash-next.md`](../models/strata-flash-next.md). Measurements:
[`../../results/20261015-strata-coder-first-run/`](../../results/20261015-strata-coder-first-run/README.md).

Only one engine serves `:8080` at a time: Strata and `llama-server` both need nearly all of the 24 GB VRAM.

## Layout

| What | Where (example) | Size |
|---|---|---|
| Strata clone (tracks upstream `main`) | `~/IA/Motores/Strata` | ~0.3 GB + engine |
| Model shards (must be on NVMe; an HDD stalls, upstream #605) | `<models_root>/Qwen3.8-Flash-Next-GSQ-RCO-Coder-IQ1_M/` | 58.4 GB |
| Pack (`experts.bin` 25.1 GB + `dense.bin`) and MTP layer | `~/IA/Motores/Strata-data/` (setup default: next to the clone) | ~32 GB |
| Config written by setup | `<clone>/strata-coder-iq1_m.json`, start script `run-coder-iq1_m.sh`, log `strata-coder-iq1_m.log` | — |

Total disk: ~90 GB on NVMe. `Strata-data/mtp/tensors` (4.9 GB) is only the source of the MTP layer; setup
verifies it, so keep it.

## Install

```bash
git clone https://github.com/Niko1221/Strata ~/IA/Motores/Strata && cd ~/IA/Motores/Strata
./setup.sh --check --backend hip       # GPU/RAM/CPU check, lists what fits
./setup.sh --setup --family coder --model IQ1_M --gguf-dir <dir with both shards> \
  --backend hip --vision no --no-browser --yes --no-start --context 131072 --kv int8
```

Setup compiles the engine for gfx1100 against a system ROCm 7 in `/opt/rocm` (10-20 min, once), builds the
pack and the MTP layer, and writes the config. Then add to `"env"` in `strata-coder-iq1_m.json`:
`"STRATA_RESIDENT_HEADROOM_GIB": "6"` (keeps 6 GiB of RAM free instead of 4; upstream tip #834 for 31 GB PCs).

Gotcha: re-running setup with another `--kv` printed the new choice but left the old `--kv` in `"args"`;
check the JSON after every setup run.

## Start, stop, update

A small wrapper (machine-local, not in this repo) does start/stop: `qwen-flash` starts it, `qwen-flash stop`
stops it. Its logic, so it can be rebuilt:

1. Refuse to start when `/tmp` is a tmpfs holding more than 2 GiB, and list its biggest files (never delete
   them). tmpfs files live in RAM until deleted; under pressure they go to zram, which is RAM as well, and
   video barely compresses: 8 GiB of test renders left there fed an idle OOM (see "Before you start").
2. Stop a `llama-server` on `:8080` if one runs (`ia` uses the same port).
3. Refuse to start below 16 GiB of `MemAvailable` (experts in RAM + headroom + server) and list the biggest
   processes; `--force` overrides both checks. Below this a long prompt OOM-killed the desktop (see results).
4. Start `run-coder-iq1_m.sh` detached and poll `http://127.0.0.1:8080/v1/models` until it answers (~35-45 s).
5. Stop: `SIGTERM` to `serve/server.py`, which also ends the `engine/strata` child; `SIGKILL` after 30 s.

Update: `cd <clone> && ./update.sh` (git pull + engine rebuild when needed; models untouched), then re-check
the config JSON.

## Harness

Strata speaks the OpenAI API at `http://127.0.0.1:8080/v1` (any model name, any key) plus `/v1/messages`
and `/v1/responses`. Wire it as a second provider `local-flash-128k` (contextWindow 131072) on `:8080`, next
to `local-262k`; `python3 scripts/check-sync.py` accepts it as optional. Pick the provider that matches the
engine you started. The response carries `reasoning_content`; reasoning effort (off/low/medium/high) is honoured.

## Before you start: free RAM

The Coder needs ~7.75 GiB of experts copied into RAM at 128K int8, plus the 6 GiB headroom. Close browsers,
Electron apps and idle agent CLIs first. Check the start log for
`resident RAM mode: ... GiB of experts in RAM` and, during long prompts, for `stall report` lines.

16 GiB is not enough on its own (2026-10-15, [`results/20261015-strata-coder-idle-oom/`](../../results/20261015-strata-coder-idle-oom/README.md)):
the copy is sized as `MemAvailable` minus the headroom, so it grows with free RAM (9.05 GiB from 16.3 GiB
available), and the kernel OOM killer fired with no request sent. Check `/tmp` (`df -h /tmp`) and zram
(`zramctl`) too: `MemAvailable` does not count what they hold as free.
