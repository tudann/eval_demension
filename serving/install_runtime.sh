#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.runtime/serving-venv"
/usr/bin/python3.12 -m venv "$VENV"
export PIP_CACHE_DIR="$ROOT/.runtime/pip-cache"
export TMPDIR="$ROOT/.runtime/tmp"
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"
"$VENV/bin/python" -m pip install 'vllm==0.30.0' 'vllm-omni==0.30.0'
"$VENV/bin/python" -m pip check
"$VENV/bin/python" -m pip freeze > "$ROOT/.runtime/serving-requirements.lock.txt"
"$VENV/bin/vllm" --version
