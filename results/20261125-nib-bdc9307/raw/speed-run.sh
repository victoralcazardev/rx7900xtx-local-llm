#!/usr/bin/env bash
# Nib speed by depth over HTTP (nib bench hung/crashed on 2e16cf0): one server start per arm.
# Same harness for both builds: the binary directory is the second argument, so A (old checkout) and
# B/C/D (new checkout) differ only in the build and in the sampling sent per request.
# usage: speed-run.sh <label> <nib-dir> [sampling-json]
set -u
label=$1 nibdir=$2 samp=${3:-'{"temperature":1.0,"top_k":256}'}
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
M=$P/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf
R=~/IA/rx7900xtx-local-llm/results/20261125-nib-bdc9307/raw
L=~/IA/rx7900xtx-local-llm/_tmp/nib-bdc9307
CRASH_LOG=$R/startup-crashes.txt
source "$R/serve-lib.sh"
cd "$nibdir" || exit 1
start_nib "$label" "$L/serve-$label.log" env HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$M" \
  --mtp "$P/mtp.safetensors" --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 \
  --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 --default-min-p 0.0 \
  --host 127.0.0.1 --port 4444 || { echo "server never came up; see $L/serve-$label.log"; exit 1; }
python3 "$R/depth_http.py" 4444 --depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9 \
  --sampling "$samp" --label "$label" --out "$R/speed.jsonl"
rc=$?
kill -INT "$NIB_PID"; sleep 5; kill -9 "$NIB_PID" 2>/dev/null; wait "$NIB_PID" 2>/dev/null; sleep 3
exit $rc
