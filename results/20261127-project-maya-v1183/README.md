# Project Maya v1.1.83 and alesha-pro maya-inkling-mini on the RX 7900 XTX (2026-11-27)

**What**: build the two Maya-family Inkling engines the user asked for on gfx1100 and run them on the files this repo
already has, with the harness of [`../20261127-tintero-dflash2/`](../20261127-tintero-dflash2/README.md).

**Status: not benchmarked.** Project Maya builds but reads only its own looped GGUF layout, whose 17.6 GB file did not
fit the free disk; alesha-pro's HIP path does not compile for gfx1100 at `27daec5`. Production is unchanged.

## mw00/project-maya v1.1.83 (`6382132`)

- Build (3 min, ROCm 10 TheRock venv from `docs/ENGINES.md`, ggml from llama.cpp `3cf03257`):
  `cmake -S project-maya-v1.1.83 -B build-hip -G Ninja -DCMAKE_BUILD_TYPE=Release -DMAYA_ENABLE_HIP=ON
  -DMAYA_PREFILL_MMQ=ON -DMAYA_BUILD_TESTS=OFF -DCMAKE_HIP_ARCHITECTURES=gfx1100 -DGPU_TARGETS=gfx1100
  -DMAYA_GGML_DIR=<llama.cpp>` then `cmake --build build-hip --target maya-ik2`. Warnings only.
- Load ([`raw/run.sh`](raw/run.sh), configs [`raw/pmaya-paged.json`](raw/pmaya-paged.json) and
  [`raw/pmaya-sparse.json`](raw/pmaya-sparse.json), model Abiray IQ4_NL q8dense) dies at once with
  `maya-ik2: no key inkling2.block_count` ([`raw/conditions.txt`](raw/conditions.txt) has both failed starts).
- Cause: the loader hardcodes the key prefix `inkling2.` (`src/ik2/ik2_main.cu:6691`) and never reads
  `general.architecture`; every Inkling-2-Mini file here (Abiray, the Nib-Pack, ggml-org) is `inkling2_loop`. Tintero
  reads both prefixes. Re-tagging the header would load a non-looped 24-layer model, not a fix.
- The file its setup installs (`tools/ik2/download.json`): `peasantsmith/Inkling-2-Mini-Maya-GGUF`
  `Maya-L/Inkling-2-Mini-Maya-L-NVFP4.gguf`, 17,629,759,680 B, sha256 `1945d7b2…`, rev `f5bef914`; NVFP4 experts in
  layers 0-19, Q8_0 elsewhere; plus a DSpark drafter and a 9,760 B runtime refusal direction
  (`Inkling-2-Mini-refusal-direction.gguf`), i.e. an uncensored option without a re-quant.
- Not run: `/home` had ~15 GB free; deleting the 11.4 GB ISTA IQ3_S downloaded for the Strata round did not raise the free
  space (unverified cause, likely filesystem snapshots), so the Maya-L download was stopped and its partial file removed.

## alesha-pro/maya-inkling-mini `27daec5`

- The README documents a HIP build (`-DSTRATA_ENABLE_HIP=ON -DSTRATA_HIP_IK2_SPIKE=ON -DSTRATA_PREFILL_MMQ=ON`) tested on
  gfx1201.
- On gfx1100 CMake first fails on a source it lists but does not ship, `tests/ik2_expert_bench.cu` (a local one-line stub
  was added to the clone to get past it), then `src/ik2/ik2_kernels.cu:907-925` does not compile: CUDA inline PTX
  (`invalid output constraint '+f' in asm`, `invalid input constraint 'l' in asm`) and `__cvta_generic_to_shared`.
- Its loader also hardcodes `inkling2.` (`src/ik2/ik2_main.cu:4566`), so it would need the Maya-L layout as well.
- Tintero is the working HIP fork of this tree.

## Next

Benchmark Project Maya once ~18 GB are free: Maya-L, paged dense and sparse decode, the same depths and sampling, plus
the refusal direction against the Unbound graft.
