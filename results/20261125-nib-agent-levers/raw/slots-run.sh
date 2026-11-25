#!/usr/bin/env bash
set -u
R=~/IA/rx7900xtx-local-llm; O=$R/_tmp/nib-slots; P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack
cd $R && python3 scripts/launch.py --stop >/dev/null 2>&1
for s in 1 2; do
  (cd ~/IA/Motores/src/nib && exec ./build/nib serve -m $P/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf --mtp $P/mtp.safetensors --no-vision --slots $s -c 262144 --kv-type q8_0 --sparse-pages 224 --default-temp 0.6 --default-top-p 0.95 --default-top-k 256 --default-min-p 0.0 --host 127.0.0.1 --port 4444) > $O/serve-slots$s.log 2>&1 &
  pid=$!; for i in $(seq 90); do curl -sf -m1 127.0.0.1:4444/v1/models >/dev/null && break; sleep 2; done
  grep -E "Config|VRAM|vram" $O/serve-slots$s.log | tail -2
  python3 $O/abab.py 4444 slots$s 60000 160000 | tee -a $O/abab.jsonl
  curl -s 127.0.0.1:4444/health | head -c 400; echo
  kill -INT $pid; sleep 5; kill -9 $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 3
done
setsid python3 scripts/launch.py --background </dev/null >/dev/null 2>&1
until curl -sf -m2 localhost:8080/health >/dev/null; do sleep 2; done; echo production restored
