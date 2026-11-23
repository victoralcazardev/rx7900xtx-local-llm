#!/usr/bin/env bash
# 2026-11-23 Inkling round: ik2_bench.py with the production maya env (ik2-abiray-paged.json).
# usage: bench.sh <label> <chunk> <ctx> <depths> <repeats> [extra ik2_bench args...] ; extra env via `env K=V bench.sh ...`
set -u -o pipefail
label=$1 chunk=$2 ctx=$3 depths=$4 repeats=$5; shift 5
cd ~/IA/Motores/src/maya-inkling-mini-hip
source ~/IA/Motores/src/build-env.sh >/dev/null 2>&1 || true
# production env first, caller's env wins
while IFS= read -r kv; do k=${kv%%=*}; [ -z "${!k+x}" ] && export "$kv"; done < <(.venv/bin/python -c 'import json;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"{k}={v}" for k,v in e.items()))')
M=~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf
O=~/IA/rx7900xtx-local-llm/_tmp/maya/r23
.venv/bin/python tools/ik2_bench.py --engine ./build-ik2/maya-ik2 --model "$M" --ctx "$ctx" --chunk "$chunk" \
  --gen 129 --repeats "$repeats" --tokens ~/IA/rx7900xtx-local-llm/_tmp/maya/docs.ids --depths "$depths" "$@" \
  2>"$O/$label.err" | sed "s/^{/{\"variant\": \"$label\", /" | tee -a "$O/bench.jsonl"
