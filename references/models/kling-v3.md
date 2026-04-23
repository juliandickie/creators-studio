# Kling Video 3.0 (canonical model ID: `kling-v3`)

**Hosting providers:** Replicate (`kwaivgi/kling-v3-video`). Kie.ai support deferred to sub-project C.

**Registry entry:** `scripts/registry/models.json` → `models.kling-v3`

## Capabilities

- Text-to-video (3–15s clips)
- Image-to-video via `start_image` (first-frame reference)
- `end_image` for interpolation (requires `start_image`)
- Native audio generation (English + Chinese; other languages unverified)
- Multi-shot via `multi_prompt` JSON array (max 6 shots per call, via `provider_opts`)
- Negative prompts

## Canonical constraints (enforced pre-HTTP by `_canonical.py`)

- `aspect_ratio` ∈ {`16:9`, `9:16`, `1:1`}
- `duration_s` integer in [3, 15]
- `resolution` ∈ {`720p`, `1080p`} (mapped to Kling `mode: standard | pro` inside the backend)
- `prompt` and `negative_prompt` max 2500 chars

## Pricing (via Replicate)

`per_second` mode, $0.02 / second of output.

- 8s clip at 1080p = $0.16
- 15s clip at 1080p = $0.30

## Character consistency via `start_image` (conditional identity lock)

Empirically verified session 19 (2026-04-16):

- When `start_image` AND prompt describe the SAME character (matching age, gender, hair, clothing, setting), Kling preserves character identity through the full clip at 1072×1928 pro mode.
- When the prompt describes a DIFFERENT character, Kling morphs completely toward the prompted character within 5 seconds — `start_image` only affects frame 0.
- **Prompt engineering is the critical variable for cross-clip character consistency.** Describe the character precisely in every shot's prompt when using `start_image`.
- Works for both human and non-human subjects (robot mascot confirmed in spike 5 Phase 2 test_11).

## Audio language limitation

Per the model card, audio generation works best in **English and Chinese only**. Other languages unverified. For non-English-or-Chinese workflows, generate with `provider_opts: {"generate_audio": false}` and use `audio_pipeline.py` for the audio bed.

## Multi-shot schema (via `provider_opts`)

`multi_prompt` is a JSON array STRING (not a list) passed via `provider_opts`. Max 6 shots per call. **Sum of shot durations MUST equal the top-level `duration_s` parameter.**

```python
canonical_params = {"prompt": "overall scene", "duration_s": 12, ...}
provider_opts = {
    "multi_prompt": json.dumps([
        {"prompt": "shot 1 description", "duration": 4},
        {"prompt": "shot 2 description", "duration": 4},
        {"prompt": "shot 3 description", "duration": 4},
    ])
}
```

## Known quirks

- `aspect_ratio` silently ignored when `start_image` is provided; output uses start image's native aspect.
- `end_image` requires `start_image`; standalone `end_image` is rejected.
- `start_image` max 10 MB; PNG / JPG / JPEG accepted (WebP intentionally excluded per the Kling model card).

## Authoritative source

`dev-docs/kwaivgi-kling-v3-video-llms.md` — model card from Replicate.
