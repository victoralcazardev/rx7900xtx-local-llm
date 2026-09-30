#!/bin/bash
# Detached T5 continuation: 128K docs on b28672, then d240000-n01 on b49152.
cd ~/engines/kvmem-llama.cpp-src
export LD_LIBRARY_PATH=$PWD/build-hip-linux/lib:$PWD/build-hip-linux/bin:/opt/rocm/lib
M=~/models/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf
R=<repo>; T=$R/_tmp/kvmem-t5; D=$R/bench/res/longctx_quality
run() { # budget out docs...
  local b=$1 out=$2; shift 2
  build-hip-linux/bin/llama-kvmem-server -m $M --device ROCm0 -ngl 99 --host 127.0.0.1 --port 8080 -c 262144 -b 512 -n 16384 --kvmem --kvmem-budget $b --kvmem-gen-reserve 16384 --kvmem-block-tokens 128 --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 2 --kvmem-mtp-state replay --temp 0 --top-k 20 --min-p 0 > $T/server-$out.log 2>&1 &
  local sp=$!
  until curl -sf localhost:8080/health >/dev/null; do kill -0 $sp || return 1; sleep 3; done
  grep listening $T/server-$out.log
  python3 $R/_tmp/kvmem_quality.py --out $T/$out.jsonl "$@"
  kill $sp; wait $sp; sleep 10
}
run 28672 n2-b28k-128k $D/longctx-20260925-170146/documents/d128000-n0{0,1}.json
run 49152 n2-b49k $D/longctx-20260926-145634/documents/d240000-n01.json
echo DONE
