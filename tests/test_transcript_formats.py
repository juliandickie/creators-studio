"""Tests for skills/create-transcript/scripts/formats.py - the pure renderers.

No network, no filesystem writes. Every renderer is a pure function of a parsed
Scribe v2 response dict. Fixtures are trimmed real responses captured 2026-07-23:

  scribe_single_speaker.json - StoryBrand clip, one speaker, no audio events.
  scribe_two_speaker.json - Perell/Harry Dry interview opening, two speakers,
                                includes a [laughs] audio_event.

Both fixtures carry the real response's extra keys (transcription_id,
audio_duration_secs, per-word logprob) so the renderers are proven to tolerate them.
"""
import json
import re
import sys
import unittest
from pathlib import Path

# Per-skill scripts live under a hyphenated dir (skills/create-transcript/scripts),
# which can't be imported as a package. Add that dir to the path and import directly.
SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "create-transcript" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import formats  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


class TestTimecode(unittest.TestCase):
    def test_clock_under_hour_has_no_leading_zero_unit(self):
        self.assertEqual(formats.fmt_time(0, "clock"), "0:00")
        self.assertEqual(formats.fmt_time(65, "clock"), "1:05")
        self.assertEqual(formats.fmt_time(600, "clock"), "10:00")

    def test_clock_over_hour(self):
        self.assertEqual(formats.fmt_time(3661, "clock"), "1:01:01")

    def test_srt_uses_comma_millis(self):
        self.assertEqual(formats.fmt_time(1.5, "srt"), "00:00:01,500")
        self.assertEqual(formats.fmt_time(3661.25, "srt"), "01:01:01,250")

    def test_vtt_uses_dot_millis(self):
        self.assertEqual(formats.fmt_time(1.5, "vtt"), "00:00:01.500")


class TestGroupTurns(unittest.TestCase):
    def test_single_speaker_is_one_turn(self):
        turns = formats.group_turns(load("scribe_single_speaker")["words"])
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["speaker_id"], "speaker_0")
        self.assertEqual(turns[0]["label"], "Speaker 0")
        self.assertIn("One of the problems", turns[0]["text"])
        # Turn text is clean - no double spaces from the spacing tokens.
        self.assertNotIn("  ", turns[0]["text"])

    def test_two_speaker_alternates_and_inlines_audio_event(self):
        turns = formats.group_turns(load("scribe_two_speaker")["words"])
        self.assertGreaterEqual(len(turns), 3)
        self.assertEqual(turns[0]["speaker_id"], "speaker_0")
        # The [laughs] event belongs to speaker_1 and renders inline in that turn.
        s1 = [t for t in turns if t["speaker_id"] == "speaker_1"]
        self.assertTrue(s1)
        self.assertIn("[laughs]", " ".join(t["text"] for t in s1))
        # Adjacent turns never share a speaker (that's what "grouping" means).
        for a, b in zip(turns, turns[1:]):
            self.assertNotEqual(a["speaker_id"], b["speaker_id"])

    def test_speaker_names_relabel(self):
        names = {"0": "David Perell", "1": "Harry Dry"}
        turns = formats.group_turns(load("scribe_two_speaker")["words"], speaker_names=names)
        labels = {t["label"] for t in turns}
        self.assertIn("David Perell", labels)
        self.assertIn("Harry Dry", labels)
        self.assertNotIn("Speaker 0", labels)

    def test_speaker_names_accept_prefixed_keys(self):
        # Accept both "1" and "speaker_1" as keys - orchestrator may pass either.
        names = {"speaker_0": "A", "speaker_1": "B"}
        turns = formats.group_turns(load("scribe_two_speaker")["words"], speaker_names=names)
        self.assertIn("A", {t["label"] for t in turns})


class TestMarkdown(unittest.TestCase):
    def test_single_speaker_header_and_body(self):
        data = load("scribe_single_speaker")
        md = formats.render_markdown(data, source_name="clip.mp4")
        self.assertIn("clip.mp4", md)
        self.assertIn("Speakers detected: 1", md)
        self.assertIn("eng", md)
        self.assertIn("One of the problems", md)      # continuous text present
        self.assertRegex(md, r"\[0:00\].*Speaker 0")    # a timecoded speaker turn

    def test_two_speaker_shows_both_and_audio_event(self):
        md = formats.render_markdown(load("scribe_two_speaker"))
        self.assertIn("Speaker 0", md)
        self.assertIn("Speaker 1", md)
        self.assertIn("[laughs]", md)

    def test_speaker_names_replace_generic_labels(self):
        md = formats.render_markdown(
            load("scribe_two_speaker"),
            speaker_names={"0": "David Perell", "1": "Harry Dry"},
        )
        self.assertIn("David Perell", md)
        self.assertNotIn("Speaker 0", md)


class TestTitle(unittest.TestCase):
    def test_title_becomes_h1_source_line_preserved(self):
        md = formats.render_markdown(load("scribe_single_speaker"),
                                     source_name="clip.mp4", title="My Great Talk")
        self.assertTrue(md.startswith("# My Great Talk"))    # H1 is the title
        self.assertIn("Source file: `clip.mp4`", md)         # video name still referenced
        self.assertNotIn("# clip.mp4", md)                   # not the filename as H1

    def test_no_title_falls_back_to_source_name(self):
        md = formats.render_markdown(load("scribe_single_speaker"), source_name="clip.mp4")
        self.assertTrue(md.startswith("# clip.mp4"))


class TestSubtitles(unittest.TestCase):
    def _starts(self, cue_block, sep):
        # Pull the start timestamp out of each "start --> end" line.
        return [line.split("-->")[0].strip()
                for line in cue_block.splitlines() if "-->" in line]

    def test_srt_structure_and_monotonic(self):
        srt = formats.render_srt(load("scribe_two_speaker"))
        self.assertTrue(srt.strip().startswith("1"))       # first cue index
        self.assertIn("-->", srt)
        # SRT uses comma millis: HH:MM:SS,mmm
        self.assertRegex(srt, r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")
        starts = self._starts(srt, ",")
        self.assertEqual(starts, sorted(starts))            # non-decreasing

    def test_vtt_header_and_dot_millis(self):
        vtt = formats.render_vtt(load("scribe_two_speaker"))
        self.assertTrue(vtt.startswith("WEBVTT"))
        self.assertRegex(vtt, r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}")

    def test_cues_respect_char_budget(self):
        # No cue should be wildly over the target line length (allow one word of slack).
        cues = formats.segment_cues(load("scribe_single_speaker")["words"],
                                    max_dur=7.0, max_chars=42)
        self.assertTrue(cues)
        for c in cues:
            self.assertLessEqual(len(c["text"]), 42 + 15)


class TestChapters(unittest.TestCase):
    def test_first_anchor_is_zero(self):
        # YouTube requires the first chapter at 0:00.
        chapters = formats.render_chapters(load("scribe_two_speaker"))
        first_marker = next(l for l in chapters.splitlines() if re.match(r"^\d+:\d\d", l.strip()))
        self.assertTrue(first_marker.strip().startswith("0:00"))


class TestPlaintext(unittest.TestCase):
    def test_plaintext_carries_the_text_field(self):
        data = load("scribe_single_speaker")
        txt = formats.render_plaintext(data)
        # Every word of the canonical text survives (wrapping may add newlines).
        self.assertEqual(" ".join(txt.split()), " ".join(data["text"].split()))


if __name__ == "__main__":
    unittest.main()
