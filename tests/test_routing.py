"""Tests for scripts/routing.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import routing
from scripts.registry import registry as reg


class TestModelResolution(unittest.TestCase):
    def setUp(self):
        self.r = reg.load_registry()

    def test_explicit_model_wins(self):
        resolved = routing.resolve_model(
            self.r, family="video", explicit_model="kling-v3-omni", config={}
        )
        self.assertEqual(resolved, "kling-v3-omni")

    def test_config_default_model(self):
        resolved = routing.resolve_model(
            self.r, family="video", explicit_model=None,
            config={"defaults": {"video_model": "kling-v3-omni"}},
        )
        self.assertEqual(resolved, "kling-v3-omni")

    def test_registry_family_default(self):
        resolved = routing.resolve_model(
            self.r, family="video", explicit_model=None, config={},
        )
        self.assertEqual(resolved, "kling-v3")  # from family_defaults in models.json

    def test_unknown_model_raises(self):
        with self.assertRaises(routing.RoutingError):
            routing.resolve_model(
                self.r, family="video", explicit_model="does-not-exist", config={},
            )

    def test_no_default_for_unknown_family_raises(self):
        # No family_default for 'speech' in registry (deferred per v4.2.0 spec;
        # music was added in v4.2.1 sub-project B, so this test now targets speech.)
        with self.assertRaises(routing.RoutingError):
            routing.resolve_model(
                self.r, family="speech", explicit_model=None, config={},
            )


class TestProviderResolution(unittest.TestCase):
    def setUp(self):
        self.r = reg.load_registry()

    def test_explicit_provider_wins_when_hosts_model(self):
        prov = routing.resolve_provider(
            self.r, model_id="nano-banana-2", explicit_provider="replicate",
            config={"providers": {"replicate": {"api_key": "r8_x"}}},
        )
        self.assertEqual(prov, "replicate")

    def test_explicit_provider_not_hosting_model_raises(self):
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_provider(
                self.r, model_id="kling-v3", explicit_provider="gemini-direct",
                config={"providers": {"gemini-direct": {"api_key": "x"}}},
            )
        self.assertIn("not available on gemini-direct", str(ctx.exception))

    def test_family_default_wins_when_hosts_model(self):
        prov = routing.resolve_provider(
            self.r, model_id="kling-v3", explicit_provider=None,
            config={
                "defaults": {"video": "replicate"},
                "providers": {"replicate": {"api_key": "r8_x"}},
            },
        )
        self.assertEqual(prov, "replicate")

    def test_global_default_used_when_hosts_model(self):
        prov = routing.resolve_provider(
            self.r, model_id="kling-v3", explicit_provider=None,
            config={
                "default_provider": "replicate",
                "providers": {"replicate": {"api_key": "r8_x"}},
            },
        )
        self.assertEqual(prov, "replicate")

    def test_first_with_key_fallback(self):
        # No defaults set; registry order is gemini-direct, replicate for nano-banana-2
        # Only replicate has a key -> should pick replicate
        prov = routing.resolve_provider(
            self.r, model_id="nano-banana-2", explicit_provider=None,
            config={"providers": {"replicate": {"api_key": "r8_x"}}},
        )
        self.assertEqual(prov, "replicate")

    def test_first_with_key_respects_registry_order(self):
        # Both keys configured; registry lists gemini-direct first -> pick it
        prov = routing.resolve_provider(
            self.r, model_id="nano-banana-2", explicit_provider=None,
            config={
                "providers": {
                    "gemini-direct": {"api_key": "AIza"},
                    "replicate": {"api_key": "r8_x"},
                },
            },
        )
        self.assertEqual(prov, "gemini-direct")

    def test_no_key_configured_raises(self):
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_provider(
                self.r, model_id="kling-v3", explicit_provider=None, config={},
            )
        self.assertIn("no API key", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
