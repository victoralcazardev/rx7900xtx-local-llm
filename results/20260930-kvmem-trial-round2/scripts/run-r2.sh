#!/bin/bash
# Round 2: block 32 at b28672, b36864 at block 128, crash repro b49152@190K.
cd ~/engines/kvmem-llama.cpp-src
export LD_LIBRARY_PATH=$PWD/build-hip-linux/lib:$PWD/build-hip-linux/bin:/opt/rocm/lib
B=$PWD/build-hip-linux/bin/llama-kvmem-server
M=~/models/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf
R=<repo>; T=$R/_tmp/kvmem-r2; D=$R/bench/res/longctx_quality/longctx-20260926-145634/documents
K="--device ROCm0 -ngl 99 --host 127.0.0.1 --port 8080 -c 262144 -b 512 -n 16384 --kvmem --kvmem-gen-reserve 16384 --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 2 --kvmem-mtp-state replay"
S="--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-effort medium --enable-thinking"
qual() { # budget block out docs...
  local b=$1 bt=$2 out=$3; shift 3
  $B -m $M $K --kvmem-budget $b --kvmem-block-tokens $bt --temp 0 --top-k 20 --min-p 0 > $T/server-$out.log 2>&1 &
  local sp=$!
  until curl -sf localhost:8080/health >/dev/null; do kill -0 $sp || return 1; sleep 3; done
  python3 $R/_tmp/kvmem_quality.py --out $T/$out.jsonl "$@"
  kill $sp; wait $sp; sleep 10
}
qual 28672 32 q-b28k-bt32 $D/d240000-n01.json $D/d240000-n00.json
python3 $R/_tmp/kvmem_depth.py --label crash-repro-b49k --out $T --depths 190000 -- $B -m $M $K --kvmem-budget 49152 --kvmem-block-tokens 128 $S
qual 36864 128 q-b36k $D/d240000-n01.json $D/d240000-n00.json
python3 $R/_tmp/kvmem_depth.py --label b28k-bt32 --out $T --depths 240000 -- $B -m $M $K --kvmem-budget 28672 --kvmem-block-tokens 32 $S
python3 $R/_tmp/kvmem_depth.py --label b36k --out $T --depths 240000 -- $B -m $M $K --kvmem-budget 36864 --kvmem-block-tokens 128 $S
echo DONE
