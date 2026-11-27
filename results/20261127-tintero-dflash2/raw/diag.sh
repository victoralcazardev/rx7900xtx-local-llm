#!/usr/bin/env bash
# Follow-up to run.sh: (1) is DFlash2 active? three 8K requests, then the engine log's draft lines; (2) sparse decode
# without a drafter (tintero refuses IK2_SPARSE_DECODE with speculation) at run.sh's depths.
# usage: diag.sh <tintero-dir>
set -u
T=$1
R=$(cd "$(dirname "$0")" && pwd)
L=~/IA/rx7900xtx-local-llm/_tmp/tintero
samp='{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}'
up() {
  for j in $(seq 1 180); do
    curl -sf -m 2 -X POST 127.0.0.1:4444/v1/chat/completions -H 'content-type: application/json' \
      -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":4,"reasoning_effort":"none"}' >/dev/null && return 0
    kill -0 "$1" 2>/dev/null || return 1; sleep 5
  done
  return 1
}
for arm in dflash2 sparse; do
  ( cd "$T" && exec .venv/bin/python serve/server.py --engine maya --config "$R/tintero-$arm.json" \
      --tokenizer ik2/tokenizer --host 127.0.0.1 --port 4444 ) > "$L/diag-$arm.log" 2>&1 &
  pid=$!
  if up "$pid"; then
    echo "$(date -Is) diag $arm up load $(cut -d' ' -f1-3 /proc/loadavg)" >> "$R/conditions.txt"
    if [ "$arm" = dflash2 ]; then
      python3 "$R/depth_http.py" 4444 --depths 8192 --gen 256 --repeats 3 --chars-per-token 2.9 --sampling "$samp" \
        --label dflash2-diag --out "$R/speed.jsonl"
      grep -i 'draft\|dflash\|accept' "$L/engine-dflash2.log" | tail -30 > "$R/dflash2-engine-lines.txt"
    else
      python3 "$R/depth_http.py" 4444 --depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9 \
        --sampling "$samp" --label sparse --out "$R/speed.jsonl"
    fi
  else
    echo "$(date -Is) diag $arm never came up: $(tail -1 "$L/engine-$arm.log" 2>/dev/null)" >> "$R/conditions.txt"
  fi
  kill -INT "$pid" 2>/dev/null; sleep 8; kill -9 "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  pgrep -x tintero >/dev/null && pkill -9 -x tintero; sleep 5
done
echo done
