#!/usr/bin/env bash
# usage: serve.sh <binary> <log> [extra flags...]; starts nib on :4444 and waits until it answers
BIN=$1; LOG=$2; shift 2
M=~/models/Inkling-2-Mini-Nib-Pack
$BIN serve -m $M/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf --mtp $M/mtp.safetensors --mmproj $M/mmproj-Inkling-2-Mini-Q8_0.gguf \
  --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 --default-temp 0.6 --default-top-p 0.95 --default-top-k 256 \
  --default-min-p 0.0 "$@" --host 127.0.0.1 --port 4444 > $LOG 2>&1 &
for j in $(seq 1 90); do curl -sf -m1 127.0.0.1:4444/v1/models >/dev/null && { grep "Config:" $LOG; exit 0; }; sleep 2; done
echo "start failed: $(tail -1 $LOG)"; exit 1
