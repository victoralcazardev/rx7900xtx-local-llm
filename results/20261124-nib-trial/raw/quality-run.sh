#!/usr/bin/env bash
# Nib quality: GSM8K 192 greedy (optional) + multi-needle retrieval at 32K/128K/240K, one server per config.
# usage: quality-run.sh <label> <gguf> <sparse-pages> <gsm:yes|no>
set -u
label=$1 model=$2 sp=$3 gsm=$4
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
R=~/IA/rx7900xtx-local-llm/results/20261124-nib-trial/raw
G=~/IA/rx7900xtx-local-llm/_tmp/maya/gsm/gsm8k-test.jsonl
cd ~/IA/Motores/src/nib
HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$model" --mtp $P/mtp.safetensors --no-vision --slots 1 -c 262848 \
  --kv-type q8_0 --sparse-pages "$sp" --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 \
  --default-min-p 0.0 --host 127.0.0.1 --port 4444 > ~/IA/rx7900xtx-local-llm/_tmp/nib/serve-q-$label.log 2>&1 &
pid=$!
for i in $(seq 1 120); do curl -sf 127.0.0.1:4444/v1/models >/dev/null && break; sleep 2; done
kill -0 $pid || { echo "server died"; exit 1; }
[ "$gsm" = yes ] && python3 $R/gsm8k_http.py 4444 $G --count 192 --max-tokens 4096 --raw --out $R/gsm-raw-$label.jsonl
python3 $R/needle_http.py 4444 $G --depths ${DEPTHS:-32000 128000 240000} --cases 3 --needles 4 --chars-per-token ${CPT:-2.9} \
  --out $R/needle-$label${SUFFIX:-}.jsonl
kill -INT $pid; sleep 5; kill -9 $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 2
