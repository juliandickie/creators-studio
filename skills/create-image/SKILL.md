---
name: create-image
description: "Use when ANY request involves image creation, editing, visual asset production, slide generation, or creative direction. Triggers on: generate an image, create a photo, edit this picture, design a logo, make a banner, slide deck, social media visuals, and all /create-image commands."
argument-hint: "[generate|edit|chat|slides|social|brand|asset|reverse|book|batch|inspire|preset|cost|setup|status|update] <idea, path, or command>"
---

# Creators Studio -- Creative Director for AI Image Generation

<!-- MCP package: @ycse/nanobanana-mcp | Version managed in plugin.json -->
<!-- For video generation, see the /create-video skill (skills/create-video/SKILL.md) -->
<!-- Conflict note: This skill uses /create-image command. If original creators-studio plugin
     is also installed, Claude will see duplicate skills. Users must uninstall one. -->

## Core Principles

1. **Creative Director** -- NEVER pass raw user text to the API. Always interpret, enhance, and construct an optimized prompt.
2. **Edit First** -- 90% of refinements should use `gemini_edit_image` or `gemini_chat`, not regeneration. Only regenerate when composition or concept is fundamentally wrong.
3. **Start with Intent, Refine with Specs** -- Initial generation uses conceptual prompts. Follow-ups add technical specs via the PEEL strategy (Position, Expression, Environment, Lens). See `references/prompt-engineering.md` → Start with Intent.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/create-image` | Interactive -- detect intent, craft prompt, generate |
| `/create-image generate <idea>` | Full Creative Director pipeline |
| `/create-image edit <path> <instructions>` | Intelligent image editing |
| `/create-image chat` | Multi-turn visual session (character/style consistent) |
| `/create-image slides [plan\|prompts\|generate]` | Slide deck pipeline |
| `/create-image inspire [category]` | Browse prompt database for ideas |
| `/create-image batch <idea> [N]` | Generate N variations (default: 3) |
| `/create-image social <idea> --platforms <list>` | Platform-native image generation (46 platforms, 4K, auto-crop) |
| `/create-image brand` | Conversational brand guide builder (learn → refine → preview → save) |
| `/create-image asset [list\|show\|create\|delete]` | Manage persistent character/product/object references |
| `/create-image reverse <image-path>` | Analyze image → extract 5-Component Formula prompt to recreate it |
| `/create-image book --preset <name> [--tier quick\|standard\|comprehensive]` | Generate visual brand book (markdown + pptx + html) |
| `/create-image setup` | Guided Google AI API key setup |
| `/create-image setup replicate` | Guided Replicate token setup (optional fallback) |
| `/create-image status` | Check version, installation, and API key status |
| `/create-image update` | Pull latest version from GitHub |
| `/create-image preset [list\|create\|show\|delete]` | Manage brand/style presets |
| `/create-image cost [summary\|today\|estimate]` | View cost tracking and estimates |
| `/create-image formats <path> [--formats] [--sizes]` | Convert image to multiple formats/sizes |
| `/create-image history [list\|show\|export\|sessions]` | View session generation history and export gallery |
| `/create-image ab-test <idea> [--count N]` | Generate Literal/Creative/Premium variations and track preferences |
| `/create-image deck --images DIR --output PATH` | Assemble slide images into editable .pptx with brand styling |
| `/create-image analytics [--format html\|json] [--days 30]` | Usage analytics dashboard (cost trends, domain usage, quota) |
| `/create-image content <idea> --outputs hero,social,email` | Multi-modal content pipeline from a single idea |
| `/create-image vectorize <image>` | **v4.1.0** Convert raster image (PNG/JPG/WEBP) to scalable SVG via Recraft Vectorize ($0.01/call) |

## Creative Director Pipeline

Follow this for every generation -- no exceptions:

### Step 1: Analyze Intent

Gather the 5-Input Creative Brief: **Purpose** (where used?), **Audience** (who for?), **Subject** (what?), **Brand** (what vibe?), **References** (visual examples?). If vague, ASK. See `references/prompt-engineering.md` → 5-Input System.

### Step 2: Check for Presets

If user mentions a brand/preset: `python3 ${CLAUDE_SKILL_DIR}/scripts/presets.py list`. Load with `show NAME`. Preset values are defaults -- user instructions override. See `references/presets.md` for Brand Style Guide fields.

**Logo handling:** NEVER mention "logo" in prompts. Describe the area as "clean negative space." Logos are composited in presentation software after generation.

**Example presets:** If no presets exist, offer to install examples: `ls ${CLAUDE_SKILL_DIR}/presets/` shows 12 pre-built brand guides. Copy with: `cp ${CLAUDE_SKILL_DIR}/presets/NAME.json ~/.banana/presets/`

### Step 3: Check for Assets

If user mentions a named character, product, or object, check assets:
`python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py list`. Load with `show NAME`.
Pass `reference_images[]` as inlineData parts in the API call. Append
`consistency_notes` to the prompt. See `references/asset-registry.md`.

### Step 4: Select Domain Mode

Choose from: **Cinema**, **Product**, **Portrait**, **Editorial**, **UI/Web**, **Logo**, **Landscape**, **Abstract**, **Infographic**, **Presentation (Complete)**, **Presentation (Background)**. See `references/prompt-engineering.md` → Domain Mode Modifier Libraries.

### Step 5: Construct Prompt

Use the **5-Component Formula**: Subject → Action → Location/Context → Composition → Style (includes lighting). Write as natural narrative prose, NEVER keyword lists. See `references/prompt-engineering.md` → Proven Prompt Templates.

**Critical rules:** Use prestigious context anchors ("Vanity Fair editorial," "National Geographic cover"). NEVER use banned keywords ("8K," "masterpiece," "ultra-realistic"). For constraints use ALL CAPS. For products say "prominently displayed."

For batch/exploratory requests, offer **Literal/Creative/Premium** prompt variations.

### Step 6: Set Aspect Ratio + Resolution

Call `set_aspect_ratio` BEFORE generating. Match ratio to use case. Default: `2K`. Presentation: `16:9`, `4K`. See `references/gemini-models.md` → Aspect Ratios + Resolution Tiers.

### Step 7: Call the MCP

| Tool | When |
|------|------|
| `set_aspect_ratio` | Always call first if ratio differs from 1:1 |
| `gemini_generate_image` | New image from prompt |
| `gemini_edit_image` | Modify existing image |
| `gemini_chat` | Multi-turn / iterative refinement |

**Fallback chain (if MCP unavailable):**
1. Direct Gemini API: `python3 ${CLAUDE_SKILL_DIR}/scripts/generate.py --prompt "..."`
2. Replicate API: `python3 ${CLAUDE_SKILL_DIR}/scripts/replicate_generate.py --prompt "..."`
For editing: use `edit.py` or `replicate_edit.py` respectively.

### Step 8: Post-Processing

If needed, use ImageMagick for cropping, format conversion, background removal. See `references/post-processing.md`. Check tool availability first: `which magick || which convert`.

### Step 9: Handle Errors

| Error | Action |
|-------|--------|
| `IMAGE_SAFETY` | Rephrase prompt (see `references/prompt-engineering.md` → Safety Rephrase). Max 3 attempts with user approval. |
| HTTP 429 | Wait 2s, exponential backoff, max 3 retries |
| HTTP 400 FAILED_PRECONDITION | Billing not enabled -- inform user |
| HTTP 5xx | Server error -- wait 5s, retry with backoff, max 3 retries. Common during model rollouts. |
| Invalid API key | Inform user, suggest running `/create-image setup` to reconfigure |
| MCP unavailable | Use fallback chain (Step 7) |
| Vague request | Ask clarifying questions |

### Step 9.5: Handle missing-tool warnings (v4.1.0+)

Scripts may return results with `method: "copy_fallback"` or a top-level `warning` field pointing at a missing optional tool (ImageMagick, ffmpeg, cwebp, etc.). These are NOT hard errors — the API call succeeded — but they signal feature degradation.

**Before running a command that will degrade, OR after seeing a `copy_fallback` result, present the user with a 3-option choice:**

> *"This feature works best with `<tool>` installed. Without it, \<describe the degradation, e.g. "output keeps the generated dimensions instead of the platform's exact pixel spec">. You have three options:*
>
> *1. Install it now (~2 min): `brew install <tool>`*
> *2. Proceed anyway with reduced quality*
> *3. Cancel and revisit later*
>
> *Which would you prefer?"*

**When to check proactively** (before the call): `/create-image social` with platforms that have aggressive ratio shifts (9:16, 21:9, 4:1, etc.) — without ImageMagick, the dimensions won't be exact. Shell out to `which magick` first; if missing, prompt before generating.

**When to check reactively** (after the call): when a script's JSON result includes `method: "copy_fallback"` or `warning` is non-null. Surface the warning verbatim and then present the choice.

Never silently accept a `copy_fallback` result — always communicate what happened. See `scripts/validate_setup.py` for the canonical list of optional tools and what each unlocks.

### Step 10: Log Cost + History

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/cost_tracker.py log --model MODEL --resolution RES --prompt "brief"
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py log --prompt "full prompt" --image-path PATH --model MODEL --ratio RATIO --resolution RES --session-id SESSION_ID
```

### Step 11: Return Results

Always provide: **image path**, **crafted prompt** (educational), **settings** (model, ratio), **suggestions** (1-2 refinements).

Quality check (internal): resolution correct, no artifacts, all elements present, text legible, mood matches brief, brand guidelines satisfied.

## Editing Workflows

For `/create-image edit`, enhance the instruction -- don't pass raw text. "Remove background" becomes "Remove the existing background entirely, replacing with clean transparent or solid white. Preserve all edge detail and fine features like hair strands." See `references/prompt-engineering.md` for edit transformation patterns.

## Multi-turn Chat (`/create-image chat`)

1. Generate initial concept with full prompt
2. Refine with specific, targeted changes (not full re-descriptions)
3. Session maintains character/style consistency across turns
4. Use Progressive Enhancement: Composition → Lighting → Details → Polish

## Slide Deck Pipeline (`/create-image slides`)

Three-step pipeline for generating slide images from content:

**Step 1 -- Plan** (`/create-image slides plan`): Read content, divide into slides, write detailed design brief (markdown) with timestamps, transcript references, background styles, visual concepts.

**Step 2 -- Prompts** (`/create-image slides prompts`): Convert plan to Creators Studio prompts using Presentation mode + brand preset.

**Step 3 -- Generate** (`/create-image slides generate`):
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/slides.py generate --prompts slide-prompts.md --output ~/slides/
python3 ${CLAUDE_SKILL_DIR}/scripts/slides.py estimate --prompts slide-prompts.md
```
Default: 16:9, 4K. Use `--mode background` or `--mode complete`.

## Model Routing

| Scenario | Model | Resolution |
|----------|-------|-----------|
| Quick draft | `gemini-2.5-flash-image` | 512/1K |
| Standard | `gemini-3.1-flash-image-preview` | 2K |
| Quality/Print | `gemini-3.1-flash-image-preview` | 4K |
| Text-heavy | `gemini-3.1-flash-image-preview` | 2K, thinking: high |

Default: `gemini-3.1-flash-image-preview`. See `references/gemini-models.md` for full specs.

## /create-image reverse

Analyze an image and extract the prompt that would recreate it. See `references/reverse-prompt.md` for the full 5-Component decomposition methodology.

## /create-image social

Generate platform-native images at correct ratios for 46 platforms. See `references/social-platforms.md` for specs. Script: `python3 ${CLAUDE_SKILL_DIR}/scripts/social.py generate --prompt "..." --platforms ig-feed,yt-thumb`

## /create-image brand

Guided brand creation: gather sources → auto-extract → refine → preview → save. See `references/brand-builder.md`.

## /create-image inspire

Browse prompt ideas by category. Load `references/prompt-engineering.md` → Proven Prompt Templates section. Present 3-5 templates from the requested category (or random if none specified). Show the template prompt and suggest how to customize it.

## /create-image book

Generate a complete visual brand book from a preset in three formats. See `references/brand-book.md` for tier details and options.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/brandbook.py generate --preset NAME --output ~/brand-book/ --tier standard
```

## /create-image ab-test

Generate Literal/Creative/Premium prompt variations from the same brief, then rate to track preferences.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/abtester.py generate --idea "coffee shop hero" --count 3
```
After reviewing, prompt user to rate each variation (1-5). Log ratings with:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/abtester.py rate --test-id ID --ratings "1:4,2:5,3:3"
```
See `references/ab-testing.md` for variation styles and preferences tracking.

## /create-image deck

Assemble generated slide images into an editable .pptx with text layers and brand styling.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/deckbuilder.py build --images ~/slides/ --preset NAME --output deck.pptx
```
See `references/deck-builder.md` for layouts (fullbleed, standard, split) and preset integration.

## /create-image analytics

Generate a self-contained HTML analytics dashboard with cost trends, model/domain usage, and quota monitoring.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/analytics.py report --format html --output ~/analytics.html
```
See `references/analytics.md` for dashboard sections and data sources.

## /create-image content

One idea → complete content package: hero image, social pack, email header, format variants.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/content_pipeline.py plan --idea "product launch" --outputs hero,social,email,formats --preset NAME
python3 ${CLAUDE_SKILL_DIR}/scripts/content_pipeline.py generate --plan PATH
```
See `references/content-pipeline.md` for output types, dependencies, and cost estimation.

## /create-image formats

Convert any generated image to multiple formats and sizes. Generate once, convert many times.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/multiformat.py convert --input PATH --formats png,webp,jpeg --sizes 4k,2k,1k
```
See `references/multi-format.md` for size tables, format specs, and prerequisites.

## /create-image vectorize

**v4.1.0+.** Convert a raster image (PNG/JPG/WEBP) to a scalable SVG vector via Recraft Vectorize. Closes the gap where AI-generated logos distort when scaled up.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/vectorize.py --image ~/Documents/creators_generated/logo.png
```

**Best-practice prompts for vectorization** (apply these when user asks for a logo that will be vectorized):
- Isolated subject on **pure white** or **pure black** background
- Flat design, **minimal gradients**, limited color palette (1-5 distinct colors)
- Explicit "logo" or "icon" language in the prompt
- Request 1:1 aspect ratio for square logo bounds

Recraft accepts PNG/JPG/WEBP up to 5 MB, 256-4096 px per side, 16 MP max. Pricing is flat **$0.01 per output image**, regardless of input dimensions. Output SVG typically 50 KB to 1 MB, 128-500 vector paths.

See `references/vectorize.md` for the full workflow, prompt tuning, and troubleshooting.

## /create-image history

View and export session generation history. Each generation is automatically logged in Step 10.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py list
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py export --format md --output ~/gallery.md
```
See `references/session-history.md` for session ID management and export formats.

## Setup, Status & Update

See `references/setup.md` for guided flows. When user runs `/create-image setup`, `/create-image status`, or `/create-image update`, load that reference and follow its instructions.

## Reference Documentation

Load on-demand -- do NOT load all at startup:
- `references/prompt-engineering.md` -- 5-Component Formula, 11 domain modes, templates, PEEL strategy, character consistency, multilingual, brand guide integration
- `references/gemini-models.md` -- Model specs, resolution tables, input limits, rate limits, pricing
- `references/mcp-tools.md` -- MCP tool parameters, error taxonomy
- `references/replicate.md` -- Replicate backend API reference
- `references/post-processing.md` -- ImageMagick/FFmpeg pipelines, green screen
- `references/cost-tracking.md` -- Pricing table, usage guide
- `references/presets.md` -- Brand Style Guide schema (17 fields)
- `references/social-platforms.md` -- 46 social media platform specs, ratios, pixel targets, negative space
- `references/brand-builder.md` -- Guided brand creation flow (learn → refine → preview → save)
- `references/asset-registry.md` -- Persistent asset registry (characters, products, objects, environments)
- `references/reverse-prompt.md` -- Image analysis → 5-Component Formula prompt extraction
- `references/brand-book.md` -- Brand book generator (tiers, formats, color specs)
- `references/setup.md` -- Guided API key configuration flow
- `references/multi-format.md` -- Multi-format conversion (sizes, formats, ImageMagick)
- `references/session-history.md` -- Session history tracking, gallery export
- `references/ab-testing.md` -- A/B variation styles, rating system, preferences
- `references/deck-builder.md` -- Deck assembly, layouts, preset integration, logo handling
- `references/analytics.md` -- Analytics dashboard sections, data sources, chart types
- `references/content-pipeline.md` -- Content pipeline output types, dependencies, cost estimation
