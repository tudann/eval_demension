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

    def test_d15_numeric_rubric_field_becomes_rubric_item(self) -> None:
        dimension = "15_audio_quality_control"
        payload = {
            "facts": {
                "dialogues": "报表怎么还没交。",
                "has_repeated_speaker": False,
                "dialogue_emotions": False,
                "target_emotion": "",
                "ambient": "办公室里很轻的环境声",
                "ambient_description": "办公室里很轻的环境声",
                "sfx": "",
                "sfx_description": "",
            },
            "gates": _gates(dimension),
            "items": [
                {
                    "id": "i1", "requirement": "对话准确性", "rubric": 5,
                    "description": "对白是否准确传达老板和员工的两句台词？",
                    "subpoint": "dialogue_accuracy", "applied": True, "fulfilled": True,
                },
                {
                    "id": "i2", "requirement": "背景音效", "rubric": 5,
                    "description": "是否能听到办公室内很轻的环境声？",
                    "subpoint": "ambient_sound",
                },
                {
                    "id": "i3", "requirement": "自然的语音质量", "rubric": 5,
                    "description": "语音是否自然清晰？",
                    "subpoint": "voice_naturalness",
                },
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual([item["kind"] for item in checklist["items"]], ["rubric_5", "rubric_5", "rubric_5"])
        self.assertEqual(checklist["items"][0]["question"], "对白是否准确传达老板和员工的两句台词？")

    def test_gate_answers_without_ids_follow_checklist_order(self) -> None:
        from v_eval.checklists import _parse_judge_payload

        parsed = _parse_judge_payload(
            {"gates": [{"answer": "yes", "回答依据": "听得清"}, {"answer": "yes", "回答依据": "没有损坏"}],
             "answers": [{"id": "i1", "score": 5, "回答依据": "对白完整"}]},
            ["g1", "g2"],
        )
        self.assertEqual([gate["id"] for gate in parsed["gates"]], ["g1", "g2"])

    def test_d15_sfx_alias_enables_conditional_item_but_music_is_not_a_subpoint(self) -> None:
        dimension = "15_audio_quality_control"
        payload = {
            "facts": {"sfx_requirement": "叮一声的问号音效"},
            "gates": _gates(dimension),
            "items": [
                _item(1, "action_sfx", "动作音效是否达到叮一声的问号音效？"),
                _item(2, "voice_naturalness", "人声是否自然？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["sfx"], "叮一声的问号音效")
        self.assertEqual(checklist["facts"]["sfx_description"], "叮一声的问号音效")
        payload["items"].append(_item(3, "music_match", "配乐是否达到童话风格？"))
        self.assertIsNone(_model_checklist_payload(payload, DIMS[dimension], dimension, _case()))

    def test_d16_dialogue_alias_enables_lip_sync(self) -> None:
        dimension = "16_audio_visual_sync"
        payload = {
            "facts": {"dialogue": "啊，故事挺好的。", "actions": "拍手并发出拍手声", "environment_changes": "雨落下时出现雨声"},
            "gates": _gates(dimension),
            "items": [
                _item(1, "lip_sync", "口型是否与台词同步？"),
                _item(2, "action_sound_sync", "拍手声是否与拍手动作同步？"),
                _item(3, "ambient_sound_sync", "雨声是否与落雨画面同步？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["dialogues"], "啊，故事挺好的。")
        self.assertEqual(checklist["facts"]["av_events"], "拍手并发出拍手声")
        self.assertEqual(checklist["facts"]["env_changes"], "雨落下时出现雨声")

    def test_d17_failure_anomaly_items_and_human_applicability(self) -> None:
        dimension = "17_failure_anomaly_control"
        payload = {
            "facts": {
                "subject": "棕色皮风衣男子",
                "has_human": True,
                "fixed_attributes": "棕色皮风衣",
                "camera_movement": "连续跟随长镜头",
            },
            "gates": _gates(dimension),
            "items": [
                _item(1, "human_deformation_rate", "男子的手和身体是否没有畸变？"),
                _item(2, "subject_disappearance_rate", "男子是否没有意外消失？"),
                _item(3, "subject_duplication_rate", "男子是否没有被复制？"),
                _item(4, "attribute_drift_rate", "皮风衣颜色是否没有漂移？"),
                _item(5, "penetration_issue", "人物是否没有穿过其他物体？"),
                _item(6, "camera_anomaly_rate", "镜头是否没有意外跳切？"),
                _item(7, "breakdown_duration", "视觉崩坏是否没有持续？"),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["subjects"], "棕色皮风衣男子")
        self.assertIs(checklist["facts"]["has_humans"], True)
        self.assertEqual(checklist["facts"]["protected_attributes"], "棕色皮风衣")
        self.assertEqual(checklist["facts"]["camera_constraints"], "连续跟随长镜头")
        payload["facts"]["has_human"] = False
        self.assertIsNone(_model_checklist_payload(payload, DIMS[dimension], dimension, _case()))

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
        deduped = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(deduped)
        self.assertEqual([item["id"] for item in deduped["items"]], ["q1"])
        payload["items"] = [{"id": "i1", "subpoint": "style_accuracy", "question": "是否写实？", "kind": "yes_no", "expect": "yes"}]
        self.assertIsNone(_model_checklist_payload(payload, DIMS[dimension], dimension, _case()))

    def test_d20_aliases_keep_only_applicable_performance_items(self) -> None:
        dimension = "20_performance_emotion"
        payload = {
            "facts": {
                "emotion": "压着的担心",
                "situation": "医院走廊里捏着检查单",
                "expression_change": "从平静慢慢变成惊喜",
                "look_at": "先看小熊再看店门口",
                "reaction": "客人走进来后停一拍再抬头",
                "dialogue": "你先别过来。",
                "has_human": True,
            },
            "gates": _gates(dimension),
            "items": [
                _item(1, "emotion_accuracy", "表情、姿态和语气是否符合压着的担心？", core=True),
                _item(2, "expression_transition", "表情是否从平静慢慢过渡到惊喜？"),
                _item(3, "gaze_attention", "视线是否先落到小熊再转到店门口？"),
                _item(4, "micro_motion", "眨眼和呼吸是否自然，而不是机械重复？"),
                _item(5, "reaction_timing", "客人走进来后，柜台后的人是否停一拍再抬头？"),
                _item(6, "dialogue_performance", "说“你先别过来”时，表情和语气是否一致？", core=True),
            ],
        }
        checklist = _model_checklist_payload(payload, DIMS[dimension], dimension, _case())
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist["facts"]["target_emotion"], "压着的担心")
        self.assertEqual(checklist["facts"]["character_situation"], "医院走廊里捏着检查单")
        self.assertEqual(checklist["facts"]["emotion_change"], "从平静慢慢变成惊喜")
        self.assertEqual(checklist["facts"]["gaze_target"], "先看小熊再看店门口")
        self.assertEqual(checklist["facts"]["reaction_event"], "客人走进来后停一拍再抬头")
        self.assertEqual(checklist["facts"]["dialogues"], "你先别过来。")
        self.assertIs(checklist["facts"]["has_humans"], True)
        self.assertEqual(
            [item["subpoint"] for item in checklist["items"]],
            ["emotion_accuracy", "expression_transition", "gaze_attention", "micro_motion", "reaction_timing", "dialogue_performance"],
        )
        self.assertEqual(checklist["gates"][0]["modality"], "audio_visual")
        payload["items"] = [_item(1, "gaze_attention", "视线是否看向老板？")]
        payload["facts"] = {"has_humans": True, "target_emotion": "", "character_situation": "", "emotion_change": "", "gaze_target": "", "reaction_event": "", "dialogues": False}
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
        with patch("v_eval.scoring.run_component", return_value=measured):
            result = score_subpoint({}, "text_accuracy", config, checklist, answers, case, {}, True, {})
        self.assertEqual(result["score"], 3.8)
        self.assertEqual(result["score_basis"], "weighted")
        self.assertEqual(result["core_score"], 3.8)

    def test_noncore_numeric_score_caps_dimension_at_four(self) -> None:
        checklist = {"items": [
            {"id": "i1", "subpoint": "dialogue_accuracy", "core": True},
            {"id": "i4", "subpoint": "ambient_sound", "core": False},
        ]}
        answers = {"answers": [{"id": "i1", "score": 5}, {"id": "i4", "score": 5}]}
        case = Case("case", Path("."), "t2va", None, None)
        measured = {"component": "clap_ambient", "status": "ok", "score": 1.0}
        with patch("v_eval.scoring.run_component", return_value=measured):
            dialogue = score_subpoint({}, "dialogue_accuracy", {"components": {"checklist": 1.0}}, checklist, answers, case, {}, True, {})
            ambient = score_subpoint({}, "ambient_sound", {"components": {"checklist": 0.6, "clap_ambient": 0.4}}, checklist, answers, case, {}, True, {})
        self.assertEqual(ambient["score"], 3.4)
        self.assertIsNone(ambient["core_score"])
        self.assertEqual(dimension_score({"dialogue_accuracy": dialogue, "ambient_sound": ambient}), 4.0)


if __name__ == "__main__":
    unittest.main()
