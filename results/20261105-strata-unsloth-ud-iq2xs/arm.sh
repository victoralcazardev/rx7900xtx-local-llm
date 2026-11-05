#!/usr/bin/env bash
# One tuning arm: restart Strata with the current run config, 1 warm-up + 3 short requests, print decode speed and
# disk reads. Paths are placeholders (<strata_dir> is the clone; its log name follows the run config).
# Usage: arm.sh <label>
set -uo pipefail
LABEL=$1
S=<strata_dir>
L=$S/strata-unsloth-ud-iq2_xs.log
export QWEN_FLASH_MODEL=unsloth-ud-iq2_xs
qwen-flash stop >/dev/null 2>&1; sleep 3
qwen-flash start --force >/dev/null 2>&1 || { echo "$LABEL: start failed"; tail -20 "$L.server.out"; exit 1; }
grep -E "prefill plan inputs|VRAM free with|resident RAM mode:" "$L" | tail -3 | sed 's/^/  /'
for i in 0 1 2 3; do
  curl -s -m 600 localhost:8080/v1/chat/completions -H 'content-type: application/json' \
    -d '{"model":"x","messages":[{"role":"user","content":"Explain in 150 words how a hash map handles collisions, then give a short Python example. Variant '$i'."}],"max_tokens":500,"reasoning_effort":"low"}' >/dev/null
  [ "$i" = 0 ] && continue
  p=$(grep "strata serve: prompt" "$L" | tail -1 | grep -oE "[0-9]+ generated in [0-9]+ ms \([0-9.]+ tok/s\)|drafts accepted [0-9]+ of [0-9]+")
  io=$(grep "file tier I/O" "$L" | tail -1 | grep -oE "the OS read [0-9.]+ MB|decode waited [0-9.]+ ms" | tr '\n' ' ')
  echo "$LABEL r$i: $(echo $p) | $io"
done
echo "$LABEL MemAvailable $(awk '/MemAvailable/{printf "%.1f GiB", $2/1048576}' /proc/meminfo) | $(grep 'hit rate' "$L" | tail -1 | grep -oE '[0-9.]+% \(')"
