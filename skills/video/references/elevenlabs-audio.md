# ElevenLabs Audio Replacement Pipeline (v3.7.1+)

This reference covers the v3.7.1 audio replacement architecture: why it exists,
how to use it, and the empirical findings from spike 3 of the strategic reset
session that informed its design.

**Quick links:**
- Script: `skills/video/scripts/elevenlabs_audio.py`
- Slash commands: `/video audio narrate|music|mix|swap|pipeline`, `/video voice design|promote|list`
- Companion reference: `skills/video/references/video-audio.md` (VEO native audio)
- Findings: spike 3 results documented in `~/Desktop/spike3-elevenlabs-audio/spike-2-and-3-findings.md`

---

## Why this exists

**The problem v3.7.1 solves:** when you stitch multiple separately-generated VEO clips into a longer sequence, each clip has its own emergent music intro/outro envelope. FFmpeg concatenation joins them losslessly but the *audio* still has audible seams every clip-duration — the music "restarts" at every cut. This is a structural artifact of independent generation, not a per-clip quality issue. **The fix is to replace the entire audio bed with a single continuous track**, eliminating clip boundaries from the audio dimension by construction.

**Empirical context:** spike 2 of the strategic reset session generated 4 VEO 3.1 Lite clips of the same autumn forest valley with identical voice descriptors and stitched them into a 32-second sequence. Voice character was perfectly consistent across all 4 clips (proving voice anchoring works), but the music bed had audible seams. Spike 3 then validated the audio-replacement architecture end-to-end with the v3.7.1 prototype, and the user confirmed the seams disappeared.

---

## Architecture

```
                     ┌───────────────────────────┐
                     │   VEO video (stitched,    │
                     │   audio will be replaced) │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
            ┌──────────────────────────────────────────┐
            │  Pipeline orchestrator (parallel calls)  │
            │                                          │
            │   ┌──────────────┐    ┌──────────────┐  │
            │   │ ElevenLabs   │    │ Eleven Music │  │
            │   │ TTS          │    │ POST /v1/    │  │
            │   │ POST /v1/tts │    │ music        │  │
            │   │ eleven_v3    │    │ music_v1     │  │
            │   └──────┬───────┘    └──────┬───────┘  │
            │          │                   │          │
            │          ▼                   ▼          │
            │     narration.mp3       music.mp3       │
            │     (continuous)        (continuous)    │
            └──────────────┬──────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────────┐
            │  FFmpeg sidechain compression    │
            │  apad narration → silence-pad    │
            │  to match music length           │
            │  threshold=0.04 ratio=10         │
            │  attack=15ms release=350ms       │
            │  weights=1.6:1.0 (voice louder)  │
            └──────────────┬───────────────────┘
                           │
                           ▼
            ┌──────────────────────────────────┐
            │  FFmpeg audio-swap into video    │
            │  -map 0:v -map 1:a               │
            │  -c:v copy (lossless)            │
            │  -c:a aac -b:a 192k              │
            │  -shortest -movflags +faststart  │
            └──────────────┬───────────────────┘
                           │
                           ▼
                  Final MP4 (ship-ready)
```

The TTS call and the music call run in parallel via `concurrent.futures.ThreadPoolExecutor` because they're independent. This roughly halves the user-perceived latency from ~19s sequential to ~12s parallel.

---

## Quick start

### One-shot pipeline (the canonical command)

```bash
python3 skills/video/scripts/elevenlabs_audio.py pipeline \
  --video stitched-sequence.mp4 \
  --text "Each year... the seasons change across this valley, painting the forest in red and gold. [exhales] The river runs COLD here..." \
  --music-prompt "Cinematic nature documentary background score, slow and contemplative warm orchestral strings with soft piano, instrumental only, no vocals, around 70 BPM" \
  --voice narrator \
  --out final.mp4
```

This runs all four stages: parallel TTS + music, FFmpeg ducked mix, FFmpeg audio-swap into the source video. Output is a final MP4 with the new audio swapped in.

### Individual stages (for debugging or partial workflows)

```bash
# Just generate narration:
elevenlabs_audio.py narrate --text "..." --voice narrator --out narration.mp3

# Just generate music:
elevenlabs_audio.py music --prompt "..." --length-ms 32000 --out music.mp3

# Mix existing narration + music:
elevenlabs_audio.py mix --narration narration.mp3 --music music.mp3 --out mixed.mp3

# Audio-swap an arbitrary audio file into a video:
elevenlabs_audio.py swap --video v.mp4 --audio mixed.mp3 --out final.mp4
```

### Status check (do this first)

```bash
elevenlabs_audio.py status
```

Verifies your ElevenLabs API key, ffmpeg/ffprobe availability, and lists any custom voices saved in `~/.banana/config.json`.

---

## Voice management

### Designing a custom voice

ElevenLabs Voice Design generates a custom voice from a text description. Three previews per call (each ~20s of sample audio); pick one and promote it to a permanent saved voice.

```bash
# Step 1: design — generates 3 candidate previews
elevenlabs_audio.py voice-design \
  --description "A mature male documentary narrator with a warm baritone voice and slight British accent. Calm, measured, authoritative delivery, like a seasoned BBC wildlife narrator. Approximately 50-60 years old. Speaks with deliberate pacing, gentle gravitas, and quiet reverence." \
  --model eleven_ttv_v3 \
  --guidance-scale 5

# Output JSON includes paths to 3 preview MP3s. Listen to them, pick the best.
# Note the generated_voice_id of the chosen preview.

# Step 2: promote — saves the chosen preview as a permanent voice + stores in config
elevenlabs_audio.py voice-promote \
  --generated-id DGEKfN3sQ7BmtUUNKoyI \
  --name "Nano Banana Narrator" \
  --role narrator \
  --description "A mature male documentary narrator with..." \
  --notes "Designed for v3.7.1. Pacing ~159 wpm. Use ellipses and audio tags to slow."
```

### Listing saved voices

```bash
elevenlabs_audio.py voice-list
```

Returns the contents of `~/.banana/config.json` `custom_voices` section.

### Using a custom voice

Pass `--voice ROLE` to any subcommand that takes a voice. The pipeline will look up the role in `custom_voices` and use the saved `voice_id`. If no `--voice` is specified, the pipeline defaults to the `narrator` role.

```bash
elevenlabs_audio.py pipeline --voice narrator ...        # default
elevenlabs_audio.py pipeline --voice character_a ...    # different role
elevenlabs_audio.py pipeline --voice 21m00Tcm4TlvDq8ikWAM ...  # literal voice_id
```

### Custom voice schema (in `~/.banana/config.json`)

```json
{
  "custom_voices": {
    "narrator": {
      "voice_id": "DGEKfN3sQ7BmtUUNKoyI",
      "name": "Nano Banana Narrator",
      "description": "...",
      "source_type": "designed",
      "design_method": "text_to_voice",
      "model_id": "eleven_ttv_v3",
      "guidance_scale": 5,
      "should_enhance": false,
      "created_at": "2026-04-14",
      "provider": "elevenlabs",
      "notes": "..."
    }
  }
}
```

**`source_type`** is the discriminator that distinguishes voice creation paths:
- **`designed`**: created via `/v1/text-to-voice/design` from a text prompt (this is the path v3.7.1 ships)
- **`cloned`**: created via Instant Voice Cloning from an audio sample (planned future addition)
- **`library`**: a hand-picked voice from the ElevenLabs community library (always supported by passing the literal voice_id)

**`provider`** is currently always `"elevenlabs"` but enables future second-provider support without schema change.

---

## Prompt engineering — TTS narration

### Default model and settings

- **Model:** `eleven_v3` (most expressive, supports audio tags, ellipses, capitalization)
- **Stability:** 0.5 (Natural mode — honors audio tags but stays close to source text)
- **Similarity boost:** 0.75 (closer to reference voice character)
- **Style:** 0.0 (no extra stylistic exaggeration)
- **Speaker boost:** true

### Audio tags

Eleven v3 supports inline audio tags in the form `[tag-name]` placed immediately before the text they modify. The documented set is non-exhaustive — the model interprets unknown tags semantically via its training. Test with the tag flexibility experiment if you're unsure.

**Documented tags useful for narration:**
- `[exhales]`, `[sighs]`, `[exhales sharply]`, `[inhales deeply]` — natural breath pauses for emotional weight
- `[whispers]` — for hushed reverent moments
- `[thoughtful]` — closest documented register for contemplative narration
- `[short pause]`, `[long pause]` — explicit pause control

**Undocumented but empirically working tags for documentary register (verified spike 3):**
- `[contemplative]` — slight slowdown vs baseline
- `[reverent]` — produces ~20% slower delivery (largest measured effect of the undocumented set)
- `[wistful]` — similar to `[thoughtful]`

**Rule of thumb:** match the tag to the voice character. Daniel and Nano Banana Narrator both honor reverent/contemplative/wistful well because they're serious documentary voices. A bright energetic voice probably won't honor `[reverent]` strongly. Don't pile up tags — 1-2 per 30-second narration is plenty.

### Ellipses for pacing

Three dots (`...`) inside or between sentences create natural contemplative pauses. They're the lightest-weight pacing control — don't carry the same risk as audio tags but produce smaller effects. Use them generously for documentary narration.

```text
Each year... the seasons change across this valley, painting the forest in red and gold.
```

### Selective capitalization for emphasis

A single capitalized word in `eleven_v3` produces audible emphasis without affecting surrounding pacing. Use sparingly — 1-2 per sentence at most.

```text
The river runs COLD here, fed by mountain springs that have flowed for ten thousand years.
```

### Line length calibration

VEO 3.1 native narration has a "delivery mode drift" failure mode when narration is too short for the clip duration: the model non-deterministically sings the line to fill the time. **The fix is to write narration lines that fill the clip duration naturally** at the target voice's WPM:

```
target_word_count = duration_seconds × (voice_wpm / 60)
```

**Per-voice WPM reference (verified spike 3):**
- VEO native narrator: ~120 wpm → 16 words for 8s clip
- Daniel + eleven_v3: ~137 wpm → 18 words for 8s clip
- Nano Banana Narrator + eleven_v3: ~159 wpm → 21 words for 8s clip

Audio tags and ellipses slow delivery by ~5-10%; account for them when targeting precise durations.

### Banned content

ElevenLabs TTS does not have the same content restrictions as Eleven Music. You can use named creators, brands, locations, etc. in narration text without triggering guardrails. The restrictions only apply to the music generation API (see below).

---

## Prompt engineering — Eleven Music

### Default model and settings

- **Model:** `music_v1`
- **Force instrumental:** `true` (always, for narration use cases — vocals would compete with the narrator)
- **Length:** 3,000ms minimum, 600,000ms (10 min) maximum

### Music prompt structure

Effective prompts include: genre/style, instrumentation, tempo (BPM), mood, and "instrumental only, no vocals" as an explicit constraint. Avoid named creators or brands — see banned content section below.

**Good example:**
```
Cinematic nature documentary background score. Slow and contemplative warm orchestral
strings with soft piano. Gentle and atmospheric, evoking autumn forests and quiet rivers.
Instrumental only, no vocals. Subtle textures, no heavy percussion. Around 70 BPM.
```

### ⚠️ Banned content (TOS guardrail)

The Eleven Music API **blocks prompts that name copyrighted creators or brands**. Empirically discovered in spike 3 v1: a prompt containing `"Annie Leibovitz / BBC Earth aesthetic"` returned HTTP 400 with code `bad_prompt` and a `prompt_suggestion` showing a sanitized version. The cleaned prompt (with the named-creator references removed) sailed through.

**This is music-API-specific.** Image generation prompts welcome creator names (`prompt-engineering.md` has many examples). Music prompts do not. Don't reuse image-gen prompt patterns for music.

**For v3.7.x prompt-construction logic:** strip named-creator references from music prompts before sending. Keep generic descriptors only (genre, mood, instrumentation, tempo).

### Audio bed continuity

ElevenLabs Music produces a single continuous track per call — there are no clip boundaries internal to the music. This is the entire reason v3.7.1 fixes the multi-clip seam problem: by replacing VEO's clip-locked audio with a single Eleven Music track, the seams literally cannot exist.

---

## FFmpeg pipeline details

### Stage 3: Sidechain compression (mix)

The mix stage uses FFmpeg's `sidechaincompress` filter with the narration as the side-chain trigger and the music as the audio being compressed. This produces "ducking" — the music drops in volume when the narrator is speaking and rises during gaps.

**Filter graph:**
```
[0:a]aformat=channel_layouts=stereo,apad=whole_dur=DURATION[narration_padded];
[1:a]volume=0.55[music_quiet];
[music_quiet][narration_padded]sidechaincompress=
    threshold=0.04:ratio=10:attack=15:release=350[ducked];
[narration_padded][ducked]amix=
    inputs=2:duration=longest:weights='1.6 1.0'[mixed]
```

**Key parameters:**
- **`apad whole_dur=DURATION`** — pads the narration with silence to match the music length. Critical: without this, the `sidechaincompress` filter inherits the narration's length and truncates the music tail.
- **`volume=0.55`** on the music — bring the music down before mixing so the narration sits above it cleanly.
- **`threshold=0.04`** — sensitivity of the side-chain trigger. Lower = more sensitive (ducks even on quiet narration parts).
- **`ratio=10`** — how much to compress the music when triggered. 10:1 is aggressive; 4:1 is gentle.
- **`attack=15ms`** — how fast the duck kicks in. Faster = more responsive, but very fast can sound pumpy.
- **`release=350ms`** — how fast the music returns to full volume after speech ends. 350ms is gentle and natural.
- **`amix weights='1.6 1.0'`** — narration is mixed 1.6× louder than the ducked music in the final output.

### Stage 4: Audio-swap (lossless video)

Replaces the audio track of an MP4 without re-encoding the video. The video is stream-copied (lossless, fast — ~65× realtime) and the new audio is re-encoded to AAC at 192 kbps for MP4 container compatibility.

```bash
ffmpeg -y \
  -i video_with_old_audio.mp4 \
  -i new_audio.mp3 \
  -map 0:v \
  -map 1:a \
  -c:v copy \
  -c:a aac -b:a 192k \
  -shortest \
  -movflags +faststart \
  output.mp4
```

**Key flags:**
- **`-map 0:v -map 1:a`** — explicitly map video from input 0 (the original video) and audio from input 1 (the new audio). Default mapping would pick whichever streams ffmpeg thinks are best; explicit mapping is unambiguous.
- **`-c:v copy`** — stream-copy the video. No re-encoding, no quality loss, blazing fast.
- **`-c:a aac -b:a 192k`** — re-encode the audio to AAC for MP4 compatibility (MP3 in MP4 works but AAC is more compatible across players). 192 kbps is broadcast-quality.
- **`-shortest`** — trim the output to the shorter of the two inputs. Handles minor video/audio duration mismatches (typically <100ms / 1 frame at 24fps).
- **`-movflags +faststart`** — moves the moov atom to the front of the file so social media uploaders can start processing the video as soon as the first byte arrives.

---

## Cost model

ElevenLabs is subscription-billed. For users on Creator tier or above, the per-call USD cost of a typical reel is effectively zero within the monthly quota.

**Approximate usage per 32-second reel:**
- TTS narration (~80 chars): negligible (~0.027% of monthly Creator quota)
- Eleven Music (32 seconds): negligible (under 1% of Creator quota for music ops)

**Creator tier quotas (April 2026):**
- 300,000 characters/month for TTS
- Additional credits for music and STS (separate from char quota)
- 100,000+ characters means ~3,750 30-second reels per month, all included in the subscription

`scripts/cost_tracker.py` includes nominal PAYG rates for ElevenLabs models so users can see the "credits-equivalent" cost of a generation, but these are not what's actually billed if the user is on a subscription tier.

---

## Empirical findings from spike 3 (carry-overs from `video-audio.md`)

These findings are documented in detail in `references/video-audio.md` "Discoveries from real production" section. Summary:

- **F2 (line-length):** narration must fill ~75-100% of clip duration to prevent VEO singing failure mode
- **F5 (tag flexibility):** v3 audio tags are open-ended, not whitelisted; undocumented tags work via semantic interpretation
- **F6 (music TOS):** Eleven Music blocks named creators/brands, image-gen does not
- **F7 (should_enhance):** Voice Design with `should_enhance=true` produces ~50% less variance and ~7% faster delivery
- **F8 (per-voice WPM):** voice character affects pacing independently of model and tags; calibrate line length per voice
- **F10 (`[exhales]`):** documented audio tag produces audible breath when placed before a sentence
- **F11 (capitalization):** single capitalized word produces emphasis without disturbing surrounding pacing
- **F12 (ellipses):** ellipses produce natural contemplative pauses, slowing delivery by ~5%

Each finding has a `<!-- verified: 2026-04-14 -->` marker in `video-audio.md` per the dated-verification principle from the strategic reset.

---

## Setup

1. **Get an ElevenLabs API key** at https://elevenlabs.io/app/settings/api-keys (Creator tier recommended for the music API)
2. **Add it to `~/.banana/config.json`:**
   ```bash
   python3 -c "import json,os; p=os.path.expanduser('~/.banana/config.json'); c=json.load(open(p)) if os.path.exists(p) else {}; c['elevenlabs_api_key']='YOUR_KEY_HERE'; json.dump(c, open(p,'w'), indent=2); os.chmod(p, 0o600)"
   ```
3. **Verify with status check:**
   ```bash
   python3 skills/video/scripts/elevenlabs_audio.py status
   ```
4. **Optionally design a custom narrator voice** (see Voice Management section above) or use any voice from your ElevenLabs library by passing the literal `voice_id`.

---

## Limitations and known issues

- **Stereo output collapses to mono in the mix stage.** The `amix` filter currently produces mono output despite the `aformat channel_layouts=stereo` directive on the narration branch. This is a polish issue — the audio is fully audible and high-quality — but the music's stereo image is lost in the mix. A future v3.7.x fix would route the narration through `pan=stereo|c0=c0|c1=c0` before mixing to force a stereo output.
- **Music TOS guardrails are runtime-discovered, not validated.** v3.7.1 does not pre-check music prompts for named creators before sending. If the API returns 400 with `bad_prompt`, the script surfaces the error message and the API's `prompt_suggestion`, but it doesn't auto-retry with a sanitized prompt. Users iterate manually.
- **Per-voice WPM is not auto-measured.** v3.7.1 uses a single default WPM constant for line-length math. A future v3.7.x fix would either probe each new custom voice with a calibration call or store an empirically-measured `wpm` field in the `custom_voices` schema.
- **Voice Design previews expire on ElevenLabs' side.** The `generated_voice_id` returned by `/v1/text-to-voice/design` is only valid for a limited time (exact TTL undocumented but appears to be hours, not days). Promote chosen previews promptly.
- **Voice cloning is not yet wired up.** The `source_type: cloned` schema field is reserved but no `voice-clone` subcommand exists in v3.7.1. Future addition.

---

## Related references

- `skills/video/references/video-audio.md` — VEO native audio capabilities (dialogue, ambient, SFX, narration before v3.7.1)
- `skills/video/references/veo-models.md` — VEO model specs and pricing
- `skills/video/references/video-prompt-engineering.md` — VEO prompt construction (different from ElevenLabs prompts)
- `skills/banana/references/post-processing.md` — FFmpeg patterns shared across image and video pipelines
- `skills/banana/scripts/cost_tracker.py` — pricing table including ElevenLabs entries
