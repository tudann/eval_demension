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
    "Write exactly one item for every applicable subpoint. "
    "If the facts make a subpoint apply, that subpoint must have its own question; do not leave it out. "
    "Do not add items for subpoints that do not apply, and do not add extra items to reach a fixed count. "
    "A later score of 5 is reserved for an exceptional result with no concrete flaw. A successful result with any slight flaw scores 4, and a clear problem scores 3. Do not set expect to yes or no, and do not use yes_no or multiple-choice items. "
    "Mark core true only for a requirement the prompt insists on, and mark at most 3 items core. "
    "A prohibition is core only when that absence is itself the demand. "
    "Do not split one requirement into separate questions about incidental absences such as watermarks, timestamps, or tickers."
)

_ANSWER_RUBRIC = (
    "Score every checklist item with an integer from 1 to 5. Do not answer yes or no. "
    "Reserve 5 for an exceptional result. A successful or mostly correct result is 4 or 3, not 5. "
    "5: every visible part of this one requirement is achieved, and you cannot name a concrete flaw. "
    "4: the requirement is achieved, but a slight flaw, local deviation, or small instability remains. "
    "3: the requirement is recognizable, but a clear omission, unnatural passage, inconsistency, or imperfect match remains. Use 3 for an adequate but imperfect result. "
    "2: the requirement is only partly achieved, and the error, absence, or instability already affects whether the content holds. "
    "1: the requirement is basically missed, or the result is severely broken or unusable. "
    "Before giving 5, cite evidence that every part of the requirement is excellent. "
    "If you can point to any flaw, the score is at most 4. If that flaw is clear, the score is at most 3. "
    "Do not give 5 merely because the prompt's main subject, style, color, lighting, or action is present. "
    "For a yes_no item, expect decides what 5 means: expect yes means the described state is fully present with no concrete flaw; "
    "expect no means the named problem is fully absent. "
    "For a rubric_5 item, 5 means the requirement written in the question is exceptionally achieved, not merely recognizable. "
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
        "Use text_accuracy for strings that must be visibly rendered, subtitle_alignment for requested subtitles, text_readability for required visible text, "
        "text_stability for text persistence, and no_unrequested_text specifically for subtitles when they were not requested. "
        "A text_accuracy question asks whether those strings appear as visible glyphs. Do not ask about lip sync, turn-taking, or whether a line was spoken aloud. "
        "Spoken dialogue is not a visible-text requirement unless the prompt asks to display that sentence or show it as subtitles. "
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
        if normalized["core"] and core_count >= CHECKLIST_MAX_CORE_ITEMS:
            normalized["core"] = False
        core_count += int(normalized["core"])
        normalized_items.append(normalized)
    applicable = [
        name for name, cfg in subpoints.items()
        if isinstance(cfg, dict) and evaluate_applies(cfg.get("applies"), facts, case)
    ]
    if any(name not in seen_subpoints for name in applicable):
        return None
    if not CHECKLIST_MIN_ITEMS <= len(normalized_items) <= CHECKLIST_MAX_ITEMS:
        return None
    return normalized_items


_VISIBLE_SPEECH_BANS = (
    "不要字幕",
    "禁止字幕",
    "无字幕",
    "不要屏幕文字",
    "禁止屏幕文字",
    "不要画面文字",
    "禁止画面文字",
    "禁止旁白画面文字",
    "不得出现字幕",
    "不要出现字幕",
    "不得有字幕",
    "不要有字幕",
)
_VISIBLE_DIALOGUE_CUES = (
    "对话气泡",
    "漫画气泡",
    "气泡文字",
    "字幕",
    "配字幕",
    "打成字幕",
    "写成字幕",
    "显示为字幕",
    "屏幕字幕",
    "画面文字",
    "写在画面",
    "写在屏幕",
)
_NON_SPEAKERS = {"场景", "画面", "镜头", "时长", "画幅", "风格", "摄影", "音乐", "音效", "要求", "注意", "主题", "作品"}
_SPEAKER_LINE = re.compile(r"(?m)^[ \t\u3000]*([^：:\n]{1,40})\s*[：:]\s*(\S.*?)\s*$")


def _compact_text(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text.casefold())


def _dialogue_lines(prompt: str) -> list[str]:
    """Return speaker-labeled lines. Section labels such as 场景 are not dialogue."""
    lines: list[str] = []
    for match in _SPEAKER_LINE.finditer(prompt):
        speaker = re.sub(r"[（(][^）)]*[）)]", "", match.group(1)).strip()
        spoken = match.group(2).strip()
        if speaker in _NON_SPEAKERS or len(_compact_text(spoken)) < 2:
            continue
        lines.append(spoken)
    return lines


def _prompt_forbids_visible_speech(prompt: str) -> bool:
    return any(phrase in prompt for phrase in _VISIBLE_SPEECH_BANS)


def _prompt_still_displays_dialogue(prompt: str) -> bool:
    """True when a subtitle ban coexists with a separate request to render the lines."""
    remaining = prompt
    for phrase in _VISIBLE_SPEECH_BANS:
        remaining = remaining.replace(phrase, "")
    return any(cue in remaining for cue in _VISIBLE_DIALOGUE_CUES)


def _fact_text_values(facts: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("expected_texts", "allowed_texts", "subtitle_lines", "requested_text", "requested_subtitles", "subtitles"):
        raw = facts.get(key)
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if isinstance(item, str) and str(item).strip())
    return values


def _text_matches_spoken(candidate: str, spoken: str) -> bool:
    left = _compact_text(candidate)
    right = _compact_text(spoken)
    if len(left) < 2 or len(right) < 2:
        return False
    return left == right or right in left or (len(left) >= 4 and left in right)


def spoken_lines_filed_as_visible_text(prompt: str, facts: dict[str, Any]) -> bool:
    """True when spoken lines were stored as required on-screen text despite a subtitle ban."""
    if not prompt or not _prompt_forbids_visible_speech(prompt) or _prompt_still_displays_dialogue(prompt):
        return False
    spoken = _dialogue_lines(prompt)
    if not spoken:
        return False
    return any(_text_matches_spoken(candidate, line) for candidate in _fact_text_values(facts) for line in spoken)


def _d18_checklist_payload(payload: dict[str, Any], dimension_cfg: dict[str, Any], case: Case,
                           model: str | None = None, prompt: str | None = None) -> dict[str, Any] | None:
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
    if prompt and spoken_lines_filed_as_visible_text(prompt, facts):
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
    system = (
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
        "Facts describe only requested text/subtitles/forbidden text from the prompt. Do not inspect or judge the generated video."
    )
    response = judge.complete(system, content, max_tokens=6000)
    checklist, conflict = _d18_checklist_from_response(response, dimension_cfg, case, judge.model, prompt)
    if checklist is None:
        response = judge.complete(
            system + " The previous JSON was rejected. If the prompt forbids on-screen text, titles, subtitles, logos, or watermarks, "
            "leave expected_texts, allowed_texts, and subtitle_lines empty and set subtitles_required false. "
            "Do not put spoken dialogue into expected_texts. Then the only applicable item is no_unrequested_text. "
            "If expected_texts is non-empty, include exactly one item for each of text_accuracy, text_readability, and text_stability.",
            content,
            max_tokens=6000,
        )
        checklist, retried_conflict = _d18_checklist_from_response(response, dimension_cfg, case, judge.model, prompt)
        conflict = conflict or retried_conflict
    if checklist is None and conflict:
        return _d18_no_visible_text_checklist(dimension_cfg, case, judge.model)
    if checklist is None:
        raw = _response_content(response.get("response"))
        preview = str(raw)[:3000].replace("\n", " ")
        raise ConfigError(f"D18 checklist judge returned invalid facts/gates/items JSON; response={preview}")
    return checklist


def _d18_checklist_from_response(response: dict[str, Any], dimension_cfg: dict[str, Any], case: Case,
                                 model: str | None, prompt: str) -> tuple[dict[str, Any] | None, bool]:
    """Return a valid checklist, and whether spoken lines were filed as visible text."""
    if response.get("status") != "ok":
        raise ConfigError(f"D18 checklist judge failed: {response.get('error')}")
    parsed = _parse_json_response(response.get("response"))
    facts = parsed.get("facts") if isinstance(parsed, dict) else None
    conflict = isinstance(facts, dict) and spoken_lines_filed_as_visible_text(prompt, facts)
    if conflict or not isinstance(parsed, dict):
        return None, conflict
    return _d18_checklist_payload(parsed, dimension_cfg, case, model, prompt), False


def _d18_no_visible_text_checklist(dimension_cfg: dict[str, Any], case: Case, model: str | None) -> dict[str, Any]:
    """Score only the absence of on-screen text after spoken lines were misfiled twice."""
    payload = {
        "facts": {
            "expected_texts": [],
            "allowed_texts": [],
            "subtitles_required": False,
            "subtitle_lines": [],
            "text_forbidden": True,
        },
        "gates": [
            {"id": gate.get("id"), "question": gate.get("question"), "expect": gate.get("expect", "yes"),
             "modality": gate.get("modality"), "core": gate.get("core", True)}
            for gate in dimension_cfg.get("gates", []) if isinstance(gate, dict)
        ],
        "items": [{
            "id": "i1",
            "subpoint": "no_unrequested_text",
            "question": "画面是否没有字幕、对白文字、标题、Logo、水印或其他未被要求出现的文字？",
            "kind": RUBRIC_KIND,
            "time_hint": "全片",
            "core": True,
            "evidence_required": True,
        }],
    }
    checklist = _d18_checklist_payload(payload, dimension_cfg, case, model, prompt=None)
    if checklist is None:
        raise ConfigError("D18 fallback checklist for forbidden on-screen text failed validation")
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


def _missing_applicable_subpoints(payload: dict[str, Any] | None, dimension_cfg: dict[str, Any],
                                  dimension: str, case: Case) -> list[str]:
    """Name applicable subpoints that the rejected checklist left without an item."""
    if not isinstance(payload, dict) or not isinstance(payload.get("facts"), dict):
        return []
    facts = _canonicalize_facts(dimension, payload["facts"])
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    present = {str(item.get("subpoint")) for item in items if isinstance(item, dict)}
    missing: list[str] = []
    for name, cfg in (dimension_cfg.get("subpoints") or {}).items():
        if isinstance(cfg, dict) and evaluate_applies(cfg.get("applies"), facts, case) and name not in present:
            missing.append(name)
    return missing


_D16_EMPTY_FACT = {
    "", "true", "false", "none", "null",
    "action_sound_sync", "ambient_sound_sync", "lip_sync", "multi_speaker_match",
}
_D16_ACTION_CUES = ("摩擦", "咔嗒", "齿轮", "绷断", "嗡鸣", "咯吱", "拍动", "拧紧", "拉动", "摆动", "螺旋桨", "扣件")
_D16_AMBIENT_CUES = ("风", "雨", "水下", "气泡", "钟声", "车流", "环境声", "海水", "瀑布")


def _d16_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text.casefold() in _D16_EMPTY_FACT:
        return ""
    return text


def _d16_unusable_fact(value: Any) -> bool:
    """A D16 fact is unusable when it is empty, a yes/no question, or a pasted prompt."""
    text = _d16_text(value)
    if not text or "是否" in text or len(text) > 180:
        return True
    return False


def _d16_generic_question(question: str) -> bool:
    return "是否" in question and not any(cue in question for cue in (*_D16_ACTION_CUES, *_D16_AMBIENT_CUES))


def _d16_speech_lines(prompt: str) -> list[str]:
    """Speaker lines and quoted words. Format notes and sound effects are not speech."""
    blocked = ("比例", "画幅", "提示", "环境", "时长", "音画", "音效")
    lines: list[str] = []
    for match in _SPEAKER_LINE.finditer(prompt):
        speaker = re.sub(r"[（(][^）)]*[）)]", "", match.group(1)).strip()
        spoken = match.group(2).strip()
        if speaker in _NON_SPEAKERS or any(word in speaker for word in blocked):
            continue
        if len(spoken) > 80 or len(_compact_text(spoken)) < 2:
            continue
        lines.append(spoken)
    if lines:
        return lines
    quotes: list[str] = []
    for clause in re.split(r"[。；;\n]", prompt):
        if "声" in clause:
            continue
        for quote in re.findall(r"[“\"]([^”\"]{2,80})[”\"]", clause):
            if len(_compact_text(quote)) < 2:
                continue
            quotes.append(quote)
    return quotes


def _d16_prepare_payload(payload: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Keep D16 facts tied to prompt speech and sounds, including when the judge fills them with junk."""
    facts = dict(payload.get("facts") or {})
    items = [dict(item) for item in payload.get("items") or [] if isinstance(item, dict)]
    spoken = _d16_speech_lines(prompt)
    if spoken:
        if _d16_unusable_fact(facts.get("dialogues")):
            facts["dialogues"] = " ".join(spoken)
    else:
        facts["dialogues"] = False
        facts["multi_speaker"] = False
        items = [item for item in items if item.get("subpoint") not in {"lip_sync", "multi_speaker_match"}]
    action, ambient = _d16_sounds_from_prompt(prompt)
    action_questions = [
        str(item.get("question") or "").strip() for item in items
        if item.get("subpoint") == "action_sound_sync" and not _d16_generic_question(str(item.get("question") or ""))
    ]
    ambient_questions = [
        str(item.get("question") or "").strip() for item in items
        if item.get("subpoint") == "ambient_sound_sync" and not _d16_generic_question(str(item.get("question") or ""))
    ]
    if _d16_unusable_fact(facts.get("av_events")):
        facts["av_events"] = action or " ".join(question for question in action_questions if question)
    if _d16_unusable_fact(facts.get("env_changes")):
        facts["env_changes"] = ambient or " ".join(question for question in ambient_questions if question)
    repaired: list[dict[str, Any]] = []
    for item in items:
        subpoint = item.get("subpoint")
        question = str(item.get("question") or "")
        if subpoint == "action_sound_sync":
            if not _d16_text(facts.get("av_events")):
                continue
            if action and action not in question:
                item["question"] = f"这些动作声音是否与对应的可见动作同时发生：{action}"
        elif subpoint == "ambient_sound_sync":
            if not _d16_text(facts.get("env_changes")):
                continue
            if ambient and ambient not in question:
                item["question"] = f"这些环境声音是否与画面中的场景或变化一致：{ambient}"
        repaired.append(item)
    if repaired and not any(item.get("core") for item in repaired):
        repaired[0]["core"] = True
    facts.setdefault("multi_speaker", False)
    return {**payload, "facts": facts, "items": repaired}


def _d16_sounds_from_prompt(prompt: str) -> tuple[str, str]:
    """Split prompt clauses into action sounds and environmental sounds."""
    text = prompt
    action: list[str] = []
    ambient: list[str] = []
    for clause in re.split(r"[。；;\n]", text):
        clause = re.sub(r"^环境音同步[:：]?", "", clause).strip(" ：:")
        if "声" not in clause:
            continue
        is_action = any(cue in clause for cue in _D16_ACTION_CUES)
        is_ambient = any(cue in clause for cue in _D16_AMBIENT_CUES)
        if is_action and not is_ambient:
            action.append(clause)
        elif is_ambient:
            ambient.append(clause)
        elif is_action:
            action.append(clause)
    return "；".join(action), "；".join(ambient)


def _d16_fallback_checklist(dimension_cfg: dict[str, Any], case: Case, model: str | None,
                            prompt: str) -> dict[str, Any] | None:
    """Build a D16 checklist from prompt sounds after the judge leaves the facts empty."""
    action, ambient = _d16_sounds_from_prompt(prompt)
    if not action and not ambient:
        return None
    items = []
    if action:
        items.append({
            "id": "i1", "subpoint": "action_sound_sync", "kind": RUBRIC_KIND, "core": True,
            "question": f"这些动作声音是否与对应的可见动作同时发生：{action}",
        })
    if ambient:
        items.append({
            "id": "i2" if action else "i1", "subpoint": "ambient_sound_sync", "kind": RUBRIC_KIND,
            "core": not action,
            "question": f"这些环境声音是否与画面中的场景或变化一致：{ambient}",
        })
    payload = {
        "facts": {
            "dialogues": False,
            "multi_speaker": False,
            "av_events": action,
            "env_changes": ambient,
        },
        "gates": [
            {"id": gate.get("id"), "question": gate.get("question"), "expect": gate.get("expect", "yes"),
             "modality": gate.get("modality"), "core": gate.get("core", True)}
            for gate in dimension_cfg.get("gates", []) if isinstance(gate, dict)
        ],
        "items": items,
    }
    return _model_checklist_payload(payload, dimension_cfg, "16_audio_visual_sync", case, model)


def _d16_checklist(payload: dict[str, Any] | None, dimension_cfg: dict[str, Any], case: Case,
                   model: str | None, prompt: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    prepared = _d16_prepare_payload(payload, prompt)
    return _model_checklist_payload(prepared, dimension_cfg, "16_audio_visual_sync", case, model)


_D20_FACT_BY_SUBPOINT = {
    "emotion_accuracy": "character_situation",
    "expression_transition": "emotion_change",
    "gaze_attention": "gaze_target",
    "reaction_timing": "reaction_event",
}


def _d20_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text.casefold() in {"", "true", "false", "none", "null"}:
        return ""
    return text


def _d20_facts_unusable(facts: dict[str, Any]) -> bool:
    """True when D20 facts enable no subpoint, so every item would be dropped."""
    if not facts:
        return True
    if facts.get("has_humans") is True:
        return False
    keys = ("target_emotion", "character_situation", "emotion_change", "gaze_target", "reaction_event", "dialogues")
    return not any(_d20_text(facts.get(key)) for key in keys)


def _d20_spoken(prompt: str) -> list[str]:
    return [line.strip() for line in re.findall(r"[“\"「]([^”\"」]{1,120})[”\"」]", prompt) if line.strip()]


def _d20_prepare_payload(payload: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Fill empty D20 facts from the questions the judge already wrote."""
    facts = dict(payload.get("facts") or {})
    items = [dict(item) for item in payload.get("items") or [] if isinstance(item, dict)]
    if not _d20_facts_unusable(facts):
        return payload
    repaired_facts: dict[str, Any] = {
        "has_humans": False,
        "target_emotion": "",
        "character_situation": "",
        "emotion_change": "",
        "gaze_target": "",
        "reaction_event": "",
        "dialogues": False,
    }
    repaired_items: list[dict[str, Any]] = []
    spoken = _d20_spoken(prompt)
    for item in items:
        subpoint = item.get("subpoint")
        question = str(item.get("question") or "").strip()
        if subpoint == "micro_motion" and question:
            repaired_facts["has_humans"] = True
            repaired_items.append(item)
            continue
        if subpoint == "dialogue_performance":
            if not spoken:
                continue
            repaired_facts["dialogues"] = " ".join(spoken)
            repaired_items.append(item)
            continue
        fact_key = _D20_FACT_BY_SUBPOINT.get(str(subpoint))
        if fact_key and question:
            repaired_facts[fact_key] = question
            repaired_items.append(item)
    return {**payload, "facts": repaired_facts, "items": repaired_items}


def _d20_checklist(payload: dict[str, Any] | None, dimension_cfg: dict[str, Any], case: Case,
                   model: str | None, prompt: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    prepared = _d20_prepare_payload(payload, prompt)
    return _model_checklist_payload(prepared, dimension_cfg, "20_performance_emotion", case, model)


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
    if dimension == "16_audio_visual_sync":
        normalized = _d16_checklist(parsed, dimension_cfg, case, judge.model, prompt)
    elif dimension == "20_performance_emotion":
        normalized = _d20_checklist(parsed, dimension_cfg, case, judge.model, prompt)
    else:
        normalized = _model_checklist_payload(parsed, dimension_cfg, dimension, case, judge.model) if parsed else None
    if normalized is None and dimension == "16_audio_visual_sync":
        from .eval_log import log_event
        log_event("checklist", "第16维事实为空，重出一次", case_id=case.case_id)
        response = judge.complete(
            system + " Your previous JSON was rejected because dialogues, av_events, and env_changes were empty. "
            "Put spoken lines in dialogues, action sounds that must match a visible action in av_events, "
            "and environmental sound that must match a visible scene or change in env_changes. "
            "Use false or an empty string only when the prompt does not request that sound. "
            "Do not leave those requirements only in the question text.",
            content,
            temperature=0.4,
            max_tokens=6000,
        )
        if response.get("status") != "ok":
            raise ConfigError(f"{dimension} checklist judge failed: {response.get('error')}")
        parsed = _parse_json_response(response.get("response"))
        normalized = _d16_checklist(parsed, dimension_cfg, case, judge.model, prompt)
        if normalized is None:
            normalized = _d16_fallback_checklist(dimension_cfg, case, judge.model, prompt)
    if normalized is None:
        from .eval_log import log_event
        log_event("checklist", "清单未通过校验，使用 temperature=0.4 重出一次", case_id=case.case_id)
        missing = _missing_applicable_subpoints(parsed, dimension_cfg, dimension, case)
        missing_hint = f" Add one rubric_5 item for each missing applicable subpoint: {', '.join(missing)}. Set core false when the checklist already has 3 core items." if missing else ""
        response = judge.complete(
            system + " Your previous JSON was rejected. "
            "Each item needs question and kind set to the string rubric_5. "
            "Do not put the question in description or requirement, and do not send a numeric rubric field. "
            "Use each subpoint at most once, include exactly one item for every applicable subpoint, "
            "keep at most 3 core items, and return only valid JSON."
            + missing_hint,
            content,
            temperature=0.4,
            max_tokens=6000,
        )
        if response.get("status") != "ok":
            raise ConfigError(f"{dimension} checklist judge failed: {response.get('error')}")
        parsed = _parse_json_response(response.get("response"))
        if dimension == "20_performance_emotion":
            normalized = _d20_checklist(parsed, dimension_cfg, case, judge.model, prompt)
        else:
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


