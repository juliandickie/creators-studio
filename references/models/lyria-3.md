# Google Lyria 3 — Clip variant (canonical model ID: `lyria-3`)

**Status:** Default within Lyria family as of v4.2.1. Used when `--music-source lyria` is set and the prompt does NOT trigger auto-routing to Lyria 3 Pro (no song-structure tags) and no `--negative-prompt` is set.

**Hosting providers:** Replicate (`google/lyria-3`).

## Capabilities

- 30-second MP3 clips at 48kHz stereo
- Text-to-music generation
- **Reference images**: up to 10 images that inspire composition (NEW vs Lyria 2)
- **Vocal generation**: instructed via prompt; use "Instrumental only" to veto
- **Multilingual**: prompt in target language for lyrics in that language
- **Structure tags**: `[Verse]`, `[Chorus]`, etc. respected in the prompt

## Canonical constraints

- `duration_fixed_s: 30`

## Supported canonical params

- `prompt` (required)
- `reference_images` (0–10 images; NEW vs Lyria 2)

**NOT supported:** `negative_prompt`, `seed`

**Filtering behavior:** if a caller passes `negative_prompt` with `lyria-3`, `ReplicateBackend.submit()` silently drops it and logs a WARN via `_logger`. Same for `seed`.

## Pricing

`per_call` mode, $0.04 per 30-second clip. **Cheaper than Lyria 2** ($0.06) despite being the newer model.

## Prompting tips

- Be specific: genre, instruments, BPM, key, mood
- Use `[Verse]`, `[Chorus]`, `[Bridge]` tags to suggest structure — but note that a 30s clip has limited room for structure, so Pro is better for multi-section songs
- Explicit "Instrumental only, no vocals" vetoes vocal generation

## Cost comparison

| Variant | Cost | Duration | Best for |
|---|---|---|---|
| Lyria 2 | $0.06 | 30s | `negative_prompt` workflows |
| **Lyria 3 Clip** | **$0.04** | **30s** | **Default — short instrumental music, reference-image workflows** |
| Lyria 3 Pro | $0.08 | up to 3 min | Full songs with structure / lyrics |
| ElevenLabs Music | subscription | 3s–5 min | Plugin default (won 12-0 bake-off); vocals + finetunes |

## Authoritative source

`dev-docs/google-lyria-3-llms.md`
