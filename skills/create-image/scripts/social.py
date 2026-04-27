#!/usr/bin/env python3
"""Creators Studio -- Social Media Multi-Platform Image Generator (v4.1.2+)

Generate images optimized for 87 placements across 16 social media platforms
from a single prompt. Groups placements by aspect ratio to avoid duplicate API
calls, generates at 4K, and crops to exact platform pixels via
resize_for_platform() (ImageMagick preferred, sips+cwebp fallback).

Uses only Python stdlib (no pip dependencies). All aspect ratios drawn from
the 14 Nano Banana 2-supported set; non-standard targets use closest-supported
generation + crop.

Usage:
    social.py generate --prompt "product launch hero" --platforms ig-feed,yt-thumb
    social.py generate --prompt "spring sale banner" --platforms instagram,youtube
    social.py generate --prompt "abstract background" --platforms ig-feed --mode image-only
    social.py list
    social.py info ig-feed
    social.py info instagram

Default mode is "complete" (v4.1.2+) — prompts that imply text (social posts,
ads with CTAs) render it naturally. Opt into text-free output with
--mode image-only, which appends explicit text-suppression to the prompt.
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_RESOLUTION = "4K"
OUTPUT_DIR = Path.home() / "Documents" / "creators_generated"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# ---------------------------------------------------------------------------
# Platform definitions
# ---------------------------------------------------------------------------

# PLATFORMS dict — 16 platforms, 87 placements, SOP max-quality specs (v4.1.2+)
#
# Restored Pinterest / Threads / Snapchat / Google Ads / Spotify from v4.1.1's
# 6-platform scope, then added Telegram / Signal / WhatsApp / ManyChat / BlueSky
# for marketer coverage (messaging groups, automated response engines, new
# social platforms). Depth + breadth both expanded.
#
# All pixel specs at SOP-recommended MAX-QUALITY values. Authoritative source:
# dev-docs/SOP Graphic Sizes - Social Media Image and Video Specifications Guide.md
# (January 2026 update). BlueSky specs are best-guess since not in SOP — verify
# against official BlueSky docs before relying on them.
#
# Non-standard target ratios (placements whose true aspect isn't in Gemini's
# 14 supported ratios) use the closest-supported ratio + resize_for_platform
# crop. Each such placement documents its generation ratio and the trim cost.
#
# All aspect ratios below are drawn from the 14 Nano Banana 2-supported set:
#   1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, 1:4, 4:1, 1:8, 8:1
# See dev-docs/google-nano-banana-2-llms.md for the authoritative list.

PLATFORMS = {
    # ═══ Instagram (10 placements) ═══════════════════════════════════════════
    "ig-profile":           {"name": "Instagram Profile Picture",       "pixels": (720, 720),   "ratio": "1:1",  "resolution": "4K", "notes": "Circular crop -- keep subject in center 70%. SOP-recommended 720x720."},
    "ig-feed":              {"name": "Instagram Feed Portrait",         "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "Preferred organic feed format. Bottom 20% may be obscured by caption overlay."},
    "ig-square":            {"name": "Instagram Feed Square",           "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Center subject; edges may clip on older devices."},
    "ig-landscape":         {"name": "Instagram Feed Landscape",        "pixels": (1080, 566),  "ratio": "16:9", "resolution": "4K", "notes": "1.91:1 crop from 16:9 source."},
    "ig-story":             {"name": "Instagram Story / Reel",          "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Top 14% and bottom 35% reserved for UI (safe zones)."},
    "ig-reel-cover":        {"name": "Instagram Reel Cover (full)",     "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Full reel cover image. Center of frame is the visible thumbnail."},
    "ig-reel-cover-grid":   {"name": "Instagram Reel Grid Thumbnail",   "pixels": (1080, 1440), "ratio": "3:4",  "resolution": "4K", "notes": "Profile-grid display variant of the reel cover."},
    "ig-story-ad":          {"name": "Instagram Story Ad (premium)",    "pixels": (1440, 2560), "ratio": "9:16", "resolution": "4K", "notes": "SOP premium quality spec for Stories Ads."},
    "ig-carousel":          {"name": "Instagram Carousel Slide",        "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Consistent ratio required across all slides; 1:1 or 4:5."},
    "ig-explore-grid":      {"name": "Instagram Explore Grid Ad",       "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Explore Ads grid placement spec."},

    # ═══ Facebook (10 placements) ════════════════════════════════════════════
    "fb-profile":           {"name": "Facebook Profile Picture",        "pixels": (720, 720),   "ratio": "1:1",  "resolution": "4K", "notes": "SOP quality spec 720x720 (displays 176x176 desktop, 196x196 mobile)."},
    "fb-cover":             {"name": "Facebook Cover Photo",            "pixels": (851, 315),   "ratio": "21:9", "resolution": "4K", "notes": "Design-size 851x315; true aspect ~2.7:1. Generates at 21:9 (closest supported), ~10% vertical trim. Safe zone center 640x312."},
    "fb-feed":              {"name": "Facebook Feed Square",            "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Organic square post."},
    "fb-landscape":         {"name": "Facebook Feed Landscape",         "pixels": (1200, 630),  "ratio": "16:9", "resolution": "4K", "notes": "1.91:1 — link preview crops tighter."},
    "fb-portrait":          {"name": "Facebook Feed Portrait",          "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "Truncated in feed with See More."},
    "fb-story":             {"name": "Facebook Story",                  "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Top 14% profile bar; bottom 20% CTA."},
    "fb-reel":              {"name": "Facebook Reel Cover",             "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Reels cover spec; safe zones top 14%, bottom 35%, sides 6%."},
    "fb-ad":                {"name": "Facebook Feed Ad (premium)",      "pixels": (1440, 1800), "ratio": "4:5",  "resolution": "4K", "notes": "SOP premium feed ad spec. Bottom 20% ad copy overlay."},
    "fb-story-ad":          {"name": "Facebook Story Ad (premium)",     "pixels": (1440, 2560), "ratio": "9:16", "resolution": "4K", "notes": "SOP premium story/reel ad spec. Safe zones top 360px, bottom 900px."},
    "fb-right-column-ad":   {"name": "Facebook Right Column Ad",        "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Desktop sidebar ad placement."},

    # ═══ YouTube (4 placements) ══════════════════════════════════════════════
    "yt-profile":           {"name": "YouTube Channel Icon",            "pixels": (800, 800),   "ratio": "1:1",  "resolution": "4K", "notes": "Displays as circle at 98x98."},
    "yt-thumb":             {"name": "YouTube Thumbnail (4K)",          "pixels": (3840, 2160), "ratio": "16:9", "resolution": "4K", "notes": "4K max-quality upload. YouTube supports up to 50MB for 4K thumbnails. Bottom-right has timestamp overlay."},
    "yt-banner":            {"name": "YouTube Channel Banner",          "pixels": (2560, 1440), "ratio": "16:9", "resolution": "4K", "notes": "Safe zone is center 1546x423 for visibility across all devices."},
    "yt-shorts":            {"name": "YouTube Shorts Cover",            "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Center subject; top/bottom cropped in browse."},

    # ═══ LinkedIn (10 placements) ════════════════════════════════════════════
    "li-profile":           {"name": "LinkedIn Profile Picture",        "pixels": (400, 400),   "ratio": "1:1",  "resolution": "4K", "notes": "Displays as circle. Also company logo spec."},
    "li-banner":            {"name": "LinkedIn Banner",                 "pixels": (1584, 396),  "ratio": "4:1",  "resolution": "4K", "notes": "Keep subject in center band."},
    "li-company-cover":     {"name": "LinkedIn Company Cover",          "pixels": (1128, 191),  "ratio": "8:1",  "resolution": "4K", "notes": "True aspect 5.9:1; generates at 8:1 (closer crop than 4:1 for this target), ~13% horizontal trim."},
    "li-landscape":         {"name": "LinkedIn Feed Landscape",         "pixels": (1200, 627),  "ratio": "16:9", "resolution": "4K", "notes": "1.91:1 standard share image."},
    "li-portrait":          {"name": "LinkedIn Feed Portrait",          "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "Truncated in feed; top portion most visible."},
    "li-square":            {"name": "LinkedIn Feed Square",            "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Safe choice for LinkedIn."},
    "li-carousel":          {"name": "LinkedIn Carousel Slide",         "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Keep margins; swipe arrows overlay edges."},
    "li-carousel-portrait": {"name": "LinkedIn Carousel Portrait",      "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "More vertical real estate for document-style carousels."},
    "li-ad":                {"name": "LinkedIn Single Image Ad",        "pixels": (1200, 628),  "ratio": "16:9", "resolution": "4K", "notes": "SOP single image ad spec (also supports 1200x1200 square)."},
    "li-message-ad-banner": {"name": "LinkedIn Message Ad Banner",      "pixels": (300, 250),   "ratio": "5:4",  "resolution": "4K", "notes": "Optional InMail banner. True aspect 1.2:1; generates at 5:4 (1.25:1), ~4% vertical trim."},

    # ═══ Twitter/X (7 placements) ════════════════════════════════════════════
    "x-profile":            {"name": "Twitter/X Profile Picture",       "pixels": (400, 400),   "ratio": "1:1",  "resolution": "4K", "notes": "Circular display."},
    "x-header":             {"name": "Twitter/X Header Banner",         "pixels": (1500, 500),  "ratio": "21:9", "resolution": "4K", "notes": "True target 3:1 (1500/500 = 3.0); Gemini generates at 21:9 (2.33:1, closest supported) then crops ~11% vertical. Safe zone: 100px buffer top/bottom; profile photo overlaps bottom-left."},
    "x-landscape":          {"name": "Twitter/X Feed Landscape",        "pixels": (1200, 675),  "ratio": "16:9", "resolution": "4K", "notes": "SOP spec for single-image feed posts. Crops from center on mobile."},
    "x-square":             {"name": "Twitter/X Feed Square",           "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Displayed with slight letterboxing on some devices."},
    "x-ad":                 {"name": "Twitter/X Image Ad",              "pixels": (800, 800),   "ratio": "1:1",  "resolution": "4K", "notes": "SOP image ad spec. SOP also allows 800x418 (1.91:1)."},
    "x-video-ad-frame":     {"name": "Twitter/X Video Ad Still",        "pixels": (1920, 1080), "ratio": "16:9", "resolution": "4K", "notes": "Video ad thumbnail / still frame at 1080p."},
    "x-amplify-preroll":    {"name": "Twitter/X Amplify Pre-roll Frame", "pixels": (1200, 1200), "ratio": "1:1",  "resolution": "4K", "notes": "Amplify Pre-roll video ad frame."},

    # ═══ TikTok (2 placements — TikTok is a video-first platform) ════════════
    "tt-profile":           {"name": "TikTok Profile Picture",          "pixels": (720, 720),   "ratio": "1:1",  "resolution": "4K", "notes": "Displays at 200x200 but upload at 720x720 for quality."},
    "tt-hashtag-banner":    {"name": "TikTok Branded Hashtag Banner",   "pixels": (1440, 288),  "ratio": "4:1",  "resolution": "4K", "notes": "True aspect 5:1; generates at 4:1 (closer than 8:1 for this target), ~10% vertical trim."},

    # ═══ Pinterest (3 placements) ════════════════════════════════════════════
    "pin-standard":         {"name": "Pinterest Standard Pin",          "pixels": (1000, 1500), "ratio": "2:3",  "resolution": "4K", "notes": "Optimal ratio for Pinterest grid."},
    "pin-long":             {"name": "Pinterest Long Pin",              "pixels": (1000, 2100), "ratio": "9:16", "resolution": "4K", "notes": "Tall pins get more grid space. True aspect 1:2.1; generates at 9:16 (closest supported), ~8% horizontal trim."},
    "pin-square":           {"name": "Pinterest Square Pin",            "pixels": (1000, 1000), "ratio": "1:1",  "resolution": "4K", "notes": "Less grid presence than portrait but cleaner for logo-style content."},

    # ═══ Threads (4 placements) ══════════════════════════════════════════════
    "threads-profile":      {"name": "Threads Profile Picture",         "pixels": (320, 320),   "ratio": "1:1",  "resolution": "4K", "notes": "Syncs with Instagram profile; 320x320 per SOP."},
    "threads-portrait":     {"name": "Threads Feed Portrait",           "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "Same as Instagram feed portrait."},
    "threads-vertical":     {"name": "Threads Feed Vertical",           "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "SOP-recommended format for maximum screen fill."},
    "threads-square":       {"name": "Threads Feed Square",             "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Safe default. Mixed carousel ratios are allowed within the same post."},

    # ═══ Snapchat (6 placements) ═════════════════════════════════════════════
    "snap-story":           {"name": "Snapchat Story",                  "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Top 14% header; bottom 20% swipe-up/reply area. 150px buffer top/bottom."},
    "snap-spotlight":       {"name": "Snapchat Spotlight",              "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Vertical required. Public creator feed."},
    "snap-geofilter":       {"name": "Snapchat Geofilter",              "pixels": (1080, 2340), "ratio": "9:16", "resolution": "4K", "notes": "True aspect 1:2.17; generates at 9:16 (closest supported), ~7% horizontal trim. Coverage max 25% of screen."},
    "snap-sticker":         {"name": "Snapchat Static Sticker",         "pixels": (512, 512),   "ratio": "1:1",  "resolution": "4K", "notes": "PNG/WEBP, max 300KB."},
    "snap-ad":              {"name": "Snapchat Ad",                     "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Bottom 30% is CTA; subject in upper 60%."},
    "snap-story-ad-tile":   {"name": "Snapchat Story Ad Tile",          "pixels": (360, 600),   "ratio": "2:3",  "resolution": "4K", "notes": "PNG required, max 2MB. True aspect 1:1.67; generates at 2:3 (1:1.5), ~10% vertical trim."},

    # ═══ Google Ads (10 placements) ══════════════════════════════════════════
    "gads-resp-landscape":  {"name": "Google Ads Responsive Landscape", "pixels": (1200, 628),  "ratio": "16:9", "resolution": "4K", "notes": "1.91:1 — Google may auto-crop further across placements."},
    "gads-resp-square":     {"name": "Google Ads Responsive Square",    "pixels": (1200, 1200), "ratio": "1:1",  "resolution": "4K", "notes": "Ad text overlaid below."},
    "gads-logo":            {"name": "Google Ads Logo",                 "pixels": (1200, 1200), "ratio": "1:1",  "resolution": "4K", "notes": "Optional logo asset (max 5MB per image)."},
    "gads-leaderboard":     {"name": "Google Ads Leaderboard",          "pixels": (728, 90),    "ratio": "8:1",  "resolution": "4K", "notes": "True aspect 8.09:1; generates at 8:1 (near-exact). Max 150KB file size."},
    "gads-mobile-lb":       {"name": "Google Ads Mobile Leaderboard",   "pixels": (320, 50),    "ratio": "8:1",  "resolution": "4K", "notes": "True aspect 6.4:1; generates at 8:1 (closest), ~20% horizontal trim. Keep text LARGE."},
    "gads-large-mobile":    {"name": "Google Ads Large Mobile Banner",  "pixels": (320, 100),   "ratio": "4:1",  "resolution": "4K", "notes": "True aspect 3.2:1; generates at 4:1 (closest), ~10% vertical trim."},
    "gads-skyscraper":      {"name": "Google Ads Wide Skyscraper",      "pixels": (160, 600),   "ratio": "1:4",  "resolution": "4K", "notes": "True aspect 1:3.75; generates at 1:4 (near-exact). Narrow vertical; text must be large."},
    "gads-half-page":       {"name": "Google Ads Half-Page",            "pixels": (300, 600),   "ratio": "9:16", "resolution": "4K", "notes": "True aspect 1:2; generates at 9:16 (1:1.78), ~6% vertical trim. Keep subject in upper half."},
    "gads-rectangle":       {"name": "Google Ads Medium Rectangle",     "pixels": (300, 250),   "ratio": "5:4",  "resolution": "4K", "notes": "True aspect 1.2:1; generates at 5:4 (1.25:1, closest), ~4% vertical trim. Compact format; center everything."},
    "gads-shopping":        {"name": "Google Ads Shopping",             "pixels": (800, 800),   "ratio": "1:1",  "resolution": "4K", "notes": "Merchant Center spec. Apparel 250x250 min; non-apparel 100x100 min; 800x800 recommended."},

    # ═══ Spotify (4 placements) ══════════════════════════════════════════════
    "spotify-profile":      {"name": "Spotify Artist Profile",          "pixels": (1000, 1000), "ratio": "1:1",  "resolution": "4K", "notes": "SOP-recommended size. 750x750 minimum."},
    "spotify-banner":       {"name": "Spotify Artist Banner",           "pixels": (2660, 1140), "ratio": "21:9", "resolution": "4K", "notes": "True aspect 2.33:1 = exact 21:9 match. Text overlays on left side."},
    "spotify-cover":        {"name": "Spotify Album/Podcast Cover",     "pixels": (3000, 3000), "ratio": "1:1",  "resolution": "4K", "notes": "Official Spotify/Apple Podcasts cover art spec. sRGB 24-bit."},
    "spotify-audio-ad":     {"name": "Spotify Audio Ad Companion",      "pixels": (640, 640),   "ratio": "1:1",  "resolution": "4K", "notes": "Companion image shown during audio ad playback."},

    # ═══ Telegram (4 placements) ═════════════════════════════════════════════
    "tg-profile":           {"name": "Telegram Profile Picture",        "pixels": (512, 512),   "ratio": "1:1",  "resolution": "4K", "notes": "Circular display. Same spec as sticker canvas."},
    "tg-sticker-static":    {"name": "Telegram Static Sticker",         "pixels": (512, 512),   "ratio": "1:1",  "resolution": "4K", "notes": "PNG/WEBP, max 512KB. One side must be exactly 512px."},
    "tg-message-image":     {"name": "Telegram Message Image",          "pixels": (1280, 1280), "ratio": "1:1",  "resolution": "4K", "notes": "Telegram auto-compresses messages to 1280x1280; send as file to avoid compression."},
    "tg-ad":                {"name": "Telegram Ad Image",               "pixels": (1280, 720),  "ratio": "16:9", "resolution": "4K", "notes": "Telegram Ads require 16:9, min 640px width, max 5MB."},

    # ═══ Signal (1 placement — minimal broadcast surface) ════════════════════
    "sg-profile":           {"name": "Signal Profile Picture",          "pixels": (500, 500),   "ratio": "1:1",  "resolution": "4K", "notes": "Signal applies aggressive compression; upload source at 500x500 for best preserved quality. Minimum is 160x160."},

    # ═══ WhatsApp (6 placements) ═════════════════════════════════════════════
    "wa-profile":           {"name": "WhatsApp Profile Picture",        "pixels": (640, 640),   "ratio": "1:1",  "resolution": "4K", "notes": "Max quality spec (640x640); 500x500 also ideal."},
    "wa-status":            {"name": "WhatsApp Status",                 "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "WhatsApp Stories-equivalent format."},
    "wa-catalog":           {"name": "WhatsApp Business Catalog",       "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Product image for Business catalog. Minimum 640x640."},
    "wa-business-cover":    {"name": "WhatsApp Business Cover",         "pixels": (1920, 1080), "ratio": "16:9", "resolution": "4K", "notes": "Recommended Business profile cover photo."},
    "wa-ctwa-square":       {"name": "WhatsApp Click-to-WhatsApp Ad",   "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Managed through Facebook/Instagram Ads Manager."},
    "wa-ctwa-story":        {"name": "WhatsApp CTWA Story Ad",          "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Vertical CTWA placement for Stories."},

    # ═══ ManyChat (2 placements — native blocks) ═════════════════════════════
    "mc-gallery-card":      {"name": "ManyChat Gallery/Card Image",     "pixels": (909, 476),   "ratio": "16:9", "resolution": "4K", "notes": "Messenger gallery card spec. True aspect 1.91:1; generates at 16:9 (1.78:1), ~3% vertical trim. Max 8MB."},
    "mc-image-block":       {"name": "ManyChat Image Block",            "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "SOP-recommended 900x900 rounded up to 1080x1080 for quality. 1:1 appears larger in chat."},

    # ═══ BlueSky (4 placements — specs unverified against official docs) ═════
    "bsky-profile":         {"name": "BlueSky Profile Picture",         "pixels": (400, 400),   "ratio": "1:1",  "resolution": "4K", "notes": "v4.1.2: best-guess spec; not in SOP. Displays circular. Verify against BlueSky official docs before production use."},
    "bsky-banner":          {"name": "BlueSky Profile Banner",          "pixels": (3000, 1000), "ratio": "21:9", "resolution": "4K", "notes": "v4.1.2: best-guess spec. True target 3:1 (3.0:1); generates at 21:9 (2.33:1, closest supported), ~11% vertical trim. Verify against BlueSky docs."},
    "bsky-feed-square":     {"name": "BlueSky Feed Square",             "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "v4.1.2: best-guess spec. BlueSky allows up to 4 images per post at common social ratios."},
    "bsky-feed-portrait":   {"name": "BlueSky Feed Portrait",           "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "v4.1.2: best-guess spec. Portrait variant for richer vertical feed presence."},
}

# Group shorthands expand to multiple platform keys (v4.1.2: 16 platforms)
GROUPS = {
    # Per-platform groups — the main placements for that platform's feed
    "instagram":    ["ig-feed", "ig-square", "ig-story", "ig-reel-cover"],
    "facebook":     ["fb-feed", "fb-landscape", "fb-portrait", "fb-story", "fb-reel"],
    "youtube":      ["yt-thumb", "yt-banner", "yt-shorts"],
    "linkedin":     ["li-landscape", "li-square", "li-portrait", "li-banner"],
    "twitter":      ["x-landscape", "x-square", "x-header"],
    "tiktok":       ["tt-profile", "tt-hashtag-banner"],
    "pinterest":    ["pin-standard", "pin-square"],
    "threads":      ["threads-portrait", "threads-square", "threads-vertical"],
    "snapchat":     ["snap-story", "snap-spotlight"],
    "google-ads":   ["gads-resp-landscape", "gads-resp-square", "gads-logo"],
    "spotify":      ["spotify-cover", "spotify-profile", "spotify-banner"],
    "telegram":     ["tg-profile", "tg-sticker-static", "tg-ad"],
    "signal":       ["sg-profile"],
    "whatsapp":     ["wa-profile", "wa-status", "wa-catalog"],
    "manychat":     ["mc-gallery-card", "mc-image-block"],
    "bluesky":      ["bsky-profile", "bsky-banner", "bsky-feed-square"],

    # Cross-platform family groups — useful for multi-channel campaigns
    "all-feeds":    ["ig-feed", "fb-portrait", "li-portrait", "x-landscape", "threads-portrait", "bsky-feed-portrait"],
    "all-squares":  ["ig-square", "fb-feed", "li-square", "x-square", "threads-square", "bsky-feed-square"],
    "all-stories":  ["ig-story", "fb-story", "snap-story", "wa-status"],
    "all-ads":      ["fb-ad", "fb-story-ad", "ig-story-ad", "li-ad", "x-ad", "snap-ad", "gads-resp-landscape", "wa-ctwa-square"],
    "all-profiles": ["ig-profile", "fb-profile", "yt-profile", "li-profile", "x-profile", "tt-profile", "threads-profile", "tg-profile", "sg-profile", "wa-profile", "bsky-profile", "spotify-profile"],
    "all-banners":  ["fb-cover", "yt-banner", "li-banner", "x-header", "spotify-banner", "bsky-banner"],
    "all-messaging": ["tg-profile", "sg-profile", "wa-profile", "wa-status", "wa-catalog", "mc-gallery-card", "mc-image-block"],
}

# 4K generation sizes for each native ratio
RATIO_4K_SIZES = {
    "1:1":  (4096, 4096),
    "2:3":  (2731, 4096),
    "3:2":  (4096, 2731),
    "3:4":  (3072, 4096),
    "4:3":  (4096, 3072),
    "4:5":  (3200, 4000),
    "5:4":  (4096, 3277),
    "9:16": (2304, 4096),
    "16:9": (4096, 2304),
    "21:9": (4096, 1756),
    "1:4":  (1024, 4096),
    "4:1":  (4096, 1024),
    "1:8":  (512, 4096),
    "8:1":  (4096, 512),
}


# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------

def _load_api_key(cli_key=None):
    """Load Google AI API key from CLI, env, or config file."""
    key = cli_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        # v4.2.2: canonical config dir (auto-migrates from ~/.banana/ on first call).
        _plugin_root = str(Path(__file__).resolve().parent.parent.parent.parent)
        if _plugin_root not in sys.path:
            sys.path.insert(0, _plugin_root)
        from scripts.paths import config_path as _csd_config  # noqa: E402
        config_path = _csd_config()
        if config_path.exists():
            try:
                with open(config_path) as f:
                    key = json.load(f).get("google_ai_api_key", "")
            except (json.JSONDecodeError, OSError):
                pass
    return key or None


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------

def resolve_platforms(platform_str):
    """Resolve a comma-separated platform string into a list of platform keys.

    Handles individual keys (ig-feed), group names (instagram), and 'all'.
    """
    if platform_str.strip().lower() == "all":
        return sorted(PLATFORMS.keys())

    keys = []
    for token in platform_str.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token in GROUPS:
            keys.extend(GROUPS[token])
        elif token in PLATFORMS:
            keys.append(token)
        else:
            print(json.dumps({"error": True, "message": f"Unknown platform '{token}'. Run 'social.py list' to see available platforms."}))
            sys.exit(1)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique


def group_by_ratio(platform_keys):
    """Group platform keys by their generation ratio.

    Returns dict: ratio -> list of platform keys.
    This avoids duplicate API calls for platforms sharing the same ratio.
    """
    groups = {}
    for key in platform_keys:
        ratio = PLATFORMS[key]["ratio"]
        groups.setdefault(ratio, []).append(key)
    return groups


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def generate_image(prompt, model, aspect_ratio, resolution, api_key, image_only=True):
    """Call Gemini API to generate an image. Returns (image_bytes, error_string)."""
    import urllib.request
    import urllib.error

    url = f"{API_BASE}/{model}:generateContent?key={api_key}"

    modalities = ["IMAGE"] if image_only else ["TEXT", "IMAGE"]
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": modalities,
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": resolution,
            },
        },
    }

    data = json.dumps(body).encode("utf-8")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            candidates = result.get("candidates", [])
            if not candidates:
                reason = result.get("promptFeedback", {}).get("blockReason", "No candidates")
                return None, f"No candidates: {reason}"

            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    return base64.b64decode(part["inlineData"]["data"]), None

            finish_reason = candidates[0].get("finishReason", "UNKNOWN")
            return None, f"No image in response. finishReason: {finish_reason}"

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 429 and attempt < max_retries - 1:
                wait = min(2 ** (attempt + 1), 32)
                print(f"  Rate limited (429). Waiting {wait}s... (attempt {attempt + 1}/{max_retries})", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 400 and "FAILED_PRECONDITION" in error_body:
                return None, "Billing not enabled. Enable at https://aistudio.google.com/apikey"
            return None, f"HTTP {e.code}: {error_body[:300]}"
        except urllib.error.URLError as e:
            return None, f"Network error: {e.reason}"

    return None, "Max retries exceeded"


# ---------------------------------------------------------------------------
# Platform-exact resize + crop (v4.1.0 — inspect source, resize to ratio, crop to spec)
# ---------------------------------------------------------------------------

def inspect_dimensions(path):
    """Return (width, height) of an image, or None if no inspection tool is available.

    Tries `magick identify` → `identify` (ImageMagick 6) → `sips` (macOS builtin) in order.
    """
    magick = shutil.which("magick")
    if magick:
        try:
            r = subprocess.run([magick, "identify", "-format", "%w %h", str(path)],
                               check=True, capture_output=True, text=True, timeout=10)
            parts = r.stdout.strip().split()
            if len(parts) >= 2:
                return int(parts[0]), int(parts[1])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
            pass

    identify = shutil.which("identify")
    if identify:
        try:
            r = subprocess.run([identify, "-format", "%w %h", str(path)],
                               check=True, capture_output=True, text=True, timeout=10)
            parts = r.stdout.strip().split()
            if len(parts) >= 2:
                return int(parts[0]), int(parts[1])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
            pass

    sips = shutil.which("sips")
    if sips:
        try:
            w = subprocess.run([sips, "-g", "pixelWidth", str(path)],
                               check=True, capture_output=True, text=True, timeout=5)
            h = subprocess.run([sips, "-g", "pixelHeight", str(path)],
                               check=True, capture_output=True, text=True, timeout=5)
            w_match = re.search(r"pixelWidth:\s*(\d+)", w.stdout)
            h_match = re.search(r"pixelHeight:\s*(\d+)", h.stdout)
            if w_match and h_match:
                return int(w_match.group(1)), int(h_match.group(1))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    return None


def resize_for_platform(input_path, output_path, target_w, target_h):
    """Produce an exact-dimension output matching a platform's upload spec.

    Pipeline:
      1. Inspect source dimensions
      2. Compare source ratio to target ratio
      3. If ratio matches (within 0.5%): pure downscale (sips or magick — both work)
      4. If ratio differs: resize-to-cover + center-crop (ImageMagick required)
      5. If no suitable tool for step 4: copy + emit missing_tool warning

    Returns dict:
      {
        "success": bool,
        "method": "resize_only" | "resize_and_crop" | "copy_fallback",
        "tool": "magick" | "convert" | "sips" | None,
        "source_dimensions": [w, h] | None,
        "output_dimensions": [w, h],
        "warning": str | None,
      }
    """
    target_ratio = target_w / target_h
    src_dims = inspect_dimensions(input_path)
    magick = shutil.which("magick") or shutil.which("convert")

    # Path A — ImageMagick available: handles both pure-resize and resize+crop
    if magick:
        cmd = [
            magick, str(input_path),
            "-resize", f"{target_w}x{target_h}^",
            "-gravity", "center",
            "-crop", f"{target_w}x{target_h}+0+0",
            "+repage",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            method = "resize_and_crop"
            if src_dims:
                src_ratio = src_dims[0] / src_dims[1]
                if abs(src_ratio - target_ratio) < 0.005:
                    method = "resize_only"  # ratio matched — 0 pixels cropped
            return {
                "success": True,
                "method": method,
                "tool": Path(magick).name,
                "source_dimensions": list(src_dims) if src_dims else None,
                "output_dimensions": [target_w, target_h],
                "warning": None,
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass  # fall through to sips attempt

    # Path B — no magick, but ratio matches and sips is available: pure downscale
    sips = shutil.which("sips")
    if sips and src_dims:
        src_ratio = src_dims[0] / src_dims[1]
        if abs(src_ratio - target_ratio) < 0.005:
            try:
                subprocess.run(
                    [sips, "--resampleHeightWidth", str(target_h), str(target_w),
                     str(input_path), "--out", str(output_path)],
                    check=True, capture_output=True, timeout=30,
                )
                return {
                    "success": True,
                    "method": "resize_only",
                    "tool": "sips",
                    "source_dimensions": list(src_dims),
                    "output_dimensions": [target_w, target_h],
                    "warning": "Used sips (ImageMagick unavailable). Same-ratio downscale only; ratio-change crops still need ImageMagick.",
                }
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                pass

    # Path C — full fallback: copy unchanged, emit structured missing-tool warning
    shutil.copy2(input_path, output_path)
    src_ratio_str = f" (source ratio ≠ target ratio)" if (
        src_dims and abs((src_dims[0] / src_dims[1]) - target_ratio) >= 0.005
    ) else ""
    return {
        "success": False,
        "method": "copy_fallback",
        "tool": None,
        "source_dimensions": list(src_dims) if src_dims else None,
        "output_dimensions": list(src_dims) if src_dims else None,  # unchanged!
        "warning": f"ImageMagick required for exact-dimension crop to {target_w}×{target_h}{src_ratio_str}. Install: brew install imagemagick",
    }


# Back-compat shim for any external caller still using the old name
def crop_image(input_path, output_path, target_w, target_h):
    """DEPRECATED: use resize_for_platform(). Returns bool for legacy callers."""
    return resize_for_platform(input_path, output_path, target_w, target_h)["success"]


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_generate(args):
    """Generate images for one or more social media platforms."""
    api_key = _load_api_key(args.api_key)
    if not api_key:
        print(json.dumps({"error": True, "message": "No API key. Run /create-image setup, set GOOGLE_AI_API_KEY env, or pass --api-key"}))
        sys.exit(1)

    platform_keys = resolve_platforms(args.platforms)
    if not platform_keys:
        print(json.dumps({"error": True, "message": "No platforms specified. Use --platforms ig-feed,yt-thumb or --platforms instagram"}))
        sys.exit(1)

    model = args.model or DEFAULT_MODEL
    # v4.1.2: default --mode is "complete" (text allowed). Explicit opt into
    # text-free via --mode image-only, which (a) sets responseModalities to
    # IMAGE only and (b) appends an explicit text-suppression clause to the
    # prompt so the model doesn't render typography in the output.
    image_only = args.mode == "image-only"

    # When image-only mode is active, append a suppression clause so the model
    # actually produces text-free output. Previously this was just a response-
    # modalities setting, which didn't affect whether the image contained text.
    effective_prompt = args.prompt
    if image_only:
        effective_prompt = (
            f"{args.prompt}\n\n"
            f"IMPORTANT: produce a clean image with NO text, NO logos, NO "
            f"typography, NO labels, NO captions. Pure visual content only."
        )

    # Output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output).resolve() if args.output else OUTPUT_DIR / f"social_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group platforms by ratio to minimize API calls
    ratio_groups = group_by_ratio(platform_keys)

    print(f"Generating for {len(platform_keys)} platform(s) across {len(ratio_groups)} unique ratio(s)...")
    print(f"  Model: {model}")
    print(f"  Mode: {'Image Only (text suppressed)' if image_only else 'Complete (text allowed — default in v4.1.2+)'}")
    print(f"  Output: {output_dir}")
    print()

    results = []
    generated_originals = {}  # ratio -> path to original file

    for ratio_idx, (ratio, keys) in enumerate(sorted(ratio_groups.items())):
        gen_w, gen_h = RATIO_4K_SIZES.get(ratio, (4096, 4096))
        platform_names = ", ".join(PLATFORMS[k]["name"] for k in keys)
        print(f"  [{ratio_idx + 1}/{len(ratio_groups)}] Generating {ratio} ({gen_w}x{gen_h}) for: {platform_names}...", end=" ", flush=True)

        image_data, error = generate_image(
            prompt=effective_prompt,
            model=model,
            aspect_ratio=ratio,
            resolution=DEFAULT_RESOLUTION,
            api_key=api_key,
            image_only=image_only,
        )

        if not image_data:
            print(f"FAILED: {error}")
            for k in keys:
                results.append({"platform": k, "name": PLATFORMS[k]["name"], "success": False, "error": error})
            continue

        # Save original (uncropped)
        safe_ratio = ratio.replace(":", "x")
        original_filename = f"original_{safe_ratio}_{timestamp}.png"
        original_path = output_dir / original_filename
        with open(original_path, "wb") as f:
            f.write(image_data)
        generated_originals[ratio] = str(original_path)
        print("OK")

        # Resize + crop for each platform in this ratio group
        for k in keys:
            spec = PLATFORMS[k]
            target_w, target_h = spec["pixels"]
            cropped_filename = f"{k}_{target_w}x{target_h}.png"
            cropped_path = output_dir / cropped_filename

            sizing = resize_for_platform(original_path, cropped_path, target_w, target_h)
            src_dims_str = f"{sizing['source_dimensions'][0]}x{sizing['source_dimensions'][1]}" if sizing["source_dimensions"] else "unknown"
            out_dims_str = f"{sizing['output_dimensions'][0]}x{sizing['output_dimensions'][1]}" if sizing["output_dimensions"] else "unchanged"
            method_label = {
                "resize_only":     f"resized {src_dims_str} → {out_dims_str} via {sizing['tool']}",
                "resize_and_crop": f"resized+cropped {src_dims_str} → {out_dims_str} via {sizing['tool']}",
                "copy_fallback":   f"COPIED UNCHANGED ({src_dims_str}) — missing_tool",
            }.get(sizing["method"], sizing["method"])
            print(f"    -> {k}: target {target_w}x{target_h} ({method_label})")
            if sizing["warning"]:
                print(f"       ⚠️  {sizing['warning']}")

            results.append({
                "platform": k,
                "name": spec["name"],
                "pixels": f"{target_w}x{target_h}",
                "ratio": ratio,
                "original": str(original_path),
                "cropped": str(cropped_path),
                "success": sizing["success"],
                "method": sizing["method"],
                "tool": sizing["tool"],
                "source_dimensions": sizing["source_dimensions"],
                "output_dimensions": sizing["output_dimensions"],
                "warning": sizing["warning"],
            })

        # Brief pause between ratio groups to avoid rate limits
        if ratio_idx < len(ratio_groups) - 1:
            time.sleep(1)

    # Summary
    succeeded = sum(1 for r in results if r["success"])
    failed = len(results) - succeeded

    print()
    print(f"Done! {succeeded}/{len(platform_keys)} platform images generated.")
    if failed:
        print(f"  {failed} failed -- check errors above.")
    print(f"  API calls made: {len(ratio_groups)} (one per unique ratio)")
    print(f"  Output: {output_dir}")

    # Write summary JSON
    summary = {
        "timestamp": timestamp,
        "prompt": args.prompt,
        "model": model,
        "mode": "complete" if not image_only else "image-only",
        "total_platforms": len(platform_keys),
        "succeeded": succeeded,
        "failed": failed,
        "api_calls": len(ratio_groups),
        "originals": generated_originals,
        "platforms": results,
    }
    summary_path = output_dir / "social-summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Machine-readable final output
    print(json.dumps({
        "success": True,
        "total": len(platform_keys),
        "succeeded": succeeded,
        "failed": failed,
        "api_calls": len(ratio_groups),
        "output_dir": str(output_dir),
        "summary": str(summary_path),
    }))


def cmd_list(args):
    """List all available platforms and groups."""
    print("Available platforms:")
    print()

    # Group by platform family
    families = {}
    for key, spec in sorted(PLATFORMS.items()):
        family = key.split("-")[0]
        families.setdefault(family, []).append((key, spec))

    for family, entries in families.items():
        family_label = {
            "ig": "Instagram", "fb": "Facebook", "yt": "YouTube",
            "li": "LinkedIn", "x": "Twitter/X", "tt": "TikTok",
            "pin": "Pinterest", "threads": "Threads", "snap": "Snapchat",
            "gads": "Google Ads", "spotify": "Spotify",
        }.get(family, family.upper())

        print(f"  {family_label}:")
        for key, spec in entries:
            w, h = spec["pixels"]
            print(f"    {key:<25} {w:>4}x{h:<4}  ({spec['ratio']})")
        print()

    print("Group shorthands:")
    for group, keys in sorted(GROUPS.items()):
        print(f"  {group:<15} -> {', '.join(keys)}")
    print()
    print(f"Total: {len(PLATFORMS)} platforms, {len(GROUPS)} groups")
    print()
    print("Use 'all' to generate for every platform.")


def cmd_info(args):
    """Show detailed info for a platform or group."""
    target = args.target.strip().lower()

    if target in GROUPS:
        print(f"Group: {target}")
        print(f"  Expands to: {', '.join(GROUPS[target])}")
        print()
        for key in GROUPS[target]:
            _print_platform_info(key)
        return

    if target in PLATFORMS:
        _print_platform_info(target)
        return

    print(json.dumps({"error": True, "message": f"Unknown platform or group '{target}'. Run 'social.py list' to see options."}))
    sys.exit(1)


def _print_platform_info(key):
    """Print detailed info for a single platform."""
    spec = PLATFORMS[key]
    w, h = spec["pixels"]
    gen_w, gen_h = RATIO_4K_SIZES.get(spec["ratio"], (4096, 4096))
    print(f"  {key}:")
    print(f"    Name:          {spec['name']}")
    print(f"    Pixels:        {w}x{h}")
    print(f"    Ratio:         {spec['ratio']}")
    print(f"    Generate at:   {gen_w}x{gen_h} (4K)")
    print(f"    Notes:         {spec['notes']}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Creators Studio Social Media Multi-Platform Image Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  social.py generate --prompt "a red sports car" --platforms ig-feed,yt-thumb
  social.py generate --prompt "product hero" --platforms instagram --mode complete
  social.py generate --prompt "sunset beach" --platforms all-feeds
  social.py list
  social.py info ig-feed
  social.py info instagram""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    p_gen = sub.add_parser("generate", help="Generate images for social media platforms")
    p_gen.add_argument("--prompt", required=True, help="Image generation prompt")
    p_gen.add_argument("--platforms", required=True,
                       help="Comma-separated platform keys, group names, or 'all'")
    p_gen.add_argument("--output", default=None, help="Output directory")
    p_gen.add_argument("--mode", choices=["complete", "image-only"], default="complete",
                       help="Output mode: complete (text allowed, DEFAULT in v4.1.2+) or image-only (explicitly suppresses text/logos/typography in the prompt). Social posts typically have text — the v4.1.1 image-only default was backwards.")
    p_gen.add_argument("--model", default=None, help=f"Model ID (default: {DEFAULT_MODEL})")
    p_gen.add_argument("--api-key", default=None, help="Google AI API key")

    # list
    sub.add_parser("list", help="List all available platforms and groups")

    # info
    p_info = sub.add_parser("info", help="Show details for a platform or group")
    p_info.add_argument("target", help="Platform key or group name")

    args = parser.parse_args()
    cmds = {"generate": cmd_generate, "list": cmd_list, "info": cmd_info}
    cmds[args.command](args)


if __name__ == "__main__":
    main()
