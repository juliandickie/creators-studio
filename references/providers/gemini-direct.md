# Gemini direct API provider reference

**Purpose:** How the plugin talks directly to `generativelanguage.googleapis.com` for Nano Banana 2 image generation and editing. Separate from Vertex AI (which is a different provider, used for VEO + Lyria pre-sub-project-B).

**Source files (current, pre-refactor):**

- `skills/create-image/scripts/generate.py` — text-to-image
- `skills/create-image/scripts/edit.py` — image-to-image editing

**Refactor status:** In sub-project A, Gemini direct remains wired through the legacy scripts. A follow-up migrates these into `scripts/backends/_gemini_direct.py` implementing the `ProviderBackend` interface. The legacy code paths continue working unchanged until then.

## Authentication

- API key query param: `?key=AIza...`
- Stored at `~/.banana/config.json` → `providers.gemini.api_key` (v4.2.0 schema)
- Migration shim reads legacy `google_api_key` too
- Get a key at <https://aistudio.google.com/apikey>

## Endpoints

- Generate: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}`
- Current default model: `gemini-3.1-flash-image-preview` (Nano Banana 2)

## Critical parameter rules (carry-over from existing plugin constraints)

- `imageSize` values are UPPERCASE on the Gemini API: `"1K"`, `"2K"`, `"4K"`. Lowercase fails silently.
- Gemini generates ONE image per API call. No batch parameter.
- No negative prompt parameter. Use semantic reframing in the prompt instead.
- `responseModalities` MUST explicitly include `"IMAGE"` or the API returns text only.
- **Describe the scene, don't list keywords.** Gemini 3.1's strength is narrative understanding.
- **Don't name publication formats in prompts** ("Vanity Fair magazine cover") — the model renders a literal magazine cover.
- NEVER mention "logo" in Presentation mode prompts — generates unwanted logo artifacts. Say "clean negative space" instead.

See `skills/create-image/references/prompt-engineering.md` for the full prompt construction system.

## Fallback chain

Primary: MCP (via the `@ycse/nanobanana-mcp` package) → Direct Gemini API → Replicate `google/nano-banana-2`.

This ordering survives the v4.2.0 refactor. Future `_gemini_direct.py` backend will participate in routing at the "Direct Gemini API" tier. Replicate already implements `ProviderBackend`; MCP is invoked via a different surface (Claude Code native MCP client, not a provider backend).

## Follow-up work (not in sub-project A)

- Refactor `generate.py` + `edit.py` into `scripts/backends/_gemini_direct.py` implementing `ProviderBackend`
- Add canonical Gemini task coverage to `_TASK_PARAM_MAPS` (`text-to-image`, `image-to-image`)
- Migrate MIME sniffing to `_canonical.normalize_image_to_data_uri()` instead of inline

Tracking: see Session 24 entry in `PROGRESS.md`.
