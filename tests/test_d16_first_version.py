from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v_eval.core import Case, answer_checklist, evaluate_case, score_subpoint
from v_eval.judge_media import (MediaPreparationError, _d16_media_windows, _extract_video_frames,
                                _uniform_timestamps, build_judge_content)
from v_eval.model_components import syncnet_component


class _NoCallJudge:
    online = True
    model = "test-judge"
    modality = "audio_visual"

    def complete(self, *args, **kwargs):  # pragma: no cover - failure guard
        raise AssertionError("judge must not be called when media preparation fails")


class MediaProtocolTests(unittest.TestCase):
    def test_uniform_timestamps_cover_complete_interval_when_limited(self) -> None:
        timestamps = _uniform_timestamps(0.0, 10.0, fps=2.0, limit=5)
        self.assertEqual(timestamps, [1.0, 3.0, 5.0, 7.0, 9.0])

    def test_d16_windows_are_question_aware_and_bounded(self) -> None:
        payload = {
            "checklist": {
                "items": [
                    {"subpoint": "lip_sync", "time_hint": "1.0-2.0s"},
                    {"subpoint": "multi_speaker_match", "time_hint": "全片"},
                    {"subpoint": "audio_change_alignment", "time_hint": "8秒至9秒"},
                    {"subpoint": "realism", "time_hint": "全片"},
                ]
            }
        }
        with patch.dict(os.environ, {"V_EVAL_D16_MAX_WINDOWS": "4", "V_EVAL_D16_MAX_TOTAL_SECONDS": "8"}):
            windows = _d16_media_windows(payload, 10.0)
        self.assertLessEqual(len(windows), 4)
        self.assertLessEqual(sum(window.end - window.start for window in windows), 8.000001)
        reasons = {reason for window in windows for reason in window.reasons}
        self.assertIn("lip_sync", reasons)
        self.assertIn("audio_change_alignment", reasons)

    def test_repeated_hints_do_not_exclude_other_question_types(self) -> None:
        payload = {"checklist": {"items": [
            {"subpoint": "lip_sync", "time_hint": f"{index}-{index + 1}s"} for index in range(4)
        ] + [{"subpoint": "audio_change_alignment", "time_hint": "8-9s"}]}}
        windows = _d16_media_windows(payload, 10.0)
        self.assertIn("audio_change_alignment", {reason for window in windows for reason in window.reasons})
        self.assertLessEqual(sum(window.end - window.start for window in windows), 12.0)

    def test_invalid_window_limit_falls_back_to_safe_defaults(self) -> None:
        with patch.dict(os.environ, {"V_EVAL_D16_MAX_WINDOWS": "bad",
                                  "V_EVAL_D16_MAX_TOTAL_SECONDS": "nan"}):
            windows = _d16_media_windows({"checklist": {"items": []}}, 10.0)
        self.assertTrue(windows)
        self.assertLessEqual(len(windows), 4)

    def test_partial_frame_extraction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "video.mp4"
            video.write_bytes(b"video")
            with patch("v_eval.judge_media._duration", return_value=2.0), \
                    patch("v_eval.judge_media._extract_one_frame", side_effect=[True, False]):
                frames = _extract_video_frames(video, Path(directory), fps=2.0, limit=2,
                                               size=448, quality=90, label="target")
        self.assertEqual(frames, [])

    def test_disabled_answer_media_raises_instead_of_sending_prompt_only(self) -> None:
        case = SimpleNamespace(
            video_path=Path("/does/not/matter.mp4"), first_frame=None, last_frame=None,
            reference_images=[], reference_videos=[], reference_audios=[],
        )
        with patch.dict(os.environ, {"V_EVAL_JUDGE_MEDIA": "0"}):
            with self.assertRaises(MediaPreparationError):
                build_judge_content("prompt", {"checklist": {}}, case, "vision")

    def test_answer_checklist_returns_media_error_without_calling_judge(self) -> None:
        case = Case("case", Path("."), "t2va", None, Path("/missing.mp4"))
        checklist = {"dimension": "16_audio_visual_sync", "gates": [], "items": []}
        with patch.dict(os.environ, {"V_EVAL_JUDGE_MEDIA": "0"}):
            result = answer_checklist(checklist, "prompt", case, _NoCallJudge())
        self.assertEqual(result["status"], "media_error")
        self.assertEqual(result["answers"], [])

    def test_d16_audio_extraction_failure_never_calls_judge(self) -> None:
        case = Case("case", Path("."), "t2va", None, Path("/missing.mp4"))
        checklist = {"dimension": "16_audio_visual_sync", "gates": [], "items": []}
        with patch("v_eval.judge_media.Path.is_file", return_value=True), \
                patch("v_eval.judge_media._duration", return_value=5.0), \
                patch("v_eval.judge_media._extract_video_frames", return_value=[SimpleNamespace(
                    path=Path("/missing.jpg"), timestamp=1.0)]), \
                patch("v_eval.judge_media._extract_video_audio", return_value=None):
            result = answer_checklist(checklist, "prompt", case, _NoCallJudge())
        self.assertEqual(result["status"], "media_error")
        self.assertIn("aligned image/audio", result["error"])

    def test_media_error_produces_no_case_score_even_with_numeric_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            video.write_bytes(b"video")
            case = Case("case", root, "t2va", None, video)
            dimension = "16_audio_visual_sync"
            task = {"dimension": dimension, "output_dir": str(root), "run_name": "test"}
            checklist = {"version": 2, "dimension": dimension, "case_id": "case", "judge_mode": "external",
                         "facts": {"dialogues": True}, "gates": [], "items": []}
            output = root / "runs" / "test" / dimension / "case"
            output.mkdir(parents=True)
            (output / "checklist.json").write_text(__import__("json").dumps(checklist))
            (output / "facts.json").write_text('{"dialogues": true}')
            with patch("v_eval.core.answer_checklist", return_value={"status": "media_error", "source": "judge",
                                                                      "error": "audio unavailable", "answers": [], "gates": []}), \
                    patch("v_eval.core.run_component", side_effect=AssertionError("numeric component must not run")):
                result = evaluate_case(task, {"subpoints": {"lip_sync": {"components": {"syncnet_conf": 1.0}}}},
                                       case, {}, force=False)
            self.assertEqual(result["status"], "media_error")
            self.assertIsNone(result["score"])
            self.assertEqual(result["subpoints"], {})


class SyncNetAdapterTests(unittest.TestCase):
    def test_unconfigured_syncnet_is_safe_fallback_status(self) -> None:
        case = SimpleNamespace(video_path=Path("/missing.mp4"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("V_EVAL_SYNCNET_COMMAND", None)
            result = syncnet_component(case, {"dialogues": True})
        self.assertEqual(result["status"], "not_configured")
        self.assertIsNone(result["score"])

    def test_real_adapter_protocol_maps_confidence_and_keeps_offset(self) -> None:
        command = (
            f"{sys.executable} -c 'import json,sys; json.load(sys.stdin); "
            "print(json.dumps({\"status\":\"ok\",\"confidence\":6.0,\"offset_ms\":-40}))'"
        )
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "video.mp4"
            audio = Path(directory) / "audio.wav"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")
            case = SimpleNamespace(video_path=video)
            with patch.dict(os.environ, {"V_EVAL_SYNCNET_COMMAND": command}, clear=False), \
                    patch("v_eval.model_components._ffprobe_duration", return_value=5.0), \
                    patch("v_eval.model_components.extract_audio", return_value=audio), \
                    patch("v_eval.model_components._silero_speech_intervals", return_value=([(1.0, 3.0)], None)), \
                    patch("v_eval.model_components._visible_face_windows", side_effect=lambda windows, case: (windows, None)):
                result = syncnet_component(case, {"dialogues": True})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["score"], 4.0)
        self.assertEqual(result["confidence"], 6.0)
        self.assertEqual(result["offset_ms"], -40.0)
        self.assertEqual(result["method"], "syncnet_v2_external_adapter")

    def test_not_configured_component_is_excluded_from_weighted_score(self) -> None:
        checklist = {
            "items": [{"id": "q1", "subpoint": "lip_sync", "kind": "yes_no",
                       "expect": "yes", "weight": 1.0, "core": False}]
        }
        answers = {"answers": [{"id": "q1", "answer": "yes"}]}
        case = Case("case", Path("."), "t2va", None, None)
        config = {"applies": "facts.dialogues", "components": {"checklist": 0.7, "syncnet_conf": 0.3}}
        unavailable = {"component": "syncnet_conf", "status": "not_configured", "score": None}
        with patch("v_eval.core.run_component", return_value=unavailable):
            result = score_subpoint({}, "lip_sync", config, checklist, answers, case,
                                    {"dialogues": True}, True, {"unanswered_excluded": True})
        self.assertEqual(result["score"], 5.0)
        self.assertEqual(result["components"]["syncnet_conf"]["status"], "not_configured")


if __name__ == "__main__":
    unittest.main()
