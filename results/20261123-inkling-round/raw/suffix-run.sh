#!/usr/bin/env bash
# IK2_SUFFIX (prompt-lookup verification, no drafter) on the q8dense file with the production env, 262K reserve.
# usage: [ARGS="--workload python --direct-answer --repeats 3"] suffix-run.sh <model> <out-dir> [windows...]
set -u -o pipefail
M=$1 O=$2; shift 2
mkdir -p "$O"
cd ~/IA/Motores/src/maya-inkling-mini-hip
source ~/IA/Motores/src/build-env.sh >/dev/null 2>&1 || true
while IFS= read -r kv; do k=${kv%%=*}; [ -z "${!k+x}" ] && export "$kv"; done < <(.venv/bin/python -c 'import json;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"{k}={v}" for k,v in e.items()))')
.venv/bin/python tests/ik2_copy_edit.py --tokenizer ik2/tokenizer ${ARGS:-} > "$O/copy.requests" || { echo "request generation failed"; exit 1; }
for w in "${@:-0 8 64 128}"; do
  IK2_SUFFIX=$w ./build-ik2/maya-ik2 --serve-ik2 --model "$M" --ctx 262144 --chunk 2048 <"$O/copy.requests" >"$O/copy-$w.log" 2>"$O/copy-$w.err"
  echo "== window $w"; grep -E "suffix verification" "$O/copy-$w.log" "$O/copy-$w.err" | head -1
  .venv/bin/python tests/ik2_copy_edit.py --tokenizer ik2/tokenizer ${ARGS:-} --score "$O/copy-$w.log"
done
