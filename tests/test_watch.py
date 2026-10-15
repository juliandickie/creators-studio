"""Tests for skills/create-transcript/scripts/watch.py (the `transcribe.py watch` subcommand).

Pure helpers are tested offline. The one end-to-end test builds a tiny video
with ffmpeg and is skipped where ffmpeg is not installed.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "create-transcript" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import watch  # noqa: E402


def _word(text, start, end, spk="speaker_0"):
    return {"text": text, "start": start, "end": end, "type": "word", "speaker_id": spk}


def _space(t, spk="speaker_0"):
    return {"text": " ", "start": t, "end": t, "type": "spacing", "speaker_id": spk}


class TestTimes(unittest.TestCase):
    def test_parse_time_forms(self):
        self.assertEqual(watch.parse_time("75"), 75)
        self.assertEqual(watch.parse_time("1:15"), 75)
        self.assertEqual(watch.parse_time("1:01:15"), 3675)
        self.assertEqual(watch.parse_time("0:07.5"), 7.5)
        self.assertIsNone(watch.parse_time(None))

    def test_parse_time_rejects_bad_input(self):
        for bad in ("1:75", "-3", "a", "1:2:3:4"):
            with self.assertRaises(SystemExit):
                watch.parse_time(bad)

    def test_parse_timestamps_sorted_unique(self):
        self.assertEqual(watch.parse_timestamps("0:10, 5,0:10,"), [5, 10])


class TestSampling(unittest.TestCase):
    def test_even_indices_keeps_first_and_last(self):
        self.assertEqual(watch._even_indices(11, 6), [0, 2, 4, 6, 8, 10])
        self.assertEqual(watch._even_indices(3, 10), [0, 1, 2])
        self.assertEqual(watch._even_indices(5, 1), [0])

    def test_auto_fps_budgets(self):
        self.assertEqual(watch.auto_fps(26.7, 100, focused=False)[1], 27)
        self.assertEqual(watch.auto_fps(45, 100, focused=False)[1], 40)
        self.assertEqual(watch.auto_fps(5, 100, focused=True)[1], 30)
        self.assertEqual(watch.auto_fps(3600, 100, focused=False)[1], 100)
        self.assertLessEqual(watch.auto_fps(2, 100, focused=True)[0], watch.MAX_FPS)

    def test_dedupe_drops_near_identical_and_deletes_files(self):
        with tempfile.TemporaryDirectory() as d:
            frames = []
            for i in range(3):
                p = Path(d) / f"frame_{i:04d}.jpg"
                p.write_bytes(b"x")
                frames.append({"index": i, "timestamp_seconds": i, "path": str(p), "reason": "uniform"})
            same, other = bytes([10] * 768), bytes([200] * 768)
            kept, dropped = watch.dedupe_by_deltas(frames, [same, same, other])
            self.assertEqual(dropped, 1)
            self.assertEqual([f["timestamp_seconds"] for f in kept], [0, 2])
            self.assertEqual([f["index"] for f in kept], [0, 1])
            self.assertFalse((Path(d) / "frame_0001.jpg").exists())

    def test_dedupe_is_a_no_op_when_thumbs_do_not_line_up(self):
        frames = [{"index": 0, "path": "a"}, {"index": 1, "path": "b"}]
        self.assertEqual(watch.dedupe_by_deltas(frames, []), (frames, 0))


class TestTranscript(unittest.TestCase):
    DATA = {"words": [
        _word("Hello", 0.0, 0.4), _space(0.4), _word("there.", 0.5, 0.9),
        _word("Hi", 5.0, 5.3, "speaker_1"), _space(5.3, "speaker_1"), _word("back.", 5.4, 5.8, "speaker_1"),
    ], "_speaker_names": {"speaker_1": "Ron"}}

    def test_lines_carry_time_and_speaker(self):
        self.assertEqual(watch.transcript_lines(self.DATA),
                         ["[0:00] Speaker 0: Hello there.", "[0:05] Ron: Hi back."])

    def test_single_speaker_has_no_label(self):
        data = {"words": self.DATA["words"][:3]}
        self.assertEqual(watch.transcript_lines(data), ["[0:00] Hello there."])

    def test_range_filter(self):
        self.assertEqual(watch.transcript_lines(self.DATA, 4.0, 10.0), ["[0:05] Ron: Hi back."])

    def test_find_cached_matches_source_and_model(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Titled - clip.json").write_text(json.dumps(
                {"_source_name": "clip.mp4", "_model": "scribe_v2"}))
            (Path(d) / "other.json").write_text(json.dumps({"_source_name": "other.mp4"}))
            (Path(d) / "broken.json").write_text("{not json")
            self.assertEqual(watch.find_cached(Path(d), "clip.mp4", "scribe_v2").name, "Titled - clip.json")
            self.assertIsNone(watch.find_cached(Path(d), "clip.mp4", "scribe_v2_medical"))
            self.assertIsNone(watch.find_cached(Path(d) / "missing", "clip.mp4", "scribe_v2"))


class TestUrl(unittest.TestCase):
    def test_is_url(self):
        self.assertTrue(watch.is_url("https://youtu.be/x"))
        self.assertFalse(watch.is_url("/Users/me/clip.mp4"))
        self.assertFalse(watch.is_url("-https://x"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
class TestEndToEnd(unittest.TestCase):
    def test_silent_video_with_cuts(self):
        """12 one-second colour cuts, no audio: scene engine, even-sampled to the cap, no API call."""
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "cuts.mp4"
            colors = "red green blue yellow purple orange white black cyan magenta gray brown".split()
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
            for c in colors:
                cmd += ["-f", "lavfi", "-i", f"color=c={c}:s=160x120:d=1:r=25"]
            cmd += ["-filter_complex", "".join(f"[{i}:v]" for i in range(len(colors)))
                    + f"concat=n={len(colors)}:v=1:a=0[v]", "-map", "[v]", "-pix_fmt", "yuv420p", str(video)]
            subprocess.run(cmd, check=True)
            args = Namespace(source=str(video), start=None, end=None, timestamps="0:06.5", max_frames=6,
                             resolution=512, no_dedup=False, keyterms=None, keyterm_set=None,
                             keyterms_replace=False, model="scribe_v2", language=None, speakers=None,
                             output_dir=str(Path(d) / "t"), api_key=None)
            with patch("urllib.request.urlopen") as net, patch("sys.stdout", new=StringIO()) as out, \
                    patch("watch.transcribe.load_config", return_value={}):
                code = watch.cmd_watch(args)
            net.assert_not_called()
            report = out.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("**Frames:** 6 (scene", report)
            self.assertIn("cue frames 1", report)
            self.assertIn("No audio stream", report)
            self.assertIn("(t=0:00.0, first-frame)", report)
            self.assertIn("(t=0:06.5, cue)", report)
            shutil.rmtree(report.split("Frames folder: `")[1].split("`")[0])


if __name__ == "__main__":
    unittest.main()
