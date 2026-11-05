# Strata v0.2.11 + Unsloth UD-IQ2_XS: in-place GGUF reads, DFlash2, and a squeeze arm (2026-11-05)

**What.** Unsloth's Qwen3.8-Flash-Next UD-IQ2_XS (Dynamic v3.1) installed on Strata v0.2.11 and measured on this
machine: smoke, then six short requests on the setup config, then a second "squeeze" arm (131K context, 2 GiB VRAM
reserve, 14 GiB RAM copy) with three warm requests. Goal: a Strata set that decodes at the user's 15 tok/s floor
(2026-11-05). The ~120K `strata_bench.py` sweep, the MTP arm and the quality gates were **not** run: the first arm
was already below the floor and the round was stopped, then deleted (cleanup below).

**Versions.** Strata `v0.2.11-3-g9f7d977d`, engine 0.1.57, ROCm 7.2.4 in `/opt/rocm`; Unsloth
`unsloth/Qwen3.8-Flash-Next-GGUF` revision `d96201194f103c906994f283f504209dc8d2a10c` (the revision Strata 0.2.11
pins). Shards, LFS sha256: `00001` `91e8dc8f…`, `00002` `11a67c82…` (47.02 GB), `00003` `05716382…` (28.80 GB, the
n-gram/PLE table every Unsloth set shares). Set size 75.8 GB.

**Machine.** RX 7900 XTX (272 W cap), Ryzen 7 5700X (AVX2, no AVX-512), 31.25 GiB RAM, Kingston A2000 NVMe
(PCIe 3.0, btrfs), zram swap with `vm.swappiness=150`.

**Commands.**

```bash
./setup.sh --setup --family qwen --model UD-IQ2_XS --gguf-dir <dir with the 3 shards> --backend hip \
  --vision no --no-browser --yes --no-start --context 262144 --kv int8 --vram-reserve-mib 3072
python3 scripts/strata.py apply && qwen-flash start
bash arm.sh base            # restart, 1 warm-up + short requests, print the log's own lines
```

`arm.sh` (this folder) sends `max_tokens 500`, `reasoning_effort low` and the tracked sampling (temperature 1.0,
`top_p` 0.95, `top_k` 20, `min_p` 0.0), then prints `N generated in ... (tok/s)`, `drafts accepted`, the OS read and
the decode wait, all parsed from the engine log.

## Install facts

- Setup wrote **no `experts.bin`** for this set: `--low-ram mmap does not apply to UD-IQ2_XS: it always reads part
  of its experts from the files`, and the start logs `experts via mmap (--mmap-experts; the GGUF shards in place,
  no experts.bin)`. Every expert read is a read of the three GGUF shards, so all three must stay on the NVMe.
- Disk cost is therefore the 75.8 GB download, not a ~33 GB pack (as for the ISTA sets) plus the download. The pack
  holds only the converted non-expert weights and the tokenizer (`index.txt: 1079 tensors, 302 served natively,
  arena 1.43 GiB`; `native pack: ... experts (largest blob 2.18 MB)`).
- Setup's start script writes `--spec 4 --mtp <mtp dir>`; the engine never receives those: the server picks the
  drafter at start (`serve/server.py:3781`, `drafting.apply`), and DFlash2 is Auto on gfx1100 since v0.2.10. Both
  arms ran DFlash2 alone (`--draft dflash2`, `--spec 6`, `--draft-fallback none`, `no MTP layer is loaded`), with
  `--draft-conf 0.7` (base) and `0.5` (ceiling).
- A start never downloads the drafter; `strata drafting fetch` puts it in `<strata_data>/dflash2/` beforehand
  (SOP). DFlash2 costs 800 MiB of VRAM (Q4_0) plus a 212.9 MiB draft head for 106,299 tokens.

## Memory split

Both arms load the same 39.4 GiB of experts; they differ in how much of it the GPU, the page-locked RAM copy and
the shards each hold.

| | Base arm (setup config) | Ceiling arm ("squeeze") |
|---|---|---|
| Context / KV / `--vram-reserve-mib` | 262,144 / int8 / 3072 | 131,072 / int8 / 2048 |
| `--resident-budget-gib` / `STRATA_RESIDENT_HEADROOM_GIB` | 8 / 6 | 14 / 4 |
| Experts, total | 39.4 GiB | 39.4 GiB |
| GPU expert cache | 11.15 GiB (6954 slots) | 13.92 GiB (8687 slots) |
| Experts the GPU cache does not hold | 28.23 GiB | 25.46 GiB |
| RAM copy, page-locked | 8.00 GiB | 14.00 GiB |
| File tier (streamed from the shards) | 20.2 GiB | 11.5 GiB |
| Page cache available to the file tier | 12.5 GiB | 7.4 GiB |
| Planned drive reads per 32,768-token prompt | ~104.9 GB | ~67.2 GB |
| Prompt-path lend slots covered by RAM | 0 of 2398 | 0 of 2403 |
| VRAM free with everything loaded | 3282 MiB | 2260 MiB |
| Conversation cache | 4352 MiB | 2048 MiB |
| `MemAvailable` after the run | — (not recorded) | 7.6 GiB |

## Per-request numbers

Short requests only (55-295-token prompts, 500-token cap); no long prompt was read in this round.

| Arm | Request | Generated | Decode tok/s | Drafts accepted | OS read | Decode waited on disk | GPU hit rate |
|---|---|---|---|---|---|---|---|
| base | warm-up | 158 | 1.6 | 112/137 (82%) | 80.5 GB | 60.7 s | 61.9% |
| base | 2 | 56 | 2.6 | 39/56 (70%) | 24.1 GB | 15.2 s | 59.6% |
| base | 3 | 399 | 5.7 | 254/320 (79%) | 49.2 GB | 42.5 s | 73.1% |
| base | 4 | 512 | 6.4 | 322/399 (81%) | 51.1 GB | 49.7 s | 77.6% |
| base | 5 | 454 | **8.2** | 302/377 (80%) | 40.3 GB | 36.3 s | 74.2% |
| base | 6 | 477 | 6.0 | 293/366 (80%) | 43.7 GB | 42.3 s | 76.9% |
| ceiling | warm-up | 472 | 10.3 | 319/456 (70%) | 70.2 GB | 33.6 s | 81.2% |
| ceiling | 2 | 385 | **10.8** | 260/392 (66%) | 25.5 GB | 20.8 s | 84.2% |
| ceiling | 3 | 456 | **10.8** | 310/453 (68%) | 26.6 GB | 21.6 s | 84.0% |
| ceiling | 4 | 402 | 7.1 | 276/377 (73%) | 27.8 GB | 23.2 s | 84.5% |

- Every warm request pulled 24-51 GB (base) or 25-28 GB (ceiling) off the drive to emit ~500 tokens, and spent
  15-50 s of its decode blocked on those reads.
- The ceiling arm's warm-up read 70.2 GB: the start had just released the shards' cached pages to build the 14 GiB
  page-locked copy (`0.20 GiB really free for a 14.00 GiB page-locked complement; the model files' cached pages
  were released`).
- The ceiling arm changed five things at once (context, VRAM reserve, RAM budget, headroom, draft confidence), so
  its +32% over the base arm's best request (8.2 -> 10.8 tok/s) is an upper bound, not an attribution.
- DFlash2 accepted ~79-81% of its drafts in the base arm and 66-73% in the ceiling arm (shorter context, lower
  `--draft-conf`); the MTP drafter was never run on this set.

## Why the experts off the GPU decide the speed

- On 32 GB, the host room beside the engine and a 6 GiB headroom left the page cache 12.5 GiB (base) or 7.4 GiB
  (ceiling). ISTA IQ2_XS on v0.2.8 had 20.67 GiB of experts off the GPU, and 18.53 GiB of them did fit a
  page-locked copy (2.1 GiB file tier); it decoded at 59-65 tok/s warm short
  ([`../20261030-strata-iq2xs-baseline/`](../20261030-strata-iq2xs-baseline/README.md)).
- UD-IQ2_XS has 39.4 GiB of experts against the ISTA set's 33.02 GiB. In the base arm the GPU cache held 11.15 GiB,
  so 28.23 GiB were off the GPU; the page-locked copy took 8.00 GiB of those, leaving 20.2 GiB that only the shards
  can serve. The engine's own plan says a 32,768-token prompt then re-reads ~104.9 GB from the drive.
- The engine priced the shards at 1.50 GB/s ("assumed": the drive probe did not recognize the NVMe) and measured
  `direct reads 1.18 GB/s, cached-path reads 0.33 GB/s (3.57x): the file cache stays`, i.e. the path it kept is the
  slow one on this host (open hypothesis 1).
- So the two remaining levers are context (ceiling arm) and a smaller expert set; more RAM copy only moves the file
  tier from 20.2 to 11.5 GiB, and every request still waits on the drive.

## Verdict

- **Rejected: below the user's 15 tok/s floor.** Best warm decode 10.8 tok/s (ceiling arm, 131K context) against
  8.2 tok/s on the setup config; halving the context and the reserve still left it 4.2 tok/s short.
- The speed comes from the file tier, not the drafter: DFlash2's acceptance was high (~79-81%) and the decode still
  waited 15-50 s per request on the drive.
- **Untested alternatives in the same family**: Unsloth UD-IQ1_M (68 GB) and UD-Q2_0 (70.5 GB). Both share this
  set's table (shard 3, sha `05716382…`), so only their other shards would download (shard 2 is 39,196,009,888 B
  and 41,738,806,688 B), and setup's RAM table on this PC gives them smaller expert sets (~35 GB and ~37 GB
  against this set's 39 GiB). Arithmetic, not measurement.
- **Not run**: the ~120K `strata_bench.py` sweep, the MTP arm, the coding suite and retrieval. The round stopped at
  the user's floor (2026-11-05) and the data is deleted, so none of them can be filled in later from this folder.

## Open hypotheses (unmeasured)

The first arms for the next round, one switch each, same set and engine.

1. **File cache instead of unbuffered reads** (3.57x measured penalty above). Arm: `STRATA_UNBUFFERED_LOAD=1`
   (forces unbuffered reads; `0` forces the cache), everything else unchanged. Compare OS read and decode wait.
2. **`GPU_PINNED_MIN_XFER_SIZE=1048576`** was carried over from the ISTA mapped mode. In this mode the copies come
   from page-locked RAM and in-place mapped shards, so the ROCclr userptr lock may only slow host->GPU copies.
   Arm: unset it and compare `strata generate: PCIe probe` and the decode's own PCIe lines.
3. **Resident budget and headroom were never swept**: two points only (8 GiB/6 GiB and 14 GiB/4 GiB). Arms:
   `--resident-budget-gib 10` and `12` at `STRATA_RESIDENT_HEADROOM_GIB` 4 and 6.
4. **`STRATA_ADAPT_OVERLAP_RESIDENT=1`**: the log says `adaptive overlap: off: not in the resident RAM mode unless
   STRATA_ADAPT_OVERLAP_RESIDENT=1`, so overlap never ran here. **`STRATA_RAM_ADAPT=1`** was never tested in the
   resident mode either (it was inert in the mapped mode). Two arms, one switch each.
5. **The drive is priced, not measured**: `drive 1.50 GB/s (assumed)`. Measure it and pin the real figure with
   `STRATA_SSD_GBPS=<GB/s>`; `STRATA_FILE_TIER_PROBE=0` shows the room rule alone.
6. **No same-hardware report exists yet**: the field reports quoted for "others run it" are the smaller ISTA IQ2_XS
   on an RTX 4070 12 GB / 32 GB (~48 tok/s), whose off-GPU set fit. Nothing published covers an Unsloth UD set of
   this size on gfx1100 + 32 GB; the cheapest next step is finding a report with `resident RAM mode` / `file tier`
   lines for the same set before buying more hardware or more RAM.

## Cleanup (2026-11-05)

Deleted: the UD-IQ2_XS model folder, `<strata_data>` (packs, `dflash2`, `mtp`), the old
`strata-engine-0.1.49.2-v0242` build, and every run config, start script and log of the deleted models in the
clone. Kept: the Strata clone at v0.2.11 with engine 0.1.57 built, the 27B and the llama.cpp engines. `/home` went
from 142 GB to 245 GB free, and `models.toml` has no `[strata.*]` table any more. Raw logs stay local (`_tmp/`,
git-ignored); this folder keeps a sanitized excerpt.

## Files here

- `arm.sh`: the restart-and-measure script, machine paths replaced by `<strata_dir>`.
- `log-excerpt.md`: the lines quoted above, copied from the engine log, machine paths replaced by placeholders.
