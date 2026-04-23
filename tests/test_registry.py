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


class TestV42SubprojectBEntries(unittest.TestCase):
    """Verify sub-project B registry additions."""

    def setUp(self):
        self.r = reg.load_registry()

    def test_veo_3_1_tiers_registered(self):
        for mid in ("veo-3.1-lite", "veo-3.1-fast", "veo-3.1"):
            self.assertIn(mid, self.r.models, f"{mid} missing from registry")
            m = self.r.models[mid]
            self.assertEqual(m.family, "video")
            self.assertIn("replicate", m.providers)

    def test_veo_lite_uses_per_second_by_resolution(self):
        m = self.r.get_model("veo-3.1-lite")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_resolution")
        self.assertEqual(pricing["rates"]["720p"], 0.05)
        self.assertEqual(pricing["rates"]["1080p"], 0.08)

    def test_veo_fast_uses_per_second_by_audio(self):
        m = self.r.get_model("veo-3.1-fast")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_audio")
        self.assertEqual(pricing["rates"]["with_audio"], 0.15)
        self.assertEqual(pricing["rates"]["without_audio"], 0.10)

    def test_veo_standard_4k_in_resolutions(self):
        m = self.r.get_model("veo-3.1")
        self.assertIn("4K", m.canonical_constraints["resolutions"])

    def test_veo_lite_duration_is_enum(self):
        m = self.r.get_model("veo-3.1-lite")
        self.assertEqual(m.canonical_constraints["duration_s"], {"enum": [4, 6, 8]})

    def test_lyria_family_has_three_models(self):
        music_models = self.r.models_by_family("music")
        for mid in ("lyria-2", "lyria-3", "lyria-3-pro"):
            self.assertIn(mid, music_models, f"{mid} missing")

    def test_lyria_2_supports_negative_prompt(self):
        m = self.r.get_model("lyria-2")
        caps = m.providers["replicate"]["capabilities"]
        self.assertIn("negative_prompt", caps)

    def test_lyria_3_supports_reference_images(self):
        m = self.r.get_model("lyria-3")
        caps = m.providers["replicate"]["capabilities"]
        self.assertIn("reference_images", caps)

    def test_lyria_3_pro_supports_custom_lyrics(self):
        m = self.r.get_model("lyria-3-pro")
        caps = m.providers["replicate"]["capabilities"]
        self.assertIn("custom_lyrics", caps)

    def test_family_defaults_music_is_elevenlabs(self):
        self.assertEqual(self.r.family_default("music"), "elevenlabs-music")

    def test_elevenlabs_music_registered_with_direct_sentinel(self):
        m = self.r.get_model("elevenlabs-music")
        self.assertEqual(m.providers["elevenlabs"]["slug"], "(direct)")

    def test_kling_v3_pricing_corrected(self):
        m = self.r.get_model("kling-v3")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_resolution_and_audio")
        self.assertEqual(pricing["rates"]["1080p"]["with_audio"], 0.336)

    def test_kling_v3_omni_pricing_corrected(self):
        m = self.r.get_model("kling-v3-omni")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_resolution_and_audio")
        self.assertEqual(pricing["rates"]["1080p"]["with_audio"], 0.28)

    def test_registry_validates(self):
        # family_defaults now points at elevenlabs-music which IS registered.
        self.r.validate()  # Should not raise


class TestMultiModelPrinciple(unittest.TestCase):
    """v4.2.1+: every family must register at least 2 models."""

    def setUp(self):
        self.r = reg.load_registry()

    def test_video_family_has_multiple_models(self):
        vs = self.r.models_by_family("video")
        self.assertGreaterEqual(len(vs), 2, f"video has only {vs}")

    def test_music_family_has_multiple_models(self):
        ms = self.r.models_by_family("music")
        self.assertGreaterEqual(len(ms), 2, f"music has only {ms}")
        # Expect 4: lyria-2, lyria-3, lyria-3-pro, elevenlabs-music
        self.assertGreaterEqual(len(ms), 4)

    def test_image_family_single_text_to_image_is_allowed(self):
        # v4.2.1 image family has nano-banana-2 + recraft-vectorize.
        # Recraft is vectorize-only (not text-to-image), so text-to-image is
        # still single-model until sub-project C adds Kie.ai Imagen / Seedream / Flux.
        # This test documents the state rather than enforcing multi-model coverage
        # per-task; the multi-model principle applies per-family.
        text_to_image_models = [
            mid for mid in self.r.models_by_family("image")
            if "text-to-image" in self.r.models[mid].tasks
        ]
        self.assertGreaterEqual(len(text_to_image_models), 1)


if __name__ == "__main__":
    unittest.main()
