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
                                _fit_image_long_side, _frame_scale_filter, _uniform_timestamps,
                                build_judge_content)
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
                    {"subpoint": "action_sound_sync", "time_hint": "8秒至9秒"},
                    {"subpoint": "ambient_sound_sync", "time_hint": "全片"},
                ]
            }
        }
        with patch.dict(os.environ, {"V_EVAL_D16_MAX_WINDOWS": "4", "V_EVAL_D16_MAX_TOTAL_SECONDS": "8"}):
            windows = _d16_media_windows(payload, 10.0)
        self.assertLessEqual(len(windows), 4)
        self.assertLessEqual(sum(window.end - window.start for window in windows), 8.000001)
        reasons = {reason for window in windows for reason in window.reasons}
        self.assertIn("lip_sync", reasons)
        self.assertIn("action_sound_sync", reasons)
        self.assertIn("ambient_sound_sync", reasons)

    def test_repeated_hints_do_not_exclude_other_question_types(self) -> None:
        payload = {"checklist": {"items": [
            {"subpoint": "lip_sync", "time_hint": f"{index}-{index + 1}s"} for index in range(4)
        ] + [{"subpoint": "action_sound_sync", "time_hint": "8-9s"}]}}
        windows = _d16_media_windows(payload, 10.0)
        self.assertIn("action_sound_sync", {reason for window in windows for reason in window.reasons})
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
            with patch("v_eval.workflow.answer_checklist", return_value={"status": "media_error", "source": "judge",
                                                                      "error": "audio unavailable", "answers": [], "gates": []}), \
                    patch("v_eval.scoring.run_component", side_effect=AssertionError("numeric component must not run")):
                result = evaluate_case(task, {"subpoints": {"lip_sync": {"components": {"syncnet_conf": 1.0}}}},
                                       case, {}, force=False)
            self.assertEqual(result["status"], "media_error")
            self.assertIsNone(result["score"])
            self.assertEqual(result["subpoints"], {})

    def test_judge_error_produces_no_case_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            video.write_bytes(b"video")
            case = Case("case", root, "t2va", None, video)
            dimension = "16_audio_visual_sync"
            task = {"dimension": dimension, "output_dir": str(root), "run_name": "test"}
            checklist = {"version": 2, "dimension": dimension, "case_id": "case", "judge_mode": "external",
                         "facts": {"dialogues": True}, "gates": [],
                         "items": [{"id": "q1", "subpoint": "lip_sync", "kind": "rubric_5", "core": True}]}
            output = root / "runs" / "test" / dimension / "case"
            output.mkdir(parents=True)
            (output / "checklist.json").write_text(__import__("json").dumps(checklist))
            (output / "facts.json").write_text('{"dialogues": true}')
            with patch("v_eval.workflow.answer_checklist", return_value={"status": "error", "source": "judge",
                                                                      "error": "service unavailable", "answers": [], "gates": []}):
                result = evaluate_case(task, {"subpoints": {"lip_sync": {"components": {"checklist": 1.0}}}},
                                       case, {}, force=False)
            self.assertEqual(result["status"], "judge_error")
            self.assertIsNone(result["score"])
            self.assertEqual(result["subpoints"], {})
            with patch("v_eval.workflow.answer_checklist", return_value={"status": "ok", "source": "judge",
                                                                    "answers": [{"id": "q1", "score": 4}], "gates": []}):
                retry = evaluate_case(task, {"subpoints": {"lip_sync": {"components": {"checklist": 1.0}}}},
                                      case, {}, force=False)
            self.assertEqual(retry["status"], "ok")
            self.assertEqual(retry["score"], 4.0)

    def test_d20_bounds_the_long_side_while_other_dimensions_keep_width_scaling(self) -> None:
        self.assertEqual(_frame_scale_filter(640), "scale=640:-2:force_original_aspect_ratio=decrease")
        self.assertEqual(
            _frame_scale_filter(640, "long_side"),
            "scale=640:640:force_original_aspect_ratio=decrease",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            video.write_bytes(b"video")
            reference = root / "input_01.png"
            from PIL import Image
            Image.new("RGB", (800, 1200), "white").save(reference)
            case = SimpleNamespace(
                video_path=video, first_frame=reference, last_frame=None,
                reference_images=[], reference_videos=[], reference_audios=[],
            )
            frame = SimpleNamespace(path=reference, timestamp=0.0)
            calls: list[str] = []

            def capture_frames(*_args, **kwargs):
                calls.append(kwargs["bound"])
                return [frame]

            with patch("v_eval.judge_media._extract_video_frames", side_effect=capture_frames), \
                    patch("v_eval.judge_media._extract_video_audio", return_value=root / "audio.wav"), \
                    patch("v_eval.judge_media._audio_block", return_value={"type": "input_audio"}):
                (root / "audio.wav").write_bytes(b"audio")
                d18 = build_judge_content("prompt", {"checklist": {"dimension": "18_text_visual_consistency"}}, case, "vision")
                d20 = build_judge_content("prompt", {"checklist": {"dimension": "20_performance_emotion"}}, case, "audio_visual")
            self.assertEqual(calls, ["width", "long_side"])
            self.assertTrue(any("input_01" in str(block) for block in d18 if isinstance(block, dict)))
            fitted = [block for block in d20 if isinstance(block, dict) and str(block.get("image_url", {})).find("image/jpeg") >= 0]
            self.assertGreaterEqual(len(fitted), 1)

    def test_long_side_fit_shrinks_portrait_stills_only(self) -> None:
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tall.png"
            Image.new("RGB", (800, 1200), "white").save(source)
            fitted = _fit_image_long_side(source, root / "fitted.jpg", 640)
            with Image.open(fitted) as image:
                self.assertLessEqual(max(image.size), 640)
                self.assertEqual(image.size[1], 640)

    def test_missing_gate_answer_is_incomplete_not_passed(self) -> None:
        from v_eval.core import gate_result

        checklist = {"gates": [{"id": "g1", "expect": "yes"}]}
        self.assertIsNone(gate_result(checklist, {"gates": []})["passed"])


class SyncNetAdapterTests(unittest.TestCase):
    def test_unconfigured_syncnet_is_safe_fallback_status(self) -> None:
        case = SimpleNamespace(video_path=Path("/missing.mp4"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("V_EVAL_SYNCNET_COMMAND", None)
            result = syncnet_component(case, {"dialogues": True})
        self.assertEqual(result["status"], "not_configured")
        self.assertIsNone(result["score"])

    def test_real_adapter_protocol_maps_confidence_and_keeps_offset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory) / "adapter.py"
            adapter.write_text(
                'import json, sys\njson.load(sys.stdin)\n'
                'print(json.dumps({"status": "ok", "confidence": 6.0, "offset_ms": -40}))\n',
                encoding="utf-8",
            )
            command = f'"{Path(sys.executable).as_posix()}" "{adapter.as_posix()}"'
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
        answers = {"answers": [{"id": "q1", "score": 5}]}
        case = Case("case", Path("."), "t2va", None, None)
        config = {"applies": "facts.dialogues", "components": {"checklist": 0.7, "syncnet_conf": 0.3}}
        unavailable = {"component": "syncnet_conf", "status": "not_configured", "score": None}
        with patch("v_eval.scoring.run_component", return_value=unavailable):
            result = score_subpoint({}, "lip_sync", config, checklist, answers, case,
                                    {"dialogues": True}, True, {})
        self.assertEqual(result["score"], 4.0)
        self.assertEqual(result["score_basis"], "checklist_only")
        self.assertEqual(result["components"]["syncnet_conf"]["status"], "not_configured")


if __name__ == "__main__":
    unittest.main()
