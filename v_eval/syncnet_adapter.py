#!/usr/bin/env python3
"""Run Oxford SyncNet v2 on the speech windows supplied by the D16 evaluator.

The evaluator sends one JSON object on stdin and expects one JSON object on
stdout. Weights are the official research release (CC BY). The physical card
comes from V_EVAL_SYNCNET_GPU and is the only device this process can see.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FRAME_RATE = 25


def _select_device() -> str:
    choice = os.environ.get("V_EVAL_SYNCNET_GPU", "3").strip().lower()
    if choice in {"cpu", "none", "-1"}:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        return "cpu"
    if not choice.isdigit():
        _fail(f"V_EVAL_SYNCNET_GPU must be a card index or cpu, got: {choice}")
    os.environ["CUDA_VISIBLE_DEVICES"] = choice
    return "cuda"


def _fail(reason: str) -> None:
    json.dump({"status": "error", "reason": reason}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    raise SystemExit(0)


def _cut_clip(video: Path, start: float, end: float, dest: Path) -> None:
    completed = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
            "-i", str(video),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-ar", "16000",
            str(dest),
        ],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "ffmpeg failed").strip()
        raise RuntimeError(detail[:500])


def main() -> None:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        _fail(f"request is not JSON: {exc}")
    if not isinstance(request, dict):
        _fail("request must be a JSON object")
    video = Path(str(request.get("video_path") or ""))
    windows = request.get("windows")
    weights = Path(str(request.get("weights_path") or os.environ.get("V_EVAL_SYNCNET_WEIGHTS") or ""))
    if not video.is_file():
        _fail(f"video not found: {video}")
    if not isinstance(windows, list) or not windows:
        _fail("request has no speech windows")
    if not weights.is_file():
        _fail(f"SyncNet weights not found: {weights}")
    face_weights = weights.parent / "sfd_face.pth"
    if not face_weights.is_file():
        _fail(f"S3FD face weights not found: {face_weights}")

    device = _select_device()
    from syncnet_python import SyncNetPipeline

    pipeline = SyncNetPipeline(
        {
            "s3fd_weights": str(face_weights),
            "syncnet_weights": str(weights),
            # The evaluator windows are about 2 seconds, which is 50 frames at
            # 25 fps. The package default requires a track longer than 50 frames.
            "min_track": 20,
            "min_face_size": 40,
        },
        device=device,
    )
    scored: list[dict[str, float]] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="syncnet-") as temp_dir:
        for index, window in enumerate(windows):
            if not isinstance(window, dict):
                continue
            try:
                start = float(window["start"])
                end = float(window["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if end - start < 0.5:
                errors.append(f"window {index} is shorter than 0.5s")
                continue
            clip = Path(temp_dir) / f"window_{index}.mp4"
            try:
                _cut_clip(video, start, end, clip)
                with contextlib.redirect_stdout(sys.stderr):
                    offsets, confidences, _dists, _best, _min_dist, _raw, has_face = pipeline.inference(
                        str(clip), audio_path=None, cache_dir=str(Path(temp_dir) / f"cache_{index}"),
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"window {index}: {exc}")
                continue
            if not has_face or not confidences:
                errors.append(f"window {index}: SyncNet found no face track")
                continue
            best = max(range(len(confidences)), key=confidences.__getitem__)
            scored.append({
                "start": round(start, 6),
                "end": round(end, 6),
                "confidence": round(float(confidences[best]), 6),
                "offset_ms": round(float(offsets[best]) * 1000.0 / FRAME_RATE, 3),
            })
    if not scored:
        _fail("; ".join(errors) or "SyncNet produced no confidence")
    confidence = sum(row["confidence"] for row in scored) / len(scored)
    offset_ms = sum(row["offset_ms"] for row in scored) / len(scored)
    json.dump(
        {
            "status": "ok",
            "confidence": round(confidence, 6),
            "offset_ms": round(offset_ms, 3),
            "windows": scored,
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
