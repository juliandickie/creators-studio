# ElevenLabs Music (canonical model ID: `elevenlabs-music`)

**Status:** Overall music default (via `family_defaults.music` in the registry as of v4.2.1). Won the v3.8.3 12-genre blind A/B bake-off vs Lyria 2 with a 12-0 sweep. Used when user invokes music generation without `--music-source lyria`.

**Hosting providers:** ElevenLabs (`(direct)` sentinel slug). NOT routed through `ReplicateBackend` yet — `audio_pipeline.py` calls the ElevenLabs API directly via the existing helpers. Registered in the model registry so `family_defaults.music` has a target and the multi-model principle is upheld.

## Capabilities

- Vocals and/or instrumental (toggled via prompt)
- Lyrics editing per-section or whole-song
- Multilingual: English, Spanish, German, Japanese, and more
- Duration 3–5 minutes (wider range than any Lyria variant)
- **Music Finetunes** — fine-tune the model on your own tracks for brand consistency (Enterprise tier: IP-protected training)
- Curated Finetunes for global genres (Afro House, more)
- **Variant generation**: the ElevenLabs web app generates 1–4 variants from a single prompt. API support unconfirmed as of v4.2.1 — flagged for investigation when ElevenLabs is refactored into a `ProviderBackend`.

## Canonical constraints

- `duration_ms: {min: 3000, max: 300000}` — 3 seconds to 5 minutes

## Pricing

`subscription` mode — billed against the user's ElevenLabs subscription, not per-call USD. `cost_tracker.py` logs usage with $0 per-call cost; dollar totals come from the ElevenLabs dashboard.

## When to use

**ElevenLabs Music (default):**
- Full-length songs with vocals and lyrics
- Multi-lingual vocal tracks
- Brand-consistent music via Finetunes
- Any music need where you have an ElevenLabs subscription

**When to fall back to Lyria:**
- `--negative-prompt` exclusion (Lyria 2)
- Image-inspired music via `reference_images` (Lyria 3 / 3-Pro)
- Pay-per-call economics instead of subscription
- User doesn't have an ElevenLabs subscription

## Future refactor note

In v4.2.1, ElevenLabs Music is called directly from `audio_pipeline.py` without going through the `ProviderBackend` abstraction. A future sub-project refactors these into `scripts/backends/_elevenlabs.py` implementing `ProviderBackend`, unifying the audio surface with the video / image surfaces. The registry entry's `(direct)` sentinel slug is the placeholder for this.

## Music bake-off queued (post-sub-project-C)

A 4-way listening-test bake-off comparing ElevenLabs Music vs Lyria 3 Clip vs Lyria 3 Pro vs Suno (via Kie.ai) is planned for after sub-project C ships. Methodology in `ROADMAP.md` § Music bake-off.

## Authoritative source

`dev-docs/elevenlabs-music.md`
