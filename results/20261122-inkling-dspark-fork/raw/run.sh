#!/usr/bin/env bash
# usage: run.sh <label> [extra llama-server args...]
set -u
E=~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix
M=~/IA/Modelos/Inkling-2-Mini-Uncensored-AD/Inkling-2-Mini-Uncensored-AD-Q4_K.gguf
L=$1; shift
D=$(dirname "$0")
$E/llama-server -m $M --port 8090 -c 262144 -ctk q8_0 -ctv q8_0 -fa on -np 1 --ctx-checkpoints 10 -ngl all "$@" >$D/$L.log 2>&1 &
P=$!
for i in $(seq 1 180); do curl -sf localhost:8090/health >/dev/null && break; kill -0 $P 2>/dev/null || { echo "$L: server died"; tail -5 $D/$L.log; exit 1; }; sleep 1; done
vram=$(cat /sys/class/drm/card1/device/mem_info_vram_used)
for task in code prose; do
  if [ $task = code ]; then q="Write a Python module implementing an LRU cache class with get, put, delete and __len__, with type hints and docstrings, plus unittest tests. Code only."; else q="Write a 300-word short story about a lighthouse keeper."; fi
  for rep in 1 2; do
    curl -s localhost:8090/v1/chat/completions -H 'Content-Type: application/json' \
      -d "$(python3 -c 'import json,sys;print(json.dumps({"messages":[{"role":"user","content":sys.argv[1]}],"temperature":0,"max_tokens":768,"reasoning_effort":"low"}))' "$q")" \
      | python3 -c "import json,sys;r=json.load(sys.stdin);t=r['timings'];print('$L $task rep$rep','tg=%.1f'%t['predicted_per_second'],'n=%d'%t['predicted_n'],'draft=%s/%s'%(t.get('draft_n_accepted','-'),t.get('draft_n','-')),'finish=',r['choices'][0]['finish_reason'])"
  done
done
echo "$L vram_used_MiB=$((vram/1048576))"
kill $P; wait $P 2>/dev/null
