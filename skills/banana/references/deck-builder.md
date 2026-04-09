# Deck Builder Reference

> Load this when the user runs `/banana deck` or asks to assemble
> generated slide images into a .pptx presentation.

## Overview

Assemble generated slide images into an editable .pptx file with text layers, brand styling, and optional logo placement. Works best with images from `/banana slides generate` but accepts any directory of images.

## Usage

```bash
# Build a deck from generated slide images
python3 ${CLAUDE_SKILL_DIR}/scripts/deckbuilder.py build --images ~/slides/ --output deck.pptx --preset luxury-dark --layout fullbleed

# See available layouts
python3 ${CLAUDE_SKILL_DIR}/scripts/deckbuilder.py layouts

# Estimate slide count before building
python3 ${CLAUDE_SKILL_DIR}/scripts/deckbuilder.py estimate --images ~/slides/
```

## Typical Workflow

1. Generate slide images: `/banana slides generate --prompts prompts.md --output ~/slides/`
2. Build the deck: `/banana deck --images ~/slides/ --preset my-brand --output presentation.pptx`
3. Open in Keynote/PowerPoint/Google Slides for final editing

## Layouts

| Layout | Description |
|--------|-------------|
| **fullbleed** | Image fills entire slide. Text overlaid with semi-transparent dark backdrop at bottom. Best for dramatic visual impact. |
| **standard** | Image occupies top 60%, text area bottom 40% with brand background color. Best for content-heavy slides. |
| **split** | 50/50 split — image on left, text content on right. Best for balanced information + visual slides. |

## Slide Structure

Every deck includes:
1. **Title slide** — Brand background color + title + optional subtitle
2. **Content slides** — One per image, arranged per layout mode
3. **Closing slide** — Brand background + "Thank You" or brand tagline

## Brand Preset Integration

If a preset is provided (`--preset NAME`), the deck inherits:
- `colors[0]` → slide background (for standard/split layouts)
- `colors[1]` → accent/heading color
- `typography` → maps to available fonts (bold → Arial Black, serif → Georgia, etc.)
- `logo_placement` → where the logo image is positioned
- `mood` → closing slide text

## Logo Handling

Logos are composited in the .pptx (not in the generated images):
```bash
/banana deck --images ~/slides/ --logo ~/brand/logo.png --preset my-brand --output deck.pptx
```

Default position: top-right corner, 5% of slide height. Override via preset's `logo_placement` field.

## Slide Notes

If `generation-summary.json` exists in the images directory (created by `slides.py`), each content slide gets notes with the original prompt used to generate the image. Useful for reproducing or refining specific slides later.

## Prerequisites

Requires python-pptx:
```bash
pip install python-pptx
```

This is the same dependency used by `brandbook.py`.
