#!/usr/bin/env python3
"""Build per-dimension task files from configs/compare_run.yaml and run them.

The regression task files stay on prompt_final.txt and video.mp4. This runner
only changes the prompt file, the video file, and the output directory.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPARE_CONFIG = ROOT / "configs" / "compare_run.yaml"
RUN_PY = ROOT / "run.py"
PYTHON = ROOT / ".venv" / "bin" / "python"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"configuration must be a YAML mapping: {path}")
    return data


def safe_stem(filename: str) -> str:
    stem = Path(filename).stem.strip()
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in stem)
    if not cleaned:
        raise SystemExit(f"cannot derive an output name from {filename}")
    return cleaned


def selected_cases(mode_root: Path, prompt_name: str, video_name: str, case_ids: set[str]) -> tuple[list[str], list[str]]:
    if not mode_root.is_dir():
        return [], []
    ready: list[str] = []
    missing_video: list[str] = []
    for case_dir in sorted(path for path in mode_root.iterdir() if path.is_dir()):
        if case_ids and case_dir.name not in case_ids:
            continue
        if not (case_dir / prompt_name).is_file():
            continue
        if (case_dir / video_name).is_file():
            ready.append(case_dir.name)
        else:
            missing_video.append(case_dir.name)
    return ready, missing_video


def build_task(template: dict[str, Any], dimension_number: int, prompt_name: str, video_name: str, case_ids: set[str], output_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    inputs = []
    skipped: list[str] = []
    for item in template.get("inputs", []):
        root = (ROOT / str(item["root"])).resolve()
        ready, missing_video = selected_cases(root, prompt_name, video_name, case_ids)
        skipped.extend(f"{item['id']}/{case_id}" for case_id in missing_video)
        if not ready:
            continue
        updated = dict(item)
        updated["root"] = str(root)
        updated["prompt_filename"] = prompt_name
        updated["video_filename"] = video_name
        updated["case_ids"] = ready
        inputs.append(updated)
    if not inputs:
        return None, skipped
    stem = safe_stem(video_name)
    task = dict(template)
    task["task_name"] = f"compare_{stem}_d{dimension_number}"
    task["run_name"] = f"compare_{stem}_d{dimension_number}"
    task["inputs"] = inputs
    task["stages"] = ["check", "checklist", "evaluate", "score"]
    task["output_dir"] = str(output_dir)
    return task, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a prompt/video comparison from configs/compare_run.yaml")
    parser.add_argument("--dry-run", action="store_true", help="write task files and print the plan without scoring")
    args = parser.parse_args(argv)

    compare = load_yaml(COMPARE_CONFIG)
    prompt_name = str(compare.get("prompt_filename") or "").strip()
    video_name = str(compare.get("video_filename") or "").strip()
    if not prompt_name or not video_name:
        raise SystemExit("compare_run.yaml needs prompt_filename and video_filename")
    dimensions = [int(item) for item in compare.get("dimensions") or []]
    if not dimensions:
        raise SystemExit("compare_run.yaml needs at least one dimension")
    case_ids = {str(item) for item in compare.get("case_ids") or []}
    force = bool(compare.get("force", False))
    run_root = ROOT / "outputs" / "compare" / safe_stem(video_name) / safe_stem(prompt_name)
    print(f"prompt: {prompt_name}")
    print(f"video: {video_name}")
    print(f"dimensions: {', '.join(str(item) for item in dimensions)}")
    print(f"output: {run_root}")
    if case_ids:
        print(f"case_ids: {', '.join(sorted(case_ids))}")

    planned: list[tuple[int, Path]] = []
    for number in dimensions:
        template_path = ROOT / "configs" / f"task_d{number}_regression.yaml"
        if not template_path.is_file():
            raise SystemExit(f"no regression config for dimension {number}: {template_path}")
        template = load_yaml(template_path)
        output_dir = run_root / f"d{number}"
        task, skipped = build_task(template, number, prompt_name, video_name, case_ids, output_dir)
        if skipped:
            print(f"d{number}: skip {len(skipped)} case(s) without {video_name}: {', '.join(skipped)}")
        if task is None:
            print(f"d{number}: no cases have both {prompt_name} and {video_name}; skip this dimension")
            continue
        count = sum(len(item["case_ids"]) for item in task["inputs"])
        task_path = run_root / f"task_d{number}.yaml"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text(yaml.safe_dump(task, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"d{number}: {count} cases -> {output_dir}")
        planned.append((number, task_path))

    if not planned:
        raise SystemExit("no dimension has a runnable case")
    if args.dry_run:
        print("dry-run: task files written, scoring not started")
        return 0

    runner = PYTHON if PYTHON.is_file() else Path(sys.executable)
    for number, task_path in planned:
        command = [str(runner), str(RUN_PY), "--task-config", str(task_path)]
        if force:
            command.append("--force")
        print(f"run d{number}: {' '.join(command)}", flush=True)
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
