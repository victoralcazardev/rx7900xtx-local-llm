# SOP: Strata with the Qwen3.8-Flash-Next Coder

**Parked since 2026-10-21**: the Coder is not installed ([state](../models/strata-flash-next.md#parked-state-2026-10-21)); this procedure is kept for when testing resumes.

Run [Strata](https://github.com/Niko1221/Strata) with the ISTA-DASLab Coder IQ1_M as an alternative to the
default llama.cpp profile, on the same port and harness wiring. Background, upstream claims and the trial
criterion: [`../models/strata-flash-next.md`](../models/strata-flash-next.md). Measurements:
[`../../results/20261015-strata-coder-first-run/`](../../results/20261015-strata-coder-first-run/README.md),
current config: [`../../results/20261016-strata-coder-vram-reserve/`](../../results/20261016-strata-coder-vram-reserve/README.md).

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
  --backend hip --vision no --no-browser --yes --no-start --context 262144 --kv int8 --vram-reserve-mib 3072
```

Setup compiles the engine for gfx1100 against a system ROCm 7 in `/opt/rocm` (10-20 min, once), builds the
pack and the MTP layer, and writes the config. Then add to `"env"` in `strata-coder-iq1_m.json`:
`"STRATA_RESIDENT_HEADROOM_GIB": "6"` (keeps 6 GiB of RAM free instead of 4; upstream tip #834 for 31 GB PCs).

Why these values: the engine offers `--kv fp16|int8|k8v4|q4_0`; int8 is the 8-bit one (k8v4 and q4_0 store 4-bit V/K). Shrinking the KV does not
free VRAM in Strata, because the expert cache takes whatever is left; only `--vram-reserve-mib` keeps VRAM
free. 3072 leaves ~1.4 GiB of the card free while loaded, enough for the desktop to open apps without the
driver pushing GPU memory into RAM (without it a Slack launch ended the KDE session). The cost is ~2.3 GiB more
experts in RAM.

Gotcha: re-running setup with another `--kv` printed the new choice but left the old `--kv` in `"args"`;
check the JSON after every setup run.

## Start, stop, update

A small wrapper (machine-local, not in this repo) does start/stop: `qwen-flash` starts it, `qwen-flash stop`
stops it. Its logic, so it can be rebuilt:

1. Refuse to start when `/tmp` is a tmpfs holding more than 2 GiB, and list its biggest files (never delete
   them). tmpfs files live in RAM until deleted; under pressure they go to zram, which is RAM as well, and
   video barely compresses: 8 GiB of test renders left there fed an idle OOM (see "Before you start").
2. Stop a `llama-server` on `:8080` if one runs (`ia` uses the same port).
3. Refuse to start below 21 GiB of `MemAvailable` (15.03 GiB of experts in RAM at 262K with the reserve + 6 GiB
   headroom) and list the biggest processes; `--force` overrides both checks. Below it the engine cuts the copy
   and reads the rest from the SSD, and a long prompt once OOM-killed the desktop (see results).
4. Start `run-coder-iq1_m.sh` detached and poll `http://127.0.0.1:8080/v1/models` until it answers (~35-45 s).
5. Stop: `SIGTERM` to `serve/server.py`, which also ends the `engine/strata` child; `SIGKILL` after 30 s.

Update: `cd <clone> && ./update.sh` (git pull + engine rebuild when needed; models untouched), then re-check
the config JSON.

## Harness

Strata speaks the OpenAI API at `http://127.0.0.1:8080/v1` (any model name, any key) plus `/v1/messages`
and `/v1/responses`. Wire it as a second provider `local-flash-262k` (contextWindow 262144) on `:8080`, next
to `local-262k`; `python3 scripts/check-sync.py` accepts it as optional. Pick the provider that matches the
engine you started. The response carries `reasoning_content`; reasoning effort (off/low/medium/high) is honoured.

## Before you start: free RAM

The Coder needs 15.03 GiB of experts copied into RAM at 262K int8 with the 3 GiB VRAM reserve, plus the 6 GiB
headroom. Close Electron apps and idle agent CLIs first; a browser can stay open if `MemAvailable` stays
≥ 21 GiB. Check the start log for
`resident RAM mode: ... GiB of experts in RAM` and, during long prompts, for `stall report` lines.

16 GiB is not enough on its own (2026-10-15, [`results/20261015-strata-coder-idle-oom/`](../../results/20261015-strata-coder-idle-oom/README.md)):
the copy is sized as `MemAvailable` minus the headroom, so it grows with free RAM (9.05 GiB from 16.3 GiB
available), and the kernel OOM killer fired with no request sent. Check `/tmp` (`df -h /tmp`) and zram
(`zramctl`) too: `MemAvailable` does not count what they hold as free.
