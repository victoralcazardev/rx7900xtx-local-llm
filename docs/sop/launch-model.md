# SOP: launch a model that's already wired up

For models already in `models.toml` (see `docs/models/models.md`). If the model doesn't exist in
the manifest yet, use `docs/sop/new-model.md` first.

## Recommended profiles (`qwen38-iq3s-mtp`, measured in `docs/measurements/`)

| Profile | For | Generation | VRAM peak |
|---|---|---|---:|
| `128k-q8q8-mtp` | **Daily use**, with vision | ~58-69 tok/s (empty ctx), ~31 at 104K | 19.6 GiB |
| `224k-q8q8-mtp` | **Default** (`scripts/launch.py` with no alias) — long context, no vision | ~22.3-25.1 at 221K fill | 22.7 GiB (~1.8 GiB margin) |
| `240k-q8q8-mtp` | Measured maximum, no vision | ~22.5-24.4 at 237K fill | 23.4 GiB (~0.3 GiB margin, tight) |
| `262k-q8q8` | Max context, official binary, no vision | ~39 (empty), ~19 at 182K | 21.4 GiB |
| `200k-q8q8-mtp` | Narrower long-context candidate, no vision | ~22-30 at 190K | 21.7 GiB |
| `262k-q8q51-mtp` | Max context + MTP (`hip-kvmix` engine), no vision | ~18.4 at 240K | 23.0 GiB (tight margin) |

`launch.py` **blocks system suspend** while the server runs (`systemd-inhibit`): suspending with a
full VRAM has been observed to hang the machine on resume (see `docs/measurements/coexistence.md`).
It also warns if free VRAM doesn't cover the profile's `vram_gib` + 0.5 GiB margin.

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
   python scripts/check-sync.py
   ```
   If the manifest reports a PROBLEM (not a WARNING), fix it before continuing.

2. **Pick alias and profile, or use the default.** With no alias, `scripts/launch.py` loads
   `models.toml`'s `[defaults] default_alias`/`default_profile` (currently `qwen38-iq3s-mtp` /
   `224k-q8q8-mtp` — see `docs/STATUS.md`):
   ```
   python scripts/launch.py --dry-run
   ```
   To pick a different alias/profile explicitly, if the model has more than one profile,
   `--profile` is required:
   ```
   python scripts/launch.py qwen38-iq3s-mtp --profile 240k-q8q8-mtp --dry-run
   ```
   Check the printed command and the "Harness provider: local-XXXk" line.

3. **Launch for real** (foreground, stays attached to the console):
   ```
   python scripts/launch.py
   ```
   or in the background with a log:
   ```
   python scripts/launch.py --background
   ```
   The log goes to `_tmp/logs/<alias>-<profile>-<timestamp>.log`. Pass an explicit
   `<alias> --profile <profile>` (see the table above) to load something other than the default.

4. **In your coding-agent harness (if any), select the provider printed in step 2** (`local-128k`
   or `local-224k`). A harness doesn't know the model alias, only the `:8080` endpoint — see
   `AGENTS.md`.

## How to verify

- `curl http://127.0.0.1:8080/health` returns `{"status":"ok"}`.
- A real request from your client gets an answer (not `connection refused`, not
  `400 exceed_context`).
- `python scripts/smoke.py <alias> --profile <profile>` for an automated check with tok/s.

## Known errors

- **`llama-server is already running`**: stop the previous process first (`pkill -x llama-server`
  or Task Manager on Windows). There's only VRAM for one.
- **`400 exceed_context`**: your harness's provider entry doesn't match the profile's real `-c`.
  Run `check-sync.py`; if the "harness" block fails, the wiring is out of sync.
- **`connection refused` when the client tries to use the model**: no server listening on `:8080`
  yet, or it crashed. Check the `--background` log or the foreground console.
- **rejected K/V combination** (`ManifestError`): in HIP only `q4_0/q4_0`, `q8_0/q8_0`, `f16/f16`,
  `bf16/bf16` have a compiled FA kernel (see `docs/ENGINES.md`). For `q8_0/q5_1` or `q8_0/q4_1` use
  the `hip-kvmix` engine (own build, see `docs/ENGINES.md`).
- **`WARNING: less than 0.5 GiB of margin`**: something else is using VRAM (another llama-server, a
  game, a browser with many tabs/video). See `docs/measurements/coexistence.md`.
- **Never suspend the machine with a model loaded** if you start the server by hand (without
  `launch.py`): use `systemd-inhibit --what=sleep:idle --mode=block llama-server ...`.
