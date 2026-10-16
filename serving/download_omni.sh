#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.env"
VENV="$HERE/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  /usr/bin/python3.12 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip -q install 'huggingface_hub[hf_xet]>=0.34,<2'
"$VENV/bin/python" - "$OMNI_MODEL_PATH" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Qwen/Qwen2.5-Omni-7B',
    revision='ae9e1690543ffd5c0221dc27f79834d0294cba00',
    local_dir=sys.argv[1],
    max_workers=4,
)
PY
"$VENV/bin/python" - "$OMNI_MODEL_PATH" <<'PY'
import json, sys
from pathlib import Path
p=Path(sys.argv[1]); index=json.loads((p/'model.safetensors.index.json').read_text())
shards=set(index['weight_map'].values())
missing=[name for name in shards if not (p/name).is_file() or (p/name).stat().st_size<1024]
if missing: raise SystemExit(f'Incomplete weights: {missing}')
print(f'Download verified: {len(shards)} weight shards, {sum((p/name).stat().st_size for name in shards)/1024**3:.2f} GiB')
PY
