#!/usr/bin/env bash
# 262K retrieval: a seeded four-word phrase at 5/50/95% among GSM8K distractors; maya-ik2 paged, then the fork, same IDs.
set -u
N=~/IA/rx7900xtx-local-llm/_tmp/maya/needle; G=~/IA/rx7900xtx-local-llm/_tmp/maya/gsm
M=~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf
D=261888
cd ~/IA/Motores/src/maya-inkling-mini-hip
eval "$(.venv/bin/python -c 'import json,shlex;e=json.load(open("ik2-abiray-paged.json"))["env"];print("\n".join(f"export {k}={shlex.quote(v)}" for k,v in e.items()))')"
needle() { .venv/bin/python tests/ik2_retrieval.py --tokenizer ik2/tokenizer --data $G/gsm8k-test.jsonl --depths $D --percent "$1" --direct-answer --max-tokens 200 "${@:2}"; }
for p in 5 50 95; do
  needle $p | ./build-ik2/maya-ik2 --serve-ik2 --model "$M" --ctx 262144 --chunk 2048 > $N/maya-$p.log 2> $N/maya-$p.err
  echo "maya $p: $(needle $p --score $N/maya-$p.log 2>&1 | tail -2 | tr '\n' ' ')"
done
E=~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix
$E/llama-server -m "$M" --port 8090 -c 262144 -ctk q8_0 -ctv q8_0 -fa on -np 1 -ngl all > $N/fork-server.log 2>&1 &
for i in $(seq 1 180); do curl -sf localhost:8090/health >/dev/null && break; sleep 1; done
for p in 5 50 95; do echo "fork $p: $(needle $p --llama-url http://127.0.0.1:8090 2>&1 | tail -2 | tr '\n' ' ')"; done
pkill -INT -x llama-server
echo done
