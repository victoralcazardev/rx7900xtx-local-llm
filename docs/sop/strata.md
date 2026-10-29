# SOP: Strata with the Qwen3.8-Flash-Next Coder

Run [Strata](https://github.com/Niko1221/Strata) with the ISTA-DASLab Coder IQ1_M as an alternative to the
default llama.cpp profile, on the same port. Background, upstream claims and measurements:
[`../models/strata-qwen-flash-next.md`](../models/strata-qwen-flash-next.md). Settings this repo tracks:
`[strata.*]` in [`../../models.toml`](../../models.toml), applied with `scripts/strata.py`.

Only one engine serves `:8080` at a time: Strata and `llama-server` both need nearly all of the 24 GB VRAM.

## Layout

| What | Where (example) | Size |
|---|---|---|
| Strata clone (tracks upstream `main`; never edit tracked files, `update.sh` refuses to pull over them) | `~/IA/Motores/Strata` | ~0.7 GB + engine |
| Model shards (must be on NVMe; an HDD stalls, upstream #605) | `<models_root>/Qwen3.8-Flash-Next-GSQ-RCO-Coder-IQ1_M/` | 58.4 GB |
| Pack (`experts.bin` ~25 GB + `dense.bin`) and MTP layer | `~/IA/Motores/Strata-data/` (setup default: next to the clone) | ~32 GB |
| Run config written by setup | `<clone>/strata-coder-iq1_m.json`, start script `run-coder-iq1_m.sh`, log `strata-coder-iq1_m.log` | — |
| Backups made by `scripts/strata.py update` | `~/IA/Motores/strata-backups/<version>-<time>/` | small |

`Strata-data/mtp/tensors` (4.9 GB) is the source of the MTP layer; setup verifies it, so keep it.
`local.toml` needs `strata_dir = "<clone>"` (see `local.example.toml`).

## Install a model

```bash
git clone https://github.com/Niko1221/Strata ~/IA/Motores/Strata && cd ~/IA/Motores/Strata
./setup.sh --check --backend hip       # GPU/RAM/CPU check, lists what fits
./setup.sh --setup --family coder --model IQ1_M --gguf-dir <dir with both shards> \
  --backend hip --vision no --no-browser --yes --no-start --context 262144 --kv int8 --vram-reserve-mib 3072
python3 scripts/strata.py apply        # from this repo: the tracked settings into the run config
```

Setup compiles the engine for gfx1100 against the system ROCm 7 in `/opt/rocm` (10-20 min, once), builds the
pack and the MTP layer, and writes the run config.

Setup downloads model files at its own pinned revision and SHA-256. To run a newer file than the pin (e.g. the
2026-10-19 Coder shard 1; re-pin in upstream [PR #3445](https://github.com/Niko1221/Strata/pull/3445)), download
it yourself, compare `sha256sum` with the LFS hash on Hugging Face, and pass its folder with `--gguf-dir`: those
files only get a whole-file check, so an unmodified `setup.py` accepts them (verified 2026-10-24). Never edit the
clone's tracked files; `update.sh` refuses to pull over them.

Setup keeps `user_args`, `env` and `sampling` when it rewrites the run config (verified 2026-10-24); it may
reorder `args`.

Why these values: `--kv` offers `int8|q4_0|k8v4`; int8 is the 8-bit one. Shrinking the KV does not free VRAM
in Strata, because the expert cache takes whatever is left; only `--vram-reserve-mib` keeps VRAM free. 3072
leaves ~1.4 GiB of the card free while loaded, enough for the desktop to open apps without the driver pushing
GPU memory into RAM (without it a Slack launch ended the KDE session). The cost is ~2.3 GiB more experts in RAM.

## Tracked settings

`models.toml` `[strata.<model>]` holds what this repo decided for each installed model; `scripts/strata.py
apply` writes it into `<clone>/<config>`: each key replaces the run config's, `env` is merged with setup's.
`user_args` is Strata's own list of hand-set engine options: every setup run and start re-applies it on top of
the `args` setup generates, so it survives updates. Change a setting in `models.toml`, never only in the JSON.

```bash
python3 scripts/strata.py status            # local vs. upstream version, server state, drift (exit 1 = drift)
python3 scripts/strata.py apply --dry-run   # what apply would change
```

## Start and stop

A small wrapper (machine-local, not in this repo) does start/stop: `qwen-flash` starts it, `qwen-flash stop`
stops it. Its logic, so it can be rebuilt:

1. Refuse to start when `/tmp` is a tmpfs holding more than 2 GiB, and list its biggest files (never delete
   them). tmpfs files live in RAM until deleted; 8 GiB of test renders there fed an idle OOM.
2. Stop a `llama-server` on `:8080` if one runs (`ia` uses the same port).
3. Refuse to start below 21 GiB of `MemAvailable` (15.03 GiB of experts in RAM at 262K with the reserve + 6 GiB
   headroom) and list the biggest processes; `--force` overrides both checks. Below it the engine cuts the copy
   and reads the rest from the SSD, and a long prompt once OOM-killed the desktop.
4. Start `run-coder-iq1_m.sh` detached and poll `http://127.0.0.1:8080/v1/models` until it answers (~35-45 s).
5. Stop: `SIGTERM` to `serve/server.py`, which also ends the `engine/strata` child; `SIGKILL` after 30 s.

## Update Strata

```bash
qwen-flash stop
python3 scripts/strata.py status            # how far behind; skip the update if 0 commits
python3 scripts/strata.py update            # backup, ./update.sh, re-apply models.toml, print config changes
qwen-flash && curl -s localhost:8080/v1/models
```

`update` refuses while Strata runs, backs up every `strata-*.json` and `run-*.sh`, runs `./update.sh` (git pull
+ engine rebuild when its source changed; model files untouched), prints what the update changed in each run
config, then re-applies `models.toml`. Arguments after `--` go to `update.sh`.

After an update, before trusting it:

1. Read the release notes since the old version (`<clone>/docs/release-notes-<version>.md`, one per release):
   new flags, changed defaults, pins of the model files you use.
2. Start it; the log must show `resident RAM mode: ... GiB of experts in RAM`, no `stall report`.
3. A short request answers with `finish_reason: stop`; for a speed check run the result folder's
   `strata_bench.py` at ~120K (compare with the last result in the owner doc, same desktop state).
4. Record the version in the owner doc; if a number moved, a result folder (`docs/STYLE.md` §8).

Rollback: `git -C <clone> checkout <old tag>`, `./setup.sh --update` (rebuilds the engine), copy the backed-up
JSON back.

## Add another Strata model

1. Read the model's card (sampling, context, thinking) and Strata's `docs/MODELS.md` (RAM + VRAM tier, fit).
2. Install it with setup as above (`--family`/`--model` from `./setup.sh --help`; `--gguf-dir` if you have the files).
3. Add a `[strata.<model>]` table to `models.toml` with `config = "strata-<model>.json"`, the card's sampling and
   the engine options this repo decides (context, KV, VRAM reserve) as `user_args`, so a change of setup's
   defaults cannot move them; run `scripts/strata.py apply`.
4. Measure (speed at depth, retrieval with `bench/strata_longctx_quality.py`, the coding suite) before wiring a
   harness to it.

## Harness

Strata speaks the OpenAI API at `http://127.0.0.1:8080/v1` (any model name, any key) plus `/v1/messages`
and `/v1/responses`. Wire it as a second provider `local-flash-262k` (contextWindow 262144) on `:8080`, next
to `local-262k`; `python3 scripts/check-sync.py` accepts it as optional. Pick the provider that matches the
engine you started. The response carries `reasoning_content`; reasoning effort (none/low/medium/high, default
high) is honoured.

## Before you start: free RAM

The Coder needs 15.03 GiB of experts copied into RAM at 262K int8 with the 3 GiB VRAM reserve, plus the 6 GiB
headroom. Close Electron apps and idle agent CLIs first; a browser can stay open if `MemAvailable` stays
≥ 21 GiB. Check the start log for `resident RAM mode: ... GiB of experts in RAM` and, during long prompts, for
`stall report` lines.

16 GiB is not enough on its own (2026-10-15, [`results/20261015-strata-coder-idle-oom/`](../../results/20261015-strata-coder-idle-oom/README.md)):
the copy is sized as `MemAvailable` minus the headroom, so it grows with free RAM (9.05 GiB from 16.3 GiB
available), and the kernel OOM killer fired with no request sent. Check `/tmp` (`df -h /tmp`) and zram
(`zramctl`) too: `MemAvailable` does not count what they hold as free.
