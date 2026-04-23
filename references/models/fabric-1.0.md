# VEED Fabric 1.0 (canonical model ID: `fabric-1.0`)

**Hosting providers:** Replicate (`veed/fabric-1.0`).

**Registry entry:** `scripts/registry/models.json` → `models.fabric-1.0`

## What it does

Audio-driven lip-sync. Input: one image + one audio file. Output: the image's face lip-synced to the audio. Mouth region ONLY — no body animation, no camera movement, no emotional direction beyond audio prosody.

## Why the plugin has it

Closes the gap where Kling doesn't accept external audio input — custom-designed ElevenLabs voices from `audio_pipeline.py narrate` had no way to reach a visible character's face. Fabric pairs the two.

## Canonical constraints

- `resolution` ∈ {`480p`, `720p`} (no 1080p or 4K)
- `duration_s` ≤ 60 (driven by audio length)
- `image` formats: jpg, jpeg, png
- `audio` formats: mp3, wav, m4a, aac

## Pricing

`per_second` mode, ~$0.15 per second of output video. Cold-start adds ~36s wall time but NOT cost (Replicate bills on output duration, not GPU wall time).

- 7s clip: ~$1.05
- 8s clip: ~$1.20
- 60s clip (max): ~$9.00

**Note:** Fabric is ~2.5× more expensive per second than Kling v3 ($0.02/s) and ~2.5× more expensive per clip than VEO Lite ($0.40/8s). Still the only path to pair a custom-designed ElevenLabs voice with a visible face.

## Canonical 2-step workflow

```
audio_pipeline.py narrate --voice brand_voice --out /tmp/narr.mp3
  → video_lipsync.py --image face.png --audio /tmp/narr.mp3
```

## Empirical verification

Three successful runs on 2026-04-15 (Replicate prediction IDs):
- `w36styf3c9rmw0cxj3cbyvnxz8` — 8s @ 720p, $1.20, cold start
- `j3qp5ndaanrmr0cxj4qrnrhhf4` — 7s @ 720p, $1.05, warm
- `55qej5ghs1rmw0cxj4wr1wjgdg` — 7s @ 720p, $1.05, warm

## Authoritative source

`dev-docs/veed-fabric-1.0-llms.md`
