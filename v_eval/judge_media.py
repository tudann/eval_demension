from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol


class CaseLike(Protocol):
    video_path: Path | None
    first_frame: Path | None
    last_frame: Path | None
    reference_images: list[Path]
    reference_videos: list[Path]
    reference_audios: list[Path]


# OpenAI-compatible chat APIs commonly accept image_url data URIs and
# input_audio blocks. Video is represented by sampled frames so the same
# request works with local Qwen-VL servers and external gateways.
_IMAGE_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_AUDIO_FORMAT = {".wav": "wav", ".mp3": "mp3", ".m4a": "mp4", ".flac": "flac", ".ogg": "ogg"}


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _image_block(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    mime = _IMAGE_MIME.get(suffix, mimetypes.guess_type(path.name)[0] or "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def _audio_block(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    audio_format = _AUDIO_FORMAT.get(suffix, "wav")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "input_audio", "input_audio": {"data": encoded, "format": audio_format}}


def _extract_video_frames(video: Path, directory: Path, limit: int, label: str) -> list[Path]:
    if not video.is_file() or limit <= 0:
        return []
    duration = 0.0
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        duration = max(0.1, float(probe.stdout.strip()))
    except (OSError, ValueError, subprocess.SubprocessError):
        duration = float(limit)
    fps = max(0.1, min(2.0, limit / duration))
    frame_dir = directory / label
    frame_dir.mkdir(parents=True, exist_ok=True)
    pattern = frame_dir / "frame-%02d.jpg"
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps:.6f},scale=768:-2:force_original_aspect_ratio=decrease", "-frames:v", str(limit), "-q:v", "5", str(pattern)],
            capture_output=True, text=True, check=True, timeout=180,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted(frame_dir.glob("frame-*.jpg"))[:limit]


def _extract_video_audio(video: Path, directory: Path, label: str) -> Path | None:
    if not video.is_file():
        return None
    target = directory / f"{label}.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-t", "120", "-y", str(target)],
            capture_output=True, text=True, check=True, timeout=180,
        )
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


def _max_frames() -> int:
    try:
        return max(0, int(os.getenv("V_EVAL_JUDGE_MAX_FRAMES", "6")))
    except ValueError:
        return 6


def build_judge_content(prompt: str, payload: dict[str, Any], case: CaseLike, modality: str,
                        media_env: str = "V_EVAL_JUDGE_MEDIA", default_media: str = "1") -> list[dict[str, Any]]:
    """Build a portable multimodal user message for a judge request."""
    content: list[dict[str, Any]] = [{"type": "text", "text": _json_text(payload)}]
    if os.getenv(media_env, default_media).lower() in {"0", "false", "no", "off"}:
        return content

    max_frames = _max_frames()
    include_audio = modality in {"audio", "audio_visual"}
    include_images = modality in {"vision", "audio_visual"}
    with tempfile.TemporaryDirectory(prefix="v-eval-judge-") as temp:
        temp_dir = Path(temp)
        if include_images:
            frame_paths = _extract_video_frames(case.video_path or Path(""), temp_dir, max_frames, "target")
            reference_frame_paths: list[Path] = []
            for index, video in enumerate(getattr(case, "reference_videos", []), start=1):
                reference_frame_paths.extend(_extract_video_frames(video, temp_dir, max_frames, f"reference-{index}"))
            image_paths = _unique_paths([case.first_frame, case.last_frame, *case.reference_images])
            for path in [*frame_paths, *reference_frame_paths, *image_paths]:
                try:
                    content.append(_image_block(path))
                except (OSError, ValueError):
                    continue
        if include_audio:
            audio_paths = _unique_paths([*case.reference_audios])
            extracted = _extract_video_audio(case.video_path or Path(""), temp_dir, "target-audio")
            if extracted:
                audio_paths.insert(0, extracted)
            for path in audio_paths[:3]:
                try:
                    content.append(_audio_block(path))
                except (OSError, ValueError):
                    continue
        # The blocks contain base64 data, so they remain valid after the temp
        # directory is removed.
        return content
