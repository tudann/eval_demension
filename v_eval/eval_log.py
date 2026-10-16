from __future__ import annotations

import json
import shutil
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


_LOG_DIR: ContextVar[Path | None] = ContextVar("v_eval_case_log_dir", default=None)


def bind_case_log(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "frames").mkdir(parents=True, exist_ok=True)
    return _LOG_DIR.set(path)


def unbind_case_log(token) -> None:
    _LOG_DIR.reset(token)


def case_log_dir() -> Path | None:
    return _LOG_DIR.get()


@contextmanager
def wait_log(stage: str, message: str, *, interval: float = 15.0, **fields: Any) -> Iterator[None]:
    """Log the start, a heartbeat, and the end of a step that can run for minutes."""
    log_event(stage, f"开始：{message}", **fields)
    stop = threading.Event()
    started = time.monotonic()

    def beat() -> None:
        while not stop.wait(interval):
            log_event(stage, f"仍在进行：{message}", elapsed_seconds=int(time.monotonic() - started))

    thread = threading.Thread(target=beat, name=f"v-eval-wait-{stage}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1)
        log_event(stage, f"完成：{message}", elapsed_seconds=round(time.monotonic() - started, 1))


def log_event(stage: str, message: str, **fields: Any) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    extra = ""
    if fields:
        extra = " " + json.dumps(fields, ensure_ascii=False, default=str)
    line = f"[{stamp}] [{stage}] {message}{extra}"
    print(line, flush=True)
    directory = _LOG_DIR.get()
    if directory is None:
        return
    with (directory / "eval.log").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_stage_report(case_id: str, checklist: dict[str, Any], answers: dict[str, Any] | None, result: dict[str, Any] | None) -> None:
    """Write a readable per-case report of checklist, judge, numeric, and blended scores."""
    directory = _LOG_DIR.get()
    if directory is None:
        return
    lines = [f"# {case_id}", ""]
    facts = checklist.get("facts") or {}
    lines.append("## 出题")
    lines.append("")
    lines.append("事实：")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(facts, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("门槛：")
    lines.append("")
    for gate in checklist.get("gates") or []:
        if isinstance(gate, dict):
            lines.append(f"- {gate.get('id')}: {gate.get('question')}（期望 {gate.get('expect', 'yes')}）")
    lines.append("")
    lines.append("检查题：")
    lines.append("")
    for item in checklist.get("items") or []:
        if isinstance(item, dict):
            core = "核心" if item.get("core") else "非核心"
            lines.append(f"- {item.get('id')} [{item.get('subpoint')}] {core}: {item.get('question')}")
    lines.append("")
    lines.append("## 抽帧")
    lines.append("")
    frame_dir = directory / "frames"
    manifests = sorted(frame_dir.glob("*.json")) if frame_dir.is_dir() else []
    if not manifests:
        lines.append("本次还没有保存关键帧。")
    for manifest in manifests:
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        lines.append(f"### {manifest.stem}")
        lines.append("")
        for row in saved:
            lines.append(f"- t={row['timestamp']}s `{row['path']}`")
        lines.append("")
    if answers:
        lines.append("## 裁判作答")
        lines.append("")
        lines.append(f"- 状态: {answers.get('status')}")
        if answers.get("error"):
            lines.append(f"- 错误: {answers.get('error')}")
        lines.append(f"- 模型: {answers.get('model')}")
        lines.append("")
        lines.append("门槛作答：")
        lines.append("")
        for gate in answers.get("gates") or []:
            if isinstance(gate, dict):
                lines.append(f"- {gate.get('id')}: {gate.get('answer')}；回答依据：{gate.get('回答依据') or ''}")
        lines.append("")
        lines.append("检查题作答：")
        lines.append("")
        for row in answers.get("answers") or []:
            if isinstance(row, dict):
                lines.append(f"- {row.get('id')}: {row.get('score', row.get('answer'))}；回答依据：{row.get('回答依据') or ''}")
        lines.append("")
    if result:
        lines.append("## 子项合成")
        lines.append("")
        for name, row in (result.get("subpoints") or {}).items():
            if not isinstance(row, dict):
                continue
            lines.append(f"### {name}")
            lines.append("")
            lines.append(f"- 适用: {row.get('applicable')}")
            lines.append(f"- 状态: {row.get('status')}")
            lines.append(f"- 子项分: {row.get('score')}")
            lines.append(f"- 核心分: {row.get('core_score')}")
            lines.append(f"- 合成方式: {row.get('score_basis')}")
            components = row.get("components") or {}
            for component, detail in components.items():
                if not isinstance(detail, dict):
                    continue
                extra = []
                for key in ("value", "reason", "method", "status"):
                    if detail.get(key) is not None:
                        extra.append(f"{key}={detail.get(key)}")
                lines.append(f"- {component}: score={detail.get('score')} ({', '.join(extra)})")
            lines.append("")
        lines.append("## 维度分")
        lines.append("")
        lines.append(f"- 状态: {result.get('status')}")
        lines.append(f"- 分数: {result.get('score')}")
        if result.get("reason"):
            lines.append(f"- 原因: {result.get('reason')}")
        gate = result.get("gate") or {}
        if gate:
            lines.append(f"- 门槛通过: {gate.get('passed')}")
            lines.append(f"- 门槛明细: {json.dumps(gate.get('gates'), ensure_ascii=False)}")
        lines.append("")
    (directory / "stage_report.md").write_text("\n".join(lines), encoding="utf-8")
    log_event("report", "阶段报告已写入", path=str(directory / "stage_report.md"), score=None if result is None else result.get("score"))


def archive_frames(label: str, samples: list[tuple[float, Path]]) -> list[dict[str, Any]]:
    """Copy extracted frames into the current case log so they can be reviewed."""
    directory = _LOG_DIR.get()
    if directory is None or not samples:
        return []
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label) or "frames"
    dest_root = directory / "frames" / safe
    dest_root.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    for index, (timestamp, source) in enumerate(samples):
        if not source.is_file():
            continue
        suffix = source.suffix.lower() or ".png"
        dest = dest_root / f"frame-{index:03d}-t{timestamp:.3f}{suffix}"
        if source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
        saved.append({
            "index": index,
            "timestamp": round(float(timestamp), 3),
            "path": str(dest.relative_to(directory)),
        })
    (directory / "frames" / f"{safe}.json").write_text(
        json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    log_event("frames", f"保存 {len(saved)} 张 {safe} 关键帧", directory=str(dest_root))
    return saved
