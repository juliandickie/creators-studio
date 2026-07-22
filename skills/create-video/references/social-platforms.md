# Social Media Video Platform Specifications (v4.1.2+)

Reference for generating platform-native videos with correct dimensions, aspect ratios, and duration bounds. Covers **37 video placements across 14 platforms** at SOP max-quality upload specs.

> **Status**: This is a **data-only reference** in v4.1.2. The `/create-video social` command that consumes this table is scheduled for **v4.2.0** and will use Kling v3 Std (default) or VEO 3.1 (backup) to generate platform-native videos. For now, this doc serves as the spec catalogue that v4.2.0's CLI will read.
>
> **Authoritative source**: [`dev-docs/SOP Graphic Sizes - Social Media Image and Video Specifications Guide.md`](../../../../dev-docs/SOP%20Graphic%20Sizes%20-%20Social%20Media%20Image%20and%20Video%20Specifications%20Guide.md) (January 2026 update). BlueSky specs are best-guess; Signal and ManyChat do not have native video placements.
>
> **Companion doc for images**: [`../../create-image/references/social-platforms.md`](../../create-image/references/social-platforms.md) covers the image specs for the same 16 platforms (87 image placements).

## How durations are expressed

Every video placement lists `duration_min_s` and `duration_max_s` in seconds. "0.5" means half-second minimum; "14400" means 4 hours (Facebook feed max). When a platform distinguishes *optimal* from *maximum* duration, we list the max in `duration_max_s` and note the optimal range in the comment column.

## Generation model routing (v4.2.0+)

The `/create-video social` command will dispatch by duration + aspect ratio:

| Target duration | Target aspect | Model |
|---|---|---|
| ≤ 15s, most ratios | 16:9, 9:16, 1:1 | Kling v3 Std (default, $0.02/s) |
| > 15s (stitched) | Any | Kling v3 Std with `video_sequence.py` multi-shot pipeline |
| Lip-sync needed | Any | Fabric 1.0 (`/create-video lipsync` manually) |
| Explicit VEO preference | Any | VEO 3.1 via `--provider veo` |

---

## Instagram (4 video placements)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `ig-feed-video` | Feed Video Portrait | 1080×1350 | 4:5 | 3-3600 | Preferred feed format. Up to 60 min. H.264 codec. |
| `ig-story-video` | Story Video | 1080×1920 | 9:16 | 1-60 | Per clip. Splits longer content into multiple 60s clips. |
| `ig-reel-video` | Reel Video | 1080×1920 | 9:16 | 1-180 | Up to 3 minutes (extended Jan 2025). |
| `ig-reel-ad-video` | Reel Ad Video | 1080×1920 | 9:16 | 1-60 | Paid placement. No licensed music. |

## Facebook (4 video placements)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `fb-feed-video` | Feed Video | 1080×1080 | 1:1 | 1-14400 | Up to 4 hours. 1080p+ recommended. H.264 / AAC 128kbps+. |
| `fb-story-video` | Story Video | 1080×1920 | 9:16 | 1-120 | Up to 2 min (splits into 20-sec cards). |
| `fb-reel-video` | Reel Video | 1080×1920 | 9:16 | 1-90 | Safe zones top 14%, bottom 35%, sides 6%. |
| `fb-ad-video` | Feed Ad Video | 1080×1080 | 1:1 | 1-14400 | Inherits feed spec. 241 min max. |

## YouTube (6 video placements)

YouTube supports the widest range - 240p to 8K, durations from 6s bumpers to 12-hour verified uploads.

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `yt-long-video` | Long-form Video | 1920×1080 | 16:9 | 1-43200 | Up to 12h verified. 240p-8K supported. 8 Mbps @ 30fps, 12 Mbps @ 60fps. |
| `yt-shorts-video` | Shorts Video | 1080×1920 | 9:16 | 1-180 | Up to 3 minutes (extended Oct 2024). |
| `yt-shorts-ad` | Shorts Ad | 1080×1920 | 9:16 | 6-60 | 9:16 required for Shorts shelf. |
| `yt-skippable-instream` | Skippable In-Stream Ad | 1920×1080 | 16:9 | 12-600 | Skippable after 5s. |
| `yt-non-skippable` | Non-Skippable In-Stream Ad | 1920×1080 | 16:9 | 15-20 | Max 20s. |
| `yt-bumper` | Bumper Ad | 1920×1080 | 16:9 | 1-6 | Non-skippable, 6s max. |

## LinkedIn (2 video placements)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `li-feed-video` | Feed Video | 1920×1080 | 16:9 | 3-600 | 10 min max. 30 fps. Max 5GB. |
| `li-video-ad` | Video Ad | 1920×1080 | 16:9 | 3-1800 | 30 min max. Max 500MB. |

## Twitter/X (3 video placements)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `x-feed-video` | Feed Video | 1280×720 | 16:9 | 0.5-14400 | 2m20s free, up to 4h Premium. Max 512MB free / 8-16GB Premium. |
| `x-video-ad` | Video Ad | 1920×1080 | 16:9 | 0.5-140 | 15s recommended. Max 140s. ≤1GB. |
| `x-amplify-preroll` | Amplify Pre-roll | 1200×1200 | 1:1 | 0.5-6 | 6 seconds or less recommended. |

## TikTok (4 video placements)

Vertical-first; 9:16 content gets algorithmic preference across all placements.

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `tt-feed-video` | Feed Video | 1080×1920 | 9:16 | 3-3600 | 60 min uploaded / 10 min in-app. Avoid top+bottom 120px. 30 fps (60 for action). H.264/H.265. |
| `tt-story-video` | Story Video | 1080×1920 | 9:16 | 1-15 | Expires after 24 hours. |
| `tt-in-feed-ad` | In-Feed Ad | 1080×1920 | 9:16 | 5-60 | 9-15s optimal. Min 720×1280; recommended 1080×1920+. |
| `tt-topview-ad` | TopView Ad | 1080×1920 | 9:16 | 5-60 | 9-15s recommended. Bitrate ≥ 2,500 kbps. |

## Pinterest (1 video placement)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `pin-video` | Video Pin / Idea Pin | 1080×1920 | 9:16 | 1-60 | Also supports 1:1; vertical gets more grid space. |

## Threads (1 video placement)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `threads-video` | Feed Video | 1080×1920 | 9:16 | 1-300 | 1s - 5min. 30 fps recommended. MP4/MOV, max 1GB. |

## Snapchat (3 video placements)

All Snapchat ad formats require 9:16 and H.264.

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `snap-spotlight-video` | Spotlight | 1080×1920 | 9:16 | 5-60 | Minimum 540×960 acceptable. |
| `snap-ad-video` | Snap Ad | 1080×1920 | 9:16 | 3-180 | 3-5s optimal. Max 1GB. |
| `snap-commercial-std` | Commercial (Standard) | 1080×1920 | 9:16 | 3-6 | Non-skippable 3-6s. Extended variant: 7-180s where first 6s non-skippable. |

## Google Ads (4 video placements)

Video ads route primarily through YouTube placements.

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `gads-skippable-instream` | Skippable In-Stream | 1920×1080 | 16:9 | 12-600 | Skippable after 5s. |
| `gads-non-skippable` | Non-Skippable | 1920×1080 | 16:9 | 15-20 | Max 20s. |
| `gads-bumper` | Bumper | 1920×1080 | 16:9 | 1-6 | 6s max (non-skippable). |
| `gads-shorts-ad` | Shorts Ad | 1080×1920 | 9:16 | 6-60 | 9:16 required. |

## Spotify (1 video placement)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `spotify-canvas` | Canvas (looping visual) | 1080×1920 | 9:16 | 3-8 | Looping vertical video behind playing track. Minimum 720×1280. MP4, max 8MB. NO text/CTAs/talking footage per platform guidelines. |

## Telegram (2 video placements)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `tg-sticker-video` | Video Sticker | 512×512 | 1:1 | 1-3 | WEBM (VP9), max 256KB, 60 fps, must loop. |
| `tg-ad-video` | Ad Video | 1280×720 | 16:9 | 3-60 | MP4, 16:9. Max 5MB for images; ads may accept larger. |

## WhatsApp (1 video placement)

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `wa-status-video` | Status Video | 1080×1920 | 9:16 | 1-30 | Max 30s status; 60s via Business API. Max 16MB. |

## BlueSky (1 video placement) - unverified spec

| Key | Name | Pixels | Ratio | Duration (s) | Notes |
|---|---|---|---|---|---|
| `bsky-video` | Feed Video | 1080×1920 | 9:16 | 1-60 | ⚠️ Best-guess spec; not in SOP. BlueSky's video support is newer - verify against official BlueSky docs. |

---

## Platforms without video placements

- **Signal** - messaging-only; no broadcast video placement. Use messaging capability directly.
- **ManyChat** - an orchestrator platform; videos inherit from the connected underlying platform (Messenger, Instagram, WhatsApp).

---

## Duration-based generation strategy (v4.2.0+ - how `/create-video social` will pick a model)

| Total target duration | Best single-generation model | Alternative |
|---|---|---|
| ≤ 15s | **Kling v3 Std** at target aspect, single shot ($0.02/s) | VEO 3.1 Lite (`--provider veo --tier lite`) at $0.05/s |
| 15s - 60s | Kling v3 Std multi-shot via `video_sequence.py` | VEO 3.1 Standard |
| > 60s | Multi-shot sequence pipeline required | - |
| Bumper (6s) / Short ad (15s) | Kling v3 Std single-shot | VEO 3.1 |

For placements that need custom voice narration (creator brand voices from `audio_pipeline.py`), pair with Fabric 1.0 lip-sync via `/create-video lipsync` after the video is generated.

## See also

- [`dev-docs/SOP Graphic Sizes...md`](../../../../dev-docs/SOP%20Graphic%20Sizes%20-%20Social%20Media%20Image%20and%20Video%20Specifications%20Guide.md) - authoritative source (January 2026)
- [`kling-models.md`](./kling-models.md) - Kling v3 Std model spec and constraints
- [`veo-models.md`](./veo-models.md) - VEO 3.1 backup specs
- [`lipsync.md`](./lipsync.md) - Fabric 1.0 audio-driven lip-sync
- [`video-sequences.md`](./video-sequences.md) - Multi-shot pipeline for > 15s durations
- [`../../create-image/references/social-platforms.md`](../../create-image/references/social-platforms.md) - **image** specs for the same 16 platforms (87 image placements)
- **v4.2.0 roadmap**: `/create-video social` will consume this spec table. See `ROADMAP.md` row 10n.
