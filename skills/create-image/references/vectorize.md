# Recraft Vectorize — Raster to SVG (v4.1.0+)

> Load this when the user wants to convert a generated raster image
> (PNG/JPG/WEBP) into a scalable SVG vector. The authoritative source for
> Recraft Vectorize capabilities is the model card at
> `dev-docs/recraft-ai-recraft-vectorize-llms.md`.

## Why `/create-image vectorize` exists

Gemini-generated logos and icons are raster images — they look crisp at the
generation resolution but distort as soon as they're scaled up for print,
banners, or larger-screen use. A proper brand logo is SVG: resolution-
independent, editable in Illustrator / Figma / Sketch, and compact enough
to ship inside email signatures and favicons.

Before v4.1.0, the plugin had no path from a raster logo to a scalable
vector version. Users had to round-trip through external tools or accept
that their brand assets wouldn't scale.

**Recraft Vectorize** (via Replicate) closes this gap. It's a specialized
AI model trained specifically for professional raster-to-SVG conversion —
different from classical tracing tools like `potrace` (monochrome-only) or
`autotrace` (older, less clean). Recraft handles multi-color inputs
natively, preserves design intent, and outputs clean editable paths.

## Model capabilities (Recraft Vectorize)

| Property | Value |
|---|---|
| Input formats | `PNG`, `JPG`, `JPEG`, `WEBP` (Recraft accepts WEBP where Kling doesn't) |
| Max file size | **5 MB** |
| Dimension range | 256–4096 px on each side |
| Max pixels | 16 MP total |
| Output format | SVG file (UTF-8 text, typically 50 KB to 1 MB) |
| Output compatibility | Adobe Illustrator, Figma, Sketch, Inkscape, any SVG-aware tool |
| Pricing | **$0.01 per output image** (flat, confirmed 2026-04-17) |
| Licensing | Commercial use permitted |
| Typical wall time | 8–20 seconds |

**Important**: Recraft is designed for **logos, icons, and clean flat
designs**. It will vectorize any raster input, but complex photographs or
highly detailed illustrations produce very large SVG files with many paths
and don't preserve photographic realism. For photographic-style outputs,
keep the raster PNG.

## Canonical workflow

```bash
# Step 1 — generate a logo with Gemini (use a Logo domain prompt)
/create-image generate "minimalist geometric logo for a tech startup
named NEXUS, single color navy blue, clean lines, negative space,
isolated on pure white background, trademark icon style"

# Output: ~/Documents/creators_generated/banana_20260417_203000.png

# Step 2 — vectorize the output
python3 ${CLAUDE_SKILL_DIR}/scripts/vectorize.py \
    --image ~/Documents/creators_generated/banana_20260417_203000.png

# Output: ~/Documents/creators_generated/banana_20260417_203000.svg
```

The plugin auto-resolves the output path to the same directory with the
`.svg` extension if `--output` isn't specified, keeping raster + vector
pair colocated.

## Best-practice prompts for vectorization

Gemini outputs that vectorize cleanly share these properties:

- **Isolated subject on pure white or pure black** — eliminates background
  noise paths
- **Flat design, minimal gradients** — Recraft handles gradients but clean
  flats produce cleaner SVGs
- **Limited color palette** — 1-5 distinct colors works best; full-color
  illustrations produce very complex SVGs
- **Explicit "logo" or "icon" language** in the prompt — biases Gemini
  toward simplified geometric forms
- **Request a square output** (1:1) — most logos live in square bounds,
  and Recraft's viewBox will inherit the source dimensions

**Example prompts that vectorize well:**

> "minimalist flat vector logo of a mountain peak, single color, clean
> geometric shapes, isolated on pure white background, brand identity style"

> "flat icon of a coffee cup with steam rising, two colors (brown + cream),
> rounded clean shapes, centered on white background, app icon style"

> "abstract hexagonal logo mark, single color gradient, geometric precision,
> negative space, on pure white, premium brand style"

**Prompts that produce suboptimal vectorization:**

- Photorealistic subjects (Recraft tries to vectorize every pixel gradient)
- Scenes with backgrounds (Recraft includes the background as paths)
- Heavy texture or noise (paths explode in count)

## Pre-flight validation

`vectorize.py` checks the input before submitting to Replicate:

- File exists and is readable
- Extension is in `{.png, .jpg, .jpeg, .webp}`
- File size ≤ 5 MB

Pixel-dimension validation (256-4096 range, 16 MP max) is done server-side
by Recraft — the client validator only warns if the caller has passed
dimensions explicitly. If you need to downscale a 4K generation before
vectorizing:

```bash
# Downscale 4K PNG to 2K before vectorize
magick large.png -resize 2048x large-2k.png

# Or WEBP-preserving
cwebp -q 85 -resize 2048 0 large.png -o large-2k.webp
```

## Cost model

Recraft bills per output image at $0.01, flat. No duration-based or
resolution-based tiers. The cost is the same whether the input is a 256×256
icon or a 4096×4096 poster.

Cost logging goes to `~/.creators-studio/costs.json` via `cost_tracker.py log` with
`--resolution N/A` (Recraft's `per_call` pricing mode ignores the resolution
argument).

## Integration with other commands

| Upstream | Action | Output | → vectorize input |
|---|---|---|---|
| `/create-image generate "...logo..."` | Generate raster logo | `logo.png` | ✓ |
| `/create-image edit logo.png "remove background"` | Clean up logo | `logo-clean.png` | ✓ |
| `/create-image asset create "brand-logo" --reference logo.svg` | Save vectorized logo as brand asset | *(SVG is stored)* | — |

Once vectorized, the SVG can be composited into presentations via
`deckbuilder.py`, included in brand books via `brandbook.py`, or delivered
directly to the user for use in Illustrator / Figma.

## Known limitations

- **Not a replacement for hand-drawn vector work.** Recraft is great at
  converting AI-generated raster logos into clean SVGs, but a human designer
  drawing from scratch in Illustrator will still produce tighter curves for
  high-stakes identity work.
- **No style control.** Recraft has a single model — you can't ask for
  "flatter" or "more curved" paths. If the output has too many paths,
  simplify the source raster first (edit out noise, increase contrast).
- **Doesn't preserve embedded text as text.** Text in the raster becomes
  vector paths, not `<text>` elements — which is actually the right behavior
  for brand assets (ensures the rendering matches across machines without
  needing the original font installed).

## Troubleshooting

**"Image too large (X MB). Recraft Vectorize limit is 5 MB"** — downscale
with `magick` or `cwebp` as shown in Pre-flight validation above.

**"Unsupported image format"** — Recraft accepts PNG, JPG, WEBP only. If
you have a different format (TIFF, BMP, HEIC), convert first:
`magick input.tiff output.png`

**SVG output is enormous (5+ MB)** — the input was probably too complex for
clean vectorization. Try simplifying: flatten colors, remove background,
boost contrast, reduce dimensions. For photographs, SVG is the wrong format
entirely — keep the raster.

## See also

- [`dev-docs/recraft-ai-recraft-vectorize-llms.md`](../../../../dev-docs/recraft-ai-recraft-vectorize-llms.md) — authoritative model card
- [`_replicate_backend.py`](../../create-video/scripts/_replicate_backend.py) — shared backend (cross-skill import)
- [`vectorize.py`](../scripts/vectorize.py) — the CLI runner
- Replicate model page: [replicate.com/recraft-ai/recraft-vectorize](https://replicate.com/recraft-ai/recraft-vectorize)
