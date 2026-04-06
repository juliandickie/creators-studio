---
name: banana-install
description: "Install, update, or check the status of Banana Claude image generation skill. Use this when asked to install banana, update banana, check banana version, or set up banana-claude."
argument-hint: "[install|update|status|setup|help]"
metadata:
  version: "1.1.0"
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
| `/banana-install setup` | Walk through API key configuration |
| `/banana-install help` | Show setup guide for new users |

## Install

Check common locations first, then clone if needed:

```bash
# Check if already installed somewhere
for dir in "$HOME/banana-claude" "$HOME/code/banana-claude" "$HOME/projects/banana-claude"; do
    if [ -d "$dir/skills/banana/SKILL.md" ] 2>/dev/null || [ -d "$dir/skills/banana" ] 2>/dev/null; then
        echo "Found existing installation at: $dir"
        break
    fi
done
```

If not found, clone:

```bash
git clone https://github.com/juliandickie/banana-claude.git "$HOME/banana-claude"
echo "Installed to ~/banana-claude"
```

After cloning, tell the user:

> **Next step:** Restart Claude Code with the plugin loaded:
> ```
> claude --plugin-dir ~/banana-claude
> ```
> Then run `/banana setup` to configure your API key.

## Update

```bash
# Find the installation
for dir in "$HOME/banana-claude" "$HOME/code/banana-claude" "$HOME/projects/banana-claude"; do
    if [ -d "$dir/.git" ]; then
        echo "Found at: $dir"
        cd "$dir" && git pull origin main
        echo "Updated! Run /reload-plugins in Claude Code."
        break
    fi
done
```

## Status

```bash
# Find and check installation
found=false
for dir in "$HOME/banana-claude" "$HOME/code/banana-claude" "$HOME/projects/banana-claude"; do
    if [ -f "$dir/skills/banana/SKILL.md" ]; then
        echo "Installation: $dir"
        grep 'version:' "$dir/skills/banana/SKILL.md" | head -1
        cd "$dir" && git log --oneline -3
        found=true
        break
    fi
done
if [ "$found" = false ]; then
    echo "Banana Claude not found. Run /banana-install install"
fi

# Check API keys
echo ""
echo "API Keys:"
python3 -c "
import json
from pathlib import Path
config_path = Path.home() / '.banana' / 'config.json'
if config_path.exists():
    config = json.load(open(config_path))
    gk = config.get('google_ai_api_key', '')
    rk = config.get('replicate_api_token', '')
    print(f'  Google AI: {gk[:10]}...{gk[-4:]}' if len(gk) > 14 else '  Google AI: NOT SET')
    print(f'  Replicate: {rk[:8]}...{rk[-4:]}' if len(rk) > 12 else '  Replicate: NOT SET')
else:
    print('  No config found at ~/.banana/config.json')
    print('  Run /banana setup to configure')
" 2>/dev/null || echo "  Could not check config"
```

## Setup

Walk the user through API key configuration step by step.

### Google AI API Key (Required)

Tell the user:

> **To get your free Google AI API key:**
>
> 1. Go to https://aistudio.google.com/apikey
> 2. Sign in with your Google account
> 3. Click **"Create API Key"**
> 4. Select any Google Cloud project (or create one -- it's free, no credit card needed)
> 5. Copy the key that appears (starts with `AIza...`)
>
> **Free tier limits:** ~5-15 images per minute, ~20-500 per day. Resets midnight Pacific.
>
> Once you have the key, paste it when I run the setup script.

Then run:
```bash
python3 "$BANANA_DIR/skills/banana/scripts/setup_mcp.py"
```

Where `$BANANA_DIR` is the installation directory found during status check.

If the user provides the key directly, use:
```bash
python3 "$BANANA_DIR/skills/banana/scripts/setup_mcp.py" --key THE_KEY
```

### Replicate API Token (Optional)

Tell the user:

> **To get a Replicate API token (optional -- adds a fallback backend):**
>
> 1. Go to https://replicate.com/account/api-tokens
> 2. Sign in (GitHub login works)
> 3. Click **"Create token"**
> 4. Copy the token (starts with `r8_...`)
>
> Replicate charges per-second of compute (~$0.05/image). No free tier.

Then run:
```bash
python3 "$BANANA_DIR/skills/banana/scripts/setup_mcp.py" --replicate-key THE_TOKEN
```

### Where Keys Are Stored

Both keys are saved to `~/.banana/config.json`:
```json
{
  "google_ai_api_key": "AIza...",
  "replicate_api_token": "r8_..."
}
```

The Google key is also saved to `~/.claude/settings.json` for the MCP server.

Keys never leave your machine. They are not sent to GitHub or any third party.

### Verify Setup

```bash
python3 "$BANANA_DIR/skills/banana/scripts/setup_mcp.py" --check
python3 "$BANANA_DIR/skills/banana/scripts/setup_mcp.py" --check-replicate
```

## Help (New User Guide)

For new users, provide this complete guide:

> ### Quick Start Guide
>
> **What is Banana Claude?**
> It's an AI image generation skill for Claude Code. You describe what you want,
> and Claude acts as a Creative Director -- interpreting your intent, selecting
> the right style, and generating images using Google's Gemini models.
>
> **What you need:**
> - Claude Code (the CLI tool from Anthropic)
> - A Google AI API key (free, takes 2 minutes)
> - Git and Node.js 18+
>
> **Install in 3 steps:**
> ```bash
> # 1. Clone
> git clone https://github.com/juliandickie/banana-claude.git ~/banana-claude
>
> # 2. Start Claude Code with the plugin
> claude --plugin-dir ~/banana-claude
>
> # 3. Set up your API key (inside Claude Code)
> /banana setup
> ```
>
> **Your first image:**
> ```
> /banana generate "a cozy coffee shop interior at golden hour"
> ```
>
> **Useful commands:**
> - `/banana generate "idea"` -- Generate an image
> - `/banana edit ~/photo.png "instruction"` -- Edit an existing image
> - `/banana chat` -- Multi-turn creative session
> - `/banana preset create my-brand --colors "#000,#FFC000" --style "premium dark"` -- Create a brand style
> - `/banana cost summary` -- Check usage and costs

## Sharing with Friends

Give them this message:

> **Want AI image generation in Claude Code?**
>
> 1. Get a free API key: https://aistudio.google.com/apikey
> 2. Run these commands:
> ```bash
> git clone https://github.com/juliandickie/banana-claude.git ~/banana-claude
> claude --plugin-dir ~/banana-claude
> ```
> 3. In Claude Code: `/banana setup` (paste your API key)
> 4. Try it: `/banana generate "a sunset over mountains"`
>
> To update: `cd ~/banana-claude && git pull`, then `/reload-plugins` in Claude Code.

## Source

Fork of [AgriciDaniel/banana-claude](https://github.com/AgriciDaniel/banana-claude)
with Replicate backend, Presentation mode, Brand Style Guides, and research-driven improvements.

Repository: https://github.com/juliandickie/banana-claude
