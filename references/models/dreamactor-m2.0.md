# ByteDance DreamActor M2.0 (canonical model ID: `dreamactor-m2.0`)

**Hosting providers:** Replicate (`bytedance/dreamactor-m2.0`).

**Registry entry:** `scripts/registry/models.json` → `models.dreamactor-m2.0`

## What it does

Motion transfer / character animation. Input: one image + a driving video. Output: the image's subject animated with the driving video's motion, facial expressions, and lip movements. Works on humans, cartoons, animals, non-humans.

## Canonical constraints

- `duration_s` ≤ 30 (driven by driving video length)
- Output resolution up to 2048×1440 (model-side cap)

## Pricing

`per_second` mode, $0.05/s.

## When to use

- **For real-footage-to-avatar workflows** — mapping a generated character onto filmed human motion.

**Don't use DreamActor for cross-clip character consistency in text-to-video.** Kling v3 with `start_image` + matched prompts does this at higher resolution (1072×1928 vs 694×1242) and 2.5× lower cost ($0.02/s vs $0.05/s). Session 19 spike (2026-04-16) confirmed this.

## Authoritative source

`dev-docs/bytedance-dreamactor-m2.0-llms.md`
