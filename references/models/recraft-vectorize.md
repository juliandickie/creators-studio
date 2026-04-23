# Recraft Vectorize (canonical model ID: `recraft-vectorize`)

**Hosting providers:** Replicate (`recraft-ai/recraft-vectorize`).

**Registry entry:** `scripts/registry/models.json` → `models.recraft-vectorize`

## What it does

Raster (PNG / JPG / WebP) → SVG vectorization. Used by `/create-image vectorize`.

## Canonical constraints

- Input size ≤ 5 MB
- Input resolution ≤ 16 MP (16,777,216 pixels)
- Input dimensions: 256–4096 px per side
- Accepts: PNG, JPG, WebP

## Pricing

`per_call` mode, $0.01 flat regardless of input dimensions within constraints.

## Authoritative source

`dev-docs/recraft-ai-recraft-vectorize-llms.md`
