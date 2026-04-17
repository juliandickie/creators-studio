# Setup, Install & Update Reference

> Load this when the user runs `/create-image setup`, `/create-image status`, `/create-image update`,
> or asks how to install/share creators-studio.
>
> Guide conversationally. Do NOT run `setup_mcp.py` without arguments (the
> interactive `input()` prompt does not work in Claude Code's shell).

## `/create-image setup` -- Google AI API Key (Primary)

Walk the user through this:

1. **Explain what they need:**
   "To generate images, you need a free Google AI API key. This lets Claude
   call Google's Gemini image generation models. No credit card required."

2. **Direct them to get the key:**
   "Go to https://aistudio.google.com/apikey and:
   - Sign in with your Google account
   - Click 'Create API Key'
   - Select any Google Cloud project (or create one -- it's free)
   - Copy the key (starts with `AIza...`)"

3. **Ask them to paste it:**
   "Paste your API key here and I'll configure everything."

4. **When they provide the key, run:**
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/setup_mcp.py --key THE_KEY_THEY_GAVE
   ```

5. **Tell them to restart Claude Code** for the MCP server to load.

6. **Free tier info:** ~5-15 images/minute, ~20-500/day. Resets midnight Pacific.

## `/create-image setup replicate` -- Replicate API (Optional Fallback)

1. **Explain the option:**
   "Replicate is an optional backup. If the primary Google API is unavailable,
   Banana Claude will automatically fall back to Replicate. It costs ~$0.05/image."

2. **Direct them to get the token:**
   "Go to https://replicate.com/account/api-tokens and:
   - Sign in (GitHub login works)
   - Click 'Create token'
   - Copy the token (starts with `r8_...`)"

3. **When they provide the token, run:**
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/setup_mcp.py --replicate-key THE_TOKEN
   ```

## `/create-image status` -- Check Installation & Keys

```bash
# Show version
grep 'version:' ${CLAUDE_SKILL_DIR}/SKILL.md | head -1

# Show git status (if in a git repo)
cd ${CLAUDE_SKILL_DIR}/../.. && git log --oneline -3 2>/dev/null

# Check API keys
python3 ${CLAUDE_SKILL_DIR}/scripts/setup_mcp.py --check
python3 ${CLAUDE_SKILL_DIR}/scripts/setup_mcp.py --check-replicate
```

## `/create-image update` -- Pull Latest Version

```bash
cd ${CLAUDE_SKILL_DIR}/../.. && git pull origin main
```
Then tell the user to run `/reload-plugins` in Claude Code.

## Where Keys Are Stored

Both keys are saved to `~/.banana/config.json` (for fallback scripts) and the
Google key is also saved to `~/.claude/settings.json` (for the MCP server).
Keys never leave the user's machine.

## New User Guide

For first-time users, provide this quick start:

> **What is Creators Studio?**
> An AI image generation skill for Claude Code. You describe what you want,
> and Claude acts as Creative Director -- interpreting intent, selecting style,
> and generating images using Google's Gemini models.
>
> **Install in 3 steps:**
> ```bash
> git clone https://github.com/juliandickie/creators-studio.git ~/creators-studio
> claude --plugin-dir ~/creators-studio
> # Then in Claude Code: /create-image setup
> ```
>
> **First image:** `/create-image generate "a cozy coffee shop at golden hour"`

## Optional Tools (v4.1.0+)

Creators Studio works out-of-the-box for most image/video generation with just a Google AI API key. These optional command-line tools unlock specific features. Run `/create-image status` to see which are installed on the user's machine and what each enables.

| Tool | macOS install | Unlocks |
|---|---|---|
| **ImageMagick** | `brew install imagemagick` | `/create-image social` exact-dimension crop (without it, social outputs may not match platform upload pixel specs); green-screen transparency; most post-processing recipes in `references/post-processing.md` |
| **ffmpeg** | `brew install ffmpeg` | `/create-video audio pipeline`, `/create-video stitch`, `/create-video lipsync` (audio handoff), video concat/trim/convert |
| **cwebp (libwebp)** | `brew install webp` | Efficient WebP encoding path for `/create-image formats` when ImageMagick isn't present |
| **imagemagick-full** (optional) | `brew install imagemagick-full` | *Keg-only.* Adds Liquid Rescale (content-aware resize), librsvg (high-quality SVG rendering), Ghostscript (PDF rendering), libraw (camera raws). Not currently used by any shipped feature — install only when a future release requires it. |

### When to prompt the user for install

When a user invokes a command that needs an optional tool that isn't installed — e.g. `/create-image social` with platforms that require aggressive ratio shifts (TikTok 9:16, LinkedIn 4:1), and `which magick` returns empty — present the 3-option choice pattern documented in SKILL.md §Step 9.5:

1. Install now — one-liner
2. Proceed with degraded output
3. Cancel

Do NOT silently degrade. Always communicate what the user is giving up by not installing.

### API credentials (activate specific model providers)

The `~/.banana/config.json` file holds all API credentials. Missing credentials degrade specific model paths, not the whole plugin:

| Credential | Activates |
|---|---|
| `google_ai_api_key` | **Required** — core Gemini image generation |
| `replicate_api_token` | Kling v3 video, Fabric lipsync, Recraft vectorize, Gemini-via-Replicate fallback |
| `elevenlabs_api_key` | `/create-video audio` pipeline, TTS narration, voice design/cloning |
| `vertex_api_key` + `vertex_project_id` + `vertex_location` | VEO 3.1 video backup, Lyria 2 music |

Same UX rule: if a user invokes a feature whose credential isn't configured, prompt them with install/configure steps rather than silently failing.

## Sharing with Friends

Copy-paste this message:

> **Want AI image generation in Claude Code?**
>
> 1. Get a free API key: https://aistudio.google.com/apikey
> 2. Run:
> ```bash
> git clone https://github.com/juliandickie/creators-studio.git ~/creators-studio
> claude --plugin-dir ~/creators-studio
> ```
> 3. In Claude Code: `/create-image setup` (paste your API key)
> 4. Try it: `/create-image generate "a sunset over mountains"`
>
> To update: `cd ~/creators-studio && git pull` then `/reload-plugins`
