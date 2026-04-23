# Google Nano Banana 2 (canonical model ID: `nano-banana-2`)

**Underlying model:** `gemini-3.1-flash-image-preview`

**Hosting providers:**

- `gemini-direct` — slug `gemini-3.1-flash-image-preview`, via Google AI Studio API (primary)
- `replicate` — slug `google/nano-banana-2` (fallback)

**Registry entry:** `scripts/registry/models.json` → `models.nano-banana-2`

## Capabilities

- Text-to-image generation
- Image-to-image editing with reference images
- Multilingual prompts (narrative understanding — prose beats keyword lists)
- 14 supported aspect ratios
- Resolutions: 512, 1K, 2K, 4K (Gemini direct); Replicate supports 1K

## Pricing

- **Gemini direct:** `by_resolution` — $0.0005 (512) / $0.002 (1K) / $0.008 (2K) / $0.032 (4K) per call
- **Replicate:** `by_resolution` — $0.003 (1K)

## Prompt engineering

**Full prompt system lives at `skills/create-image/references/prompt-engineering.md`** — 5-component formula, 11 domain modes, PEEL strategy, brand guide integration. All prompt engineering applies to this model whether served via Gemini direct or Replicate.

Key rules (from the official Google guide at `dev-docs/nano-banana-image-generation.md`):

- **Describe the scene, don't list keywords.** Gemini 3.1's strength is narrative understanding.
- **Don't name publication formats** (`"Vanity Fair magazine cover style"`) — the model renders a literal magazine cover with masthead typography.
- **Never mention "logo" in Presentation mode prompts** — produces unwanted logo artifacts. Say "clean negative space" instead.
- The old "banned keywords" list (`"8K"`, `"masterpiece"`, `"ultra-realistic"`) is useless on Gemini 3.1 but not harmful.

## Critical API parameter rules

- `imageSize` values UPPERCASE on Gemini: `"1K"`, `"2K"`, `"4K"` (lowercase fails silently)
- ONE image per API call (no batch parameter)
- `responseModalities` MUST include `"IMAGE"` or the API returns text only
- No negative prompt parameter — use semantic reframing in the prompt

## Canonical constraints (in registry)

- `aspect_ratio` ∈ {`1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`, `1:4`, `4:1`, `1:8`, `8:1`}
- `resolutions` ∈ {`512`, `1K`, `2K`, `4K`}

## Authoritative sources

- `dev-docs/nano-banana-image-generation.md` — Google's official Gemini 3.1 Flash Image prompting guide
- `dev-docs/google-nano-banana-2-llms.md` — Replicate model card
