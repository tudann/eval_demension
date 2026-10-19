#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
IMAGE="d13-style-eval:13"

if [[ -z "${D13_DATA:-}" || -z "${D13_OUTPUT:-}" ]]; then
  echo "Usage: D13_DATA=/path/to/13_style_visual_control D13_OUTPUT=/path/to/outputs $0 [--force]" >&2
  echo "D13_DATA must contain t2va, f2va, fl2va, and r2va. The vision judge must already be running." >&2
  exit 2
fi

docker load -i "$HERE/d13-style-eval.tar"
exec docker run --rm --network host --gpus '"device=0"' \
  -e "V_EVAL_CHECKLIST_URL=${V_EVAL_CHECKLIST_URL:-http://127.0.0.1:8013/v1}" \
  -e "V_EVAL_VISION_JUDGE_URL=${V_EVAL_VISION_JUDGE_URL:-http://127.0.0.1:8013/v1}" \
  -e "V_EVAL_CHECKLIST_MODEL=${V_EVAL_CHECKLIST_MODEL:-Qwen3-VL-32B-Instruct-FP8}" \
  -e "V_EVAL_VISION_JUDGE_MODEL=${V_EVAL_VISION_JUDGE_MODEL:-Qwen3-VL-32B-Instruct-FP8}" \
  -e "V_EVAL_CLIP_DEVICE=${V_EVAL_CLIP_DEVICE:-cuda:0}" \
  -v "$D13_DATA:/data:ro" \
  -v "$D13_OUTPUT:/outputs" \
  "$IMAGE" "$@"
