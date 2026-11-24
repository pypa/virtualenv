#!/usr/bin/env bash
set -euo pipefail

diagnostics=.tox/hang-diagnostics
sample_tree() {
  local pid=$1 child
  while read -r child; do
    sample_tree "$child"
  done < <(pgrep -P "$pid")
  sample "$pid" 1 -file "$diagnostics/native-$pid.txt" || true
}

"$@" &
suite=$!
(
  while kill -0 "$suite" 2>/dev/null; do
    sleep 10
    for log in "$diagnostics"/controller-*.log; do
      [[ -f "$log" ]] || continue
      if awk '/ DUMP$/ || / TEST / { stalled=0 } /subprocess\.py.* in _execute_child/ { stalled=1 }
              END { exit !stalled }' "$log"; then
        ps -axo pid,ppid,stat,comm > "$diagnostics/processes.txt"
        sample_tree "$suite"
        exit
      fi
    done
  done
) &
monitor=$!
trap 'kill "$monitor" 2>/dev/null || true' EXIT
wait "$suite"
