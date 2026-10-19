from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run import (DEFAULT_DIMS, ROOT, load_yaml, missing_required_images, partition_ready_cases,
                 resolve_task_paths, run_checklist, run_evaluate, run_score, validate_cases_ready,
                 validate_task)
from v_eval.core import Case, ConfigError, discover_cases
from v_eval.judge_media import build_judge_content


class LocalWorkflowTests(unittest.TestCase):
    def test_all_seven_configs_load_and_discover_case_dirs(self) -> None:
        dims = load_yaml(DEFAULT_DIMS)
        for number in (13, 14, 15, 16, 17, 18, 20):
            with self.subTest(dimension=number):
                path = ROOT / "configs" / f"task_d{number}_local.yaml"
                task = resolve_task_paths(load_yaml(path), path)
                validate_task(task, dims)
                self.assertEqual({item["mode"] for item in task["inputs"]},
                                 {"t2va", "f2va", "l2va", "fl2va", "r2va"})
                self.assertIsInstance(discover_cases(task), list)

    def test_incomplete_case_is_rejected_before_judge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt_final.txt"
            prompt.write_text("A person speaks", encoding="utf-8")
            case = Case("case1", root, "t2va", prompt, None)
            with self.assertRaisesRegex(ConfigError, "video.mp4"):
                validate_cases_ready([case])
            video = root / "video.mp4"
            video.write_bytes(b"placeholder")
            case.video_path = video
            validate_cases_ready([case])

    def test_image_modes_without_images_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt_final.txt"
            video = root / "video.mp4"
            prompt.write_text("edit the subject", encoding="utf-8")
            video.write_bytes(b"placeholder")
            missing = Case("no_image", root, "f2va", prompt, video)
            ready_case = Case("with_image", root, "f2va", prompt, video, first_frame=root / "input_01.png")
            r2va_missing = Case("r2va_no_ref", root, "r2va", prompt, video)
            r2va_ready = Case("r2va_ok", root, "r2va", prompt, video, reference_images=[root / "input_01.png"])
            (root / "input_01.png").write_bytes(b"png")
            self.assertEqual(missing_required_images(missing), ["input_01 image"])
            self.assertEqual(missing_required_images(ready_case), [])
            self.assertEqual(missing_required_images(r2va_missing), ["reference image"])
            self.assertEqual(missing_required_images(r2va_ready), [])
            ready, skipped = partition_ready_cases([missing, ready_case, r2va_missing, r2va_ready])
            self.assertEqual([case.case_id for case in ready], ["with_image", "r2va_ok"])
            self.assertEqual([case.case_id for case in skipped], ["no_image", "r2va_no_ref"])

    def test_unnumbered_reference_prompt_keeps_every_input_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "r2va"
            case_dir = root / "case1"
            case_dir.mkdir(parents=True)
            (case_dir / "prompt_final.txt").write_text("以参考图为首帧，保持原图构图。", encoding="utf-8")
            (case_dir / "video.mp4").write_bytes(b"placeholder")
            (case_dir / "input_01.png").write_bytes(b"png")
            (case_dir / "input_02.jpg").write_bytes(b"jpg")
            task = {"inputs": [{
                "id": "r2va", "root": str(root), "mode": "r2va",
                "prompt_filename": "prompt_final.txt", "video_filename": "video.mp4",
                "references": {"image_pattern": "input_{index:02d}"},
            }]}
            found = discover_cases(task)
            self.assertEqual([path.name for path in found[0].reference_images], ["input_01.png", "input_02.jpg"])
            numbered = case_dir / "prompt_final.txt"
            numbered.write_text("只使用参考图1，不要使用其他图。", encoding="utf-8")
            found = discover_cases(task)
            self.assertEqual([path.name for path in found[0].reference_images], ["input_01.png"])

    def test_each_dimension_produces_a_score_with_valid_judge_responses(self) -> None:
        dims = load_yaml(DEFAULT_DIMS)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt_final.txt"
            video = root / "video.mp4"
            prompt.write_text("test prompt", encoding="utf-8")
            video.write_bytes(b"placeholder; judge media is mocked")
            case = Case("case1", root, "t2va", prompt, video, task_id="t2va")
            for number in (13, 14, 15, 16, 17, 18, 20):
                with self.subTest(dimension=number):
                    path = ROOT / "configs" / f"task_d{number}_local.yaml"
                    task = resolve_task_paths(load_yaml(path), path)
                    task["output_dir"] = str(root / f"d{number}")
                    dimension_cfg = dims["dimensions"][task["dimension"]]
                    subpoint = next(iter(dimension_cfg["subpoints"]))
                    gates = dimension_cfg["gates"]
                    checklist = {
                        "version": 2, "dimension": task["dimension"], "case_id": case.case_id,
                        "judge_mode": "external",
                        "facts": {name: True for name in dimension_cfg["facts"]},
                        "gates": gates,
                        "items": [{"id": "q1", "subpoint": subpoint, "kind": "rubric_5", "core": True}],
                    }
                    answers = {
                        "status": "ok", "source": "judge", "answers": [{"id": "q1", "score": 5}],
                        "gates": [{"id": gate["id"], "answer": gate["expect"]} for gate in gates],
                    }
                    generator = "v_eval.workflow.generate_d18_checklist" if number == 18 else "v_eval.workflow.generate_model_checklist"
                    with patch(generator, return_value=checklist), patch("v_eval.workflow.answer_checklist", return_value=answers):
                        run_checklist(task, dims, [case], force=True)
                        results = run_evaluate(task, dims, [case], force=True)
                    summary = run_score(task, [case])
                    self.assertEqual(results[0]["status"], "ok")
                    self.assertEqual(results[0]["score"], 5.0)
                    self.assertEqual(summary["scored"], 1)

    def test_installed_ffmpeg_prepares_vision_audio_and_sync_media(self) -> None:
        local_bin = ROOT / ".runtime" / "ffmpeg" / "bin"
        ffmpeg = local_bin / "ffmpeg.exe"
        ffprobe = local_bin / "ffprobe.exe"
        if not ffmpeg.is_file() or not ffprobe.is_file():
            self.skipTest("project-local FFmpeg is not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            subprocess.run([
                str(ffmpeg), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                "color=c=blue:s=128x128:r=5:d=1", "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=16000:duration=1", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video),
            ], check=True, capture_output=True)
            case = Case("smoke", root, "t2va", None, video)
            with patch.dict(os.environ, {"PATH": str(local_bin) + os.pathsep + os.environ.get("PATH", "")}):
                for modality, dimension in (("vision", "13_style_visual_control"),
                                            ("audio", "15_audio_quality_control"),
                                            ("audio_visual", "16_audio_visual_sync")):
                    with self.subTest(modality=modality):
                        content = build_judge_content("test", {"checklist": {"dimension": dimension}},
                                                      case, modality)
                        types = {item["type"] for item in content}
                        if modality != "audio":
                            self.assertIn("image_url", types)
                        if modality != "vision":
                            self.assertIn("input_audio", types)


if __name__ == "__main__":
    unittest.main()
