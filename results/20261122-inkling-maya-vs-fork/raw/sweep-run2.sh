#!/usr/bin/env bash
# Maya tuning sweep: same tokens/script as raw/maya.jsonl, one knob changed per variant.
set -u
cd ~/IA/Motores/src/maya-inkling-mini-hip
source ~/IA/Motores/src/build-env.sh >/dev/null 2>&1 || true
eval "$(.venv/bin/python -c 'import json,shlex;e=json.load(open("ik2-abiray-local.json"))["env"];print("\n".join(f"export {k}={shlex.quote(v)}" for k,v in e.items()))')"
M=~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf
O=~/IA/rx7900xtx-local-llm/_tmp/maya/sweep
run() { # label chunk extra-env...
  local label=$1 chunk=$2; shift 2
  echo "== $label" >&2
  env "$@" .venv/bin/python tools/ik2_bench.py --engine ./build-ik2/maya-ik2 --model "$M" --ctx 393216 --chunk "$chunk" \
    --gen 129 --repeats 1 --tokens ~/IA/rx7900xtx-local-llm/_tmp/maya/docs.ids --depths ${DEPTHS:-512,8192,131072,262144} \
    2>"$O/$label.err" | sed "s/^{/{\"variant\": \"$label\", /" | tee -a "$O/sweep.jsonl"
}
DEPTHS=512,32768,131072,262144
run paged-w8 2048 IK2_PAGED_KV=1 IK2_FLASH_WAVES=8
run paged-w2 2048 IK2_PAGED_KV=1 IK2_FLASH_WAVES=2
run paged-c1024 1024 IK2_PAGED_KV=1
run paged-w4-rep 2048 IK2_PAGED_KV=1
echo done
