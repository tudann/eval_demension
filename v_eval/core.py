from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from .judge_media import MediaPreparationError, build_judge_content
from .model_components import run_local_component


VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}

CHECKLIST_MIN_ITEMS = 1
CHECKLIST_MAX_ITEMS = 30
CHECKLIST_MAX_CORE_ITEMS = 3
RUBRIC_KIND = "rubric_5"
_RUBRIC_SCORES = {1, 2, 3, 4, 5}
_MEASUREMENT_MISSING = {"not_configured", "error"}

_RUBRIC_GENERATION_RULES = (
    "Each item uses kind rubric_5 and states one requirement. "
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
    "Return only JSON with gates and answers. Each answer object contains id and score. "
    "Gates still use an answer of yes or no. Omit an item only when the media cannot support a score."
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
        "emotion_control for explicit vocal emotion, ambient_sound for described ambience, action_sfx for named action sounds, and music_match for required or forbidden music. "
        "Do not add visual-only, text, endpoint, or unrelated audio questions."
    ),
    "16_audio_visual_sync": (
        "D16 strategy: create questions only for stated audio-visual relationships. "
        "Use lip_sync only for dialogue and visible speech, multi_speaker_match only for multiple speakers, audio_change_alignment for named action or environment changes, "
        "and realism only when the prompt requests realistic audio-visual behavior. "
        "Do not invent dialogue, multiple speakers, or synchronization events absent from the prompt."
    ),
    "17_motion_temporal_consistency": (
        "D17 strategy: create questions only for visual motion and temporal requirements present in the prompt. "
        "Use motion_consistency for requested object or action continuity, camera_motion for explicit camera movement, subject_consistency for named subjects, "
        "temporal_continuity for event order and state transitions, and human_motion only when people are present. "
        "Do not add audio, text, editing, or human-body questions when the prompt has no such content."
    ),
    "18_text_visual_consistency": (
        "D18 strategy: create questions only for text requirements or explicit absence of text. "
        "Use text_accuracy for required strings, subtitle_alignment for requested subtitles, text_readability for required visible text, "
        "text_stability for text persistence, and no_unrequested_text for unwanted text, subtitles, or watermarks. "
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
        "music_required": ("music_requirement", "requested_music", "background_music"),
        "music_forbidden": ("forbidden_music", "no_music", "no_background_music"),
        "reference_audio_role": ("reference_audio",),
    },
    "16_audio_visual_sync": {
        "dialogues": ("dialogue", "dialogue_requirement", "requested_dialogue"),
        "multi_speaker": ("multiple_speakers", "speakers"),
        "av_events": ("actions", "av_event", "audio_events"),
        "env_changes": ("environment_changes", "env_change"),
        "realistic": ("realism", "realism_requirement", "audio_layers"),
    },
    "17_motion_temporal_consistency": {
        "subjects": ("subject", "subject_consistency", "requested_subject"),
        "main_subject_noun": ("main_subject",),
        "has_humans": ("human", "human_motion", "has_human"),
        "requested_camera_motion": ("camera_motion", "camera_movement"),
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
    "dialogue_emotions", "music_required", "music_forbidden", "multi_speaker", "realistic", "has_humans",
}
_TEXT_COMPANIONS = {
    "music_required": "music_description",
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
        "music_required (boolean), music_forbidden (boolean), music_description (string, empty unless music is required), "
        "reference_audio_role (string, empty when none). "
        "dialogue_accuracy requires non-empty dialogues. emotion_control requires dialogue_emotions true. "
        "ambient_sound requires non-empty ambient. action_sfx requires non-empty sfx. "
        "music_match requires music_required or music_forbidden. timbre_consistency requires has_repeated_speaker or reference_audio_role. "
        "voice_naturalness is always allowed."
    ),
    "16_audio_visual_sync": (
        "facts must use exactly these keys: dialogues (spoken text, or false when there is no speech), multi_speaker (boolean), "
        "av_events (string, empty when no action sound must match a visible event), env_changes (string, empty when none), "
        "realistic (boolean, true only when the prompt requests realistic audio-visual behavior). "
        "Do not use dialogue, actions, or audio_layers as fact keys. "
        "lip_sync requires non-empty dialogues. multi_speaker_match requires multi_speaker true. "
        "audio_change_alignment requires av_events or env_changes. realism requires realistic true."
    ),
    "17_motion_temporal_consistency": (
        "facts must use exactly these keys: subjects (named subjects, empty string when none), main_subject_noun (string), "
        "has_humans (boolean), requested_camera_motion (string, empty when camera movement is not specified). "
        "Do not use camera_motion, subject_consistency, or human_motion as fact keys. "
        "camera_motion items require non-empty requested_camera_motion. subject_consistency requires non-empty subjects. "
        "human_motion requires has_humans true. motion_consistency and temporal_continuity are always allowed."
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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "no", "0", "none", "null"}
    return bool(value)


def _get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _safe_json(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_json(v) for v in value]
    return value


@dataclass
class Case:
    case_id: str
    root: Path
    mode: str
    prompt_path: Path | None
    video_path: Path | None
    first_frame: Path | None = None
    last_frame: Path | None = None
    reference_images: list[Path] = field(default_factory=list)
    reference_videos: list[Path] = field(default_factory=list)
    reference_audios: list[Path] = field(default_factory=list)
    source: str | None = None
    task_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return _safe_json(asdict(self))

    @property
    def output_id(self) -> str:
        return f"{self.task_id}/{self.case_id}" if self.task_id else self.case_id


def _prompt_reference_indices(prompt: str, kind: str) -> set[int]:
    """Return one-based referenced media indices from the documented markers."""
    if not prompt:
        return set()
    aliases = {
        "image": r"(?:\[\s*reference\s+(?:image|picture)\s+|<\s*(?:reference\s+)?(?:image|picture)\s+|(?:reference\s+)?(?:image|picture)\s*|参考图\s*|(?<!像)图\s*|@图片\s*)(\d+)\s*(?:\]|>)?",
        "video": r"(?:\[\s*reference\s+video\s+|<\s*(?:reference\s+)?video\s+|(?:reference\s+)?video\s+|参考视频\s*)(\d+)\s*(?:\]|>)?",
        "audio": r"(?:\[\s*reference\s+audio\s+|<\s*(?:reference\s+)?audio\s+|(?:reference\s+)?audio\s+|参考音频\s*)(\d+)\s*(?:\]|>)?",
    }
    return {int(value) for value in re.findall(aliases[kind], prompt, flags=re.IGNORECASE)}


def _filter_referenced(paths: list[Path], prompt: str, kind: str) -> list[Path]:
    indices = _prompt_reference_indices(prompt, kind)
    if not indices:
        return []
    selected: list[Path] = []
    for path in paths:
        match = re.search(r"(?:_|-)(\d+)(?:\.[^.]+)?$", path.name)
        if match and int(match.group(1)) in indices:
            selected.append(path)
    return selected


class ConfigError(ValueError):
    pass


def _find_named(case_dir: Path, stem: str, extensions: set[str]) -> Path | None:
    direct = case_dir / stem
    if direct.is_file():
        return direct
    for suffix in extensions:
        candidate = case_dir / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _all_named(case_dir: Path, pattern: str, extensions: set[str], index: int) -> list[Path]:
    stem = pattern.format(index=index)
    found = []
    direct = case_dir / stem
    if direct.is_file():
        found.append(direct)
    for suffix in extensions:
        candidate = case_dir / f"{stem}{suffix}"
        if candidate.is_file() and candidate not in found:
            found.append(candidate)
    return found


def _discover_cases_from_input(input_cfg: dict[str, Any], task_id: str | None = None) -> list[Case]:
    root = Path(input_cfg.get("root", ""))
    if not root.is_dir():
        if input_cfg.get("allow_missing_root", False):
            return []
        raise ConfigError(f"input.root does not exist: {root}")
    mode = str(input_cfg.get("mode", "t2va")).lower()
    allowed_modes = {"t2va", "f2va", "l2va", "fl2va", "r2va"}
    if mode not in allowed_modes:
        raise ConfigError(f"unsupported input.mode: {mode}")
    requested = input_cfg.get("case_ids") or []
    requested_set = {str(item) for item in requested}
    case_dirs = [p for p in sorted(root.iterdir()) if p.is_dir() and (not requested_set or p.name in requested_set)]
    if requested_set:
        missing = sorted(requested_set - {p.name for p in case_dirs})
        if missing:
            raise ConfigError(f"case_ids not found below input.root: {', '.join(missing)}")
    prompt_name = input_cfg.get("prompt_filename", "prompt_final.txt")
    video_name = input_cfg.get("video_filename", "video.mp4")
    refs = input_cfg.get("references", {}) or {}
    cases: list[Case] = []
    for case_dir in case_dirs:
        prompt = case_dir / prompt_name
        video = case_dir / video_name
        prompt_text = prompt.read_text(encoding="utf-8", errors="replace") if prompt.is_file() else ""
        first = last = None
        images: list[Path] = []
        videos: list[Path] = []
        audios: list[Path] = []
        if mode in {"f2va", "fl2va"}:
            first = _find_named(case_dir, str(refs.get("first_frame_filename", "input_01")), IMAGE_EXTENSIONS)
        if mode in {"l2va", "fl2va"}:
            default_last = "input_02" if mode == "fl2va" else "input_01"
            last = _find_named(case_dir, str(refs.get("last_frame_filename", default_last)), IMAGE_EXTENSIONS)
        if mode == "r2va":
            image_pattern = refs.get("image_pattern", "input_{index:02d}")
            image_exts = {str(x).lower() for x in refs.get("image_extensions", sorted(IMAGE_EXTENSIONS))}
            video_pattern = refs.get("video_pattern", "ref_video_{index:02d}")
            audio_pattern = refs.get("audio_pattern", "ref_audio_{index:02d}")
            for index in range(1, 9):
                current = _all_named(case_dir, str(image_pattern), image_exts, index)
                current_v = _all_named(case_dir, str(video_pattern), VIDEO_EXTENSIONS, index)
                current_a = _all_named(case_dir, str(audio_pattern), AUDIO_EXTENSIONS, index)
                images.extend(_filter_referenced(current, prompt_text, "image"))
                videos.extend(_filter_referenced(current_v, prompt_text, "video"))
                audios.extend(_filter_referenced(current_a, prompt_text, "audio"))
        cases.append(Case(case_dir.name, case_dir, mode, prompt if prompt.is_file() else None,
                          video if video.is_file() else None, first, last,
                          sorted(images)[:8], sorted(videos)[:2], sorted(audios)[:1],
                          source=str(input_cfg.get("source", "local")), task_id=task_id))
    return cases


def discover_cases(task: dict[str, Any]) -> list[Case]:
    inputs = task.get("inputs")
    if inputs is None:
        return _discover_cases_from_input(task.get("input", {}))
    if not isinstance(inputs, list) or not inputs:
        raise ConfigError("inputs must be a non-empty list")
    cases: list[Case] = []
    seen_ids: set[str] = set()
    for index, input_cfg in enumerate(inputs, start=1):
        if not isinstance(input_cfg, dict):
            raise ConfigError(f"inputs[{index - 1}] must be a YAML mapping")
        mode = str(input_cfg.get("mode", "")).lower()
        task_id = str(input_cfg.get("id") or mode or f"input_{index}")
        if task_id in seen_ids:
            raise ConfigError(f"duplicate inputs id: {task_id}")
        if "/" in task_id or "\\" in task_id or task_id in {".", ".."}:
            raise ConfigError(f"inputs id must be a safe directory name: {task_id}")
        seen_ids.add(task_id)
        cases.extend(_discover_cases_from_input(input_cfg, task_id=task_id))
    return cases


def read_prompt(case: Case) -> str:
    if not case.prompt_path:
        return ""
    return case.prompt_path.read_text(encoding="utf-8", errors="replace")


def evaluate_applies(expression: str | None, facts: dict[str, Any], case: Case | None) -> bool:
    if not expression:
        return True
    parts = [part.strip() for part in re.split(r"\s+or\s+", expression.strip())]
    for part in parts:
        if part.startswith("facts."):
            value = facts.get(part[6:])
        elif part.startswith("case.") and case:
            value = getattr(case, part[5:], None)
        else:
            value = facts.get(part)
        if _truthy(value):
            return True
    return False


class JudgeClient:
    """OpenAI-compatible online judge client."""

    def __init__(self, modality: str, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: int = 180, role: str = "judge"):
        self.modality = modality
        self.role = role
        prefix = "V_EVAL_AUDIO_JUDGE" if modality in {"audio", "audio_visual"} else "V_EVAL_VISION_JUDGE"
        role_prefix = "V_EVAL_CHECKLIST"
        legacy_url = os.getenv("V_EVAL_JUDGE_URL")
        legacy_model = os.getenv("V_EVAL_JUDGE_MODEL")
        role_url = os.getenv(f"{role_prefix}_URL") if role == "checklist" else None
        role_model = os.getenv(f"{role_prefix}_MODEL") if role == "checklist" else None
        role_key = os.getenv(f"{role_prefix}_API_KEY") if role == "checklist" else None
        self.base_url = base_url or role_url or os.getenv(f"{prefix}_URL") or legacy_url
        self.model = model or role_model or os.getenv(f"{prefix}_MODEL") or legacy_model or (
            "Qwen2.5-Omni-7B" if modality in {"audio", "audio_visual"} else "Qwen3-VL-32B-Instruct"
        )
        self.api_key = api_key or role_key or (
            os.getenv(f"{prefix}_API_KEY")
            or os.getenv("V_EVAL_JUDGE_API_KEY")
            or os.getenv("V_EVAL_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        self.timeout = timeout

    @property
    def online(self) -> bool:
        return bool(self.base_url)

    def complete(self, system: str, user: str | list[dict[str, Any]], *, temperature: float = 0,
                 max_tokens: int | None = None) -> dict[str, Any]:
        if not self.base_url:
            raise ConfigError(f"{self.role} judge endpoint is not configured for {self.modality}")
        request_body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
        }
        if max_tokens is not None:
            request_body["max_tokens"] = max_tokens
        payload = json.dumps(request_body).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.base_url.rstrip("/") + "/chat/completions", data=payload,
                                         headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return {"status": "ok", "response": json.loads(response.read().decode("utf-8")), "model": self.model}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            detail = str(exc)
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:2000]
                except OSError:
                    pass
            return {"status": "error", "error": detail, "model": self.model}


def _response_content(payload: Any) -> Any:
    if isinstance(payload, dict):
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content", "") if isinstance(message, dict) else ""
            if isinstance(content, list):
                return "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
            return content
    return payload


def _parse_json_response(payload: Any) -> dict[str, Any] | None:
    content = _response_content(payload)
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return None
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


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


def _normalize_item(item: dict[str, Any], configured_subpoints: set[str], index: int) -> dict[str, Any] | None:
    if str(item.get("subpoint")) not in configured_subpoints:
        return None
    question = str(item.get("question") or item.get("description") or "").strip()
    item_id = str(item.get("id") or f"q{index}")
    if not question:
        return None
    normalized_choice = _normalize_choice_kind(item.get("kind", "yes_no"), item.get("options", []))
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
            return None
        subpoint_cfg = subpoints[normalized["subpoint"]]
        if not evaluate_applies(subpoint_cfg.get("applies"), facts, case):
            return None
        question_key = re.sub(r"[\W_]+", "", normalized["question"].casefold())
        if normalized["id"] in seen_ids or not question_key or question_key in seen_questions:
            return None
        seen_ids.add(normalized["id"])
        seen_questions.add(question_key)
        seen_subpoints.add(normalized["subpoint"])
        core_count += int(normalized["core"])
        if core_count > CHECKLIST_MAX_CORE_ITEMS:
            return None
        normalized_items.append(normalized)
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
    }
    content = build_judge_content(prompt, request_payload, case, judge.modality,
                                  media_env="V_EVAL_CHECKLIST_MEDIA", default_media="0",
                                  allow_media=False)
    response = judge.complete(
        f"For {dimension}, understand only what the prompt requests and return JSON with facts, gates, and items. "
        "Generate all gates and case-specific items; do not inspect or judge the generated media. "
        "Every item must use an allowed subpoint and preserve all allowed gate ids. "
        "Include only requirements that are actually present and only applicable subpoints. "
        f"{_RUBRIC_GENERATION_RULES} "
        "Never repeat the same question. Every question must be answerable from the corresponding media. "
        "Facts describe requested requirements, not observed output. Use booleans or yes/no consistently for fact values. "
        f"Fact schema: {_FACT_SCHEMAS.get(dimension, '')} "
        "Do not return markdown. "
        f"Dimension-specific strategy: {_CHECKLIST_STRATEGIES.get(dimension, '')}",
        content,
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
        "17_motion_temporal_consistency",
        "18_text_visual_consistency",
    }:
        return "vision"
    raise ConfigError(f"unsupported judge dimension: {dimension}")


def _parse_judge_payload(payload: Any) -> dict[str, Any] | None:
    parsed = _parse_json_response(payload)
    if isinstance(parsed, dict) and isinstance(parsed.get("answers"), list):
        return {"answers": parsed["answers"], "gates": parsed.get("gates", [])}
    return None


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
        response = judge.complete(
            "Answer every supplied gate, and score every checklist item, only when the attached target media contains enough evidence. "
            "Never infer a score from the prompt alone. "
            f"{_ANSWER_RUBRIC} "
            "Use the supplied exact media timestamps in concise evidence when possible.",
            content,
            max_tokens=4096,
        )
        if response.get("status") == "ok":
            parsed = _parse_judge_payload(response.get("response"))
            if parsed is not None:
                return {"status": "ok", "source": "judge", "model": judge.model,
                        "raw": response.get("response"), **parsed}
            return {"status": "error", "source": "judge", "model": judge.model,
                    "error": "judge response was not valid checklist JSON", "answers": [], "gates": []}
        return {"status": "error", "source": "judge", "model": judge.model,
                "error": response.get("error"), "answers": [], "gates": []}
    raise ConfigError(f"{dimension} answer judge endpoint is not configured")


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
    return {"passed": not any(value is False for value in results.values()), "gates": results}


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
    core_score = _blend_component_scores(core_base if isinstance(core_base, (int, float)) else None, checklist_weight, numeric_ok, missing_measurement)
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


def _case_output_root(task: dict[str, Any], case: Case) -> Path:
    return Path(task.get("output_dir", "outputs")) / "runs" / str(task.get("run_name", "local")) / str(task["dimension"]) / case.output_id


def prepare_case(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case) -> dict[str, Any]:
    out_root = _case_output_root(task, case)
    out_root.mkdir(parents=True, exist_ok=True)
    dimension = str(task["dimension"])
    prompt = read_prompt(case)
    supported = {
        "13_style_visual_control", "14_edit_controllable_gen", "15_audio_quality_control",
        "16_audio_visual_sync", "17_motion_temporal_consistency", "18_text_visual_consistency",
        "20_performance_emotion",
    }
    if dimension not in supported:
        raise ConfigError(f"unsupported dimension: {dimension}")
    checklist = generate_d18_checklist(task, dimension_cfg, case, prompt) if dimension == "18_text_visual_consistency" else generate_model_checklist(task, dimension_cfg, case, prompt)
    facts = checklist["facts"]
    (out_root / "facts.json").write_text(json.dumps(_safe_json(facts), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_root / "checklist.json").write_text(json.dumps(_safe_json(checklist), ensure_ascii=False, indent=2), encoding="utf-8")
    return checklist


def evaluate_case(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case, scoring: dict[str, Any], force: bool = False) -> dict[str, Any]:
    dimension = str(task["dimension"])
    out_root = _case_output_root(task, case)
    out_root.mkdir(parents=True, exist_ok=True)
    facts_path = out_root / "facts.json"
    checklist_path = out_root / "checklist.json"
    answers_path = out_root / "answers.json"
    result_path = out_root / "result.json"
    if result_path.is_file() and not force:
        return json.loads(result_path.read_text(encoding="utf-8"))
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
        answers = answer_checklist(checklist, prompt, case, judge, dimension=dimension)
        gates = gate_result(checklist, answers)
        if answers.get("status") == "media_error":
            result = {"case_id": result_case_id, "source_case_id": case.case_id, "input_id": case.task_id,
                      "dimension": dimension, "status": "media_error", "score": None,
                      "reason": answers.get("error"), "gate": gates, "facts": facts, "subpoints": {},
                      "case": case.as_dict(), "judge": {"mode": answers.get("source"), "status": "media_error"}}
        else:
            subpoints = {name: score_subpoint(task, name, cfg, checklist, answers, case, facts, bool(gates["passed"]), scoring) for name, cfg in dimension_cfg.get("subpoints", {}).items()}
            score = dimension_score(subpoints)
            if gates["passed"] is False:
                score = float(scoring.get("invalid_gate_score", 1.0))
                status = "gate_failed"
            else:
                status = "ok" if score is not None else "no_score"
            result = {"case_id": result_case_id, "source_case_id": case.case_id, "input_id": case.task_id,
                      "dimension": dimension, "status": status, "score": score,
                      "gate": gates, "facts": facts, "subpoints": subpoints, "case": case.as_dict(),
                      "judge": {"mode": answers.get("source"), "status": answers.get("status")}}
    facts_path.write_text(json.dumps(_safe_json(facts), ensure_ascii=False, indent=2), encoding="utf-8")
    checklist_path.write_text(json.dumps(_safe_json(checklist), ensure_ascii=False, indent=2), encoding="utf-8")
    answers_path.write_text(json.dumps(_safe_json(answers), ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.write_text(json.dumps(_safe_json(result), ensure_ascii=False, indent=2), encoding="utf-8")
    return result
