"""Tests for audio_pipeline.generate_sfx (ElevenLabs /v1/sound-generation).

Network is mocked via urllib.request.urlopen, so the suite runs offline.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "create-video" / "scripts"),
)

import audio_pipeline  # noqa: E402


def _fake_urlopen(body=b"ID3fake-mp3"):
    m = MagicMock()
    m.read.return_value = body
    m.__enter__.return_value = m
    m.__exit__.return_value = False
    return m


class TestGenerateSfx(unittest.TestCase):
    def test_request_shape_and_file_written(self):
        with tempfile.TemporaryDirectory() as d, \
                patch("urllib.request.urlopen", return_value=_fake_urlopen()) as op:
            out = Path(d) / "whoosh.mp3"
            r = audio_pipeline.generate_sfx("a fast whoosh", "k", duration_s=2.5,
                                            loop=True, output_path=out)
            req = op.call_args[0][0]
            self.assertTrue(req.full_url.endswith("/v1/sound-generation"))
            self.assertEqual(req.get_header("Xi-api-key"), "k")
            body = json.loads(req.data)
            self.assertEqual(body["text"], "a fast whoosh")
            self.assertEqual(body["duration_seconds"], 2.5)
            self.assertTrue(body["loop"])
            self.assertEqual(body["model_id"], "eleven_text_to_sound_v2")
            self.assertEqual(out.read_bytes(), b"ID3fake-mp3")
            self.assertEqual(r["path"], str(out))

    def test_duration_omitted_when_none(self):
        with tempfile.TemporaryDirectory() as d, \
                patch("urllib.request.urlopen", return_value=_fake_urlopen()) as op:
            audio_pipeline.generate_sfx("rain", "k", output_path=Path(d) / "r.mp3")
            self.assertNotIn("duration_seconds", json.loads(op.call_args[0][0].data))

    def test_out_of_range_rejected_before_any_call(self):
        with patch("urllib.request.urlopen") as op:
            for kwargs in ({"duration_s": 0.2}, {"duration_s": 31}, {"prompt_influence": 1.5}):
                with self.assertRaises(SystemExit):
                    audio_pipeline.generate_sfx("x", "k", **kwargs)
            op.assert_not_called()


if __name__ == "__main__":
    unittest.main()
