# SOP: Strata with Qwen3.8-Flash-Next

Run [Strata](https://github.com/Niko1221/Strata) with a Qwen3.8-Flash-Next GGUF as an alternative to the default
llama.cpp profile, on the same port. **State (2026-11-05): the clone stays at v0.2.11 with engine 0.1.57 built and no
model is installed.** The last set, Unsloth UD-IQ2_XS, decoded below the 15 tok/s floor and was deleted with every
other Flash-Next set ([`../../results/20261105-strata-unsloth-ud-iq2xs/`](../../results/20261105-strata-unsloth-ud-iq2xs/README.md));
the steps below are what the next install repeats. Background, upstream claims and measurements:
[`../models/strata-qwen-flash-next.md`](../models/strata-qwen-flash-next.md). Settings this repo tracks:
`[strata.*]` in [`../../models.toml`](../../models.toml) (none today), applied with `scripts/strata.py`.

Only one engine serves `:8080` at a time: Strata and `llama-server` both need nearly all of the 24 GB VRAM.

## Layout

| What | Where (example) | Size |
|---|---|---|
| Strata clone (tracks upstream `main`; never edit tracked files, `update.sh` refuses to pull over them) | `<strata_dir>` (`local.toml`) | ~0.7 GB + engine |
| Model shards (must be on NVMe; an HDD stalls, upstream #605) | `<models_root>/Qwen3.8-Flash-Next-<size>/` | 68-76 GB per Unsloth set (one shard is the shared 28.8 GB n-gram table) |
| Pack: the converted non-expert weights (1.4 GB); ISTA sets add `experts.bin` (~25 GB), Unsloth sets keep their experts in the shards | `<strata_data>/packs/<model>/` (setup default: next to the clone) | 1.4-33 GB |
| MTP layer and DFlash2 drafter | `<strata_data>/mtp/`, `<strata_data>/dflash2/` | ~5 GB / 800 MiB of VRAM |
| Run config written by setup | `<strata_dir>/strata-<model>.json`, start script `run-<model>.sh`, log `strata-<model>.log` | — |
| Backups made by `scripts/strata.py update` | `<strata_dir>/../strata-backups/<version>-<time>/` | small |

`<strata_data>/mtp/tensors` (4.9 GB) is the source of the MTP layer; setup verifies it, so keep it when the model
stays. Everything under `<strata_data>` was deleted on 2026-11-05, so the next install rebuilds it. A **start never
downloads the DFlash2 drafter** (`serve/server.py`): run `.venv/bin/python strata.py drafting fetch --mode dflash2`
from the clone first, or the server falls back to MTP (or to no drafter when neither file is there).
`local.toml` needs `strata_dir = "<strata_dir>"` (see `local.example.toml`).

## Install a model

```bash
git clone https://github.com/Niko1221/Strata ~/IA/Motores/Strata && cd ~/IA/Motores/Strata
./setup.sh --check --backend hip       # GPU/RAM/CPU check, lists what fits
./setup.sh --setup --family qwen --model UD-IQ2_XS --gguf-dir <dir with the set's shards> \
  --backend hip --vision no --no-browser --yes --no-start --context 262144 --kv int8 --vram-reserve-mib 3072
python3 scripts/strata.py apply        # from this repo: the tracked settings into the run config
```

Setup compiles the engine for gfx1100 against the system ROCm 7 in `/opt/rocm` (10-20 min, once), builds the
pack and the MTP layer, and writes the run config. `./setup.sh --check --backend hip` lists what fits and what
does not, but its RAM arithmetic is optimistic: it counts a resident mode the engine may then find unfittable
(2026-10-30) and it does not subtract `--vram-reserve-mib`.

**Some sets have no `experts.bin`.** For Unsloth Dynamic v3.1 sets setup says `--low-ram mmap does not apply to
<set>: it always reads part of its experts from the files` and writes no pack of experts: the engine reads them in
place from the GGUF shards (`experts via mmap (--mmap-experts; the GGUF shards in place, no experts.bin)`). Every
shard must then stay on the NVMe for the model to run at all, and the disk cost is the download alone
(2026-11-05, [`results/20261105-strata-unsloth-ud-iq2xs/`](../../results/20261105-strata-unsloth-ud-iq2xs/README.md)).

Setup downloads model files at its own pinned revision and SHA-256. To run a newer file than the pin (e.g. the
2026-10-19 Coder shard 1; re-pin in upstream [PR #3445](https://github.com/Niko1221/Strata/pull/3445)), download
it yourself, compare `sha256sum` with the LFS hash on Hugging Face, and pass its folder with `--gguf-dir`: those
files only get a whole-file check, so an unmodified `setup.py` accepts them (verified 2026-10-24). Never edit the
clone's tracked files; `update.sh` refuses to pull over them.

Setup keeps `user_args`, `env` and `sampling` when it rewrites the run config (verified 2026-10-24); it may
reorder `args`. It also copies the current `user_args` into `args`, so an option later removed from `user_args`
stays in `args` until deleted by hand (seen 2026-10-30 with `--resident-budget-gib`): after every `./setup.sh` run,
compare `args` with what you intend and check the live command line with `pgrep -af engine/strata`.

Setup builds the engine only when its source hash changes. Installing a library afterwards (e.g. `pacman -S
hipblaslt`) does not trigger a rebuild, and CMake keeps `hipblaslt_DIR-NOTFOUND` in `build-hip/CMakeCache.txt`:
setup still writes `STRATA_HIPBLASLT_TUNING` into `env`, but an engine without hipBLASLt ignores it. Check with
`ldd engine/strata | grep hipblaslt` (verified 2026-10-30).

**AMD stall with experts read from host memory (`GPU_PINNED_MIN_XFER_SIZE`).** ROCclr copies a pageable source of
1 MiB or more by locking its pages as a GPU userptr; expert blobs are 1.1-1.5 MB. When the kernel reclaims those
pages (page cache of `experts.bin`, or a pageable RAM copy under zram swap), the GPU queues are suspended
(`journalctl -k`: `svm_range_restore_work` -> `filemap_fault`, `page allocation stall`) and the engine's watchdog
kills a long prompt ("no progress for 60 s"). Upstream documents it (Strata `docs/AMD_HIP.md`, "Linux: verify
timeouts while the kernel reclaims host memory") and the engine sets the fix itself only with
`STRATA_ARENA_MMAP=1`. Set `GPU_PINNED_MIN_XFER_SIZE = "1048576"` in the model's `env`. On 2026-10-30, without it, a
121,709-token prompt stalled in all three memory modes (resident 18.53 GiB, resident 14 GiB, mapped); with it, mapped
mode passed 120K four times and 240K once with no stall (transient order-0 `page allocation failure` lines appeared
twice, without a stall). This host runs `vm.swappiness=150` with zram, which pushes anonymous memory out early.
Status: validated for IQ2_XS in mapped mode; the resident mode with the fix is untested
([`results/20261030-strata-iq2xs-baseline/`](../../results/20261030-strata-iq2xs-baseline/README.md)).

**Capacity first on 32 GB.** The experts the GPU does not hold must fit the host room beside the engine; when they
do not, every request streams the difference from the shards and decode drops to single-digit tok/s. Read it from the
start log: `prefill plan inputs: N GiB experts, M GiB in the GPU caches, K GiB RAM copy ..., file tier F GiB`, then
`prefill plan: ... about X GB read from the drive per 32768-token prompt`. An F above ~1 GiB is a warning, not a
detail: the ISTA IQ2_XS (33.02 GiB of experts) reached F 2.1 GiB and 59-65 tok/s on this host; Unsloth UD-IQ2_XS
(39.4 GiB) could not get below 11.5 GiB and decoded at 8.2-10.8 tok/s
([results](../../results/20261105-strata-unsloth-ud-iq2xs/README.md)).

Keep the hipBLASLt table off: on gfx1100 it makes prefill faster but decode at depth 16-25% slower
([IQ2_XS results](../../results/20261030-strata-iq2xs-baseline/README.md)). Once the engine links hipBLASLt, setup's
`STRATA_HIPBLASLT_TUNING` path loads the table whatever `STRATA_HIPBLASLT_TABLE` says, so a `[strata.<model>]` `env`
sets the path to `""` and the switch to `off`. The local `build-hip` now finds hipBLASLt, so the next rebuild links it.

Residual memory pressure (2026-10-30, `journalctl -k`): 17 order-0 `page allocation failure` lines (mode
`GFP_KERNEL|__GFP_HIGH|__GFP_NOMEMALLOC`, from plasmashell, kswapd0 and the engine's pool threads), 14 of them during
the stalled arms and 3 with the fix (no stall); zone Normal fell to 3-29 MiB free against a 60 MiB `min`, with
`vm.min_free_kbytes=67584` and `vm.watermark_scale_factor=10`. Candidate, not tested: make kswapd reclaim earlier with
`vm.watermark_scale_factor=125` and `vm.min_free_kbytes=262144` in `/etc/sysctl.d/` (needs sudo, reserves ~0.6 GiB
more), and/or cap `--conversation-cache-mib` (mapped mode sizes it at 8192 MiB of anonymous memory). That zram is the
allocating side is an inference from the flags.

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

A small wrapper (machine-local, not in this repo) does start/stop: `qwen-flash start` starts it, `qwen-flash
stop` stops it, and `qwen-flash start --force` skips its pre-start checks (the options come with the subcommand, not
before it). Its logic, so it can be rebuilt:

1. Refuse to start when `/tmp` is a tmpfs holding more than 2 GiB, and list its biggest files (never delete
   them). tmpfs files live in RAM until deleted; 8 GiB of test renders there fed an idle OOM.
2. Stop a `llama-server` on `:8080` if one runs (`ia` uses the same port).
3. Refuse to start below a `MemAvailable` floor sized from the model's RAM copy plus the 6 GiB headroom (21 GiB
   for the Coder's 15.03 GiB at 262K) and list the biggest processes; `--force` overrides both checks. Below it the
   engine cuts the copy and reads the rest from the SSD, and a long prompt once OOM-killed the desktop.
4. Start `run-${QWEN_FLASH_MODEL}.sh` detached (log `strata-<model>.log`; the server's own output goes to
   `strata-<model>.log.server.out`, which is where prompt progress, silence kills and engine exit codes appear) and
   poll `http://127.0.0.1:8080/v1/models` until it answers (~35-60 s). Its built-in default model name still says
   `iq2_xs`, which was deleted on 2026-11-05: set `QWEN_FLASH_MODEL=<model>` or the script is not found.
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
2. Install it with setup as above (`--family`/`--model` from `./setup.sh --help`; `--gguf-dir` if you have the
   files), then fetch the drafter: `.venv/bin/python strata.py drafting fetch --mode dflash2` — a start never
   downloads it, and setup's written `--spec 4 --mtp` is not what the engine gets either (the server picks the
   drafter at start, `serve/server.py` `drafting.apply`; DFlash2 is Auto on gfx1100 since v0.2.10).
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

Each set needs its RAM copy (`--resident-budget-gib`, or the automatic value) plus the 6 GiB headroom: the Coder
took 15.03 GiB at 262K int8 with the 3 GiB VRAM reserve, so 21 GiB of `MemAvailable`. Close Electron apps and idle
agent CLIs first; a browser can stay open if `MemAvailable` stays above that. Check the start log for
`resident RAM mode: ... GiB of experts in RAM` and, during long prompts, for `stall report` lines — and read the
`prefill plan inputs` line (file tier) before judging any speed.

16 GiB is not enough on its own (2026-10-15, [`results/20261015-strata-coder-idle-oom/`](../../results/20261015-strata-coder-idle-oom/README.md)):
the copy is sized as `MemAvailable` minus the headroom, so it grows with free RAM (9.05 GiB from 16.3 GiB
available), and the kernel OOM killer fired with no request sent. Check `/tmp` (`df -h /tmp`) and zram
(`zramctl`) too: `MemAvailable` does not count what they hold as free.
