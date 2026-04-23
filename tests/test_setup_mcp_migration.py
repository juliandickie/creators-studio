"""Tests for setup_mcp.py config migration shim (v4.2.0)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "create-image" / "scripts"),
)

import setup_mcp


class TestMigrateOldFlatKeys(unittest.TestCase):
    def test_old_flat_keys_are_migrated(self):
        old = {
            "replicate_api_token": "r8_old",
            "google_api_key": "AIza_old",
            "elevenlabs_api_key": "sk_old",
        }
        new = setup_mcp.migrate_config_to_v4_2_0(old)
        self.assertEqual(new["providers"]["replicate"]["api_key"], "r8_old")
        self.assertEqual(new["providers"]["gemini"]["api_key"], "AIza_old")
        self.assertEqual(new["providers"]["elevenlabs"]["api_key"], "sk_old")

    def test_already_migrated_passes_through(self):
        already = {
            "providers": {
                "replicate": {"api_key": "r8_new"},
                "gemini": {"api_key": "AIza_new"},
            }
        }
        new = setup_mcp.migrate_config_to_v4_2_0(already)
        self.assertEqual(new["providers"]["replicate"]["api_key"], "r8_new")

    def test_mixed_schema_prefers_new(self):
        mixed = {
            "replicate_api_token": "r8_old",
            "providers": {"replicate": {"api_key": "r8_new"}},
        }
        new = setup_mcp.migrate_config_to_v4_2_0(mixed)
        # New wins over old when both present
        self.assertEqual(new["providers"]["replicate"]["api_key"], "r8_new")

    def test_non_api_keys_preserved(self):
        old = {
            "replicate_api_token": "r8_old",
            "custom_voices": {"narrator": {"voice_id": "abc"}},
            "named_creator_triggers": ["Annie Leibovitz"],
        }
        new = setup_mcp.migrate_config_to_v4_2_0(old)
        # Keys unrelated to provider auth pass through unchanged
        self.assertEqual(new["custom_voices"], {"narrator": {"voice_id": "abc"}})
        self.assertEqual(new["named_creator_triggers"], ["Annie Leibovitz"])

    def test_vertex_keys_grouped_under_vertex_provider(self):
        old = {
            "vertex_api_key": "ya29.x",
            "vertex_project_id": "my-project",
            "vertex_location": "us-central1",
        }
        new = setup_mcp.migrate_config_to_v4_2_0(old)
        self.assertEqual(new["providers"]["vertex"]["api_key"], "ya29.x")
        self.assertEqual(new["providers"]["vertex"]["project_id"], "my-project")
        self.assertEqual(new["providers"]["vertex"]["location"], "us-central1")

    def test_empty_config(self):
        # Empty config should still yield a consistent shape
        new = setup_mcp.migrate_config_to_v4_2_0({})
        self.assertIsInstance(new, dict)
        # No providers section unless there was something to put there
        # (that's OK — the routing layer handles missing providers gracefully)

    def test_none_config_is_safe(self):
        # Defensive: migrate should tolerate None/falsy
        self.assertEqual(setup_mcp.migrate_config_to_v4_2_0(None), {})


if __name__ == "__main__":
    unittest.main()
