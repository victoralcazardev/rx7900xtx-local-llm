#!/usr/bin/env bash
# Retest Chromadera/nib#1 on the new build, as the author asked. Output: one log per test + summary.txt.
set -u
NEW=~/IA/Motores/src/nib-main; OLD=~/IA/Motores/src/nib
P=~/IA/Modelos/Inkling-2-Mini-Nib-Pack; M=$P/Inkling-2-Mini-NVFP4-Mixed.gguf
O=~/IA/rx7900xtx-local-llm/_tmp/nib-retest; S=$O/summary.txt; : > $S
kmsg() { journalctl -k --since "@$1" --no-pager 2>/dev/null | grep -iE 'amdgpu|gpu reset|page fault|ring|traps: nib' | tail -5; }
up() { for j in $(seq 1 60); do curl -sf -m1 127.0.0.1:4444/v1/models >/dev/null && return 0; kill -0 $1 2>/dev/null || return 1; sleep 2; done; return 2; }
python3 ~/IA/rx7900xtx-local-llm/scripts/launch.py --stop >/dev/null 2>&1
# 1. startup crash rate, interleaved new/old, serve --mtp
for i in $(seq 1 10); do for b in new old; do
  d=$NEW; [ $b = old ] && d=$OLD; t=$(date +%s)
  (cd $d && exec ./build/nib serve -m $M --mtp $P/mtp.safetensors --no-vision --slots 1 -c 262848 --kv-type q8_0 --sparse-pages 224 --host 127.0.0.1 --port 4444) > $O/start-$b-$i.log 2>&1 &
  pid=$!; up $pid; r=$?
  case $r in 0) res=up;; 1) wait $pid; res="died exit=$?";; *) res=timeout;; esac
  kill -INT $pid 2>/dev/null; sleep 4; kill -9 $pid 2>/dev/null; wait $pid 2>/dev/null
  echo "start $b #$i: $res | last: $(grep -v '^\s*$' $O/start-$b-$i.log | tail -1 | cut -c1-90)" >> $S; kmsg $t >> $S; sleep 3
done; done
# 2-3. bench sp224, with and without graphs (issue #1)
for g in "" "--no-graph"; do t=$(date +%s)
  (cd $NEW && timeout 300 ./build/nib bench -m $M -c 262848 --kv-type q8_0 --sparse-pages 224 $g -d 0) > $O/bench-sp224$g.log 2>&1
  echo "bench sp224 $g: exit $? | $(tail -2 $O/bench-sp224$g.log | tr '\n' ' ' | cut -c1-200)" >> $S; kmsg $t >> $S; sleep 3; done
# 4. bench sp0 (issue #2: hang)
t=$(date +%s)
(cd $NEW && HIP_LAUNCH_BLOCKING=1 AMD_LOG_LEVEL=1 timeout 300 ./build/nib bench -m $M -c 262848 --kv-type q8_0 --sparse-pages 0 -d 0) > $O/bench-sp0.log 2>&1
echo "bench sp0 (HIP_LAUNCH_BLOCKING=1): exit $? (124=timeout) | $(tail -2 $O/bench-sp0.log | tr '\n' ' ' | cut -c1-200)" >> $S; kmsg $t >> $S; sleep 3
# 5. serve without --mtp under gdb (issue #3)
t=$(date +%s)
(cd $NEW && exec gdb -batch -ex run -ex "bt 30" --args ./build/nib serve -m $M --no-vision --slots 1 -c 262848 --kv-type q8_0 --sparse-pages 224 --host 127.0.0.1 --port 4444) > $O/serve-nomtp-gdb.log 2>&1 &
pid=$!; up $pid; r=$?
if [ $r = 0 ]; then
  curl -s -m120 127.0.0.1:4444/v1/chat/completions -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"What is 17*23?"}],"max_tokens":512,"temperature":0}' > $O/serve-nomtp-req.json
  echo "serve no-mtp: up; request: $(python3 -c 'import json;d=json.load(open("'$O'/serve-nomtp-req.json"));print(d["choices"][0]["finish_reason"],d["usage"]["completion_tokens"],d.get("timings",{}).get("predicted_per_second"))' 2>&1)" >> $S
  pkill -INT -f "nib serve -m $M --no-vision" ; sleep 5; pkill -9 -f "nib serve -m $M --no-vision"
else echo "serve no-mtp: r=$r" >> $S; fi
sleep 8; kill $pid 2>/dev/null; wait $pid 2>/dev/null
grep -E "^#|SIG" $O/serve-nomtp-gdb.log | head -20 >> $S; kmsg $t >> $S
# restore production
cd ~/IA/rx7900xtx-local-llm && setsid python3 scripts/launch.py --background </dev/null >/dev/null 2>&1
until curl -sf -m2 localhost:8080/health >/dev/null; do sleep 2; done; echo "production restored" >> $S
cat $S
