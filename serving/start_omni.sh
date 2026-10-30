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

# Stage overrides below use these fractions of the *full* card (vLLM does not
# scale to free memory). Keep in sync with --stage-overrides.
STAGE0_UTIL=0.45
STAGE1_UTIL=0.25
STAGE2_UTIL=0.12
# Extra headroom MiB on top of the three stages.
OMNI_MEM_SLACK_MIB="${OMNI_MEM_SLACK_MIB:-2048}"

if curl -fsS --max-time 2 "http://127.0.0.1:${OMNI_PORT}/health" >/dev/null 2>&1; then
  echo "Qwen2.5-Omni already healthy at http://127.0.0.1:${OMNI_PORT}/v1"
  exit 0
fi

TOTAL_MIB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits -i "$GPU" | tr -d ' ')"
FREE_MIB="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$GPU" | tr -d ' ')"
NEED_MIB="$(awk -v t="$TOTAL_MIB" -v a="$STAGE0_UTIL" -v b="$STAGE1_UTIL" -v c="$STAGE2_UTIL" -v s="$OMNI_MEM_SLACK_MIB" \
  'BEGIN { printf "%d", t * (a + b + c) + s }')"
EXISTING_APPS="$(nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader -i "$GPU" || true)"

if [[ -n "$EXISTING_APPS" ]]; then
  echo "GPU ${GPU} already has compute process(es); co-residing if free VRAM is enough:"
  echo "$EXISTING_APPS" | sed 's/^/  /'
fi
echo "GPU ${GPU} memory: free ${FREE_MIB} MiB / total ${TOTAL_MIB} MiB; Omni needs ~${NEED_MIB} MiB (stages ${STAGE0_UTIL}+${STAGE1_UTIL}+${STAGE2_UTIL} + ${OMNI_MEM_SLACK_MIB} MiB slack)"

if [[ "$FREE_MIB" -lt "$NEED_MIB" ]]; then
  echo "GPU ${GPU} free VRAM ${FREE_MIB} MiB < required ${NEED_MIB} MiB. Not starting." >&2
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
# Single-GPU serve; avoid IB/P2P waits when sharing a busy node.
export NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE:-1}"
export NCCL_IB_DISABLE="${NCCL_IB_DISABLE:-1}"

LOG="$HERE/logs/omni_gpu${GPU}.log"
: > "$LOG"
nohup "$BIN" serve "$OMNI_MODEL_PATH" --omni \
  --host 127.0.0.1 --port "$OMNI_PORT" \
  --served-model-name "$OMNI_MODEL_NAME" \
  --max-model-len 16384 \
  --init-timeout 6000 \
  --stage-init-timeout 1800 \
  --stage-overrides "{\"0\":{\"devices\":\"0\",\"enforce_eager\":true,\"gpu_memory_utilization\":${STAGE0_UTIL}},\"1\":{\"devices\":\"0\",\"enforce_eager\":true,\"gpu_memory_utilization\":${STAGE1_UTIL}},\"2\":{\"devices\":\"0\",\"enforce_eager\":true,\"gpu_memory_utilization\":${STAGE2_UTIL}}}" \
  > "$LOG" 2>&1 < /dev/null &
echo $! > "$HERE/logs/omni_gpu${GPU}.pid"
echo "Started ${OMNI_MODEL_NAME} on GPU ${GPU}, PID $(cat "$HERE/logs/omni_gpu${GPU}.pid")"
echo "Endpoint: http://127.0.0.1:${OMNI_PORT}/v1"
echo "Log: $LOG"
