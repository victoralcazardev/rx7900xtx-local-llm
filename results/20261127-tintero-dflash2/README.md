# Tintero `dc52e6f` with and without the DFlash2 drafter on the RX 7900 XTX (2026-11-27)

**What**: `GodGMN/tintero` `dc52e6f` — the gfx1100 HIP fork of `alesha-pro/maya-inkling-mini`, built with our ROCm 10
TheRock venv — on the file the `maya-ik2` profile runs, Abiray's Uncensored IQ4_NL q8dense, at 262,144 tokens. Four
tintero arms through one harness: paged dense KV, paged dense KV plus the DFlash2 drafter, token-major dense KV, and
token-major KV with `IK2_SPARSE_DECODE`. The same harness ran the production Nib build with `--sparse-pages 0`
(dense-vs-dense); Nib's sparse-pages number is its own `--sparse-pages 224` default measured in the same day's
[nib-v022](../20261127-nib-v022/README.md) run (arm A). Decode and prefill at 7.8K/33K/134K/258K, Nib's production
sampling.

**Status: not adopted.** Nib wins every like-for-like pair up to 134K and still leads at 258K: dense
143.1/106.4/86.9/66.5 against 91.0/87.4/63.4/46.3 tok/s, sparse 106.9 against 90.5. Nib also prefills 1.08-2.05x
faster. The DFlash2 drafter shows a gain only at 258K (+13%) and cannot be combined with sparse decode, which is
tintero's fastest arm at depth. Production stays `2e16cf0` + the thinking-cap patch.

**Caveats**: the sparse arm ran on a loaded host — it started at load 17.0 (the Strata 0.2.23 install landed at
19:28 inside its window) and its 134K repeats are 88.8 and 68.4 tok/s, a 23% spread. The paged base arm started at
load 9.4-10.0 and the other two tintero arms at 2.6-3.9. The Nib sparse column comes from the load-40 nib-v022 run, so
it may understate Nib; the Nib dense column here ran at load 5.2. Every arm waited for six consecutive 30 s idle checks
first (no other engine process, GPU use ≤5%).

| Arm | KV | Drafter | VRAM | Config |
|---|---|---|---:|---|
| tintero paged dense (`base`) | paged (`IK2_PAGED_KV=1`) | no | 92% | [`raw/tintero-base.json`](raw/tintero-base.json) |
| tintero + DFlash2 (`dflash2`) | paged | `--draft` the DFlash2 file | 96% | [`raw/tintero-dflash2.json`](raw/tintero-dflash2.json) |
| tintero token-major dense (`dense-tm`) | token-major | no | 91% | [`raw/tintero-dense-tm.json`](raw/tintero-dense-tm.json) |
| tintero sparse (`sparse`) | token-major + `IK2_SPARSE_DECODE=1` | no | 90% | [`raw/tintero-sparse.json`](raw/tintero-sparse.json) |
| Nib dense (`nib-dense`) | `--sparse-pages 0`, `--kv-type q8_0` | MTP (`mtp.safetensors`) | 95% | [`raw/run2.sh`](raw/run2.sh) |

## Speed by depth

Decode tok/s, median of 2 repeats, median prefill in parentheses; prompts are unique per request (a nonce line first),
uncached, 256-token cap. Prompt token counts differ slightly between engines (Nib's own tokenizer), and Nib's sparse
column counted 134,187 and 258,129 tokens.

| Prompt tokens (tintero / Nib) | paged dense | + DFlash2 | token-major dense | sparse | Nib dense (`sp=0`) | Nib sparse 224 |
|---:|---:|---:|---:|---:|---:|---:|
| 7,823 / 7,824 | 91.0 (2,800) | 59.9\* (2,815) | 94.0 (3,418) | 98.3 (3,284) | 143.1 (3,695) | 121.2 (3,582) |
| 33,142 | 87.4 (2,246) | 85.4 (2,813) | 79.2 (2,368) | 92.2 (2,874) | 106.4 (3,444) | 120.8 (3,433) |
| 134,456 / 134,445 | 63.4 (974) | 64.7 (1,869) | 55.3 (1,312) | 78.6 (1,669) | 86.9 (2,691) | 108.0 (3,030) |
| 258,569 / 258,447 | 46.3 (1,314) | 52.4 (1,305) | 41.1 (1,086) | 90.5 (1,171) | 66.5 (2,115) | 106.9 (2,961) |

\* one of the two 8K replies stopped at 29 tokens (23.6 tok/s); the other was 96.2, and a fresh start with three 8K
requests (`dflash2-diag`) gave 95.7/99.9/97.0. Four more replies stopped before the cap (paged 134K: 33 tokens,
token-major 8K: 25, Nib dense 8K and 258K: 194 and 95); the medians above include them. Per-repeat `tg_all`: raw
[`raw/speed.jsonl`](raw/speed.jsonl), 21 rows.

Read as ratios, Nib's dense arm is 1.6x/1.2x/1.4x/1.4x tintero's paged arm and 1.5x/1.3x/1.6x/1.6x its token-major
one; Nib's sparse arm is 1.2x/1.3x/1.4x/1.2x tintero's. Tintero's prefill is not monotonic in the paged arm (974 at 134K against
1,314 at 258K), so read that column as noisy; the token-major and sparse arms are monotonic. Nib's prefill lead runs
from 1.08x at 8K to 2.05x at 134K against tintero's dense arms.

**Sparse decode is what carries depth, on both engines.** Tintero sparse beats tintero paged dense at every depth and
is 1.96x it at 258K (90.5 against 46.3), and its 258K number sits above its own 134K one. Nib shows the same effect in
reverse: its sparse-pages arm (106.9 at 258K) is 61% above its dense arm measured here (66.5) — but those two Nib rows
come from different runs on differently loaded hosts, so read that pair as a direction, not a measurement.

## The DFlash2 drafter: in VRAM, no acceptance evidence

The drafter (`incoai/Inkling-2-Mini-DFlash2`, rev `4f9088ea`, `model.safetensors` 989,975,616 B = 944 MiB, sha256
`217980ab00d116693fa5946df7bbfd967caf5fac1f529afd541fbd470ddb54ee`) loads through `--draft`: VRAM goes from 92% to
96% of 24 GB (≈0.96 GB), and the server answers normally. What is missing is any line proving that drafting ran:

- The engine prints `drafter: <path>, <GiB> of VRAM, <s> s` once at load and a `speculative: … accepted …` summary
  per run (`src/ik2/ik2_main.cu:5534`, `:6908`), both on **stdout**. The server captures the engine's stdout on a pipe
  and sends only its **stderr** to the log file (`serve/server.py:1004-1005`), so those two lines never reach
  `_tmp/tintero/engine-dflash2.log`. [`raw/dflash2-engine-lines.txt`](raw/dflash2-engine-lines.txt) is that grep and
  is 0 bytes by construction, not because the drafter was idle.
- The per-request `timings` the server returns carry `mtp_tok_per_round` and `mtp_avg_accepted`; both are `null` in
  every tintero row of `raw/speed.jsonl` (Nib's MTP rows fill them). So no acceptance rate was reported either.

What is left is the speed: nothing at 8K (97.0 on the diagnostic start against the arm's 91.0), -2% at 33K, +2% at
134K, and +13% at 258K (52.4 against 46.3). A 13% step between two starts taken at different loads is not evidence of
acceptance; the sparse arm alone varied 23% between two repeats of one depth. Either way it does not change the verdict:
even taking 258K at face value, tintero with the drafter is 52.4 tok/s against Nib's 106.9.

**It also cannot stack with the fast arm.** `IK2_SPARSE_DECODE` refuses speculation outright: the third arm of
`raw/run.sh` never came up (`up=no`, VRAM 4%) and the engine printed
`tintero: IK2_SPARSE_DECODE requires single-stream decode without speculation`. Sparse decode has a second gate: the
first attempt at it also refused, with
`IK2_SPARSE_DECODE requires token-major IK2_KV=fp8 and IK2_ATTN_MMA=3 with 128-wide heads`, and only ran once
`IK2_PAGED_KV` was dropped from the config: [`raw/tintero-sparse.json`](raw/tintero-sparse.json) is the token-major config
plus `IK2_SPARSE_DECODE=1`. Times, loads and VRAM readings: [`raw/conditions.txt`](raw/conditions.txt).

## Setup

| | |
|---|---|
| Dates / GPU | 2026-11-27 18:40-19:39 local (WET), RX 7900 XTX 24 GB (gfx1100), CachyOS, kernel 7.3.6-1-cachyos |
| Runtime | our ROCm 10 TheRock venv (the `maya-ik2` recipe in [`docs/ENGINES.md`](../../docs/ENGINES.md)); `tintero` links that venv's `libamdhip64.so.7` through its RUNPATH; `ROCBLAS_TENSILE_LIBPATH=/opt/rocm/lib/rocblas/library` |
| Build | `~/IA/Motores/src/tintero-dc52e6f`, `GodGMN/tintero` `dc52e6f23c040d9…` (2026-11-27 16:56, merge of PR #10), `cmake -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_HIP=ON -DSTRATA_BUILD_TESTS=OFF`, target `tintero`; `build-ik2/tintero` 18:36, sha256 `99d464dd18f542ab…` |
| Workspace reuse | `.venv` and `ik2/tokenizer` symlinked from the `maya-inkling-mini-hip-f472e94` worktree |
| Server | `serve/server.py --engine maya --config raw/tintero-<arm>.json --tokenizer ik2/tokenizer --host 127.0.0.1 --port 4444`, one start per arm |
| Model | `Inkling-2-Mini-Uncensored-IQ4_NL-q8dense.gguf` 15,357,929,856 B, `--max-context 262144 --chunk 2048`; 27 `IK2_*` variables (28 keys with `ROCBLAS_TENSILE_LIBPATH`) as listed in the arm's config |
| Drafter | `~/IA/Modelos/Inkling-2-Mini-DFlash2/model.safetensors` (rev `4f9088ea`, sha256 above) |
| Nib arms | `~/IA/Motores/src/nib-thinkcap`, `2e16cf0` + `engine-patches/nib-reasoning-budget-2e16cf0.patch`, `build/nib` 2026-11-25 20:40, sha256 `79aec4a96629100a…`; `serve -m <Nib-Pack gguf> --mtp mtp.safetensors --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 0` |
| Harness | `raw/depth_http.py … --depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9 --sampling '{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}'`; every request also sends `reasoning_effort: "none"` |
| Sequence | [`raw/run.sh`](raw/run.sh) (three arms), [`raw/diag.sh`](raw/diag.sh) (drafter diagnostic + sparse retry), [`raw/run2.sh`](raw/run2.sh) (dense-vs-sparse on both engines) |

## Not measured

- Quality: no GSM8K, retrieval or tool-call run for tintero, and no reply text was stored (the server's request counters were
  not kept), so nothing here compares output.
- A Nib dense-vs-sparse A/B on an idle host: the two Nib rows come from different runs (see the caveat).
- Tintero drafting with the model's own MTP block (`mtp.safetensors`), which is what Nib runs; only the external
  DFlash2 drafter was tried.
- `IK2_DRAFT_WIDTH` / `IK2_MARGIN` tuning, and any sampling other than Nib's production set.

## Raw files

[`raw/run.sh`](raw/run.sh) · [`raw/diag.sh`](raw/diag.sh) · [`raw/run2.sh`](raw/run2.sh) · [`raw/depth_http.py`](raw/depth_http.py) ·
[`raw/speed.jsonl`](raw/speed.jsonl) (21 rows) · [`raw/conditions.txt`](raw/conditions.txt) · [`raw/dflash2-engine-lines.txt`](raw/dflash2-engine-lines.txt) (0 B) ·
the five arm configs. Server and engine logs stay in the git-ignored
`_tmp/tintero/`: the load lines quoted above are in `engine-dflash2.log`, the drafter refusal in
`engine-dflash2-sparse.log`; the paged-KV refusal survives only as the quoted `tail -1` line in `raw/conditions.txt`,
because `engine-sparse.log` was overwritten by the successful sparse run afterwards.
