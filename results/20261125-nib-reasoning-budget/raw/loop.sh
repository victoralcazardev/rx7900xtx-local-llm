#!/usr/bin/env bash
# usage: loop.sh <nib-binary> <n> <tag>; starts serve n times, one chat request each, records outcome
BIN=$1; N=$2; TAG=$3; M=~/models/Inkling-2-Mini-Nib-Pack
OUT=_tmp/nibcap/$TAG; mkdir -p $OUT
for i in $(seq 1 $N); do
  $BIN serve -m $M/Inkling-2-Mini-Unbound-v2.1-NVFP4-Mixed.gguf --mtp $M/mtp.safetensors --mmproj $M/mmproj-Inkling-2-Mini-Q8_0.gguf \
    --slots 1 -c 262144 --kv-type q8_0 --sparse-pages 224 --default-temp 0.6 --default-top-p 0.95 --default-top-k 256 --default-min-p 0.0 $EXTRA \
    --host 127.0.0.1 --port 4444 > $OUT/start-$i.log 2>&1 &
  pid=$!; res=died
  for j in $(seq 1 150); do
    kill -0 $pid 2>/dev/null || break
    if curl -sf -m 1 127.0.0.1:4444/v1/models >/dev/null; then
      r=$(curl -s -m 60 127.0.0.1:4444/v1/chat/completions -H 'content-type: application/json' \
        -d '{"messages":[{"role":"user","content":"Count from 1 to 20."}],"max_tokens":256}' | head -c 2000)
      echo "$r" | grep -q '"content"' && res=ok || res=badreq
      break
    fi
    sleep 2
  done
  kill $pid 2>/dev/null; wait $pid 2>/dev/null; rc=$?
  echo "$(date +%T) $TAG start $i: $res exit=$rc last: $(grep -v '^\s*$' $OUT/start-$i.log | tail -1 | head -c 150)" | tee -a $OUT/summary.txt
  sleep 3
done
