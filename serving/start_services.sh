#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
mkdir -p "$HERE/logs"
for spec in vision omni; do
  if [[ "$spec" == vision ]]; then port="$VISION_PORT"; else port="$OMNI_PORT"; fi
  if curl -fsS --max-time 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    echo "$spec already healthy at 127.0.0.1:$port"
    continue
  fi
  nohup "$HERE/start_${spec}.sh" > "$HERE/logs/${spec}.log" 2>&1 < /dev/null &
  echo $! > "$HERE/logs/${spec}.pid"
  echo "Started $spec, PID $(cat "$HERE/logs/${spec}.pid"), log $HERE/logs/${spec}.log"
done
