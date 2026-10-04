#!/usr/bin/env bash
# usage: arm.sh <arm> <engine_dir>   Runs the §8 start gate, one server, the watcher and run_arm.py.
set -u
ARM=$1; ENG=$2; PORT=18085
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
D=/sys/class/drm/card1/device; H=$D/hwmon/hwmon3
gate() {
  local j m v
  j=$(( $(cat $H/temp2_input) / 1000 )); m=$(( $(cat $H/temp3_input) / 1000 )); v=$(( $(cat $D/mem_info_vram_used) / 1048576 ))
  echo "gate: junction=${j}C mem=${m}C vram_used=${v}MiB llama-server=$(pgrep -x llama-server | tr '\n' ' ')"
  pgrep -x llama-server >/dev/null && return 1
  ss -ltnH | grep -q ":$PORT " && return 1
  [ "$j" -lt 90 ] && [ "$m" -lt 95 ] && [ "$v" -lt 2048 ]
}
until gate; do sleep 30; done
LOG=$HERE/$ARM.server.log
export E3_SWAP0=$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
echo "swap used at arm start: ${E3_SWAP0} MiB"
"$ENG/llama-server" -m ~/models/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf \
  --port $PORT -c 262144 -ctk q8_0 -ctv q5_1 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 -fa on -np 1 \
  --ctx-checkpoints 4 -ngl all --metrics --spec-type draft-mtp,ngram-map-k4v --spec-draft-n-max 3 -ub 256 \
  --reasoning-effort medium --cache-ram 12288 -lv 4 > "$LOG" 2>&1 &
SPID=$!
echo "server pid=$SPID arm=$ARM engine=$ENG"
python3 "$REPO/scripts/gpu_watch.py" --interval 2 --pid $SPID --port $PORT > "$HERE/$ARM.gpu.csv" &
WPID=$!
# abort monitor: 3 consecutive rows junction>104 or mem>105, or vram_free<300
( bad=0; while kill -0 $SPID 2>/dev/null; do
    sleep 2; row=$(tail -1 "$HERE/$ARM.gpu.csv")
    IFS=, read -r _ _ j m _ _ _ vf _ <<<"$row"
    if [[ "$j" =~ ^[0-9.]+$ ]] && { awk "BEGIN{exit !($j>104 || $m>105)}"; }; then bad=$((bad+1)); else bad=0; fi
    if [ $bad -ge 3 ] || { [[ "$vf" =~ ^[0-9]+$ ]] && [ "$vf" -lt 300 ] && grep -q "listening on" "$LOG"; }; then
      echo "ABORT: thermal/VRAM limit row=$row"; kill $SPID; fi
  done ) &
until grep -q "listening on" "$LOG"; do kill -0 $SPID 2>/dev/null || { echo "server died"; tail -20 "$LOG"; exit 1; }; sleep 2; done
python3 "$HERE/run_arm.py" "$ARM" $PORT "$LOG" $SPID; RC=$?
kill $SPID; wait $SPID 2>/dev/null; sleep 3
echo "run_arm rc=$RC; server $SPID stopped; llama-server now: [$(pgrep -x llama-server | tr '\n' ' ')]"
