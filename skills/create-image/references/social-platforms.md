# Social Media Platform Specifications (v4.1.2+)

Reference for generating platform-optimized images from a single prompt. This covers **87 image placements across 16 platforms** at SOP max-quality upload dimensions.

> **Scope restored and expanded in v4.1.2.** v4.1.1 over-narrowed to 6 platforms; v4.1.2 brings back Pinterest, Threads, Snapchat, Google Ads, Spotify plus adds Telegram, Signal, WhatsApp, ManyChat, and BlueSky for broadcast + messaging coverage. Authoritative source for all specs: [`dev-docs/SOP Graphic Sizes - Social Media Image and Video Specifications Guide.md`](../../../../dev-docs/SOP%20Graphic%20Sizes%20-%20Social%20Media%20Image%20and%20Video%20Specifications%20Guide.md) (January 2026 update). BlueSky specs are best-guess since not in SOP - flagged for verification.

> **Companion doc for video**: [`../../create-video/references/social-platforms.md`](../../create-video/references/social-platforms.md) covers video-side specs for the same 16 platforms (37 video placements with duration ranges), ready for v4.2.0's forthcoming `/create-video social` command.

## Max-quality upload principle

Every spec targets the **highest-quality dimensions each platform accepts**. Generation cost is unchanged (still 4K natively); crop target improved.

| Placement | v4.0.x (minimum) | v4.1.2 (max quality) | Pixel count |
|---|---|---|---|
| YouTube Thumbnail | 1280×720 | **3840×2160** (4K) | **9× more pixels** |
| Instagram Profile | 320×320 | 720×720 | 5.1× |
| Facebook Feed Ad | 1080×1080 | 1440×1800 (4:5) | 2.2× |
| Facebook Story Ad | 1080×1920 | 1440×2560 | 1.8× |
| Instagram Story Ad | 1080×1920 | 1440×2560 | 1.8× |

## Default mode flipped (v4.1.2+)

`/create-image social` default `--mode` is now **`complete`** (text rendering allowed). Opt into text-free output with `--mode image-only`, which appends an explicit "NO text, NO logos, NO typography" suppression clause to the prompt.

| Mode | Flag | Description |
|------|------|-------------|
| **Complete** (default) | `--mode complete` | Prompt drives text rendering. Finished asset ready to post. Best for social posts, ads, banners, hero images. |
| Image Only | `--mode image-only` | Appends explicit text-suppression clause. Best for background plates, slide layers, logo-free asset bases. |

Most social placements are finished assets that need text. Claude's prompt engineering is what drives whether text appears, not a flag. The flag is an opt-out for the minority case where clean text-free output is wanted.

## Generation Strategy

1. **Generate at the nearest Gemini-supported aspect ratio at 4K**. The `ratio` column below - 14 ratios supported by Nano Banana 2: `1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, 1:4, 4:1, 1:8, 8:1`.
2. **Inspect → resize → crop** via `resize_for_platform()`. Source dims checked, scaled to match target ratio, cropped to exact spec.
3. **Tool fallback chain**: ImageMagick (preferred) → sips (same-ratio cases) → structured missing-tool warning.

---

## Instagram (10 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `ig-profile` | Profile Picture | 720×720 | 1:1 | SOP-recommended. Circular crop. |
| `ig-feed` | Feed Portrait | 1080×1350 | 4:5 | **Preferred organic feed format.** |
| `ig-square` | Feed Square | 1080×1080 | 1:1 | Safe default. |
| `ig-landscape` | Feed Landscape | 1080×566 | 16:9 | 1.91:1 crop. |
| `ig-story` | Story / Reel | 1080×1920 | 9:16 | Top 14% + bottom 35% reserved for UI. |
| `ig-reel-cover` | Reel Cover (full) | 1080×1920 | 9:16 | Full cover image. |
| `ig-reel-cover-grid` | Reel Grid Thumbnail | 1080×1440 | 3:4 | Profile-grid display variant. |
| `ig-story-ad` | Story Ad (premium) | 1440×2560 | 9:16 | SOP premium spec. |
| `ig-carousel` | Carousel Slide | 1080×1080 | 1:1 | Same ratio required across all slides. |
| `ig-explore-grid` | Explore Grid Ad | 1080×1080 | 1:1 | Explore Ads grid placement. |

## Facebook (10 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `fb-profile` | Profile Picture | 720×720 | 1:1 | SOP quality spec. |
| `fb-cover` | Cover Photo | 851×315 | 21:9 | True ~2.7:1 target; 21:9 gen + ~10% trim. |
| `fb-feed` | Feed Square | 1080×1080 | 1:1 | Organic square post. |
| `fb-landscape` | Feed Landscape | 1200×630 | 16:9 | 1.91:1. |
| `fb-portrait` | Feed Portrait | 1080×1350 | 4:5 | Truncated in feed with See More. |
| `fb-story` | Story | 1080×1920 | 9:16 | Top 14% profile bar; bottom 20% CTA. |
| `fb-reel` | Reel Cover | 1080×1920 | 9:16 | Safe zones top 14%, bottom 35%, sides 6%. |
| `fb-ad` | Feed Ad (premium) | 1440×1800 | 4:5 | SOP premium feed ad spec. |
| `fb-story-ad` | Story Ad (premium) | 1440×2560 | 9:16 | SOP premium story/reel ad spec. |
| `fb-right-column-ad` | Right Column Ad | 1080×1080 | 1:1 | Desktop sidebar placement. |

## YouTube (4 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `yt-profile` | Channel Icon | 800×800 | 1:1 | Displays as circle at 98×98. |
| `yt-thumb` | **Thumbnail (4K)** | **3840×2160** | 16:9 | 4K max-quality upload. YouTube accepts up to 50MB for 4K thumbnails. |
| `yt-banner` | Channel Banner | 2560×1440 | 16:9 | Safe zone center 1546×423. |
| `yt-shorts` | Shorts Cover | 1080×1920 | 9:16 | Center subject; top/bottom cropped in browse. |

## LinkedIn (10 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `li-profile` | Profile Picture | 400×400 | 1:1 | Also company logo spec. |
| `li-banner` | Profile Banner | 1584×396 | 4:1 | Keep subject in center band. |
| `li-company-cover` | Company Cover | 1128×191 | 8:1 | True 5.9:1; 8:1 gen + ~13% horizontal trim. |
| `li-landscape` | Feed Landscape | 1200×627 | 16:9 | 1.91:1 standard share image. |
| `li-portrait` | Feed Portrait | 1080×1350 | 4:5 | Truncated; top portion most visible. |
| `li-square` | Feed Square | 1080×1080 | 1:1 | Safe choice. |
| `li-carousel` | Carousel Slide | 1080×1080 | 1:1 | Swipe arrows overlay edges. |
| `li-carousel-portrait` | Carousel Portrait | 1080×1350 | 4:5 | More vertical real estate. |
| `li-ad` | Single Image Ad | 1200×628 | 16:9 | Also supports 1200×1200 square. |
| `li-message-ad-banner` | Message Ad Banner | 300×250 | 5:4 | True 1.2:1; 5:4 gen + ~4% trim. |

## Twitter/X (7 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `x-profile` | Profile Picture | 400×400 | 1:1 | Circular display. |
| `x-header` | Header Banner | 1500×500 | 21:9 | True 3:1 target; 21:9 gen + ~11% vertical trim. |
| `x-landscape` | Feed Landscape | 1200×675 | 16:9 | SOP single-image feed spec. |
| `x-square` | Feed Square | 1080×1080 | 1:1 | Displayed with slight letterboxing. |
| `x-ad` | Image Ad | 800×800 | 1:1 | SOP image ad spec. |
| `x-video-ad-frame` | Video Ad Still | 1920×1080 | 16:9 | Video ad thumbnail / still frame. |
| `x-amplify-preroll` | Amplify Pre-roll Frame | 1200×1200 | 1:1 | Amplify Pre-roll video ad still. |

## TikTok (2 placements - static images; TikTok is video-first)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `tt-profile` | Profile Picture | 720×720 | 1:1 | Displays at 200×200 but upload at 720×720. |
| `tt-hashtag-banner` | Branded Hashtag Banner | 1440×288 | 4:1 | True 5:1; 4:1 gen + ~10% vertical trim. |

*Note: TikTok's primary surfaces are video. See [`../../create-video/references/social-platforms.md`](../../create-video/references/social-platforms.md) for TikTok feed/story/ad video specs.*

## Pinterest (3 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `pin-standard` | Standard Pin | 1000×1500 | 2:3 | Optimal ratio for Pinterest grid. |
| `pin-long` | Long Pin | 1000×2100 | 9:16 | Tall pins get more grid space. |
| `pin-square` | Square Pin | 1000×1000 | 1:1 | Less grid presence but cleaner for logos. |

## Threads (4 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `threads-profile` | Profile Picture | 320×320 | 1:1 | Syncs with Instagram. |
| `threads-portrait` | Feed Portrait | 1080×1350 | 4:5 | Same as Instagram feed portrait. |
| `threads-vertical` | Feed Vertical | 1080×1920 | 9:16 | SOP-recommended for max screen fill. |
| `threads-square` | Feed Square | 1080×1080 | 1:1 | Safe default. Mixed carousel ratios allowed. |

## Snapchat (6 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `snap-story` | Story | 1080×1920 | 9:16 | 150px buffer top/bottom. |
| `snap-spotlight` | Spotlight | 1080×1920 | 9:16 | Vertical required. |
| `snap-geofilter` | Geofilter | 1080×2340 | 9:16 | True 1:2.17; 9:16 gen + ~7% horizontal trim. Max 25% coverage. |
| `snap-sticker` | Static Sticker | 512×512 | 1:1 | PNG/WEBP, max 300KB. |
| `snap-ad` | Ad | 1080×1920 | 9:16 | Bottom 30% CTA; subject in upper 60%. |
| `snap-story-ad-tile` | Story Ad Tile | 360×600 | 2:3 | PNG, max 2MB. True 1:1.67; 2:3 gen + ~10% trim. |

## Google Ads (10 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `gads-resp-landscape` | Responsive Landscape | 1200×628 | 16:9 | 1.91:1; Google auto-crops further. |
| `gads-resp-square` | Responsive Square | 1200×1200 | 1:1 | Ad text overlaid below. |
| `gads-logo` | Logo Asset | 1200×1200 | 1:1 | Optional logo; max 5MB. |
| `gads-leaderboard` | Leaderboard | 728×90 | 8:1 | True 8.09:1; 8:1 near-exact. Max 150KB. |
| `gads-mobile-lb` | Mobile Leaderboard | 320×50 | 8:1 | True 6.4:1; 8:1 gen + ~20% trim. Keep text LARGE. |
| `gads-large-mobile` | Large Mobile Banner | 320×100 | 4:1 | True 3.2:1; 4:1 gen + ~10% trim. |
| `gads-skyscraper` | Wide Skyscraper | 160×600 | 1:4 | True 1:3.75; 1:4 near-exact. |
| `gads-half-page` | Half-Page | 300×600 | 9:16 | True 1:2; 9:16 gen + ~6% trim. Keep subject in upper half. |
| `gads-rectangle` | Medium Rectangle | 300×250 | 5:4 | True 1.2:1; 5:4 gen + ~4% trim. Compact; center everything. |
| `gads-shopping` | Shopping (Merchant Center) | 800×800 | 1:1 | Apparel 250×250 min; 800×800 recommended. |

## Spotify (4 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `spotify-profile` | Artist Profile | 1000×1000 | 1:1 | 750×750 minimum; 1000×1000 recommended. |
| `spotify-banner` | Artist Banner | 2660×1140 | 21:9 | True 2.33:1 = exact 21:9 match. |
| `spotify-cover` | Album/Podcast Cover | 3000×3000 | 1:1 | Official cover art spec. sRGB 24-bit. |
| `spotify-audio-ad` | Audio Ad Companion | 640×640 | 1:1 | Shown during audio ad playback. |

## Telegram (4 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `tg-profile` | Profile Picture | 512×512 | 1:1 | Circular display. |
| `tg-sticker-static` | Static Sticker | 512×512 | 1:1 | PNG/WEBP, max 512KB. |
| `tg-message-image` | Message Image | 1280×1280 | 1:1 | Telegram auto-compresses to 1280×1280. |
| `tg-ad` | Ad Image | 1280×720 | 16:9 | Telegram Ads, min 640px width, max 5MB. |

## Signal (1 placement)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `sg-profile` | Profile Picture | 500×500 | 1:1 | Aggressive compression; upload at 500×500 for best preserved quality. |

## WhatsApp (6 placements)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `wa-profile` | Profile Picture | 640×640 | 1:1 | Max quality spec. |
| `wa-status` | Status | 1080×1920 | 9:16 | WhatsApp Stories-equivalent. |
| `wa-catalog` | Business Catalog | 1080×1080 | 1:1 | Product image for Business catalog. |
| `wa-business-cover` | Business Cover | 1920×1080 | 16:9 | Business profile cover photo. |
| `wa-ctwa-square` | Click-to-WhatsApp Ad | 1080×1080 | 1:1 | Managed through Facebook Ads Manager. |
| `wa-ctwa-story` | CTWA Story Ad | 1080×1920 | 9:16 | Vertical CTWA Story placement. |

## ManyChat (2 placements - native blocks)

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `mc-gallery-card` | Gallery/Card Image | 909×476 | 16:9 | Messenger gallery spec. True 1.91:1; 16:9 gen + ~3% trim. Max 8MB. |
| `mc-image-block` | Image Block | 1080×1080 | 1:1 | 1:1 appears larger in chat. |

## BlueSky (4 placements) - specs unverified against official docs

| Key | Name | Pixels | Ratio | Notes |
|---|---|---|---|---|
| `bsky-profile` | Profile Picture | 400×400 | 1:1 | ⚠️ Best-guess; verify against BlueSky docs. |
| `bsky-banner` | Profile Banner | 3000×1000 | 21:9 | ⚠️ True 3:1; 21:9 gen + ~11% trim. Verify. |
| `bsky-feed-square` | Feed Square | 1080×1080 | 1:1 | ⚠️ Best-guess. BlueSky allows up to 4 images per post. |
| `bsky-feed-portrait` | Feed Portrait | 1080×1350 | 4:5 | ⚠️ Best-guess. |

---

## Group Shortcuts

### Per-platform groups

| Group | Expands to |
|---|---|
| `instagram` | ig-feed, ig-square, ig-story, ig-reel-cover |
| `facebook` | fb-feed, fb-landscape, fb-portrait, fb-story, fb-reel |
| `youtube` | yt-thumb, yt-banner, yt-shorts |
| `linkedin` | li-landscape, li-square, li-portrait, li-banner |
| `twitter` | x-landscape, x-square, x-header |
| `tiktok` | tt-profile, tt-hashtag-banner |
| `pinterest` | pin-standard, pin-square |
| `threads` | threads-portrait, threads-square, threads-vertical |
| `snapchat` | snap-story, snap-spotlight |
| `google-ads` | gads-resp-landscape, gads-resp-square, gads-logo |
| `spotify` | spotify-cover, spotify-profile, spotify-banner |
| `telegram` | tg-profile, tg-sticker-static, tg-ad |
| `signal` | sg-profile |
| `whatsapp` | wa-profile, wa-status, wa-catalog |
| `manychat` | mc-gallery-card, mc-image-block |
| `bluesky` | bsky-profile, bsky-banner, bsky-feed-square |

### Cross-platform family groups

| Group | Use case |
|---|---|
| `all-feeds` | Standard feed post across IG/FB/LI/X/Threads/BlueSky |
| `all-squares` | 1:1 asset for every main platform |
| `all-stories` | 9:16 vertical for IG/FB/Snap/WhatsApp |
| `all-ads` | Every paid placement across the set |
| `all-profiles` | Profile pictures for every platform (12 variants) |
| `all-banners` | Cover/header for every platform with one |
| `all-messaging` | Telegram + Signal + WhatsApp + ManyChat set for messaging groups and automated response engines |

---

## Usage

```bash
# Single placement
/create-image social "product launch hero" --platforms yt-thumb

# Multiple specific
/create-image social "product launch hero" --platforms ig-feed,yt-thumb,li-landscape

# Per-platform group
/create-image social "product launch hero" --platforms instagram

# Cross-platform family
/create-image social "product launch hero" --platforms all-stories

# Messaging-channel pack for an automated campaign
/create-image social "Spring Sale 25% OFF banner" --platforms all-messaging

# Text-free background plate (opt out of default text-rendering)
/create-image social "dark premium gradient background" --platforms ig-story --mode image-only
```

Platforms sharing the same generation ratio are grouped automatically - if Instagram feed (4:5) and Facebook portrait (4:5) both need 4:5, only one Gemini API call is made and cropped to both specs.

## See also

- [`dev-docs/SOP Graphic Sizes...md`](../../../../dev-docs/SOP%20Graphic%20Sizes%20-%20Social%20Media%20Image%20and%20Video%20Specifications%20Guide.md) - authoritative source for specs (January 2026)
- [`dev-docs/google-nano-banana-2-llms.md`](../../../../dev-docs/google-nano-banana-2-llms.md) - Nano Banana 2 supported aspect ratios (the 14 ratios)
- [`../../create-video/references/social-platforms.md`](../../create-video/references/social-platforms.md) - **video** specs for the same 16 platforms (37 placements with duration ranges)
- [`../scripts/social.py`](../scripts/social.py) - CLI runner
- [`../scripts/social.py::resize_for_platform`](../scripts/social.py) - v4.1.0 exact-dimension enforcer
