#!/usr/bin/env bash
# Greedy GSM8K on one model, same protocol as raw/gsm8k-run.sh and raw/gsm8k-q8d.sh: questions
# OFFSET..OFFSET+COUNT-1 of the OpenAI test set, the port's tests/ik2_gsm8k.py, 4096-token cap,
# maya-ik2 --serve-ik2 --ctx 8192 --chunk 2048 with the paged config (ik2-abiray-paged.json env).
# The request stream is generated once per OUT dir (token IDs from the first model given) and reused,
# so every model scored there answers exactly the same token IDs.
# usage: gsm8k-pair.sh <MODEL> <OFFSET> <OUT> [COUNT]      (COUNT default 96)
#    or: MODEL=<gguf> OFFSET=<n> OUT=<dir> [COUNT=<n>] gsm8k-pair.sh
# LABEL names the output files (default: the model's folder name); OUT/<LABEL>.{log,err,jsonl}.
set -u
D=~/IA/rx7900xtx-local-llm/results/20261123-inkling-round/raw
M=${1:-${MODEL:-}}
OFF=${2:-${OFFSET:-}}
O=${3:-${OUT:-}}
N=${4:-${COUNT:-96}}
if [ -z "$M" ] || [ -z "$OFF" ] || [ -z "$O" ]; then
  echo "usage: gsm8k-pair.sh <MODEL> <OFFSET> <OUT> [COUNT]" >&2; exit 2
fi
L=${LABEL:-$(basename "$(dirname "$M")")}
G=~/IA/rx7900xtx-local-llm/_tmp/maya/gsm
R=$O/gsm-$OFF.requests
mkdir -p "$O"
cd ~/IA/Motores/src/maya-inkling-mini-hip || exit 1
args="--model $M --data $G/gsm8k-test.jsonl --offset $OFF --count $N --max-tokens 4096"
if [ -f "$R" ]; then
  echo "$L: reusing request stream $R ($(wc -l < "$R") lines)"
else
  .venv/bin/python tests/ik2_gsm8k.py $args > "$R" || { echo "$L: request generation failed" >&2; exit 1; }
  echo "$L: wrote request stream $R"
fi
# production env, but a variable the caller set wins (e.g. IK2_KV=fp8-global for an A/B), as in bench_m.sh
eval "$(.venv/bin/python -c 'import json,os,shlex;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"export {k}={shlex.quote(v)}" for k,v in e.items() if k not in os.environ))')"
echo "$L: IK2_KV=$IK2_KV"
t0=$(date +%s)
./build-ik2/maya-ik2 --serve-ik2 --model "$M" --ctx 8192 --chunk 2048 < "$R" > "$O/$L.log" 2> "$O/$L.err"
rc=$?
echo "$L: maya exit $rc, wall $(( $(date +%s)-t0 )) s"
[ $rc -eq 0 ] || { echo "$L: maya failed, see $O/$L.err" >&2; exit 1; }
grep -m3 'VRAM free before graph capture\|every expert stays' "$O/$L.log"
.venv/bin/python tests/ik2_gsm8k.py $args --score "$O/$L.log" > "$O/$L.jsonl" || { echo "$L: scoring failed" >&2; exit 1; }
tail -1 "$O/$L.jsonl"
echo "$L: per-question scores in $O/$L.jsonl"
