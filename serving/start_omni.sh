#!/usr/bin/env bash
# Start Qwen2.5-Omni-7B on one physical GPU.
#
#   bash serving/start_omni.sh 2
#
# With no argument, the card comes from OMNI_GPU in serving/config.env.
# CUDA_VISIBLE_DEVICES makes that card logical device 0, so the three Omni
# stages must keep devices "0". Their memory fractions are 0.45 / 0.25 / 0.12.
# A single global utilization cannot place thinker, talker, and token2wav together.
# ZMQ IPC paths must stay under 107 characters, so the temp dir is /keyan/omni-tmp
# rather than the longer project cache path.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
GPU="${1:-$OMNI_GPU}"
BIN="$PROJECT_ROOT/.runtime/serving-venv/bin/vllm"
OMNI_TMP=/keyan/omni-tmp

[[ "$GPU" =~ ^[0-9]+$ ]] || { echo "GPU must be a card index, got: $GPU" >&2; exit 1; }
[[ -x "$BIN" ]] || { echo 'Missing serving runtime: run serving/install_runtime.sh' >&2; exit 1; }
[[ -s "$OMNI_MODEL_PATH/model.safetensors.index.json" ]] || { echo 'Missing Qwen2.5-Omni weights: run serving/download_omni.sh' >&2; exit 1; }

if curl -fsS --max-time 2 "http://127.0.0.1:${OMNI_PORT}/health" >/dev/null 2>&1; then
  echo "Qwen2.5-Omni already healthy at http://127.0.0.1:${OMNI_PORT}/v1"
  exit 0
fi
if [[ -n "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader -i "$GPU" | head -1)" ]]; then
  echo "GPU ${GPU} already has a compute process. Not starting another server." >&2
  exit 1
fi

mkdir -p "$HERE/logs" "$OMNI_TMP"
# shellcheck disable=SC1091
source "$HERE/off_overlay_env.sh"
off_overlay_cache_root
export TMPDIR="$OMNI_TMP"
export TMP="$OMNI_TMP"
export TEMP="$OMNI_TMP"
export CUDA_VISIBLE_DEVICES="$GPU"
export PYTHONUNBUFFERED=1

LOG="$HERE/logs/omni_gpu${GPU}.log"
nohup "$BIN" serve "$OMNI_MODEL_PATH" --omni \
  --host 127.0.0.1 --port "$OMNI_PORT" \
  --served-model-name "$OMNI_MODEL_NAME" \
  --max-model-len 16384 \
  --stage-overrides '{"0":{"devices":"0","gpu_memory_utilization":0.45},"1":{"devices":"0","gpu_memory_utilization":0.25},"2":{"devices":"0","gpu_memory_utilization":0.12}}' \
  > "$LOG" 2>&1 < /dev/null &
echo $! > "$HERE/logs/omni_gpu${GPU}.pid"
echo "Started ${OMNI_MODEL_NAME} on GPU ${GPU}, PID $(cat "$HERE/logs/omni_gpu${GPU}.pid")"
echo "Endpoint: http://127.0.0.1:${OMNI_PORT}/v1"
echo "Log: $LOG"
