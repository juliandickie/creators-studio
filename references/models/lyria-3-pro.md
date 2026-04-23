# Google Lyria 3 Pro (canonical model ID: `lyria-3-pro`)

**Status:** Registered for opt-in and auto-routed use. NOT the default — ElevenLabs Music is the overall music default; Lyria 3 Clip is the within-Lyria default. Pro is auto-selected when user passes `--music-source lyria` with a prompt containing song-structure markers, AND confirms via `--confirm-upgrade` flag.

**Hosting providers:** Replicate (`google/lyria-3-pro`).

## What makes it unique

A full-song generator, not just a clip. Produces structured tracks up to ~3 minutes with verses, choruses, bridges, custom lyrics, and timestamp control. This is a meaningful capability gap vs Lyria 2 / Lyria 3 Clip (both 30-second fixed) and is closer in spirit to Suno (available after sub-project C) than to ElevenLabs Music.

## Capabilities

- MP3 audio up to ~3 minutes at 48kHz stereo
- Text-to-song with structure tags: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Hook]`, `[Intro]`, `[Outro]`
- Custom lyrics embedded in the prompt
- Timestamp control: `[0:00 - 0:30] Intro: soft piano` guides timing
- Reference images (up to 10) to inspire composition
- Multilingual
- Vocal generation with lyric following

## Canonical constraints

- `duration_max_s: 180` — aspirational; Google's model card says duration is "influenced by prompting" rather than strictly controlled.

## Supported canonical params

- `prompt` (required; contains the song structure, lyrics, and tempo/style direction)
- `reference_images` (0–10 images)

**NOT supported:** `negative_prompt`, `seed`

## Auto-selection rules (v4.2.1)

`audio_pipeline.py::resolve_lyria_version()` auto-routes to Lyria 3 Pro when:
1. User passed `--music-source lyria`
2. User did NOT pass `--lyria-version`
3. User did NOT pass `--negative-prompt`
4. Prompt contains song-structure markers detected by `detect_lyrics_intent()`: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Hook]`, `[Intro]`, `[Outro]`, `[Pre-Chorus]`, `[Refrain]`, or timestamp ranges like `[0:00 - 0:30]`
5. Prompt does NOT contain explicit instrumental markers (`"instrumental only"`, `"no vocals"`, `"no lyrics"`)
6. User passes `--confirm-upgrade` to acknowledge the 2× cost vs Lyria 3 Clip

Without `--confirm-upgrade`, the auto-detection raises `LyriaUpgradeGateError` with a 3-option help message. This prevents silent cost surprises.

## Pricing

`per_call` mode, $0.08 per file (up to ~3 min). Effective per-second rate for a full 3-minute song: ~$0.00044/s — dramatically cheaper than Lyria 3 Clip at per-second rates, but per-file pricing means short songs don't get a discount.

## Prompting tips (from the Google model card)

- Separate lyrics from musical direction. Example:
  ```
  [Verse 1]
  Walking through the neon glow,
  city lights reflect below

  [Chorus]
  We are the echoes in the night

  Genre: Dreamy indie pop. Mood: Nostalgic and uplifting. Tempo: 110 BPM.
  ```
- Timestamp control for precise timing:
  ```
  [0:00 - 0:15] Intro: Soft lo-fi beat
  [0:15 - 0:45] Verse: Warm Fender Rhodes piano
  [0:45 - 1:15] Chorus: Full arrangement with lush pads
  ```
- Include duration hint in prompt: `"Generate approximately a 2-minute track"`
- Iterate with Lyria 3 Clip first (cheaper, faster) to find a sound, then use Pro for the final full song

## Authoritative source

`dev-docs/google-lyria-3-pro-llms.md`
