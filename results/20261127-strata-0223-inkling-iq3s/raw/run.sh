#!/usr/bin/env bash
# Strata 0.2.23 (strata-inkling 0.1.70, hip-rx7900 package) with ISTA's Inkling-2-Mini GSQ-RCO IQ3_S on the
# RX 7900 XTX: start through `strata launch`, then decode/prefill by depth with the same harness and sampling as the
# nib and tintero rounds of 2026-11-27. Waits until no other GPU benchmark runs.
# usage: run.sh
set -u
R=$(cd "$(dirname "$0")" && pwd)
L=~/IA/rx7900xtx-local-llm/_tmp/strata-iq3s
H=~/IA/rx7900xtx-local-llm/results/20261127-nib-v022/raw
M=~/IA/Modelos/Inkling-2-Mini-GSQ-RCO-ISTA
PORT=4445
mkdir -p "$L"
samp='{"temperature":0.6,"top_p":0.95,"top_k":256,"min_p":0.0}'
while pgrep -f 'run2.sh|build-ik2/tintero|build/nib serve|parakeet-cli' >/dev/null; do sleep 30; done
echo "$(date -Is) start, load $(cut -d' ' -f1-3 /proc/loadavg), GPU $(rocm-smi --showuse | grep -o 'use (%): [0-9]*')" \
  >> "$R/conditions.txt"
strata launch --model-path "$M" --model gsq-rco-iq3_s --family inkling-2-mini --context 256k --vision off \
  --parallel 1 --tune skip --access local --port $PORT --yes --no-tui > "$L/launch.log" 2>&1
echo "$(date -Is) launch exit $?" >> "$R/conditions.txt"
ok=no
for j in $(seq 1 120); do curl -sf -m 2 127.0.0.1:$PORT/health >/dev/null && { ok=yes; break; }; sleep 5; done
echo "$(date -Is) health=$ok" >> "$R/conditions.txt"
pgrep -af 'strata' | grep -v -e run.sh -e pgrep | cut -c1-400 > "$R/processes.txt"
if [ $ok = yes ]; then
  python3 "$H/depth_http.py" $PORT --depths 8192 32768 131072 250000 --gen 256 --repeats 2 --chars-per-token 2.9 \
    --sampling "$samp" --label strata-iq3s --out "$R/speed.jsonl"
  rocm-smi --showmemuse | grep 'VRAM%' >> "$R/conditions.txt"
  python3 "$H/gsm8k_http.py" $PORT ~/IA/rx7900xtx-local-llm/_tmp/maya/gsm/gsm8k-test.jsonl --count 192 \
    --max-tokens 4096 --out "$R/gsm-strata-iq3s.jsonl" > "$R/gsm-summary.txt" 2>&1
fi
strata runtime stop > "$L/stop.log" 2>&1 || strata runtime cleanup >> "$L/stop.log" 2>&1 || true
sleep 5; pgrep -af "strata-inkling|serve/server.py" | head -3 >> "$R/conditions.txt"
echo done
