# KVMem trial

Measured trial of the kvmem-llama.cpp fork on this card (2026-09-30): round 2 and final round, then round 1. Not adopted.

## KVMem trial round 2 and final round (2026-09-30, not adopted)

**Outcome: candidate = budget 28,672 + `--kvmem-block-tokens 32`; meets 3 of 4 go/no-go criteria,
agent run (T6) outstanding, not adopted.** Background, source pin and protocol are under the round 1
section below; evidence: [`results/20260930-kvmem-trial-round2/`](../../results/20260930-kvmem-trial-round2/).
Single samples.

| Criterion | Result |
|---|---|
| Decode at 160K+ at least ~1.3x the current profile | Met: 45.5 tok/s at 244K vs. 20.8 (2.2x); VRAM 15.1 GiB; round 1 at block 128 gave 48.6 |
| Retrieval 8/8 exact at 240K | Met: 8/8 at 240K; 4/4 at 190K and 4/4 at 220K; 128K 8/8 was measured at block 128 and not re-run at 32 |
| At least ~4 GiB host RAM free at 256K | Met: minimum 10.15 GiB at 244K (RSS 13.67 GiB) |
| Agent run without output-cap failures | Not run (T6) |

- Block size, not budget, fixes the round 1 miss (`PLANO-01-03-469`): block 32 at 28,672 is 8/8;
  budget 36,864 at block 128 is 3/4 with the same miss.
- Budget 49,152 is unusable: the 190K crash reproduced (2 of 2), a GPU `Memory access fault` at the
  end of prefill, and the faulted server ignores SIGTERM. Not traced; not reported upstream, nor is
  the ROCm build fix.
- Not done: candidate speed at 128K/190K, MTP n=3, traced crash run, quality on the remaining
  documents. The 16,384-token per-turn output cap remains a risk. Next step: T6 with the candidate.

## KVMem trial (round 1 run 2026-09-30, not adopted)

[kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp) (paper
[arXiv:2609.04852](https://arxiv.org/abs/2609.04852)) is a llama.cpp fork with its own
`llama-kvmem-server`. It keeps the full logical workspace (`-c 262144`) in host RAM and, for each
agent step, retrieves the relevant 128-token KV blocks into a bounded GPU working set
(`--kvmem-budget` + `--kvmem-gen-reserve`). Attention then runs over that set instead of the whole
history. It is the one candidate that could bound decode cost at depth, where the current profile
drops to ~19-23 tok/s (see `measurements/agent-traffic.md` and `measurements/depth.md`). Claims and
caveats are checked in [`SOURCES.md`](../SOURCES.md#context-length-and-compaction-claims-reviewed-2026-09-30).

**Round 1 outcome (2026-09-30): promising, not adopted; next round pending.** Evidence, exact
commands and raw data: [`results/20260930-kvmem-trial/`](../../results/20260930-kvmem-trial/). Built
from source at `abe72b38256d` with two local ROCm build fixes (`rocm-build-fix.patch`, not reported
upstream); `llama-kvmem-server` lacks `/tokenize` and `/completion`, so `bench/depth_bench.py` and
`bench/longctx_quality.py` could not be used and two chat-API scripts replaced them (steps 3-4
below were run that way). Single samples; the arms also differ in KV types (q8/q8 vs. q8/q5_1),
MTP n (2 vs. 3) and `-ub`, so ratios are not a pure KVMem effect.

| Criterion | Result |
|---|---|
| Decode at 160K+ at least ~1.3x the current profile | Met: at 244K, 48.6 tok/s (budget 28,672, 2.34x) and 40.2 (budget 49,152, 1.93x) vs. 20.8; VRAM ~15-16 GiB vs. 22.6 GiB |
| Retrieval 8/8 exact at 240K | Budget 28,672: 7/8 (deterministic miss, needle at token 40,302); 128K 8/8. Budget 49,152: 8/8 |
| At least ~4 GiB host RAM free at 256K | Met: minimum 6.51 GiB (RSS 9.4 GiB at budget 28,672, 13.1 GiB at 49,152) |
| Agent run without output-cap failures | Not run (T6) |

Other findings: budget 49,152 crashed once at the end of a 190K prefill (`Memory access fault by
GPU node-1`, not reproduced); thinking is off by default and needs `--enable-thinking`; MTP
acceptance is not reported; smoke test 71.5 tok/s at empty context. Blockers before adoption:
reproduce the crash, run the agent run, and accept the 16,384-token per-turn output cap.
Third-party context: [`SOURCES.md`](../SOURCES.md) (upstream issue #4 on mid-band retrieval collapse).

**Next round**: run as round 2 above (crash reproduced, budget 36,864, block 32); budget 40,960, 3 repeats and MTP n=3 were not run.

**Source pinned for the trial**: `kvmem/kvmem-llama.cpp` commit `abe72b38256d` (2026-09-30, source
version 0.17.0), llama.cpp submodule `7fe450e19305`. The prebuilt ROCm packages are older
(`rc3-rocm-beta2`, built on Ubuntu 24.04 against a ROCm 10 runtime), so build from source with the
same ROCm 10 venv toolchain as `hip-kvmix` (above):

```bash
git clone https://github.com/kvmem/kvmem-llama.cpp.git && cd kvmem-llama.cpp
git checkout abe72b38256d && git submodule update --init
source ~/src/rocm10-venv/bin/activate && export ROCM_PATH=$(rocm-sdk path --root)
python3 scripts/build-rocm.py --linux --gpu-targets gfx1100 --jobs 6   # output: build-hip-linux/
ctest --test-dir build-hip-linux --output-on-failure
```

Build only with the model server stopped: HIP kernel compilation needs several GiB of RAM per job,
and a loaded `llama-server` plus the desktop can leave as little as ~9 GiB available on this host.

**Known fit constraints (from the upstream README and ROCm guide, not yet verified here):**

- **KV types**: `f16`, `q8_0`, `q5_0`, `q4_0` only; there is **no `q5_1`**. The upstream IQ3 recipe
  uses `q8_0/q8_0`, which the bounded GPU working set makes affordable. Mixed pairs other than
  `q8_0/q4_0` have argument-parsing checks only, and "ROCm/Vulkan combinations have not been
  validated".
- **Per-turn output cap**: one generation can't exceed `--kvmem-gen-reserve` (16,384 tokens on the
  IQ3 recipe), thinking included. In the real agent traffic here, 4 of 1,303 turns went over 16,384
  output tokens. The upstream launcher also passes `--reasoning-budget 4096`; this repository sets
  a reasoning budget only with evidence (`AGENTS.md`), so the trial leaves it out and records any
  turn that hits the cap.
- **Retrieval anchor**: the IQ3 launchers use `--kvmem-query-policy user`, so retrieval is keyed
  on the last real user message. Tool results are not treated as user messages. The upstream
  query-replay report says the already-read suffix after that user message is kept rather than
  re-selected. In a harness session where one user message starts hours of tool calls, that
  suffix can exceed the GPU budget. How KVMem behaves there is the main open question for this
  workload, even though the paper's DeepSWE result (43.8% → 48.4%) is the same kind of
  single-task agent loop.
- **MTP**: the ROCm launcher uses MTP n=2 with `--kvmem-mtp-state replay`; the current profile uses
  n=3.
- **Host RAM**: the ROCm guide measures ~13-14 GiB of runtime host memory at 256K and recommends
  32 GiB of system RAM. This host has 32 GiB installed, 31.25 GiB usable (`MemTotal`; ~890 MiB is
  reserved by firmware and the kernel), plus zram swap. KVMem replaces `llama-server` (~3.5 GiB
  RSS with the current profile), so the net increase is ~10 GiB. With the desktop's current usage
  that should leave ~10 GiB available; the trial measures it.
- **GPU KV budget**: the ROCm launchers default to `KVMEM_GPU_KV_BUDGET=28672`, validated on a
  16 GiB card. This card has 24 GiB, so a larger budget is possible.

**Trial protocol** (GPU free, `llama-server` stopped):

1. Build and `ctest` as above; check `llama-kvmem-server --help` for every flag below before
   using it.
2. Smoke test on port 8080, text-only (no `--mmproj`), card sampling, with the upstream IQ3 KVMem
   flags: `-c 262144 --kvmem --kvmem-budget 28672 --kvmem-gen-reserve 16384
   --kvmem-block-tokens 128 --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --spec-type draft-mtp
   --spec-draft-n-max 2 --kvmem-mtp-state replay --reasoning-effort medium` (if supported).
3. Decode speed at depth: `BENCH_SERVER=.../llama-kvmem-server` with `bench/depth_bench.py
   --extra "<KVMem flags>"` at 128K/190K/240K fill; also MTP n=3 and a larger `--kvmem-budget`.
4. Long-context quality: `bench/longctx_quality.py --server .../llama-kvmem-server --variants
   <q8q8 MTP variant> --extra "<KVMem flags>"` at 128K and 240K. Exact-match retrieval is exactly
   what a bounded working set could lose.
5. Real agent run: 1-2 hours of the harness's local agent on a documented plan, then the same
   session analysis as `measurements/agent-traffic.md`: wall tok/s by depth, compactions, repeated
   tool calls, turns hitting the output cap.
6. Record peak process VRAM, host RSS, exact commands and commit hashes (upstream asks for the
   same).

**Go/no-go**: continue to a longer trial only if decode at 160K+ fill is at least ~1.3x the current
profile's (~19-23 tok/s), long-context retrieval matches the current 8/8 exact at 240K, at least
~4 GiB of host RAM stays free at 256K, and the agent run shows no output-cap failures and no loss
of task state. Otherwise record the numbers and drop it.
