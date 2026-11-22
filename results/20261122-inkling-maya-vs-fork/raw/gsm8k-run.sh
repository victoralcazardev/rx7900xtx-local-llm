#!/usr/bin/env bash
# Paired GSM8K (first 96 test questions, greedy, 4096-token cap): maya-ik2 paged vs. the GodGMN fork, same token IDs.
set -u
G=~/IA/rx7900xtx-local-llm/_tmp/maya/gsm
M=~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf
cd ~/IA/Motores/src/maya-inkling-mini-hip
args="--model $M --data $G/gsm8k-test.jsonl --count 96 --max-tokens 4096"
eval "$(.venv/bin/python -c 'import json,shlex;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"export {k}={shlex.quote(v)}" for k,v in e.items()))')"
t0=$(date +%s)
./build-ik2/maya-ik2 --serve-ik2 --model "$M" --ctx 8192 --chunk 2048 < $G/gsm-0.requests > $G/gsm-maya.log 2> $G/gsm-maya.err
echo "maya wall $(( $(date +%s)-t0 )) s"
.venv/bin/python tests/ik2_gsm8k.py $args --score $G/gsm-maya.log | tail -3
E=~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix
$E/llama-server -m "$M" --port 8090 -c 8192 -ctk q8_0 -ctv q8_0 -fa on -np 1 -ngl all > $G/fork-server.log 2>&1 &
for i in $(seq 1 120); do curl -sf localhost:8090/health >/dev/null && break; sleep 1; done
t0=$(date +%s)
.venv/bin/python tests/ik2_gsm8k.py $args --llama-url http://127.0.0.1:8090 > $G/gsm-fork.out 2>&1
echo "fork wall $(( $(date +%s)-t0 )) s"; tail -3 $G/gsm-fork.out
pkill -INT -x llama-server
echo done
