from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import tempfile
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
                          size: int, quality: int, label: str, midpoint: bool = False) -> list[Path]:
    if not video.is_file() or limit <= 0:
        return []
    duration = _duration(video)
    if duration <= 0:
        return []
    frame_dir = directory / label
    frame_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    duration = _duration(video)
    count = min(limit, max(1, int(round(duration * fps))))
    timestamps = [min(max(0.0, (index + 0.5) / fps), max(0.0, duration - 0.001)) for index in range(count)]
    for index, timestamp in enumerate(timestamps):
        target = frame_dir / f"frame-{index:03d}.jpg"
        if _extract_one_frame(video, timestamp, target, size, quality):
            paths.append(target)
    return paths


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


def build_judge_content(prompt: str, payload: dict[str, Any], case: CaseLike, modality: str,
                        media_env: str = "V_EVAL_JUDGE_MEDIA", default_media: str = "1",
                        allow_media: bool = True) -> list[dict[str, Any]]:
    """Build media according to the documented visual/audio/audio-visual judge protocol."""
    content: list[dict[str, Any]] = [{"type": "text", "text": _json_text(payload)}]
    if not allow_media or os.getenv(media_env, default_media).lower() in {"0", "false", "no", "off"}:
        return content

    include_audio = modality in {"audio", "audio_visual"}
    include_images = modality in {"vision", "audio_visual"}
    with tempfile.TemporaryDirectory(prefix="v-eval-judge-") as temp:
        temp_dir = Path(temp)
        if include_images:
            if modality == "audio_visual":
                frames = _extract_video_frames(case.video_path or Path(""), temp_dir, fps=1.0, limit=12,
                                               size=448, quality=90, label="target")
            else:
                frames = _extract_video_frames(case.video_path or Path(""), temp_dir, fps=2.0, limit=32,
                                               size=640, quality=90, label="target")
            image_paths = _unique_paths([case.first_frame, case.last_frame, *case.reference_images])
            for path in [*frames, *image_paths]:
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
        return content
