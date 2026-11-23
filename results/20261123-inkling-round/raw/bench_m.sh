#!/usr/bin/env bash
# 2026-11-23 Inkling round: bench.sh with the model taken from the MODEL env var, so the
# Q8_0-dense re-type (raw/retype_q8.py) can be measured with the identical production env.
# usage: MODEL=<gguf> IK2_DRAFT_CTX=... bench_m.sh <label> <chunk> <ctx> <depths> <repeats> [extra ik2_bench args...]
set -u
label=$1 chunk=$2 ctx=$3 depths=$4 repeats=$5; shift 5
cd ~/IA/Motores/src/maya-inkling-mini-hip
source ~/IA/Motores/src/build-env.sh >/dev/null 2>&1 || true
# production env first, caller's env wins
while IFS= read -r kv; do k=${kv%%=*}; [ -z "${!k+x}" ] && export "$kv"; done < <(.venv/bin/python -c 'import json;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"{k}={v}" for k,v in e.items()))')
M=${MODEL:-~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf}
O=~/IA/rx7900xtx-local-llm/_tmp/maya/r23
.venv/bin/python tools/ik2_bench.py --engine ./build-ik2/maya-ik2 --model "$M" --ctx "$ctx" --chunk "$chunk" \
  --gen 129 --repeats "$repeats" --tokens ~/IA/rx7900xtx-local-llm/_tmp/maya/docs.ids --depths "$depths" "$@" \
  2>"$O/$label.err" | sed "s/^{/{\"variant\": \"$label\", /" | tee -a "$O/bench.jsonl"
