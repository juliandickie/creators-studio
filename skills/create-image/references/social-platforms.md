# Social Media Platform Specifications (v4.1.1+)

Reference for generating platform-optimized images from a single prompt. This covers **38 placement specs across 6 platforms** at max-quality upload dimensions.

> **Scope narrowed in v4.1.1** from 11 platforms (46 shallow placements) to **6 platforms with deep coverage**: Instagram, Facebook, YouTube, LinkedIn, Twitter/X, TikTok. Pinterest, Threads, Snapchat, Google Ads, and Spotify were retired because coverage was 2-3 placements each with no profile photos or ad variants. Authoritative source for all specs: [`dev-docs/SOP Graphic Sizes - Social Media Image and Video Specifications Guide.md`](../../../dev-docs/SOP%20Graphic%20Sizes%20-%20Social%20Media%20Image%20and%20Video%20Specifications%20Guide.md) (January 2026 update).

## Max-quality upload principle

Every spec in this file targets the **highest-quality dimensions each platform accepts**, not the minimum required for upload. The difference is significant:

| Placement | v4.0.x (minimum) | v4.1.1 (max quality) | Pixel-count ratio |
|---|---|---|---|
| YouTube Thumbnail | 1280×720 | **3840×2160** (4K) | **9× more pixels** |
| Instagram Profile | 320×320 | **720×720** | 5.1× |
| Facebook Feed Ad | 1080×1080 | **1440×1800** (4:5) | 2.2× |
| Facebook Story Ad | 1080×1920 | **1440×2560** | 1.8× |
| Instagram Story Ad | 1080×1920 | **1440×2560** | 1.8× |

Generation still happens at 4K natively (via Gemini's `imageSize: "4K"`); the final crop produces max-quality platform-spec outputs. The trim ratio is small for most placements, so quality is preserved. Upload size limits for all platforms accommodate these dimensions.

## Generation Strategy

1. **Generate at the nearest Gemini-supported aspect ratio at 4K**. See the `ratio` column below — that's what's passed to Gemini's `aspect_ratio` parameter.
2. **Inspect → resize → crop to exact target pixels** via `resize_for_platform()` (v4.1.0+). Checks actual Gemini output dimensions (may be slightly off the requested ratio), scales to match target ratio, crops to exact spec.
3. **Tool fallback chain**: ImageMagick (preferred) → sips (same-ratio cases) → structured missing-tool warning if neither handles the ratio change. Never silent degradation.

## Output Modes

| Mode | Flag | Description |
|------|------|-------------|
| Complete | `--mode complete` | Full image with text overlays baked in (hero banners, ads with CTA) |
| Image Only | `--mode image-only` (default) | Clean image, no text — for posts where text is added in-app or via design tool |

---

## Instagram (8 placements)

Feed grid shifted to 3:4 vertical thumbnails in 2025; 4:5 portrait is now the preferred organic feed format.

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `ig-profile` | Profile Picture | 720×720 | 1:1 | Circular crop. Keep subject in center 70%. Upgraded from 320×320 minimum. |
| `ig-feed` | Feed Portrait | 1080×1350 | 4:5 | **Preferred organic feed format.** Bottom 20% may be obscured by caption overlay. |
| `ig-square` | Feed Square | 1080×1080 | 1:1 | Center subject; edges may clip on older devices. |
| `ig-landscape` | Feed Landscape | 1080×566 | 16:9 | 1.91:1 crop from 16:9 generation. |
| `ig-story` | Story / Reel | 1080×1920 | 9:16 | Top 14% and bottom 35% reserved for UI (safe zones). |
| `ig-reel-cover` | Reel Cover (full) | 1080×1920 | 9:16 | Full cover image; center of frame is the visible thumbnail. |
| `ig-reel-cover-grid` | Reel Grid Thumbnail | 1080×1440 | 3:4 | Profile-grid display variant of the reel cover. |
| `ig-story-ad` | Story Ad (premium) | 1440×2560 | 9:16 | **SOP premium quality spec** — not the 1080×1920 minimum. |

## Facebook (8 placements)

Meta Ads ecosystem offers extensive placement options. Feed ad specs upgraded in v4.1.1 to the 1440×X premium variants.

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `fb-profile` | Profile Picture | 720×720 | 1:1 | Quality-recommended spec (displays 176×176 desktop, 196×196 mobile). |
| `fb-cover` | Cover Photo | 851×315 | 21:9 | Design size; desktop displays 820×312, mobile 640×360. Safe zone: center 640×312. Generates at 21:9 (closest supported) then crops ~10% vertical to reach 2.7:1. |
| `fb-feed` | Feed Square | 1080×1080 | 1:1 | Organic square post. |
| `fb-landscape` | Feed Landscape | 1200×630 | 16:9 | 1.91:1 — link preview crops tighter. |
| `fb-portrait` | Feed Portrait | 1080×1350 | 4:5 | Truncated in feed with See More. |
| `fb-story` | Story / Reel | 1080×1920 | 9:16 | Top 14% profile bar; bottom 20% CTA. |
| `fb-ad` | Feed Ad (premium) | 1440×1800 | 4:5 | **SOP premium feed ad spec** (was 1080×1080 in v4.0.x). Bottom 20% ad copy overlay. |
| `fb-story-ad` | Story Ad (premium) | 1440×2560 | 9:16 | **SOP premium story/reel ad spec.** Safe zones top 360px, bottom 900px. |

## YouTube (4 placements)

YouTube supports the widest resolution range among the six platforms (240p to 8K).

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `yt-profile` | Channel Icon | 800×800 | 1:1 | Displays as circle at 98×98. |
| `yt-thumb` | **Thumbnail (4K)** | **3840×2160** | 16:9 | **v4.1.1 major upgrade: 4K thumbnail** (was 1280×720 minimum in v4.0.x). YouTube accepts thumbnail uploads up to 50MB for 4K. Bottom-right has timestamp overlay. |
| `yt-banner` | Channel Banner | 2560×1440 | 16:9 | Safe zone: center 1546×423 for visibility across all devices. |
| `yt-shorts` | Shorts Cover | 1080×1920 | 9:16 | Center subject; top/bottom cropped in browse. |

## LinkedIn (9 placements)

Document carousels and native video drive organic reach on LinkedIn.

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `li-profile` | Profile Picture | 400×400 | 1:1 | Displays as circle. Same spec as company logo. |
| `li-banner` | Profile Banner | 1584×396 | 4:1 | Keep subject in center band. |
| `li-landscape` | Feed Landscape | 1200×627 | 16:9 | 1.91:1 standard share image. |
| `li-portrait` | Feed Portrait | 1080×1350 | 4:5 | Truncated in feed; top portion most visible. |
| `li-square` | Feed Square | 1080×1080 | 1:1 | Safe choice for LinkedIn. |
| `li-carousel` | Carousel Slide | 1080×1080 | 1:1 | Keep margins; swipe arrows overlay edges. |
| `li-carousel-portrait` | Carousel Portrait | 1080×1350 | 4:5 | More vertical real estate for document-style carousels. |
| `li-ad` | Single Image Ad | 1200×628 | 16:9 | Also supports 1200×1200 square per SOP. |
| `li-video-ad-frame` | Video Ad Still | 1920×1080 | 16:9 | Video ad thumbnail / still frame at 1080p. |

## Twitter/X (6 placements)

X Premium subscribers have extended video limits; image specs unchanged.

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `x-profile` | Profile Picture | 400×400 | 1:1 | Circular display. |
| `x-header` | Header Banner | 1500×500 | 21:9 | **v4.1.1 FIX**: was labeled `3:2` in v4.0.x — true target is 3:1 (1500/500 = 3.0), but Gemini doesn't support 3:1 natively; generates at 21:9 (2.33:1, closest supported) then crops ~11% vertical. Safe zone: 100px buffer top/bottom; profile photo overlaps bottom-left. |
| `x-landscape` | Feed Landscape | 1200×675 | 16:9 | **v4.1.1 CORRECTED** from 1600×900. SOP spec for single-image feed posts. Crops from center on mobile. |
| `x-square` | Feed Square | 1080×1080 | 1:1 | Displayed with slight letterboxing on some devices. |
| `x-ad` | Image Ad | 800×800 | 1:1 | **v4.1.1 CORRECTED** from 1600×900 landscape to SOP-spec 1:1. SOP also allows 800×418 (1.91:1). |
| `x-video-ad-frame` | Video Ad Still | 1920×1080 | 16:9 | Video ad thumbnail / still frame at 1080p. |

## TikTok (3 placements)

Vertical-first platform; 9:16 content receives algorithmic preference across all placements.

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `tt-profile` | Profile Picture | 720×720 | 1:1 | Displays at 200×200 but upload at 720×720 for quality. |
| `tt-feed` | Feed / Cover | 1080×1920 | 9:16 | 9:16 preferred. Avoid top and bottom 120 pixels due to UI overlays. |
| `tt-ad` | In-Feed / TopView Ad | 1080×1920 | 9:16 | Both in-feed ads and TopView ads use same 1080×1920 9:16 spec. |

---

## Group Shortcuts

Shortcuts that expand to multiple platform keys for multi-channel campaigns.

### Per-platform groups

| Group | Expands to |
|---|---|
| `instagram` | `ig-feed, ig-square, ig-story, ig-reel-cover` |
| `facebook` | `fb-feed, fb-landscape, fb-portrait, fb-story` |
| `youtube` | `yt-thumb, yt-banner, yt-shorts` |
| `linkedin` | `li-landscape, li-square, li-portrait, li-banner` |
| `twitter` | `x-landscape, x-square, x-header` |
| `tiktok` | `tt-feed` |

### Cross-platform family groups

| Group | Expands to | Use case |
|---|---|---|
| `all-feeds` | `ig-feed, fb-portrait, li-portrait, x-landscape` | A standard post across all 4 feed-based platforms |
| `all-squares` | `ig-square, fb-feed, li-square, x-square` | 1:1 asset for every major platform |
| `all-stories` | `ig-story, fb-story, tt-feed` | 9:16 vertical content for Stories/Reels/TikTok |
| `all-ads` | `fb-ad, fb-story-ad, ig-story-ad, li-ad, x-ad, tt-ad` | Every paid-placement ad variant |
| `all-profiles` | `ig-profile, fb-profile, yt-profile, li-profile, x-profile, tt-profile` | Profile pictures for every platform |
| `all-banners` | `fb-cover, yt-banner, li-banner, x-header` | Cover/banner for every platform |

---

## Usage

```bash
# Single placement
/create-image social "product launch hero" --platforms yt-thumb

# Multiple specific placements
/create-image social "product launch hero" --platforms ig-feed,yt-thumb,li-landscape

# Per-platform group
/create-image social "product launch hero" --platforms instagram

# Cross-platform family
/create-image social "product launch hero" --platforms all-stories
```

Platforms sharing the same generation ratio are grouped automatically — if Instagram feed (4:5) and Facebook portrait (4:5) both need the same ratio, **only one Gemini API call is made** and cropped to both specs. Minimizes cost and API calls.

## Safe Zones Reference

For placements with UI overlays, keep the key subject within the central safe zone:

| Placement | Safe zone | Obscured by |
|---|---|---|
| `ig-feed` | Avoid bottom 20% | Caption overlay |
| `ig-story` / `fb-story` / `ig-story-ad` / `fb-story-ad` | Avoid top 14% + bottom 35% | Profile bar + reply/CTA |
| `fb-cover` | Center 640×312 | Edges crop on mobile |
| `yt-thumb` | Avoid bottom-right corner | Timestamp overlay |
| `yt-banner` | Center 1546×423 | Only visible area across devices |
| `li-banner` | Center band | Cropped on mobile |
| `x-header` | 100px buffer top/bottom | Profile photo overlaps bottom-left |
| `tt-feed` / `tt-ad` | Avoid top 120px + bottom 120px | UI overlays |

## See also

- [`dev-docs/SOP Graphic Sizes - Social Media Image and Video Specifications Guide.md`](../../../dev-docs/SOP%20Graphic%20Sizes%20-%20Social%20Media%20Image%20and%20Video%20Specifications%20Guide.md) — authoritative source for all specs (January 2026 update)
- [`../scripts/social.py`](../scripts/social.py) — the platform generator CLI
- [`../scripts/social.py::resize_for_platform`](../scripts/social.py) — v4.1.0 exact-dimension enforcer
