#!/usr/bin/env python3
"""Validate that LIVE config files point at things that actually exist.

WHY THIS EXISTS
---------------
The v4.0.0 rename (skills/banana -> skills/create-image) left several config
files pointing at paths that no longer existed. Because each one fails
silently, nobody noticed for months:

  - .github/workflows/validate.yml checked skills/banana/SKILL.md, so the whole
    CI job would have errored had it ever run (fixed in PR #16).
  - CODEOWNERS assigned owners to /skills/banana/, so those files had no owner
    at all - CODEOWNERS does not warn about rules that match nothing.
  - .github/dependabot.yml declared a "pip" ecosystem in a repo with zero pip
    dependencies and no manifest, so it could never produce an update.

The common shape is config that references something nonexistent and stays
quiet about it. This script turns that class of bug into a CI failure.

WHAT IS AND IS NOT CHECKED
--------------------------
Checked: STRUCTURED config, where a path is operative - the file's behaviour
depends on the path resolving. A pattern matching nothing there is always a bug.

NOT checked: prose documentation (CLAUDE.md, README.md) or historical records
(CHANGELOG.md, PROGRESS.md, ROADMAP.md, docs/plans/). This is deliberate and
was measured, not assumed: 52 of 137 backticked file tokens in CLAUDE.md do not
resolve as literal paths, because the docs legitimately mention bare basenames
("generate.py"), deliberately deleted files ("_vertex_backend.py" is documented
as removed in v4.2.1), user-home paths ("~/.creators-studio/config.json") and
gitignored reference dirs ("dev-docs/"). A gate at 38% false positives gets
muted, which is worse than no gate. Those files also legitimately contain the
retired names as historical record, which is why no repo-wide grep for
"skills/banana" or "nano-banana-studio" exists either.

Stdlib only, per the project's zero-pip-dependencies rule.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

# Dependabot ecosystem -> manifest globs that must exist for the entry to do
# anything. Ecosystems absent from this map are skipped rather than failed, so
# adding a new ecosystem never breaks CI on a name this script has not modelled.
ECOSYSTEM_MANIFESTS: dict[str, list[str]] = {
    "pip": [
        "requirements*.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "poetry.lock",
    ],
    "npm": ["package.json"],
    "docker": ["Dockerfile*"],
    "bundler": ["Gemfile"],
    "cargo": ["Cargo.toml"],
    "gomod": ["go.mod"],
    "composer": ["composer.json"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
    "terraform": ["*.tf"],
    "gitsubmodule": [".gitmodules"],
}

# github-actions is special: dependabot requires directory "/" and always reads
# workflow files from .github/workflows regardless of the directory setting.
GITHUB_ACTIONS_MANIFESTS = [".github/workflows/*.yml", ".github/workflows/*.yaml"]


class Finding:
    """One problem found in a live config file."""

    def __init__(self, file: str, line: int | None, message: str) -> None:
        self.file = file
        self.line = line
        self.message = message

    def render(self) -> str:
        """Format for the terminal, or as a GitHub Actions annotation in CI."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            loc = f"file={self.file}"
            if self.line is not None:
                loc += f",line={self.line}"
            return f"::error {loc}::{self.message}"
        where = self.file if self.line is None else f"{self.file}:{self.line}"
        return f"  {where}: {self.message}"


def tracked_files(root: Path) -> list[str]:
    """Every file git tracks, as repo-relative POSIX paths.

    Uses git rather than a filesystem walk so gitignored artifacts (dev-docs/,
    spikes/, __pycache__) never count as "existing" - CI checks out only
    tracked content, so anything untracked is absent as far as CI is concerned.
    """
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def codeowners_pattern_matches(pattern: str, paths: list[str]) -> bool:
    """Does a CODEOWNERS path pattern match at least one tracked file?

    Implements the realistic subset of the gitignore-style syntax CODEOWNERS
    uses: a bare "*" catch-all, root-anchored paths ("/scripts/x.py"),
    directory prefixes ("/skills/" or "docs/"), and unanchored globs ("*.py",
    matched against both the full path and the basename).
    """
    if pattern == "*":
        return True

    anchored = pattern.startswith("/")
    body = pattern.strip("/") if pattern.endswith("/") else pattern.lstrip("/")
    if not body:
        return True

    is_dir = pattern.endswith("/")

    for path in paths:
        if is_dir:
            # Directory rule: match anything beneath it.
            if path == body or path.startswith(body + "/"):
                return True
            if not anchored and (f"/{body}/" in f"/{path}"):
                return True
            continue

        if path == body or fnmatch(path, body):
            return True
        if not anchored:
            # Unanchored patterns also match by basename or any path suffix,
            # which is how "*.py" and "SKILL.md" behave in CODEOWNERS.
            if fnmatch(os.path.basename(path), body) or path.endswith(f"/{body}"):
                return True

    return False


def check_codeowners(root: Path, paths: list[str]) -> list[Finding]:
    """Every CODEOWNERS rule must match at least one tracked file.

    A rule matching nothing means those files silently have no owner, which is
    exactly how the retired /skills/banana/ rules survived the v4.0.0 rename.
    Comment and blank lines are skipped by parsing, so prose explaining a past
    removal never trips this.
    """
    rel = "CODEOWNERS"
    target = root / rel
    if not target.is_file():
        return []

    findings: list[Finding] = []
    for lineno, raw in enumerate(target.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        pattern = fields[0]
        if len(fields) < 2:
            findings.append(
                Finding(rel, lineno, f"rule {pattern!r} has no owner assigned")
            )
            continue
        if not codeowners_pattern_matches(pattern, paths):
            findings.append(
                Finding(
                    rel,
                    lineno,
                    f"pattern {pattern!r} matches no tracked file, so those "
                    f"paths have no code owner (stale after a rename?)",
                )
            )
    return findings


def _dir_prefix(directory: str) -> str:
    """Normalise a dependabot `directory` value to a repo-relative prefix."""
    cleaned = (directory or "/").strip("/")
    return f"{cleaned}/" if cleaned else ""


def check_dependabot(root: Path, paths: list[str]) -> list[Finding]:
    """Every declared dependabot ecosystem must have a manifest to track.

    Catches the inverse of a stale path: an entry that looks active but can
    never fire, like the "pip" entry this repo carried despite having zero pip
    dependencies and no requirements.txt.
    """
    rel = ".github/dependabot.yml"
    target = root / rel
    if not target.is_file():
        return []

    entries = _parse_dependabot_entries(target.read_text())
    findings: list[Finding] = []

    for lineno, ecosystem, directory in entries:
        globs = (
            GITHUB_ACTIONS_MANIFESTS
            if ecosystem == "github-actions"
            else ECOSYSTEM_MANIFESTS.get(ecosystem)
        )
        if globs is None:
            continue  # ecosystem we do not model; do not guess

        prefix = "" if ecosystem == "github-actions" else _dir_prefix(directory)
        if any(fnmatch(p, f"{prefix}{g}") for g in globs for p in paths):
            continue

        findings.append(
            Finding(
                rel,
                lineno,
                f"ecosystem {ecosystem!r} (directory {directory!r}) has no "
                f"manifest to track, so it can never produce an update; "
                f"expected one of: {', '.join(globs)}",
            )
        )
    return findings


def _parse_dependabot_entries(text: str) -> list[tuple[int, str, str]]:
    """Extract (line, ecosystem, directory) triples without a YAML dependency.

    dependabot.yml has a fixed, shallow shape, so a line scan is enough and
    keeps this script stdlib-only. Each `- package-ecosystem:` opens an entry;
    the following `directory:` belongs to it.
    """
    entries: list[tuple[int, str, str]] = []
    current: list | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("- package-ecosystem:") or line.startswith(
            "package-ecosystem:"
        ):
            if current:
                entries.append(tuple(current))  # type: ignore[arg-type]
            value = line.split(":", 1)[1].strip().strip("\"'")
            current = [lineno, value, "/"]
        elif line.startswith("directory:") and current:
            current[2] = line.split(":", 1)[1].strip().strip("\"'")

    if current:
        entries.append(tuple(current))  # type: ignore[arg-type]
    return entries


def check_marketplace_source(root: Path) -> list[Finding]:
    """Each local plugin `source` in marketplace.json must resolve to a plugin.

    Paths resolve relative to the directory CONTAINING .claude-plugin/, so for
    this repo "./" correctly points at the plugin root. Remote sources (git or
    URL objects) are skipped.
    """
    rel = ".claude-plugin/marketplace.json"
    target = root / rel
    if not target.is_file():
        return []

    try:
        data = json.loads(target.read_text())
    except json.JSONDecodeError as exc:
        return [Finding(rel, None, f"invalid JSON: {exc}")]

    findings: list[Finding] = []
    for entry in data.get("plugins", []):
        source = entry.get("source")
        if not isinstance(source, str):
            continue  # remote/object sources are out of scope
        resolved = (root / source).resolve()
        name = entry.get("name", "<unnamed>")
        if not resolved.is_dir():
            findings.append(
                Finding(rel, None, f"plugin {name!r} source {source!r} is not a directory")
            )
        elif not (resolved / ".claude-plugin" / "plugin.json").is_file():
            findings.append(
                Finding(
                    rel,
                    None,
                    f"plugin {name!r} source {source!r} has no "
                    f".claude-plugin/plugin.json",
                )
            )
    return findings


def run_checks(root: Path) -> list[Finding]:
    """Run every live-config check and return the combined findings."""
    paths = tracked_files(root)
    return [
        *check_codeowners(root, paths),
        *check_dependabot(root, paths),
        *check_marketplace_source(root),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate that live config files reference things that exist."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repo root (defaults to this script's repo).",
    )
    args = parser.parse_args(argv)

    findings = run_checks(args.root)
    if findings:
        print(f"Live config check FAILED with {len(findings)} problem(s):")
        for finding in findings:
            print(finding.render())
        return 1

    print("Live config check passed: CODEOWNERS, dependabot.yml and "
          "marketplace.json all reference paths that exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
