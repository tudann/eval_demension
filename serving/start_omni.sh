#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
BIN="$PROJECT_ROOT/.runtime/serving-venv/bin/vllm"
[[ -x "$BIN" ]] || { echo 'Missing serving runtime: run serving/install_runtime.sh' >&2; exit 1; }
[[ -s "$OMNI_MODEL_PATH/model.safetensors.index.json" ]] || { echo 'Missing Qwen2.5-Omni weights: run serving/download_omni.sh' >&2; exit 1; }
export CUDA_VISIBLE_DEVICES="$OMNI_GPU"
exec "$BIN" serve "$OMNI_MODEL_PATH" --omni \
  --host 127.0.0.1 --port "$OMNI_PORT" \
  --served-model-name "$OMNI_MODEL_NAME" \
  --gpu-memory-utilization "$OMNI_GPU_MEMORY_UTILIZATION" \
  --max-model-len 16384
