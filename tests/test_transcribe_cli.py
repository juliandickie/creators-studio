"""Tests for skills/create-transcript/scripts/transcribe.py.

Network is mocked via urllib.request.urlopen so tests run offline. The pure
helpers (auth order, keyterm merge/sanitise, speaker parse, probe parse,
multipart build) are tested directly; the one integration test proves that a
transcription makes exactly one network call and that render-from-cache makes
none.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "create-transcript" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import transcribe  # noqa: E402


def _fake_urlopen(payload, status=200):
    m = MagicMock()
    m.read.return_value = json.dumps(payload).encode("utf-8")
    m.status = status
    m.__enter__.return_value = m
    m.__exit__.return_value = False
    return m


SCRIBE_RESPONSE = {
    "language_code": "eng",
    "language_probability": 1.0,
    "text": "Hello world.",
    "audio_duration_secs": 3.0,
    "words": [
        {"text": "Hello", "start": 0.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"},
        {"text": " ", "start": 0.5, "end": 0.6, "type": "spacing", "speaker_id": "speaker_0"},
        {"text": "world.", "start": 0.6, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
    ],
}


class TestAuthOrder(unittest.TestCase):
    def test_cli_key_wins(self):
        key = transcribe.get_api_key("cli-key", {"elevenlabs_api_key": "cfg"},
                                     {"ELEVENLABS_API_KEY": "env"})
        self.assertEqual(key, "cli-key")

    def test_env_beats_config(self):
        key = transcribe.get_api_key(None, {"elevenlabs_api_key": "cfg"},
                                     {"ELEVENLABS_API_KEY": "env"})
        self.assertEqual(key, "env")

    def test_config_is_last_resort(self):
        key = transcribe.get_api_key(None, {"elevenlabs_api_key": "cfg"}, {})
        self.assertEqual(key, "cfg")

    def test_missing_key_raises(self):
        with self.assertRaises(SystemExit):
            transcribe.get_api_key(None, {}, {})


class TestKeyterms(unittest.TestCase):
    def test_three_tier_union_dedup(self):
        cfg = {"transcription": {"keyterms": ["Medit", "iTero"]}}
        with patch.object(transcribe, "DEFAULT_KEYTERMS", ["iDD"]):
            merged = transcribe.resolve_keyterms("iTero,Ascot", replace=False, config=cfg)
        # CLI + config + default, order-preserving, deduped (iTero appears once).
        self.assertEqual(merged, ["iTero", "Ascot", "Medit", "iDD"])

    def test_replace_uses_only_cli(self):
        cfg = {"transcription": {"keyterms": ["Medit"]}}
        merged = transcribe.resolve_keyterms("OnlyThis", replace=True, config=cfg)
        self.assertEqual(merged, ["OnlyThis"])

    def test_sanitize_drops_forbidden_and_oversize(self):
        kept, dropped = transcribe.sanitize_keyterms([
            "Good", "bad[bracket]", "x" * 60, "one two three four five six", "  ",
        ])
        self.assertEqual(kept, ["Good"])
        self.assertEqual(len(dropped), 3)  # bracket, oversize, >5-words (blank skipped silently)


class TestSpeakers(unittest.TestCase):
    def test_parse_plain_and_prefixed(self):
        self.assertEqual(
            transcribe.parse_speakers("0=Julian,1=Dr Ahmad"),
            {"speaker_0": "Julian", "speaker_1": "Dr Ahmad"},
        )
        self.assertEqual(transcribe.parse_speakers("speaker_2=X"), {"speaker_2": "X"})

    def test_empty(self):
        self.assertEqual(transcribe.parse_speakers(None), {})
        self.assertEqual(transcribe.parse_speakers("garbage"), {})


class TestProbeParse(unittest.TestCase):
    def test_no_audio_stream(self):
        probe = {"streams": [{"codec_type": "video"}], "format": {"duration": "12.0"}}
        dur, has_audio = transcribe.parse_probe(probe)
        self.assertEqual(dur, 12.0)
        self.assertFalse(has_audio)

    def test_audio_present(self):
        probe = {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                 "format": {"duration": "49.9"}}
        dur, has_audio = transcribe.parse_probe(probe)
        self.assertAlmostEqual(dur, 49.9)
        self.assertTrue(has_audio)


class TestMultipart(unittest.TestCase):
    def test_list_field_repeats(self):
        ctype, body = transcribe.build_multipart(
            {"model_id": "scribe_v2", "keyterms": ["Medit", "iTero"]},
            [("file", "a.mp3", b"\x00\x01")],
        )
        self.assertTrue(ctype.startswith("multipart/form-data; boundary="))
        text = body.decode("latin-1")
        # keyterms emitted as two repeated parts, not one joined field.
        self.assertEqual(text.count('name="keyterms"'), 2)
        self.assertIn("Medit", text)
        self.assertIn("iTero", text)
        self.assertIn('name="file"; filename="a.mp3"', text)
        self.assertIn("scribe_v2", text)

    def test_bool_becomes_lowercase(self):
        _, body = transcribe.build_multipart({"diarize": True}, [])
        self.assertIn("true", body.decode("latin-1"))


class TestIntegration(unittest.TestCase):
    def test_transcribe_writes_formats_with_one_network_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            fake_audio = Path(tmp) / "clip.mp3"
            fake_audio.write_bytes(b"\x00\x00")
            with patch.object(transcribe, "probe_media", return_value=(3.0, True)), \
                 patch.object(transcribe, "extract_audio", return_value=fake_audio), \
                 patch.object(transcribe, "log_cost"), \
                 patch("transcribe.urllib.request.urlopen",
                       return_value=_fake_urlopen(SCRIBE_RESPONSE)) as mock_open:
                res = transcribe.transcribe_file(
                    str(Path(tmp) / "clip.mp4"), api_key="k", keyterms=["Medit"],
                    language=None, diarize=True, out_dir=out,
                    fmts=["md", "srt", "vtt", "json"], speaker_names={"speaker_0": "Ny"},
                )
            self.assertEqual(mock_open.call_count, 1)            # exactly one API call
            self.assertEqual(res["status"], "ok")
            self.assertTrue((out / "clip.md").exists())
            self.assertTrue((out / "clip.json").exists())
            md = (out / "clip.md").read_text()
            self.assertIn("Ny", md)                              # speaker name applied
            cached = json.loads((out / "clip.json").read_text())
            self.assertEqual(cached["_speaker_names"], {"speaker_0": "Ny"})

    def test_no_audio_raises_before_any_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(transcribe, "probe_media", return_value=(5.0, False)), \
                 patch("transcribe.urllib.request.urlopen") as mock_open:
                with self.assertRaises(transcribe.NoAudioStreamError):
                    transcribe.transcribe_file(
                        str(Path(tmp) / "silent.mp4"), api_key="k", keyterms=[],
                        language=None, diarize=True, out_dir=Path(tmp) / "o",
                        fmts=["md"], speaker_names=None,
                    )
                mock_open.assert_not_called()                   # failed loud, no upload

    def test_rename_re_renders_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = Path(tmp) / "clip.json"
            j.write_text(json.dumps(SCRIBE_RESPONSE))
            args = transcribe.build_parser().parse_args(
                ["rename", "--json", str(j), "--speakers", "0=Renamed", "--formats", "md"]
            )
            with patch("transcribe.urllib.request.urlopen") as mock_open:
                rc = args.func(args)
            self.assertEqual(rc, 0)
            mock_open.assert_not_called()                       # cache-only, no charge
            self.assertIn("Renamed", (Path(tmp) / "clip.md").read_text())


if __name__ == "__main__":
    unittest.main()
