# No speech-to-text capability - 2026-07-23

> **RESOLVED in v4.3.0.** Item 1 (the capability gap) is closed by the new
> `/create-transcript` skill (`skills/create-transcript/`), which adds ElevenLabs
> Scribe v2 speech-to-text. Item 2 (multipart helper) was implemented as
> `_http_post_multipart` in `transcribe.py`. Item 3 (demux video inputs) is done
> in `extract_audio`. Kept for the record. Spec:
> `docs/superpowers/specs/2026-07-23-create-transcript-skill-design.md`.

Captured while trying to run three downloaded .webm clips through ElevenLabs Scribe v2 "via the creators-studio plugin". The job was completed, but entirely outside the plugin, because the capability does not exist in it. Same observation / priority / suggested fix shape as the 2026-06-05 note.

---

## 1. The plugin has no transcription path at all (P2)

Observation. creators-studio v4.2.3 ships two skills, create-image and create-video. The ElevenLabs integration in skills/create-video/scripts/audio_pipeline.py is outbound audio only - generate_narration() for TTS and generate_music_elevenlabs() for music. There is no speech-to-text function, no scribe entry in scripts/registry/models.json, and no reference doc under references/models/ for any Scribe model. references/models/elevenlabs-music.md is the only ElevenLabs model doc.

Why it matters. The plugin is the natural place to reach for anything ElevenLabs, it already holds the account key, and dev-docs/elevenlabs-llms-full.txt in the parent project folder documents Scribe v2 in detail (models table around line 297, capability section around line 2280). The docs are already sitting in the project but nothing consumes them. A user reasonably assumes the plugin covers ElevenLabs end to end and discovers otherwise only by reading audio_pipeline.py.

Suggested fix. Either add a transcribe entry point (a stt_transcribe.py alongside audio_pipeline.py calling POST /v1/speech-to-text, reusing the existing _get_elevenlabs_key() and _http_* helpers, which already do everything needed except multipart upload), or state the boundary in one line in README.md and CLAUDE.md - "creators-studio generates audio, it does not transcribe it, use Descript for transcripts".

---

## 2. _http_post_json cannot do multipart, so file upload has to be hand-rolled (P3)

Observation. The HTTP helpers in audio_pipeline.py (_http_post_json, _http_get_json, _http_error_message) are JSON-body only. Speech-to-text is a multipart/form-data upload, so any STT addition needs a new helper rather than reusing the existing ones. Everything else is reusable as-is - key resolution, error message formatting, the ELEVENLABS_API base constant.

Why it matters. It is the only real work in adding item 1, worth knowing up front so the change is not mis-scoped as trivial wiring.

Suggested fix. Add a _http_post_multipart(url, fields, files, api_key) next to the existing helpers. Roughly 20 lines with urllib, no new dependency.

---

## 3. Vorbis-in-WebM inputs are worth demuxing before upload (P3)

Observation. Not a defect, a workflow note. The source files here were VP9 video with Vorbis audio, about 26 MB across three clips totalling four minutes. Piping them straight to the API would have uploaded the full video payload for a model that only consumes audio. An ffmpeg demux to mono 16 kHz MP3 (-vn -ac 1 -ar 16000 -b:a 64k) cut it to 1.9 MB with no transcription-quality cost, since Scribe resamples to 16 kHz internally. Billing is per second of audio either way, so the saving is upload time, not credits.

Suggested fix. If item 1 gets built, demux any video input to mono 16 kHz audio before upload rather than posting the container as-is. ffmpeg is already a dependency, _check_ffmpeg() exists in audio_pipeline.py.

---

## Verified behaviour, for whoever builds this

POST https://api.elevenlabs.io/v1/speech-to-text, header xi-api-key, multipart fields file, model_id=scribe_v2, diarize=true, tag_audio_events=true, timestamps_granularity=word, language_code=eng. All three clips returned HTTP 200. Diarization correctly split a two-person interview into speaker_0 and speaker_1, and audio events came back inline as [laughs] and [chuckles] entries with type audio_event in the words array. Response shape is language_code, language_probability, text, and a flat words array of {text, start, end, type, speaker_id} where type is word, spacing, or audio_event.
