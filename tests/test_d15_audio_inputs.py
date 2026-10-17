from __future__ import annotations

import unittest

import numpy as np

from v_eval.model_components import _dnsmos_mel_batches


class DnsMosInputTests(unittest.TestCase):
    def test_mel_batches_match_model_v8_rank(self) -> None:
        for seconds in (1.0, 8.0, 20.0):
            signal = np.zeros(int(seconds * 16000), dtype=np.float32)
            batches = _dnsmos_mel_batches(signal)
            self.assertGreaterEqual(len(batches), 1)
            for batch in batches:
                self.assertEqual(batch.shape, (1, 900, 120))
