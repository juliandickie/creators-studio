---
name: create-transcript
description: "Use when ANY request involves transcribing, transcription, speech-to-text, subtitles, captions, or turning audio/video into text. Triggers on: transcribe this, get me a transcript, make subtitles, caption this video, pull the text from this recording, and all /create-transcript commands."
argument-hint: "[transcribe|rename|cost|status] <file, folder, or command>"
---

# Creators Studio - Transcript Creative Director

<!-- ElevenLabs Scribe v2 (batch) speech-to-text. Shares the ElevenLabs key + config with /create-video audio. Version managed in plugin.json. -->
<!-- This skill uses the /create-transcript command. Part of the creators-studio plugin. -->

## Core Principles

1. **One API call per file, ever.** The raw Scribe JSON is cached to disk and every human format (markdown, SRT, VTT, chapters, plaintext) is a pure render of that cache. Speaker renames and added formats regenerate from the cache - never re-transcribe a file you already have JSON for.
2. **Faithful, not editorialised.** This skill produces accurate transcripts. Summaries, action items, or rewrites are a *later* turn on the output, never baked into the transcript.
3. **Names and brands matter.** Diarized speakers come back anonymous and brand names come back mangled unless you help. Use speaker naming and keyterms - they are the difference between a raw dump and a usable transcript.
4. **Fail loud.** A file with no audio, a failed upload, or a partial batch is surfaced explicitly with counts. "Done" means every file succeeded.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/create-transcript <file>` | Transcribe one file with smart default formats. |
| `/create-transcript <file> --formats md,srt,vtt,json` | Choose output formats (`all` for every format; `json` always written). |
| `/create-transcript <file> --keyterm-set dental` | Activate a named keyterm set (per-category vocab from config) on this video only. |
| `/create-transcript <file> --keyterms "Medit,iTero,iDD"` | Add ad-hoc bias terms for this run (one-offs, unions on top of any set). |
| `/create-transcript <file> --speakers "0=Julian,1=Dr Ahmad"` | Name diarized speakers up front. |
| `/create-transcript <folder> --batch` | Transcribe every audio/video file in a folder. |
| `/create-transcript rename --json X.json --speakers "0=Name,1=Name"` | Re-render formats with named speakers - no API call, no charge. |
| `/create-transcript cost <file or folder>` | Estimate audio-minutes before running (no fabricated price). |
| `/create-transcript status` | Check ElevenLabs key + ffmpeg/ffprobe + config keyterms. |

All commands run `python3 ${CLAUDE_SKILL_DIR}/scripts/transcribe.py <subcommand> ...`.

## Transcript Creative Director Pipeline

Follow this for every request - no exceptions.

### Step 1: Analyze Intent

What is the transcript *for*? It sets the default formats:

- **"just transcribe it" / a read-through** → `md,json`
- **video, subtitles, captions, YouTube, Descript** → add `srt,vtt`
- **YouTube chapters / long talk** → add `chapters`
- **feed another tool / paste raw** → add `txt`

When the source is a **video** file, default to `md,srt,vtt,json`. When it is **audio only**, default to `md,json`. State the formats you chose; let the user override with `--formats`.

### Step 2: Language

Default to **auto-detect** (omit `--language`). Only pin `--language <iso>` (e.g. `eng`) when the user states the language or auto-detect has visibly struggled on a prior run.

### Step 3: Keyterms

Keyterms fix brand/product/person names a general model mis-spells. Run `status` to see the configured **keyterm sets** and the always-on list, then:

- If the video fits a category with a set (e.g. `dental`, `agency`), activate it with `--keyterm-set <name>`. This is how keyterms apply to *specific* videos only - nothing is biased unless you name a set.
- For one-off names not in any set (a guest, a specific model), add `--keyterms "..."` for the run (unions on top of the set).
- If nothing fits, run without keyterms - no bias, no surcharge.

Surface the resolved list before running if it is non-trivial, and mention the cost note (keyterms add a +20% surcharge; >100 keyterms force a 20 s minimum billable). See `references/keyterms.md`.

### Step 4: Run

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/transcribe.py "<file-or-folder>" --formats <chosen> [--keyterm-set NAME] [--keyterms "..."] [--speakers "..."] [--output-dir DIR]
```

Outputs land in `<source>/transcripts/` unless `--output-dir` is given. Batch prints a per-file PASS/FAIL summary - if any file failed, report it, do not claim the batch succeeded.

### Step 5: Name the speakers

If diarization found more than one speaker and names were not supplied, read the first utterance of each speaker from the JSON and ask the user who is who:

> Speaker 0 opens: *"One of the problems with most companies…"*
> Speaker 1 opens: *"I do. [laughs]"*
> Who is each speaker?

Then apply the names without re-transcribing:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/transcribe.py rename --json "<name>.json" --speakers "0=Name,1=Name"
```

Watch for mis-attributed identity in the *content itself* - diarization labels who spoke, not who they are. (In the reference clips, the speaker is Harry Dry, not the interviewer David Perell.)

### Step 6: Name the chapters (if requested)

`chapters.txt` ships with placeholder titles (lead snippets) and a forced `0:00` first marker. **Rewrite each placeholder into a meaningful title** based on the content - the script finds the boundaries, you name them. This mirrors the Descript YouTube-chapter convention (per-cue paragraphs + timestamped markers).

### Step 7: Verify before done

Read back one rendered artifact (the markdown) and confirm the speaker count and detected language match the JSON. Report the output paths. Never report "transcribed" on an exit code alone - confirm the rendered file reads correctly.

## Setup

Needs an ElevenLabs API key (shared with `/create-video audio`) at `~/.creators-studio/config.json` (`elevenlabs_api_key`), plus `ffmpeg` and `ffprobe` on PATH. Run `/create-transcript status` to check all three. Keyterm sets live under `transcription.keyterm_sets` (per-video) and the always-on base under `transcription.keyterms` in the same config - see `references/keyterms.md`.

## References

- `references/scribe-models.md` - Scribe v2 roster, endpoint, constraints, billing.
- `references/transcript-formats.md` - the five formats, timecodes, turn vs cue grouping.
- `references/keyterms.md` - keyterm prompting, per-video sets vs always-on list, precedence, recommended config seed.
