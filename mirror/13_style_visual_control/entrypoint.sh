#!/bin/bash
set -euo pipefail
cd /opt/d13-eval
if [[ -z "${V_EVAL_CHECKLIST_URL:-}" || -z "${V_EVAL_VISION_JUDGE_URL:-}" ]]; then
  echo "Set V_EVAL_CHECKLIST_URL and V_EVAL_VISION_JUDGE_URL to the vision judge, for example http://127.0.0.1:8013/v1" >&2
  exit 2
fi
exec /opt/d13-eval/.venv/bin/python run.py "$@"
