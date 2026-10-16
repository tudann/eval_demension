"""Backward-compatible imports for the evaluation workflow.

New code should import from cases, judge_client, checklists, scoring, or workflow.
"""

from .cases import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    Case,
    ConfigError,
    _all_named,
    _discover_cases_from_input,
    _filter_referenced,
    _find_named,
    _get_path,
    _prompt_reference_indices,
    _safe_json,
    _truthy,
    discover_cases,
    evaluate_applies,
    read_prompt,
)
from .checklists import (
    CHECKLIST_MAX_CORE_ITEMS,
    CHECKLIST_MAX_ITEMS,
    CHECKLIST_MIN_ITEMS,
    RUBRIC_KIND,
    _ANSWER_RUBRIC,
    _BOOL_FACTS,
    _CHECKLIST_STRATEGIES,
    _FACT_ALIASES,
    _FACT_SCHEMAS,
    _RUBRIC_GENERATION_RULES,
    _TEXT_COMPANIONS,
    _attach_fact_companion,
    _canonicalize_facts,
    _d18_checklist_payload,
    _judge_modality,
    _model_checklist_payload,
    _normalize_choice_kind,
    _normalize_item,
    _parse_judge_payload,
    _validate_checklist_items,
    answer_checklist,
    generate_d18_checklist,
    generate_model_checklist,
)
from .judge_client import JudgeClient, _parse_json_response, _response_content
from .judge_media import MediaPreparationError, build_judge_content
from .model_components import run_local_component
from .scoring import (
    _MEASUREMENT_MISSING,
    _RUBRIC_SCORES,
    _blend_component_scores,
    checklist_component,
    component_enabled,
    dimension_score,
    gate_result,
    image_score,
    normalize_answer,
    rubric_score,
    run_component,
    score_subpoint,
)
from .workflow import _case_output_root, evaluate_case, prepare_case
