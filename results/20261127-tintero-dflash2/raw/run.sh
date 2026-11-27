#!/usr/bin/env bash
# Tintero dc52e6f on the RX 7900 XTX: decode/prefill by depth without a drafter, with the DFlash2 drafter, and with
# DFlash2 + sparse decode, same model (Abiray IQ4_NL q8dense) and the nib production sampling. One server per arm.
# Waits for an idle GPU first: the depth numbers are worthless while another GPU job runs.
# usage: run.sh <tintero-dir>
set -u
T=$1
R=$(cd "$(dirname "$0")" && pwd)
L=~/IA/rx7900xtx-local-llm/_tmp/tintero
mkdir -p "$L"
samp='{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}'

gpu_busy() {  # another GPU or heavy media job running, or GPU use above 5%
  pgrep -f 'parakeet-cli|remotion render|llama-server|build/nib|maya-ik2|build-ik2/tintero' >/dev/null && return 0
  local use; use=$(rocm-smi --showuse | grep -o 'GPU use (%): [0-9]*' | grep -o '[0-9]*$')
  [ "${use:-100}" -gt 5 ]
}
idle=0
while [ $idle -lt 6 ]; do  # 6 consecutive idle checks, 30 s apart
  if gpu_busy; then idle=0; else idle=$((idle+1)); fi
  sleep 30
done
echo "$(date -Is) GPU idle, load $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$R/conditions.txt"

for arm in base dflash2 dflash2-sparse; do
  ( cd "$T" && .venv/bin/python serve/server.py --engine maya --config "$R/tintero-$arm.json" \
      --tokenizer ik2/tokenizer --host 127.0.0.1 --port 4444 ) > "$L/serve-$arm.log" 2>&1 &
  pid=$! ok=no
  for j in $(seq 1 180); do
    curl -sf -m 2 -X POST 127.0.0.1:4444/v1/chat/completions -H 'content-type: application/json' \
      -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":4,"reasoning_effort":"none"}' >/dev/null \
      && { ok=yes; break; }
    kill -0 "$pid" 2>/dev/null || break; sleep 5
  done
  echo "$(date -Is) $arm up=$ok load $(cut -d' ' -f1-3 /proc/loadavg)" >> "$R/conditions.txt"
  [ "$ok" = yes ] && python3 "$R/depth_http.py" 4444 --depths 8192 32768 131072 250000 --gen 256 --repeats 2 \
      --chars-per-token 2.9 --sampling "$samp" --label "$arm" --out "$R/speed.jsonl"
  rocm-smi --showmemuse | grep 'VRAM%' >> "$R/conditions.txt"
  kill -INT "$pid"; sleep 8; pkill -9 -P "$pid" 2>/dev/null; kill -9 "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  pkill -9 -f 'build-ik2/tintero' 2>/dev/null; sleep 5
done
echo done
