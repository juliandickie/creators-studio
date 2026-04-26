#!/usr/bin/env bash
# scripts/dev/publish.sh — open a PR for currently-modified files.
#
# WHY THIS SCRIPT EXISTS
# ----------------------
# Direct pushes to `main` are blocked by the Claude Code harness's default
# safety rail ("Push to default branch (main) bypasses pull request review").
# So the standard flow for landing changes on this repo goes through a PR:
#
#   1. Create a feature branch
#   2. Commit changes onto it (NOT onto main)
#   3. Push the branch
#   4. Open a PR via `gh pr create`
#   5. Merge it on GitHub (squash recommended)
#
# This script automates all of that so you don't have to remember the
# sequence. Particularly the "if you accidentally committed to main, roll
# main back to origin/main while keeping the commit on the new branch"
# trick (`git branch -f main origin/main`) — easy to forget, hard to debug.
#
# USAGE
# -----
#   scripts/dev/publish.sh "docs: short commit title"
#   scripts/dev/publish.sh "fix: bug in foo" "Multi-line PR body."
#
# The first argument is the commit title (also used as the PR title).
# Conventional Commit prefixes (`docs:`, `feat:`, `fix:`, `chore:`,
# `refactor:`) are recognized — the type drives the branch prefix
# (`docs/...`, `feat/...`, etc), and the rest becomes the slug.
#
# WHAT THIS SCRIPT WILL **NOT** DO
# --------------------------------
# - It will NOT bump versions, edit CHANGELOG, or touch CITATION.cff.
#   Those are part of the version-release workflow — see
#   `scripts/dev/release-zip.sh` for that flow.
# - It will NOT use `git add -A` — only tracked files modified in your
#   working tree are staged. Untracked files are left alone (per the
#   CLAUDE.md commit-policy — avoids accidentally committing .env,
#   credentials, screenshots, etc).
# - It will NOT push or commit if there's nothing to commit.
# - It will NOT amend prior commits (per the CLAUDE.md no-amend rule).

set -euo pipefail

# ---------- argument parsing ----------

if [[ $# -lt 1 ]]; then
  cat <<'USAGE' >&2
Usage: scripts/dev/publish.sh "<commit title>" [body]

Examples:
  scripts/dev/publish.sh "docs: clarify install path"
  scripts/dev/publish.sh "fix: wrong ratio in social.py" "Closes #42."
USAGE
  exit 1
fi

title="$1"
body="${2:-}"

# ---------- preflight checks ----------

command -v gh  >/dev/null || { echo "ERROR: gh CLI not installed. Install with: brew install gh" >&2; exit 1; }
command -v git >/dev/null || { echo "ERROR: git not installed." >&2; exit 1; }

# Verify we're at the plugin root (look for the manifest)
if [[ ! -f .claude-plugin/plugin.json ]]; then
  echo "ERROR: Run this from the plugin root (where .claude-plugin/plugin.json lives)." >&2
  exit 1
fi

# Verify gh is authenticated
if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh CLI not authenticated. Run: gh auth login" >&2
  exit 1
fi

# Verify there are tracked changes to publish
if git diff --quiet && git diff --cached --quiet; then
  echo "ERROR: No changes to publish. Make some edits first." >&2
  exit 1
fi

# ---------- derive branch name from title ----------

# Pull off the conventional-commit type (docs:, feat:, fix:, chore:, refactor:)
# Anything else falls back to "change".
type=$(echo "$title" | grep -oE '^[a-z]+(\([a-z0-9-]+\))?:' | sed 's/[(:].*//' | head -1)
[[ -z "$type" ]] && type="change"

# Slug the rest: lowercase, non-alphanumeric → hyphens, collapse runs, trim
slug=$(echo "$title" \
  | sed -E 's/^[a-z]+(\([a-z0-9-]+\))?:[[:space:]]*//' \
  | tr '[:upper:]' '[:lower:]' \
  | tr -c 'a-z0-9' '-' \
  | sed -E 's/^-+//; s/-+$//; s/-+/-/g' \
  | cut -c1-50)

if [[ -z "$slug" ]]; then
  echo "ERROR: Could not derive a branch slug from title: '$title'" >&2
  exit 1
fi

branch="${type}/${slug}"

# ---------- show the plan before mutating anything ----------

current_branch=$(git rev-parse --abbrev-ref HEAD)
echo "Plan:"
echo "  Current branch: ${current_branch}"
echo "  New branch:     ${branch}"
echo "  Title:          ${title}"
[[ -n "$body" ]] && echo "  Body:           (provided, ${#body} chars)"
echo "  Changed files:"
git diff --name-only HEAD | sed 's/^/    /'
echo

# ---------- create branch + commit + push ----------

git checkout -b "$branch"

# Stage only tracked files (no -A — never auto-include untracked)
git add -u

if [[ -n "$body" ]]; then
  git commit -m "$title" -m "$body" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
else
  git commit -m "$title" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
fi

# If we were on main when running this, the commit also landed on local main.
# Roll it back so main stays in sync with origin/main and the work only lives
# on the new branch.
if [[ "$current_branch" == "main" ]]; then
  git branch -f main origin/main
  echo "  ↳ Local main rolled back to origin/main (commit kept on ${branch})"
fi

git push -u origin "$branch"

# ---------- open PR ----------

pr_body="${body:-$title}"
pr_url=$(gh pr create \
  --title "$title" \
  --body "${pr_body}

🤖 Generated with [Claude Code](https://claude.com/claude-code)" \
  | tail -1)

echo
echo "✓ PR opened: ${pr_url}"
echo
echo "Next: review and merge on GitHub. After merge, locally:"
echo "  git checkout main && git pull origin main && git branch -D ${branch}"
