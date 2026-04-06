---
name: banana-install
description: "Install, update, or check the status of Banana Claude image generation skill. Use this when asked to install banana, update banana, check banana version, or set up banana-claude."
argument-hint: "[install|update|status|setup]"
metadata:
  version: "1.0.0"
  author: juliandickie
  source: "https://github.com/juliandickie/banana-claude"
---

# Banana Claude -- Installer & Updater

## Commands

| Command | What it does |
|---------|-------------|
| `/banana-install install` | Clone and install banana-claude from GitHub |
| `/banana-install update` | Pull latest changes and reload |
| `/banana-install status` | Check current version and installation |
| `/banana-install setup` | Configure API keys (Google AI + optional Replicate) |

## Install

Clone the repo and register as a local plugin:

```bash
# Clone if not already present
if [ ! -d "$HOME/code/banana-claude" ]; then
    git clone https://github.com/juliandickie/banana-claude.git "$HOME/code/banana-claude"
    echo "Cloned banana-claude to ~/code/banana-claude"
else
    echo "banana-claude already exists at ~/code/banana-claude"
fi
```

After cloning, tell the user to restart Claude Code with:
```
claude --plugin-dir ~/code/banana-claude
```

Or for standalone installation (copies files to `~/.claude/skills/banana/`):
```bash
bash ~/code/banana-claude/install.sh
```

## Update

Pull the latest changes from the fork:

```bash
cd "$HOME/code/banana-claude" && git pull origin main
```

Then tell the user to run `/reload-plugins` in Claude Code to pick up changes.

If the user also wants upstream changes from the original repo:
```bash
cd "$HOME/code/banana-claude" && git fetch upstream && git log --oneline upstream/main..main
```
Show them what's different and ask if they want to merge: `git merge upstream/main`

## Status

Check the current installation:

```bash
# Check if repo exists
ls -la "$HOME/code/banana-claude/skills/banana/SKILL.md" 2>/dev/null && echo "Installed" || echo "Not installed"

# Show version
grep 'version:' "$HOME/code/banana-claude/skills/banana/SKILL.md" 2>/dev/null | head -1

# Show git status
cd "$HOME/code/banana-claude" 2>/dev/null && git log --oneline -3 && echo "---" && git remote -v

# Check API keys
python3 "$HOME/code/banana-claude/skills/banana/scripts/setup_mcp.py" --check 2>/dev/null
python3 "$HOME/code/banana-claude/skills/banana/scripts/setup_mcp.py" --check-replicate 2>/dev/null
```

## Setup

Configure API keys. Run interactively:

```bash
# Google AI API key (required) -- get free at https://aistudio.google.com/apikey
python3 "$HOME/code/banana-claude/skills/banana/scripts/setup_mcp.py"

# Replicate API token (optional fallback) -- get at https://replicate.com/account/api-tokens
python3 "$HOME/code/banana-claude/skills/banana/scripts/setup_mcp.py" --replicate-key YOUR_TOKEN
```

Both keys are stored in `~/.banana/config.json` for fallback scripts and in
`~/.claude/settings.json` for the MCP server (Google key only).

## Sharing with Friends

To share banana-claude with someone:

1. They need Claude Code installed
2. Give them this one-liner:
```bash
git clone https://github.com/juliandickie/banana-claude.git ~/code/banana-claude && claude --plugin-dir ~/code/banana-claude
```
3. Then they run `/banana setup` to add their own API key
4. To update later: `cd ~/code/banana-claude && git pull` then `/reload-plugins`

## Source

This skill is a fork of [AgriciDaniel/banana-claude](https://github.com/AgriciDaniel/banana-claude)
with Replicate backend, Presentation mode, Brand Style Guides, and research-driven prompt improvements.

Repository: https://github.com/juliandickie/banana-claude
