# bench/

Benchmark scripts used to produce the numbers in `docs/measurements/`. They talk directly to
a running (or self-started) `llama-server`, not through `scripts/launch.py` — a benchmark run
wants full control over the exact command and its own instrumentation (GPU telemetry,
thermal abort, VRAM/GTT tracking via sysfs and `/proc/<pid>/fdinfo`).

All scripts here should be run under `systemd-inhibit` (suspending mid-measurement, or
mid-inference in general, with the GPU full has been observed to hang the machine), but the
guard they enforce differs per script:

- `depth_bench.py`, `longctx_quality.py` and `concurrency_bench.py` refuse to run (`--run`)
  without both the `IA_BENCH_INHIBITED=1` environment variable and `--inhibitor-ok`; their
  `--smoke` mode touches no server/GPU and needs neither.
- `spec_bench.py` and `spec_depth_bench.py` only check `IA_BENCH_INHIBITED=1`.
- `ladder_bench.py`, `oom_probe.py` and `summarize.py` have no guard at all — wrap them in
  `systemd-inhibit` yourself.

## Configuration

None of these scripts read `models.toml`/`local.toml` (`depth_bench.py`,
`longctx_quality.py`, `spec_bench.py`, `spec_depth_bench.py`, `oom_probe.py`) — they talk to a
fixed, already-decided configuration via environment variables, so a benchmark run stays
pinned to one exact model/engine/corpus regardless of what the daily-driver manifest points
at:

| Variable | Meaning |
|---|---|
| `BENCH_SERVER` | path to the `llama-server` binary under test |
| `BENCH_MODEL` | path to the GGUF under test |
| `BENCH_WIKI` | path to a `wikitext-2-raw` `wiki.train.raw` file (or similar long corpus) |
| `BENCH_OUT` | output directory (default: `bench/res`) |
| `BENCH_DFLASH_MODEL` | DFlash draft GGUF (only for `spec_depth_bench.py`'s `dfl3`/`dfl5` variants) |
| `BENCH_MODEL_NO_MTP` | base model without an MTP head (only for the same `dfl*` variants) |
| `BENCH_MAX_HOTSPOT_C` | overrides the shared `Monitor`'s hotspot abort threshold, default `104` (°C) — see "Thermal and power guards" below |
| `BENCH_EXPECT_POWER_CAP_W` | expected GPU power cap (W); a deep run (depth/`-c` ≥ 128K) warns on stderr if the active `power1_cap` is above it — see "Thermal and power guards" below |

## Thermal and power guards

All four scripts that touch a real server (`depth_bench.py`, `spec_depth_bench.py`,
`concurrency_bench.py`, `longctx_quality.py`) share `depth_bench.py`'s `Monitor`, which aborts a
run after 3 consecutive unsafe telemetry readings (edge ≥ 95°C, hotspot ≥ `BENCH_MAX_HOTSPOT_C`,
or GPU-evicted VRAM > 512 MiB). `BENCH_MAX_HOTSPOT_C` defaults to `104` (°C) — below this
project's ~105°C unattended-run policy, see
[`../docs/measurements/thermals-power.md`](../docs/measurements/thermals-power.md).

`depth_bench.py`, `concurrency_bench.py` and `longctx_quality.py` also call
`depth_bench.check_power_cap(depth_or_ctx)` before starting a run: it reads the active
`power1_cap` from sysfs for **every** AMD card found (globbing `card*/device/hwmon/hwmon*/power1_cap`
— never a fixed card/hwmon index, since it can change across reboots, and never just the first
match, since a multi-GPU host can expose `power1_cap` on more than one device), records all of
them in that run's metadata JSON, and, for a deep run (depth or `-c` ≥ 128K), prints a warning to
stderr for each card whose active cap is above `BENCH_EXPECT_POWER_CAP_W` (unset by default — no
warning is printed unless you set it; an invalid value is ignored with a warning instead of
crashing the run). It never writes `power1_cap`. `power1_cap` is not persisted by the driver and
resets to the factory default on reboot; see
[`../docs/measurements/thermals-power.md`](../docs/measurements/thermals-power.md) for how to set
and verify it.

`ladder_bench.py` is the exception: it reuses `scripts/manifest.py` and needs
`bench/local.bench.toml` (git-ignored — copy the shape from the root `local.example.toml`:
`models_root` + `[engines]`).

## Scripts

| Script | Old name (still in historical `command.json` files) | Measures |
|---|---|---|
| `depth_bench.py` | `validacion262.py` | Cold matrix: tok/s and acceptance at fixed input depths (128K/200K/240K), KV q8_0/q8_0 vs. q8_0/q5_1+MTP2, plus a warm second turn reusing the KV cache. |
| `longctx_quality.py` | `calidad262.py` | Long-context retrieval quality (RULER-style needle test) across the same depths and KV/MTP variants. Run 32K-240K, 60/60 exact match cumulative — see [`../results/20260925-longctx-quality-200k/`](../results/20260925-longctx-quality-200k/), [`../results/20260926-longctx-quality-224k/`](../results/20260926-longctx-quality-224k/), [`../results/20260926-longctx-quality-262k/`](../results/20260926-longctx-quality-262k/), and `docs/measurements/depth.md`. |
| `spec_bench.py` | `mtp262.py` | Paired comparison of speculative-decoding variants (no draft, MTP n=2/n=3, n-gram map/mod) across six task types. |
| `spec_depth_bench.py` | `mtpprof262.py` | Speculative-decoding draft-n sweep (including DFlash) at a fixed deep context (default 240K), to see which draft length wins once the KV read dominates. |
| `summarize.py` | `resumen262.py` | Turns a `depth_bench.py` output folder into a Markdown table (throughput, warm-turn reuse, VRAM/GTT/thermal peaks per phase). |
| `ladder_bench.py` | `escalera.py` | One-shot pass/fail matrix used to pick the model/profile shortlist: loads a case, measures load time, VRAM and tok/s, and records any OOM. |
| `oom_probe.py` | `estres.py` | Minimal OOM probe: fills the context with N characters of real text and asks for a short summary. |
| `concurrency_bench.py` | (new) | Multi-agent concurrency: one server with `-np N` parallel slots, N simultaneous streaming requests, per-slot tok/s + draft acceptance + aggregate throughput + peak VRAM/GTT. |

## `--extra`: A/B-testing a new flag without editing a script

`depth_bench.py`, `spec_depth_bench.py` and `concurrency_bench.py` accept `--extra "<flags>"`:
shlex-split and appended to the `llama-server` argv for every case/variant, and recorded verbatim
in that run's `command.json` (and, for `depth_bench.py`, in `metadata.json`). A flag that
duplicates one the script already hardcodes is warned about on stderr, not rejected. Examples:

```bash
# spec_depth_bench.py: sweep --spec-draft-p-min at a fixed depth
env IA_BENCH_INHIBITED=1 python bench/spec_depth_bench.py --run --depth 190000 \
    --variants n2 --tag pmin03 --extra "--spec-draft-p-min 0.3"

# depth_bench.py: a smaller checkpoint stride for warm-turn reuse
env IA_BENCH_INHIBITED=1 python bench/depth_bench.py --run --inhibitor-ok \
    --target-only --extra "-cms 2048"
```

## `concurrency_bench.py`: multi-agent slots

One server launched with `-np N` (parallel slots), then N concurrent streaming chat requests
fired at it, one synthetic prompt per slot (reusing `depth_bench.py`'s corpus/prompt builder,
so each slot's prompt is built at an exact tokenized depth). Records per-slot tok/s
(`timings.predicted_per_second`), prompt tok/s, draft accepted/proposed, wall time, aggregate
throughput and peak VRAM/GTT under concurrent load — input for the multi-agent/oh-my-pi slot
count decision. `--kv-unified`/`--no-kv-unified`/`--kv-unified-per-slot N` and MTP
(`--mtp --spec-draft-n-max K`) are optional; `--extra` works the same as above.

```bash
# 2 slots, 32K depth each, MTP n=2 on
env IA_BENCH_INHIBITED=1 python bench/concurrency_bench.py --run --inhibitor-ok \
    --slots 2 --depth 32000 --mtp --spec-draft-n-max 2
```

## Not ported

| Old name | Successor / status |
|---|---|
| `spec.py` | Superseded by `spec_bench.py` / `spec_depth_bench.py` |
| `archivar-validacion.py` | Not moved (marked unsafe during triage) |
| `*.orig*` copies | Not ported (history lives in git, not in parallel files) |
| `estres.sh`, `kld-kv.sh`, `matriz.sh`, `memoria.sh`, `motores.sh`, `profundo.sh`, `convivencia.sh` | Not ported (one-off, machine-specific shell diagnostics); conclusions are written up in `docs/measurements/` |
| `download_models.py` | Not ported (no entries in the current RX 7900 XTX model batch, see the root `AGENTS.md`) |
