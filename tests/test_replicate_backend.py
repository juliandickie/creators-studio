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


if __name__ == "__main__":
    unittest.main()
