#!/usr/bin/env bash
# One nib server per file: 8 gray-zone refusal prompts (temp 0) and optionally GSM8K 192 (maya prompt, --raw).
# usage: unbound-run.sh <label> <gguf> <gsm:yes|no>
set -u
label=$1 model=$2 gsm=$3
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
R=~/IA/rx7900xtx-local-llm/results/20261124-nib-trial/raw
I=~/IA/rx7900xtx-local-llm/results/20261123-inkling-round/raw
cd ~/IA/Motores/src/nib
./build/nib serve -m "$model" --mtp $P/mtp.safetensors --no-vision --slots 1 -c 262848 --kv-type q8_0 \
  --sparse-pages 224 --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 --default-min-p 0.0 \
  --host 127.0.0.1 --port 4444 > ~/IA/rx7900xtx-local-llm/_tmp/nib/serve-u-$label.log 2>&1 &
pid=$!
for i in $(seq 1 120); do curl -sf 127.0.0.1:4444/v1/models >/dev/null && break; sleep 2; done
kill -0 $pid || { echo "server died"; exit 1; }
python3 $I/refusal_one.py 4444 $I/refusal-q8dense.json 1 2 3 4 5 6 7 8 > $R/refusal-$label.json
[ "$gsm" = yes ] && python3 $R/gsm8k_http.py 4444 ~/IA/rx7900xtx-local-llm/_tmp/maya/gsm/gsm8k-test.jsonl \
  --count 192 --max-tokens 4096 --raw --out $R/gsm-raw-$label.jsonl
kill -INT $pid; sleep 5; kill -9 $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 2
