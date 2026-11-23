#!/usr/bin/env bash
# Usage: run.sh <ctx> <percent>  -- one retrieval at depth ctx-256 on maya-ik2 (q8d, launcher env), VRAM sampled every 2 s.
set -u
CTX=$1; P=$2; D=$((CTX-256))
O=$(cd "$(dirname "$0")" && pwd); G=~/IA/rx7900xtx-local-llm/_tmp/maya/gsm
M=~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray-q8dense/Inkling-2-Mini-Uncensored-IQ4_NL-q8dense.gguf
cd ~/IA/Motores/src/maya-inkling-mini-hip-f472e94
eval "$(.venv/bin/python -c 'import json,shlex;e=json.load(open("/home/victor/IA/rx7900xtx-local-llm/_tmp/maya/inkling2-mini-unc-q8d.maya.json"))["env"];print("\n".join(f"export {k}={shlex.quote(v)}" for k,v in e.items()))')"
needle() { .venv/bin/python tests/ik2_retrieval.py --tokenizer ik2/tokenizer --data $G/gsm8k-test.jsonl --depths $D --percent "$1" --direct-answer --max-tokens 200 "${@:2}"; }
VR=$(ls /sys/class/drm/card*/device/mem_info_vram_used | head -1)
( while sleep 2; do echo "$(date +%s) $(cat $VR)"; done ) > $O/vram-$CTX-$P.txt &
MON=$!
T0=$(date +%s)
needle $P | ./build-ik2/maya-ik2 --serve-ik2 --model "$M" --ctx $CTX --chunk 2048 > $O/maya-$CTX-$P.log 2> $O/maya-$CTX-$P.err
RC=$?
kill $MON
echo "ctx=$CTX p=$P rc=$RC wall=$(( $(date +%s)-T0 ))s peak_vram_MiB=$(awk '{if($2>m)m=$2}END{printf "%.0f", m/1048576}' $O/vram-$CTX-$P.txt) total_MiB=$(( $(cat ${VR%used}total)/1048576 ))"
echo "score: $(needle $P --score $O/maya-$CTX-$P.log 2>&1 | tail -2 | tr '\n' ' ')"
grep -i -E "resident|free before|out of memory|error" $O/maya-$CTX-$P.err | head -8
