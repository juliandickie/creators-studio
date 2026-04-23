# Google VEO 3.1 (canonical model IDs: `veo-3.1-lite` / `veo-3.1-fast` / `veo-3.1`)

**Status:** Registered and reachable via Replicate as of v4.2.1. NOT the default — Kling v3 remains the video family default per the v3.8.0 spike 5 quality verdict. VEO is opt-in backup via `--provider replicate --model veo-3.1-{lite,fast,}`. A post-sub-project-C bake-off will re-evaluate the Kling-vs-VEO default in light of v4.2.1's corrected Kling pricing.

**Hosting providers:** Replicate (all three tiers). Vertex AI retired in v4.2.1.

## Three tiers at a glance

| Tier | Canonical ID | Replicate slug | Cost (8s @ 1080p + audio) | Unique capabilities |
|---|---|---|---|---|
| Lite | `veo-3.1-lite` | `google/veo-3.1-lite` | $0.64 | Cheapest; audio always on |
| Fast | `veo-3.1-fast` | `google/veo-3.1-fast` | $1.20 | Audio toggle; up to 3 reference images |
| Standard | `veo-3.1` | `google/veo-3.1` | $3.20 | 4K output; video extension; highest fidelity |

## Canonical constraints (enforced pre-HTTP)

All three tiers:
- `duration_s` ∈ {4, 6, 8} — enum, not range
- `aspect_ratio` ∈ {`16:9`, `9:16`} — no 1:1 support
- `resolution` ∈ {`720p`, `1080p`} for Lite/Fast; Standard adds `4K`

**Lite-specific conditional:** `resolution=1080p` requires `duration_s=8`. NOT machine-enforced by `_canonical.py` in v4.2.1 — Replicate's server-side rejection is the safety net. Documented in the registry entry's `canonical_constraints.conditional` field.

## Pricing breakdown

**VEO 3.1 Lite** — `per_second_by_resolution` mode:
- 720p: $0.05/s
- 1080p: $0.08/s (requires 8s duration)
- Audio is always on — no without-audio variant

**VEO 3.1 Fast** — `per_second_by_audio` mode:
- With audio: $0.15/s
- Without audio: $0.10/s

**VEO 3.1 Standard** — `per_second_by_audio` mode:
- With audio: $0.40/s
- Without audio: $0.20/s

## Capabilities per tier

**Lite:** text-to-video, image-to-video, 4/6/8 second durations, audio always on, 720p or 1080p. No reference images. No video extension.

**Fast:** text-to-video, image-to-video, 4/6/8 second durations, audio toggle, 720p or 1080p, up to 3 reference images for character/style consistency, frame-to-frame generation (start + end frames).

**Standard:** everything Fast does, plus 4K output and video extension (build longer narratives by chaining clips where the next one continues from the previous).

## Cost comparison (8s @ 1080p with audio)

| Model | Cost |
|---|---|
| **VEO 3.1 Lite** | **$0.64** (cheapest option at 1080p) |
| VEO 3.1 Fast | $1.20 |
| Kling v3 pro-audio | $2.69 |
| VEO 3.1 Standard | $3.20 (most expensive) |

The v3.8.0 narrative of "Kling is 7.5× cheaper than VEO" was based on an incorrect Kling price point; at the verified v4.2.1 rates, **VEO Lite is actually ~4× cheaper than Kling at comparable settings**. Queued for re-evaluation in a post-sub-project-C bake-off.

## Prompting tips (from Google dev-docs)

- Be specific: camera angles, lighting, mood, audio cues
- For image-to-video: describe the motion you want, not just what's in the image
- Audio cues in quotation marks render as dialogue; unquoted descriptions become ambient
- Reference images (Fast/Standard): clear, well-lit, subject-from-desired-angle

## Authoritative sources

- `dev-docs/google-veo-3.1-lite-llms.md`
- `dev-docs/google-veo-3.1-fast-llms.md`
- `dev-docs/google-veo-3.1-llms.md`
- Google Gemini API: https://ai.google.dev/gemini-api/docs
