#!/usr/bin/env bash
# mw00/project-maya v1.1.83 maya-ik2 (HIP build) on the RX 7900 XTX: paged dense KV and sparse decode (token-major KV),
# same model (Abiray IQ4_NL q8dense), depths and sampling as the 2026-11-27 tintero and nib rounds.
# usage: run.sh <project-maya-dir>
set -u
T=$1
R=$(cd "$(dirname "$0")" && pwd)
L=~/IA/rx7900xtx-local-llm/_tmp/pmaya
samp='{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}'
up() {
  for j in $(seq 1 180); do
    curl -sf -m 2 -X POST 127.0.0.1:4444/v1/chat/completions -H 'content-type: application/json' \
      -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":4,"reasoning_effort":"none"}' >/dev/null && return 0
    kill -0 "$1" 2>/dev/null || return 1; sleep 5
  done
  return 1
}
bench() {  # <pid> <label>
  if up "$1"; then
    echo "$(date -Is) $2 up load $(cut -d' ' -f1-3 /proc/loadavg)" >> "$R/conditions.txt"
    python3 "$R/depth_http.py" 4444 --depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9 \
      --sampling "$samp" --label "$2" --out "$R/speed.jsonl"
    rocm-smi --showmemuse | grep 'VRAM%' | sed "s/^/$2 /" >> "$R/conditions.txt"
  else
    echo "$(date -Is) $2 never came up" >> "$R/conditions.txt"
  fi
  kill -INT "$1" 2>/dev/null; sleep 8; kill -9 "$1" 2>/dev/null; wait "$1" 2>/dev/null
  pgrep -x tintero >/dev/null && pkill -9 -x tintero; sleep 5
}
for arm in paged sparse; do
  ( cd "$T" && exec .venv/bin/python serve/server.py --engine maya --config "$R/pmaya-$arm.json" \
      --tokenizer ik2/tokenizer --host 127.0.0.1 --port 4444 ) > "$L/run-$arm.log" 2>&1 &
  bench $! "pmaya-$arm"
  pgrep -x maya-ik2 >/dev/null && pkill -9 -x maya-ik2; sleep 3
done
echo done
