from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}


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
    """Keep numbered references when the prompt cites them; otherwise keep every file."""
    indices = _prompt_reference_indices(prompt, kind)
    if not indices:
        return list(paths)
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


