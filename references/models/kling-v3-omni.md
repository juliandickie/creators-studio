# Kling Video 3.0 Omni (canonical model ID: `kling-v3-omni`)

**Hosting providers:** Replicate (`kwaivgi/kling-v3-omni-video`).

**Registry entry:** `scripts/registry/models.json` → `models.kling-v3-omni`

## Capabilities (in addition to all Kling v3 capabilities)

- **Reference images** — multimodal conditioning via `reference_images` array
- **Video editing** — takes an input video and applies natural-language edits (camera, style, subject swaps) while preserving motion and timing
- Everything Kling v3 does (text-to-video, image-to-video, multi-shot, native audio, negative prompts)

## When to use v3-omni vs v3

- **Use v3-omni for:** reference-image-driven style transfer, video editing workflows, multimodal inputs beyond `start_image`.
- **Use v3 for:** straightforward text-to-video and image-to-video. Same per-second rate, simpler API surface.

## Pricing

Same as Kling v3: `per_second` mode, $0.02/s.

## Canonical constraints

Same as Kling v3 (see `kling-v3.md`).

## Authoritative source

`dev-docs/kwaivgi-kling-v3-omni-video-llms.md`
