#!/usr/bin/env bash
# Start-only A/B: interleaved starts of the production build and plain v0.2.2 (no local patch), production flags,
# each stopped once /v1/models answers. Attributes the v0.2.2 start-up SIGSEGV to upstream or to the patch.
# usage: start-ab.sh <old-nib-dir> <plain-new-nib-dir> <n>
set -u
old=$1 new=$2 n=${3:-8}
R=$(cd "$(dirname "$0")" && pwd)
L=~/IA/rx7900xtx-local-llm/_tmp/nib-v022
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
M=$P/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf
one() {  # <tag> <dir>
  ( cd "$2" && env HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$M" --mtp "$P/mtp.safetensors" --no-vision \
      --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 --host 127.0.0.1 --port 4444 ) > "$L/ab-$1.log" 2>&1 &
  local pid=$! ok=no j rc
  for j in $(seq 1 90); do
    curl -sf -m 1 127.0.0.1:4444/v1/models >/dev/null && { ok=yes; break; }
    kill -0 "$pid" 2>/dev/null || break; sleep 2
  done
  kill -INT "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; rc=$?
  echo "$(date +%T) $1: up=$ok exit=$rc last: $(grep -v '^$' "$L/ab-$1.log" | tail -1 | cut -c1-90)" >> "$R/start-ab.txt"
  sleep 3
}
for i in $(seq 1 "$n"); do one "old-$i" "$old"; one "plain-$i" "$new"; done
