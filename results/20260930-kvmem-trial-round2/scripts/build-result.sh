#!/usr/bin/env bash
# Check the background build's actual wait status and reject a missing output binary.
check_build_result() {
  local pid=$1 binary=$2 build_status
  if wait "$pid"; then
    build_status=0
  else
    build_status=$?
  fi

  printf 'BUILD_EXIT=%s\n' "$build_status"
  if (( build_status != 0 )); then
    printf 'BUILD_FAILED: background build exited with status %s\n' "$build_status" >&2
    return "$build_status"
  fi
  if [[ ! -x "$binary" ]]; then
    printf 'NO_NEW_BINARY: expected executable was not produced: %s\n' "$binary" >&2
    return 1
  fi
}
