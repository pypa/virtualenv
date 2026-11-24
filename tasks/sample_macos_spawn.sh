#!/usr/bin/env bash
set -euo pipefail

diagnostics=.tox/hang-diagnostics
mkdir -p "$diagnostics"
sample_tree() {
  local pid=$1 child
  while read -r child; do
    sample_tree "$child"
  done < <(pgrep -P "$pid")
  sample "$pid" 1 -file "$diagnostics/native-$pid.txt" || true
}

(
  while kill -0 "$$" 2>/dev/null; do
    sleep 10
    for log in "$diagnostics"/controller-*.log; do
      [[ -f "$log" ]] || continue
      if awk '/ DUMP$/ || / TEST / { stalled=0 } /subprocess\.py.* in _execute_child/ { stalled=1 }
              END { exit !stalled }' "$log"; then
        ps -axo pid,ppid,stat,comm > "$diagnostics/processes.txt"
        pid=${log##*/controller-}
        sample_tree "${pid%.log}"
        exit
      fi
    done
  done
) > "$diagnostics/sampler.log" 2>&1 &
monitor=$!
trap 'kill "$monitor" 2>/dev/null || true' EXIT
"$@"
