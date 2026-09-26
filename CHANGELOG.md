# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

- Measured MTP n=4 at 240K depth on the exact adopted flags (`-ub 256`): -8% mean tg vs. n=3
  (21.4 vs. 23.3 tok/s), 66% vs. 71% acceptance — n=3 stays adopted. Also found generated text is
  not bit-identical across n=2/n=3/`-ub 256` at temperature 0 for essay and code tasks.
- Re-validated long-context retrieval quality at 240K on the exact adopted server flags (MTP n=3,
  `-ub 256`, not just the KV q8_0/q5_1 variant, using `bench/longctx_quality.py`'s `--mtp-n`/
  `--extra` options): 8/8 exact match — cumulative 68/68 exact match, 32K-240K fill.

## [2026-09-26]

- Adopted `262k-q8q51-mtp` (262,144 context, KV `q8_0/q5_1`, MTP n=3, `-ub 256`) as the single
  default profile — see `docs/DECISIONS.md` and `docs/STATUS.md`.
- Reduced `models.toml` to a single model/profile and a single harness provider entry
  (`local-262k`), removing overlapping alternatives.
- Validated long-context retrieval quality: 60/60 exact match, 0 loop detections, 32K-240K fill.
- Evaluated and rejected the ROCm 10.0.0 runtime libraries (kept the ROCm 10 compiler) and
  BeeLlama v0.4.7's KVarN KV cache quantization — see `docs/measurements/engines.md` and
  `docs/measurements/kv-quality.md`.
- Added a systemd unit for the permanent 272 W power cap.
- Added community and CI files (`CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `CITATION.cff`, issue/PR templates, GitHub Actions CI) for public contributions.

## [2026-09-25]

- Initial curated public release: config, launcher, benchmark scripts, and measurement
  write-ups for running long-context Qwen3.8-27B on an AMD RX 7900 XTX.
