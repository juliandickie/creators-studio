# Video Sequence Production Reference

> Load this when the user wants to create a multi-shot video sequence
> (15s, 30s, 60s+) or runs `/video sequence`.

## Overview

VEO generates max 8 seconds per clip. Longer productions require a **shot list** approach: break the script into individual shots, generate storyboard frame pairs for approval, then batch-generate video clips and stitch them together.

## The 4-Stage Pipeline

### Stage 1: Shot List (Free)

Claude breaks the user's script/concept into individual shots:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py plan --script "30-second product launch ad" --target 30
```

Each shot specifies: number, duration, camera, subject, action, setting, audio, consistency anchors, and prompts for start/end frame generation.

### Stage 2: Storyboard (Cheap — image cost only)

Generate start/end frame image pairs for visual approval:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py storyboard --plan shot-list.json
```

Uses `/banana`'s `generate.py` (cross-skill) to produce still frames at ~$0.08 each. User reviews the visual storyboard and approves or requests changes before committing to video.

**Cost:** N shots x 2 frames x $0.078 = ~$0.80 for 5 shots

### Stage 3: Video Generation (Expensive — VEO cost)

Generate video clips from approved storyboard frames:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_sequence.py generate --storyboard ~/storyboard/
```

Each shot uses its start frame as `--first-frame` and end frame as `--last-frame` for VEO, ensuring frame-perfect continuity between shots.

**Cost:** N shots x $1.20 = ~$6.00 for 5 shots

### Stage 4: Assembly

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
