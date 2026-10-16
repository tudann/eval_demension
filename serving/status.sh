#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
for spec in vision omni; do
  if [[ "$spec" == vision ]]; then port="$VISION_PORT"; else port="$OMNI_PORT"; fi
  if curl -fsS --max-time 5 "http://127.0.0.1:$port/health" >/dev/null; then echo "$spec: healthy at 127.0.0.1:$port"; else echo "$spec: unavailable at 127.0.0.1:$port"; fi
done
nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv
