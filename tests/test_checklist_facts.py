from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from unittest.mock import patch

from v_eval.core import (
    Case,
    _d18_checklist_payload,
    _model_checklist_payload,
    checklist_component,
    dimension_score,
    score_subpoint,
)


ROOT = Path(__file__).resolve().parents[1]
DIMS = yaml.safe_load((ROOT / "configs" / "dims_13_18.yaml").read_text(encoding="utf-8"))["dimensions"]


def _case(case_id: str = "case", first_frame: Path | None = None) -> Case:
    return Case(case_id, Path("."), "f2va" if first_frame else "t2va", None, None, first_frame)


def _gates(dimension: str) -> list[dict]:
    return [
        {"id": gate["id"], "question": gate["question"], "expect": True, "modality": gate["modality"], "core": True}
        for gate in DIMS[dimension]["gates"]
    ]


def _item(index: int, subpoint: str, question: str, core: bool = False) -> dict:
    return {"id": f"i{index}", "subpoint": subpoint, "question": question, "kind": "rubric_5", "core": core}


class ChecklistFactAliasTests(unittest.TestCase):
    def test_d13_alias_keys_keep_lighting_and_color_items(self) -> None:
        dimension = "13_style_visual_control"
        payload = {
            "facts": {
                "style_requirement": "超写实",
                "lighting_requirement": "电影光影",
                "color_requirement": "深红色背景",
            },
            "gates": _gates(dimension),
            "items": [
                _item(1, "style_accuracy", "风格是否达到超写实？"),
                _item(2, "style_persistence", "超写实风格是否全程稳定？"),
                _item(3, "lighting_control", "光照是否达到电影光影？"),
                _item(4, "color_control", "色彩是否达到深红色背景？"),
                _item(5, "style_content_compat", "风格是否保留人物主体？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["target_lighting"], "电影光影")
        self.assertEqual(checklist["facts"]["target_colors"], "深红色背景")
        self.assertEqual(checklist["facts"]["style_spec"], "超写实")
        self.assertEqual(len(checklist["items"]), 5)
        self.assertTrue(all(item["kind"] == "rubric_5" for item in checklist["items"]))

    def test_d15_music_and_sfx_aliases_enable_conditional_items(self) -> None:
        dimension = "15_audio_quality_control"
        payload = {
            "facts": {"music_requirement": "童话风格配乐", "sfx_requirement": "叮一声的问号音效"},
            "gates": _gates(dimension),
            "items": [
                _item(1, "music_match", "配乐是否达到童话风格？"),
                _item(2, "action_sfx", "动作音效是否达到叮一声的问号音效？"),
                _item(3, "voice_naturalness", "人声是否自然？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertIs(checklist["facts"]["music_required"], True)
        self.assertEqual(checklist["facts"]["music_description"], "童话风格配乐")
        self.assertEqual(checklist["facts"]["sfx"], "叮一声的问号音效")
        self.assertEqual(checklist["facts"]["sfx_description"], "叮一声的问号音效")

    def test_d16_dialogue_alias_enables_lip_sync(self) -> None:
        dimension = "16_audio_visual_sync"
        payload = {
            "facts": {"dialogue": "啊，故事挺好的。", "audio_layers": "人声清晰，背景音乐轻微"},
            "gates": _gates(dimension),
            "items": [
                _item(1, "lip_sync", "口型是否与台词同步？"),
                _item(2, "realism", "音画关系是否自然？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["dialogues"], "啊，故事挺好的。")
        self.assertIs(checklist["facts"]["realistic"], True)

    def test_d17_motion_aliases_enable_conditional_items(self) -> None:
        dimension = "17_motion_temporal_consistency"
        payload = {
            "facts": {
                "camera_motion": "连续跟随长镜头",
                "subject_consistency": "棕色皮风衣男子",
                "human_motion": "男子稳步行走",
            },
            "gates": _gates(dimension),
            "items": [
                _item(1, "camera_motion", "镜头运动是否达到连续跟随长镜头？"),
                _item(2, "subject_consistency", "棕色皮风衣男子是否保持一致？"),
                _item(3, "temporal_continuity", "从酒吧到森林是否连续？"),
                _item(4, "human_motion", "男子行走是否自然？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["requested_camera_motion"], "连续跟随长镜头")
        self.assertEqual(checklist["facts"]["subjects"], "棕色皮风衣男子")
        self.assertIs(checklist["facts"]["has_humans"], True)

    def test_d18_copies_allowed_text_when_expected_text_is_empty(self) -> None:
        dimension = "18_text_visual_consistency"
        payload = {
            "facts": {
                "expected_texts": [],
                "allowed_texts": ["老板,给我来根儿烤肠!"],
                "subtitles_required": False,
                "subtitle_lines": [],
                "text_forbidden": False,
            },
            "gates": _gates(dimension),
            "items": [
                _item(1, "text_readability", "要求出现的文字是否清晰可读？"),
                _item(2, "text_stability", "要求出现的文字是否全程稳定？"),
                _item(3, "text_accuracy", "画面文字是否准确呈现要求的句子？"),
                _item(4, "no_unrequested_text", "画面是否没有未被要求的文字？"),
            ],
        }
        checklist = _d18_checklist_payload(payload, DIMS[dimension], _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["expected_texts"], ["老板,给我来根儿烤肠!"])

    def test_rubric_items_reject_duplicate_subpoints_and_yes_no(self) -> None:
        dimension = "13_style_visual_control"
        payload = {
            "facts": {"style_spec": "写实"},
            "gates": _gates(dimension),
            "items": [_item(1, "style_accuracy", "风格是否达到写实？")],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertEqual(len(checklist["items"]), 1)
        payload["items"].append(_item(2, "style_accuracy", "另一种风格问法？"))
        self.assertIsNone(_model_checklist_payload(payload, DIMS[dimension], dimension, _case()))
        payload["items"] = [{"id": "i1", "subpoint": "style_accuracy", "question": "是否写实？", "kind": "yes_no", "expect": "yes"}]
        self.assertIsNone(_model_checklist_payload(payload, DIMS[dimension], dimension, _case()))


class RubricScoreTests(unittest.TestCase):
    def test_subpoint_uses_lowest_grade_and_caps_skipped_items(self) -> None:
        checklist = {"items": [
            {"id": "a", "subpoint": "lip_sync", "core": True},
            {"id": "b", "subpoint": "lip_sync", "core": False},
        ]}
        both = checklist_component(checklist, {"answers": [{"id": "a", "score": 5}, {"id": "b", "score": 2}]}, "lip_sync", {})
        self.assertEqual(both["score"], 2.0)
        self.assertEqual(both["core_score"], 5.0)
        self.assertTrue(both["noncore_flaw"])
        skipped = checklist_component(checklist, {"answers": [{"id": "a", "score": 5}]}, "lip_sync", {})
        self.assertEqual(skipped["score"], 3.0)
        self.assertEqual(skipped["core_score"], 5.0)

    def test_dimension_cap_follows_core_and_limits_noncore_to_four(self) -> None:
        self.assertEqual(dimension_score({
            "core": {"applicable": True, "score": 5, "core_score": 5, "noncore_flaw": False},
            "other": {"applicable": True, "score": 5, "core_score": None, "noncore_flaw": False},
        }), 5.0)
        self.assertEqual(dimension_score({
            "core": {"applicable": True, "score": 2, "core_score": 2, "noncore_flaw": False},
            "other": {"applicable": True, "score": 5, "core_score": None, "noncore_flaw": False},
        }), 2.0)
        self.assertEqual(dimension_score({
            "core": {"applicable": True, "score": 1, "core_score": 5, "noncore_flaw": True},
        }), 4.0)
        self.assertEqual(dimension_score({
            "only": {"applicable": True, "score": 1, "core_score": None, "noncore_flaw": True},
        }), 4.0)

    def test_successful_numeric_component_stays_in_the_weighted_average(self) -> None:
        checklist = {"items": [{"id": "q1", "subpoint": "text_accuracy", "core": True}]}
        answers = {"answers": [{"id": "q1", "score": 5}]}
        case = Case("case", Path("."), "t2va", None, None)
        config = {"components": {"checklist": 0.6, "ocr_cer": 0.4}}
        measured = {"component": "ocr_cer", "status": "ok", "score": 2.0}
        with patch("v_eval.core.run_component", return_value=measured):
            result = score_subpoint({}, "text_accuracy", config, checklist, answers, case, {}, True, {})
        self.assertEqual(result["score"], 3.8)
        self.assertEqual(result["score_basis"], "weighted")
        self.assertEqual(result["core_score"], 3.8)


if __name__ == "__main__":
    unittest.main()
