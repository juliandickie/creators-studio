"""Tests for scripts/paths.py — the v4.2.2 ~/.banana/ → ~/.creators-studio/
config-directory migration helper.

Uses a temporary directory + monkeypatched ``Path.home()`` so the real
user state is never touched. All four state-graph corners are covered:
  - neither dir exists (first-ever install)
  - only old dir exists (v4.2.1-and-earlier upgrade path)
  - only new dir exists (fresh v4.2.2+ install)
  - both dirs exist (post-migration steady state)
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import paths


class _FakeHomeMixin:
    """TestCase mixin that gives each test a clean ~/ via a temp directory."""

    def setUp(self):
        # Each test gets its own temp dir as the fake $HOME so paths.py's
        # Path.home() returns it. Cleaned up in tearDown.
        self._tmp = tempfile.mkdtemp(prefix="creators_studio_test_home_")
        self._home_patcher = patch(
            "scripts.paths.Path.home",
            return_value=Path(self._tmp),
        )
        self._home_patcher.start()

    def tearDown(self):
        self._home_patcher.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)

    @property
    def home(self) -> Path:
        return Path(self._tmp)


class TestNeitherDirectoryExists(_FakeHomeMixin, unittest.TestCase):
    """First-ever install at v4.2.2+: no ~/.banana/, no ~/.creators-studio/."""

    def test_creators_studio_dir_creates_new(self):
        self.assertFalse((self.home / ".banana").exists())
        self.assertFalse((self.home / ".creators-studio").exists())

        result = paths.creators_studio_dir()

        self.assertEqual(result, self.home / ".creators-studio")
        self.assertTrue(result.exists())
        # Old dir should NOT have been created
        self.assertFalse((self.home / ".banana").exists())

    def test_status_reports_none(self):
        status = paths.migration_status()
        self.assertEqual(status["state"], "none")
        self.assertFalse(status["new_exists"])
        self.assertFalse(status["old_exists"])

    def test_idempotent_repeat_calls(self):
        first = paths.creators_studio_dir()
        second = paths.creators_studio_dir()
        third = paths.creators_studio_dir()
        self.assertEqual(first, second)
        self.assertEqual(second, third)


class TestOnlyOldExists(_FakeHomeMixin, unittest.TestCase):
    """v4.2.1-and-earlier upgrade: ~/.banana/ has user state, no new dir."""

    def setUp(self):
        super().setUp()
        old = self.home / ".banana"
        old.mkdir()
        # Populate with realistic user state
        (old / "config.json").write_text(json.dumps({
            "providers": {"replicate": {"api_key": "r8_test"}},
            "google_ai_api_key": "AIza-test",
        }))
        (old / "costs.json").write_text('{"entries": [], "totals": {}}')
        (old / "presets").mkdir()
        (old / "presets" / "my-brand.json").write_text('{"name": "my-brand"}')
        (old / "custom_voices").mkdir()
        (old / "custom_voices" / "narrator.json").write_text(
            '{"voice_id": "abc", "source_type": "designed"}'
        )

    def test_creators_studio_dir_triggers_copy_migration(self):
        result = paths.creators_studio_dir()
        self.assertEqual(result, self.home / ".creators-studio")
        # New dir created
        self.assertTrue(result.exists())
        # Old dir preserved (NOT moved)
        self.assertTrue((self.home / ".banana").exists())

    def test_migration_copies_files(self):
        paths.creators_studio_dir()
        new = self.home / ".creators-studio"
        # All files copied
        self.assertTrue((new / "config.json").exists())
        self.assertTrue((new / "costs.json").exists())
        self.assertTrue((new / "presets" / "my-brand.json").exists())
        self.assertTrue((new / "custom_voices" / "narrator.json").exists())

    def test_migration_preserves_file_contents(self):
        paths.creators_studio_dir()
        new = self.home / ".creators-studio"
        config = json.loads((new / "config.json").read_text())
        self.assertEqual(config["google_ai_api_key"], "AIza-test")
        self.assertEqual(
            config["providers"]["replicate"]["api_key"], "r8_test",
        )

    def test_migration_preserves_old_dir_contents(self):
        # The old dir must be intact after migration so v4.2.1 plugins
        # still work AND the user can manually verify before deleting.
        paths.creators_studio_dir()
        old = self.home / ".banana"
        self.assertTrue((old / "config.json").exists())
        self.assertTrue((old / "presets" / "my-brand.json").exists())
        self.assertTrue((old / "custom_voices" / "narrator.json").exists())

    def test_status_reports_old_only_before_call(self):
        # Before any call to creators_studio_dir(), status should report
        # old_only.
        status = paths.migration_status()
        self.assertEqual(status["state"], "old_only")
        self.assertTrue(status["old_exists"])
        self.assertFalse(status["new_exists"])

    def test_status_reports_migrated_after_call(self):
        paths.creators_studio_dir()  # trigger migration
        status = paths.migration_status()
        self.assertEqual(status["state"], "migrated")
        self.assertTrue(status["old_exists"])
        self.assertTrue(status["new_exists"])

    def test_idempotent_after_migration(self):
        first = paths.creators_studio_dir()
        # Touch the new dir to confirm second call doesn't re-copy
        marker = first / ".test_marker"
        marker.touch()
        second = paths.creators_studio_dir()
        # The second call returned the same dir without re-copying
        self.assertEqual(first, second)
        self.assertTrue(marker.exists())


class TestOnlyNewExists(_FakeHomeMixin, unittest.TestCase):
    """Fresh v4.2.2+ install: ~/.creators-studio/ already exists, no old."""

    def setUp(self):
        super().setUp()
        new = self.home / ".creators-studio"
        new.mkdir()
        (new / "config.json").write_text('{"existing": "state"}')

    def test_creators_studio_dir_returns_existing_no_op(self):
        result = paths.creators_studio_dir()
        self.assertEqual(result, self.home / ".creators-studio")
        # Old dir should not have been created
        self.assertFalse((self.home / ".banana").exists())
        # Existing state untouched
        self.assertEqual(
            json.loads((result / "config.json").read_text())["existing"],
            "state",
        )

    def test_status_reports_new_only(self):
        status = paths.migration_status()
        self.assertEqual(status["state"], "new_only")
        self.assertTrue(status["new_exists"])
        self.assertFalse(status["old_exists"])


class TestBothExist(_FakeHomeMixin, unittest.TestCase):
    """Post-migration steady state: both ~/.banana/ AND ~/.creators-studio/.

    creators_studio_dir() should return the new dir without re-copying,
    leaving both intact.
    """

    def setUp(self):
        super().setUp()
        old = self.home / ".banana"
        new = self.home / ".creators-studio"
        old.mkdir()
        new.mkdir()
        (old / "config.json").write_text('{"in": "old"}')
        (new / "config.json").write_text('{"in": "new"}')

    def test_returns_new_dir_no_recopy(self):
        result = paths.creators_studio_dir()
        self.assertEqual(result, self.home / ".creators-studio")
        # Both still exist with their distinct contents
        self.assertEqual(
            json.loads((result / "config.json").read_text())["in"], "new",
        )
        self.assertEqual(
            json.loads((self.home / ".banana" / "config.json").read_text())["in"],
            "old",
        )

    def test_status_reports_migrated(self):
        status = paths.migration_status()
        self.assertEqual(status["state"], "migrated")


class TestConvenienceAccessors(_FakeHomeMixin, unittest.TestCase):
    """The 8 convenience helpers (config_path, costs_path, etc.) all
    point inside ~/.creators-studio/."""

    def test_all_accessors_under_creators_studio_dir(self):
        base = paths.creators_studio_dir()
        self.assertEqual(paths.config_path(), base / "config.json")
        self.assertEqual(paths.costs_path(), base / "costs.json")
        self.assertEqual(paths.presets_dir(), base / "presets")
        self.assertEqual(paths.history_dir(), base / "history")
        self.assertEqual(paths.assets_dir(), base / "assets")
        self.assertEqual(
            paths.ab_preferences_path(), base / "ab_preferences.json",
        )
        self.assertEqual(paths.ab_history_dir(), base / "ab_history")
        self.assertEqual(paths.analytics_path(), base / "analytics.html")


class TestSymlinkPreservation(_FakeHomeMixin, unittest.TestCase):
    """Symlinks in ~/.banana/ should survive the copytree migration."""

    def test_symlink_to_external_file_preserved(self):
        old = self.home / ".banana"
        old.mkdir()
        # Create a target file outside the dir
        target_dir = Path(self._tmp) / "external"
        target_dir.mkdir()
        target_file = target_dir / "shared.json"
        target_file.write_text('{"shared": true}')
        # Symlink inside ~/.banana/ pointing at it
        link = old / "shared_link.json"
        os.symlink(target_file, link)

        paths.creators_studio_dir()

        new_link = self.home / ".creators-studio" / "shared_link.json"
        self.assertTrue(new_link.is_symlink())
        # And it still resolves correctly
        self.assertEqual(
            json.loads(new_link.read_text())["shared"], True,
        )


class TestMigrationFailureFallback(_FakeHomeMixin, unittest.TestCase):
    """If shutil.copytree raises, fall back to old dir + log error."""

    def setUp(self):
        super().setUp()
        old = self.home / ".banana"
        old.mkdir()
        (old / "config.json").write_text('{"keep": "this"}')

    @patch("scripts.paths.shutil.copytree", side_effect=PermissionError("denied"))
    def test_copy_failure_falls_back_to_old_dir(self, _mock):
        with self.assertLogs(paths._logger, level="ERROR") as cm:
            result = paths.creators_studio_dir()
        # Returned old dir as fallback
        self.assertEqual(result, self.home / ".banana")
        # Logged the failure
        self.assertTrue(any("Migration" in msg and "failed" in msg
                            for msg in cm.output))
        # Old dir intact
        self.assertEqual(
            json.loads((result / "config.json").read_text())["keep"], "this",
        )


if __name__ == "__main__":
    unittest.main()
