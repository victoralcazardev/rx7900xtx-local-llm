#!/usr/bin/env bash
# IK2_SUFFIX (prompt-lookup verification, no drafter) on the q8dense file with the production env, 262K reserve.
# usage: [ARGS="--workload python --direct-answer --repeats 3"] suffix-run.sh <model> <out-dir> [windows...]
# Default windows: 0 8 64 128. Appends one JSON object per scored answer to <out-dir>/suffix-scores.jsonl,
# tagged with the window and the workload ARGS. Exits nonzero if any engine run or scoring fails.
set -u -o pipefail
M=$1 O=$2; shift 2
mkdir -p "$O" && O=$(cd "$O" && pwd)   # absolute: the script cds into the engine tree below
windows=("$@"); [ ${#windows[@]} -eq 0 ] && windows=(0 8 64 128)
cd ~/IA/Motores/src/maya-inkling-mini-hip || exit 1
source ~/IA/Motores/src/build-env.sh >/dev/null 2>&1 || true
while IFS= read -r kv; do k=${kv%%=*}; [ -z "${!k+x}" ] && export "$kv"; done < <(.venv/bin/python -c 'import json;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"{k}={v}" for k,v in e.items()))')
.venv/bin/python tests/ik2_copy_edit.py --tokenizer ik2/tokenizer ${ARGS:-} > "$O/copy.requests" || { echo "request generation failed" >&2; exit 1; }
rc=0
for w in "${windows[@]}"; do
  if ! IK2_SUFFIX=$w ./build-ik2/maya-ik2 --serve-ik2 --model "$M" --ctx 262144 --chunk 2048 <"$O/copy.requests" >"$O/copy-$w.log" 2>"$O/copy-$w.err"; then
    echo "window $w: maya failed, see $O/copy-$w.err" >&2; rc=1; continue
  fi
  grep -h -m1 "suffix verification" "$O/copy-$w.log" "$O/copy-$w.err" >&2
  .venv/bin/python tests/ik2_copy_edit.py --tokenizer ik2/tokenizer ${ARGS:-} --score "$O/copy-$w.log" \
    | W=$w A="${ARGS:-}" .venv/bin/python -c 'import json,os,sys
for l in sys.stdin:
    l=l.strip()
    if l.startswith("{"): print(json.dumps({"window": int(os.environ["W"]), "args": os.environ["A"], **json.loads(l)}))' \
    | tee -a "$O/suffix-scores.jsonl" || { echo "window $w: scoring failed" >&2; rc=1; }
done
exit $rc
