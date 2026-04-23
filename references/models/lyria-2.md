# Google Lyria 2 (canonical model ID: `lyria-2`)

**Status:** Registered for `--music-source lyria --lyria-version 2` and for auto-selection when `--negative-prompt` is provided. NOT the default — Lyria 3 Clip is the within-Lyria default as of v4.2.1 (cheaper + newer).

**Hosting providers:** Replicate (`google/lyria-2`). Vertex retired in v4.2.1.

## What makes it unique

Lyria 2 is the only Lyria variant on Replicate that accepts `negative_prompt`. This was the v3.8.3 justification for keeping Lyria in the plugin after ElevenLabs Music won the 12-genre bake-off — `negative_prompt` is Lyria 2's differentiator vs ElevenLabs Music (which has no equivalent exclusion param).

## Canonical constraints

- `duration_fixed_s: 30` — every Lyria 2 clip is exactly 30 seconds. Use `generate_music_lyria_extended` for longer tracks (chains N clips with FFmpeg crossfade).

## Supported canonical params

- `prompt` (required)
- `negative_prompt` (unique to Lyria 2)
- `seed`

**NOT supported:** `reference_images` (Lyria 3 / 3-Pro only). `ReplicateBackend` silently drops `reference_images` with a WARN if passed to `lyria-2`.

## Pricing

`per_call` mode, $0.06 per 30-second clip.

## Auto-selection rules

The `audio_pipeline.py::resolve_lyria_version()` function auto-selects Lyria 2 when:
- User passes `--music-source lyria` AND sets `--negative-prompt "..."`, AND
- User does NOT pass `--lyria-version` explicitly

Users can force Lyria 2 even without `--negative-prompt` via `--lyria-version 2`.

## Authoritative source

`dev-docs/google-lyria-2-llms.md`
