#!/usr/bin/env python3
"""Banana Claude -- Social Media Multi-Platform Image Generator

Generate images optimized for 45+ social media placements from a single prompt.
Groups platforms by aspect ratio to avoid duplicate API calls, generates at 4K,
and crops to exact platform pixels with ImageMagick.

Uses only Python stdlib (no pip dependencies).

Usage:
    social.py generate --prompt "a cat in space" --platforms ig-feed,yt-thumb
    social.py generate --prompt "product hero" --platforms instagram,youtube --mode complete
    social.py list
    social.py info ig-feed
    social.py info instagram
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

# PLATFORMS dict — 6 platforms, 38 placements, max-quality specs (v4.1.1+)
#
# Scope narrowed from 11 platforms (v4.0.x) to 6 (Instagram, Facebook, YouTube,
# LinkedIn, Twitter/X, TikTok) in v4.1.1 to reflect honest coverage — the
# previous 46 "platforms" were actually 46 placements across 11 prefixes
# with shallow (2-3 placement) coverage on Pinterest, Threads, Snapchat,
# Google Ads, Spotify.
#
# All pixel specs upgraded to SOP-recommended MAX-QUALITY values, not minimum
# platform requirements. Authoritative source for every spec below is:
# dev-docs/SOP Graphic Sizes - Social Media Image and Video Specifications Guide.md
# (January 2026 update).
#
# Key upgrades from v4.0.x → v4.1.1:
# - yt-thumb:        1280×720  → 3840×2160  (9× pixel count, 4K quality)
# - ig-profile:       320×320  → 720×720    (quality-recommended spec)
# - fb-profile:       (new)    → 720×720    (quality-recommended spec)
# - fb-ad:          1080×1080  → 1440×1800  (SOP premium feed ad)
# - fb-story-ad:    1080×1920  → 1440×2560  (SOP premium story ad)
# - ig-story-ad:    1080×1920  → 1440×2560  (SOP premium story ad — new key)
# - x-header:       3:2 ratio  → 3:1 ratio  (bug fix; 1500/500 = 3:1)
# - x-landscape:   1600×900    → 1200×675   (SOP-correct single-image feed spec)
# - x-ad:          1600×900    → 800×800    (SOP-correct image ad spec)

PLATFORMS = {
    # ═══ Instagram (8 placements) ═══════════════════════════════════════════
    "ig-profile":           {"name": "Instagram Profile Picture",       "pixels": (720, 720),   "ratio": "1:1",  "resolution": "4K", "notes": "Circular crop -- keep subject in center 70%. SOP-recommended 720x720 (was 320x320 minimum in v4.0.x)."},
    "ig-feed":              {"name": "Instagram Feed Portrait",         "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "Preferred organic feed format. Bottom 20% may be obscured by caption overlay."},
    "ig-square":            {"name": "Instagram Feed Square",           "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Center subject; edges may clip on older devices."},
    "ig-landscape":         {"name": "Instagram Feed Landscape",        "pixels": (1080, 566),  "ratio": "16:9", "resolution": "4K", "notes": "1.91:1 crop from 16:9 source."},
    "ig-story":             {"name": "Instagram Story / Reel",          "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Top 14% and bottom 35% reserved for UI (safe zones)."},
    "ig-reel-cover":        {"name": "Instagram Reel Cover (full)",     "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Full reel cover image. Center of frame is the visible thumbnail."},
    "ig-reel-cover-grid":   {"name": "Instagram Reel Grid Thumbnail",   "pixels": (1080, 1440), "ratio": "3:4",  "resolution": "4K", "notes": "Profile-grid display variant of the reel cover."},
    "ig-story-ad":          {"name": "Instagram Story Ad (premium)",    "pixels": (1440, 2560), "ratio": "9:16", "resolution": "4K", "notes": "SOP premium quality spec for Stories Ads (1440x2560, not 1080x1920)."},

    # ═══ Facebook (8 placements) ═════════════════════════════════════════════
    "fb-profile":           {"name": "Facebook Profile Picture",        "pixels": (720, 720),   "ratio": "1:1",  "resolution": "4K", "notes": "SOP quality spec 720x720 (displays 176x176 desktop, 196x196 mobile)."},
    "fb-cover":             {"name": "Facebook Cover Photo",            "pixels": (851, 315),   "ratio": "21:9", "resolution": "4K", "notes": "Design-size 851x315; desktop displays 820x312, mobile 640x360. Safe zone is center 640x312."},
    "fb-feed":              {"name": "Facebook Feed Square",            "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Organic square post."},
    "fb-landscape":         {"name": "Facebook Feed Landscape",         "pixels": (1200, 630),  "ratio": "16:9", "resolution": "4K", "notes": "1.91:1 — link preview crops tighter."},
    "fb-portrait":          {"name": "Facebook Feed Portrait",          "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "Truncated in feed with See More."},
    "fb-story":             {"name": "Facebook Story / Reel",           "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Top 14% profile bar; bottom 20% CTA."},
    "fb-ad":                {"name": "Facebook Feed Ad (premium)",      "pixels": (1440, 1800), "ratio": "4:5",  "resolution": "4K", "notes": "SOP premium feed ad spec 1440x1800 (was 1080x1080 in v4.0.x). Bottom 20% ad copy overlay."},
    "fb-story-ad":          {"name": "Facebook Story Ad (premium)",     "pixels": (1440, 2560), "ratio": "9:16", "resolution": "4K", "notes": "SOP premium story/reel ad spec 1440x2560. Safe zones top 360px, bottom 900px."},

    # ═══ YouTube (4 placements) ══════════════════════════════════════════════
    "yt-profile":           {"name": "YouTube Channel Icon",            "pixels": (800, 800),   "ratio": "1:1",  "resolution": "4K", "notes": "Displays as circle at 98x98."},
    "yt-thumb":             {"name": "YouTube Thumbnail (4K)",          "pixels": (3840, 2160), "ratio": "16:9", "resolution": "4K", "notes": "4K max-quality upload per v4.1.1 (was 1280x720 minimum in v4.0.x). YouTube supports up to 50MB for 4K thumbnails. Bottom-right has timestamp overlay."},
    "yt-banner":            {"name": "YouTube Channel Banner",          "pixels": (2560, 1440), "ratio": "16:9", "resolution": "4K", "notes": "Safe zone is center 1546x423 for visibility across all devices."},
    "yt-shorts":            {"name": "YouTube Shorts Cover",            "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Center subject; top/bottom cropped in browse."},

    # ═══ LinkedIn (9 placements) ═════════════════════════════════════════════
    "li-profile":           {"name": "LinkedIn Profile Picture",        "pixels": (400, 400),   "ratio": "1:1",  "resolution": "4K", "notes": "Displays as circle. Also company logo spec."},
    "li-banner":            {"name": "LinkedIn Banner",                 "pixels": (1584, 396),  "ratio": "4:1",  "resolution": "4K", "notes": "Keep subject in center band."},
    "li-landscape":         {"name": "LinkedIn Feed Landscape",         "pixels": (1200, 627),  "ratio": "16:9", "resolution": "4K", "notes": "1.91:1 standard share image."},
    "li-portrait":          {"name": "LinkedIn Feed Portrait",          "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "Truncated in feed; top portion most visible."},
    "li-square":            {"name": "LinkedIn Feed Square",            "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Safe choice for LinkedIn."},
    "li-carousel":          {"name": "LinkedIn Carousel Slide",         "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Keep margins; swipe arrows overlay edges."},
    "li-carousel-portrait": {"name": "LinkedIn Carousel Portrait",      "pixels": (1080, 1350), "ratio": "4:5",  "resolution": "4K", "notes": "More vertical real estate for document-style carousels."},
    "li-ad":                {"name": "LinkedIn Single Image Ad",        "pixels": (1200, 628),  "ratio": "16:9", "resolution": "4K", "notes": "SOP single image ad spec (also supports 1200x1200 square)."},
    "li-video-ad-frame":    {"name": "LinkedIn Video Ad Still",         "pixels": (1920, 1080), "ratio": "16:9", "resolution": "4K", "notes": "Video ad thumbnail / still frame at 1080p."},

    # ═══ Twitter/X (6 placements) ════════════════════════════════════════════
    "x-profile":            {"name": "Twitter/X Profile Picture",       "pixels": (400, 400),   "ratio": "1:1",  "resolution": "4K", "notes": "Circular display."},
    "x-header":             {"name": "Twitter/X Header Banner",         "pixels": (1500, 500),  "ratio": "21:9", "resolution": "4K", "notes": "v4.1.1 FIX: was incorrectly labeled 3:2 in v4.0.x. True target aspect is 3:1 (1500/500 = 3.0); Gemini generates at 21:9 (2.33:1, closest supported ratio) then crops ~11% vertical to exact 3:1. Safe zone: 100px buffer top/bottom; profile photo overlaps bottom-left."},
    "x-landscape":          {"name": "Twitter/X Feed Landscape",        "pixels": (1200, 675),  "ratio": "16:9", "resolution": "4K", "notes": "v4.1.1 CORRECTED to SOP spec (was 1600x900 in v4.0.x). Crops from center on mobile."},
    "x-square":             {"name": "Twitter/X Feed Square",           "pixels": (1080, 1080), "ratio": "1:1",  "resolution": "4K", "notes": "Displayed with slight letterboxing on some devices."},
    "x-ad":                 {"name": "Twitter/X Image Ad",              "pixels": (800, 800),   "ratio": "1:1",  "resolution": "4K", "notes": "v4.1.1 CORRECTED to SOP spec 800x800 1:1 (was 1600x900 16:9 in v4.0.x). SOP also allows 800x418 (1.91:1)."},
    "x-video-ad-frame":     {"name": "Twitter/X Video Ad Still",        "pixels": (1920, 1080), "ratio": "16:9", "resolution": "4K", "notes": "Video ad thumbnail / still frame at 1080p (SOP: 1920x1080 16:9 or 1200x1200 1:1 accepted)."},

    # ═══ TikTok (3 placements) ═══════════════════════════════════════════════
    "tt-profile":           {"name": "TikTok Profile Picture",          "pixels": (720, 720),   "ratio": "1:1",  "resolution": "4K", "notes": "Displays at 200x200 but upload at 720x720 for quality."},
    "tt-feed":              {"name": "TikTok Feed / Cover",             "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "9:16 preferred. Avoid top and bottom 120 pixels due to UI overlays."},
    "tt-ad":                {"name": "TikTok In-Feed / TopView Ad",     "pixels": (1080, 1920), "ratio": "9:16", "resolution": "4K", "notes": "Both in-feed ads and TopView ads use same 1080x1920 9:16 spec at SOP-recommended quality."},
}

# Group shorthands expand to multiple platform keys (v4.1.1: 6 platforms)
GROUPS = {
    "instagram":    ["ig-feed", "ig-square", "ig-story", "ig-reel-cover"],
    "facebook":     ["fb-feed", "fb-landscape", "fb-portrait", "fb-story"],
    "youtube":      ["yt-thumb", "yt-banner", "yt-shorts"],
    "linkedin":     ["li-landscape", "li-square", "li-portrait", "li-banner"],
    "twitter":      ["x-landscape", "x-square", "x-header"],
    "tiktok":       ["tt-feed"],
    # Cross-platform family groups — useful for multi-channel campaigns
    "all-feeds":    ["ig-feed", "fb-portrait", "li-portrait", "x-landscape"],
    "all-squares":  ["ig-square", "fb-feed", "li-square", "x-square"],
    "all-stories":  ["ig-story", "fb-story", "tt-feed"],
    "all-ads":      ["fb-ad", "fb-story-ad", "ig-story-ad", "li-ad", "x-ad", "tt-ad"],
    "all-profiles": ["ig-profile", "fb-profile", "yt-profile", "li-profile", "x-profile", "tt-profile"],
    "all-banners":  ["fb-cover", "yt-banner", "li-banner", "x-header"],
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
        config_path = Path.home() / ".banana" / "config.json"
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
    image_only = args.mode != "complete"

    # Output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output).resolve() if args.output else OUTPUT_DIR / f"social_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group platforms by ratio to minimize API calls
    ratio_groups = group_by_ratio(platform_keys)

    print(f"Generating for {len(platform_keys)} platform(s) across {len(ratio_groups)} unique ratio(s)...")
    print(f"  Model: {model}")
    print(f"  Mode: {'Complete (with text)' if not image_only else 'Image Only'}")
    print(f"  Output: {output_dir}")
    print()

    results = []
    generated_originals = {}  # ratio -> path to original file

    for ratio_idx, (ratio, keys) in enumerate(sorted(ratio_groups.items())):
        gen_w, gen_h = RATIO_4K_SIZES.get(ratio, (4096, 4096))
        platform_names = ", ".join(PLATFORMS[k]["name"] for k in keys)
        print(f"  [{ratio_idx + 1}/{len(ratio_groups)}] Generating {ratio} ({gen_w}x{gen_h}) for: {platform_names}...", end=" ", flush=True)

        image_data, error = generate_image(
            prompt=args.prompt,
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
        description="Banana Claude Social Media Multi-Platform Image Generator",
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
    p_gen.add_argument("--mode", choices=["complete", "image-only"], default="image-only",
                       help="Output mode: complete (with text) or image-only (default)")
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
