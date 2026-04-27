# Video Sequence Production Reference

> Load this when the user wants to create a multi-shot video sequence
> (15s, 30s, 60s+) or runs `/create-video sequence`.

## Overview

VEO generates max 8 seconds per clip. Longer productions require a **shot list** approach: break the script into individual shots, generate storyboard frame pairs for approval, then batch-generate video clips and stitch them together.

This Gemini + VEO workflow (Gemini for still storyboard frames → VEO for
clip interpolation) is Google's officially recommended pattern for
multi-shot production, not just our opinion. It both lets you catch
composition problems at image cost before committing to video cost, and
locks in per-shot continuity via first/last frame keyframing.

## Draft-then-Final Workflow (v3.6.0+)

```
Plan → Storyboard → Generate (draft) → Review → Generate (final) → Stitch
```

With three VEO tiers reachable through the v3.6.0 Vertex AI backend
(Lite, Fast, Standard), the cheapest validated path is to run the whole
sequence at **Lite draft** quality first, review the motion and
continuity, then re-run the approved shots at **Standard** for delivery.

```bash
# 1. First pass: draft at Lite ($0.05/sec, 8× cheaper than Standard)
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py generate \
    --storyboard ~/storyboard --quality-tier draft

# 2. Review the MP4s. Approve, tweak prompts, or regenerate.

# 3. Final pass: Standard for delivery
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py generate \
    --storyboard ~/storyboard --quality-tier standard
```

`--quality-tier draft` maps to `veo-3.1-lite-generate-001` (the alias
`--quality-tier lite` is also accepted). The Vertex AI backend
auto-routes Lite — no extra flag needed if you have Vertex credentials
in `~/.creators-studio/config.json` (see `veo-models.md` → Backend Availability
for the 3-minute setup).

### Cost Comparison (4 shots × 8 s, 30-second sequence)

| Mode | Draft pass | Final pass | Total |
|---|---|---|---|
| Blind at Standard | — | $12.80 | $12.80 |
| Blind at Fast | — | $4.80 | $4.80 |
| Blind at Lite | — | $1.60 | $1.60 |
| **Lite draft + Fast final** | **$1.60** | **$4.80** | **$6.40** |
| **Lite draft + Standard final** | **$1.60** | **$12.80** | **$14.40** |

A Lite draft pass adds **just $1.60** to a $12.80 Standard final. In
practice, blind generation at Standard typically needs 1–2 regenerations
per shot because the user cannot preview motion before committing. One
regeneration of a single 8 s Standard shot ($3.20) already exceeds the
$1.60 draft-pass protection. **Draft-then-final pays for itself the
first time it prevents a regeneration on any shot at Standard tier** —
and it usually prevents several.

## Timestamp Prompting: Pack Multiple Shots per Clip

VEO 3.1 supports a timestamp syntax within a single prompt that directs
multi-shot sequences inside one 8-second generation. A 30-second sequence
that would otherwise need 4 clips can sometimes be compressed to 2
clips with 4 sub-shots each, cutting VEO cost by ~50%. See the
timestamp-prompting section in `video-prompt-engineering.md` for syntax
and caveats.

## Character Drift Mitigation

VEO treats each prompt as a fresh generation with no persistent
character memory. Between clips, faces, clothing, and hairstyle can
subtly or dramatically shift. The consistency rules below (identity
lock, wardrobe lock, reference images) are **mitigations, not
solutions** — see the Known Limitations section of `veo-models.md`.

## The 5-Stage Pipeline

`plan → storyboard → review → generate → stitch`

v3.6.2 promoted "review" from an implicit human step to a first-class
pipeline stage with its own subcommand. The stage order matches the
cost gradient: each stage gets more expensive, so the approval gate
lives at the last cheap moment before committing to VEO spend.

### Stage 1: Shot List (Free)

Claude breaks the user's script/concept into individual shots:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py plan --script "30-second product launch ad" --target 30
```

Each shot specifies: number, duration, camera, subject, action, setting, audio, consistency anchors, and prompts for start/end frame generation. Shots that should let VEO pick their own ending (e.g. establishing shots that cut away) can set `"use_veo_interpolation": true` — the storyboard stage will skip generating an end frame for those shots and the generate stage will drop `--last-frame` from the VEO call.

**v3.6.3 — shot-type semantic defaults.** Pass `--shot-types` as a comma-separated list to pre-fill each shot's duration, camera hint, and `use_veo_interpolation` flag from a built-in defaults table:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py plan \
    --script "30-second product launch ad" \
    --target 30 \
    --shot-types establishing,medium,closeup,product
```

The eight supported shot types with their defaults:

| Type | Default duration | Default camera hint | `use_veo_interpolation` |
|---|---:|---|---|
| `establishing` | 8 s | slow dolly forward or wide aerial reveal | **true** (cuts away) |
| `content` | 8 s | static medium shot or subtle handheld | false |
| `medium` | 6 s | static medium shot with gentle rack focus | false |
| `closeup` | 6 s | tight close-up, shallow depth of field | false |
| `product` | 8 s | slow orbit or push-in with macro framing | false |
| `transition` | 4 s | whip pan, match cut, or light flare | **true** (bridges shots) |
| `cutaway` | 4 s | brief detail insert, static or slow push | **true** (independent) |
| `broll` | 6 s | handheld or drifting observational | **true** (independent) |

When `--shot-types` is provided, the shot count is determined by the list length and durations are rescaled to hit `--target` exactly. Claude can override any field in plan.json after generation — the defaults are a starting point, not a constraint.

### Stage 2: Storyboard (Cheap — image cost only)

Generate start/end frame image pairs for visual approval:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py storyboard --plan shot-list.json
```

Uses `/create-image`'s `generate.py` (cross-skill) to produce still frames at ~$0.08 each. User reviews the visual storyboard and approves or requests changes before committing to video.

**v3.6.2 partial regeneration:** use `--shots 1,3-5` to regenerate only a subset of frames when one shot needs iteration but the rest are approved.
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py storyboard \
    --plan shot-list.json --shots 3
# Only regenerates shot 3's start and (optionally) end frames.
```

**Cost:** N shots × 2 frames × $0.078 ≈ $0.80 for 5 shots. Shots with `use_veo_interpolation=true` only need the start frame, saving $0.08 each.

### Stage 3: Review (Free — the approval gate, mandatory in v3.6.3+)

`video_sequence.py review` generates a `REVIEW-SHEET.md` interleaving
each shot's frames, VEO prompt, cost estimate, and parameters into a
single markdown file:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py review \
    --plan shot-list.json \
    --storyboard ~/sequences/my-project/storyboard \
    --quality-tier draft
```

The review sheet is written to `<storyboard>/REVIEW-SHEET.md` by default. Open it in Quick Look (Space key in Finder) or any markdown preview to see the full sequence at a glance: each shot block shows the start (and end, if not interpolating) frame inline, the full VEO prompt, the resolved model and cost for the selected `--quality-tier`, and a ✅/⚠️ status badge indicating whether the shot is ready to generate. The footer shows sequence totals and lists any gaps that would block `generate`.

This is a pure markdown artifact — no VEO calls, no Gemini calls, no cost. It's regenerated on demand so you can review, tweak the plan, and re-run as many times as you want before committing to VEO spend.

**v3.6.3 — mandatory gate with plan hash tracking.** `generate` now refuses to run unless a valid `REVIEW-SHEET.md` exists in the storyboard directory AND its embedded frame hashes match the current storyboard state. The review sheet contains a machine-readable manifest block (wrapped in HTML comments so it doesn't render in markdown previews) with the SHA-256 of each frame at the time the review was written. When `generate` runs, it recomputes the hashes and compares — any drift means someone regenerated a frame after the review was approved, and the pipeline aborts with a clear "stale review — regenerate with `review` then retry" message listing the drifted shot numbers.

**Bypass for automation**: pass `--skip-review` to `generate`. This disables the safety net entirely, intended for CI paths that know what they're doing. Don't use it interactively — the gate exists specifically to catch the most expensive category of mistake (generating a $12 Standard clip against a frame that was silently regenerated after review).

### Stage 4: Video Generation (Expensive — VEO cost)

Generate video clips from approved storyboard frames:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py generate --storyboard ~/storyboard/ --quality-tier draft
```

Each shot uses its start frame as `--first-frame`. If `use_veo_interpolation` is not set on the shot, the end frame is also passed as `--last-frame` for frame-perfect continuity. Use `--quality-tier draft` for the Lite-tier first pass; re-run with `--quality-tier standard` after reviewing the draft.

**v3.6.3 mandatory review gate**: `generate` checks for a valid `REVIEW-SHEET.md` with matching frame hashes before doing any work. Missing, unparseable, or stale reviews abort with a clear error. Use `--skip-review` to bypass for automation.

**Cost (at Lite draft):** N shots × $0.40 = ~$1.60 for 4 shots of 8s each. At Standard: ~$12.80.

### Stage 5: Stitch (Assembly)

Concatenate clips into final sequence:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py stitch --clips ~/clips/ --output final.mp4
```

## First/Last Frame Chaining

The key to seamless sequences: the end frame of shot N becomes the start frame of shot N+1.

```
Shot 1: start_A → (VEO) → clip ending at frame B
Shot 2: frame B → (VEO) → clip ending at frame C
Shot 3: frame C → (VEO) → clip ending at frame D
```

The storyboard stage generates these frame pairs using Gemini image generation (cheap), then the video stage interpolates motion between them (expensive but guided).

## Target Durations

| Target | Shots | Structure | Est. Cost |
|--------|-------|-----------|-----------|
| **15s** | 2-3 | Establish → Action → Close | $3-5 |
| **30s** | 4-5 | Establish → Problem → Solution → Product → CTA | $6-9 |
| **60s** | 8-10 | Full narrative arc with B-roll | $12-16 |
| **90s** | 12-15 | Tutorial with cutaways | $18-24 |

Costs include storyboard frames + video clips. Actual cost depends on resolution and model tier.

## Consistency Rules

1. **Identity lock** — Repeat character descriptions verbatim in every shot prompt
2. **Wardrobe lock** — Never vary clothing between shots
3. **Lighting lock** — Same lighting setup described in every prompt
4. **Setting lock** — Identical environment description when shots share a location
5. **Grade lock** — Same color grade (e.g., "teal-and-magenta") in every prompt
6. **Reference images** — Use asset registry references in every shot (up to 3)

## Shot List JSON Format

```json
{
  "script": "30-second product launch ad for wireless earbuds",
  "target_duration": 30,
  "preset": "tech-saas",
  "shots": [
    {
      "number": 1,
      "duration": 8,
      "type": "establishing",
      "camera": "Slow dolly forward through glass door",
      "subject": "Modern tech showroom, minimalist white shelves",
      "action": "Camera reveals the product display",
      "setting": "Clean tech retail space, morning light",
      "audio": "Ambient: soft electronic hum, SFX: glass door sliding",
      "prompt": "Full VEO prompt here...",
      "start_frame_prompt": "Banana prompt for start frame...",
      "end_frame_prompt": "Banana prompt for end frame...",
      "consistency_notes": "Same showroom lighting throughout"
    }
  ]
}
```

## Cost Estimation

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py estimate --plan shot-list.json
```

Shows breakdown: storyboard cost + video cost + total before any generation begins.
