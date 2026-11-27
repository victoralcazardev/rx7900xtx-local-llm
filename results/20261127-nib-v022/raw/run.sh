#!/usr/bin/env bash
# Nib v0.2.2 (+ thinking-cap patch) vs. production 2e16cf0 (+ the same patch): start loop, speed arms,
# greedy parity, GSM8K + tool call, thinking cap. One GPU, every step sequential.
# usage: run.sh <old-nib-dir> <new-nib-dir>
set -u
old=$1 new=$2
R=$(cd "$(dirname "$0")" && pwd)
L=~/IA/rx7900xtx-local-llm/_tmp/nib-v022
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
M=$P/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf
CRASH_LOG=$R/startup-crashes.txt
source "$R/serve-lib.sh"
mkdir -p "$L"
card='{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}'      # production: Unbound card + top_k 256
card_nok='{"temperature":0.6,"top_p":0.95,"min_p":0.0}'              # Unbound card as written (server top_k 0)

# 1. start loop: 10 starts of the new build with the production flags, stopped once /v1/models answers
for i in $(seq 1 10); do
  ( cd "$new" && env HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$M" --mtp "$P/mtp.safetensors" --no-vision \
      --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 --host 127.0.0.1 --port 4444 ) > "$L/start-$i.log" 2>&1 &
  pid=$! ok=no
  for j in $(seq 1 120); do
    curl -sf -m 1 127.0.0.1:4444/v1/models >/dev/null && { ok=yes; break; }
    kill -0 "$pid" 2>/dev/null || break; sleep 2
  done
  kill -INT "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null; wait "$pid"; rc=$?
  echo "start $i: up=$ok exit=$rc last: $(grep -v '^$' "$L/start-$i.log" | tail -1)" >> "$R/start-loop.txt"
  sleep 3
done

# 2. speed: A old card+top_k256, B new card+top_k256, C new card without top_k
bash "$R/speed-run.sh" A-old-card "$old" "$card"
bash "$R/speed-run.sh" B-new-card "$new" "$card"
bash "$R/speed-run.sh" C-new-card-notopk "$new" "$card_nok"

# 3. greedy parity (new, cap unset) against the 2e16cf0 file of the bdc9307 trial
bash "$R/greedy-run.sh" new-v022 "$new"
python3 "$R/greedy_compare.py" "$R/../../20261125-nib-bdc9307/raw/greedy-old-2e16cf0.jsonl" \
  "$R/greedy-new-v022.jsonl" > "$R/greedy-parity.txt" 2>&1

# 4. GSM8K 192 + tool call (new)
bash "$R/quality-run.sh" new-v022 "$new"

# 5. thinking cap 256 fires and the answer follows (new), 3 requests
cd "$new" && start_nib cap "$L/serve-cap.log" env HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$M" \
  --mtp "$P/mtp.safetensors" --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 \
  --default-temp 0.6 --default-top-p 0.95 --default-top-k 256 --default-min-p 0.0 --reasoning-budget 256 \
  --host 127.0.0.1 --port 4444 && {
  for k in 1 2 3; do python3 "$R/capreq.py" >> "$R/cap256.txt" 2>&1; done
  grep '\[serve\]' "$L/serve-cap.log" | tail -3 >> "$R/cap256.txt"
  kill -INT "$NIB_PID"; sleep 5; kill -9 "$NIB_PID" 2>/dev/null; wait "$NIB_PID" 2>/dev/null; }
echo done
