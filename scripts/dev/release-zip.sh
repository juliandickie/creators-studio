#!/usr/bin/env bash
# scripts/dev/release-zip.sh — build a distribution zip and create a GitHub Release.
#
# WHY THIS SCRIPT EXISTS
# ----------------------
# The plugin's primary install path is the native `/plugin marketplace add`
# flow, which fetches the catalog live from GitHub — no zip needed for that
# audience. But for users who prefer to download a pinned snapshot (offline
# installs, corporate environments without git access, demoing a specific
# version), the project also publishes a `.zip` artifact attached to each
# GitHub Release.
#
# This script automates the build-and-release sequence documented in
# CLAUDE.md "Feature Completion Checklist → step 11":
#   1. Validate the version argument matches plugin.json
#   2. Build the zip with the canonical exclude list
#   3. `gh release create` with the zip attached
#
# WHAT THIS SCRIPT WILL **NOT** DO
# --------------------------------
# - It will NOT bump the version. Run a separate version-bump commit (touching
#   plugin.json, README badge, CITATION.cff, CHANGELOG, PROGRESS) BEFORE
#   invoking this script. The script just packages and releases what's
#   already committed.
# - It will NOT push commits or branches. Make sure the version-bump commit
#   has already merged to main before tagging. The script tags the current
#   `main` HEAD on the remote.
# - It will NOT create a release if the tag already exists.
#
# USAGE
# -----
#   scripts/dev/release-zip.sh 4.2.2
#   scripts/dev/release-zip.sh 4.2.2 "Custom release notes here"
#
# The version argument is BARE (no leading 'v') — the script adds it where
# needed. This matches plugin.json's `"version": "4.2.2"` form.

set -euo pipefail

# ---------- argument parsing ----------

if [[ $# -lt 1 ]]; then
  cat <<'USAGE' >&2
Usage: scripts/dev/release-zip.sh <version> [release notes]

Examples:
  scripts/dev/release-zip.sh 4.2.2
  scripts/dev/release-zip.sh 4.2.2 "See CHANGELOG.md for details"

Pre-flight requirements:
  - Version argument matches `version` in .claude-plugin/plugin.json
  - That version's CHANGELOG.md entry exists
  - Version-bump commit has already been pushed to origin/main
USAGE
  exit 1
fi

version="$1"
notes="${2:-See CHANGELOG.md for details}"

# Validate version is a sane semver (e.g. 4.2.2 or 4.2.2.1 — no leading v)
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
  echo "ERROR: version must be a bare semver like 4.2.2 (no leading 'v', no suffix)" >&2
  exit 1
fi

tag="v${version}"
zipname="creators-studio-${tag}.zip"

# ---------- preflight ----------

command -v gh    >/dev/null || { echo "ERROR: gh CLI not installed. Run: brew install gh" >&2; exit 1; }
command -v zip   >/dev/null || { echo "ERROR: zip not installed (try: brew install zip)" >&2; exit 1; }
command -v jq    >/dev/null || { echo "ERROR: jq not installed (try: brew install jq)" >&2; exit 1; }

# Verify plugin root
if [[ ! -f .claude-plugin/plugin.json ]]; then
  echo "ERROR: Run this from the plugin root (where .claude-plugin/plugin.json lives)." >&2
  exit 1
fi

# Cross-check version against plugin.json
manifest_version=$(jq -r '.version' .claude-plugin/plugin.json)
if [[ "$manifest_version" != "$version" ]]; then
  echo "ERROR: version mismatch." >&2
  echo "  Argument:        $version" >&2
  echo "  plugin.json:     $manifest_version" >&2
  echo "  Bump plugin.json (and README badge + CITATION.cff) before running this script." >&2
  exit 1
fi

# Cross-check CHANGELOG has the section
if ! grep -q "^## \[${version}\]" CHANGELOG.md; then
  echo "ERROR: no '## [${version}]' section found in CHANGELOG.md." >&2
  echo "  Add the section before releasing." >&2
  exit 1
fi

# Verify gh is authenticated
if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh CLI not authenticated. Run: gh auth login" >&2
  exit 1
fi

# Verify the tag doesn't already exist on the remote
if gh release view "$tag" >/dev/null 2>&1; then
  echo "ERROR: GitHub Release '$tag' already exists. Delete it first or pick a new version." >&2
  exit 1
fi

# Working tree must be clean (we're packaging committed state)
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: working tree is dirty. Commit or stash before releasing." >&2
  echo "(Releases must reflect committed state, not local edits.)" >&2
  exit 1
fi

# Local main must match origin/main (release tags origin/main HEAD)
git fetch origin main --quiet
local_main=$(git rev-parse main)
remote_main=$(git rev-parse origin/main)
if [[ "$local_main" != "$remote_main" ]]; then
  echo "ERROR: local main ($local_main) does not match origin/main ($remote_main)." >&2
  echo "  Push or pull first so the release matches what's on GitHub." >&2
  exit 1
fi

# ---------- show plan ----------

echo "Plan:"
echo "  Version:    $version"
echo "  Tag:        $tag"
echo "  Zip:        ../$zipname"
echo "  Tagging:    origin/main @ ${remote_main:0:7}"
echo "  Notes:      $notes"
echo

# ---------- build zip ----------

# Exclude list (synced with CLAUDE.md "GitHub Release + Distribution Zips"):
#   - .git/                — repo metadata
#   - .DS_Store, __pycache__, *.pyc — OS / Python detritus
#   - .github/             — CI config not needed by users
#   - screenshots/         — 11+ MB of WebP source images
#   - PROGRESS.md          — dev-history noise
#   - ROADMAP.md           — internal planning doc
#   - CODEOWNERS, CODE_OF_CONDUCT.md, SECURITY.md, CITATION.cff — repo meta
#   - .gitattributes, .gitignore — git metadata
#   - .claude/             — local Claude Code settings
#   - spikes/              — exploratory work, confusing for end-users
#   - tests/               — dev-only, users don't need them
#   - dev-docs/            — third-party reference dumps (large)
#   - scripts/dev/         — these very release scripts; users don't need them
zip_target="../${zipname}"
if [[ -f "$zip_target" ]]; then
  echo "Removing stale ${zip_target}"
  rm -f "$zip_target"
fi

zip -r "$zip_target" . \
  -x ".git/*" \
  -x ".DS_Store" \
  -x "*/.DS_Store" \
  -x "*__pycache__/*" \
  -x "*.pyc" \
  -x ".github/*" \
  -x "screenshots/*" \
  -x "PROGRESS.md" \
  -x "ROADMAP.md" \
  -x "CODEOWNERS" \
  -x "CODE_OF_CONDUCT.md" \
  -x "SECURITY.md" \
  -x "CITATION.cff" \
  -x ".gitattributes" \
  -x ".gitignore" \
  -x ".claude/*" \
  -x "spikes/*" \
  -x "tests/*" \
  -x "dev-docs/*" \
  -x "scripts/dev/*"

zip_size=$(du -h "$zip_target" | awk '{print $1}')
echo
echo "✓ Built ${zip_target} (${zip_size})"

# ---------- create release ----------

gh release create "$tag" \
  "$zip_target" \
  --title "$tag" \
  --notes "$notes"

# Refetch tags so local repo knows about the new tag
git fetch origin --tags --quiet

echo
echo "✓ Released $tag"
echo "  https://github.com/juliandickie/creators-studio/releases/tag/$tag"
echo
echo "Cleanup (optional): rm $zip_target"
