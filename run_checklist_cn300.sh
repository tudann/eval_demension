#!/usr/bin/env bash
# Run the checklist stage for the Chinese 300-case D13–D18 set.
# Six dimensions run at the same time. Cases inside one dimension stay serial.
# Already valid checklist.json files are reused unless --force is passed.

set -u
export PYTHONUNBUFFERED=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

FORCE=()
if [[ "${1:-}" == "--force" ]]; then
  FORCE=(--force)
elif [[ -n "${1:-}" ]]; then
  echo "用法: $0 [--force]" >&2
  exit 2
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

missing=()
for name in V_EVAL_CHECKLIST_URL V_EVAL_CHECKLIST_MODEL V_EVAL_CHECKLIST_API_KEY; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
done
if ((${#missing[@]})); then
  echo "缺少出题接口环境变量: ${missing[*]}" >&2
  echo "请在 .env 中填写，或在运行前 export。" >&2
  exit 2
fi

mkdir -p outputs/logs
echo "出题模型: ${V_EVAL_CHECKLIST_MODEL}"
echo "日志目录: ${ROOT}/outputs/logs"

pids=()
dims=()
for n in 13 14 15 16 17 18; do
  log="outputs/logs/cn300_d${n}_checklist.log"
  echo "启动第 ${n} 维，日志 ${log}"
  .venv/bin/python run.py \
    --task-config "configs/task_d${n}_cn300.yaml" \
    --stages checklist \
    "${FORCE[@]}" \
    >"$log" 2>&1 &
  pids+=("$!")
  dims+=("$n")
done

failed=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    echo "第 ${dims[$i]} 维完成"
  else
    status=$?
    echo "第 ${dims[$i]} 维退出码 ${status}，查看 outputs/logs/cn300_d${dims[$i]}_checklist.log" >&2
    failed=1
  fi
done

echo "清单目录: outputs/d13 至 outputs/d18 下的 runs/cn300_dNN/"
exit "$failed"
