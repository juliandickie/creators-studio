#!/usr/bin/env python3
"""Creators Studio -- Raster to SVG vectorization via Recraft Vectorize (v4.1.0+)

Converts a generated PNG/JPG/WEBP logo or icon into a clean, editable SVG
with scalable vector paths. Closes the gap where Gemini-generated logos
distort when scaled up — SVG output is resolution-independent and works
with Illustrator / Figma / Sketch.

Typical workflow (two-step, pairs with /create-image generate):

    # Step 1 — generate a logo with Gemini
    /create-image generate "minimalist geometric logo for a tech startup,
    single color, clean lines, negative space, isolated on pure white"

    # Step 2 — vectorize the output
    python3 vectorize.py --image ~/Documents/creators_generated/logo.png

Uses only Python stdlib via plugin-root scripts/backends/_replicate.py
helpers (v4.2.0+). Zero pip deps.

See:
- skills/create-image/references/vectorize.md (reference doc)
- dev-docs/recraft-ai-recraft-vectorize-llms.md (authoritative model card)

Pricing: $0.01 per output image (flat fee, confirmed 2026-04-17).
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Cross-skill import of the shared Replicate backend helper.
# Path: skills/create-image/scripts/vectorize.py →
#       scripts/backends/_replicate.py   (as of v4.2.0 — plugin-root)
# Prior to v4.2.0 this reached into skills/create-video/scripts/ via a
# cross-skill shim. The shared provider abstraction now lives at plugin
# root so both skills can import without cross-skill path reach-through.
_plugin_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)
from scripts.backends import _replicate as replicate  # noqa: E402


# ─── Constants ──────────────────────────────────────────────────────

RECRAFT_MODEL_SLUG = "recraft-ai/recraft-vectorize"
DEFAULT_POLL_INTERVAL = 5         # fast operation — poll more often than video
DEFAULT_MAX_WAIT = 180            # typical completion ~10-30s; 3min is plenty
OUTPUT_DIR = Path.home() / "Documents" / "creators_generated"


# ─── Progress + error helpers (mirror video_lipsync.py) ─────────────

def _error_exit(message):
    """Print JSON error to stdout and exit 1."""
    print(json.dumps({"error": True, "message": message}))
    sys.exit(1)


def _progress(data):
    """Print progress JSON to stderr."""
    print(json.dumps(data), file=sys.stderr)


# ─── Recraft API flow ───────────────────────────────────────────────

def _submit_recraft(*, image_uri, token):
    """Submit a Recraft Vectorize prediction and return the poll URL."""
    body = replicate.build_recraft_request_body(image=image_uri)
    url = replicate.build_predictions_url(RECRAFT_MODEL_SLUG)

    _progress({
        "status": "submitting",
        "backend": "replicate",
        "model": RECRAFT_MODEL_SLUG,
    })

    try:
        result = replicate.replicate_post(url, body, token=token, timeout=60)
        prediction_id, poll_url = replicate.parse_replicate_submit_response(result)
    except replicate.ReplicateBackendError as e:
        _error_exit(f"Recraft submit failed: {e}")

    _progress({
        "status": "submitted",
        "backend": "replicate",
        "prediction_id": prediction_id,
    })
    return poll_url


def _poll_recraft(poll_url, token, interval, max_wait):
    """Poll the Recraft prediction URL until terminal state.

    Returns the output SVG URL on success. Exits with error on
    failed / canceled / aborted / timeout.
    """
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            _error_exit(
                f"Timeout: Recraft prediction not done after {max_wait}s. "
                f"Poll URL: {poll_url}"
            )

        try:
            result = replicate.replicate_get(poll_url, token=token, timeout=30)
            status, payload = replicate.parse_replicate_poll_response(result)
        except replicate.ReplicateBackendError as e:
            _error_exit(f"Recraft poll failed: {e}")

        if status == "running":
            _progress({
                "polling": True,
                "backend": "replicate",
                "elapsed": int(elapsed),
                "status": "processing",
            })
            time.sleep(interval)
            continue

        if status == "done":
            # Recraft output is a single URI string per the model card.
            # Defensively handle list shape for forward-compat.
            if isinstance(payload, list):
                payload = payload[0] if payload else None
            if not payload:
                _error_exit("Recraft prediction succeeded but output is empty.")
            return payload

        # status == "failed" (covers failed | canceled | aborted)
        err_str = str(payload) if payload else "unknown error"
        _error_exit(f"Recraft prediction failed: {err_str}")


def _download_svg(output_url, output_path):
    """Download the SVG file from the Recraft output URL."""
    _progress({
        "status": "downloading",
        "backend": "replicate",
        "url": output_url,
    })

    try:
        req = urllib.request.Request(
            output_url,
            headers={"User-Agent": replicate.REPLICATE_USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        _error_exit(f"Failed to download Recraft SVG: {e}")

    return str(output_path)


# ─── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Vectorize a raster image to SVG via Recraft Vectorize",
    )
    parser.add_argument(
        "--image", required=True,
        help="Raster image to vectorize (PNG, JPG, or WEBP). "
             "Constraints: ≤5 MB, 256-4096 px on each side, ≤16 MP. "
             "Best results on logos, icons, and clean flat designs.",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output SVG path. Defaults to "
             "~/Documents/creators_generated/<input_stem>.svg",
    )
    parser.add_argument(
        "--replicate-key", default=None,
        help="Replicate API token. Loads from REPLICATE_API_TOKEN env var "
             "or ~/.banana/config.json replicate_api_token field if unset.",
    )
    parser.add_argument(
        "--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between polls (default: {DEFAULT_POLL_INTERVAL})",
    )
    parser.add_argument(
        "--max-wait", type=int, default=DEFAULT_MAX_WAIT,
        help=f"Max wait seconds (default: {DEFAULT_MAX_WAIT})",
    )

    args = parser.parse_args()

    # ── Validation ──
    image_path = Path(args.image).expanduser().resolve()
    if not image_path.is_file():
        _error_exit(f"Input image not found: {image_path}")

    # Let the backend's validator enforce size + format (belt + suspenders).
    try:
        image_uri = replicate.recraft_image_path_to_data_uri(image_path)
    except replicate.ReplicateValidationError as e:
        _error_exit(str(e))

    # Resolve output path
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = (OUTPUT_DIR / f"{image_path.stem}.svg").resolve()

    # ── Credentials ──
    try:
        creds = replicate.load_replicate_credentials(cli_token=args.replicate_key)
    except replicate.ReplicateAuthError as e:
        _error_exit(str(e))

    _progress({
        "status": "backend_selected",
        "backend": "replicate",
        "model": RECRAFT_MODEL_SLUG,
    })

    # ── Submit + poll + download ──
    gen_start = time.time()

    poll_url = _submit_recraft(
        image_uri=image_uri,
        token=creds["api_token"],
    )

    output_url = _poll_recraft(
        poll_url=poll_url,
        token=creds["api_token"],
        interval=args.poll_interval,
        max_wait=args.max_wait,
    )

    saved_path = _download_svg(output_url, output_path)
    gen_time = round(time.time() - gen_start, 1)

    result = {
        "path": saved_path,
        "model": RECRAFT_MODEL_SLUG,
        "source_image": str(image_path),
        "source_size_bytes": image_path.stat().st_size,
        "generation_time_seconds": gen_time,
        "backend": "replicate",
        "cost_usd": 0.01,
    }
    print(json.dumps(result, indent=2))

    # Log cost to ~/.banana/costs.json. Shell out to cost_tracker.py for
    # consistency with video_generate.py / video_lipsync.py. Best-effort;
    # never block output on cost-logging failure.
    try:
        _cost_tracker = str(Path(__file__).resolve().parent / "cost_tracker.py")
        _prompt_summary = f"vectorize: {image_path.name}"
        subprocess.run(
            [sys.executable, _cost_tracker, "log",
             "--model", RECRAFT_MODEL_SLUG,
             "--resolution", "N/A",
             "--prompt", _prompt_summary],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
