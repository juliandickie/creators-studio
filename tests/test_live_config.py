"""Tests for scripts/dev/check_live_config.py - the live-config staleness gate.

The point of this gate is to fail when a config file references something that
does not exist. A matcher bug would make it pass silently, which is the exact
failure mode it was written to prevent, so the pattern matcher and each check
are tested directly - including regression tests that replay the real
pre-fix CODEOWNERS and dependabot.yml content and assert they are caught.

Imported by file path rather than as a package: scripts/dev/ deliberately has
no __init__.py (it holds dev tooling excluded from release zips).
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "dev" / "check_live_config.py"
)
_spec = importlib.util.spec_from_file_location("check_live_config", _MODULE_PATH)
assert _spec and _spec.loader
clc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clc)


# Representative slice of the real repo layout.
PATHS = [
    "CODEOWNERS",
    "CLAUDE.md",
    "README.md",
    ".github/workflows/validate.yml",
    ".github/dependabot.yml",
    ".claude-plugin/plugin.json",
    "skills/create-image/SKILL.md",
    "skills/create-image/references/gemini-models.md",
    "skills/create-image/scripts/generate.py",
    "skills/create-video/SKILL.md",
    "skills/create-transcript/SKILL.md",
    "scripts/routing.py",
    "tests/test_routing.py",
]


class PatternMatchingTests(unittest.TestCase):
    def test_catch_all_matches(self):
        self.assertTrue(clc.codeowners_pattern_matches("*", PATHS))

    def test_anchored_file_that_exists(self):
        self.assertTrue(
            clc.codeowners_pattern_matches("/skills/create-image/SKILL.md", PATHS)
        )

    def test_anchored_file_that_does_not_exist(self):
        self.assertFalse(
            clc.codeowners_pattern_matches("/skills/banana/SKILL.md", PATHS)
        )

    def test_anchored_directory_that_exists(self):
        self.assertTrue(
            clc.codeowners_pattern_matches("/skills/create-image/references/", PATHS)
        )

    def test_anchored_directory_that_does_not_exist(self):
        self.assertFalse(
            clc.codeowners_pattern_matches("/skills/banana/references/", PATHS)
        )

    def test_unanchored_directory(self):
        self.assertTrue(clc.codeowners_pattern_matches("tests/", PATHS))

    def test_extension_glob(self):
        self.assertTrue(clc.codeowners_pattern_matches("*.py", PATHS))

    def test_extension_glob_with_no_matches(self):
        self.assertFalse(clc.codeowners_pattern_matches("*.rs", PATHS))

    def test_bare_basename(self):
        self.assertTrue(clc.codeowners_pattern_matches("SKILL.md", PATHS))


class CodeownersTests(unittest.TestCase):
    def _write(self, body: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "CODEOWNERS").write_text(body)
        return tmp

    def test_live_rules_produce_no_findings(self):
        root = self._write("# Global owner\n* @juliandickie\n")
        self.assertEqual(clc.check_codeowners(root, PATHS), [])

    def test_stale_rule_is_flagged(self):
        root = self._write("/skills/banana/SKILL.md @juliandickie\n")
        findings = clc.check_codeowners(root, PATHS)
        self.assertEqual(len(findings), 1)
        self.assertIn("matches no tracked file", findings[0].message)
        self.assertEqual(findings[0].line, 1)

    def test_comments_and_blanks_are_skipped(self):
        # A comment explaining a past removal must not trip the check - the
        # real CODEOWNERS carries exactly such a note about /skills/banana/.
        root = self._write(
            "# The previous rules pointed at /skills/banana/, now removed.\n"
            "\n"
            "* @juliandickie\n"
        )
        self.assertEqual(clc.check_codeowners(root, PATHS), [])

    def test_rule_without_owner_is_flagged(self):
        root = self._write("/scripts/routing.py\n")
        findings = clc.check_codeowners(root, PATHS)
        self.assertEqual(len(findings), 1)
        self.assertIn("no owner assigned", findings[0].message)

    def test_missing_codeowners_file_is_not_an_error(self):
        self.assertEqual(
            clc.check_codeowners(Path(tempfile.mkdtemp()), PATHS), []
        )

    def test_regression_real_pre_fix_content_is_caught(self):
        """The actual CODEOWNERS that shipped broken for months."""
        root = self._write(
            "# Global owner\n"
            "* @juliandickie\n"
            "\n"
            "# Skill core\n"
            "/skills/banana/SKILL.md @juliandickie\n"
            "/skills/banana/references/ @juliandickie\n"
        )
        findings = clc.check_codeowners(root, PATHS)
        self.assertEqual(len(findings), 2)
        self.assertEqual([f.line for f in findings], [5, 6])


class DependabotTests(unittest.TestCase):
    def _write(self, body: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / ".github").mkdir()
        (tmp / ".github" / "dependabot.yml").write_text(body)
        return tmp

    GITHUB_ACTIONS_ONLY = (
        'version: 2\n'
        'updates:\n'
        '  - package-ecosystem: "github-actions"\n'
        '    directory: "/"\n'
        '    schedule:\n'
        '      interval: "weekly"\n'
    )

    def test_github_actions_with_workflows_is_clean(self):
        root = self._write(self.GITHUB_ACTIONS_ONLY)
        self.assertEqual(clc.check_dependabot(root, PATHS), [])

    def test_pip_without_manifest_is_flagged(self):
        root = self._write(
            'version: 2\n'
            'updates:\n'
            '  - package-ecosystem: "pip"\n'
            '    directory: "/"\n'
        )
        findings = clc.check_dependabot(root, PATHS)
        self.assertEqual(len(findings), 1)
        self.assertIn("no manifest to track", findings[0].message)

    def test_pip_with_manifest_is_clean(self):
        root = self._write(
            'version: 2\n'
            'updates:\n'
            '  - package-ecosystem: "pip"\n'
            '    directory: "/"\n'
        )
        self.assertEqual(
            clc.check_dependabot(root, PATHS + ["requirements.txt"]), []
        )

    def test_unmodelled_ecosystem_is_skipped_not_failed(self):
        root = self._write(
            'version: 2\n'
            'updates:\n'
            '  - package-ecosystem: "some-future-ecosystem"\n'
            '    directory: "/"\n'
        )
        self.assertEqual(clc.check_dependabot(root, PATHS), [])

    def test_comments_are_ignored_by_the_parser(self):
        root = self._write(
            'version: 2\n'
            'updates:\n'
            '  # No "pip" entry on purpose - zero pip dependencies.\n'
            '  - package-ecosystem: "github-actions"\n'
            '    directory: "/"\n'
        )
        self.assertEqual(clc.check_dependabot(root, PATHS), [])

    def test_regression_real_pre_fix_content_is_caught(self):
        """The actual dependabot.yml with the no-op pip entry."""
        root = self._write(
            'version: 2\n'
            'updates:\n'
            '  - package-ecosystem: "pip"\n'
            '    directory: "/"\n'
            '    schedule:\n'
            '      interval: "weekly"\n'
            '    labels:\n'
            '      - "dependencies"\n'
            '    open-pull-requests-limit: 5\n'
            '  - package-ecosystem: "github-actions"\n'
            '    directory: "/"\n'
            '    schedule:\n'
            '      interval: "weekly"\n'
        )
        findings = clc.check_dependabot(root, PATHS)
        self.assertEqual(len(findings), 1)
        self.assertIn("'pip'", findings[0].message)


class MarketplaceSourceTests(unittest.TestCase):
    def _write(self, source: str, *, create_plugin: bool) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / ".claude-plugin").mkdir()
        (tmp / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"plugins": [{"name": "creators-studio", "source": source}]})
        )
        if create_plugin:
            (tmp / ".claude-plugin" / "plugin.json").write_text('{"name": "x"}')
        return tmp

    def test_valid_local_source_is_clean(self):
        root = self._write("./", create_plugin=True)
        self.assertEqual(clc.check_marketplace_source(root), [])

    def test_source_without_plugin_manifest_is_flagged(self):
        root = self._write("./", create_plugin=False)
        findings = clc.check_marketplace_source(root)
        self.assertEqual(len(findings), 1)
        self.assertIn("no .claude-plugin/plugin.json", findings[0].message)

    def test_source_pointing_at_missing_directory_is_flagged(self):
        root = self._write("./does-not-exist", create_plugin=True)
        findings = clc.check_marketplace_source(root)
        self.assertEqual(len(findings), 1)
        self.assertIn("not a directory", findings[0].message)


class RealRepoTests(unittest.TestCase):
    def test_this_repo_passes_all_live_config_checks(self):
        root = Path(__file__).resolve().parent.parent
        findings = clc.run_checks(root)
        self.assertEqual(
            findings, [], "\n".join(f.render() for f in findings)
        )


if __name__ == "__main__":
    unittest.main()
