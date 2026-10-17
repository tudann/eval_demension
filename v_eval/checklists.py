from __future__ import annotations

import re
from typing import Any

from .cases import Case, ConfigError, _truthy, evaluate_applies
from .judge_client import JudgeClient, _parse_json_response, _response_content
from .judge_media import MediaPreparationError, build_judge_content


CHECKLIST_MIN_ITEMS = 1
CHECKLIST_MAX_ITEMS = 30
CHECKLIST_MAX_CORE_ITEMS = 3
RUBRIC_KIND = "rubric_5"

_ITEM_OBJECT_RULES = (
    "Each item object must contain id, subpoint, question, kind, and core. "
    "kind is the string rubric_5, not a number and not a field named rubric. "
    "question is the requirement itself. Do not use requirement, description, applied, or fulfilled."
)

_RUBRIC_GENERATION_RULES = (
    "Each item uses kind rubric_5 and states one requirement. "
    f"{_ITEM_OBJECT_RULES} "
    "Write at most one item for each applicable subpoint, and do not add items to reach a count of six. "
    "A later score of 5 means that requirement is fully achieved. Do not set expect to yes or no, and do not use yes_no or multiple-choice items. "
    "Mark core true only for a requirement the prompt insists on, and mark at most 3 items core. "
    "A prohibition is core only when that absence is itself the demand. "
    "Do not split one requirement into separate questions about incidental absences such as watermarks, timestamps, or tickers."
)

_ANSWER_RUBRIC = (
    "Score every checklist item with an integer from 1 to 5. Do not answer yes or no. "
    "5: the requirement is fully and accurately achieved, natural and stable, with almost no perceptible problem. "
    "4: the core of the requirement is achieved, with only a slight flaw or local deviation that does not obviously affect viewing. "
    "3: the requirement is basically achieved, but a clear problem, omission, or unnatural result remains. "
    "2: the requirement is only partly achieved, and the error, absence, or instability already affects whether the content holds. "
    "1: the requirement is basically missed, or the result is severely broken or unusable. "
    "For a yes_no item, expect decides what 5 means: expect yes means the described state is fully present; "
    "expect no means the named problem is fully absent. "
    "For a rubric_5 item, 5 means the requirement written in the question is fully achieved. "
    "Score multiple-choice items on the same 1-5 scale; do not return an option id. "
    "Return only JSON with gates and answers. "
    "Each gate object contains id, answer, and 回答依据. The answer is the string yes or no. "
    "Each answer object contains id, score, and 回答依据. The score is an integer from 1 to 5. "
    "回答依据 is one short sentence that cites what is visible or audible, including a media timestamp when the frames supply one. "
    "Do not leave 回答依据 empty. Omit an item only when the media cannot support a score."
)

_CHECKLIST_STRATEGIES: dict[str, str] = {
    "13_style_visual_control": (
        "D13 strategy: create questions only for requirements actually present in the prompt. "
        "Use style_accuracy for recognizable style and visual language; style_persistence for stability across time; "
        "style_content_compat for whether style preserves the requested subject and action; lighting_control only for explicit lighting requirements; "
        "color_control only for explicit color or palette requirements. "
        "Do not invent audio, editing, text, or endpoint requirements."
    ),
    "14_edit_controllable_gen": (
        "D14 strategy: create questions only for editing or controllability requirements present in the prompt or input mode. "
        "Use local_edit_accuracy for the requested edit, non_target_preservation for unaffected content, subject_replacement for identity or clothing replacement, "
        "add_remove_object for explicit object insertion or removal, video_extension for continuation, and first_last_frame only when endpoint media exists. "
        "Do not invent an edit, replacement, continuation, or endpoint requirement that the case does not contain."
    ),
    "15_audio_quality_control": (
        "D15 strategy: create questions only for audio requirements present in the prompt. "
        "Use dialogue_accuracy for requested dialogue or forbidden speech, voice_naturalness for audible speech quality, timbre_consistency for repeated or referenced voices, "
        "emotion_control for explicit vocal emotion, ambient_sound for described ambience, and action_sfx for named action sounds. "
        "Music is not a D15 subpoint in this evaluation taxonomy; do not create a music item. "
        "Do not add visual-only, text, endpoint, or unrelated audio questions."
    ),
    "16_audio_visual_sync": (
        "D16 strategy: create questions only for stated audio-visual relationships. "
        "Use lip_sync only for dialogue and visible speech, multi_speaker_match only for multiple speakers, "
        "action_sound_sync for a named visible action and its sound, and ambient_sound_sync for environmental sound aligned to a visible scene or environmental change. "
        "Do not invent dialogue, multiple speakers, or synchronization events absent from the prompt."
    ),
    "17_failure_anomaly_control": (
        "D17 strategy: assess failure and anomaly control, never general motion quality. "
        "Use human_deformation_rate for malformed human anatomy, subject_disappearance_rate for unintended loss of a subject, "
        "subject_duplication_rate for unintended extra copies, attribute_drift_rate for changes in identity, color, shape or other protected attributes, "
        "penetration_issue for objects or body parts passing through each other, camera_anomaly_rate for unintended camera jumps, cuts, crop or framing failures, "
        "and breakdown_duration for whether a visual breakdown persists or recovers across the clip. "
        "Phrase each item so 5 means the anomaly is absent or brief and harmless, and 1 means frequent, severe, or prolonged failure. "
        "Only use human_deformation_rate when people or human body parts are involved. Do not infer a numerical rate or duration from the prompt; scoring requires video evidence. "
        "Do not add audio, text, editing, or unrelated performance questions."
    ),
    "18_text_visual_consistency": (
        "D18 strategy: create questions only for text requirements or explicit absence of text. "
        "Use text_accuracy for required strings, subtitle_alignment for requested subtitles, text_readability for required visible text, "
        "text_stability for text persistence, and no_unrequested_text specifically for subtitles when they were not requested. "
        "Do not invent subtitles or required strings, and do not split one text requirement across several questions."
    ),
    "20_performance_emotion": (
        "D20 strategy: create one rubric_5 question only for performance requirements present in the prompt. "
        "Use emotion_accuracy for whether expression, posture, and vocal tone match the specified emotion and situation; "
        "expression_transition for a requested change of expression with a visible transition rather than a sudden cut or a frozen face; "
        "gaze_attention for looking at the named person, object, or away from camera; "
        "micro_motion for blinks, breathing, and small head movement when a person is present; "
        "reaction_timing for a reaction that follows hearing a line, being touched, or seeing an event; "
        "dialogue_performance for spoken words, facial expression, and body action expressing the same intent. "
        "Do not invent an emotion, gaze target, reaction, or line that the prompt does not contain. "
        "Do not add style, editing, text, or camera-only questions."
    ),
}

# Models often rename these keys. Applies checks only the names in dims_13_18.yaml.
_FACT_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "13_style_visual_control": {
        "target_lighting": ("lighting_requirement", "requested_lighting", "lighting"),
        "target_colors": ("color_requirement", "requested_colors", "colors", "palette"),
        "style_spec": ("style_requirement", "requested_style", "style"),
        "reference_image_roles": ("reference_roles", "reference_image_role"),
    },
    "14_edit_controllable_gen": {
        "edit_targets": ("edit_target", "requested_edit", "local_edit", "subject_edit"),
        "preserved": ("non_target_preservation", "preservation"),
        "has_subject_replacement": ("subject_replacement", "subject_edit", "replacement"),
        "add_objects": ("added_objects", "objects_to_add"),
        "remove_objects": ("removed_objects", "objects_to_remove"),
        "is_continuation": ("continuation", "video_extension"),
    },
    "15_audio_quality_control": {
        "dialogues": ("dialogue", "dialogue_requirement", "requested_dialogue"),
        "voice_forbidden": ("forbidden_voice", "no_voice", "no_speech"),
        "has_repeated_speaker": ("repeated_speaker",),
        "dialogue_emotions": ("emotion", "emotion_requirement", "vocal_emotion"),
        "ambient": ("ambient_requirement", "ambient_sound", "ambience"),
        "sfx": ("sfx_requirement", "action_sfx", "sound_effects"),
        "reference_audio_role": ("reference_audio",),
    },
    "16_audio_visual_sync": {
        "dialogues": ("dialogue", "dialogue_requirement", "requested_dialogue"),
        "multi_speaker": ("multiple_speakers", "speakers"),
        "av_events": ("actions", "av_event", "audio_events"),
        "env_changes": ("environment_changes", "env_change"),
    },
    "17_failure_anomaly_control": {
        "subjects": ("subject", "subject_consistency", "requested_subject"),
        "has_humans": ("human", "has_human", "has_person", "human_body_parts"),
        "protected_attributes": ("attributes", "fixed_attributes", "identity_constraints"),
        "camera_constraints": ("camera_requirements", "camera_movement"),
        "anomaly_constraints": ("forbidden_anomalies", "failure_constraints"),
    },
    "20_performance_emotion": {
        "has_humans": ("human", "has_human", "person"),
        "target_emotion": ("emotion", "emotion_requirement", "requested_emotion"),
        "character_situation": ("situation", "character_context", "scene_situation"),
        "emotion_change": ("expression_change", "emotion_transition", "expression_transition"),
        "gaze_target": ("gaze", "look_at", "attention_target"),
        "reaction_event": ("reaction", "trigger_event", "reaction_trigger"),
        "dialogues": ("dialogue", "dialogue_text", "requested_dialogue"),
    },
}

_BOOL_FACTS = {
    "has_subject_replacement", "is_continuation", "voice_forbidden", "has_repeated_speaker",
    "dialogue_emotions", "multi_speaker", "has_humans",
}
_TEXT_COMPANIONS = {
    "dialogue_emotions": "target_emotion",
    "ambient": "ambient_description",
    "sfx": "sfx_description",
}

_FACT_SCHEMAS: dict[str, str] = {
    "13_style_visual_control": (
        "facts must use exactly these keys: target_lighting (string, empty when no lighting is requested), "
        "target_colors (string, empty when no color or palette is requested), style_spec (string, empty when no visual style is requested), "
        "reference_image_roles (array of strings, empty when none). "
        "Do not rename them to lighting_requirement, color_requirement, or style_requirement. "
        "lighting_control items require non-empty target_lighting. color_control items require non-empty target_colors. "
        "style_accuracy, style_persistence, and style_content_compat are always allowed."
    ),
    "14_edit_controllable_gen": (
        "facts must use exactly these keys: edit_targets (string or array, empty when there is no local edit), "
        "preserved (string, empty when nothing must stay unchanged), has_subject_replacement (boolean), "
        "add_objects (string or array, empty when none), remove_objects (string or array, empty when none), is_continuation (boolean). "
        "local_edit_accuracy requires non-empty edit_targets. subject_replacement requires has_subject_replacement true. "
        "add_remove_object requires add_objects or remove_objects. video_extension requires is_continuation true. "
        "first_last_frame items are allowed only when case.first_frame or case.last_frame exists. non_target_preservation is always allowed."
    ),
    "15_audio_quality_control": (
        "facts must use exactly these keys: dialogues (requested speech text, or false when none), voice_forbidden (boolean), "
        "has_repeated_speaker (boolean), dialogue_emotions (boolean), target_emotion (string, empty unless dialogue_emotions is true), "
        "ambient (string, empty when none), ambient_description (the same ambient text, or empty), "
        "sfx (string, empty when none), sfx_description (the same effect text, or empty), "
        "reference_audio_role (string, empty when none). "
        "dialogue_accuracy requires non-empty dialogues. emotion_control requires dialogue_emotions true. "
        "ambient_sound requires non-empty ambient. action_sfx requires non-empty sfx. "
        "timbre_consistency requires has_repeated_speaker or reference_audio_role. "
        "voice_naturalness is always allowed."
    ),
    "16_audio_visual_sync": (
        "facts must use exactly these keys: dialogues (spoken text, or false when there is no speech), multi_speaker (boolean), "
        "av_events (string, empty when no action sound must match a visible event), "
        "env_changes (string, empty when no environmental sound must match a visible scene or change). "
        "Do not use dialogue, actions, or audio_layers as fact keys. "
        "lip_sync requires non-empty dialogues. multi_speaker_match requires multi_speaker true. "
        "action_sound_sync requires av_events. ambient_sound_sync requires env_changes."
    ),
    "17_failure_anomaly_control": (
        "facts must use exactly these keys: subjects (named protected subjects, or empty string), "
        "has_humans (boolean, true when a person or human body part is visible), "
        "protected_attributes (string describing attributes that must remain stable, or empty), "
        "camera_constraints (string describing required or forbidden camera behavior, or empty), "
        "anomaly_constraints (string describing explicitly forbidden failures, or empty). "
        "human_deformation_rate requires has_humans true. The other six subpoints are allowed when the prompt makes them relevant. "
        "Do not claim that a numeric rate or duration was measured from the prompt."
    ),
    "20_performance_emotion": (
        "facts must use exactly these keys: has_humans (boolean), "
        "target_emotion (string, empty when no emotion is specified), "
        "character_situation (string, empty when no character situation is specified), "
        "emotion_change (string describing the requested expression change, empty when none), "
        "gaze_target (string, empty when no looking target or attention is specified), "
        "reaction_event (string describing the heard line, touch, or seen event that should trigger a reaction, empty when none), "
        "dialogues (spoken text, or false when there is no speech). "
        "Do not use emotion, gaze, reaction, or dialogue as fact keys. "
        "emotion_accuracy requires target_emotion or character_situation. "
        "expression_transition requires non-empty emotion_change. gaze_attention requires non-empty gaze_target. "
        "micro_motion requires has_humans true. reaction_timing requires non-empty reaction_event. "
        "dialogue_performance requires non-empty dialogues."
    ),
}


def _normalize_choice_kind(kind: Any, options: Any) -> tuple[str, list[dict[str, str]]] | None:
    normalized_kind = str(kind or "yes_no").strip().lower()
    aliases = {"single_choice": "multiple_choice_3", "choice_3": "multiple_choice_3", "choice_4": "multiple_choice_4",
               "rubric": RUBRIC_KIND, "score_5": RUBRIC_KIND}
    normalized_kind = aliases.get(normalized_kind, normalized_kind)
    if normalized_kind == RUBRIC_KIND:
        return normalized_kind, []
    if normalized_kind == "yes_no":
        return normalized_kind, []
    if normalized_kind in {"multiple_choice", "single_choice"}:
        normalized_kind = "multiple_choice_3" if isinstance(options, list) and len(options) == 3 else "multiple_choice_4"
    if normalized_kind not in {"multiple_choice_3", "multiple_choice_4"} or not isinstance(options, list):
        return None
    expected_count = 3 if normalized_kind == "multiple_choice_3" else 4
    if len(options) != expected_count:
        return None
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for option in options:
        if not isinstance(option, dict):
            return None
        option_id = str(option.get("id", "")).strip()
        label = str(option.get("label", "")).strip()
        if not option_id or not label or option_id in seen:
            return None
        seen.add(option_id)
        normalized.append({"id": option_id, "label": label})
    return normalized_kind, normalized


def _item_kind(item: dict[str, Any]) -> Any:
    """Read kind, and accept a numeric rubric field as the required 5-point item."""
    kind = item.get("kind")
    if kind not in (None, ""):
        return kind
    rubric = item.get("rubric")
    if rubric in {5, "5", "rubric", "rubric_5"}:
        return RUBRIC_KIND
    return "yes_no"


def _normalize_item(item: dict[str, Any], configured_subpoints: set[str], index: int) -> dict[str, Any] | None:
    if str(item.get("subpoint")) not in configured_subpoints:
        return None
    question = str(item.get("question") or item.get("description") or item.get("requirement") or "").strip()
    item_id = str(item.get("id") or f"q{index}")
    if not question:
        return None
    normalized_choice = _normalize_choice_kind(_item_kind(item), item.get("options", []))
    if normalized_choice is None:
        return None
    kind, options = normalized_choice
    try:
        weight = float(item.get("weight", 1.0))
    except (TypeError, ValueError):
        return None
    if weight not in {0.5, 1.0, 2.0}:
        return None
    normalized: dict[str, Any] = {
        "id": item_id, "subpoint": str(item["subpoint"]), "question": question,
        "kind": kind, "time_hint": str(item.get("time_hint", "全片")),
        "weight": weight, "core": bool(item.get("core", False)),
        "evidence_required": bool(item.get("evidence_required", True)),
    }
    if kind != RUBRIC_KIND:
        expect = item.get("expect", "yes")
        if isinstance(expect, bool):
            expect = "yes" if expect else "no"
        expect = str(expect).strip()
        valid_answers = {"yes", "no"} if kind == "yes_no" else {option["id"] for option in options}
        if expect not in valid_answers:
            return None
        normalized["expect"] = expect
    if options:
        normalized["options"] = options
    return normalized


def _validate_checklist_items(items: Any, dimension_cfg: dict[str, Any], facts: dict[str, Any],
                              case: Case) -> list[dict[str, Any]] | None:
    """Normalize checklist items and enforce shared count, applicability, and quality constraints."""
    if not isinstance(items, list) or not CHECKLIST_MIN_ITEMS <= len(items) <= CHECKLIST_MAX_ITEMS:
        return None
    subpoints = dimension_cfg.get("subpoints") or {}
    configured_subpoints = set(subpoints)
    normalized_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    seen_subpoints: set[str] = set()
    core_count = 0
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            return None
        normalized = _normalize_item(item, configured_subpoints, index)
        if normalized is None or normalized["kind"] != RUBRIC_KIND:
            return None
        if normalized["subpoint"] in seen_subpoints:
            # Keep the first question for each subpoint; later duplicates are dropped.
            continue
        subpoint_cfg = subpoints[normalized["subpoint"]]
        if not evaluate_applies(subpoint_cfg.get("applies"), facts, case):
            # Drop invented questions for subpoints that do not apply to this case.
            continue
        question_key = re.sub(r"[\W_]+", "", normalized["question"].casefold())
        if normalized["id"] in seen_ids or not question_key or question_key in seen_questions:
            continue
        seen_ids.add(normalized["id"])
        seen_questions.add(question_key)
        seen_subpoints.add(normalized["subpoint"])
        core_count += int(normalized["core"])
        if core_count > CHECKLIST_MAX_CORE_ITEMS:
            return None
        normalized_items.append(normalized)
    if not CHECKLIST_MIN_ITEMS <= len(normalized_items) <= CHECKLIST_MAX_ITEMS:
        return None
    return normalized_items


def _d18_checklist_payload(payload: dict[str, Any], dimension_cfg: dict[str, Any], case: Case,
                           model: str | None = None) -> dict[str, Any] | None:
    """Validate a model-authored D18 facts/checklist without local question generation."""
    facts = payload.get("facts")
    gates = payload.get("gates")
    items = payload.get("items")
    if not isinstance(facts, dict) or not isinstance(gates, list) or not isinstance(items, list):
        return None
    expected_keys = {"expected_texts", "allowed_texts", "subtitles_required", "subtitle_lines", "text_forbidden"}
    if not expected_keys.issubset(facts):
        # Accept richer model-authored facts and normalize them for local OCR.
        requested_text = facts.get("requested_text")
        forbidden_text = facts.get("forbidden_text")
        requested_values = requested_text if isinstance(requested_text, list) else [requested_text]
        requested_values = [str(item).strip() for item in requested_values if isinstance(item, str) and item.strip()]
        quoted = []
        for value in requested_values:
            quoted.extend(re.findall(r"[“\"]([^”\"]+)[”\"]", value))
        expected = quoted or requested_values
        subtitle_values = facts.get("requested_subtitles", facts.get("subtitles", []))
        if isinstance(subtitle_values, str):
            subtitle_values = [subtitle_values]
        if not isinstance(subtitle_values, list):
            subtitle_values = []
        subtitle_lines = [str(item).strip() for item in subtitle_values if isinstance(item, str) and item.strip()]
        if requested_text is not None or forbidden_text is not None or "requested_subtitles" in facts or "subtitles" in facts:
            facts = {**facts,
                     "expected_texts": expected,
                     "allowed_texts": expected,
                     "subtitles_required": bool(facts.get("subtitles_required", False) or subtitle_lines),
                     "subtitle_lines": subtitle_lines,
                     "text_forbidden": bool(forbidden_text)}
        else:
            return None
    if not isinstance(facts["expected_texts"], list) or not isinstance(facts["allowed_texts"], list):
        return None
    if not all(isinstance(item, str) and item.strip() for item in facts["expected_texts"] + facts["allowed_texts"]):
        return None
    if not any(str(item).strip() for item in facts["expected_texts"]) and facts["allowed_texts"]:
        facts = {**facts, "expected_texts": [str(item).strip() for item in facts["allowed_texts"] if str(item).strip()]}
    if not isinstance(facts["subtitles_required"], bool) or not isinstance(facts["text_forbidden"], bool):
        return None
    if not isinstance(facts["subtitle_lines"], list) or not all(isinstance(item, str) for item in facts["subtitle_lines"]):
        return None
    configured_gates = {str(gate.get("id")): gate for gate in dimension_cfg.get("gates", []) if isinstance(gate, dict)}
    if not gates or any(not isinstance(gate, dict) or str(gate.get("id")) not in configured_gates for gate in gates):
        return None
    if set(str(gate.get("id")) for gate in gates) != set(configured_gates) or len(gates) != len(configured_gates):
        return None
    normalized_gates = []
    for gate in gates:
        base = configured_gates[str(gate["id"])]
        expect = gate.get("expect", base.get("expect", "yes"))
        if isinstance(expect, bool):
            expect = "yes" if expect else "no"
        normalized_gates.append({**base, "question": str(gate.get("question") or base["question"]), "expect": str(expect)})
    normalized_items = _validate_checklist_items(items, dimension_cfg, facts, case)
    if normalized_items is None:
        return None
    return {"version": 2, "dimension": "18_text_visual_consistency", "case_id": case.case_id,
            "facts": facts, "gates": normalized_gates, "items": normalized_items,
            "judge_mode": "external", "judge_model": model}


def generate_d18_checklist(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case,
                           prompt: str) -> dict[str, Any]:
    judge = JudgeClient("vision", role="checklist")
    if not judge.online:
        raise ConfigError("D18 checklist requires an online checklist judge; offline mode is disabled")
    subpoint_applies = {
        name: (cfg.get("applies") or "always")
        for name, cfg in (dimension_cfg.get("subpoints") or {}).items()
        if isinstance(cfg, dict)
    }
    request_payload = {
        "task": "Understand the prompt and author the D18 checklist for this one case.",
        "dimension": "18_text_visual_consistency",
        "prompt": prompt,
        "case": case.as_dict(),
        "allowed_gates": dimension_cfg.get("gates", []),
        "allowed_subpoints": list(subpoint_applies),
        "subpoint_applies": subpoint_applies,
        "output_schema": {"facts": "object", "gates": "array", "items": "array"},
    }
    content = build_judge_content(prompt, request_payload, case, judge.modality,
                                  media_env="V_EVAL_CHECKLIST_MEDIA", default_media="0",
                                  allow_media=False)
    response = judge.complete(
        "For D18, return exactly one JSON object and no markdown or explanatory text. "
        "The JSON must contain exactly these top-level keys: facts, gates, items. "
        "facts must contain exactly these keys and value types: expected_texts (array of strings), "
        "allowed_texts (array of strings), subtitles_required (boolean), subtitle_lines (array of strings), "
        "text_forbidden (boolean). Do not use requested_text, forbidden_text, subtitles, or other aliases. "
        "gates must be an array containing every allowed gate exactly once; each gate must contain id, question, expect, modality, core, "
        "and expect must be the string yes or no, never a boolean. "
        "Include items only for applicable D18 subpoints and honor subpoint_applies exactly. "
        "Spoken dialogue or quoted speech is not expected_texts or subtitle_lines unless the prompt asks to display that sentence on screen or as subtitles. "
        "subtitle_alignment items are allowed only when subtitles_required is true. Do not write hypothetical questions such as whether subtitles would be synchronized if they appeared. "
        f"{_RUBRIC_GENERATION_RULES} "
        "Every JSON string must be validly escaped. Avoid unescaped double quotation marks inside question text; "
        "use single quotation marks around quoted prompt text or encode embedded quotes as \\\". "
        "each item must contain id, subpoint, question, kind, time_hint, core, evidence_required. "
        "Every subpoint must be one of the allowed subpoints. Use question, never description, requirement, or other aliases. "
        f"{_CHECKLIST_STRATEGIES['18_text_visual_consistency']} "
        "Facts describe only requested text/subtitles/forbidden text from the prompt. Do not inspect or judge the generated video.",
        content,
        max_tokens=6000,
    )
    if response.get("status") != "ok":
        raise ConfigError(f"D18 checklist judge failed: {response.get('error')}")
    parsed = _parse_json_response(response.get("response"))
    checklist = _d18_checklist_payload(parsed, dimension_cfg, case, judge.model) if parsed else None
    if checklist is None:
        raw = _response_content(response.get("response"))
        preview = str(raw)[:3000].replace("\n", " ")
        raise ConfigError(f"D18 checklist judge returned invalid facts/gates/items JSON; response={preview}")
    return checklist


def _attach_fact_companion(facts: dict[str, Any], canonical: str) -> None:
    """Keep boolean gates boolean, and preserve a text description for numeric matchers."""
    value = facts.get(canonical)
    companion = _TEXT_COMPANIONS.get(canonical)
    if isinstance(value, str) and _truthy(value):
        if companion and not _truthy(facts.get(companion)):
            facts[companion] = value
        if canonical in _BOOL_FACTS:
            facts[canonical] = True


def _canonicalize_facts(dimension: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Copy known alias keys onto the fact names that applies expressions read."""
    normalized = dict(facts)
    for canonical, aliases in _FACT_ALIASES.get(dimension, {}).items():
        if not _truthy(normalized.get(canonical)):
            for alias in aliases:
                if _truthy(normalized.get(alias)):
                    normalized[canonical] = normalized[alias]
                    break
        _attach_fact_companion(normalized, canonical)
    return normalized


def _model_checklist_payload(payload: dict[str, Any], dimension_cfg: dict[str, Any], dimension: str,
                             case: Case, model: str | None = None) -> dict[str, Any] | None:
    """Validate a model-authored facts/checklist for any D13-D17 dimension."""
    facts = payload.get("facts")
    gates = payload.get("gates")
    items = payload.get("items")
    if not isinstance(facts, dict) or not isinstance(gates, list) or not isinstance(items, list):
        return None
    facts = _canonicalize_facts(dimension, facts)
    configured_gates = {str(gate.get("id")): gate for gate in dimension_cfg.get("gates", []) if isinstance(gate, dict)}
    if not configured_gates:
        return None
    if (not gates or len(gates) != len(configured_gates)
            or any(not isinstance(gate, dict) or str(gate.get("id")) not in configured_gates for gate in gates)
            or {str(gate.get("id")) for gate in gates} != set(configured_gates)):
        return None
    normalized_gates = []
    for gate in gates:
        if not isinstance(gate, dict) or str(gate.get("id")) not in configured_gates:
            return None
        base = configured_gates[str(gate["id"])]
        expect = gate.get("expect", base.get("expect", "yes"))
        if isinstance(expect, bool):
            expect = "yes" if expect else "no"
        normalized_gates.append({**base, "question": str(gate.get("question") or base["question"]), "expect": str(expect)})
    normalized_items = _validate_checklist_items(items, dimension_cfg, facts, case)
    if normalized_items is None:
        return None
    return {"version": 2, "dimension": dimension, "case_id": case.case_id,
            "facts": facts, "gates": normalized_gates, "items": normalized_items,
            "judge_mode": "external", "judge_model": model}


def generate_model_checklist(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case,
                             prompt: str) -> dict[str, Any]:
    dimension = str(task["dimension"])
    judge = JudgeClient(_judge_modality(dimension), role="checklist")
    if not judge.online:
        raise ConfigError(f"{dimension} checklist requires an online checklist judge; offline mode is disabled")
    allowed_subpoints = list((dimension_cfg.get("subpoints") or {}).keys())
    request_payload = {
        "task": "Understand the prompt and author the evaluation checklist for this one case.",
        "dimension": dimension, "prompt": prompt, "case": case.as_dict(),
        "allowed_gates": dimension_cfg.get("gates", []), "allowed_subpoints": allowed_subpoints,
        "subpoint_applies": {
            name: (cfg.get("applies") or "always")
            for name, cfg in (dimension_cfg.get("subpoints") or {}).items()
            if isinstance(cfg, dict)
        },
        "fact_schema": _FACT_SCHEMAS.get(dimension, ""),
        "output_schema": {"facts": "object", "gates": "array", "items": "array"},
        "item_schema": {
            "id": "q1", "subpoint": "one allowed subpoint",
            "question": "the requirement, written as one question",
            "kind": "rubric_5", "core": False,
        },
    }
    content = build_judge_content(prompt, request_payload, case, judge.modality,
                                  media_env="V_EVAL_CHECKLIST_MEDIA", default_media="0",
                                  allow_media=False)
    system = (
        f"For {dimension}, understand only what the prompt requests and return JSON with facts, gates, and items. "
        "Generate all gates and case-specific items; do not inspect or judge the generated media. "
        "Every item must use an allowed subpoint and preserve all allowed gate ids. "
        "Include only requirements that are actually present and only applicable subpoints. "
        f"{_RUBRIC_GENERATION_RULES} "
        "Never repeat the same question. Every question must be answerable from the corresponding media. "
        "Facts describe requested requirements, not observed output. Use booleans or yes/no consistently for fact values. "
        f"Fact schema: {_FACT_SCHEMAS.get(dimension, '')} "
        "Do not return markdown. "
        f"Dimension-specific strategy: {_CHECKLIST_STRATEGIES.get(dimension, '')}"
    )
    response = judge.complete(system, content, max_tokens=6000)
    if response.get("status") != "ok":
        raise ConfigError(f"{dimension} checklist judge failed: {response.get('error')}")
    parsed = _parse_json_response(response.get("response"))
    normalized = _model_checklist_payload(parsed, dimension_cfg, dimension, case, judge.model) if parsed else None
    if normalized is None:
        from .eval_log import log_event
        log_event("checklist", "清单未通过校验，使用 temperature=0.4 重出一次", case_id=case.case_id)
        response = judge.complete(
            system + " Your previous JSON was rejected. "
            "Each item needs question and kind set to the string rubric_5. "
            "Do not put the question in description or requirement, and do not send a numeric rubric field. "
            "Use each subpoint at most once, keep at most 3 core items, and return only valid JSON.",
            content,
            temperature=0.4,
            max_tokens=6000,
        )
        if response.get("status") != "ok":
            raise ConfigError(f"{dimension} checklist judge failed: {response.get('error')}")
        parsed = _parse_json_response(response.get("response"))
        normalized = _model_checklist_payload(parsed, dimension_cfg, dimension, case, judge.model) if parsed else None
    if normalized is None:
        raw = _response_content(response.get("response"))
        preview = str(raw)[:2000].replace("\n", " ")
        raise ConfigError(f"{dimension} checklist judge returned invalid facts/gates/items JSON; response={preview}")
    return normalized


def _judge_modality(dimension: str) -> str:
    """Return the judge modality used for checklist and answer requests."""
    if dimension == "15_audio_quality_control":
        return "audio"
    if dimension in {"16_audio_visual_sync", "20_performance_emotion"}:
        return "audio_visual"
    if dimension in {
        "13_style_visual_control",
        "14_edit_controllable_gen",
        "17_failure_anomaly_control",
        "18_text_visual_consistency",
    }:
        return "vision"
    raise ConfigError(f"unsupported judge dimension: {dimension}")


def _answer_basis(row: dict[str, Any]) -> str:
    for key in ("回答依据", "basis", "evidence", "reason"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _with_basis(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["回答依据"] = _answer_basis(item)
        normalized.append(item)
    return normalized


def _normalize_gate_answers(gates: Any, expected_ids: list[str] | None = None) -> list[dict[str, Any]]:
    if isinstance(gates, dict):
        gates = [{"id": key, "answer": value} for key, value in gates.items()]
    if not isinstance(gates, list):
        return []
    normalized = _with_basis(gates)
    # A bare list in checklist order still belongs to those gate ids.
    if expected_ids and len(normalized) == len(expected_ids) and all(not row.get("id") for row in normalized):
        for row, gate_id in zip(normalized, expected_ids):
            row["id"] = gate_id
    return normalized


def _missing_gate_ids(parsed: dict[str, Any], expected_ids: list[str]) -> list[str]:
    returned = {str(row.get("id")) for row in parsed.get("gates") or [] if isinstance(row, dict) and row.get("id")}
    return [gate_id for gate_id in expected_ids if gate_id not in returned]


def _parse_judge_payload(payload: Any, expected_gate_ids: list[str] | None = None) -> dict[str, Any] | None:
    parsed = _parse_json_response(payload)
    if not isinstance(parsed, dict):
        return None
    answers = parsed.get("answers")
    if not isinstance(answers, list):
        answers = parsed.get("items")
    if isinstance(answers, list):
        return {"answers": _with_basis(answers), "gates": _normalize_gate_answers(parsed.get("gates", []), expected_gate_ids)}
    return None


def _log_answer_basis(parsed: dict[str, Any]) -> None:
    from .eval_log import log_event

    for gate in parsed.get("gates") or []:
        if isinstance(gate, dict):
            log_event("judge", f"门槛 {gate.get('id')}", answer=gate.get("answer"), 回答依据=gate.get("回答依据") or "")
    for row in parsed.get("answers") or []:
        if isinstance(row, dict):
            log_event("judge", f"检查题 {row.get('id')}", score=row.get("score"), 回答依据=row.get("回答依据") or "")


def _missing_answer_basis(parsed: dict[str, Any]) -> bool:
    rows = [*(parsed.get("gates") or []), *(parsed.get("answers") or [])]
    return any(isinstance(row, dict) and not str(row.get("回答依据") or "").strip() for row in rows)


def answer_checklist(checklist: dict[str, Any], prompt: str, case: Case, judge: JudgeClient,
                     dimension: str | None = None) -> dict[str, Any]:
    dimension = dimension or str(checklist.get("dimension", ""))

    if judge.online:
        request_payload = {"prompt": prompt, "case": case.as_dict(), "checklist": checklist}
        try:
            content = build_judge_content(prompt, request_payload, case, judge.modality)
        except MediaPreparationError as exc:
            return {"status": "media_error", "source": "judge", "model": judge.model,
                    "error": str(exc), "answers": [], "gates": []}
        system = (
            "Answer every supplied gate, and score every checklist item, only when the attached target media contains enough evidence. "
            "Never infer a score from the prompt alone. "
            f"{_ANSWER_RUBRIC} "
            "Use the supplied exact media timestamps in concise evidence when possible. "
            "The JSON object must use the keys gates and answers. "
            "Return one gate object for every supplied gate id, for example "
            '{"id":"g1","answer":"yes","回答依据":"what was heard"}. '
            "Every gate and every answer must include a non-empty 回答依据."
        )
        expected_gate_ids = [str(gate.get("id")) for gate in checklist.get("gates") or [] if isinstance(gate, dict) and gate.get("id")]
        response = judge.complete(system, content, max_tokens=4096)
        if response.get("status") == "ok":
            parsed = _parse_judge_payload(response.get("response"), expected_gate_ids)
            missing_gates = _missing_gate_ids(parsed, expected_gate_ids) if parsed else expected_gate_ids
            if parsed is None or _missing_answer_basis(parsed) or missing_gates:
                from .eval_log import log_event
                if parsed is None:
                    reason = "作答 JSON 无法解析"
                elif missing_gates:
                    reason = f"作答缺少门槛 {','.join(missing_gates)}"
                else:
                    reason = "作答缺少回答依据"
                log_event("judge", f"{reason}，使用 temperature=0.4 重试一次")
                response = judge.complete(
                    system + " Your previous response was rejected. Return only one JSON object. "
                    f"Include every gate id: {', '.join(expected_gate_ids)}. "
                    "Each gate object needs id, answer, and a non-empty 回答依据.",
                    content,
                    temperature=0.4,
                    max_tokens=4096,
                )
                parsed = _parse_judge_payload(response.get("response"), expected_gate_ids) if response.get("status") == "ok" else None
            if parsed is not None and response.get("status") == "ok":
                _log_answer_basis(parsed)
                return {"status": "ok", "source": "judge", "model": judge.model,
                        "raw": response.get("response"), **parsed}
            preview = str(_response_content(response.get("response")))[:2000].replace("\n", " ")
            return {"status": "error", "source": "judge", "model": judge.model,
                    "error": f"judge response was not valid checklist JSON: {preview}", "answers": [], "gates": []}
        return {"status": "error", "source": "judge", "model": judge.model,
                "error": response.get("error"), "answers": [], "gates": []}
    raise ConfigError(f"{dimension} answer judge endpoint is not configured")


