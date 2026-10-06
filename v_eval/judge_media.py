from __future__ import annotations

import base64
import json
import math
import mimetypes
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image


class CaseLike(Protocol):
    video_path: Path | None
    first_frame: Path | None
    last_frame: Path | None
    reference_images: list[Path]
    reference_videos: list[Path]
    reference_audios: list[Path]


class MediaPreparationError(RuntimeError):
    """Raised when target media required by a judge request cannot be prepared."""


@dataclass(frozen=True)
class TimedFrame:
    path: Path
    timestamp: float


@dataclass(frozen=True)
class MediaWindow:
    start: float
    end: float
    reasons: tuple[str, ...]


_IMAGE_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_AUDIO_FORMAT = {".wav": "wav", ".mp3": "mp3", ".m4a": "mp4", ".flac": "flac", ".ogg": "ogg"}
_D16_WINDOW_SECONDS = {
    "lip_sync": 2.0,
    "multi_speaker_match": 2.5,
    "audio_change_alignment": 3.0,
    "realism": 3.0,
}


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _image_block(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    mime = _IMAGE_MIME.get(suffix, mimetypes.guess_type(path.name)[0] or "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def _audio_block(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "input_audio", "input_audio": {"data": encoded, "format": _AUDIO_FORMAT.get(suffix, "wav")}}


def _duration(video: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return max(0.0, float(result.stdout.strip()))
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _uniform_timestamps(start: float, end: float, *, fps: float, limit: int) -> list[float]:
    """Return midpoint samples spread across the complete interval."""
    span = max(0.0, end - start)
    if span <= 0 or fps <= 0 or limit <= 0:
        return []
    count = min(limit, max(1, int(round(span * fps))))
    step = span / count
    upper = max(start, end - 0.001)
    return [min(upper, start + (index + 0.5) * step) for index in range(count)]


def _extract_one_frame(video: Path, timestamp: float, target: Path, size: int, quality: int) -> bool:
    raw = target.with_suffix(".png")
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{timestamp:.6f}", "-i", str(video),
             "-frames:v", "1", "-vf", f"scale={size}:-2:force_original_aspect_ratio=decrease", "-y", str(raw)],
            capture_output=True, text=True, check=True, timeout=60,
        )
        with Image.open(raw) as image:
            image.convert("RGB").save(target, format="JPEG", quality=quality, optimize=True)
        raw.unlink(missing_ok=True)
        return target.is_file() and target.stat().st_size > 0
    except (OSError, ValueError, subprocess.SubprocessError):
        raw.unlink(missing_ok=True)
        return False


def _extract_video_frames(video: Path, directory: Path, *, fps: float, limit: int,
                          size: int, quality: int, label: str, start: float = 0.0,
                          end: float | None = None) -> list[TimedFrame]:
    if not video.is_file() or limit <= 0:
        return []
    duration = _duration(video)
    if duration <= 0:
        return []
    interval_start = min(max(0.0, start), duration)
    interval_end = min(duration, end if end is not None else duration)
    timestamps = _uniform_timestamps(interval_start, interval_end, fps=fps, limit=limit)
    frame_dir = directory / label
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames: list[TimedFrame] = []
    for index, timestamp in enumerate(timestamps):
        target = frame_dir / f"frame-{index:03d}-t{timestamp:.3f}.jpg"
        if not _extract_one_frame(video, timestamp, target, size, quality):
            return []
        frames.append(TimedFrame(target, timestamp))
    return frames


def _extract_video_audio(video: Path, directory: Path, label: str, *, start: float = 0.0,
                         end: float | None = None) -> Path | None:
    if not video.is_file():
        return None
    target = directory / f"{label}.wav"
    command = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.6f}", "-i", str(video)]
    if end is not None:
        command.extend(["-t", f"{max(0.0, end - start):.6f}"])
    else:
        command.extend(["-t", os.getenv("V_EVAL_JUDGE_MAX_AUDIO_SECONDS", "120")])
    command.extend(["-vn", "-ac", "1", "-ar", "16000", "-y", str(target)])
    try:
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    return target if target.is_file() and target.stat().st_size else None


def _unique_paths(paths: list[Path | None]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if path is None or not path.is_file() or str(path) in seen:
            continue
        seen.add(str(path))
        result.append(path)
    return result


def _time_hint_ranges(value: Any, duration: float) -> list[tuple[float, float]]:
    """Parse explicit second or mm:ss ranges; prose-only hints intentionally fall back to uniform coverage."""
    text = str(value or "").strip().lower()
    if not text or text in {"全片", "整段", "whole video", "full video", "all"}:
        return []

    def seconds(token: str) -> float:
        token = token.strip()
        if ":" in token:
            minute, second = token.split(":", 1)
            return float(minute) * 60.0 + float(second)
        return float(token)

    ranges: list[tuple[float, float]] = []
    token = r"(?:\d{1,3}:\d{1,2}(?:\.\d+)?|\d+(?:\.\d+)?)"
    for match in re.finditer(rf"({token})\s*(?:s|秒)?\s*(?:-|~|–|—|to|至|到)\s*({token})\s*(?:s|秒)?", text):
        try:
            start, end = seconds(match.group(1)), seconds(match.group(2))
        except ValueError:
            continue
        start, end = max(0.0, min(start, end)), min(duration, max(start, end))
        if end > start:
            ranges.append((start, end))
    return ranges


def _d16_media_windows(payload: dict[str, Any], duration: float) -> list[MediaWindow]:
    """Select bounded, question-aware D16 windows while retaining whole-video coverage."""
    checklist = payload.get("checklist") if isinstance(payload.get("checklist"), dict) else {}
    items = checklist.get("items", []) if isinstance(checklist, dict) else []
    active = []
    hinted: list[tuple[float, float, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subpoint = str(item.get("subpoint", ""))
        if subpoint not in _D16_WINDOW_SECONDS:
            continue
        if subpoint not in active:
            active.append(subpoint)
        for start, end in _time_hint_ranges(item.get("time_hint"), duration):
            hinted.append((start, end, subpoint))
    if not active:
        active = ["realism"]

    try:
        max_windows = max(1, int(os.getenv("V_EVAL_D16_MAX_WINDOWS", "4")))
        max_total = float(os.getenv("V_EVAL_D16_MAX_TOTAL_SECONDS", "12"))
        if not math.isfinite(max_total) or max_total <= 0:
            raise ValueError("invalid D16 duration limit")
    except ValueError:
        max_windows, max_total = 4, 12.0
    length_limit = max_total / max_windows
    windows: list[MediaWindow] = []
    covered: set[str] = set()
    for hinted_start, hinted_end, reason in hinted:
        if reason in covered or len(windows) >= max_windows:
            continue
        length = min(_D16_WINDOW_SECONDS[reason], length_limit, duration)
        center = (hinted_start + hinted_end) / 2.0
        start = min(max(0.0, center - length / 2.0), max(0.0, duration - length))
        windows.append(MediaWindow(start, min(duration, start + length), (reason,)))
        covered.add(reason)

    remaining_slots = max_windows - len(windows)
    if remaining_slots > 0:
        slot_span = duration / remaining_slots
        uncovered = [reason for reason in active if reason not in covered]
        for index in range(remaining_slots):
            reason = uncovered[index] if index < len(uncovered) else active[index % len(active)]
            length = min(_D16_WINDOW_SECONDS[reason], length_limit, duration)
            center = (index + 0.5) * slot_span
            start = min(max(0.0, center - length / 2.0), max(0.0, duration - length))
            windows.append(MediaWindow(start, min(duration, start + length), (reason,)))

    return sorted(windows, key=lambda item: item.start)


def _append_target_frames(content: list[dict[str, Any]], frames: list[TimedFrame], *, window_id: str | None = None) -> None:
    for index, frame in enumerate(frames, start=1):
        prefix = f"{window_id}-" if window_id else ""
        content.append({"type": "text", "text": f"Target frame {prefix}F{index:02d}; exact video timestamp={frame.timestamp:.3f}s."})
        content.append(_image_block(frame.path))


def _build_d16_content(content: list[dict[str, Any]], payload: dict[str, Any], case: CaseLike,
                       temp_dir: Path) -> None:
    video = case.video_path or Path("")
    duration = _duration(video)
    if duration <= 0:
        raise MediaPreparationError("D16 target video duration is unavailable")
    windows = _d16_media_windows(payload, duration)
    if not windows:
        raise MediaPreparationError("D16 produced no usable synchronized media windows")
    manifest = []
    for index, window in enumerate(windows, start=1):
        window_id = f"W{index:02d}"
        frames = _extract_video_frames(video, temp_dir, fps=2.0, limit=6, size=448, quality=90,
                                       label=window_id, start=window.start, end=window.end)
        audio = _extract_video_audio(video, temp_dir, f"{window_id}-audio", start=window.start, end=window.end)
        if not frames or audio is None:
            raise MediaPreparationError(
                f"D16 failed to extract aligned image/audio media for {window_id} "
                f"[{window.start:.3f}, {window.end:.3f}]s"
            )
        manifest.append({"id": window_id, "start_seconds": round(window.start, 3),
                         "end_seconds": round(window.end, 3), "question_types": list(window.reasons),
                         "frame_timestamps": [round(frame.timestamp, 3) for frame in frames]})
        content.append({"type": "text", "text": (
            f"Synchronized D16 window {window_id}: [{window.start:.3f}, {window.end:.3f}]s; "
            f"question types={','.join(window.reasons)}. The following frames and audio are cut from exactly this interval."
        )})
        _append_target_frames(content, frames, window_id=window_id)
        content.append({"type": "text", "text": (
            f"Target audio {window_id}; exact video interval=[{window.start:.3f}, {window.end:.3f}]s; 16 kHz mono."
        )})
        content.append(_audio_block(audio))
    content.insert(1, {"type": "text", "text": "D16 synchronized media manifest:\n" + _json_text(manifest)})


def build_judge_content(prompt: str, payload: dict[str, Any], case: CaseLike, modality: str,
                        media_env: str = "V_EVAL_JUDGE_MEDIA", default_media: str = "1",
                        allow_media: bool = True) -> list[dict[str, Any]]:
    """Build timestamped media and refuse answer-stage requests without required target media."""
    content: list[dict[str, Any]] = [{"type": "text", "text": _json_text(payload)}]
    if not allow_media:
        return content
    if os.getenv(media_env, default_media).lower() in {"0", "false", "no", "off"}:
        raise MediaPreparationError(f"judge media is disabled by {media_env}")

    include_audio = modality in {"audio", "audio_visual"}
    include_images = modality in {"vision", "audio_visual"}
    video = case.video_path or Path("")
    if not video.is_file():
        raise MediaPreparationError("target video file is unavailable")

    with tempfile.TemporaryDirectory(prefix="v-eval-judge-") as temp:
        temp_dir = Path(temp)
        dimension = str((payload.get("checklist") or {}).get("dimension", "")) if isinstance(payload.get("checklist"), dict) else ""
        if modality == "audio_visual" and dimension == "16_audio_visual_sync":
            _build_d16_content(content, payload, case, temp_dir)
        else:
            if include_images:
                frames = _extract_video_frames(video, temp_dir, fps=2.0, limit=32,
                                               size=640, quality=90, label="target")
                if not frames:
                    raise MediaPreparationError("target video frames could not be extracted")
                content.append({"type": "text", "text": (
                    "Target frames are uniformly sampled over the complete video. "
                    "Each image is preceded by its exact timestamp."
                )})
                _append_target_frames(content, frames)
            if include_audio:
                extracted = _extract_video_audio(video, temp_dir, "target-audio")
                if extracted is None:
                    raise MediaPreparationError("target video audio could not be extracted")
                content.append({"type": "text", "text": "Target audio begins at video timestamp 0.000s; 16 kHz mono."})
                content.append(_audio_block(extracted))

        image_paths = _unique_paths([case.first_frame, case.last_frame, *case.reference_images])
        for index, path in enumerate(image_paths, start=1):
            try:
                content.append({"type": "text", "text": f"Condition/reference image {index}; this is not a target-video frame."})
                content.append(_image_block(path))
            except (OSError, ValueError):
                continue
        for index, path in enumerate(_unique_paths([*case.reference_audios])[:2] if dimension != "16_audio_visual_sync" else [], start=1):
            try:
                content.append({"type": "text", "text": f"Reference audio {index}; this is not the target-video audio."})
                content.append(_audio_block(path))
            except (OSError, ValueError):
                continue
        return content
