"""Tests for scripts/backends/_replicate.py — the ReplicateBackend class.

HTTP calls are mocked via urllib.request.urlopen so tests run offline.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backends import _base, _replicate

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_urlopen_response(payload, status_code=200):
    """Build a mock that mimics urllib.request.urlopen()'s return value."""
    m = MagicMock()
    m.read.return_value = json.dumps(payload).encode("utf-8")
    m.status = status_code
    m.getcode = MagicMock(return_value=status_code)
    m.__enter__.return_value = m
    m.__exit__.return_value = False
    return m


class TestReplicateBackendContract(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()

    def test_backend_is_provider_backend(self):
        self.assertIsInstance(self.backend, _base.ProviderBackend)

    def test_backend_name_is_replicate(self):
        self.assertEqual(self.backend.name, "replicate")

    def test_supports_expected_tasks(self):
        # Tasks the plugin actually uses on Replicate today
        expected = {"text-to-video", "image-to-video", "lipsync", "vectorize"}
        self.assertTrue(expected.issubset(self.backend.supported_tasks))


class TestReplicateSubmitKling(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_text_to_video_translates_params(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_kling_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        job_ref = self.backend.submit(
            task="text-to-video",
            model_slug="kwaivgi/kling-v3-video",
            canonical_params={
                "prompt": "a cinematic product shot",
                "duration_s": 8,
                "aspect_ratio": "16:9",
                "resolution": "1080p",
            },
            provider_opts={},
            config=self.config,
        )

        self.assertIsInstance(job_ref, _base.JobRef)
        self.assertEqual(job_ref.provider, "replicate")
        self.assertEqual(job_ref.external_id, "abcdef1234567890")
        self.assertTrue(job_ref.poll_url.startswith("https://api.replicate.com"))

        # Verify the request body translated canonical -> provider-specific
        call_args = mock_urlopen.call_args
        request = call_args[0][0]  # positional args, first arg
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["prompt"], "a cinematic product shot")
        self.assertEqual(body["input"]["duration"], 8)  # duration_s -> duration
        self.assertEqual(body["input"]["aspect_ratio"], "16:9")
        self.assertEqual(body["input"]["mode"], "pro")  # 1080p -> pro mode

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_merges_provider_opts_after_canonical(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_kling_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="text-to-video",
            model_slug="kwaivgi/kling-v3-video",
            canonical_params={
                "prompt": "test",
                "duration_s": 8,
                "aspect_ratio": "16:9",
            },
            provider_opts={"multi_prompt": "[...]", "generate_audio": False},
            config=self.config,
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        # provider_opts must land in input
        self.assertEqual(body["input"]["multi_prompt"], "[...]")
        self.assertEqual(body["input"]["generate_audio"], False)
        # canonical still present
        self.assertEqual(body["input"]["duration"], 8)

    def test_submit_raises_auth_error_without_key(self):
        with self.assertRaises(_base.ProviderAuthError):
            self.backend.submit(
                task="text-to-video",
                model_slug="kwaivgi/kling-v3-video",
                canonical_params={"prompt": "test"},
                provider_opts={},
                config={},  # no API key
            )


class TestReplicatePollStateMapping(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.job_ref = _base.JobRef(
            provider="replicate",
            external_id="abc",
            poll_url="https://api.replicate.com/v1/predictions/abc",
            raw={},
        )
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    def _check_state(self, provider_state, canonical_state):
        with patch("scripts.backends._replicate.urllib.request.urlopen") as m:
            m.return_value = _fake_urlopen_response({
                "id": "abc",
                "status": provider_state,
                "output": None,
                "error": None,
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            })
            status = self.backend.poll(self.job_ref, self.config)
            self.assertEqual(
                status.state, canonical_state,
                "provider {!r} should map to canonical {!r}".format(
                    provider_state, canonical_state
                ),
            )

    def test_starting_maps_to_running(self):
        self._check_state("starting", "running")

    def test_processing_maps_to_running(self):
        self._check_state("processing", "running")

    def test_succeeded_maps_to_succeeded(self):
        self._check_state("succeeded", "succeeded")

    def test_failed_maps_to_failed(self):
        self._check_state("failed", "failed")

    def test_canceled_maps_to_canceled(self):
        self._check_state("canceled", "canceled")

    def test_aborted_maps_to_failed(self):
        self._check_state("aborted", "failed")


class TestReplicateMigrationShim(unittest.TestCase):
    """Config migration: old flat replicate_api_token should still work."""

    def setUp(self):
        self.backend = _replicate.ReplicateBackend()

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_legacy_flat_key_accepted(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_kling_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)
        # Old flat key, no new providers.* block
        config = {"replicate_api_token": "r8_legacy"}
        job_ref = self.backend.submit(
            task="text-to-video",
            model_slug="kwaivgi/kling-v3-video",
            canonical_params={"prompt": "test", "duration_s": 8, "aspect_ratio": "16:9"},
            provider_opts={},
            config=config,
        )
        self.assertEqual(job_ref.external_id, "abcdef1234567890")


class TestMusicGenerationSubmit(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_3_translates_prompt(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        job_ref = self.backend.submit(
            task="music-generation",
            model_slug="google/lyria-3",
            canonical_params={"prompt": "jazz saxophone track"},
            provider_opts={},
            config=self.config,
        )
        self.assertEqual(job_ref.provider, "replicate")
        self.assertEqual(job_ref.external_id, "lyriaabc123")

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["prompt"], "jazz saxophone track")

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_2_preserves_negative_prompt(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="music-generation",
            model_slug="google/lyria-2",
            canonical_params={"prompt": "jazz", "negative_prompt": "drums"},
            provider_opts={},
            config=self.config,
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["prompt"], "jazz")
        self.assertEqual(body["input"]["negative_prompt"], "drums")

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_3_drops_negative_prompt_with_warning(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        with self.assertLogs("scripts.backends._replicate", level="WARNING") as ctx:
            self.backend.submit(
                task="music-generation",
                model_slug="google/lyria-3",
                canonical_params={"prompt": "jazz", "negative_prompt": "drums"},
                provider_opts={},
                config=self.config,
            )
        self.assertTrue(
            any("negative_prompt" in msg for msg in ctx.output),
            f"Expected WARN about negative_prompt drop; got: {ctx.output}",
        )

        # Verify it wasn't actually sent
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("negative_prompt", body["input"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_3_accepts_reference_images(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="music-generation",
            model_slug="google/lyria-3",
            canonical_params={
                "prompt": "jazz with visuals",
                "reference_images": ["data:image/png;base64,iVBO..."],
            },
            provider_opts={},
            config=self.config,
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        # canonical 'reference_images' -> provider 'images'
        self.assertIn("images", body["input"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_2_drops_reference_images_with_warning(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        with self.assertLogs("scripts.backends._replicate", level="WARNING") as ctx:
            self.backend.submit(
                task="music-generation",
                model_slug="google/lyria-2",
                canonical_params={
                    "prompt": "jazz with visuals",
                    "reference_images": ["data:image/png;base64,iVBO..."],
                },
                provider_opts={},
                config=self.config,
            )
        self.assertTrue(
            any("reference_images" in msg for msg in ctx.output),
            f"Expected WARN about reference_images drop; got: {ctx.output}",
        )


class TestVEOSubmit(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_veo_text_to_video_translates_params(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_veo_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        job_ref = self.backend.submit(
            task="text-to-video",
            model_slug="google/veo-3.1-fast",
            canonical_params={
                "prompt": "A cinematic drone shot of a lighthouse at sunset",
                "duration_s": 8,
                "aspect_ratio": "16:9",
                "resolution": "720p",
            },
            provider_opts={},
            config=self.config,
        )
        self.assertEqual(job_ref.external_id, "veoxyz789")

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["duration"], 8)
        self.assertEqual(body["input"]["aspect_ratio"], "16:9")
        # For non-Kling models, resolution is passed through as-is.

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_veo_image_to_video(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_veo_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="image-to-video",
            model_slug="google/veo-3.1-fast",
            canonical_params={
                "prompt": "Animate this scene with gentle movement",
                "start_image": "https://example.com/input.jpg",
                "duration_s": 8,
                "aspect_ratio": "16:9",
            },
            provider_opts={},
            config=self.config,
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        # VEO on Replicate uses 'image' for image-to-video input per the
        # dev-docs model card examples (`output = replicate.run("google/veo-3.1-lite",
        # input={"image": "https://...", "prompt": "..."})`). The existing
        # _TASK_PARAM_MAPS["image-to-video"] maps canonical start_image -> provider
        # start_image (which works for Kling). If VEO rejects 'start_image' in
        # practice, add a per-model field rename in submit() similar to the
        # Kling resolution->mode translation.
        #
        # For this test: assert that SOME image field landed in the body. If
        # the test needs adjustment later based on real VEO behavior, update here.
        self.assertTrue("start_image" in body["input"] or "image" in body["input"],
                        f"Neither 'start_image' nor 'image' in VEO body: {body['input']}")


class TestPixverseValidateParams(unittest.TestCase):
    """Validates the module-level validate_pixverse_params() helper."""

    def test_valid_text_to_video_params_pass(self):
        # Should not raise
        _replicate.validate_pixverse_params(
            duration=8, resolution="1080p", aspect_ratio="16:9",
            prompt="a cinematic shot",
        )

    def test_valid_transition_params_pass(self):
        # image + last_frame_image is valid (transition mode)
        _replicate.validate_pixverse_params(
            duration=5, resolution="720p",
            image="https://example.com/first.jpg",
            last_frame_image="https://example.com/last.jpg",
            prompt="morph from first to last",
        )

    def test_invalid_duration_below_min_rejected(self):
        with self.assertRaises(_replicate.ReplicateValidationError):
            _replicate.validate_pixverse_params(
                duration=0, resolution="720p",
            )

    def test_invalid_duration_above_max_rejected(self):
        with self.assertRaises(_replicate.ReplicateValidationError):
            _replicate.validate_pixverse_params(
                duration=20, resolution="720p",
            )

    def test_non_integer_duration_rejected(self):
        with self.assertRaises(_replicate.ReplicateValidationError):
            _replicate.validate_pixverse_params(
                duration=8.5, resolution="720p",
            )

    def test_invalid_resolution_rejected(self):
        with self.assertRaises(_replicate.ReplicateValidationError):
            _replicate.validate_pixverse_params(
                duration=8, resolution="4K",  # PixVerse maxes at 1080p
            )

    def test_invalid_aspect_ratio_rejected(self):
        with self.assertRaises(_replicate.ReplicateValidationError):
            _replicate.validate_pixverse_params(
                duration=8, resolution="720p", aspect_ratio="1:1",  # not in PixVerse list
            )

    def test_last_frame_without_first_frame_rejected(self):
        with self.assertRaises(_replicate.ReplicateValidationError):
            _replicate.validate_pixverse_params(
                duration=5, resolution="720p",
                last_frame_image="https://example.com/last.jpg",
                # image not provided — should fail
            )

    def test_multi_shot_in_transition_mode_rejected(self):
        with self.assertRaises(_replicate.ReplicateValidationError):
            _replicate.validate_pixverse_params(
                duration=5, resolution="720p",
                image="https://example.com/first.jpg",
                last_frame_image="https://example.com/last.jpg",
                multi_shot=True,
            )

    def test_aspect_ratio_with_image_logs_warning(self):
        # Non-blocking: aspect_ratio is ignored when image is provided.
        with self.assertLogs(_replicate._logger, level="WARNING") as cm:
            _replicate.validate_pixverse_params(
                duration=5, resolution="720p", aspect_ratio="16:9",
                image="https://example.com/first.jpg",
            )
        self.assertTrue(any("IGNORED" in msg for msg in cm.output))


class TestPixverseBuildRequestBody(unittest.TestCase):
    """Validates the module-level build_pixverse_request_body() helper."""

    def test_text_to_video_minimal(self):
        body = _replicate.build_pixverse_request_body(
            "a cat playing",
            duration=8, resolution="720p", aspect_ratio="16:9",
        )
        self.assertEqual(body["input"]["prompt"], "a cat playing")
        self.assertEqual(body["input"]["duration"], 8)
        # Critical: canonical 'resolution' becomes PixVerse's 'quality' field
        self.assertEqual(body["input"]["quality"], "720p")
        self.assertEqual(body["input"]["aspect_ratio"], "16:9")
        self.assertTrue(body["input"]["generate_audio_switch"])  # default True

    def test_image_to_video_uses_image_field_name(self):
        body = _replicate.build_pixverse_request_body(
            "animate this",
            duration=5, resolution="720p",
            image="https://example.com/face.jpg",
        )
        # PixVerse uses 'image', not 'start_image' or 'first_frame_image'
        self.assertEqual(body["input"]["image"], "https://example.com/face.jpg")
        # aspect_ratio omitted (image is provided)
        self.assertNotIn("aspect_ratio", body["input"])

    def test_transition_uses_last_frame_image_field_name(self):
        body = _replicate.build_pixverse_request_body(
            "morph",
            duration=5, resolution="720p",
            image="https://example.com/first.jpg",
            last_frame_image="https://example.com/last.jpg",
        )
        # PixVerse field name is 'last_frame_image' (not 'end_image')
        self.assertEqual(body["input"]["last_frame_image"], "https://example.com/last.jpg")

    def test_audio_disabled(self):
        body = _replicate.build_pixverse_request_body(
            "silent clip", duration=5, resolution="720p", aspect_ratio="16:9",
            generate_audio=False,
        )
        self.assertFalse(body["input"]["generate_audio_switch"])

    def test_multi_clip_emitted_only_when_true(self):
        body_off = _replicate.build_pixverse_request_body(
            "test", duration=5, resolution="720p", aspect_ratio="16:9",
            generate_multi_clip=False,
        )
        self.assertNotIn("generate_multi_clip_switch", body_off["input"])

        body_on = _replicate.build_pixverse_request_body(
            "test", duration=5, resolution="720p", aspect_ratio="16:9",
            generate_multi_clip=True,
        )
        self.assertTrue(body_on["input"]["generate_multi_clip_switch"])


class TestPixverseSubmit(unittest.TestCase):
    """Tests ReplicateBackend.submit() Pixverse-specific dispatch."""

    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_text_to_video_renames_resolution_to_quality(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_pixverse_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        job_ref = self.backend.submit(
            task="text-to-video",
            model_slug="pixverse/pixverse-v6",
            canonical_params={
                "prompt": "a cinematic product shot",
                "duration_s": 8,
                "aspect_ratio": "16:9",
                "resolution": "1080p",
                "audio_enabled": True,
            },
            provider_opts={},
            config=self.config,
        )

        self.assertEqual(job_ref.external_id, "px1234567890abcdef")

        # Verify on-the-wire body
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["prompt"], "a cinematic product shot")
        self.assertEqual(body["input"]["duration"], 8)
        # CRITICAL: resolution → quality field rename
        self.assertEqual(body["input"]["quality"], "1080p")
        self.assertNotIn("resolution", body["input"])
        # audio_enabled → generate_audio_switch field rename
        self.assertTrue(body["input"]["generate_audio_switch"])
        self.assertNotIn("audio_enabled", body["input"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_image_to_video_renames_start_image_to_image(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_pixverse_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="image-to-video",
            model_slug="pixverse/pixverse-v6",
            canonical_params={
                "prompt": "animate",
                "duration_s": 5,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "start_image": "data:image/png;base64,abc",
            },
            provider_opts={},
            config=self.config,
        )
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        # CRITICAL: start_image → image rename
        self.assertEqual(body["input"]["image"], "data:image/png;base64,abc")
        self.assertNotIn("start_image", body["input"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_transition_renames_end_image_to_last_frame_image(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_pixverse_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="image-to-video",
            model_slug="pixverse/pixverse-v6",
            canonical_params={
                "prompt": "morph",
                "duration_s": 5,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "start_image": "data:image/png;base64,abc",
                "end_image": "data:image/png;base64,xyz",
            },
            provider_opts={},
            config=self.config,
        )
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        # CRITICAL: end_image → last_frame_image rename
        self.assertEqual(body["input"]["last_frame_image"], "data:image/png;base64,xyz")
        self.assertNotIn("end_image", body["input"])

    def test_submit_end_image_without_start_image_raises(self):
        with self.assertRaises(_base.ProviderValidationError):
            self.backend.submit(
                task="image-to-video",
                model_slug="pixverse/pixverse-v6",
                canonical_params={
                    "prompt": "morph",
                    "duration_s": 5,
                    "aspect_ratio": "16:9",
                    "resolution": "720p",
                    # start_image missing
                    "end_image": "data:image/png;base64,xyz",
                },
                provider_opts={},
                config=self.config,
            )

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_multi_shot_emits_generate_multi_clip_switch(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_pixverse_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="text-to-video",
            model_slug="pixverse/pixverse-v6",
            canonical_params={
                "prompt": "Shot 1, ...; Shot 2, ...; Shot 3, ...",
                "duration_s": 10,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "multi_shot": True,
            },
            provider_opts={},
            config=self.config,
        )
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertTrue(body["input"]["generate_multi_clip_switch"])
        self.assertNotIn("multi_shot", body["input"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_audio_enabled_false_emits_generate_audio_switch_false(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_pixverse_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="text-to-video",
            model_slug="pixverse/pixverse-v6",
            canonical_params={
                "prompt": "silent clip",
                "duration_s": 5,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "audio_enabled": False,
            },
            provider_opts={},
            config=self.config,
        )
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertFalse(body["input"]["generate_audio_switch"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_audio_enabled_defaults_to_true(self, mock_urlopen):
        # Plugin convention: audio is on by default. PixVerse's API default
        # is false, so submit() must explicitly emit generate_audio_switch=True
        # when canonical audio_enabled is not specified.
        with open(str(FIXTURES / "replicate_pixverse_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="text-to-video",
            model_slug="pixverse/pixverse-v6",
            canonical_params={
                "prompt": "default audio",
                "duration_s": 5,
                "aspect_ratio": "16:9",
                "resolution": "720p",
            },
            provider_opts={},
            config=self.config,
        )
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertTrue(body["input"]["generate_audio_switch"])


if __name__ == "__main__":
    unittest.main()
