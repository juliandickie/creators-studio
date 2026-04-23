"""Tests for scripts/registry/registry.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.registry import registry as reg


class TestRegistryLoad(unittest.TestCase):
    def test_load_default_registry(self):
        r = reg.load_registry()
        self.assertEqual(r.version, 1)
        self.assertIn("kling-v3", r.models)

    def test_family_defaults_present(self):
        r = reg.load_registry()
        self.assertEqual(r.family_defaults["video"], "kling-v3")
        self.assertEqual(r.family_defaults["image"], "nano-banana-2")

    def test_model_entry_has_providers(self):
        r = reg.load_registry()
        kling = r.models["kling-v3"]
        self.assertIn("replicate", kling.providers)
        self.assertEqual(kling.providers["replicate"]["slug"], "kwaivgi/kling-v3-video")


class TestRegistryQuery(unittest.TestCase):
    def setUp(self):
        self.r = reg.load_registry()

    def test_get_model_by_id(self):
        m = self.r.get_model("kling-v3")
        self.assertEqual(m.display_name, "Kling Video 3.0")

    def test_get_model_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.r.get_model("does-not-exist")

    def test_models_by_family(self):
        videos = self.r.models_by_family("video")
        self.assertIn("kling-v3", videos)
        self.assertIn("fabric-1.0", videos)
        self.assertNotIn("nano-banana-2", videos)

    def test_providers_for_model(self):
        provs = self.r.providers_for_model("kling-v3")
        self.assertEqual(provs, ["replicate"])
        provs = self.r.providers_for_model("nano-banana-2")
        self.assertIn("gemini-direct", provs)
        self.assertIn("replicate", provs)

    def test_provider_order_preserved(self):
        # gemini-direct must appear BEFORE replicate for nano-banana-2
        # because it's listed first in models.json (routing fallback order)
        provs = self.r.providers_for_model("nano-banana-2")
        self.assertLess(provs.index("gemini-direct"), provs.index("replicate"))


class TestRegistryValidate(unittest.TestCase):
    def test_validate_passes_for_default(self):
        r = reg.load_registry()
        # Should not raise
        r.validate()

    def test_validate_catches_missing_family_default(self):
        # Inject a family default that doesn't exist in models
        r = reg.load_registry()
        r.family_defaults["image"] = "does-not-exist"
        with self.assertRaises(reg.RegistryValidationError):
            r.validate()

    def test_validate_catches_model_with_no_providers(self):
        r = reg.load_registry()
        r.models["kling-v3"].providers.clear()
        with self.assertRaises(reg.RegistryValidationError):
            r.validate()


if __name__ == "__main__":
    unittest.main()
