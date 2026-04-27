# Brand/Style Presets Reference

> Load this on-demand when the user asks about presets or brand consistency.

## Preset Schema

Each preset is stored as `~/.creators-studio/presets/NAME.json`:

```json
{
  "name": "tech-saas",
  "description": "Clean tech SaaS brand",
  "colors": ["#2563EB", "#1E40AF", "#F8FAFC"],
  "style": "clean minimal tech illustration, flat vectors, soft shadows",
  "typography": "bold geometric sans-serif",
  "lighting": "bright diffused studio, no harsh shadows",
  "mood": "professional, trustworthy, modern",
  "default_ratio": "16:9",
  "default_resolution": "2K",

  "_comment": "--- Brand Style Guide fields below (all optional) ---",
  "background_styles": {
    "dark-premium": {"bg": "#000000", "text": "#FFFFFF", "accent": "#2563EB"},
    "light-clean": {"bg": "#F8FAFC", "text": "#1E40AF", "accent": "#2563EB"}
  },
  "visual_motifs": "subtle geometric grid pattern in light blue at 20% opacity",
  "logo_placement": "bottom-left, 12% of width",
  "do_list": ["Use generous white space", "Keep layouts clean and minimal", "Use brand blue for CTAs"],
  "dont_list": ["No gradients on backgrounds", "No more than 2 accent colors", "No decorative fonts"],
  "prompt_keywords": {
    "aesthetic": ["clean", "minimal", "modern", "professional"],
    "mood": ["trustworthy", "innovative", "approachable"],
    "photography": ["bright", "high-key lighting", "sharp focus"]
  },
  "prompt_suffix": "Clean minimal tech aesthetic, bright diffused lighting, professional and trustworthy mood.",
  "technical_specs": {"color_space": "sRGB", "min_dpi": 150}
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique preset identifier |
| `description` | string | No | Brief description |
| `colors` | string[] | No | Hex color palette |
| `style` | string | No | Visual style description |
| `typography` | string | No | Typography description |
| `lighting` | string | No | Lighting description |
| `mood` | string | No | Mood/emotion description |
| `default_ratio` | string | No | Default aspect ratio |
| `default_resolution` | string | No | Default resolution |
| `background_styles` | object | No | Named background variants (each with bg/text/accent) |
| `visual_motifs` | string | No | Pattern/overlay description with opacity |
| `logo_placement` | string | No | Where the logo goes in post-production (NOT mentioned in prompts -- see logo exclusion rule) |
| `do_list` | string[] | No | Brand guidelines to follow |
| `dont_list` | string[] | No | Brand guidelines to avoid |
| `prompt_keywords` | object | No | Categorized keywords to weave into prompts |
| `prompt_suffix` | string | No | Appended verbatim to every prompt |
| `technical_specs` | object | No | Technical defaults (color_space, min_dpi, etc.) |

All Brand Style Guide fields (below the `_comment` line) are **optional**. Presets without them continue to work as before.

## Example Presets

### tech-saas
- **Colors:** #2563EB, #1E40AF, #F8FAFC (blue + white)
- **Style:** Clean minimal tech illustration, flat vectors, soft shadows
- **Typography:** Bold geometric sans-serif
- **Mood:** Professional, trustworthy, modern

### luxury-brand
- **Colors:** #1A1A1A, #C9A96E, #FAFAF5 (black + gold + cream)
- **Style:** Elegant high-end photography, rich textures, deep contrast
- **Typography:** Thin elegant serif, generous letter-spacing
- **Mood:** Exclusive, sophisticated, aspirational

### editorial-magazine
- **Colors:** #000000, #FFFFFF, #FF3B30 (black + white + accent red)
- **Style:** Bold editorial photography, strong geometric composition
- **Typography:** Condensed all-caps sans-serif headlines
- **Mood:** Bold, provocative, contemporary

### premium-brand (Brand Style Guide)
- **Colors:** #000000, #FFC000, #FFFFFF, #C0C0C0 (black + gold + white + silver)
- **Style:** Premium dark photography, dramatic lighting, gold accents, editorial quality
- **Typography:** Bold geometric sans-serif headlines, light weight body text
- **Mood:** Confident, innovative, premium, forward-thinking
- **Background styles:**
  - `dark-premium`: pure black BG, white text, gold accent
  - `gold-gradient`: gradient from #FFC000 to dark amber, black text
- **Visual motifs:** Geometric network pattern in silver at 30-50% opacity
- **Logo placement:** Bottom-left, 15% of width *(added in post-production, NOT mentioned in prompts)*
- **Prompt suffix:** "Premium dark aesthetic with gold accents, dramatic lighting, confident and innovative mood."
- **Do:** Use generous negative space, maintain high contrast, keep patterns subtle
- **Don't:** Use busy backgrounds behind text, mix more than 2 accent colors, use white backgrounds

## How Presets Merge into Reasoning Brief

When a preset is active, Claude uses its values as defaults for the Reasoning Brief:
1. **Colors** → inform palette descriptions in Context and Style components
2. **Style** → becomes the base for the Style component
3. **Typography** → used for any text rendering
4. **Lighting** → becomes the base for the Lighting component
5. **Mood** → influences Action and Context components

User instructions always override preset values. If a user says "make it dark"
but the preset has bright lighting, follow the user's instruction.

**Brand Style Guide additions** (when present):

6. **background_styles** → if Presentation mode, select the matching background variant; apply its bg/text/accent colors
7. **visual_motifs** → append motif description to the Style component at specified opacity
8. **logo_placement** → records where logo goes in post-production. Do NOT mention "logo" in the prompt -- instead describe that area as "clean negative space" or "uncluttered background"
9. **do_list / dont_list** → Claude checks the final prompt against these rules before sending
10. **prompt_keywords** → weave relevant keywords from matching categories into the prompt naturally
11. **prompt_suffix** → appended verbatim to the end of the constructed prompt
12. **technical_specs** → override default_ratio and default_resolution if present; apply color_space

## Managing Presets

```bash
# List presets
presets.py list

# Show details
presets.py show tech-saas

# Create interactively (Claude fills in details from conversation)
presets.py create NAME --colors "#hex,#hex" --style "..." --mood "..."

# Delete
presets.py delete NAME --confirm
```
