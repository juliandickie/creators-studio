# PixVerse V6 (canonical model ID: `pixverse-v6`)

**Hosting providers:** Replicate (`pixverse/pixverse-v6`).

**Registry entry:** `scripts/registry/models.json` → `models.pixverse-v6`

## What it does

PixVerse V6 is a flagship text-to-video model from PixVerse with three modes:

- **Text-to-video** — `prompt` + `aspect_ratio`
- **Image-to-video** — `prompt` + `image` (first frame)
- **Transition (first/last frame)** — `prompt` + `image` (first) + `last_frame_image` (last)

Up to 15 seconds of 1080p output with synchronized audio. Per the PixVerse readme, it ranks among the top video models globally alongside Seedance 2.0.

## Why the plugin has it

A general-purpose competitor to Kling v3 and VEO 3.1. Specific differentiators:

- **Native multilingual text-in-video** — sharp typography in English, Chinese, and other languages with high-precision positioning. Kling and VEO can render text but treat it as imagery; PixVerse treats it as a first-class capability.
- **4-tier resolution pricing** — 360p / 540p / 720p / 1080p. Most granular tier set in the video roster, so the 360p draft mode is `$0.05`/s without audio (cheaper than VEO Lite's 720p at `$0.05`/s and competitive with Kling Std).
- **Multi-shot via boolean toggle** — `generate_multi_clip_switch: true` with a single prompt structured as `"Shot 1, ..., Shot 2, ..., Shot 3, ..."`. Simpler authoring than Kling v3's `multi_prompt` JSON array; less precise control over per-shot duration.
- **First-person POV** — high-speed motion from immersive first-person perspectives.

## Canonical constraints

- `aspect_ratio` ∈ {`16:9`, `9:16`}
- `duration_s` integer in [1, 15] (billed per second)
- `resolution` ∈ {`360p`, `540p`, `720p`, `1080p`}
- `image` (first frame): jpg, jpeg, png (URL or data URI)
- `last_frame_image`: same formats; **requires `image`** to be present
- `aspect_ratio` is **ignored** when `image` is provided (output uses image's native aspect)
- `generate_multi_clip_switch` is **NOT available in transition mode** (i.e., when `last_frame_image` is set)

## Pricing

`per_second_by_resolution_and_audio` mode — same shape as Kling v3.

| Resolution | No audio | With audio |
|---|---|---|
| **360p** | `$0.05`/s | `$0.07`/s |
| **540p** | `$0.07`/s | `$0.09`/s |
| **720p** | `$0.09`/s | `$0.12`/s |
| **1080p** | `$0.18`/s | `$0.23`/s |

**Worked examples** (from PixVerse readme):
- 5s @ 720p with audio = `$0.60`
- 10s @ 1080p without audio = `$1.80`
- 15s @ 1080p with audio (max) = `$3.45`
- 15s @ 360p without audio (cheapest 15s) = `$0.75`

**Source:** PixVerse readme block at the bottom of `dev-docs/pixverse-pixverse-v6-llms.md` (last verified 2026-04-27). Re-fetch on every PixVerse pricing review — Replicate occasionally adjusts model rates.

## Comparisons

For an 8s clip with audio at 1080p (a typical "ship-quality social asset"):

| Model | Cost | Notes |
|---|---|---|
| **Kling v3 Std** (default) | $2.69 | Pro mode 1080p with audio. Multi-shot via `multi_prompt` JSON array. |
| **PixVerse V6** | $1.84 | Cheaper than Kling at 1080p with audio. Multi-shot via boolean toggle + structured prompt. |
| **VEO 3.1 Standard** | $3.20 | Premium VEO. Most expensive in roster. |
| **VEO 3.1 Lite** | $0.40 | Cheapest at 1080p. Single-shot only — extended workflows produce glitches per spike 5. |
| **VEO 3.1 Fast** | $1.20 | Mid-tier VEO. |

PixVerse V6 sits between Kling Std and VEO Standard on price at 1080p with audio. Whether it ranks similarly on quality awaits an empirical bake-off (see "Follow-ups" below).

## Backend wiring status

**Registry-only as of 2026-04-27** — Pixverse v6 is registered in `scripts/registry/models.json` and `cost_tracker.py` PRICING dict so cost-logging works the moment runtime wiring lands, but the canonical-param-to-Pixverse-field translation in `scripts/backends/_replicate.py` is **not yet implemented**. Calling `/create-video generate --model pixverse-v6` today will error.

The same pattern was used for `elevenlabs-music` per the v4.2.1 multi-model principle: register the alternative so "make it the new default" is a registry-entry change, not a code change.

To wire it up, a future change would need:
- Canonical → Pixverse field translation: `start_image → image`, `end_image → last_frame_image`, `resolution → quality`, `audio_enabled → generate_audio_switch`, plus a Pixverse-specific `multi_shot` flag → `generate_multi_clip_switch` mapping.
- `validate_pixverse_params()` helper in `_replicate.py` matching the constraints above.
- Optional registration as a v3.x quality-tier alternative in `video_sequence.py`.

## Follow-ups (queued)

- **Empirical bake-off vs Kling v3 Std and VEO 3.1 Standard**, focused on:
  - Multi-shot prompt-following (the key differentiator vs single-shot models)
  - Native text-in-video legibility (Chinese, English, mixed)
  - Character emotion + physics realism on shared shot types
  - Cost-per-quality at 720p (the most-shipped tier)
- **Verify aspect_ratio support beyond 16:9 / 9:16** — examples in the model card use only those two; 1:1 / 4:3 / others may or may not be accepted by the API.
- **Verify duration upper bound of 15s** — mentioned as "up to 15 seconds of 1080p" in the readme; lower resolutions may allow longer.

## Authoritative source

`dev-docs/pixverse-pixverse-v6-llms.md` (full model card) plus the live model page at https://replicate.com/pixverse/pixverse-v6 (re-fetch on every PixVerse capability or pricing review).
