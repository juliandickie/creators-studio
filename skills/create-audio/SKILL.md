---
name: create-audio
description: "Use when ANY request is for audio on its own, with no video: music, a soundtrack or background bed, sound effects, Foley, ambience, a whoosh or impact, a jingle or sting, a voiceover or narration, or designing and cloning a voice. Triggers on: make me some music, generate a sound effect, I need a whoosh, background track for this, record a voiceover, design a voice, and all /create-audio commands."
argument-hint: "[music|sfx|narrate|mix|voice|status] <prompt, text, or command>"
---

# Creators Studio - Audio Creative Director

<!-- ElevenLabs Music, Sound Effects and TTS, with Lyria as the alternative music source. Shares the ElevenLabs key and custom voices with /create-video. Version managed in plugin.json. -->
<!-- This skill uses the /create-audio command. Part of the creators-studio plugin. -->

## Core Principles

1. **Creative Director for audio.** Never pass the user's words straight through. Work out the use (ad, intro, game, podcast, video bed), then write the prompt in sound terms: genre, mood, instruments, tempo, texture, length.
2. **Pick the right engine.** A full piece of music goes to `music`. A short sound, a hit, an ambience or a drum loop goes to `sfx`. Spoken words go to `narrate`. The sound-effects model cannot produce full music productions, and the music model is wasted on a one-second whoosh.
3. **Verify before done.** Probe every file with `ffprobe` and check it isn't silent before reporting it. Report the path, duration and the exact prompt used.

## Quick Reference

All commands run `python3 ${CLAUDE_SKILL_DIR}/../create-video/scripts/audio_pipeline.py <subcommand> ...`. The script lives with /create-video because the video audio pipeline uses the same code.

| Command | What it does |
|---------|-------------|
| `/create-audio music --prompt "..." [--length-ms N] [--with-vocals] [--source lyria\|elevenlabs]` | A music track. ElevenLabs Music by default, 3 s to 5 min, instrumental unless `--with-vocals`. Lyria is the alternative and supports `--negative-prompt`. |
| `/create-audio sfx --prompt "..." [--duration S] [--loop] [--influence 0-1]` | A sound effect, ambience or musical element, 0.5 to 30 s. |
| `/create-audio narrate --text "..." [--voice ROLE]` | A voiceover with ElevenLabs TTS, using a saved custom voice role or a voice ID. |
| `/create-audio mix --narration N --music M` | Mix a voiceover over music with automatic ducking. |
| `/create-audio voice design --description "..."` | Three voice previews from a text description. |
| `/create-audio voice promote --generated-id ID --name N --role R` | Save a preview as a permanent custom voice. |
| `/create-audio voice clone --audio PATH --name N --role R` | Clone a voice from 30+ seconds of audio (Instant Voice Cloning). |
| `/create-audio voice list` | List saved custom voices. |
| `/create-audio status` | Check the ElevenLabs key, ffmpeg and custom voices. |

`voice design`, `voice promote`, `voice clone` and `voice list` map to the script's `voice-design`, `voice-promote`, `voice-clone` and `voice-list` subcommands. Add `--out PATH` to any generating command; the default folder is `~/Documents/creators_audio/`.

To put audio into a video (replace a clip's soundtrack, or narration plus music laid over a stitched sequence), use `/create-video audio swap` or `/create-video audio pipeline`.

## Pipeline

### Step 1 - Brief

Ask only what is missing: where the audio will be used, how long it must be, the mood, and whether it must loop. A sound for a video cut needs its exact length.

### Step 2 - Choose the command

| Need | Command |
|---|---|
| Background music, intro, outro, jingle, song | `music` |
| One-shot sound: whoosh, impact, click, notification, door, footsteps | `sfx` |
| Ambience or room tone to sit under something | `sfx --loop` |
| Drum loop, riser, braam, synth pad, a few bars | `sfx` (add BPM and key) |
| Spoken words | `narrate` |

### Step 3 - Write the prompt

**Sound effects.** Describe the sound plainly, then what it hits or where it happens: "Glass shattering on concrete". For a sequence, list the events in order: "Footsteps on gravel, then a metallic door opens". Sound-design words sharpen the result: impact, whoosh, ambience, one-shot, loop, stem, braam, glitch, drone. For musical elements, give tempo and key: "90s hip-hop drum loop, 90 BPM".
- Leave `--duration` off to let the model pick a natural length. Set it when the sound must fit a cut.
- `--influence` defaults to 0.3. Raise it toward 1 for a literal reading, and lower it for more varied takes.
- `--loop` makes a seamless loop, which suits ambience and textures.

**Music.** Genre, mood, instrumentation, tempo and structure, in plain descriptive words: "Warm acoustic folk, fingerpicked guitar and soft cello, hopeful, 90 BPM, gentle build to the end". Never name artists, composers, bands, films or brands. Both music providers reject these, and the script strips known names before sending (`--allow-creators` turns that off). Instrumental is the default; add `--with-vocals` for sung parts.

**Narration.** Use the `eleven_v3` default model. Audio tags such as `[exhales]` or `[warmly]` set emotion, ellipses (`...`) add pauses, and selective CAPS add emphasis. Match the line length to the voice's measured WPM, stored in `custom_voices.<role>.wpm`.

### Step 4 - Generate and check

Run the command, then confirm with `ffprobe` that the duration matches the brief, and use `ffmpeg -af volumedetect` to confirm the file isn't silent. For anything over a few seconds, offer two or three prompt variations rather than one take.

### Step 5 - Report

Give the file path, duration, the prompt used, and one suggested refinement.

## Voice selection

- `--voice narrator` reads `custom_voices.narrator` from `~/.creators-studio/config.json`. Any other role name works the same way.
- Any string that isn't a saved role is treated as an ElevenLabs voice ID.
- To make a new voice: `voice design`, listen to the previews, then `voice promote`. Cloning needs the speaker's consent.

## Cost

All three engines use your ElevenLabs subscription credits; Lyria music bills through Replicate per clip. ElevenLabs' sound-effects page lists a set duration at 40 credits per second. Check the ElevenLabs usage page rather than quoting a dollar price.

## Setup

Needs `elevenlabs_api_key` in `~/.creators-studio/config.json` (the same key as /create-transcript and /create-video audio) and `ffmpeg`/`ffprobe` on PATH. Run `/create-audio status` to check.

## References

- `../create-video/references/audio-pipeline.md` - music providers and bake-off results, Lyria prompting, voice design and cloning, the custom voice schema, TTS prompt engineering, WPM measurement.
