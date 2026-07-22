# Image-to-Video Reference

> Load this when the user wants to animate a still image or convert
> a generated image into a video clip.

## Overview

Animate any still image by passing it as a first frame (and optionally a last frame) to VEO 3.1. The model generates realistic motion starting from the image, guided by your text prompt.

## Usage

### Animate a single image (first frame only)
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_generate.py \
    --prompt "slow orbit revealing the product, SFX: soft mechanical hum" \
    --first-frame ~/Documents/creators_generated/banana_20260409.png \
    --duration 8 --aspect-ratio 16:9
```

### Interpolate between two frames (first + last)
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_generate.py \
    --prompt "camera dollies forward through the doorway" \
    --first-frame start.png --last-frame end.png \
    --duration 8 --aspect-ratio 16:9
```

### With reference images for character consistency
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/video_generate.py \
    --prompt "the character turns to face the camera and smiles" \
    --first-frame scene.png \
    --reference-image ~/assets/character-front.jpg ~/assets/character-profile.jpg \
    --duration 6
```

## Cross-Skill Workflow: /create-image → /create-video

The primary workflow is generating a high-quality still with `/create-image`, then animating it with `/create-video`:

1. **Generate still:** `/create-image generate "product shot of wireless earbuds on dark surface"` → `banana_20260409.png`
2. **Animate:** `/create-video animate banana_20260409.png "slow orbit, product rotating, SFX: soft whoosh"`
3. **Result:** 8-second MP4 that starts from the exact composition of the still

This ensures:
- Image quality is controlled by Gemini (which excels at stills)
- Motion is controlled by VEO (which excels at animation)
- Composition and framing are locked by the input image

## Asset Registry Integration

If the user mentions a named asset, load its reference images:
```bash
python3 ${CLAUDE_SKILL_DIR}/../create-image/scripts/assets.py show CHARACTER_NAME
```

Pass the asset's `reference_images[]` as `--reference-image` arguments to video_generate.py. VEO supports up to 3 reference images per shot.

## Image Requirements

| Property | Requirement |
|----------|-------------|
| Format | PNG, JPEG, WebP |
| Min resolution | 720p (1280x720) |
| Max file size | 7 MB |
| Aspect ratio | Should match video aspect ratio (16:9 or 9:16) |

If the image ratio doesn't match the video ratio, VEO will crop/pad. For best results, generate the source image at the same ratio as the target video.

## First/Last Frame for Sequence Chaining

The end frame of shot N becomes the start frame of shot N+1:

```
Shot 1: start_A.png → (VEO) → end_B.mp4
Shot 2: [last frame of end_B.mp4] → (VEO) → end_C.mp4
```

To extract the last frame from a video for chaining:
```bash
ffmpeg -sseof -0.1 -i clip.mp4 -frames:v 1 -update 1 lastframe.png
```

Or use `/create-image generate` to create purpose-built end frames for each shot (higher quality than extracting from video).

## Tips

- **Motion description matters** - "slow orbit" gives smooth motion, "dynamic handheld" gives energy
- **Match lighting** - If the source image has warm lighting, describe warm lighting in the prompt
- **Keep it simple** - One motion per clip. Don't combine zoom + pan + subject movement
- **Audio enhances realism** - Always include SFX or ambient even for product animations
