#!/usr/bin/env bash
# Greedy (temperature 0) parity gate: three prompts against one build, same server flags as the
# speed arms. Run it once per build, then diff the two files with greedy_compare.py.
# usage: greedy-run.sh <label> <nib-dir>
set -u
label=$1 nibdir=$2
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
M=$P/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf
R=~/IA/rx7900xtx-local-llm/results/20261127-nib-v022/raw
L=~/IA/rx7900xtx-local-llm/_tmp/nib-v022
CRASH_LOG=$R/startup-crashes.txt
source "$R/serve-lib.sh"
cd "$nibdir" || exit 1
start_nib "g-$label" "$L/serve-g-$label.log" env HIP_VISIBLE_DEVICES=0 ./build/nib serve -m "$M" \
  --mtp "$P/mtp.safetensors" --no-vision --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 \
  --default-temp 1.0 --default-top-p 1.0 --default-top-k 0 --default-min-p 0.0 \
  --host 127.0.0.1 --port 4444 || { echo "server never came up; see $L/serve-g-$label.log"; exit 1; }
python3 "$R/greedy_parity.py" 4444 --label "$label" --out "$R/greedy-$label.jsonl" --depth 32768 --gen 256
rc=$?
kill -INT "$NIB_PID"; sleep 5; kill -9 "$NIB_PID" 2>/dev/null; wait "$NIB_PID" 2>/dev/null; sleep 3
exit $rc
