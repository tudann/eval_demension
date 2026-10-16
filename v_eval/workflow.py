from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cases import Case, ConfigError, _safe_json, read_prompt
from .checklists import _judge_modality, answer_checklist, generate_d18_checklist, generate_model_checklist
from .eval_log import bind_case_log, log_event, unbind_case_log, write_stage_report
from .judge_client import JudgeClient
from .scoring import dimension_score, gate_result, score_subpoint


def _case_output_root(task: dict[str, Any], case: Case) -> Path:
    return Path(task.get("output_dir", "outputs")) / "runs" / str(task.get("run_name", "local")) / str(task["dimension"]) / case.output_id


def prepare_case(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case) -> dict[str, Any]:
    out_root = _case_output_root(task, case)
    out_root.mkdir(parents=True, exist_ok=True)
    token = bind_case_log(out_root)
    try:
        return _prepare_case(task, dimension_cfg, case, out_root)
    finally:
        unbind_case_log(token)


def _prepare_case(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case, out_root: Path) -> dict[str, Any]:
    dimension = str(task["dimension"])
    prompt = read_prompt(case)
    log_event("checklist", "开始出题", case_id=case.output_id, dimension=dimension)
    supported = {
        "13_style_visual_control", "14_edit_controllable_gen", "15_audio_quality_control",
        "16_audio_visual_sync", "17_failure_anomaly_control", "18_text_visual_consistency",
        "20_performance_emotion",
    }
    if dimension not in supported:
        raise ConfigError(f"unsupported dimension: {dimension}")
    checklist = generate_d18_checklist(task, dimension_cfg, case, prompt) if dimension == "18_text_visual_consistency" else generate_model_checklist(task, dimension_cfg, case, prompt)
    facts = checklist["facts"]
    (out_root / "facts.json").write_text(json.dumps(_safe_json(facts), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_root / "checklist.json").write_text(json.dumps(_safe_json(checklist), ensure_ascii=False, indent=2), encoding="utf-8")
    log_event(
        "checklist", "出题完成",
        gates=len(checklist.get("gates") or []),
        items=len(checklist.get("items") or []),
    )
    write_stage_report(case.output_id, checklist, None, None)
    return checklist


def evaluate_case(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case, scoring: dict[str, Any], force: bool = False) -> dict[str, Any]:
    dimension = str(task["dimension"])
    out_root = _case_output_root(task, case)
    out_root.mkdir(parents=True, exist_ok=True)
    token = bind_case_log(out_root)
    try:
        return _evaluate_case(task, dimension_cfg, case, scoring, force, out_root)
    finally:
        unbind_case_log(token)


def _evaluate_case(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case, scoring: dict[str, Any], force: bool, out_root: Path) -> dict[str, Any]:
    dimension = str(task["dimension"])
    log_event("evaluate", "开始作答与计分", case_id=case.output_id, dimension=dimension)
    facts_path = out_root / "facts.json"
    checklist_path = out_root / "checklist.json"
    answers_path = out_root / "answers.json"
    result_path = out_root / "result.json"
    if result_path.is_file() and not force:
        cached_result = json.loads(result_path.read_text(encoding="utf-8"))
        if cached_result.get("status") in {"ok", "gate_failed"}:
            log_event("evaluate", "使用已有结果", status=cached_result.get("status"), score=cached_result.get("score"))
            return cached_result
    prompt = read_prompt(case)
    if checklist_path.is_file() and facts_path.is_file() and not force:
        facts = json.loads(facts_path.read_text(encoding="utf-8"))
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
        if (checklist.get("version") != 2 or checklist.get("judge_mode") != "external"
                or checklist.get("dimension") != dimension
                or checklist.get("case_id") != case.case_id):
            raise ConfigError(f"cached checklist is not a matching external version-2 checklist: {checklist_path}")
    else:
        checklist = generate_d18_checklist(task, dimension_cfg, case, prompt) if dimension == "18_text_visual_consistency" else generate_model_checklist(task, dimension_cfg, case, prompt)
        facts = checklist["facts"]
    result_case_id = case.output_id
    if not case.video_path:
        answers = {"status": "skipped", "source": "judge", "answers": [], "gates": [],
                   "error": "video file not found"}
        status = "skipped_missing_video"
        result = {"case_id": result_case_id, "source_case_id": case.case_id, "input_id": case.task_id,
                  "dimension": dimension, "status": status, "score": None, "reason": "video file not found", "case": case.as_dict()}
    else:
        judge = JudgeClient(_judge_modality(dimension), role="judge")
        log_event("judge", "开始裁判作答", model=judge.model, online=judge.online)
        answers = answer_checklist(checklist, prompt, case, judge, dimension=dimension)
        gates = gate_result(checklist, answers)
        log_event("judge", "裁判作答结束", status=answers.get("status"), gate_passed=gates.get("passed"))
        if answers.get("status") != "ok":
            answer_status = str(answers.get("status") or "error")
            result_status = "media_error" if answer_status == "media_error" else f"judge_{answer_status}"
            result = {"case_id": result_case_id, "source_case_id": case.case_id, "input_id": case.task_id,
                      "dimension": dimension, "status": result_status, "score": None,
                      "reason": answers.get("error"), "gate": gates, "facts": facts, "subpoints": {},
                      "case": case.as_dict(), "judge": {"mode": answers.get("source"), "status": answer_status}}
        elif gates["passed"] is None:
            result = {"case_id": result_case_id, "source_case_id": case.case_id, "input_id": case.task_id,
                      "dimension": dimension, "status": "judge_incomplete", "score": None,
                      "reason": "judge omitted one or more required gates", "gate": gates,
                      "facts": facts, "subpoints": {}, "case": case.as_dict(),
                      "judge": {"mode": answers.get("source"), "status": "incomplete"}}
        else:
            log_event("score", "开始子项计分")
            subpoints = {name: score_subpoint(task, name, cfg, checklist, answers, case, facts, bool(gates["passed"]), scoring) for name, cfg in dimension_cfg.get("subpoints", {}).items()}
            for name, row in subpoints.items():
                if isinstance(row, dict):
                    log_event("score", f"子项 {name}", applicable=row.get("applicable"), status=row.get("status"), score=row.get("score"), basis=row.get("score_basis"))
            score = dimension_score(subpoints)
            if gates["passed"] is False:
                score = float(scoring.get("invalid_gate_score", 1.0))
                status = "gate_failed"
            else:
                status = "ok" if score is not None else "no_score"
            log_event("score", "维度分", score=score, status=status)
            result = {"case_id": result_case_id, "source_case_id": case.case_id, "input_id": case.task_id,
                      "dimension": dimension, "status": status, "score": score,
                      "gate": gates, "facts": facts, "subpoints": subpoints, "case": case.as_dict(),
                      "judge": {"mode": answers.get("source"), "status": answers.get("status")}}
    facts_path.write_text(json.dumps(_safe_json(facts), ensure_ascii=False, indent=2), encoding="utf-8")
    checklist_path.write_text(json.dumps(_safe_json(checklist), ensure_ascii=False, indent=2), encoding="utf-8")
    answers_path.write_text(json.dumps(_safe_json(answers), ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.write_text(json.dumps(_safe_json(result), ensure_ascii=False, indent=2), encoding="utf-8")
    write_stage_report(case.output_id, checklist, answers, result)
    log_event("evaluate", "case 完成", status=result.get("status"), score=result.get("score"), report=str(out_root / "stage_report.md"))
    return result

