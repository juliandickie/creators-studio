# Create Transcript — Speech-to-Text Skill

**Status:** Approved design, pending implementation
**Date:** 2026-07-23
**Scope:** A third top-level skill, `/create-transcript`, adding ElevenLabs Scribe v2 speech-to-text to the plugin. First ingest/analysis capability in a plugin that has been generation-only until now.

## 1. Context and motivation

`creators-studio` generates media — images (`/create-image`), video and audio (`/create-video`). It has never *ingested* media. The one ElevenLabs surface it uses is outbound: `audio_pipeline.py` does TTS narration and music generation. There is no speech-to-text anywhere, no `scribe` entry in `scripts/registry/models.json`, and no reference doc for any Scribe model. This gap is recorded in `docs/dev-notes/2026-07-23-no-speech-to-text-capability.md`, written after a real job (transcribing three downloaded clips) had to be completed entirely outside the plugin using nothing from it but the stored API key.

The account key is already present at `~/.creators-studio/config.json` (`elevenlabs_api_key`), and the full Scribe v2 API is already pinned locally at `dev-docs/elevenlabs-llms-full.txt`. Everything needed exists except the skill that consumes it. This spec defines that skill.

The plugin's identity is "Creative Director." Transcription fits: turning a raw recording into a clean, speaker-labelled, brand-correct transcript is a directed interpretation task, not a mechanical dump. The skill is a Creative Director for the *inbound* half of the pipeline.

**Non-goals for this spec:**

- **Realtime transcription** (`scribe_v2_realtime`). A WebSocket streaming transport for live audio — an entirely different surface that does nothing for transcribing files on disk. Excluded deliberately, not deferred-by-omission.
- **Translation / dubbing.** ElevenLabs has a dubbing product; out of scope. This skill transcribes in the source language.
- **Summarisation, action-item extraction, or any LLM post-processing of the transcript.** The skill produces faithful transcripts. Claude can summarise the *output* in a later turn, but the skill itself does not editorialise.
- **A ProviderBackend refactor.** Like `elevenlabs-music`, Scribe is called directly rather than through the `scripts/backends/` abstraction. Registered in `models.json` for honesty, but wiring it into `ProviderBackend` is future work (matches the Music precedent exactly).
- **Human review / Productions ordering.** ElevenLabs offers human-edited transcripts as a paid upgrade; not wired.
- **Speaker *identification* from voiceprints.** Diarization returns anonymous `speaker_0/1/...`; naming them is a human-in-the-loop relabel (§6), not biometric matching.

## 2. Where it lives

A new top-level skill directory, sibling to the existing two:

```
creators-studio/
└── skills/
    ├── create-image/
    ├── create-video/
    └── create-transcript/          ← NEW
        ├── SKILL.md                 orchestrator
        ├── references/
        │   ├── scribe-models.md     Scribe v2 roster, constraints, languages, billing
        │   ├── transcript-formats.md the 5 output formats + rendering rules
        │   └── keyterms.md          keyterm prompting + standing vocabulary
        └── scripts/
            ├── transcribe.py        CLI, media prep, API call, orchestration
            └── formats.py           pure renderers: JSON → md / srt / vtt / chapters / txt
```

**Why a new skill rather than a `/create-video` subcommand.** Three reasons. (1) Discoverability — `/create-transcript` is the command a user reaches for; burying transcription under a *generation* skill hides it. (2) `create-video/SKILL.md` is already 20+ command rows and carries a size check in the Feature Completion Checklist — adding an ingest capability there pushes against that ceiling. (3) Separation of concern — ingest and generation are different jobs with different mental models. The name keeps the `create-*` verb-noun family symmetry with `create-image` and `create-video`.

**Command:** `/create-transcript`. Argument shape follows the sibling skills:

```
/create-transcript <file-or-dir>                          transcribe with defaults
/create-transcript <file> --formats md,srt,vtt,json       choose outputs
/create-transcript <file> --keyterms "Medit,iTero,iDD"    bias vocabulary
/create-transcript <dir> --batch                          whole-folder
/create-transcript rename --json X.json --speakers "0=Julian,1=Dr Ahmad"
/create-transcript status                                 key + ffmpeg + config check
/create-transcript cost <file-or-dir>                     estimate audio-minutes before running
```

## 3. Design principle — render everything from cached JSON

The single most important property of this design: **the API is called exactly once per source file, ever.** The raw Scribe response is written to disk (`<name>.json`) as the canonical artifact. Every human-facing format — markdown, SRT, WebVTT, YouTube chapters, plain text — is a *pure render* of that JSON. Speaker renaming, adding a format later, tweaking chapter boundaries: all regenerate from the cache. None re-hit the API. None re-charge.

This makes `formats.py` a set of pure functions with **no network and no filesystem side effects** — input is a parsed dict, output is a string. That is what makes the whole skill testable offline against real fixtures, and it is why renaming a speaker is free.

```
source media ──ffmpeg──▶ mono 16kHz mp3 ──POST /v1/speech-to-text──▶ raw JSON  (written once)
                                                                         │
                    ┌────────────────┬───────────────┬─────────────────┼──────────────┐
                    ▼                ▼               ▼                  ▼              ▼
                 .md (turns)      .srt            .vtt          chapters.txt      .txt (plain)
                                        all pure renders of the JSON — no API, no charge
```

## 4. Pipeline (single file)

`transcribe.py` runs this sequence:

1. **Resolve input.** A file path, or (with `--batch` / a directory arg) a walk over known media extensions.
2. **Probe.** `ffprobe` the file. If it has **no audio stream**, fail loud with a clear message and a non-zero exit — never silently produce an empty transcript. Capture duration for the cost log.
3. **Demux.** `ffmpeg -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 64k`. Video containers (VP9/H.264 + Vorbis/AAC) become small mono 16 kHz MP3. Scribe resamples to 16 kHz internally, so this is lossless for transcription quality and cuts upload payload ~20×. Files that are *already* audio still get normalised to the same mono 16 kHz MP3 for a consistent upload path. Skip re-encode only if already mono 16 kHz mp3.
4. **Assemble keyterms** (§7).
5. **Call Scribe.** One `POST https://api.elevenlabs.io/v1/speech-to-text`, `multipart/form-data`: `model_id=scribe_v2`, `diarize=true`, `tag_audio_events=true`, `timestamps_granularity=word`, `language_code` (default auto-detect — omit the field — unless `--language` given), keyterms when present. `xi-api-key` header from config.
6. **Cache.** Write the raw response to `<output-dir>/<name>.json`. This is the point of no further billing.
7. **Render.** For each requested format, call the matching pure function in `formats.py` and write the file.
8. **Log usage.** Non-blocking cost-tracker call recording audio-seconds consumed (§8). A logging failure never blocks output (bare-except pattern, matching `video_generate.py`).

**Auth resolution** reuses the existing precedent: `--api-key` flag → `ELEVENLABS_API_KEY` / `XI_API_KEY` env → `elevenlabs_api_key` in `~/.creators-studio/config.json` (via `scripts/paths.py::config_path()`). Same order `audio_pipeline.py::_get_api_key()` already uses.

**Multipart upload.** The existing `_http_post_json` helpers are JSON-body only. STT needs `multipart/form-data`. A `_http_post_multipart(url, fields, files, api_key)` stdlib helper (~20 lines, `urllib` only, no dependency) is added in `transcribe.py`. Note: `audio_pipeline.py` already grew a `_http_post_multipart()` for v3.7.4 voice-cloning — this skill's copy follows the same shape; a future refactor could hoist one shared helper, but cross-skill import of a private helper is out of scope for v1 (YAGNI).

## 5. Output formats (`formats.py`)

Five pure renderers. All consume the parsed Scribe response `{language_code, language_probability, text, words:[{text,start,end,type,speaker_id}]}` where `type ∈ {word, spacing, audio_event}`.

| Format | Function | Content |
|---|---|---|
| Markdown | `render_markdown` | Header (source, duration, engine, language+confidence, speaker count) + speaker-labelled turns with `[hh:mm:ss]` timecodes + a continuous-text block. The readable deliverable. |
| SRT | `render_srt` | Numbered cues built by grouping words into ≤~7s / ≤~42-char lines on natural pause boundaries. Standard subtitle file. |
| WebVTT | `render_vtt` | `WEBVTT` header + `hh:mm:ss.mmm` cues from the same segmentation as SRT. Web-native. |
| YouTube chapters | `render_chapters` | Per-cue paragraphs plus `0:00 Title` chapter markers. **Script emits timed anchors on pause boundaries; Claude names them** (see §SKILL below). Matches the existing Descript export convention. |
| Plain text | `render_plaintext` | The `text` field, lightly wrapped. The lossless-content, zero-markup fallback. |

**Turn grouping** (shared by markdown + chapters): fold the flat word stream into contiguous same-`speaker_id` runs, joining `word`/`spacing` pieces and rendering `audio_event` entries inline as `[laughs]` / `[applause]`. **Subtitle segmentation** (shared by SRT + VTT) is independent: it breaks on duration/character limits regardless of speaker, because subtitle timing serves reading speed, not turn structure.

Raw JSON is not a renderer — it is the cache from step 6, always written, and is what every other format regenerates from.

## 6. Speaker naming — two-phase, cache-backed

Diarization returns anonymous `speaker_0`, `speaker_1`. Naming is human-in-the-loop and costs no API call:

- **Phase 1 (in the skill run).** After the JSON is cached, `SKILL.md` has Claude surface the first utterance of each detected speaker ("Speaker 0 opens: *'One of the problems with most companies...'*; Speaker 1 opens: *'I do. [laughs]'*") and ask the user who each is — unless `--speakers "0=Name,1=Name"` was passed up front, in which case it is applied directly.
- **Phase 2 (any time later).** `transcribe.py rename --json X.json --speakers "0=Julian,1=Dr Ahmad"` re-renders every co-located format from the cached JSON with the names substituted. A mapping is also persisted into the JSON (`_speaker_names` sidecar key) so subsequent renders keep the names without re-passing them.

Renaming never re-hits the API. This is the payoff of §3.

## 7. Keyterm prompting — three-tier precedence

Scribe v2 batch biases transcription toward supplied key terms (up to 1000, ≤50 chars each) — the fix for brand/product names that generic models mangle (`Medit`, `iTero`, `Spiffy`, `iDD`, `Ascot`, `Al-Hassiny`). Precedence mirrors the house pattern already used by `audio_pipeline.py::strip_named_creators()`:

1. `--keyterms "a,b,c"` CLI flag (per-run override).
2. `transcription.keyterms` array in `~/.creators-studio/config.json` (user standing list).
3. A small shipped default in `keyterms.md`, empty-safe.

The lists **merge** (union, de-duplicated), they do not replace — a per-run `--keyterms` adds to the standing config list rather than shadowing it, because you almost always still want your brand names. `--keyterms-replace` is the escape hatch if pure override is ever needed. Julian's standing dental/product vocabulary is documented in `keyterms.md` as the recommended config seed.

## 8. Registry and cost

**Registry** (`scripts/registry/models.json`): a new `transcription` family and a `scribe-v2` model, following the `elevenlabs-music` shape exactly — including honest subscription pricing:

```json
"scribe-v2": {
  "display_name": "ElevenLabs Scribe v2",
  "family": "transcription",
  "tasks": ["speech-to-text"],
  "doc": "skills/create-transcript/references/scribe-models.md",
  "canonical_constraints": {
    "max_file_bytes": 3221225472,
    "max_duration_s": 36000,
    "languages": "90+",
    "max_keyterms": 1000
  },
  "providers": {
    "elevenlabs": {
      "slug": "(direct)",
      "capabilities": ["diarization", "audio_events", "word_timestamps",
                       "keyterm_prompting", "entity_detection", "multichannel"],
      "pricing": { "mode": "subscription", "rate": null, "currency": "USD" },
      "availability": "GA",
      "notes": "Called directly by skills/create-transcript/scripts/transcribe.py, not via ProviderBackend — same pattern as elevenlabs-music. rate is null because Scribe is subscription/credit billed per the ElevenLabs pricing page; the plugin does not hardcode an unverified per-minute figure."
    }
  }
}
```

Add `"transcription": "scribe-v2"` to `family_defaults`.

**`rate: null` is deliberate.** The pinned docs (`elevenlabs-llms-full.txt` line ~2375) only link out to the pricing page for a Scribe figure — "billed per hour of audio, rates vary by tier." No trustworthy constant exists to hardcode, and the plugin already models ElevenLabs as `subscription`-billed for Music. Inventing a per-minute number would be a fabricated fact; the skill tracks **audio-seconds consumed** instead and reports usage, not dollars.

**Cost tracker** (`cost_tracker.py`): the existing `subscription` handling already returns "no PAYG rate" cleanly. `/create-transcript cost` estimates **audio-minutes** for a file or folder (sum of `ffprobe` durations) so the user can see consumption before committing, without asserting a price.

## 9. Batch mode

`--input DIR` (or a directory positional / `--batch`) walks known media extensions (`.mp3 .wav .m4a .aac .flac .ogg .opus .webm .mp4 .mov .mkv .m4v`). Sequential by default; `--concurrency N` (default 1, sane cap) allows limited parallelism. Consistent with the workflow-fanout lesson (server-side throttling is real): the cap is conservative and each file writes its own JSON + formats immediately, so a mid-run failure loses nothing already done. **A per-file failure never aborts the batch** — it is caught, logged, and the run continues. The end-of-run summary is an explicit table: filename, duration, speakers, formats written, and PASS/FAIL per file with a total count. Partial success is surfaced loudly (fail-loud rule), never swallowed.

## 10. Testing

Two new test modules, stdlib `unittest`, zero network, matching the existing 74-test suite (`python3 -m unittest discover tests`):

- **`tests/test_transcript_formats.py`** — exercises every pure renderer in `formats.py` against real fixtures. Two fixtures, built from actual Scribe responses captured 2026-07-23:
  - `tests/fixtures/scribe_single_speaker.json` — the StoryBrand clip. One speaker; proves the single-speaker turn path and continuous-text rendering.
  - `tests/fixtures/scribe_two_speaker.json` — the Perell/Harry Dry interview. Two speakers **and** `audio_event` entries (`[laughs]`), so diarization grouping and inline audio-event rendering both get real coverage.
  Assertions: timecode formatting, turn boundaries at speaker changes, SRT/VTT cue segmentation and monotonic timestamps, audio-event inlining, speaker-name substitution, chapter-anchor emission.
- **`tests/test_transcribe_cli.py`** — `urlopen` patched (same technique as `test_replicate_backend.py`); asserts multipart assembly, keyterm three-tier merge, auth resolution order, the no-audio-stream failure path, and that render-from-cache touches no network.

Fixtures are trimmed real responses (a handful of words each) — enough to prove structure, small enough to read in a diff.

## 11. SKILL.md orchestration contract

`SKILL.md` drives the Creative-Director layer that the scripts cannot:

- **Intent** — accept a path or folder, infer sensible default formats (md + json always; srt/vtt when the source is video or the user mentions subtitles/YouTube).
- **Language** — default to auto-detect; only pin `--language` when the user states it.
- **Speaker naming** — run the Phase-1 prompt (§6) after diarization unless names were supplied.
- **Chapter naming** — when chapters are requested, read the timed anchors `render_chapters` emitted and write meaningful human titles for each (the split responsibility: the script finds the boundaries, Claude names them). Matches the Descript per-cue + END-marker convention.
- **Keyterms** — surface the merged list when it is non-trivial so the user can confirm before the single billable call.
- **Verify before done** — after writing, read back one rendered artifact and confirm speaker count and language against the JSON, per the house verify-before-done rule; report the output paths.

## 12. Shipping (Feature Completion Checklist)

New user-facing feature ⇒ **minor bump 4.2.3 → 4.3.0**. All checklist items apply:

- **Version (3 files):** `plugin.json`, README badge, `CITATION.cff` (+ `date-released` 2026-07-23).
- **Docs:** CHANGELOG `## [4.3.0]` (Added/Changed) + link ref; README What's New (1–3 sentences, value-forward — *not* a changelog), commands table, and **architecture diagram updated with the new skill dir and its files**; PROGRESS session entry; ROADMAP mark; CLAUDE.md file-responsibilities table gains every new file.
- **Command sync:** the new command appears identically in SKILL.md and README.
- **New-script checks:** `chmod +x` on both scripts, `py_compile` clean, `--help` works.
- **Cross-file consistency:** version identical across the 3 files; CLAUDE.md table matches disk.
- **Lands via `scripts/dev/publish.sh "feat: add /create-transcript speech-to-text skill"`** — direct pushes to main are blocked by the harness rail; the script branches, stages tracked files only, commits with the Co-Authored-By trailer, pushes, opens the PR.

Once merged, close out `docs/dev-notes/2026-07-23-no-speech-to-text-capability.md` — its item 1 (the capability gap) is resolved by this skill.

## 13. Build order

1. `formats.py` pure renderers + `tests/test_transcript_formats.py` with the two real fixtures (TDD — the renderers are the testable core, written first against captured data).
2. `transcribe.py` — auth, `_http_post_multipart`, ffprobe/ffmpeg prep, the single API call, cache, render dispatch, `rename` subcommand, `cost`/`status` subcommands.
3. `tests/test_transcribe_cli.py` with `urlopen` patched.
4. Registry entry + `family_defaults`; cost-tracker `cost` path.
5. Reference docs: `scribe-models.md`, `transcript-formats.md`, `keyterms.md`.
6. `SKILL.md`.
7. Feature Completion Checklist (§12) end to end.
8. Publish PR.
