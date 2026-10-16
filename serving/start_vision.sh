#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
BIN="$PROJECT_ROOT/.runtime/serving-venv/bin/vllm"
[[ -x "$BIN" ]] || { echo 'Missing serving runtime: run serving/install_runtime.sh' >&2; exit 1; }
[[ -s "$VISION_MODEL_PATH/model.safetensors.index.json" ]] || { echo 'Missing Qwen3-VL weights' >&2; exit 1; }
[[ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader -i "$VISION_GPU" | head -1)" ]] || echo 'GPU has running processes; check free VRAM before starting.' >&2
# shellcheck disable=SC1091
source "$HERE/off_overlay_env.sh"
off_overlay_cache_root
export CUDA_VISIBLE_DEVICES="$VISION_GPU"
exec "$BIN" serve "$VISION_MODEL_PATH" \
  --host 127.0.0.1 --port "$VISION_PORT" \
  --served-model-name "$VISION_MODEL_NAME" \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization "$VISION_GPU_MEMORY_UTILIZATION" \
  --max-model-len 16384
