#!/usr/bin/env python3
"""Banana Claude -- Direct API Fallback: Image Generation

Generate images via Gemini REST API when MCP is unavailable.
Uses only Python stdlib (no pip dependencies).

Usage:
    generate.py --prompt "a cat in space" [--aspect-ratio 16:9] [--resolution 1K]
                [--model MODEL] [--api-key KEY] [--thinking LEVEL] [--image-only]
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_RESOLUTION = "2K"  # Must be uppercase -- lowercase values are silently rejected by the API
DEFAULT_RATIO = "1:1"
OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2",
                "4:5", "5:4", "1:4", "4:1", "1:8", "8:1", "21:9"}
VALID_RESOLUTIONS = {"512", "1K", "2K", "4K"}

# v3.6.3: MIME type detection for --reference-image inputs. Gemini
# image generation accepts PNG/JPEG/WebP/GIF reference images as
# inlineData parts alongside the text prompt. Three images is the
# practical limit — more than that confuses the model about which
# reference to prioritize.
MAX_REFERENCE_IMAGES = 3
REFERENCE_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _read_reference_image(path):
    """Read a reference image and return (base64_string, mime_type).

    Validates the file exists and the extension maps to a supported
    MIME type. Raises SystemExit with a clean JSON error on failure
    so the calling pipeline sees the same error format as other
    validation failures in this script.
    """
    p = Path(path)
    if not p.exists():
        print(json.dumps({"error": True, "message": f"Reference image not found: {path}"}))
        sys.exit(1)
    ext = p.suffix.lower()
    mime = REFERENCE_MIME_MAP.get(ext)
    if not mime:
        print(json.dumps({
            "error": True,
            "message": f"Unsupported reference-image format '{ext}'. Use: {', '.join(sorted(REFERENCE_MIME_MAP))}"
        }))
        sys.exit(1)
    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return data, mime


def generate_image(prompt, model, aspect_ratio, resolution, api_key,
                   thinking_level=None, image_only=False,
                   reference_images=None):
    """Call Gemini API to generate an image.

    v3.6.3: `reference_images` accepts a list of image file paths (up
    to MAX_REFERENCE_IMAGES). Each reference is attached to the request
    as an inlineData part alongside the text prompt. Gemini uses these
    as soft style/content guidance — they're not a strict composition
    lock (use /banana edit for that), they're a "generate a new image
    informed by these references" nudge. The primary use case is
    cross-shot character/product continuity in video sequences:
    generate a fresh frame that matches the character and wardrobe of
    a previous storyboard frame without locking the composition.
    """
    url = f"{API_BASE}/{model}:generateContent?key={api_key}"

    modalities = ["IMAGE"] if image_only else ["TEXT", "IMAGE"]

    # Build the parts list. Text prompt first, then reference images.
    # Ordering matters for Gemini: the text prompt establishes the
    # generation intent, and the reference images provide visual
    # anchors the model can draw from.
    parts = [{"text": prompt}]
    if reference_images:
        if len(reference_images) > MAX_REFERENCE_IMAGES:
            print(json.dumps({
                "error": True,
                "message": (
                    f"Too many reference images ({len(reference_images)}). "
                    f"Maximum is {MAX_REFERENCE_IMAGES}."
                ),
            }))
            sys.exit(1)
        for ref_path in reference_images:
            b64, mime = _read_reference_image(ref_path)
            parts.append({"inlineData": {"mimeType": mime, "data": b64}})

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": modalities,
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": resolution,
            },
        },
    }

    if thinking_level:
        body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking_level}

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    max_retries = 3
    result = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            break  # Success
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 429 and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(json.dumps({"retry": True, "attempt": attempt + 1, "wait_seconds": wait, "reason": "rate_limited"}), file=sys.stderr)
                time.sleep(wait)
                # Rebuild request for retry
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                continue
            if e.code == 400 and "FAILED_PRECONDITION" in error_body:
                print(json.dumps({"error": True, "status": 400, "message": "Billing not enabled. Enable billing at https://aistudio.google.com/apikey"}))
                sys.exit(1)
            print(json.dumps({"error": True, "status": e.code, "message": error_body}))
            sys.exit(1)
        except urllib.error.URLError as e:
            print(json.dumps({"error": True, "message": str(e.reason)}))
            sys.exit(1)

    if result is None:
        print(json.dumps({"error": True, "message": "Max retries exceeded"}))
        sys.exit(1)

    # Extract image from response
    candidates = result.get("candidates", [])
    if not candidates:
        finish_reason = result.get("promptFeedback", {}).get("blockReason", "UNKNOWN")
        print(json.dumps({"error": True, "message": f"No candidates returned. Reason: {finish_reason}"}))
        sys.exit(1)

    parts = candidates[0].get("content", {}).get("parts", [])
    image_data = None
    text_response = ""

    for part in parts:
        if "inlineData" in part:
            image_data = part["inlineData"]["data"]
        elif "text" in part:
            text_response = part["text"]

    if not image_data:
        finish_reason = candidates[0].get("finishReason", "UNKNOWN")
        print(json.dumps({"error": True, "message": f"No image in response. finishReason: {finish_reason}"}))
        sys.exit(1)

    # Save image
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"banana_{timestamp}.png"
    output_path = (OUTPUT_DIR / filename).resolve()

    with open(output_path, "wb") as f:
        f.write(base64.b64decode(image_data))

    result_dict = {
        "path": str(output_path),
        "model": model,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "text": text_response,
    }
    if reference_images:
        result_dict["reference_images"] = list(reference_images)
        result_dict["reference_count"] = len(reference_images)
        # v3.6.3 note: image-to-image (reference-guided) generation
        # returns roughly half-resolution output vs pure text-to-image
        # because Gemini's reference-guided path uses a different
        # upscale ladder. A 2K request may return ~1K-ish depending
        # on the aspect ratio. For VEO input this is acceptable (still
        # above the 720p floor), but worth knowing for final-delivery
        # workflows.
        result_dict["note"] = (
            "reference-guided generation returns ~1K-ish resolution "
            "regardless of --resolution request; this is expected "
            "Gemini behavior"
        )
    return result_dict


def main():
    parser = argparse.ArgumentParser(description="Generate images via Gemini REST API")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--aspect-ratio", default=DEFAULT_RATIO, help=f"Aspect ratio (default: {DEFAULT_RATIO})")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help=f"Resolution: 512, 1K, 2K, 4K (default: {DEFAULT_RESOLUTION})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--api-key", default=None, help="Google AI API key (or set GOOGLE_AI_API_KEY env)")
    parser.add_argument("--thinking", default=None, choices=["minimal", "low", "medium", "high"], help="Thinking level")
    parser.add_argument("--image-only", action="store_true", help="Return image only (no text)")
    parser.add_argument(
        "--reference-image", nargs="+", default=None,
        help=(
            "v3.6.3+: up to 3 reference image paths that guide the "
            "generation as soft style/content anchors. Attached as "
            "inlineData parts alongside the text prompt. Use for "
            "cross-shot character continuity (e.g. regenerate a "
            "frame that matches a previous storyboard shot's "
            "character and wardrobe). This is different from "
            "/banana edit — use edit.py when you want to modify an "
            "existing image; use --reference-image when you want to "
            "generate a fresh image informed by references. Note: "
            "reference-guided generation returns ~1K-ish output "
            "resolution regardless of --resolution request."
        ),
    )

    args = parser.parse_args()

    if args.aspect_ratio not in VALID_RATIOS:
        print(json.dumps({"error": True, "message": f"Invalid aspect ratio '{args.aspect_ratio}'. Valid: {sorted(VALID_RATIOS)}"}))
        sys.exit(1)

    if args.resolution not in VALID_RESOLUTIONS:
        print(json.dumps({"error": True, "message": f"Invalid resolution '{args.resolution}'. Valid: {sorted(VALID_RESOLUTIONS)}"}))
        sys.exit(1)

    api_key = args.api_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Try ~/.banana/config.json
        config_path = Path.home() / ".banana" / "config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    api_key = json.load(f).get("google_ai_api_key", "")
            except (json.JSONDecodeError, OSError):
                pass
    if not api_key:
        print(json.dumps({"error": True, "message": "No API key. Run /banana setup, set GOOGLE_AI_API_KEY env, or pass --api-key"}))
        sys.exit(1)

    # v3.6.3: validate reference image count early so the error fires
    # before any API calls instead of mid-request.
    if args.reference_image and len(args.reference_image) > MAX_REFERENCE_IMAGES:
        print(json.dumps({
            "error": True,
            "message": (
                f"Too many --reference-image paths ({len(args.reference_image)}). "
                f"Maximum is {MAX_REFERENCE_IMAGES}."
            ),
        }))
        sys.exit(1)

    result = generate_image(
        prompt=args.prompt,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        api_key=api_key,
        thinking_level=args.thinking,
        image_only=args.image_only,
        reference_images=args.reference_image,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
