# Transcript Output Formats

Every format is a **pure render** of the cached Scribe JSON (`formats.py`, no
network, no filesystem). Choose formats with `--formats md,srt,vtt,chapters,txt`
or `--formats all`. `json` is always written (it is the cache) even if omitted.

## The formats

| Format | File | Built from | Use |
|---|---|---|---|
| Markdown | `<name>.md` | speaker turns | Readable deliverable — header + `[timecode] Speaker` turns + continuous text. |
| SRT | `<name>.srt` | word cues | Subtitles for editors, YouTube, Descript. `HH:MM:SS,mmm`. |
| WebVTT | `<name>.vtt` | word cues | Web-native subtitles for HTML5 players. `HH:MM:SS.mmm`. |
| Chapters | `<name>.chapters.txt` | pause boundaries | YouTube description — `M:SS Title` markers + per-chapter paragraphs. |
| Plain text | `<name>.txt` | the `text` field | Zero-markup paste target. |
| JSON | `<name>.json` | (the cache) | Lossless archive; every other format regenerates from it. |

## Two independent groupings

The renderers use two **different** ways of chunking the same word stream, because
turns and subtitles serve different jobs:

- **Turn grouping** (markdown, chapters) folds contiguous same-`speaker_id` runs
  into a single labelled block. Audio events (`[laughs]`) render inline in the
  speaker's turn. A speaker change starts a new turn.
- **Cue segmentation** (SRT, VTT) ignores speakers entirely and breaks on reading
  limits — `DEFAULT_CUE_MAX_DUR` (7 s) and `DEFAULT_CUE_MAX_CHARS` (42 chars).
  Subtitle timing is about reading speed, not conversation structure.

## Timecodes

`fmt_time(seconds, style)`:

| style | Example | Where |
|---|---|---|
| `clock` | `0:00`, `1:23`, `1:02:03` | Markdown turns, chapter markers (no leading zero on the top unit). |
| `srt` | `00:01:23,500` | SRT cues (comma millis). |
| `vtt` | `00:01:23.500` | VTT cues (dot millis). |

## Chapters — the split responsibility

`render_chapters` only finds the boundaries and emits a **lead-snippet
placeholder title** per chapter, always forcing the first marker to `0:00` (a
YouTube requirement). It cannot title chapters meaningfully — that needs
understanding of the content. `SKILL.md` instructs Claude to rewrite the
placeholder titles into real ones after the render. A continuous monologue with
no pauses correctly yields a single `0:00` chapter.

## Speaker names

Diarization returns anonymous `speaker_0`, `speaker_1`. Names are applied two ways,
both of which cost **no API call**:

- At run time: `--speakers "0=Julian,1=Dr Ahmad"`, or the orchestrator asks after
  diarization.
- Later: `transcribe.py rename --json <name>.json --speakers "0=Julian,1=Dr Ahmad"`
  re-renders every co-located format from the cache and persists the mapping into
  the JSON (`_speaker_names`).

`render_markdown` and `group_turns` accept a `speaker_names` dict keyed by either
`"0"` or `"speaker_0"` — both forms work.
