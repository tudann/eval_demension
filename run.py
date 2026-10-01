from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from v_eval.core import ConfigError, discover_cases, evaluate_case, prepare_case


ROOT = Path(__file__).resolve().parent
DEFAULT_DIMS = ROOT / "configs" / "dims_13_18.yaml"


def resolve_task_paths(task: dict[str, Any], config_path: Path) -> dict[str, Any]:
    """Resolve relative input and output paths from the task file directory."""
    base = config_path.resolve().parent.parent
    input_configs: list[dict[str, Any]] = []
    if isinstance(task.get("input"), dict):
        input_configs.append(task["input"])
    if isinstance(task.get("inputs"), list):
        input_configs.extend(item for item in task["inputs"] if isinstance(item, dict))
    for input_cfg in input_configs:
        value = input_cfg.get("root")
        if isinstance(value, str) and value and not Path(value).is_absolute():
            input_cfg["root"] = str((base / value).resolve())
    output = task.get("output_dir")
    if isinstance(output, str) and output and not Path(output).is_absolute():
        task["output_dir"] = str((base / output).resolve())
    return task


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file not found: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"configuration must be a YAML mapping: {path}")
    return data


def validate_task(task: dict[str, Any], dims: dict[str, Any]) -> None:
    dimension = task.get("dimension")
    if dimension not in dims.get("dimensions", {}):
        raise ConfigError(f"unknown dimension: {dimension}")
    has_input = isinstance(task.get("input"), dict) and bool(task["input"].get("root"))
    has_inputs = isinstance(task.get("inputs"), list) and bool(task["inputs"])
    if has_input == has_inputs:
        raise ConfigError("configure exactly one of input or inputs")
    if has_inputs:
        allowed_modes = {"t2va", "f2va", "l2va", "fl2va", "r2va"}
        input_ids: set[str] = set()
        for index, input_cfg in enumerate(task["inputs"]):
            if not isinstance(input_cfg, dict):
                raise ConfigError(f"inputs[{index}] must be a YAML mapping")
            if not input_cfg.get("root"):
                raise ConfigError(f"inputs[{index}].root is required")
            mode = str(input_cfg.get("mode", "")).lower()
            if mode not in allowed_modes:
                raise ConfigError(f"unsupported inputs[{index}].mode: {mode}")
            input_id = str(input_cfg.get("id") or mode)
            if not input_id or input_id in input_ids:
                raise ConfigError(f"duplicate inputs id: {input_id}")
            input_ids.add(input_id)
    stages = task.get("stages", ["check", "checklist", "evaluate", "score"])
    unknown = sorted(set(stages) - {"check", "checklist", "evaluate", "score"})
    if unknown:
        raise ConfigError(f"unknown stages: {', '.join(unknown)}")
    dimension_cfg = dims["dimensions"][dimension]
    overrides = (task.get("evaluation") or {}).get("subpoints", {}) or {}
    for subpoint, override in overrides.items():
        if subpoint not in dimension_cfg.get("subpoints", {}):
            raise ConfigError(f"unknown subpoint override: {subpoint}")
        configured = dimension_cfg["subpoints"][subpoint].get("components", {})
        for component, enabled in (override.get("components", {}) or {}).items():
            if component not in configured:
                raise ConfigError(f"unknown component override: {subpoint}.{component}")
            if not isinstance(enabled, bool):
                raise ConfigError(f"component switch must be boolean: {subpoint}.{component}")


def output_base(task: dict[str, Any]) -> Path:
    return Path(task.get("output_dir", "outputs")) / "runs" / str(task.get("run_name", "local"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_check(task: dict[str, Any]) -> list[Any]:
    cases = discover_cases(task)
    with_video = sum(case.video_path is not None for case in cases)
    judge_status = {
        "vision": bool(os.getenv("V_EVAL_VISION_JUDGE_URL") or os.getenv("V_EVAL_JUDGE_URL")),
        "audio": bool(os.getenv("V_EVAL_AUDIO_JUDGE_URL") or os.getenv("V_EVAL_JUDGE_URL")),
    }
    modes = sorted({case.mode for case in cases})
    mode_counts = {mode: sum(case.mode == mode for case in cases) for mode in modes}
    print(f"check: dimension={task['dimension']} cases={len(cases)} with_video={with_video} "
          f"modes={mode_counts} "
          f"vision_judge={'online' if judge_status['vision'] else 'offline'} "
          f"audio_judge={'online' if judge_status['audio'] else 'offline'}")
    return cases


def run_checklist(task: dict[str, Any], dims: dict[str, Any], cases: list[Any], force: bool) -> None:
    # The checklist stage freezes facts and items without producing a score.
    dimension_cfg = dims["dimensions"][task["dimension"]]
    for case in cases:
        prepare_case(task, dimension_cfg, case)
    print(f"checklist: prepared {len(cases)} case records")


def run_evaluate(task: dict[str, Any], dims: dict[str, Any], cases: list[Any], force: bool) -> list[dict[str, Any]]:
    dimension_cfg = dims["dimensions"][task["dimension"]]
    results = [evaluate_case(task, dimension_cfg, case, dims["scoring"], force=force) for case in cases]
    print(f"evaluate: wrote {len(results)} case results")
    return results


def run_score(task: dict[str, Any], cases: list[Any] | None = None) -> dict[str, Any]:
    base = output_base(task)
    dimension = str(task["dimension"])
    case_ids = [case.output_id for case in cases] if cases is not None else []
    results: list[dict[str, Any]] = []
    if case_ids:
        result_paths = [base / dimension / case_id / "result.json" for case_id in case_ids]
    else:
        result_paths = sorted((base / dimension).glob("**/result.json")) if (base / dimension).is_dir() else []
    for path in result_paths:
        if path.is_file():
            results.append(json.loads(path.read_text(encoding="utf-8")))
    scored = [row for row in results if row.get("score") is not None]
    scores = [float(row["score"]) for row in scored]
    per_mode: dict[str, dict[str, Any]] = {}
    for mode in sorted({str((row.get("case") or {}).get("mode", "unknown")) for row in results}):
        mode_rows = [row for row in results if str((row.get("case") or {}).get("mode", "unknown")) == mode]
        mode_scores = [float(row["score"]) for row in mode_rows if row.get("score") is not None]
        per_mode[mode] = {
            "n": len(mode_rows),
            "scored": len(mode_scores),
            "skipped": sum(row.get("score") is None for row in mode_rows),
            "gate_failed": sum(row.get("status") == "gate_failed" for row in mode_rows),
            "mean_score": round(sum(mode_scores) / len(mode_scores), 3) if mode_scores else None,
        }
    summary = {
        "dimension": dimension,
        "run_name": task.get("run_name", "local"),
        "n": len(results),
        "scored": len(scored),
        "skipped": sum(row.get("score") is None for row in results),
        "gate_failed": sum(row.get("status") == "gate_failed" for row in results),
        "mean_score": round(sum(scores) / len(scores), 3) if scores else None,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "per_mode": per_mode,
    }
    write_json(base / "summary.json", summary)
    (base / "per_case.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results), encoding="utf-8")
    mode_lines = "".join(
        f"- {mode}: {row['scored']}/{row['n']} scored, mean {row['mean_score']} / 5\n"
        for mode, row in per_mode.items()
    )
    (base / "summary.md").write_text(
        f"# {dimension}\n\n- Cases: {summary['n']}\n- Scored: {summary['scored']}\n- Gate failed: {summary['gate_failed']}\n- Mean score: {summary['mean_score']} / 5\n\n## By input mode\n\n{mode_lines}",
        encoding="utf-8",
    )
    print(f"score: mean={summary['mean_score']} scored={summary['scored']} gate_failed={summary['gate_failed']}")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local D13-D18 video evaluation workflow")
    parser.add_argument("--task-config", "--config", required=True, type=Path)
    parser.add_argument("--dims-config", type=Path, default=DEFAULT_DIMS)
    parser.add_argument("--stages", nargs="+", choices=["check", "checklist", "evaluate", "score"])
    parser.add_argument("--force", action="store_true", help="ignore existing case result caches")
    args = parser.parse_args(argv)
    try:
        task = resolve_task_paths(load_yaml(args.task_config), args.task_config)
        dims = load_yaml(args.dims_config)
        validate_task(task, dims)
        stages = args.stages or task.get("stages", ["check", "checklist", "evaluate", "score"])
        cases = run_check(task) if "check" in stages else discover_cases(task)
        if "checklist" in stages:
            run_checklist(task, dims, cases, args.force)
        if "evaluate" in stages:
            run_evaluate(task, dims, cases, args.force)
        if "score" in stages:
            run_score(task, cases)
        return 0
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
