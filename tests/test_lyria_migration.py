"""Tests for v4.2.1 Lyria migration in audio_pipeline.py:
- detect_lyrics_intent pattern matching
- resolve_lyria_version routing with --confirm-upgrade gate
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "create-video" / "scripts"),
)

import audio_pipeline


class TestDetectLyricsIntent(unittest.TestCase):
    def test_verse_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Verse] a song"))

    def test_chorus_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Chorus] sing along"))

    def test_bridge_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Bridge] middle 8"))

    def test_hook_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Hook] catchy line"))

    def test_timestamp_detected(self):
        self.assertTrue(
            audio_pipeline.detect_lyrics_intent("[0:00 - 0:30] intro music"),
        )

    def test_plain_prompt_not_detected(self):
        self.assertFalse(
            audio_pipeline.detect_lyrics_intent("a jazz track with saxophone"),
        )

    def test_instrumental_only_overrides_verse_tag(self):
        self.assertFalse(
            audio_pipeline.detect_lyrics_intent(
                "instrumental only: [Verse] style arrangement"
            ),
        )

    def test_no_vocals_overrides(self):
        self.assertFalse(
            audio_pipeline.detect_lyrics_intent("[Verse] tag but no vocals"),
        )

    def test_case_insensitive(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[VERSE 1] caps"))


class TestResolveLyriaVersion(unittest.TestCase):
    def test_explicit_version_2_wins(self):
        result = audio_pipeline.resolve_lyria_version(
            "[Verse] lyrics here",
            explicit_version="2",
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-2")

    def test_explicit_version_3_wins_over_detection(self):
        result = audio_pipeline.resolve_lyria_version(
            "[Verse] song structure",
            explicit_version="3",
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3")

    def test_explicit_version_3_pro_wins(self):
        result = audio_pipeline.resolve_lyria_version(
            "plain prompt",
            explicit_version="3-pro",
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3-pro")

    def test_negative_prompt_auto_routes_lyria_2(self):
        result = audio_pipeline.resolve_lyria_version(
            "jazz track",
            explicit_version=None,
            confirm_upgrade=False,
            has_negative_prompt=True,
        )
        self.assertEqual(result, "lyria-2")

    def test_plain_prompt_defaults_lyria_3(self):
        result = audio_pipeline.resolve_lyria_version(
            "a mellow jazz track",
            explicit_version=None,
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3")

    def test_lyrics_detected_without_confirm_raises(self):
        with self.assertRaises(audio_pipeline.LyriaUpgradeGateError):
            audio_pipeline.resolve_lyria_version(
                "[Verse] walking home",
                explicit_version=None,
                confirm_upgrade=False,
                has_negative_prompt=False,
            )

    def test_lyrics_detected_with_confirm_routes_to_pro(self):
        result = audio_pipeline.resolve_lyria_version(
            "[Verse] walking home",
            explicit_version=None,
            confirm_upgrade=True,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3-pro")

    def test_error_message_lists_three_options(self):
        try:
            audio_pipeline.resolve_lyria_version(
                "[Verse] walking home",
                explicit_version=None,
                confirm_upgrade=False,
                has_negative_prompt=False,
            )
            self.fail("Expected LyriaUpgradeGateError")
        except audio_pipeline.LyriaUpgradeGateError as e:
            msg = str(e)
            self.assertIn("--confirm-upgrade", msg)
            self.assertIn("--lyria-version 3", msg)
            self.assertIn("--lyria-version 3-pro", msg)


if __name__ == "__main__":
    unittest.main()
