# Fold video watching into creators-studio

2026-10-10. Intent, not yet scoped.

## Why

Julian wants fewer plugins and skills loaded. Today watching a video takes two plugins: the third-party watch plugin (bradautomates/claude-video, MIT) for frames, and create-transcript for the words. watch's own speech fallback needs a Groq, OpenAI or WhisperX setup, so on this machine it returns no transcript at all.

## Evidence from the first run

The clip was "Video by askmate_auto - 1080p.webm", 27 s, a single speaker.

- watch, local engine: 26 frames, no transcript. The burned-in captions it showed left out "about vehicles" and "we wanna combine the two", and the final frame cut off mid-caption. I misread both as flaws in the video.
- create-transcript (Scribe v2, keyterm M.A.T.E.): complete, accurate text in one call.

## Shape to consider

- Either a `/create-transcript --frames` flag, or a small sibling skill that reuses transcribe.py's ffmpeg probe and Scribe cache.
- What to take from watch: yt-dlp download, caption-first, scene/keyframe sampling with a cap, 16x16 near-duplicate dedup, timestamped frame list, `--start/--end`, `--timestamps` cue frames.
- Keep the MIT attribution if any watch code is copied.
- After it ships, remove watch from the outfit marketplace and drop the standing rule in ~/.claude/CLAUDE.md that pairs /watch with /create-transcript.
