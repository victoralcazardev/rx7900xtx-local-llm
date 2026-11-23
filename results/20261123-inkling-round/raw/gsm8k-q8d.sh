#!/usr/bin/env bash
# Greedy GSM8K (first 96 test questions, 4096-token cap) on the Q8_0-dense re-type, maya-ik2
# paged only. Model and request stream come from raw/gsm8k-run.sh (2026-11-22 round), so the
# score is directly comparable to that round's 95/96 on the original Abiray IQ4_NL file.
# usage: MODEL=<gguf> gsm8k-q8d.sh
set -u
G=~/IA/rx7900xtx-local-llm/_tmp/maya/gsm
O=~/IA/rx7900xtx-local-llm/_tmp/maya/r23/gsm-q8d
M=${MODEL:-~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf}
mkdir -p "$O"
cd ~/IA/Motores/src/maya-inkling-mini-hip
eval "$(.venv/bin/python -c 'import json,shlex;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"export {k}={shlex.quote(v)}" for k,v in e.items()))')"
t0=$(date +%s)
./build-ik2/maya-ik2 --serve-ik2 --model "$M" --ctx 8192 --chunk 2048 < $G/gsm-0.requests > $O/gsm.log 2> $O/gsm.err
echo "maya wall $(( $(date +%s)-t0 )) s"
.venv/bin/python tests/ik2_gsm8k.py --model "$M" --data $G/gsm8k-test.jsonl --count 96 --max-tokens 4096 \
  --score $O/gsm.log | tail -3
