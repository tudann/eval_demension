#!/usr/bin/env bash
# Start Qwen3-VL-32B-Instruct-FP8 on the configured GPU with the machine SGLang.
# Uses /opt/sglang, not the project vLLM virtualenv. Radix cache is disabled
# because this SGLang build crashes during prefill when it is left on.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
BIN=/opt/sglang/bin/python
[[ -x "$BIN" ]] || { echo "Missing SGLang runtime: $BIN" >&2; exit 1; }
[[ -s "$VISION_MODEL_PATH/model.safetensors.index.json" ]] || { echo "Missing Qwen3-VL weights: $VISION_MODEL_PATH" >&2; exit 1; }

if curl -fsS --max-time 2 "http://127.0.0.1:${VISION_PORT}/health" >/dev/null 2>&1; then
  echo "Qwen3-VL already healthy at http://127.0.0.1:${VISION_PORT}/v1"
  exit 0
fi
if [[ -n "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader -i "$VISION_GPU" | head -1)" ]]; then
  echo "GPU ${VISION_GPU} already has a compute process. Not starting another server." >&2
  exit 1
fi

mkdir -p "$HERE/logs"
export CUDA_VISIBLE_DEVICES="$VISION_GPU"
export PYTHONUNBUFFERED=1
nohup "$BIN" -u -m sglang.launch_server \
  --model-path "$VISION_MODEL_PATH" \
  --served-model-name "$VISION_MODEL_NAME" \
  --host 127.0.0.1 \
  --port "$VISION_PORT" \
  --tp-size 1 \
  --mem-fraction-static 0.85 \
  --context-length 32768 \
  --disable-radix-cache \
  > "$HERE/logs/qwen3_vl.log" 2>&1 < /dev/null &
echo $! > "$HERE/logs/qwen3_vl.pid"
echo "Started ${VISION_MODEL_NAME} on GPU ${VISION_GPU}, PID $(cat "$HERE/logs/qwen3_vl.pid")"
echo "Endpoint: http://127.0.0.1:${VISION_PORT}/v1"
echo "Log: $HERE/logs/qwen3_vl.log"
