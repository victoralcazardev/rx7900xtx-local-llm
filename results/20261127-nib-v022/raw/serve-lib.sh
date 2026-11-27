#!/usr/bin/env bash
# Sourced by the run scripts: start one nib server and retry a start that dies.
# The bdc9307 build intermittently segfaults while initializing the DSpark drafter or a HIP graph
# (right after "[InklingEngine] Ready!"): 3 of 9 serve starts in this run and 2 of 10 in the retest,
# 0/15 for 2e16cf0 (raw/startup-crashes.txt). A failed start is recorded there and retried up to 4
# times; the harness never silently skips an arm.
# Sets NIB_PID; returns 1 if every attempt died.
# usage: start_nib <tag> <log-file> <command...>

start_nib() {
  local tag=$1 log=$2 i j pid ok rc
  shift 2
  for i in 1 2 3 4; do
    "$@" > "$log" 2>&1 &
    pid=$!
    ok=no
    for j in $(seq 1 120); do
      curl -sf -m 1 127.0.0.1:4444/v1/models >/dev/null && { ok=yes; break; }
      kill -0 "$pid" 2>/dev/null || break
      sleep 2
    done
    if [ "$ok" = yes ]; then
      NIB_PID=$pid
      echo "[serve] $tag: up on attempt $i (pid $pid)" >&2
      return 0
    fi
    kill -9 "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    rc=$?
    echo "[serve] $tag: attempt $i failed (exit $rc): $(tail -1 "$log")" >&2
    printf '%s %s attempt %s exit %s last_line: %s\n' "$(date -Is)" "$tag" "$i" "$rc" \
      "$(tail -1 "$log")" >> "$CRASH_LOG"
    sleep 3
  done
  return 1
}
