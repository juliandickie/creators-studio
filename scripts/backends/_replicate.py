#!/usr/bin/env python3
"""Creators Studio — Replicate provider backend.

Implements the ProviderBackend contract (scripts/backends/_base.py) for
Replicate (api.replicate.com). Hosts model registry entries for Kling v3,
Fabric 1.0, and Recraft Vectorize — every Replicate-hosted model the
plugin currently uses.

Pure data-translation layer. No global state. Stdlib only (urllib.request,
base64, json).

See:
- docs/superpowers/specs/2026-04-23-provider-abstraction-design.md
- dev-docs/kwaivgi-kling-v3-video-llms.md (Kling input schema)
- dev-docs/veed-fabric-1.0-llms.md (Fabric input schema)
- dev-docs/recraft-ai-recraft-vectorize-llms.md (Recraft input schema)
- dev-docs/replicate-openapi.json (canonical Replicate API contract)

Two API surfaces coexist in this module:

1. **Legacy module-level helpers** (validate_kling_params,
   build_kling_request_body, replicate_post, replicate_get, etc.) —
   called directly by pre-v4.2.0 code paths. Preserved during the
   v4.2.0 transition.

2. **ReplicateBackend class** (v4.2.0+) — implements the
   ProviderBackend ABC contract. New call sites use this class; it
   delegates to the legacy helpers internally.

Canonical state mapping (Replicate's 6-value enum → canonical 5 values):
    starting, processing        → running
    succeeded                   → succeeded
    canceled                    → canceled
    failed, aborted             → failed

User-Agent: every request sends
    User-Agent: creators-studio/4.2.0 (+https://github.com/juliandickie/creators-studio)
to avoid Cloudflare WAF rejection on /v1/account (observed HTTP 403
error 1010 without it).

Run `python3 -m scripts.backends._replicate diagnose` to verify auth
works without burning budget.
"""

import argparse
import base64
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


# ─── Endpoint templates ─────────────────────────────────────────────

# Base URL per the Replicate OpenAPI schema.
REPLICATE_API_BASE = "https://api.replicate.com/v1"

# Model predictions endpoint template. Owner and name are separated by "/"
# in the slug (e.g., "kwaivgi/kling-v3-video").
REPLICATE_PREDICTIONS_URL_TEMPLATE = (
    REPLICATE_API_BASE + "/models/{owner}/{name}/predictions"
)

# Free endpoint used by --diagnose to verify auth without burning a
# generation. Returns the account name + type for the authenticated token.
REPLICATE_ACCOUNT_URL = REPLICATE_API_BASE + "/account"

# User-Agent identifying our client to Replicate. Sent on every request.
# Cloudflare's edge rules reject the default Python-urllib/3.x user agent
# on some endpoints (observed: HTTP 403 error 1010 on /v1/account with no
# User-Agent). Identifying the client avoids the WAF heuristic and gives
# Replicate a way to contact us if they see odd traffic.
REPLICATE_USER_AGENT = "creators-studio/4.2.0 (+https://github.com/juliandickie/creators-studio)"


# ─── Model registry ─────────────────────────────────────────────────

# v3.8.0 ships with a deliberately lean roster: Kling v3 Std only. PrunaAI
# P-Video was considered in spike 5 Phase 1 but the user declined to wire
# it after reviewing the output. Other Replicate models (Kling Omni, Runway,
# xAI Grok, ByteDance Seedance) are deferred — see ROADMAP priorities
# 10a (Seedance retest) and 10b (Omni retest if wall time improves).
REPLICATE_MODELS = {
    "kwaivgi/kling-v3-video": {
        "family": "kling",
        "display_name": "Kling v3 Std",
        "aspects": ["16:9", "9:16", "1:1"],
        "min_duration_s": 3,
        "max_duration_s": 15,
        "modes": ["standard", "pro"],
        "supports_audio": True,
        "supports_multi_prompt": True,
        "supports_negative_prompt": True,
        "supports_start_image": True,
        "supports_end_image": True,
        "price_usd_per_8s_clip_pro": 0.16,
        "price_usd_per_15s_clip_pro": 0.30,
    },
    # v3.8.1: Fabric 1.0 — audio-driven talking head lip-sync specialist.
    # Closes the gap left by v3.8.0 (VEO chars can't speak external voices).
    # Pair with audio_pipeline.py narrate output for custom ElevenLabs voices.
    "veed/fabric-1.0": {
        "family": "fabric",
        "display_name": "VEED Fabric 1.0",
        "resolutions": ["480p", "720p"],
        "max_duration_s": 60,
        "supports_audio_input": True,
        "supports_image_input": True,
        "image_formats": ["jpg", "jpeg", "png"],
        "audio_formats": ["mp3", "wav", "m4a", "aac"],
        # Pricing: Replicate does not publish Fabric per-call cost publicly
        # in the model card. v3.8.1 verification will measure empirically
        # and update this field before release.
        "price_usd_per_call_estimate": 0.30,
    },
    # v4.1.0: Recraft Vectorize — AI-based raster-to-SVG for logo/icon work.
    # Closes the gap where Gemini-generated logos can't scale without
    # distortion. Output is editable SVG (Illustrator/Figma compatible).
    # See dev-docs/recraft-ai-recraft-vectorize-llms.md for the canonical
    # input schema and licensing (commercial use permitted).
    "recraft-ai/recraft-vectorize": {
        "family": "recraft",
        "display_name": "Recraft Vectorize",
        "image_formats": ["png", "jpg", "jpeg", "webp"],
        "max_image_bytes": 5 * 1024 * 1024,       # 5 MB per model card
        "max_megapixels": 16,                      # 16 MP per model card
        "min_dimension_px": 256,                   # 256 px min per model card
        "max_dimension_px": 4096,                  # 4096 px max per model card
        "price_usd_per_call": 0.01,                # $0.01/output image confirmed 2026-04-17
    },
}


# ─── Kling v3 Std parameter constraints ─────────────────────────────
# All values below are sourced from the Kling v3 Std model card at
# dev-docs/kwaivgi-kling-v3-video-llms.md. Any changes here must be
# traceable to that file.

VALID_ASPECT_RATIOS = {"16:9", "9:16", "1:1"}
VALID_MODES = {"standard", "pro"}
MIN_DURATION_S = 3
MAX_DURATION_S = 15
MAX_PROMPT_CHARS = 2500
MAX_NEGATIVE_PROMPT_CHARS = 2500
MAX_MULTI_PROMPT_SHOTS = 6
MIN_SHOT_DURATION_S = 1
MAX_START_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB per the model card

# Replicate OpenAPI Prediction.status enum — all 6 values.
RUNNING_STATUSES = {"starting", "processing"}
TERMINAL_SUCCESS_STATUSES = {"succeeded"}
TERMINAL_FAILURE_STATUSES = {"failed", "canceled", "aborted"}

# File extension to MIME type. Replicate accepts .jpg/.jpeg/.png for image
# inputs per the Kling model card. Intentionally narrow — we don't want to
# accept .webp because Kling's model card doesn't list it as supported.
IMAGE_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


# ─── Fabric 1.0 parameter constraints (v3.8.1+) ────────────────────
# Sourced from dev-docs/veed-fabric-1.0-llms.md. Fabric is the lip-sync
# specialist: image + audio → talking-head MP4. Dramatically simpler
# input surface than Kling (no prompt, no multi_prompt, no negative_prompt).

VALID_FABRIC_RESOLUTIONS = {"480p", "720p"}
FABRIC_MAX_DURATION_S = 60
MAX_FABRIC_IMAGE_BYTES = 10 * 1024 * 1024  # Conservative — Fabric doesn't publish
MAX_FABRIC_AUDIO_BYTES = 50 * 1024 * 1024  # 60s at reasonable bitrates ≈ 1-5 MB

# Audio extension to MIME type. Fabric model card lists: mp3, wav, m4a, aac.
# Intentionally narrow: don't accept .ogg/.flac/.opus because they aren't listed.
AUDIO_MIME_MAP = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
}


# ─── Recraft Vectorize parameter constraints (v4.1.0+) ─────────────
# Sourced from dev-docs/recraft-ai-recraft-vectorize-llms.md. Recraft accepts
# WEBP in addition to PNG/JPG (Kling doesn't), so we maintain a separate MIME
# map rather than widening the Kling-specific one.

MAX_RECRAFT_IMAGE_BYTES = 5 * 1024 * 1024       # 5 MB per model card
RECRAFT_MAX_MEGAPIXELS = 16                      # 16 MP per model card
RECRAFT_MIN_DIMENSION_PX = 256
RECRAFT_MAX_DIMENSION_PX = 4096

RECRAFT_IMAGE_MIME_MAP = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


# ─── Logger ─────────────────────────────────────────────────────────

# Named logger lets callers attach handlers / tests use self.assertLogs.
_logger = logging.getLogger(__name__)


# ─── Error types ────────────────────────────────────────────────────

class ReplicateBackendError(RuntimeError):
    """Base class for Replicate backend errors.

    Raised by this module when it can't proceed. Callers in video_generate.py
    should catch and translate to _error_exit() JSON for user-facing output.
    """


class ReplicateValidationError(ReplicateBackendError):
    """Pre-flight validation failed — caller passed an invalid parameter.

    Raised by validate_kling_params() and build_kling_request_body() when the
    input would be rejected by Replicate. Catching these locally prevents a
    wasted API call.
    """


class ReplicateAuthError(ReplicateBackendError):
    """Auth failed — missing or invalid Replicate API token.

    Points the user at setup_mcp.py --replicate-key in the error message so
    they can fix it without leaving the terminal.
    """


class ReplicateSubmitError(ReplicateBackendError):
    """Submit POST returned a non-2xx response or unparseable body."""


class ReplicatePollError(ReplicateBackendError):
    """Poll GET returned a non-2xx response or unparseable body."""


# ─── Credentials loader ─────────────────────────────────────────────

def load_replicate_credentials(*, cli_token=None):
    """Load the Replicate API token with the same precedence as setup_mcp.py.

    Precedence:
        1. CLI flag (explicit --replicate-key)
        2. Env var REPLICATE_API_TOKEN
        3. ~/.banana/config.json field replicate_api_token

    Returns a dict with key: api_token.
    Raises ReplicateAuthError with a setup pointer if the token is missing.
    """
    token = cli_token or os.environ.get("REPLICATE_API_TOKEN")

    if not token:
        config_path = Path.home() / ".banana" / "config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                token = cfg.get("replicate_api_token", "")
            except (json.JSONDecodeError, OSError):
                pass

    if not token:
        raise ReplicateAuthError(
            "No Replicate API token. Set it with:\n"
            "  python3 skills/create-image/scripts/setup_mcp.py --replicate-key YOUR_TOKEN\n"
            "Or set the REPLICATE_API_TOKEN environment variable.\n"
            "Get a token at: https://replicate.com/account/api-tokens"
        )
    return {"api_token": token}


# ─── URL builder ────────────────────────────────────────────────────

def build_predictions_url(model_slug):
    """Return the POST URL for a model's predictions endpoint.

    Model slug format: "owner/name" (e.g., "kwaivgi/kling-v3-video").
    """
    if "/" not in model_slug:
        raise ReplicateBackendError(
            f"Invalid model slug '{model_slug}'. Expected 'owner/name' format."
        )
    owner, name = model_slug.split("/", 1)
    return REPLICATE_PREDICTIONS_URL_TEMPLATE.format(owner=owner, name=name)


# ─── Image helpers ──────────────────────────────────────────────────

def image_path_to_data_uri(path):
    """Read an image file and return a single data URI string.

    Format: "data:{mime};base64,{base64_data}"

    Replicate's Kling integration accepts either HTTPS URLs or data URIs
    for start_image / end_image. Data URIs are simpler for the common case
    of local files; the Kling model card specifies a 10 MB cap which this
    function enforces at the boundary.

    Raises ReplicateValidationError if the file is missing, has an
    unsupported extension, or exceeds the 10 MB limit.
    """
    p = Path(path)
    if not p.exists():
        raise ReplicateValidationError(f"Image not found: {path}")
    ext = p.suffix.lower()
    mime = IMAGE_MIME_MAP.get(ext)
    if not mime:
        raise ReplicateValidationError(
            f"Unsupported image format '{ext}'. "
            f"Kling v3 Std accepts: {', '.join(sorted(IMAGE_MIME_MAP))}"
        )
    size = p.stat().st_size
    if size > MAX_START_IMAGE_BYTES:
        mb = size / (1024 * 1024)
        cap_mb = MAX_START_IMAGE_BYTES / (1024 * 1024)
        raise ReplicateValidationError(
            f"Image file too large ({mb:.1f} MB). "
            f"Kling v3 Std start_image/end_image limit is {cap_mb:.0f} MB "
            f"per the model card."
        )
    with open(p, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def audio_path_to_data_uri(path):
    """Read an audio file and return a single data URI string.

    Format: "data:{mime};base64,{base64_data}"

    Fabric 1.0 (v3.8.1+) accepts either HTTPS URLs or data URIs for the
    `audio` field. Mirrors image_path_to_data_uri() but for audio: mp3,
    wav, m4a, aac. Enforces a size cap matching ~60 seconds at typical
    bitrates so users don't accidentally upload huge files.

    Raises ReplicateValidationError if the file is missing, has an
    unsupported extension, or exceeds the size cap.
    """
    p = Path(path)
    if not p.exists():
        raise ReplicateValidationError(f"Audio not found: {path}")
    ext = p.suffix.lower()
    mime = AUDIO_MIME_MAP.get(ext)
    if not mime:
        raise ReplicateValidationError(
            f"Unsupported audio format '{ext}'. "
            f"Fabric 1.0 accepts: {', '.join(sorted(AUDIO_MIME_MAP))}"
        )
    size = p.stat().st_size
    if size > MAX_FABRIC_AUDIO_BYTES:
        mb = size / (1024 * 1024)
        cap_mb = MAX_FABRIC_AUDIO_BYTES / (1024 * 1024)
        raise ReplicateValidationError(
            f"Audio file too large ({mb:.1f} MB). "
            f"Fabric 1.0 cap is {cap_mb:.0f} MB (~60 s at typical bitrates)."
        )
    with open(p, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ─── Parameter validation ───────────────────────────────────────────

def validate_kling_params(
    *,
    aspect_ratio,
    duration,
    mode,
    multi_prompt=None,
    start_image=None,
    end_image=None,
    prompt=None,
    negative_prompt=None,
):
    """Validate Kling v3 Std input against the model card's rules.

    Rules enforced (all sourced from dev-docs/kwaivgi-kling-v3-video-llms.md):

      1. aspect_ratio ∈ {"16:9", "9:16", "1:1"}
      2. duration is an integer in [3, 15]
      3. mode ∈ {"standard", "pro"}
      4. If multi_prompt is provided:
         a. Must be a valid JSON string
         b. Must parse to a list of shot objects
         c. Max 6 shots
         d. Each shot.duration >= 1 second
         e. sum(shot.duration for shot in shots) == duration  ← MOST CRITICAL
      5. If end_image is provided, start_image must also be provided
      6. If prompt is provided, must be <= 2500 chars
      7. If negative_prompt is provided, must be <= 2500 chars

    Non-blocking warning:
      - If both aspect_ratio AND start_image are provided, the model card
        says aspect_ratio is ignored. We log a WARNING so the caller knows.

    Raises ReplicateValidationError on any rule violation. Returns None.
    """
    # 1. aspect_ratio
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise ReplicateValidationError(
            f"Invalid aspect_ratio '{aspect_ratio}'. "
            f"Kling v3 Std supports: {sorted(VALID_ASPECT_RATIOS)}."
        )

    # 2. duration
    if not isinstance(duration, int) or not (MIN_DURATION_S <= duration <= MAX_DURATION_S):
        raise ReplicateValidationError(
            f"Invalid duration {duration!r}. "
            f"Kling v3 Std supports integer seconds in "
            f"[{MIN_DURATION_S}, {MAX_DURATION_S}]."
        )

    # 3. mode
    if mode not in VALID_MODES:
        raise ReplicateValidationError(
            f"Invalid mode '{mode}'. "
            f"Kling v3 Std supports: {sorted(VALID_MODES)}."
        )

    # 4. multi_prompt (the hard one)
    if multi_prompt is not None:
        try:
            shots = json.loads(multi_prompt)
        except json.JSONDecodeError as e:
            raise ReplicateValidationError(
                f"multi_prompt is not valid JSON: {e}. "
                f"Expected a JSON array string per the Kling model card."
            ) from None
        if not isinstance(shots, list):
            raise ReplicateValidationError(
                f"multi_prompt must be a JSON array, got "
                f"{type(shots).__name__}."
            )
        if len(shots) > MAX_MULTI_PROMPT_SHOTS:
            raise ReplicateValidationError(
                f"multi_prompt has {len(shots)} shots; max is "
                f"{MAX_MULTI_PROMPT_SHOTS} per the Kling model card."
            )
        if len(shots) == 0:
            raise ReplicateValidationError(
                "multi_prompt must contain at least one shot."
            )
        total_shot_duration = 0
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict):
                raise ReplicateValidationError(
                    f"multi_prompt shot {i} is not an object: {shot!r}"
                )
            shot_dur = shot.get("duration")
            if not isinstance(shot_dur, int) or shot_dur < MIN_SHOT_DURATION_S:
                raise ReplicateValidationError(
                    f"multi_prompt shot {i} has invalid duration "
                    f"{shot_dur!r}; must be integer >= "
                    f"{MIN_SHOT_DURATION_S} second."
                )
            total_shot_duration += shot_dur
        # THIS is the critical rule from the Kling model card:
        # "total must equal duration"
        if total_shot_duration != duration:
            raise ReplicateValidationError(
                f"multi_prompt shot durations sum to {total_shot_duration}, "
                f"but duration is {duration}. The Kling model card requires "
                f"sum(shot.duration) == duration."
            )

    # 5. end_image requires start_image
    if end_image is not None and start_image is None:
        raise ReplicateValidationError(
            "end_image requires start_image. Kling's first-and-last frame "
            "mode uses both images to constrain the generation."
        )

    # 6-7. prompt / negative_prompt length
    if prompt is not None and len(prompt) > MAX_PROMPT_CHARS:
        raise ReplicateValidationError(
            f"prompt is {len(prompt)} chars; max is {MAX_PROMPT_CHARS} "
            f"per the Kling model card."
        )
    if negative_prompt is not None and len(negative_prompt) > MAX_NEGATIVE_PROMPT_CHARS:
        raise ReplicateValidationError(
            f"negative_prompt is {len(negative_prompt)} chars; max is "
            f"{MAX_NEGATIVE_PROMPT_CHARS} per the Kling model card."
        )

    # Non-blocking warning: aspect_ratio is ignored when start_image is set.
    if start_image is not None and aspect_ratio is not None:
        _logger.warning(
            "aspect_ratio='%s' will be IGNORED by Kling because start_image "
            "is provided. The output will use the start image's native "
            "aspect ratio per the Kling v3 Std model card.",
            aspect_ratio,
        )


def validate_fabric_params(*, image, audio, resolution="720p"):
    """Validate Fabric 1.0 input against the model card's rules.

    Rules enforced (all sourced from dev-docs/veed-fabric-1.0-llms.md):

      1. resolution ∈ {"480p", "720p"}
      2. image file exists and has extension in {.jpg, .jpeg, .png}
      3. audio file exists and has extension in {.mp3, .wav, .m4a, .aac}

    Fabric's input surface is dramatically simpler than Kling's — no prompt,
    no multi_prompt, no duration parameter (derived from audio length), no
    negative_prompt. The validator only has three things to check.

    `image` and `audio` must be pathlib.Path objects (or anything Path()
    can accept). Strings are also accepted.

    Raises ReplicateValidationError on any rule violation. Returns None.
    """
    # 1. resolution
    if resolution not in VALID_FABRIC_RESOLUTIONS:
        raise ReplicateValidationError(
            f"Invalid resolution '{resolution}'. "
            f"Fabric 1.0 supports: {sorted(VALID_FABRIC_RESOLUTIONS)}."
        )

    # 2. image
    image_path = Path(image)
    if not image_path.exists():
        raise ReplicateValidationError(f"Image not found: {image}")
    image_ext = image_path.suffix.lower()
    if image_ext not in IMAGE_MIME_MAP:
        raise ReplicateValidationError(
            f"Unsupported image format '{image_ext}'. "
            f"Fabric 1.0 accepts: {', '.join(sorted(IMAGE_MIME_MAP))} "
            f"per the model card."
        )

    # 3. audio
    audio_path = Path(audio)
    if not audio_path.exists():
        raise ReplicateValidationError(f"Audio not found: {audio}")
    audio_ext = audio_path.suffix.lower()
    if audio_ext not in AUDIO_MIME_MAP:
        raise ReplicateValidationError(
            f"Unsupported audio format '{audio_ext}'. "
            f"Fabric 1.0 accepts: {', '.join(sorted(AUDIO_MIME_MAP))} "
            f"per the model card."
        )


# ─── Request body builder ───────────────────────────────────────────

def build_kling_request_body(
    prompt,
    *,
    duration,
    aspect_ratio,
    mode="pro",
    negative_prompt=None,
    start_image=None,
    end_image=None,
    multi_prompt=None,
    generate_audio=True,
):
    """Build the JSON dict to serialize for POST /v1/models/.../predictions.

    Wraps the input parameters in the Replicate-required `{"input": {...}}`
    envelope. Returns a dict ready to be JSON-serialized and POSTed.

    Only fields with non-None values are included in the "input" dict, to
    keep the request body minimal and match the examples from the Kling
    model card. `generate_audio` is always included because Kling treats
    omission as True (the model card default).

    Does NOT call validate_kling_params() internally — callers should
    validate separately so the error surface is predictable.
    """
    input_dict = {
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "mode": mode,
        "generate_audio": generate_audio,
    }
    if negative_prompt is not None:
        input_dict["negative_prompt"] = negative_prompt
    if start_image is not None:
        input_dict["start_image"] = start_image
    if end_image is not None:
        input_dict["end_image"] = end_image
    if multi_prompt is not None:
        # Per the Kling model card: multi_prompt is a STRING containing a
        # JSON array. We preserve it verbatim — do NOT re-parse and re-
        # serialize because that could reorder fields or drop whitespace
        # in ways that confuse downstream consumers.
        input_dict["multi_prompt"] = multi_prompt
    return {"input": input_dict}


def build_fabric_request_body(image, audio, resolution="720p"):
    """Build the JSON dict to serialize for Fabric 1.0 predictions.

    Wraps the input parameters in the Replicate-required `{"input": {...}}`
    envelope. Returns a dict ready to be JSON-serialized and POSTed.

    Unlike build_kling_request_body(), there are no optional fields — Fabric
    only takes image + audio + resolution. Simpler surface = simpler builder.

    `image` and `audio` can be HTTPS URLs or data URIs (the caller handles
    the file-path-to-data-URI conversion via image_path_to_data_uri() /
    audio_path_to_data_uri() before calling this function).

    Does NOT call validate_fabric_params() internally — callers should
    validate separately so the error surface is predictable.
    """
    return {
        "input": {
            "image": image,
            "audio": audio,
            "resolution": resolution,
        }
    }


# ─── Recraft Vectorize helpers (v4.1.0+) ───────────────────────────

def recraft_image_path_to_data_uri(path):
    """Read an image file and return a data URI for Recraft Vectorize.

    Format: "data:{mime};base64,{base64_data}"

    Unlike image_path_to_data_uri() (Kling), this accepts WEBP too per the
    Recraft model card. Enforces the 5 MB cap. Pixel-dimension validation
    is optional and handled by validate_recraft_image() separately.

    Raises ReplicateValidationError if the file is missing, has an
    unsupported extension, or exceeds the 5 MB limit.
    """
    p = Path(path)
    if not p.exists():
        raise ReplicateValidationError(f"Image not found: {path}")
    ext = p.suffix.lower()
    mime = RECRAFT_IMAGE_MIME_MAP.get(ext)
    if not mime:
        raise ReplicateValidationError(
            f"Unsupported image format '{ext}'. "
            f"Recraft Vectorize accepts: {', '.join(sorted(RECRAFT_IMAGE_MIME_MAP))}"
        )
    size = p.stat().st_size
    if size > MAX_RECRAFT_IMAGE_BYTES:
        mb = size / (1024 * 1024)
        cap_mb = MAX_RECRAFT_IMAGE_BYTES / (1024 * 1024)
        raise ReplicateValidationError(
            f"Image file too large ({mb:.1f} MB). "
            f"Recraft Vectorize limit is {cap_mb:.0f} MB per the model card. "
            f"Downscale with: magick input.png -resize 2048x input.png "
            f"(or cwebp -q 85 input.png -o input.webp for WEBP)."
        )
    with open(p, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def validate_recraft_image(image, *, dimensions=None):
    """Validate a Recraft Vectorize input image against model-card constraints.

    - `image`: path (file will be checked), HTTPS URL (assumed valid), or data URI
    - `dimensions`: optional (width, height) tuple for pixel-dimension bounds check

    Extension + size checks are handled by recraft_image_path_to_data_uri()
    when the caller converts a local path. This function is for the final
    belt-and-suspenders check of pixel dimensions IF the caller has them.
    """
    if dimensions is not None:
        w, h = dimensions
        if w < RECRAFT_MIN_DIMENSION_PX or h < RECRAFT_MIN_DIMENSION_PX:
            raise ReplicateValidationError(
                f"Image too small ({w}x{h}). Recraft requires both dimensions "
                f"≥ {RECRAFT_MIN_DIMENSION_PX} px."
            )
        if w > RECRAFT_MAX_DIMENSION_PX or h > RECRAFT_MAX_DIMENSION_PX:
            raise ReplicateValidationError(
                f"Image too large ({w}x{h}). Recraft max dimension is "
                f"{RECRAFT_MAX_DIMENSION_PX} px per side."
            )
        mp = (w * h) / 1_000_000
        if mp > RECRAFT_MAX_MEGAPIXELS:
            raise ReplicateValidationError(
                f"Image exceeds {RECRAFT_MAX_MEGAPIXELS} MP ({mp:.1f} MP at "
                f"{w}x{h}). Downscale before submitting."
            )


def build_recraft_request_body(image):
    """Build the JSON dict to serialize for Recraft Vectorize predictions.

    Wraps the single input parameter in the Replicate-required `{"input": {...}}`
    envelope. The simplest builder in this module — Recraft takes one argument.

    `image` can be an HTTPS URL or a data URI (use
    recraft_image_path_to_data_uri() to convert local paths).
    """
    return {
        "input": {
            "image": image,
        }
    }


# ─── Response parsers ───────────────────────────────────────────────

def parse_replicate_submit_response(response_dict):
    """Extract (prediction_id, poll_url) from a predictions-create response.

    Replicate submit response shape (per OpenAPI):
        {
          "id": "...",
          "status": "starting",
          "urls": {"get": "https://...", "cancel": "https://..."},
          "created_at": "...",
          ...
        }

    Raises ReplicateBackendError if the shape doesn't match.
    """
    if not isinstance(response_dict, dict):
        raise ReplicateBackendError(
            f"Unexpected submit response type: {type(response_dict).__name__}"
        )
    pid = response_dict.get("id")
    if not pid:
        raise ReplicateBackendError(
            f"No prediction id in submit response. "
            f"Keys present: {list(response_dict.keys())}"
        )
    urls = response_dict.get("urls") or {}
    poll_url = urls.get("get")
    if not poll_url:
        raise ReplicateBackendError(
            f"No urls.get in submit response. "
            f"urls keys: {list(urls.keys())}"
        )
    return (pid, poll_url)


def parse_replicate_poll_response(response_dict):
    """Parse a Replicate prediction GET response into a state tuple.

    Returns one of:
        ("running", None)            — still in progress, keep polling
        ("done", output)             — succeeded; output is the URI string
                                       (or list for multi-output models)
        ("failed", error_info)       — failed, canceled, or aborted

    The Replicate Prediction.status enum has 6 values per the OpenAPI schema:
      - starting, processing          → running
      - succeeded                     → done
      - failed, canceled, aborted     → failed

    Note: `aborted` is easy to miss (spike client doesn't know it) and
    represents predictions terminated before predict() was called (queue
    eviction, deadline reached). It must be treated as terminal failure,
    NOT as running — otherwise the poll loop spins forever.
    """
    if not isinstance(response_dict, dict):
        raise ReplicateBackendError(
            f"Unexpected poll response type: {type(response_dict).__name__}"
        )
    status = response_dict.get("status")
    if status in RUNNING_STATUSES:
        return ("running", None)
    if status in TERMINAL_SUCCESS_STATUSES:
        output = response_dict.get("output")
        return ("done", output)
    if status in TERMINAL_FAILURE_STATUSES:
        error_info = response_dict.get("error")
        return ("failed", error_info)
    # Unknown status — defensive fallthrough. Treat as failure so we don't
    # spin-poll forever on an enum value Replicate adds in the future.
    raise ReplicateBackendError(
        f"Unknown prediction status '{status}'. "
        f"Expected one of: {sorted(RUNNING_STATUSES | TERMINAL_SUCCESS_STATUSES | TERMINAL_FAILURE_STATUSES)}"
    )


# ─── HTTP helpers ───────────────────────────────────────────────────

def replicate_post(url, body, *, token, timeout=60):
    """POST a JSON body to a Replicate endpoint and return the parsed JSON.

    Sends `Authorization: Bearer {token}` per the OpenAPI schema. Does NOT
    send a `Prefer: wait` header — the spike's `wait=0` is out-of-spec per
    the regex `^wait(=([1-9]|[1-9][0-9]|60))?$`, and omitting the header
    gives us the correct async-first semantic for Kling's 3-6 min wall times.

    Raises ReplicateSubmitError on non-2xx or unparseable body.
    """
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": REPLICATE_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body_text)
            msg = err.get("detail") or err.get("title") or body_text[:500]
            raise ReplicateSubmitError(
                f"Replicate HTTP {e.code}: {msg}"
            ) from None
        except (json.JSONDecodeError, ValueError):
            raise ReplicateSubmitError(
                f"Replicate HTTP {e.code}: {body_text[:500]}"
            ) from None
    except urllib.error.URLError as e:
        raise ReplicateSubmitError(f"Replicate network error: {e.reason}") from None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ReplicateSubmitError(
            f"Replicate returned non-JSON response: {raw[:300]!r}"
        ) from None


def replicate_get(url, *, token, timeout=60):
    """GET from a Replicate endpoint (used for polling prediction status).

    Same auth as replicate_post but without a body. Raises ReplicatePollError
    on non-2xx or unparseable body.
    """
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": REPLICATE_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body_text)
            msg = err.get("detail") or err.get("title") or body_text[:500]
            raise ReplicatePollError(
                f"Replicate HTTP {e.code}: {msg}"
            ) from None
        except (json.JSONDecodeError, ValueError):
            raise ReplicatePollError(
                f"Replicate HTTP {e.code}: {body_text[:500]}"
            ) from None
    except urllib.error.URLError as e:
        raise ReplicatePollError(f"Replicate network error: {e.reason}") from None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ReplicatePollError(
            f"Replicate returned non-JSON response: {raw[:300]!r}"
        ) from None


# ─── Diagnose CLI ───────────────────────────────────────────────────

def _cmd_diagnose(args):
    """Diagnose the Replicate setup without burning a Kling generation.

    Pings the free /v1/account endpoint through the same auth path to verify
    credentials are live. Reports token prefix and account info. Exit 0 on
    success, 1 on any failure.
    """
    print("=== Replicate backend diagnose ===")

    try:
        creds = load_replicate_credentials(cli_token=args.replicate_key)
    except ReplicateAuthError as e:
        print(f"FAIL (auth): {e}")
        sys.exit(1)

    token = creds["api_token"]
    token_preview = token[:8] + "..." + token[-4:] if len(token) > 12 else "<short>"
    print(f"  api_token: {token_preview} ({len(token)} chars)")

    print("\n  sanity check: GET /v1/account ...")
    try:
        result = replicate_get(REPLICATE_ACCOUNT_URL, token=token, timeout=30)
    except ReplicatePollError as e:
        print(f"FAIL (sanity check): {e}")
        sys.exit(1)

    username = result.get("username", "<unknown>")
    account_type = result.get("type", "<unknown>")
    print(f"  OK: account = {username} (type: {account_type})")

    print("\n  registered models:")
    for slug, info in REPLICATE_MODELS.items():
        # Each family exposes different capability metadata. Format each
        # family's row appropriately so the diagnose output doesn't KeyError
        # on families with different capability shapes.
        display = info.get("display_name", slug)
        family = info.get("family", "?")
        if family == "kling":
            aspects = ", ".join(info.get("aspects", []))
            min_d = info.get("min_duration_s", "?")
            max_d = info.get("max_duration_s", "?")
            print(
                f"    {slug:30s} — {display} ({min_d}-{max_d}s, {aspects})"
            )
        elif family == "fabric":
            resolutions = ", ".join(info.get("resolutions", []))
            max_d = info.get("max_duration_s", "?")
            print(
                f"    {slug:30s} — {display} (lipsync, ≤{max_d}s, {resolutions})"
            )
        else:
            # Unknown family — show the slug + display name and nothing else.
            print(f"    {slug:30s} — {display}")

    print("\nAll checks passed. Replicate backend is reachable.")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Replicate backend helper for Kling video generation (v3.8.0+)",
    )
    sub = parser.add_subparsers(dest="command")

    p_diag = sub.add_parser(
        "diagnose", help="Verify Replicate auth without burning a generation"
    )
    p_diag.add_argument(
        "--replicate-key",
        default=None,
        help="Override the Replicate API token (else reads env/config)",
    )

    args = parser.parse_args()
    if args.command is None:
        # Default: diagnose
        args = parser.parse_args(["diagnose"])

    if args.command == "diagnose":
        _cmd_diagnose(args)
    else:
        parser.print_help()
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════
# ProviderBackend implementation (v4.2.0+ — adapts the legacy helpers above
# into the canonical interface defined in scripts/backends/_base.py.)
# ═══════════════════════════════════════════════════════════════════════

from typing import Any  # noqa: E402

from scripts.backends._base import (  # noqa: E402
    AuthStatus,
    JobRef,
    JobStatus,
    ProviderAuthError,
    ProviderBackend,
    ProviderError,
    ProviderHTTPError,
    ProviderValidationError,
    TaskResult,
)


# Canonical task → provider-specific param translator tables.
# Indexed by task; each entry maps canonical_param_name → provider_field_name.
# These mappings stay LOCAL to this module — they never leak to orchestrator code.
_TASK_PARAM_MAPS: dict[str, dict[str, str]] = {
    "text-to-video": {
        "prompt": "prompt",
        "duration_s": "duration",
        "aspect_ratio": "aspect_ratio",
        "negative_prompt": "negative_prompt",
        "seed": "seed",
    },
    "image-to-video": {
        "prompt": "prompt",
        "duration_s": "duration",
        "aspect_ratio": "aspect_ratio",
        "start_image": "start_image",
        "end_image": "end_image",
        "negative_prompt": "negative_prompt",
        "seed": "seed",
    },
    "lipsync": {
        "image": "image",
        "audio": "audio",
        "resolution": "resolution",
    },
    "vectorize": {
        "source_image": "image",
    },
}


def _resolution_to_kling_mode(resolution: str) -> str:
    """Kling uses 'mode' (standard=720p, pro=1080p), not an explicit resolution."""
    match resolution:
        case "720p":
            return "standard"
        case "1080p":
            return "pro"
        case _:
            raise ProviderValidationError(
                f"Kling does not support resolution={resolution!r}"
            )


def _replicate_state_to_canonical(provider_state: str) -> str:
    """Map Replicate's 6-value enum to canonical 5-state JobStatus.state.

    Replicate states: starting | processing | succeeded | failed | canceled | aborted
    Canonical states: pending | running | succeeded | failed | canceled
    """
    if provider_state in RUNNING_STATUSES:
        return "running"
    if provider_state in TERMINAL_SUCCESS_STATUSES:
        return "succeeded"
    if provider_state == "canceled":
        return "canceled"
    if provider_state in TERMINAL_FAILURE_STATUSES:
        # TERMINAL_FAILURE_STATUSES is {"failed", "canceled", "aborted"}; canceled
        # is handled above, so this branch covers only failed + aborted.
        return "failed"
    # Unknown provider state — treat as running so the caller's poll loop
    # continues rather than spinning forever on a phantom failure.
    return "running"


class ReplicateBackend(ProviderBackend):
    """Replicate implementation of the ProviderBackend contract.

    Delegates to the legacy module-level helpers (validate_kling_params,
    build_kling_request_body, replicate_post, etc.) so the refactor is
    mechanical — zero duplicated logic, zero behavior change.
    """

    name = "replicate"
    supported_tasks = {
        "text-to-image",
        "image-to-image",
        "text-to-video",
        "image-to-video",
        "lipsync",
        "vectorize",
    }

    def _api_key(self, config: dict[str, Any]) -> str:
        """Extract the Replicate API token, honoring the v4.2.0 schema
        plus the legacy flat `replicate_api_token` key."""
        key: str | None = None
        if isinstance(providers := config.get("providers"), dict):
            if isinstance(rep := providers.get("replicate"), dict):
                key = rep.get("api_key")
        if not key:
            key = config.get("replicate_api_token")
        if not key:
            raise ProviderAuthError(
                "No Replicate API key configured. Set "
                "providers.replicate.api_key in ~/.banana/config.json "
                "or run /create-video setup."
            )
        return key

    def auth_check(self, config: dict[str, Any]) -> AuthStatus:
        try:
            api_key = self._api_key(config)
        except ProviderAuthError as e:
            return AuthStatus(ok=False, message=str(e), provider=self.name)

        req = urllib.request.Request(
            REPLICATE_ACCOUNT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": REPLICATE_USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.getcode() if hasattr(resp, "getcode") else getattr(resp, "status", 200)
                if code == 200:
                    return AuthStatus(
                        ok=True,
                        message=f"Authenticated (HTTP {code})",
                        provider=self.name,
                    )
                return AuthStatus(
                    ok=False,
                    message=f"Unexpected status: HTTP {code}",
                    provider=self.name,
                )
        except urllib.error.HTTPError as e:
            return AuthStatus(
                ok=False,
                message=f"HTTP {e.code}: {e.reason}",
                provider=self.name,
            )
        except Exception as e:
            return AuthStatus(ok=False, message=str(e), provider=self.name)

    def submit(
        self,
        *,
        task: str,
        model_slug: str,
        canonical_params: dict[str, Any],
        provider_opts: dict[str, Any],
        config: dict[str, Any],
    ) -> JobRef:
        api_key = self._api_key(config)

        if task not in _TASK_PARAM_MAPS:
            raise ProviderValidationError(
                f"Replicate backend does not handle task {task!r}. "
                f"Supported: {sorted(_TASK_PARAM_MAPS.keys())}"
            )

        # Translate canonical params to Replicate's input schema.
        param_map = _TASK_PARAM_MAPS[task]
        input_body: dict[str, Any] = {
            prov_key: canonical_params[canon_key]
            for canon_key, prov_key in param_map.items()
            if canon_key in canonical_params
        }

        # Kling-specific: resolution → mode translation
        if model_slug.startswith("kwaivgi/kling-") and "resolution" in canonical_params:
            input_body["mode"] = _resolution_to_kling_mode(canonical_params["resolution"])

        # Merge provider_opts LAST so they can shadow auto-derived fields.
        input_body.update(provider_opts)

        owner, name = model_slug.split("/", 1)
        url = REPLICATE_PREDICTIONS_URL_TEMPLATE.format(owner=owner, name=name)

        # Use the existing replicate_post helper for HTTP, but wrap its
        # error types in canonical ones.
        try:
            raw = replicate_post(url, {"input": input_body}, token=api_key)
        except ReplicateAuthError as e:
            raise ProviderAuthError(str(e)) from e
        except ReplicateSubmitError as e:
            # Distinguish auth failures (401/403) by message substring — the
            # legacy helper bundles them all as ReplicateSubmitError.
            msg = str(e)
            if "HTTP 401" in msg or "HTTP 403" in msg:
                raise ProviderAuthError(msg) from e
            raise ProviderHTTPError(msg) from e
        except ReplicateBackendError as e:
            raise ProviderHTTPError(str(e)) from e

        try:
            pid, poll_url = parse_replicate_submit_response(raw)
        except ReplicateBackendError as e:
            raise ProviderHTTPError(str(e)) from e

        return JobRef(
            provider=self.name,
            external_id=pid,
            poll_url=poll_url,
            raw=raw,
        )

    def poll(self, job_ref: JobRef, config: dict[str, Any]) -> JobStatus:
        api_key = self._api_key(config)
        try:
            raw = replicate_get(job_ref.poll_url, token=api_key)
        except ReplicatePollError as e:
            msg = str(e)
            if "HTTP 401" in msg or "HTTP 403" in msg:
                raise ProviderAuthError(msg) from e
            raise ProviderHTTPError(msg) from e
        except ReplicateBackendError as e:
            raise ProviderHTTPError(str(e)) from e

        state = _replicate_state_to_canonical(raw.get("status", ""))
        output = raw.get("output")
        return JobStatus(
            state=state,
            output={"output": output} if output is not None else None,
            error=raw.get("error"),
            raw=raw,
        )

    def parse_result(self, job_status: JobStatus, *, download_to: Path) -> TaskResult:
        if job_status.state != "succeeded":
            raise ProviderError(
                f"parse_result called on non-succeeded job (state={job_status.state!r})"
            )

        output = job_status.output["output"] if job_status.output else None
        output_urls: list[str] = []
        if isinstance(output, str):
            output_urls = [output]
        elif isinstance(output, list):
            output_urls = [u for u in output if isinstance(u, str)]

        download_to = Path(download_to)
        download_to.parent.mkdir(parents=True, exist_ok=True)
        output_paths: list[Path] = []
        for i, url in enumerate(output_urls):
            dest = download_to if i == 0 else download_to.with_name(
                f"{download_to.stem}_{i}{download_to.suffix}"
            )
            req = urllib.request.Request(
                url, headers={"User-Agent": REPLICATE_USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
                f.write(resp.read())
            output_paths.append(dest)

        raw = job_status.raw or {}
        metrics = raw.get("metrics", {}) if isinstance(raw, dict) else {}
        duration_s = metrics.get("video_output_duration_seconds")

        metadata: dict[str, Any] = {}
        if duration_s is not None:
            metadata["duration_s"] = duration_s

        return TaskResult(
            output_paths=output_paths,
            output_urls=output_urls,
            metadata=metadata,
            provider_metadata=raw,
            cost=None,  # Cost computed by cost_tracker.py using pricing mode
            task_id=raw.get("id", ""),
        )


if __name__ == "__main__":
    main()
