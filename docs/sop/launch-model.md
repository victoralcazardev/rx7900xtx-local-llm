# SOP: launch a model that's already wired up

For models already in `models.toml` (see `docs/STATUS.md`). If the model doesn't exist in
the manifest yet, use `docs/sop/new-model.md` first.

## Qwen3.8-27B setup (`huihui-iq3s-mtp`; the stock `qwen38-iq3s-mtp` reference takes the same steps)

`models.toml` carries several setups side by side and recommends none of them
([`docs/STATUS.md`](../STATUS.md)). This one, from `docs/DECISIONS.md` 2026-09-26, with its 240K numbers
measured on the stock GSQ-RCO quant:

| Profile | For | Generation | VRAM peak |
|---|---|---|---:|
| `262k-q8q51-mtp` | Long-context Qwen3.8-27B — max context + MTP n=3, `-ub 256`, no vision | 18.6-26.9 at 240K fill | 22.2 GiB |

`launch.py` **blocks system suspend** while the server runs (`systemd-inhibit`): suspending with a
full VRAM has been observed to hang the machine on resume (see `docs/measurements/coexistence.md`).
It also warns if free VRAM doesn't cover the profile's `vram_gib` + 0.5 GiB margin.

### Inkling-2-Mini uncensored (`inkling2-mini-unc`)

Two profiles on the same Abiray IQ4_NL file; `--profile` is required. Text only, no vision.

| Profile | Engine | Decode at 512 / 128K / 262K (tok/s, 272 W) | Use |
|---|---|---|---|
| `inkling2-mini-unc-q8d` / `315k-maya` | `maya` (GodGMN `maya-inkling-mini` HIP port, not llama.cpp) | 106.1 / 68.9 at 512 / 128K | Faster on this card; 315K context |
| `262k-q8q8` | `hip-inkling` (GodGMN `inkling-rdna3` llama.cpp fork) | 57.6 / 44.5 / 37.8 | llama.cpp features (`/metrics`, n-gram speculation, checkpoints) |

```
python3 scripts/launch.py inkling2-mini-unc-q8d --profile 315k-maya --background --wait   # returns once /health answers
python3 scripts/smoke.py inkling2-mini-unc-q8d --profile 315k-maya     # automated check, starts and stops its own server
python3 scripts/launch.py --stop                                     # stop any model server, wait until the VRAM is free
```

Both serve the `local-262k` harness provider on `:8080`. Evidence:
[maya vs. fork](../../results/20261122-inkling-maya-vs-fork/README.md); engine setup and updates:
[ENGINES.md](../ENGINES.md#maya-inkling-mini-hip-maya-ik2-experimental-inkling-2-mini-only).

### Optional shortcut

`python3 scripts/launch.py <alias> --profile <profile>` is the full command; a short wrapper saves
typing it out. On Linux/macOS, add a POSIX shell function (`~/.bashrc`, `~/.zshrc`) that forwards
every argument:

```sh
ia() { python3 <repo>/scripts/launch.py "$@"; }
```

or, in fish, a matching function in `~/.config/fish/functions/ia.fish`:

```fish
function ia
    python3 <repo>/scripts/launch.py $argv
end
```

Replace `<repo>` with the absolute path to this repository. This is not part of the repository
itself — it's a convenience each user sets up locally, so `ia <alias> --profile <profile>` becomes
shorthand for the `launch.py` invocation below.

## Steps

1. **Check that no other server is running** (one port `:8080`, one model at a time):
   ```
   python3 scripts/check-sync.py
   ```
   If the manifest reports a PROBLEM (not a WARNING), fix it before continuing.

2. **Pick alias and profile.** With no alias, `scripts/launch.py` uses `models.toml`'s
   `[defaults] default_alias`/`default_profile` fallback (`inkling2-mini-unc-q8d` / `315k-maya`, the
   setup last in use — not a recommendation; see `docs/STATUS.md`):
   ```
   python3 scripts/launch.py --dry-run
   ```
   To pick an alias/profile explicitly, `--profile` is required if the model has more than one
   profile:
   ```
   python3 scripts/launch.py huihui-iq3s-mtp --profile 262k-q8q51-mtp --dry-run
   ```
   Check the printed command and the "Harness provider: local-262k" line.

3. **Launch for real** (foreground, stays attached to the console):
   ```
   python3 scripts/launch.py
   ```
   or detached in the background:
   ```
   python3 scripts/launch.py --background          # add --wait to return only once it answers /health
   ```
   From an agent's shell tool, start it with `setsid -f python3 scripts/launch.py --background
   >/dev/null 2>&1 </dev/null`: otherwise the tool's timeout kills the launcher's process group and
   the server with it (observed 2026-10-23: "cleaning up before exit" ~2 min after launch). Stop it
   with `python3 scripts/launch.py --stop` when done (SIGINT to llama-server or maya's server, waits until
   the GPU process exits, SIGKILL after 90 s): it holds ~22 GiB of VRAM.
   Both modes write the server log to `_tmp/logs/<alias>-<profile>-<timestamp>.log`; foreground
   also echoes it to the console. Keep these logs: cache misses and timings of a real session can
   only be analyzed from them. On Linux the launcher also writes `<log>.gpu.csv` from
   `scripts/gpu_watch.py`: GPU temperatures, power, VRAM and (trailing columns) sclk/mclk/vddgfx and the server's host `RssAnon` (`rss_anon_mib`) every 5 s, with rows flagged
   `HOT` or `VRAM` past the safety limits; it is read-only and stops with the server. Pass an explicit
   `<alias> --profile <profile>` (see the tables above) to load a different setup than the fallback.

4. **In your coding-agent harness (if any), select the provider printed in step 2**
   (`local-262k`, or `local-315k` for a 315K profile). A harness doesn't know the model alias, only the `:8080` endpoint — see
   `AGENTS.md`.

## How to verify

- `curl http://127.0.0.1:8080/health` returns `{"status":"ok"}`.
- A real request from your client gets an answer (not `connection refused`, not
  `400 exceed_context`).
- `python3 scripts/smoke.py <alias> --profile <profile>` for an automated check with tok/s. It starts its own
  server, so stop a running one first (otherwise it exits 2 with `ABORTED`).

## Known errors

- **`a model server (llama-server, maya-ik2 or nib) is already alive`**: stop the previous process first
  (`python3 scripts/launch.py --stop` on Linux, or Task Manager on Windows).
  There's only VRAM for one.
- **`400 exceed_context`**: your harness's provider entry doesn't match the profile's real `-c`.
  Run `check-sync.py`; if the "harness" block fails, the wiring is out of sync.
- **`connection refused` when the client tries to use the model**: no server listening on `:8080`
  yet, or it crashed. Check its log in `_tmp/logs/`.
- **A harness turn "hangs" and then ends with "Response was truncated"**: usually not a hung server. Check
  `curl :8080/health` (`busy:false` means it is idle) and the last `[serve]` line of the newest log: `gen=`
  equal to the harness's `max_tokens` (e.g. 32768) and no `tools` tag means the model spent the whole budget
  without a tool call. The text itself is only in the harness's session file (Gentle Shell / Pi:
  `~/.gentle-shell/agent/sessions/<cwd>/<session>.jsonl`, the assistant entry with `"stopReason":"length"`);
  count repeated paragraphs to tell a loop from long reasoning. Fix: retry the turn; if it repeats, check the
  model's sampling against its card (Inkling case: [`docs/models/inkling-2-mini.md`](../models/inkling-2-mini.md)).
- **rejected K/V combination** (`ManifestError`): in HIP only `q4_0/q4_0`, `q8_0/q8_0`, `f16/f16`,
  `bf16/bf16` have a compiled FA kernel (see `docs/ENGINES.md`). For `q8_0/q5_1` or `q8_0/q4_1` use
  the `hip-kvmix` engine (own build, see `docs/ENGINES.md`).
- **`WARNING: less than 0.5 GiB of margin`**: something else is using VRAM (another llama-server, a
  game, a browser with many tabs/video). See `docs/measurements/coexistence.md`.
- **Never suspend the machine with a model loaded** if you start the server by hand (without
  `launch.py`): use `systemd-inhibit --what=sleep:idle --mode=block llama-server ...`.
