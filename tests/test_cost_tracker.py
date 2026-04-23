"""Tests for v4.2.1 pricing modes in cost_tracker.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "create-image" / "scripts"),
)

import cost_tracker


class TestCostTrackerPerSecondByResolution(unittest.TestCase):
    def test_veo_lite_720p_8s(self):
        # 720p: $0.05/s × 8s = $0.40
        cost = cost_tracker._lookup_cost(
            "veo-3.1-lite", "720p", duration_s=8,
        )
        self.assertEqual(cost, 0.40)

    def test_veo_lite_1080p_8s(self):
        # 1080p: $0.08/s × 8s = $0.64
        cost = cost_tracker._lookup_cost(
            "veo-3.1-lite", "1080p", duration_s=8,
        )
        self.assertEqual(cost, 0.64)

    def test_unknown_resolution_returns_none(self):
        cost = cost_tracker._lookup_cost(
            "veo-3.1-lite", "4K", duration_s=8,
        )
        self.assertIsNone(cost)

    def test_missing_duration_returns_none(self):
        cost = cost_tracker._lookup_cost(
            "veo-3.1-lite", "720p",
        )
        self.assertIsNone(cost)


class TestCostTrackerPerSecondByAudio(unittest.TestCase):
    def test_veo_fast_with_audio_8s(self):
        cost = cost_tracker._lookup_cost(
            "veo-3.1-fast", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, 1.20)  # $0.15 × 8

    def test_veo_fast_without_audio_8s(self):
        cost = cost_tracker._lookup_cost(
            "veo-3.1-fast", "1080p",
            duration_s=8, audio_enabled=False,
        )
        self.assertEqual(cost, 0.80)  # $0.10 × 8

    def test_veo_standard_with_audio_8s(self):
        cost = cost_tracker._lookup_cost(
            "veo-3.1", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, 3.20)  # $0.40 × 8

    def test_missing_audio_flag_returns_none(self):
        cost = cost_tracker._lookup_cost(
            "veo-3.1-fast", "1080p", duration_s=8,
        )
        self.assertIsNone(cost)


class TestCostTrackerPerSecondByResolutionAndAudio(unittest.TestCase):
    def test_kling_v3_pro_audio_8s(self):
        # 1080p with audio: $0.336/s × 8s = $2.688
        cost = cost_tracker._lookup_cost(
            "kling-v3", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, 2.688)

    def test_kling_v3_standard_no_audio_8s(self):
        # 720p without audio: $0.168/s × 8s = $1.344
        cost = cost_tracker._lookup_cost(
            "kling-v3", "720p",
            duration_s=8, audio_enabled=False,
        )
        self.assertEqual(cost, 1.344)

    def test_kling_v3_omni_cheaper_than_v3_on_audio(self):
        # Omni pro-audio: $0.28 × 8 = $2.24 (cheaper than v3's $2.688)
        cost = cost_tracker._lookup_cost(
            "kling-v3-omni", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, 2.24)

    def test_missing_fields_returns_none(self):
        # All of resolution, audio_enabled, duration_s required
        cost = cost_tracker._lookup_cost(
            "kling-v3", "1080p", duration_s=8,
        )
        self.assertIsNone(cost)


if __name__ == "__main__":
    unittest.main()
