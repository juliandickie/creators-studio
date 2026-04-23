"""Tests for scripts/backends/_base.py canonical types."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

# Add plugin root to path so we can import scripts.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backends import _base


class TestCanonicalTypes(unittest.TestCase):
    def test_job_ref_has_required_fields(self):
        ref = _base.JobRef(
            provider="replicate",
            external_id="abc123",
            poll_url="https://api.replicate.com/v1/predictions/abc123",
            raw={"id": "abc123"},
        )
        self.assertEqual(ref.provider, "replicate")
        self.assertEqual(ref.external_id, "abc123")

    def test_job_status_states_are_canonical(self):
        # Canonical 5 states: pending | running | succeeded | failed | canceled
        for state in ("pending", "running", "succeeded", "failed", "canceled"):
            status = _base.JobStatus(state=state, output=None, error=None, raw={})
            self.assertEqual(status.state, state)

    def test_task_result_cost_is_optional(self):
        result = _base.TaskResult(
            output_paths=[Path("/tmp/out.mp4")],
            output_urls=["https://example.com/out.mp4"],
            metadata={"duration_s": 8},
            provider_metadata={"prediction_id": "abc123"},
            cost=Decimal("0.16"),
            task_id="abc123",
        )
        self.assertEqual(result.cost, Decimal("0.16"))

        result_no_cost = _base.TaskResult(
            output_paths=[], output_urls=[], metadata={},
            provider_metadata={}, cost=None, task_id="xyz",
        )
        self.assertIsNone(result_no_cost.cost)

    def test_auth_status_bool(self):
        ok = _base.AuthStatus(ok=True, message="authenticated", provider="replicate")
        self.assertTrue(ok.ok)
        bad = _base.AuthStatus(ok=False, message="401 Unauthorized", provider="kie")
        self.assertFalse(bad.ok)


class TestExceptionHierarchy(unittest.TestCase):
    def test_validation_error_is_provider_error(self):
        self.assertTrue(issubclass(_base.ProviderValidationError, _base.ProviderError))

    def test_auth_error_is_provider_error(self):
        self.assertTrue(issubclass(_base.ProviderAuthError, _base.ProviderError))

    def test_http_error_is_provider_error(self):
        self.assertTrue(issubclass(_base.ProviderHTTPError, _base.ProviderError))


class TestProviderBackendABC(unittest.TestCase):
    def test_cannot_instantiate_abc_directly(self):
        with self.assertRaises(TypeError):
            _base.ProviderBackend()

    def test_subclass_without_all_methods_cannot_instantiate(self):
        class Incomplete(_base.ProviderBackend):
            name = "incomplete"

            def auth_check(self, config):
                pass

            # Missing submit, poll, parse_result

        with self.assertRaises(TypeError):
            Incomplete()

    def test_fully_implemented_subclass_instantiates(self):
        class Complete(_base.ProviderBackend):
            name = "complete"
            supported_tasks = {"text-to-image"}

            def auth_check(self, config):
                return _base.AuthStatus(ok=True, message="ok", provider="complete")

            def submit(self, *, task, model_slug, canonical_params, provider_opts, config):
                return _base.JobRef(
                    provider="complete", external_id="x",
                    poll_url="https://example.com", raw={},
                )

            def poll(self, job_ref, config):
                return _base.JobStatus(state="running", output=None, error=None, raw={})

            def parse_result(self, job_status, *, download_to):
                return _base.TaskResult(
                    output_paths=[], output_urls=[], metadata={},
                    provider_metadata={}, cost=None, task_id="x",
                )

        # Should not raise
        backend = Complete()
        self.assertEqual(backend.name, "complete")
        self.assertIn("text-to-image", backend.supported_tasks)


if __name__ == "__main__":
    unittest.main()
