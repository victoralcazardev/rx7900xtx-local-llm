#!/usr/bin/env bash
# Dense vs. sparse on both engines, same depths and sampling as run.sh:
#   tintero dense token-major KV, tintero sparse decode (needs token-major KV, refuses a drafter),
#   nib production build with --sparse-pages 0 (dense); nib sparse 224 is the 2026-11-27 nib-v022 arm A.
# usage: run2.sh <tintero-dir> <nib-dir>
set -u
T=$1 N=$2
R=$(cd "$(dirname "$0")" && pwd)
L=~/IA/rx7900xtx-local-llm/_tmp/tintero
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
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
for arm in dense-tm sparse; do
  ( cd "$T" && exec .venv/bin/python serve/server.py --engine maya --config "$R/tintero-$arm.json" \
      --tokenizer ik2/tokenizer --host 127.0.0.1 --port 4444 ) > "$L/run2-$arm.log" 2>&1 &
  bench $! "tintero-$arm"
done
( cd "$N" && exec env HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$P/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf" \
    --mtp "$P/mtp.safetensors" --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 0 \
    --host 127.0.0.1 --port 4444 ) > "$L/run2-nib-dense.log" 2>&1 &
bench $! nib-dense
echo done
