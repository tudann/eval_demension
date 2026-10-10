from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from v_eval.core import Case, _d18_checklist_payload, _model_checklist_payload


ROOT = Path(__file__).resolve().parents[1]
DIMS = yaml.safe_load((ROOT / "configs" / "dims_13_18.yaml").read_text(encoding="utf-8"))["dimensions"]


def _case(case_id: str = "case", first_frame: Path | None = None) -> Case:
    return Case(case_id, Path("."), "f2va" if first_frame else "t2va", None, None, first_frame)


def _gates(dimension: str) -> list[dict]:
    return [
        {"id": gate["id"], "question": gate["question"], "expect": True, "modality": gate["modality"], "core": True}
        for gate in DIMS[dimension]["gates"]
    ]


def _item(index: int, subpoint: str, question: str) -> dict:
    return {"id": f"i{index}", "subpoint": subpoint, "question": question, "kind": "yes_no", "expect": True}


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
                _item(1, "style_accuracy", "是否为超写实风格？"),
                _item(2, "style_persistence", "超写实风格是否全程稳定？"),
                _item(3, "lighting_control", "是否使用电影光影？"),
                _item(4, "color_control", "背景是否为深红色？"),
                _item(5, "style_content_compat", "风格是否保留人物主体？"),
                _item(6, "style_accuracy", "材质细节是否逼真？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["target_lighting"], "电影光影")
        self.assertEqual(checklist["facts"]["target_colors"], "深红色背景")
        self.assertEqual(checklist["facts"]["style_spec"], "超写实")
        self.assertEqual(len(checklist["items"]), 6)

    def test_d15_music_and_sfx_aliases_enable_conditional_items(self) -> None:
        dimension = "15_audio_quality_control"
        payload = {
            "facts": {"music_requirement": "童话风格配乐", "sfx_requirement": "叮一声的问号音效"},
            "gates": _gates(dimension),
            "items": [
                _item(1, "music_match", "是否有童话风格配乐？"),
                _item(2, "music_match", "配乐是否贯穿需要配乐的段落？"),
                _item(3, "music_match", "配乐是否盖过人声或音效？"),
                _item(4, "action_sfx", "是否出现问号音效？"),
                _item(5, "action_sfx", "问号音效是否与问号出现同步？"),
                _item(6, "voice_naturalness", "如果出现人声，人声是否自然？"),
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
                _item(2, "lip_sync", "台词开始时嘴是否张开？"),
                _item(3, "lip_sync", "台词结束后嘴是否闭合？"),
                _item(4, "lip_sync", "口型是否覆盖整句台词？"),
                _item(5, "realism", "人声是否比背景音乐更清晰？"),
                _item(6, "realism", "音画关系是否自然？"),
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
                _item(1, "camera_motion", "镜头是否持续跟随男子？"),
                _item(2, "subject_consistency", "男子的风衣是否保持一致？"),
                _item(3, "subject_consistency", "男子身高是否保持一致？"),
                _item(4, "temporal_continuity", "从酒吧到森林是否连续？"),
                _item(5, "temporal_continuity", "是否没有突然跳帧？"),
                _item(6, "human_motion", "行走姿态是否自然？"),
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
                _item(1, "text_readability", "招牌文字是否清晰可读？"),
                _item(2, "text_stability", "招牌文字是否全程稳定？"),
                _item(3, "text_stability", "招牌文字是否没有位置偏移？"),
                _item(4, "text_accuracy", "画面是否出现“老板,给我来根儿烤肠!”？"),
                _item(5, "no_unrequested_text", "是否没有额外水印？"),
                _item(6, "no_unrequested_text", "是否没有无关字幕？"),
            ],
        }
        checklist = _d18_checklist_payload(payload, DIMS[dimension], _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["expected_texts"], ["老板,给我来根儿烤肠!"])


if __name__ == "__main__":
    unittest.main()
