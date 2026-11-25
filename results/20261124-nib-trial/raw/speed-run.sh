#!/usr/bin/env bash
# Nib speed by depth over HTTP (nib bench hung/crashed on 2e16cf0): one server start per config.
# usage: speed-run.sh <label> <gguf> <sparse-pages> <mtp:on|off> [sampling-json]
set -u
label=$1 model=$2 sp=$3 mtp=$4 samp=${5:-'{"temperature":1.0,"top_k":256}'}
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
R=~/IA/rx7900xtx-local-llm/results/20261124-nib-trial/raw
cd ~/IA/Motores/src/nib
extra=(); [ "$mtp" = on ] && extra=(--mtp $P/mtp.safetensors)
HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$model" "${extra[@]}" --no-vision --slots 1 -c 262848 \
  --kv-type q8_0 --sparse-pages "$sp" --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 \
  --default-min-p 0.0 --host 127.0.0.1 --port 4444 > ~/IA/rx7900xtx-local-llm/_tmp/nib/serve-$label.log 2>&1 &
pid=$!
for i in $(seq 1 120); do curl -sf 127.0.0.1:4444/v1/models >/dev/null && break; sleep 2; done
python3 $R/depth_http.py 4444 --depths 512 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9 \
  --sampling "$samp" --label "$label" --out $R/speed.jsonl
kill -INT $pid; wait $pid 2>/dev/null; sleep 3
