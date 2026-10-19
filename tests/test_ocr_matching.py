from __future__ import annotations

import unittest

from v_eval.model_components import (
    _ocr_mean_cer,
    _ocr_ordered_cer,
    _ocr_readability,
    _ocr_scene_stability,
    _ocr_span_stability,
)


def _line(text: str, score: float = 0.99, height: float = 32) -> dict:
    return {"text": text, "score": score, "height": height}


class OcrMatchingTest(unittest.TestCase):
    def test_repeated_frames_do_not_raise_character_error(self) -> None:
        frames = [[_line("这杯咖啡，"), _line("能让我清醒吗？")] for _ in range(8)]
        targets = ["这杯咖啡，", "能让我清醒吗？"]
        self.assertLess(_ocr_mean_cer(targets, frames), 0.05)

    def test_missing_target_is_a_full_error(self) -> None:
        frames = [[_line("其他文字")] for _ in range(4)]
        self.assertEqual(_ocr_mean_cer(["校园贷"], frames), 1.0)

    def test_extra_text_does_not_improve_readability(self) -> None:
        frames = [[_line("乱码"), _line("星河影像展", score=0.2, height=8)]]
        self.assertLess(_ocr_readability(["星河影像展"], frames), 0.8)
        self.assertGreater(_ocr_readability(["星河影像展"], [[_line("星河影像展")]]), 0.9)

    def test_subtitle_order_ignores_a_line_that_stays_on_screen(self) -> None:
        frames = [
            [_line("我们订的是今晚七点半吧？")],
            [_line("我们订的是今晚七点半吧？")],
            [_line("对，B2展厅，两个人。")],
        ]
        cer = _ocr_ordered_cer(["我们订的是今晚七点半吧？", "对，B2展厅，两个人。"], frames)
        self.assertLess(cer, 0.05)

    def test_scene_text_must_persist_but_a_subtitle_span_may_be_short(self) -> None:
        frames = [[_line("海报")] if index < 2 else [_line("其他")] for index in range(8)]
        self.assertLess(_ocr_scene_stability(["海报"], frames), 0.3)
        self.assertEqual(_ocr_span_stability(["海报"], frames), 1.0)


if __name__ == "__main__":
    unittest.main()
