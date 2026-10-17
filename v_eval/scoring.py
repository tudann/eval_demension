from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .cases import Case, _truthy, evaluate_applies
from .model_components import run_local_component

_RUBRIC_SCORES = {1, 2, 3, 4, 5}
_MEASUREMENT_MISSING = {"not_configured", "error"}


def normalize_answer(value: Any) -> str | None:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return None
    text = str(value).strip().lower()
    if text.startswith("y") or text in {"1", "true", "是", "通过"}:
        return "yes"
    if text.startswith("n") or text in {"0", "false", "否", "不通过"}:
        return "no"
    return text or None


def rubric_score(value: Any) -> int | None:
    """Parse a 1-5 rubric score. yes/no is not a score."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)) and float(value) in _RUBRIC_SCORES and float(value) == int(value):
        return int(value)
    text = str(value).strip()
    if text in {"1", "2", "3", "4", "5"}:
        return int(text)
    return None


def checklist_component(checklist: dict[str, Any], answers: dict[str, Any], subpoint: str, scoring: dict[str, Any]) -> dict[str, Any]:
    """Score one subpoint from 1-5 item grades. The subpoint grade is the lowest item grade."""
    del scoring
    rows = {str(row.get("id")): row for row in answers.get("answers", []) if isinstance(row, dict)}
    selected = [item for item in checklist.get("items", []) if item.get("subpoint") == subpoint]
    if not selected:
        return {"status": "no_answer", "score": None, "core_score": None, "noncore_flaw": False, "details": []}
    details = []
    answered: list[int] = []
    core_answered: list[int] = []
    core_skipped = False
    noncore_flaw = False
    for item in selected:
        item_row = rows.get(str(item.get("id")), {})
        raw = item_row.get("score", item_row.get("answer"))
        grade = rubric_score(raw)
        is_core = bool(item.get("core"))
        if grade is None:
            if is_core:
                core_skipped = True
            else:
                noncore_flaw = True
            details.append({"id": item.get("id"), "valid": False, "score": None, "core": is_core})
            continue
        answered.append(grade)
        if is_core:
            core_answered.append(grade)
        elif grade < 5:
            noncore_flaw = True
        details.append({"id": item.get("id"), "valid": True, "score": grade, "core": is_core})
    has_core = any(bool(item.get("core")) for item in selected)
    if not answered and not core_skipped and not noncore_flaw:
        return {"status": "no_answer", "score": None, "core_score": None, "noncore_flaw": False, "details": details}
    if not answered:
        score: float | None = 3.0
        status = "unanswered_cap"
    else:
        score = float(min(answered))
        status = "ok"
        if len(answered) < len(selected):
            score = min(score, 3.0)
            status = "unanswered_cap"
    core_score: float | None = None
    if has_core:
        if core_answered:
            core_score = float(min(core_answered))
            if core_skipped:
                core_score = min(core_score, 3.0)
        else:
            core_score = 3.0
    return {"status": status, "score": score, "core_score": core_score, "noncore_flaw": noncore_flaw, "details": details}


def gate_result(checklist: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    returned = {str(row.get("id")): normalize_answer(row.get("answer")) for row in answers.get("gates", []) if isinstance(row, dict)}
    results: dict[str, bool | None] = {}
    for gate in checklist.get("gates", []):
        answer = returned.get(str(gate.get("id")))
        expect = normalize_answer(gate.get("expect", "yes"))
        results[str(gate.get("id"))] = None if answer is None else answer == expect
    passed = False if any(value is False for value in results.values()) else None if any(
        value is None for value in results.values()
    ) else True
    return {"passed": passed, "gates": results}


def image_score(reference: Path | None, target: Path | None) -> dict[str, Any]:
    if not reference or not target:
        return {"status": "missing_input", "score": None, "reason": "reference or target frame unavailable"}
    try:
        with Image.open(reference) as ref, Image.open(target) as dst:
            ref = ref.convert("RGB").resize((64, 64))
            dst = dst.convert("RGB").resize((64, 64))
            diff = sum(abs(a - b) for p, q in zip(ref.getdata(), dst.getdata()) for a, b in zip(p, q)) / (64 * 64 * 3 * 255)
        return {"status": "ok", "score": round(max(1.0, min(5.0, 5.0 - diff * 4.0)), 3), "method": "pixel_l1_proxy"}
    except Exception as exc:
        return {"status": "error", "score": None, "reason": str(exc)}


def run_component(name: str, case: Case, facts: dict[str, Any]) -> dict[str, Any]:
    local_result = run_local_component(name, case, facts)
    if local_result is not None:
        return local_result
    return {"component": name, "status": "not_configured", "score": None,
            "reason": "no local adapter is registered for this component"}


def component_enabled(task: dict[str, Any], subpoint: str, component: str) -> bool:
    override = ((task.get("evaluation") or {}).get("subpoints") or {}).get(subpoint, {})
    switches = override.get("components", {}) if isinstance(override, dict) else {}
    if component in switches:
        return _truthy(switches[component])
    return True


def _blend_component_scores(base: float | None, checklist_weight: float, numeric_ok: list[tuple[float, float]],
                            missing_measurement: bool) -> float | None:
    """Keep a missing numeric model from being folded into a perfect checklist score."""
    if base is None and not numeric_ok:
        return None
    if missing_measurement:
        if base is None:
            return None
        return float(min(base, 4.0))
    if base is None:
        weight = sum(item_weight for item_weight, _score in numeric_ok)
        return round(sum(item_weight * item_score for item_weight, item_score in numeric_ok) / weight, 3)
    if not numeric_ok:
        return float(base)
    weighted = checklist_weight * base + sum(item_weight * item_score for item_weight, item_score in numeric_ok)
    total = checklist_weight + sum(item_weight for item_weight, _score in numeric_ok)
    return round(weighted / total, 3) if total else float(base)


def score_subpoint(task: dict[str, Any], sp_name: str, sp_cfg: dict[str, Any], checklist: dict[str, Any], answers: dict[str, Any], case: Case, facts: dict[str, Any], gates_ok: bool, scoring: dict[str, Any]) -> dict[str, Any]:
    if not evaluate_applies(sp_cfg.get("applies"), facts, case):
        return {"applicable": False, "status": "not_applicable", "score": None, "components": {}}
    components: dict[str, Any] = {}
    if not gates_ok:
        return {"applicable": True, "status": "gate_failed", "score": float(scoring.get("invalid_gate_score", 1.0)),
                "core_score": float(scoring.get("invalid_gate_score", 1.0)), "noncore_flaw": False,
                "components": {}, "checklist": None}
    numeric_ok: list[tuple[float, float]] = []
    missing_measurement = False
    checklist_result: dict[str, Any] | None = None
    checklist_weight = 0.0
    for name, weight in (sp_cfg.get("components") or {}).items():
        if not component_enabled(task, sp_name, name):
            continue
        if name == "checklist":
            checklist_result = checklist_component(checklist, answers, sp_name, scoring)
            components[name] = checklist_result
            checklist_weight = float(weight)
        else:
            result = run_component(name, case, facts)
            components[name] = result
            if result.get("status") == "ok" and result.get("score") is not None:
                numeric_ok.append((float(weight), float(result["score"])))
            elif result.get("status") in _MEASUREMENT_MISSING:
                missing_measurement = True
    base = None if checklist_result is None else checklist_result.get("score")
    core_base = None if checklist_result is None else checklist_result.get("core_score")
    noncore_flaw = bool(checklist_result.get("noncore_flaw")) if checklist_result else False
    score = _blend_component_scores(base if isinstance(base, (int, float)) else None, checklist_weight, numeric_ok, missing_measurement)
    # A missing core checklist grade means this subpoint is not core. Numeric scores still
    # change the subpoint grade, but must not become a core grade and pull the dimension below 4.
    core_score = _blend_component_scores(float(core_base), checklist_weight, numeric_ok, missing_measurement) if isinstance(core_base, (int, float)) else None
    basis = "checklist_only" if missing_measurement else "weighted"
    return {"applicable": True, "status": "ok" if score is not None else "no_component_score", "score": score,
            "core_score": core_score, "noncore_flaw": noncore_flaw, "score_basis": basis, "components": components}


def dimension_score(subpoints: dict[str, Any]) -> float | None:
    """Cap the dimension by the worst core subpoint. Non-core flaws can only lower a 5 to a 4."""
    core_values: list[float] = []
    flaw = False
    any_score = False
    for row in subpoints.values():
        if not isinstance(row, dict) or not row.get("applicable"):
            continue
        score = row.get("score")
        core_value = row.get("core_score")
        if isinstance(score, (int, float)):
            any_score = True
        if isinstance(core_value, (int, float)):
            core_values.append(float(core_value))
        elif isinstance(score, (int, float)) and float(score) < 5:
            flaw = True
        if row.get("noncore_flaw"):
            flaw = True
    if core_values:
        worst = min(core_values)
        if worst < 4:
            return round(worst, 3)
        if worst < 5 or flaw:
            return 4.0
        return 5.0
    if not any_score:
        return None
    if flaw or any(isinstance(row.get("score"), (int, float)) and float(row["score"]) < 5
                   for row in subpoints.values() if isinstance(row, dict) and row.get("applicable")):
        return 4.0
    return 5.0


