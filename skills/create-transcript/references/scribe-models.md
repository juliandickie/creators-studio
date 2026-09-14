# Scribe v2 - Speech-to-Text Model Reference

Authoritative source: `dev-docs/elevenlabs-llms-full.txt` (workspace root). Query
with an Explore subagent or grep - do not Read the 10 MB file raw.

## Model roster

| Model | What it is | Use here |
|---|---|---|
| `scribe_v2` | State-of-the-art batch speech recognition, 90+ languages. Word-level timestamps, diarization (up to 32 speakers), audio-event tagging, keyterm prompting (up to 1000), entity detection. | **Default.** `--model scribe_v2`, or omit the flag. |
| `scribe_v2_medical` | Clinical-speech sibling of `scribe_v2`, GA 2026-09-11. Same options, same response shape, same billing rate. | **Opt-in via `--model scribe_v2_medical`.** For clinical source audio. See "Choosing between v2 and v2 Medical" below. |
| `scribe_v2_realtime` | WebSocket streaming recognition, ~150 ms latency. | **Not used.** Live-audio transport, irrelevant to transcribing files on disk. Out of scope by design. |
| `scribe_v1`, `scribe_v1_experimental` | Prior generation. | Superseded by v2. Not offered by this skill. |

The batch endpoint's full accepted roster is `scribe_v1`, `scribe_v1_experimental`,
`scribe_v2`, `scribe_v2_medical` - confirmed 2026-09-14 by sending a deliberately
invalid `model_id` and reading the `unsupported_model` error, which enumerates
them. That probe is the authoritative check when the docs page lags; the
`/v1/models` endpoint lists text-to-speech models only and will not show Scribe.

`keyterms` is accepted by both v2 models. It is NOT accepted with `scribe_v1` -
the API returns HTTP 400 there.

## Choosing between v2 and v2 Medical

`scribe_v2_medical` is a **separate model, not a mode**. There is no quality
ladder here: picking it is a bet that the audio is clinical, and that bet can go
either way on a given file. Both were verified 2026-09-14 to accept the identical
field set (`diarize`, `tag_audio_events`, `timestamps_granularity`,
`language_code`, `keyterms`) and return the identical response shape, so the two
are drop-in swappable and a cached run of either re-renders with no API call.

Because it costs the same and takes the same options, the only sound way to pick
is to run both on a representative sample of the actual source and diff them.
The cache makes that cheap: two runs, then every format is a free re-render.

Keyterms and the medical model are **independent** levers and can be combined -
a keyterm set biases toward specific spellings (brand names, clinician surnames),
while the model choice affects the underlying acoustic and language modelling.

## Endpoint

```
POST https://api.elevenlabs.io/v1/speech-to-text
Header:  xi-api-key: <key>
Body:    multipart/form-data
```

Fields this skill sends (`transcribe.py`):

| Field | Value | Why |
|---|---|---|
| `model_id` | `scribe_v2` (default) or `scribe_v2_medical` | The batch STT model, set by `--model`. Recorded in the cache as `_model` so re-renders report the right engine. |
| `file` | the audio bytes | Demuxed mono 16 kHz MP3 (see below). |
| `diarize` | `true` (default) | Speaker separation → `speaker_0`, `speaker_1`, … |
| `tag_audio_events` | `true` | Inline `[laughs]`, `[applause]`, etc. |
| `timestamps_granularity` | `word` | Powers every timecode and subtitle cue. |
| `language_code` | omitted by default | Omitting = auto-detect. Pass `--language eng` to pin. |
| `keyterms` | repeated field | Bias terms, one form part each. See `keyterms.md`. |

`keyterms` is a JSON array in the SDK; over raw multipart it is sent as **repeated
`keyterms` parts** (`build_multipart` handles list values this way).

## Constraints (Scribe v2)

| Limit | Value |
|---|---|
| Max file size | 3 GB |
| Max audio duration | 10 hours |
| Languages | 90+ (auto-detected) |
| Speakers (diarization) | up to 32 |
| Keyterms | up to 1000, < 50 chars each, ≤ 5 words each |
| Forbidden keyterm chars | `< > { } [ ] \` |

## Audio preparation

The skill demuxes every input to **mono 16 kHz MP3** (`ffmpeg -vn -ac 1 -ar 16000
-b:a 64k`) before upload. Scribe resamples to 16 kHz internally, so this is
lossless for transcription quality while cutting a video-container upload ~20×.
Files over 8 minutes are chunked and transcribed concurrently server-side (2-4
way), so long files still return in reasonable time.

Input formats accepted: both audio and video. The skill walks these extensions in
batch mode: `.mp3 .wav .m4a .aac .flac .ogg .opus .webm .mp4 .mov .mkv .m4v .wmv
.avi`. A file with **no audio stream** fails loud (`NoAudioStreamError`) rather
than producing an empty transcript.

## Response shape

```json
{
  "language_code": "eng",
  "language_probability": 1.0,
  "text": "One of the problems ...",
  "audio_duration_secs": 49.997,
  "transcription_id": "...",
  "words": [
    {"text": "One", "start": 0.1, "end": 0.3, "type": "word", "speaker_id": "speaker_0"},
    {"text": " ",   "start": 0.3, "end": 0.32, "type": "spacing", "speaker_id": "speaker_0"},
    {"text": "[laughs]", "start": 4.6, "end": 4.7, "type": "audio_event", "speaker_id": "speaker_1"}
  ]
}
```

`type` is `word`, `spacing`, or `audio_event`. Per-word `logprob` is present and
ignored by the renderers. This raw JSON is cached to disk as `<name>.json` and is
the single source every other format re-renders from - the API is never called
twice for the same file.

## Billing

Scribe is **subscription / credit billed per second of audio**. The plugin does
**not** hardcode a per-minute price (the pinned docs only link out to the pricing
page, which varies by tier). `/create-transcript cost` reports audio-minutes for
planning; the registry entry and cost tracker record the model as
`mode: subscription, rate: null`.

Two documented cost modifiers apply when keyterms are used:

- **+20% surcharge** on the base transcription cost whenever `keyterms` is sent.
- **20-second minimum billable duration** per request when **more than 100**
  keyterms are supplied.

The skill surfaces both notes at run time when keyterms are active, so a large
standing keyterm list on a batch of very short clips is a visible decision, not a
silent cost.
