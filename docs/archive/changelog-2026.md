# Changelog archive (2026)

Dated releases of [`CHANGELOG.md`](../CHANGELOG.md) from before the current cycle, moved here on 2026-11-23: the
live file keeps `Unreleased` and the current month ([STYLE.md](../STYLE.md) §8). Frozen: the entries are verbatim
from that move and are never edited again; a later change is a new entry in the live file.

## [2026-09-26]

### Changed

- Adopted `262k-q8q51-mtp` (262,144 context, KV `q8_0/q5_1`, MTP n=3, `-ub 256`) as the single
  default profile — see `docs/DECISIONS.md` and `docs/STATUS.md`.
- Reduced `models.toml` to a single model/profile and a single harness provider entry
  (`local-262k`), removing overlapping alternatives.
- Validated long-context retrieval quality: 60/60 exact match, 0 loop detections, 32K-240K fill.
- Evaluated and rejected the ROCm 10.0.0 runtime libraries (kept the ROCm 10 compiler) and
  BeeLlama v0.4.7's KVarN KV cache quantization — see `docs/measurements/engines.md` and
  `docs/measurements/kv-quality.md`.
### Added

- Added a systemd unit for the permanent 272 W power cap.
- Added community and CI files (`CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `CITATION.cff`, issue/PR templates, GitHub Actions CI) for public contributions.

## [2026-09-25]

### Added


- Initial curated public release: config, launcher, benchmark scripts, and measurement
  write-ups for running long-context Qwen3.8-27B on an AMD RX 7900 XTX.
