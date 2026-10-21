#!/usr/bin/env bash
# Read configs/compare_run.yaml and score the selected dimensions.
# Edit that file, then run this script. It does not use video.mp4 or prompt_final.txt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a
# shellcheck disable=SC1091
source .env
set +a
exec .venv/bin/python scripts/run_compare.py "$@"
