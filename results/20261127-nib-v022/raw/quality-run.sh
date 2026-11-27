#!/usr/bin/env bash
# Nib quality parity on the new build: GSM8K 192 exactly as the previous trial ran it for the Unbound
# graft (maya's rendered prompt to /v1/completions, greedy, 4,096-token cap), then one OpenAI
# tool-call request. One server start.
# usage: quality-run.sh <label> <nib-dir> [gsm-jsonl]
set -u
label=$1 nibdir=$2 G=${3:-$HOME/IA/rx7900xtx-local-llm/_tmp/maya/gsm/gsm8k-test.jsonl}
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
M=$P/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf
R=~/IA/rx7900xtx-local-llm/results/20261127-nib-v022/raw
L=~/IA/rx7900xtx-local-llm/_tmp/nib-v022
CRASH_LOG=$R/startup-crashes.txt
source "$R/serve-lib.sh"
cd "$nibdir" || exit 1
start_nib "$label-q" "$L/serve-q-$label.log" env HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$M" \
  --mtp "$P/mtp.safetensors" --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 \
  --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 --default-min-p 0.0 \
  --host 127.0.0.1 --port 4444 || { echo "server never came up; see $L/serve-q-$label.log"; exit 1; }
python3 "$R/gsm8k_http.py" 4444 "$G" --count 192 --max-tokens 4096 --raw --out "$R/gsm-raw-$label.jsonl"
python3 "$R/tool_check.py" 4444 --out "$R/tool-$label.txt"
kill -INT "$NIB_PID"; sleep 5; kill -9 "$NIB_PID" 2>/dev/null; wait "$NIB_PID" 2>/dev/null; sleep 3
