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

from .judge_media import build_judge_content
from .model_components import run_local_component


VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}


def _truthy(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.lower() in {"true", "yes", "1"})


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
            for index in range(1, 100):
                current = _all_named(case_dir, str(image_pattern), image_exts, index)
                current_v = _all_named(case_dir, str(video_pattern), VIDEO_EXTENSIONS, index)
                current_a = _all_named(case_dir, str(audio_pattern), AUDIO_EXTENSIONS, index)
                if not current and not current_v and not current_a:
                    if index > 1:
                        break
                    continue
                images.extend(current)
                videos.extend(current_v)
                audios.extend(current_a)
        cases.append(Case(case_dir.name, case_dir, mode, prompt if prompt.is_file() else None,
                          video if video.is_file() else None, first, last, images, videos, audios,
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


def infer_facts(dimension: str, prompt: str, case: Case) -> dict[str, Any]:
    text = prompt.lower()
    has = lambda *terms: any(term in text for term in terms)
    facts: dict[str, Any] = {}
    if dimension == "13_style_visual_control":
        facts = {
            "target_lighting": has("lighting", "light", "光", "照明", "明亮", "阴影", "shadow"),
            "target_colors": has("color", "colour", "red", "blue", "green", "暖色", "冷色", "颜色", "色彩"),
            "style_spec": prompt[:500],
            "reference_image_roles": [{"path": str(p), "role": "unknown", "confidence": 0.0} for p in case.reference_images],
        }
    elif dimension == "14_edit_controllable_gen":
        edit = has("edit", "change", "modify", "replace", "remove", "add", "修改", "编辑", "替换", "删除", "增加", "添加")
        replacement = has("replace", "替换", "换成", "主体替换")
        add = re.findall(r"(?:add|增加|添加)\s+([\w-]+)", text) or re.findall(r"(?:增加|添加)([^，。,.]+)", prompt)
        remove = re.findall(r"(?:remove|删除)\s+([\w-]+)", text) or re.findall(r"删除([^，。,.]+)", prompt)
        facts = {"edit_targets": [prompt[:120]] if edit else [], "preserved": [], "has_subject_replacement": replacement,
                 "add_objects": add, "remove_objects": remove,
                 "is_continuation": has("continue", "continuation", "extend", "续写", "延长"),
                 "static_camera": has("static", "固定镜头", "静止")}
    elif dimension == "15_audio_quality_control":
        emotion_terms = {
            "angry": "angry", "anger": "angry", "愤怒": "angry", "生气": "angry",
            "happy": "happy", "happiness": "happy", "开心": "happy", "高兴": "happy",
            "sad": "sad", "sadness": "sad", "悲伤": "sad",
            "fear": "fearful", "fearful": "fearful", "恐惧": "fearful",
            "surprise": "surprised", "惊讶": "surprised", "disgust": "disgusted", "厌恶": "disgusted",
            "neutral": "neutral", "平静": "neutral",
        }
        target_emotion = next((value for term, value in emotion_terms.items() if term in text), None)
        facts = {"dialogues": has("dialogue", "says", "say", "speaks", "voice", "对白", "说", "台词"),
                 "voice_forbidden": has("no voice", "without speech", "禁止说话", "无对白"),
                 "has_repeated_speaker": has("same speaker", "重复说话人", "同一声音"),
                 "dialogue_emotions": target_emotion is not None,
                 "target_emotion": target_emotion,
                 "ambient": has("ambient", "background sound", "环境音", "风声", "雨声"),
                 "ambient_description": prompt[:300],
                 "sfx": has("sound effect", "sfx", "脚步", "碰撞", "音效"),
                 "sfx_description": prompt[:300],
                 "music_required": has("music", "音乐", "配乐"),
                 "music_forbidden": has("no music", "without music", "不要音乐", "禁止配乐"),
                 "music_description": prompt[:300],
                 "reference_audio_role": bool(case.reference_audios)}
    elif dimension == "16_audio_visual_sync":
        facts = {"dialogues": has("dialogue", "says", "speaks", "对白", "说"),
                 "multi_speaker": has("two speakers", "multiple speakers", "多人", "两个说话人"),
                 "av_events": has("sound when", "同步", "同时", "impact", "碰撞"),
                 "env_changes": has("environment changes", "场景变化", "环境变化"),
                 "realistic": has("realistic", "natural", "真实", "自然")}
    elif dimension == "17_motion_temporal_consistency":
        facts = {"subjects": [prompt[:100]], "main_subject_noun": "subject", "has_humans": has("person", "people", "man", "woman", "人", "人物", "女孩", "男孩"),
                 "requested_camera_motion": has("pan", "zoom", "dolly", "camera", "镜头", "推拉", "摇镜")}
    elif dimension == "18_text_visual_consistency":
        expected = re.findall(r"[\"']([^\"']+)[\"']", prompt)
        facts = {"expected_texts": expected, "allowed_texts": expected, "subtitles_required": has("subtitle", "subtitles", "字幕"),
                 "subtitle_lines": [], "text_forbidden": has("no text", "without text", "禁止文字", "不得出现文字")}
    return facts


def _default_items(dimension: str, facts: dict[str, Any], dimension_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    number = 1
    for subpoint, cfg in dimension_cfg.get("subpoints", {}).items():
        applies = cfg.get("applies")
        if applies and not evaluate_applies(applies, facts, None):
            continue
        items.append({"id": f"q{number}", "subpoint": subpoint,
                      "question": f"视频是否满足“{cfg.get('name_zh', subpoint)}”的要求？",
                      "kind": "yes_no", "expect": "yes", "modality": "vision",
                      "time_hint": "全片", "weight": 1.0, "core": number == 1})
        number += 1
    return items


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
        if bool(value):
            return True
    return False


class JudgeClient:
    """OpenAI-compatible judge client; absent endpoint means offline mode."""

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

    def complete(self, system: str, user: str | list[dict[str, Any]], *, temperature: float = 0) -> dict[str, Any]:
        if not self.base_url:
            return {"status": "offline", "model": self.model}
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
        }).encode()
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


def make_checklist(dimension: str, facts: dict[str, Any], dimension_cfg: dict[str, Any], case: Case) -> dict[str, Any]:
    items = _default_items(dimension, facts, dimension_cfg)
    return {"version": 1, "dimension": dimension, "facts": facts,
            "gates": dimension_cfg.get("gates", []), "items": items,
            "judge_mode": "local_template", "case_id": case.case_id}


def _judge_modality(dimension: str) -> str:
    if dimension == "16_audio_visual_sync":
        return "audio_visual"
    return "audio" if dimension == "15_audio_quality_control" else "vision"


def _normalize_checklist(payload: dict[str, Any], local: dict[str, Any], model: str | None = None) -> dict[str, Any] | None:
    gates = payload.get("gates")
    items = payload.get("items")
    if not isinstance(gates, list) or not isinstance(items, list) or not items:
        return None
    local_items = {str(item.get("id")): item for item in local.get("items", [])}
    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        fallback = local_items.get(str(item.get("id"))) or local_items.get(f"q{index}") or {}
        row = dict(fallback)
        row.update(item)
        row["id"] = str(row.get("id") or f"q{index}")
        row.setdefault("kind", "yes_no")
        row.setdefault("expect", "yes")
        row.setdefault("weight", 1.0)
        row.setdefault("core", index == 1)
        if row.get("subpoint"):
            normalized_items.append(row)
    if not normalized_items:
        return None
    normalized_gates = [gate for gate in gates if isinstance(gate, dict) and gate.get("id")]
    if not normalized_gates:
        normalized_gates = list(local.get("gates", []))
    return {**local, "gates": normalized_gates, "items": normalized_items,
            "judge_mode": "external", "judge_model": model}


def generate_checklist(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case,
                       facts: dict[str, Any], prompt: str) -> dict[str, Any]:
    dimension = str(task["dimension"])
    local = make_checklist(dimension, facts, dimension_cfg, case)
    judge = JudgeClient(_judge_modality(dimension), role="checklist")
    if not judge.online:
        return local
    request_payload = {
        "task": "Generate the evaluation checklist for this one case.",
        "dimension": dimension,
        "prompt": prompt,
        "facts": facts,
        "dimension_config": dimension_cfg,
        "local_template": local,
        "output_schema": {"gates": "array", "items": "array"},
    }
    content = build_judge_content(prompt, request_payload, case, judge.modality,
                                  media_env="V_EVAL_CHECKLIST_MEDIA", default_media="0")
    response = judge.complete(
        "Create a rigorous checklist from the supplied dimension configuration. Return only JSON with gates and items. "
        "Preserve gate ids and item subpoints when the local template provides them. Do not invent unsupported dimensions.",
        content,
    )
    if response.get("status") != "ok":
        return {**local, "judge_mode": "local_fallback", "judge_error": response.get("error")}
    parsed = _parse_json_response(response.get("response"))
    normalized = _normalize_checklist(parsed, local, judge.model) if parsed else None
    if normalized is None:
        return {**local, "judge_mode": "local_fallback", "judge_error": "external checklist response was invalid"}
    return normalized


def offline_answer(item: dict[str, Any], prompt: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Conservative deterministic answer used when no judge service is configured."""
    answer = "yes"
    evidence = "offline mode: no remote judge configured; checklist item retained for manual review"
    if item.get("subpoint") == "music_match" and facts.get("music_forbidden"):
        answer = "yes"
    return {"id": item["id"], "answer": answer, "evidence": evidence, "source": "offline"}


def _parse_judge_payload(payload: Any) -> dict[str, Any] | None:
    parsed = _parse_json_response(payload)
    if isinstance(parsed, dict) and isinstance(parsed.get("answers"), list):
        return {"answers": parsed["answers"], "gates": parsed.get("gates", [])}
    return None


def answer_checklist(checklist: dict[str, Any], prompt: str, case: Case, judge: JudgeClient) -> dict[str, Any]:
    if judge.online:
        request_payload = {"prompt": prompt, "case": case.as_dict(), "checklist": checklist}
        content = build_judge_content(prompt, request_payload, case, judge.modality)
        response = judge.complete(
            "Answer every supplied gate and checklist item using the media and prompt. Return only JSON with 'gates' and 'answers' arrays. "
            "Each row must preserve the supplied id and use yes/no (or true/false for gates). Include concise evidence.",
            content,
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
    answers = [offline_answer(item, prompt, checklist.get("facts", {})) for item in checklist.get("items", [])]
    gates = [{"id": gate["id"], "answer": gate.get("expect", "yes"), "evidence": "offline mode: gate retained for manual review", "source": "offline"} for gate in checklist.get("gates", [])]
    return {"status": "offline", "source": "offline", "model": judge.model, "answers": answers, "gates": gates}


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


def checklist_component(checklist: dict[str, Any], answers: dict[str, Any], subpoint: str, scoring: dict[str, Any]) -> dict[str, Any]:
    rows = {str(row.get("id")): row for row in answers.get("answers", []) if isinstance(row, dict)}
    selected = [item for item in checklist.get("items", []) if item.get("subpoint") == subpoint]
    weighted_total = 0.0
    weighted_correct = 0.0
    core_failed = False
    details = []
    for item in selected:
        answer = normalize_answer(rows.get(item.get("id"), {}).get("answer"))
        expect = normalize_answer(item.get("expect"))
        if answer is None and scoring.get("unanswered_excluded", True):
            details.append({"id": item.get("id"), "valid": False, "correct": None})
            continue
        correct = answer == expect
        weight = float(item.get("weight", 1.0))
        weighted_total += weight
        weighted_correct += weight if correct else 0.0
        core_failed = core_failed or (bool(item.get("core")) and not correct)
        details.append({"id": item.get("id"), "valid": True, "correct": correct, "answer": answer})
    if weighted_total == 0:
        return {"status": "no_answer", "score": None, "details": details}
    ratio = weighted_correct / weighted_total
    score = 5.0 if ratio >= 1.0 else 4.0 if ratio >= 0.8 else 3.0 if ratio >= 0.6 else 2.0 if ratio >= 0.3 else 1.0
    if core_failed:
        score = min(score, float(scoring.get("core_failure_cap", 2.0)))
    return {"status": "ok", "score": score, "ratio": ratio, "details": details, "core_failed": core_failed}


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


def score_subpoint(task: dict[str, Any], sp_name: str, sp_cfg: dict[str, Any], checklist: dict[str, Any], answers: dict[str, Any], case: Case, facts: dict[str, Any], gates_ok: bool, scoring: dict[str, Any]) -> dict[str, Any]:
    if not evaluate_applies(sp_cfg.get("applies"), facts, case):
        return {"applicable": False, "status": "not_applicable", "score": None, "components": {}}
    components: dict[str, Any] = {}
    if not gates_ok:
        return {"applicable": True, "status": "gate_failed", "score": float(scoring.get("invalid_gate_score", 1.0)), "components": {}, "checklist": None}
    weighted = 0.0
    total_weight = 0.0
    for name, weight in (sp_cfg.get("components") or {}).items():
        if not component_enabled(task, sp_name, name):
            continue
        if name == "checklist":
            result = checklist_component(checklist, answers, sp_name, scoring)
        else:
            result = run_component(name, case, facts)
        components[name] = result
        if result.get("status") in {"ok", "offline"} and result.get("score") is not None:
            weighted += float(weight) * float(result["score"])
            total_weight += float(weight)
    score = round(weighted / total_weight, 3) if total_weight else None
    return {"applicable": True, "status": "ok" if score is not None else "no_component_score", "score": score, "components": components}


def _case_output_root(task: dict[str, Any], case: Case) -> Path:
    return Path(task.get("output_dir", "outputs")) / "runs" / str(task.get("run_name", "local")) / str(task["dimension"]) / case.output_id


def prepare_case(task: dict[str, Any], dimension_cfg: dict[str, Any], case: Case,
                 *, use_external: bool = True) -> dict[str, Any]:
    out_root = _case_output_root(task, case)
    out_root.mkdir(parents=True, exist_ok=True)
    prompt = read_prompt(case)
    facts = infer_facts(str(task["dimension"]), prompt, case)
    checklist = generate_checklist(task, dimension_cfg, case, facts, prompt) if use_external else make_checklist(
        str(task["dimension"]), facts, dimension_cfg, case
    )
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
    else:
        facts = infer_facts(dimension, prompt, case)
        checklist = generate_checklist(task, dimension_cfg, case, facts, prompt)
    judge = JudgeClient(_judge_modality(dimension), role="judge")
    answers = answer_checklist(checklist, prompt, case, judge)
    gates = gate_result(checklist, answers)
    result_case_id = case.output_id
    if not case.video_path:
        status = "skipped_missing_video"
        result = {"case_id": result_case_id, "source_case_id": case.case_id, "input_id": case.task_id,
                  "dimension": dimension, "status": status, "score": None, "reason": "video file not found", "case": case.as_dict()}
    else:
        subpoints = {name: score_subpoint(task, name, cfg, checklist, answers, case, facts, bool(gates["passed"]), scoring) for name, cfg in dimension_cfg.get("subpoints", {}).items()}
        applicable = [row["score"] for row in subpoints.values() if row.get("applicable") and row.get("score") is not None]
        score = round(sum(applicable) / len(applicable), 3) if applicable else None
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
