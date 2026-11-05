# Engine log excerpt, Unsloth UD-IQ2_XS on Strata v0.2.11 (2026-11-05)

Copied from the engine log of both arms, unedited except for the machine paths (`<strata_dir>`, `<strata_data>`,
`<models_root>`). Base arm: engine line, memory plan and one warm request; ceiling arm: the same plus its three
warm requests. The full server output (`strata serve: prompt ...`, `thinking:`/`answering:` progress) is not
published.

## Base arm (setup config, started 17:04)

```text
[strata] 2026-11-05 17:04:11 engine started: <strata_dir>/engine/strata --serve --pack <strata_data>/packs/unsloth-ud-iq2_xs --native <models_root>/Qwen3.8-Flash-Next-UD-IQ2_XS/Qwen3.8-Flash-Next-UD-IQ2_XS-00001-of-00003.gguf --expert-profile <strata_dir>/data/expert-profile.bin --expert-cache auto --prefill auto --resident-budget-gib 8 --max-context 262144 --kv int8 --vram-reserve-mib 3072 --draft dflash2 --draft-model <strata_data>/dflash2/qwen3.8-flash-next-dflash2.q4_0.pack --draft-fallback none --mtp-draft-vocab <strata_data>/mtp/rt/draft_vocab.bin --spec 6 --draft-conf 0.7
strata generate: experts via mmap (--mmap-experts; the GGUF shards in place, no experts.bin)
strata generate: the file tier reads through the file cache (20.4 GiB available, 8.0 GiB of it still to be taken by the RAM copy, 31.4 GiB of experts read from the files: the file cache can keep the ones that come back; the cache holds 36% of the read set, direct reads 1.18 GB/s, cached-path reads 0.33 GB/s (3.57x): the file cache stays)
strata generate: expert cache 6954 slots, 11.15 GiB of VRAM; policy is
FileExpertSource: RAM budget 8.00 GiB: 5018 of the 28.23 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: WARNING: 2398 of 2398 lendable slots (100%) will read their experts from the pack during a long prompt; expect a slower prompt read on 50K+ token prompts (one measurement: 18% uncovered cost 26%). Raise --resident-budget-gib (the lend region comes after the ranked experts) and restart; the line above should read N of N.
strata generate: resident RAM mode: 8.00 GiB of experts in RAM (page-locked), 6954 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
strata: prefill plan: chunk 8192, ring 96 kept: file set 24.4 GiB does not fit the page cache 12.5 GiB -> about 104.9 GB read from the drive per 32768-token prompt (4 chunks); no option does better (the set cannot fit: fewest passes win)
strata: prefill plan inputs: 39.4 GiB experts, 11.1 GiB in the GPU caches, 8.0 GiB RAM copy (0 lend slots kept), file tier 20.2 GiB; 12.5 GiB available for the page cache; PCIe 14.0 GB/s; drive 1.50 GB/s (assumed); a 32768-token prompt
strata serve: prompt chunk auto: 8192 tokens, a 96-slot ring
strata dflash2: 106299-token draft head (212.9 MiB), drafter 800 MiB of VRAM (Q4_0 weights)
strata serve: DFlash2 drafter on (<strata_data>/dflash2/qwen3.8-flash-next-dflash2.q4_0.pack, graphs captured in 105 ms); windows up to 8 tokens; no MTP layer is loaded (--draft-fallback none)
strata serve: conversation cache sized from the free RAM: 4352 MiB for up to 4 parked conversations, so an agent's next turn reuses its prompt (--conversation-cache-mib N sets it, 0 turns it off)
strata serve: adaptive overlap: off: not in the resident RAM mode unless STRATA_ADAPT_OVERLAP_RESIDENT=1
strata serve: 3282 MiB of VRAM free with everything loaded
strata serve: prompt 66 tokens = 0 reused + 66 read in 10112 ms (6.5 tok/s), 454 generated in 55338 ms (8.2 tok/s), drafts accepted 302 of 377, 1 checkpoints
strata serve: decode expert cache hit rate: 74.2% (182092 hits / 245426 lookups); 8494 more read by the GPU over PCIe or from another GPU (3.3% of all 253920 routed)
strata serve: file tier I/O this request: the OS read 40313.9 MB from storage (16526 major faults) for 57698.8 MB of expert reads; page cache held 52830.0 MB at the read, not 4868.8 MB; ... decode waited 36336.9 ms in 13858 fetches; decode gate: cache room 0.36 of the experts, ...
strata serve: suffix drafts: 2 windows, 2 of 2 drafts accepted
```

## Ceiling arm (squeeze: 131K, reserve 2048, budget 14, headroom 4; started 17:22)

```text
[strata] 2026-11-05 17:22:20 engine started: <strata_dir>/engine/strata --serve --pack <strata_data>/packs/unsloth-ud-iq2_xs --native <models_root>/Qwen3.8-Flash-Next-UD-IQ2_XS/Qwen3.8-Flash-Next-UD-IQ2_XS-00001-of-00003.gguf --expert-profile <strata_dir>/data/expert-profile.bin --expert-cache auto --prefill auto --max-context 131072 --kv int8 --vram-reserve-mib 2048 --resident-budget-gib 14 --draft dflash2 --draft-model <strata_data>/dflash2/qwen3.8-flash-next-dflash2.q4_0.pack --draft-fallback none --mtp-draft-vocab <strata_data>/mtp/rt/draft_vocab.bin --spec 6 --draft-conf 0.5
strata generate: expert cache 8687 slots, 13.92 GiB of VRAM; policy is
FileExpertSource: RAM budget 14.00 GiB: 8761 of the 25.46 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: 0.20 GiB really free for a 14.00 GiB page-locked complement; the model files' cached pages were released: 19.86 GiB free
FileExpertSource: mapped pinned cache complement ready: resident 14.00 GiB, pinned 14.00 GiB in 35 s; page-locked and mapped
strata generate: resident RAM mode: 14.00 GiB of experts in RAM (page-locked), 8687 in the GPU cache; adaptive swaps exchange them with the GPU cache (no file reads)
strata: prefill plan: chunk 8192, ring 96 kept: file set 15.6 GiB does not fit the page cache 7.4 GiB -> about 67.2 GB read from the drive per 32768-token prompt (4 chunks); no option does better (the set cannot fit: fewest passes win)
strata: prefill plan inputs: 39.4 GiB experts, 13.9 GiB in the GPU caches, 14.0 GiB RAM copy (0 lend slots kept), file tier 11.5 GiB; 7.4 GiB available for the page cache; PCIe 14.0 GB/s; drive 1.50 GB/s (assumed); a 32768-token prompt
strata serve: DFlash2 drafter on (<strata_data>/dflash2/qwen3.8-flash-next-dflash2.q4_0.pack, graphs captured in 68 ms); windows up to 8 tokens; no MTP layer is loaded (--draft-fallback none)
strata serve: conversation cache sized from the free RAM: 2048 MiB for up to 4 parked conversations, so an agent's next turn reuses its prompt (--conversation-cache-mib N sets it, 0 turns it off)
strata serve: adaptive overlap: off: not in the resident RAM mode unless STRATA_ADAPT_OVERLAP_RESIDENT=1
strata serve: 2260 MiB of VRAM free with everything loaded
strata serve: prompt 66 tokens = 0 reused + 66 read in 10517 ms (6.3 tok/s), 385 generated in 35692 ms (10.8 tok/s), drafts accepted 260 of 392, 1 checkpoints
strata serve: decode expert cache hit rate: 84.2% (202027 hits / 239871 lookups); 8289 more read by the GPU over PCIe or from another GPU (3.3% of all 248160 routed)
strata serve: file tier I/O this request: the OS read 25467.2 MB from storage (5580 major faults) for 18594.4 MB of expert reads; page cache held 15522.2 MB at the read, not 3072.1 MB; ... decode waited 20824.0 ms in 7822 fetches; decode gate: cache room 0.19 of the experts, ...
strata serve: prompt 66 tokens = 0 reused + 66 read in 9458 ms (7.0 tok/s), 456 generated in 42314 ms (10.8 tok/s), drafts accepted 310 of 453, 1 checkpoints
strata serve: file tier I/O this request: the OS read 26628.6 MB from storage (7555 major faults) for 20975.4 MB of expert reads; ... decode waited 21570.6 ms in 9026 fetches; ...
strata serve: prompt 66 tokens = 0 reused + 66 read in 19281 ms (3.4 tok/s), 402 generated in 56626 ms (7.1 tok/s), drafts accepted 276 of 377, 1 checkpoints
strata serve: file tier I/O this request: the OS read 27811.5 MB from storage (9715 major faults) for 18197.0 MB of expert reads; ... decode waited 23221.4 ms in 8424 fetches; decode gate: cache room 0.19 of the experts, ...
```
