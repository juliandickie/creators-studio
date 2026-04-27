#!/usr/bin/env python3
"""Creators Studio -- Video Generation via Google VEO 3.1

Generate videos via VEO REST API using async long-running operations.
Uses only Python stdlib (no pip dependencies).

Usage:
    video_generate.py --prompt "a cat jumping in slow motion" [--duration 8]
                      [--aspect-ratio 16:9] [--resolution 1080p]
                      [--model veo-3.1-generate-preview]
                      [--first-frame PATH] [--last-frame PATH]
                      [--reference-image PATH [PATH ...]]
                      [--api-key KEY] [--poll-interval 10] [--max-wait 300]
                      [--output DIR]
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Replicate backend helper. As of v4.2.0 this lives at plugin-root
# scripts/backends/_replicate.py — same module, new location as part of
# the provider-agnostic architecture. The module still exposes all legacy
# helpers (validate_kling_params, build_kling_request_body, etc.) so this
# call site continues to work unchanged; it also exposes the new
# ReplicateBackend class for v4.2.0+ callers using the provider abstraction.
#
# v4.2.1: Vertex AI backend retired. All VEO 3.1 traffic now routes through
# Replicate using `google/veo-3.1-*` slugs (see Task 6 registry entries).
# The --backend vertex-ai flag is still accepted for one release but emits
# a DeprecationWarning and auto-routes to Replicate.
import subprocess  # noqa: E402 — used by cost-log shell-out
_plugin_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)
from scripts.backends import _replicate as replicate  # noqa: E402
from scripts.backends._replicate import ReplicateBackend  # noqa: E402
from scripts.backends._base import (  # noqa: E402
    ProviderAuthError,
    ProviderValidationError,
    ProviderHTTPError,
    ProviderError,
)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
OPERATIONS_BASE = "https://generativelanguage.googleapis.com/v1beta"
# v3.8.0+: Kling v3 Std is the default video model. VEO 3.1 is the opt-in
# backup via --provider veo. See spikes/v3.8.0-provider-bakeoff/ and
# skills/create-video/references/kling-models.md for the bake-off findings.
DEFAULT_MODEL = "kwaivgi/kling-v3-video"
DEFAULT_DURATION = 8
DEFAULT_RATIO = "16:9"
DEFAULT_RESOLUTION = "1080p"
DEFAULT_POLL_INTERVAL = 10
DEFAULT_MAX_WAIT = 300
OUTPUT_DIR = Path.home() / "Documents" / "creators_generated"

# All video model IDs the plugin knows about. v4.2.1: the VEO 3.1 family is
# now served via Replicate using `google/veo-3.1-*` slugs; the legacy Vertex
# -001 / -preview IDs are still accepted on the CLI (for backwards compat)
# and are auto-translated to Replicate slugs via _translate_vertex_model_id().
VALID_MODELS = {
    # Replicate slugs (owner/name format). These are the canonical IDs.
    "kwaivgi/kling-v3-video",         # Kling v3 Std (DEFAULT, multi_prompt, 1:1, native audio)
    "google/veo-3.1",                 # VEO 3.1 Standard (Replicate)
    "google/veo-3.1-fast",            # VEO 3.1 Fast (Replicate)
    "google/veo-3.1-lite",            # VEO 3.1 Lite (Replicate)
    "pixverse/pixverse-v6",           # PixVerse V6 (multi-shot toggle, native text-in-video, 4-tier res)
    # Legacy Gemini-API preview IDs — still callable on the direct Gemini API.
    "veo-3.1-generate-preview",       # Standard (preview API)
    "veo-3.1-fast-generate-preview",  # Fast (preview API)
    # Legacy Vertex GA IDs — auto-translated to Replicate slugs on entry.
    # Retained here so `--model veo-3.1-fast-generate-001` passes the
    # VALID_MODELS gate during the deprecation window.
    "veo-3.1-generate-001",           # Auto-translated → google/veo-3.1
    "veo-3.1-fast-generate-001",      # Auto-translated → google/veo-3.1-fast
    "veo-3.1-lite-generate-001",      # Auto-translated → google/veo-3.1-lite
    "veo-3.0-generate-001",           # Legacy predecessor (no Replicate equivalent)
}

# Replicate model slugs (owner/name format). The _select_backend() router
# treats any model containing "/" as a Replicate model.
MODELS_REPLICATE = {
    "kwaivgi/kling-v3-video",
    "google/veo-3.1",
    "google/veo-3.1-fast",
    "google/veo-3.1-lite",
    "pixverse/pixverse-v6",
}

# v4.2.1: Vertex retirement. Map legacy Vertex VEO model IDs to their Replicate
# equivalents so users passing --backend vertex-ai + Vertex-style model names
# continue to work (with a deprecation warning). The mapping is empirical:
# Vertex used '-generate-001' suffixes; Replicate uses path-style slugs.
_VERTEX_TO_REPLICATE_SLUG: dict[str, str] = {
    "veo-3.1-generate-001":         "google/veo-3.1",
    "veo-3.1-fast-generate-001":    "google/veo-3.1-fast",
    "veo-3.1-lite-generate-001":    "google/veo-3.1-lite",
    # Users sometimes drop the -001 suffix in casual usage:
    "veo-3.1-generate":             "google/veo-3.1",
    "veo-3.1-fast-generate":        "google/veo-3.1-fast",
    "veo-3.1-lite-generate":        "google/veo-3.1-lite",
}


def _translate_vertex_model_id(model_slug: str) -> str:
    """If model_slug looks like a legacy Vertex VEO ID, translate to Replicate.
    Pass-through for anything else (Kling slugs, already-Replicate VEO slugs,
    preview IDs).
    """
    return _VERTEX_TO_REPLICATE_SLUG.get(model_slug, model_slug)


# v4.2.1: BACKEND_VERTEX_AI kept for backwards-compat argparse acceptance only.
# When the user passes --backend vertex-ai, _select_backend() translates it
# to BACKEND_REPLICATE + logs a DeprecationWarning. All Vertex-specific code
# paths (submit/poll/save, credentials loading, service-agent retry) are gone.
BACKEND_GEMINI_API = "gemini-api"
BACKEND_VERTEX_AI = "vertex-ai"  # deprecated alias, auto-routes to replicate
BACKEND_REPLICATE = "replicate"
BACKEND_AUTO = "auto"
VALID_BACKENDS = {BACKEND_GEMINI_API, BACKEND_VERTEX_AI, BACKEND_REPLICATE, BACKEND_AUTO}

# VEO 3.1 accepts prompts up to 1,024 tokens (English only). We have no
# tokenizer dependency, so approximate using ~4 chars/token for English prose.
# Warn near the limit, hard-reject clearly over.
PROMPT_WARN_CHARS = 3800   # ~950 tokens
PROMPT_ERROR_CHARS = 4500  # ~1,125 tokens

# Generated video download URIs expire 48 hours after creation on Google's
# servers. We download immediately so runtime is safe, but manifests that
# store URIs become stale after this window.
DOWNLOAD_RETENTION_HOURS = 48

# Model-aware parameter constraints. All VEO 3.1 tiers share the same
# {4, 6, 8} duration set. v3.5.0 documented a 5-60 second range for Lite
# based on unverified docs; real-API testing during v3.6.0 proved this
# wrong — the API explicitly rejects 5-second Lite requests with
# "Unsupported output video duration 5 seconds, supported durations are
# [8,4,6] for feature text_to_video".
STANDARD_DURATIONS = {4, 6, 8}
VALID_DURATIONS_BY_MODEL = {
    # VEO 3.1 tiers all use STANDARD_DURATIONS (the empty-dict default).
    # Kling v3 Std accepts any integer in [3, 15] per the Kling model card
    # at dev-docs/kwaivgi-kling-v3-video-llms.md. We expand the range to
    # an explicit set so the existing `duration not in valid_durations`
    # check works without conditional logic.
    "kwaivgi/kling-v3-video": set(range(3, 16)),
    # PixVerse V6 accepts integer seconds in [1, 15] per the model card at
    # dev-docs/pixverse-pixverse-v6-llms.md.
    "pixverse/pixverse-v6": set(range(1, 16)),
}

STANDARD_RATIOS = {"16:9", "9:16"}
VALID_RATIOS_BY_MODEL = {
    # VEO 3.1 tiers all use STANDARD_RATIOS (the empty-dict default).
    # Kling v3 Std supports 1:1 per the Kling model card — the only
    # plugin-registered model that does. v3.5.0 documented 1:1 for VEO
    # Lite but that claim was wrong; Vertex AI explicitly rejects it.
    "kwaivgi/kling-v3-video": {"16:9", "9:16", "1:1"},
    # PixVerse V6 supports 16:9 and 9:16. The model-card examples never
    # show 1:1 or 4:3, so we don't claim them. (Pixverse silently ignores
    # aspect_ratio when image is provided — handled by validator.)
    "pixverse/pixverse-v6": {"16:9", "9:16"},
}

# Lite does NOT support 4K per reference doc line 55, 274.
# Kling v3 Std maxes at 1080p (pro mode) per the Kling model card.
# PixVerse V6 maxes at 1080p per the model card pricing block.
# v4.2.1: adds the Replicate VEO slugs (google/veo-3.1-lite) alongside the
# legacy Vertex -001 IDs so the 4K gate works for both forms.
MODELS_WITHOUT_4K = {
    "veo-3.1-lite-generate-001",
    "veo-3.0-generate-001",
    "kwaivgi/kling-v3-video",
    "google/veo-3.1-lite",
    "pixverse/pixverse-v6",
}

# 2026-04-27: VALID_RESOLUTIONS expanded to include 360p + 540p for PixVerse
# V6's 4-tier pricing model. Other models reject these via their own
# validation paths (Kling/VEO have their own resolution allowlists in their
# registry constraints; the canonical-validator catches mismatches before
# any HTTP call). PixVerse is currently the only model that USES 360p/540p.
VALID_RESOLUTIONS = {"360p", "540p", "720p", "1080p", "4K"}


def _valid_durations(model):
    """Return the set of valid durations for a given model."""
    return VALID_DURATIONS_BY_MODEL.get(model, STANDARD_DURATIONS)


def _valid_ratios(model):
    """Return the set of valid aspect ratios for a given model."""
    return VALID_RATIOS_BY_MODEL.get(model, STANDARD_RATIOS)


def _select_backend(args):
    """Return which backend to use for this request.

    v4.2.1: Vertex is removed. `--backend vertex-ai` is deprecated and
    auto-routes to Replicate with a DeprecationWarning.

    `--backend auto` routing rules (in precedence order):
    1. `--model` is a Replicate slug (contains "/") → Replicate (Kling / VEO-on-Replicate)
    2. `--model` is a legacy Vertex ID (veo-3.1-*-001) → Replicate (auto-translated)
    3. `--model` is a preview ID → Gemini API (preserves v3.4.x text-to-video path)
    4. Fallback → Gemini API
    """
    explicit = getattr(args, "backend", None)

    if explicit == BACKEND_VERTEX_AI:
        import warnings
        warnings.warn(
            "--backend vertex-ai is deprecated. Vertex AI was retired in "
            "v4.2.1; VEO 3.1 now routes through Replicate. This flag is "
            "honored for one release and will be removed in v4.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return BACKEND_REPLICATE

    if explicit == BACKEND_REPLICATE:
        return BACKEND_REPLICATE
    if explicit == BACKEND_GEMINI_API:
        return BACKEND_GEMINI_API

    # explicit in (None, BACKEND_AUTO) → auto-route from model shape.
    # Replicate model slugs contain "/" (owner/name).
    if "/" in args.model:
        return BACKEND_REPLICATE

    # Legacy Vertex IDs will be translated to Replicate slugs upstream in
    # main(); by the time we reach here, translation already happened. But
    # if a caller invoked _select_backend() before translation, still route
    # legacy IDs to Replicate.
    if args.model in _VERTEX_TO_REPLICATE_SLUG:
        return BACKEND_REPLICATE

    # Text-only on a preview-tier model → Gemini API.
    return BACKEND_GEMINI_API

MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _error_exit(message):
    """Print JSON error to stdout and exit."""
    print(json.dumps({"error": True, "message": message}))
    sys.exit(1)


def _progress(data):
    """Print progress JSON to stderr."""
    print(json.dumps(data), file=sys.stderr)


def _load_api_key(cli_key):
    """Load API key: CLI -> env -> config.json."""
    api_key = cli_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # v4.2.2: canonical config dir auto-migrates from ~/.banana/ on first call.
        from scripts.paths import config_path as _csd_config  # noqa: E402
        config_path = _csd_config()
        if config_path.exists():
            try:
                with open(config_path) as f:
                    api_key = json.load(f).get("google_ai_api_key", "")
            except (json.JSONDecodeError, OSError):
                pass
    if not api_key:
        _error_exit("No API key. Run /create-image setup, set GOOGLE_AI_API_KEY env, or pass --api-key")
    return api_key


def _read_image_base64(path):
    """Read image file, return (base64_string, mime_type)."""
    p = Path(path)
    if not p.exists():
        _error_exit(f"Image not found: {path}")
    ext = p.suffix.lower()
    mime = MIME_MAP.get(ext)
    if not mime:
        _error_exit(f"Unsupported image format '{ext}'. Use: {', '.join(sorted(MIME_MAP))}")
    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return data, mime


# Max MP4 size for inline Scene Extension v2 payload. Gemini API's inlineData
# limit is 20 MB; we leave a 5 MB margin for the base64 overhead (33% inflation)
# and other request JSON. A 720p 8s clip is typically 2-5 MB so this is comfortable.
MAX_VIDEO_INPUT_BYTES = 15 * 1024 * 1024  # 15 MB


def _read_video_base64(path):
    """Read MP4 file for Scene Extension v2, return (base64_string, mime_type).

    Enforces a 15 MB cap to stay under the Gemini API inline payload limit.
    For larger videos, the user should extract a last frame and use --first-frame
    instead (see video_extend.py --method keyframe).
    """
    p = Path(path)
    if not p.exists():
        _error_exit(f"Video not found: {path}")
    ext = p.suffix.lower()
    if ext not in (".mp4", ".mov", ".m4v"):
        _error_exit(f"Unsupported video format '{ext}'. Use: .mp4, .mov, .m4v")
    size = p.stat().st_size
    if size > MAX_VIDEO_INPUT_BYTES:
        size_mb = size / (1024 * 1024)
        _error_exit(
            f"Video file too large ({size_mb:.1f} MB). "
            f"Scene Extension v2 limit is 15 MB (Gemini API inline payload). "
            f"For larger videos, use video_extend.py --method keyframe."
        )
    mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/mp4"}
    mime = mime_map[ext]
    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return data, mime


def _http_request(url, data=None, method="GET", max_retries=3):
    """Make HTTP request with retry on 429. Returns parsed JSON."""
    headers = {"Content-Type": "application/json"} if data else {}
    encoded = json.dumps(data).encode("utf-8") if data else None

    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
        try:
            timeout = 120 if method == "POST" else 30
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 429 and attempt < max_retries - 1:
                wait = 10
                _progress({"retry": True, "attempt": attempt + 1, "wait_seconds": wait, "reason": "rate_limited"})
                time.sleep(wait)
                continue
            if e.code == 400:
                try:
                    err_json = json.loads(error_body)
                    msg = err_json.get("error", {}).get("message", error_body)
                except (json.JSONDecodeError, KeyError):
                    msg = error_body
                _error_exit(f"Bad request: {msg}")
            if e.code == 403:
                _error_exit("API key invalid or billing not enabled. Check key at https://aistudio.google.com/apikey")
            _error_exit(f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            _error_exit(f"Network error: {e.reason}")

    _error_exit("Max retries exceeded (rate limited)")


def _submit_gemini_api(prompt, model, duration, ratio, resolution, api_key,
                       first_frame=None, last_frame=None, ref_images=None,
                       negative_prompt=None, seed=None, video_input=None):
    """POST to the Gemini API (generativelanguage.googleapis.com) endpoint.

    Uses the legacy request shape:
      {
        "instances": [{"prompt": "...", "image": {"inlineData": {...}}, ...}],
        "parameters": {...}
      }

    Image parts use `inlineData.data` (Gemini convention) rather than
    `bytesBase64Encoded` (Vertex convention). This is the v3.4.x-compatible
    code path that preserves working text-to-video on Standard/Fast preview
    IDs. As of 2026-04-10 this path does NOT serve image-to-video, Lite, or
    GA -001 IDs — callers should route those through Vertex via _select_backend().
    """
    url = f"{API_BASE}/{model}:predictLongRunning?key={api_key}"

    instance = {"prompt": prompt}

    if video_input:
        b64, mime = _read_video_base64(video_input)
        instance["video"] = {"inlineData": {"data": b64, "mimeType": mime}}
    else:
        if first_frame:
            b64, mime = _read_image_base64(first_frame)
            instance["image"] = {"inlineData": {"data": b64, "mimeType": mime}}

        if last_frame:
            b64, mime = _read_image_base64(last_frame)
            instance["lastFrame"] = {"inlineData": {"data": b64, "mimeType": mime}}

        if ref_images:
            ref_list = []
            for img_path in ref_images[:3]:
                b64, mime = _read_image_base64(img_path)
                ref_list.append({
                    "image": {"inlineData": {"data": b64, "mimeType": mime}},
                    "referenceType": "asset"
                })
            instance["referenceImages"] = ref_list

    body = {
        "instances": [instance],
        "parameters": {
            "aspectRatio": ratio,
            "sampleCount": 1,
            "durationSeconds": duration,
        },
    }

    if resolution != DEFAULT_RESOLUTION:
        body["parameters"]["resolution"] = resolution

    if negative_prompt:
        body["parameters"]["negativePrompt"] = negative_prompt
    if seed is not None:
        body["parameters"]["seed"] = seed

    _progress({"status": "submitting", "backend": BACKEND_GEMINI_API,
               "model": model, "duration": duration})
    result = _http_request(url, data=body, method="POST")

    op_name = result.get("name")
    if not op_name:
        _error_exit(f"No operation name in response: {json.dumps(result)[:200]}")

    _progress({"status": "submitted", "operation": op_name})
    return op_name


def _submit_replicate(prompt, model, duration, ratio, resolution,
                      replicate_creds,
                      first_frame=None, last_frame=None, ref_images=None,
                      negative_prompt=None, seed=None, video_input=None):
    """POST to Replicate's predictions API.

    v4.2.1: handles both Kling v3 Std and the VEO 3.1 family (google/veo-3.1,
    google/veo-3.1-fast, google/veo-3.1-lite) now that Vertex has been retired.

    For Kling, translates the VEO-shaped kwargs to Kling's input schema via
    the existing validate_kling_params + build_kling_request_body helpers.
    For VEO-on-Replicate, delegates to the generic ReplicateBackend.submit()
    which translates canonical params (prompt, duration_s, aspect_ratio,
    start_image, end_image, negative_prompt, seed) via _TASK_PARAM_MAPS.

    Returns the prediction poll URL so _poll_replicate can GET directly
    without reconstructing the URL.
    """
    # VEO-family Replicate slugs use the generic ReplicateBackend surface.
    if model.startswith("google/veo-"):
        return _submit_replicate_via_backend(
            prompt=prompt, model=model, duration=duration, ratio=ratio,
            resolution=resolution, replicate_creds=replicate_creds,
            first_frame=first_frame, last_frame=last_frame,
            ref_images=ref_images, negative_prompt=negative_prompt,
            seed=seed, video_input=video_input,
        )

    # PixVerse V6 also uses the ReplicateBackend ABC path. Same dispatch
    # function as VEO; the backend's submit() recognizes the model_slug
    # prefix and translates canonical params to PixVerse's field names
    # (resolution → quality, start_image → image, end_image → last_frame_image,
    # audio_enabled → generate_audio_switch, multi_shot → generate_multi_clip_switch).
    if model.startswith("pixverse/pixverse-"):
        return _submit_replicate_via_backend(
            prompt=prompt, model=model, duration=duration, ratio=ratio,
            resolution=resolution, replicate_creds=replicate_creds,
            first_frame=first_frame, last_frame=last_frame,
            ref_images=ref_images, negative_prompt=negative_prompt,
            seed=seed, video_input=video_input,
        )

    # Kling path (preserved from v3.8.0) — uses the legacy Kling-specific
    # helpers (validate_kling_params / build_kling_request_body).
    if ref_images:
        _error_exit(
            "--reference-image is not supported by Kling v3 Std. "
            "Kling uses start_image + end_image for image-driven generation. "
            "For reference-image workflows, use --provider veo."
        )
    if video_input:
        _error_exit(
            "--video-input (Scene Extension v2) is not supported by Kling v3 Std. "
            "Kling's extended workflow uses multi_prompt chain via video_sequence.py. "
            "If you specifically need VEO Scene Extension v2, use "
            "--provider veo and acknowledge the spike 5 findings."
        )

    # Translate resolution → mode. Kling maxes at 1080p (pro). 4K was
    # already blocked upstream by MODELS_WITHOUT_4K, but double-check
    # defensively at the backend boundary.
    if resolution == "720p":
        mode = "standard"
    elif resolution == "1080p":
        mode = "pro"
    else:
        # 4K should have been caught upstream, but if it slips through,
        # downgrade silently with a progress note.
        _progress({
            "status": "resolution_downgraded",
            "reason": "Kling v3 Std maxes at 1080p (pro mode)",
            "from": resolution,
            "to": "1080p",
        })
        mode = "pro"

    # Translate first_frame / last_frame to Replicate data URIs.
    start_image_uri = None
    end_image_uri = None
    if first_frame:
        try:
            start_image_uri = replicate.image_path_to_data_uri(Path(first_frame))
        except replicate.ReplicateValidationError as e:
            _error_exit(f"Kling first-frame encode failed: {e}")
    if last_frame:
        try:
            end_image_uri = replicate.image_path_to_data_uri(Path(last_frame))
        except replicate.ReplicateValidationError as e:
            _error_exit(f"Kling last-frame encode failed: {e}")

    # Validate parameters against the Kling model card rules.
    try:
        replicate.validate_kling_params(
            aspect_ratio=ratio,
            duration=duration,
            mode=mode,
            start_image=start_image_uri,
            end_image=end_image_uri,
            prompt=prompt,
            negative_prompt=negative_prompt,
        )
    except replicate.ReplicateValidationError as e:
        _error_exit(f"Kling parameter validation failed: {e}")

    # Build request body and URL.
    body = replicate.build_kling_request_body(
        prompt=prompt,
        duration=duration,
        aspect_ratio=ratio,
        mode=mode,
        negative_prompt=negative_prompt,
        start_image=start_image_uri,
        end_image=end_image_uri,
    )
    url = replicate.build_predictions_url(model)

    _progress({
        "status": "submitting",
        "backend": BACKEND_REPLICATE,
        "model": model,
        "duration": duration,
        "mode": mode,
        "aspect_ratio": ratio,
    })

    try:
        result = replicate.replicate_post(
            url, body, token=replicate_creds["api_token"], timeout=120
        )
        prediction_id, poll_url = replicate.parse_replicate_submit_response(result)
    except replicate.ReplicateBackendError as e:
        _error_exit(f"Replicate submit failed: {e}")

    _progress({
        "status": "submitted",
        "backend": BACKEND_REPLICATE,
        "prediction_id": prediction_id,
    })
    # Return the poll URL — _poll_replicate needs the full URL, not just
    # the prediction ID.
    return poll_url


def _submit_replicate_via_backend(*, prompt, model, duration, ratio, resolution,
                                   replicate_creds, first_frame, last_frame,
                                   ref_images, negative_prompt, seed, video_input):
    """VEO-on-Replicate path (v4.2.1). Uses the generic ReplicateBackend ABC
    to submit via canonical params + _TASK_PARAM_MAPS translation.

    Pre-flight: reject Scene Extension v2 (Kling nor VEO-on-Replicate accept
    the `video` input parameter; this was a Vertex-only feature).
    """
    if video_input:
        _error_exit(
            "--video-input (Scene Extension v2) is a Vertex-only feature that "
            "was retired in v4.2.1. VEO on Replicate does not accept a video "
            "input parameter. Use --provider kling + video_sequence.py for "
            "extended workflows."
        )
    if ref_images:
        _error_exit(
            "--reference-image is not wired into the VEO-on-Replicate path. "
            "Use --first-frame / --last-frame for image-to-video."
        )

    task = "image-to-video" if first_frame else "text-to-video"
    is_pixverse = model.startswith("pixverse/pixverse-")
    encode_label = "PixVerse" if is_pixverse else "VEO"

    canonical_params: dict = {
        "prompt": prompt,
        "duration_s": duration,
        "aspect_ratio": ratio,
    }
    if negative_prompt:
        canonical_params["negative_prompt"] = negative_prompt
    if seed is not None:
        canonical_params["seed"] = seed
    if first_frame:
        try:
            canonical_params["start_image"] = replicate.image_path_to_data_uri(
                Path(first_frame)
            )
        except replicate.ReplicateValidationError as e:
            _error_exit(f"{encode_label} first-frame encode failed: {e}")
    if last_frame:
        try:
            canonical_params["end_image"] = replicate.image_path_to_data_uri(
                Path(last_frame)
            )
        except replicate.ReplicateValidationError as e:
            _error_exit(f"{encode_label} last-frame encode failed: {e}")

    # PixVerse-specific canonical extras. Submit()'s pixverse block reads
    # these from canonical_params (they're not in _TASK_PARAM_MAPS for
    # text-to-video / image-to-video). VEO's path ignores these keys.
    if is_pixverse:
        canonical_params["resolution"] = resolution
        # Plugin convention: audio is on by default. PixVerse's API default
        # is false. A future PR can add a CLI flag to override; for now,
        # always emit true.
        canonical_params["audio_enabled"] = True
        # multi_shot defaults to false. A future PR can add a CLI flag.

    # Build a minimal config dict for ReplicateBackend._api_key().
    config = {
        "providers": {"replicate": {"api_key": replicate_creds["api_token"]}},
    }

    _progress({
        "status": "submitting",
        "backend": BACKEND_REPLICATE,
        "model": model,
        "duration": duration,
        "aspect_ratio": ratio,
        "task": task,
    })

    try:
        job_ref = ReplicateBackend().submit(
            task=task,
            model_slug=model,
            canonical_params=canonical_params,
            provider_opts={},
            config=config,
        )
    except ProviderValidationError as e:
        _error_exit(f"Replicate VEO validation failed: {e}")
    except ProviderAuthError as e:
        _error_exit(f"Replicate auth failed: {e}")
    except (ProviderHTTPError, ProviderError) as e:
        _error_exit(f"Replicate submit failed: {e}")

    _progress({
        "status": "submitted",
        "backend": BACKEND_REPLICATE,
        "prediction_id": job_ref.external_id,
    })
    return job_ref.poll_url


def _submit_operation(*, backend, replicate_creds=None, **kwargs):
    """Dispatch to the right backend.

    v4.2.1: Vertex branch removed. Backends are: gemini (preview API) and
    replicate (Kling + VEO family).

    kwargs are forwarded to the backend-specific submit function. All backends
    share the core shape: prompt, model, duration, ratio, resolution,
    first_frame, last_frame, ref_images, negative_prompt, seed, video_input.
    """
    if backend == BACKEND_REPLICATE:
        return _submit_replicate(replicate_creds=replicate_creds, **kwargs)
    # Gemini API path: the api_key is already in kwargs as api_key=...
    return _submit_gemini_api(**kwargs)


def _poll_gemini_api(operation_name, api_key, interval, max_wait):
    """Poll the Gemini API operation endpoint via GET.

    Gemini API polling shape: GET /v1beta/{operation_name}?key={api_key}
    Returns the raw response dict on done=true.
    """
    url = f"{OPERATIONS_BASE}/{operation_name}?key={api_key}"
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            _error_exit(
                f"Timeout: operation not done after {max_wait}s. "
                f"Operation: {operation_name}"
            )

        result = _http_request(url, method="GET")

        if result.get("done"):
            error = result.get("error")
            if error:
                msg = error.get("message", str(error))
                if "safety" in msg.lower() or "blocked" in msg.lower():
                    _error_exit(f"VIDEO_SAFETY: {msg}")
                _error_exit(f"Operation failed: {msg}")
            return result

        _progress({"polling": True, "backend": BACKEND_GEMINI_API,
                   "elapsed": int(elapsed), "status": "processing"})
        time.sleep(interval)


def _poll_replicate(poll_url, replicate_creds, interval, max_wait):
    """Poll a Replicate prediction URL until it reaches a terminal state.

    poll_url is the full prediction GET URL returned by _submit_replicate
    (extracted from the submit response's urls.get field).

    Returns a tuple (status, payload):
      ("done", output_url_string)  — caller should download from the URL

    Raises via _error_exit() for failed / canceled / aborted / timeout.
    The Replicate Prediction.status enum has 6 values; parse_replicate_poll_
    response() already maps failed/canceled/aborted to the "failed" bucket.
    """
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            _error_exit(
                f"Timeout: Replicate prediction not done after {max_wait}s. "
                f"Poll URL: {poll_url}"
            )

        try:
            result = replicate.replicate_get(
                poll_url, token=replicate_creds["api_token"], timeout=30
            )
            status, payload = replicate.parse_replicate_poll_response(result)
        except replicate.ReplicateBackendError as e:
            _error_exit(f"Replicate poll failed: {e}")

        if status == "running":
            _progress({
                "polling": True,
                "backend": BACKEND_REPLICATE,
                "elapsed": int(elapsed),
                "status": "processing",
            })
            time.sleep(interval)
            continue

        if status == "done":
            # Kling v3 Std output is a single URI string per the model card.
            # Defensively handle list output for forward-compat with other
            # Replicate models that return arrays.
            if isinstance(payload, list):
                payload = payload[0] if payload else None
            if not payload:
                _error_exit("Replicate prediction succeeded but output is empty.")
            return ("done", payload)

        # status == "failed" (covers failed | canceled | aborted)
        err_str = str(payload) if payload else "unknown error"
        if "safety" in err_str.lower() or "nsfw" in err_str.lower():
            _error_exit(f"VIDEO_SAFETY: {err_str}")
        _error_exit(f"Replicate prediction failed: {err_str}")


def _poll_operation(*, backend, operation_name, api_key, replicate_creds,
                    model, interval, max_wait):
    """Dispatch polling to the right backend.

    v4.2.1: Vertex branch removed.

    Returns:
        - For Gemini API: the raw response dict (legacy shape), for _save_video
        - For Replicate: a tuple ("done", output_url_string)

    For Replicate, operation_name is actually the poll URL (full HTTPS URL)
    returned by _submit_replicate — not a prediction ID.
    """
    if backend == BACKEND_REPLICATE:
        return _poll_replicate(operation_name, replicate_creds, interval, max_wait)
    return _poll_gemini_api(operation_name, api_key, interval, max_wait)


def _save_video_gemini_api(response, output_dir, api_key=None):
    """Save video from a Gemini API poll response. Returns the output path.

    The Gemini API returns a response shape that's been through at least
    three variants in this codebase's history:
      - response.generateVideoResponse.generatedSamples[0].video.uri
      - response.generatedSamples[0].video.uri (older path)
      - samples[0].video.bytesBase64Encoded (inline bytes)

    We try each shape in turn. The video URI path requires downloading
    with the API key in the query string; the bytesBase64Encoded path
    writes directly.
    """
    resp_body = response.get("response", {})
    gen_resp = resp_body.get("generateVideoResponse", {})
    samples = gen_resp.get("generatedSamples", [])
    if not samples:
        samples = resp_body.get("generatedSamples", [])
    if not samples:
        _error_exit(
            f"No video in response. Response keys: {list(resp_body.keys())}, "
            f"body: {json.dumps(resp_body)[:300]}"
        )

    video_data = samples[0].get("video", {})
    b64 = video_data.get("bytesBase64Encoded")
    uri = video_data.get("uri")

    if not b64 and not uri:
        _error_exit(f"No video data or URI in response: {json.dumps(video_data)[:200]}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"video_{timestamp}.mp4"
    output_path = (out / filename).resolve()

    if b64:
        _progress({"status": "saving", "source": "base64"})
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(b64))
    else:
        _progress({"status": "downloading", "uri": uri})
        download_url = uri
        if api_key and "key=" not in uri:
            sep = "&" if "?" in uri else "?"
            download_url = f"{uri}{sep}key={api_key}"
        try:
            req = urllib.request.Request(download_url)
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(output_path, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            _error_exit(f"Failed to download video: {e}")

    return str(output_path)


def _save_video_replicate(output_url, output_dir):
    """Download a video from Replicate's delivery URL and save it locally.

    Replicate returns a pre-signed URL on succeeded predictions that's
    accessible without auth (the URL itself is the capability token). The
    URL typically lives at replicate.delivery/... and expires after a few
    hours, so we download immediately.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"video_{timestamp}.mp4"
    output_path = (out / filename).resolve()

    _progress({
        "status": "downloading",
        "backend": BACKEND_REPLICATE,
        "url": output_url,
    })

    try:
        req = urllib.request.Request(output_url)
        with urllib.request.urlopen(req, timeout=300) as resp:
            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        _error_exit(f"Failed to download Replicate video: {e}")

    return str(output_path)


def _save_video(*, backend, poll_result, output_dir, api_key=None):
    """Dispatch save to the right backend.

    v4.2.1: Vertex branch removed.

    poll_result is whatever _poll_operation returned for this backend:
      - Gemini API: the raw response dict
      - Replicate: a tuple ("done", output_url_string)
    """
    if backend == BACKEND_REPLICATE:
        status, output_url = poll_result
        if status != "done":
            _error_exit(
                f"_save_video called for Replicate with status={status!r}; "
                f"expected 'done'. Caller bug."
            )
        return _save_video_replicate(output_url, output_dir)
    return _save_video_gemini_api(poll_result, output_dir, api_key=api_key)


def _normalize_provider(provider, model_slug):
    """Resolve --provider alias to the canonical (provider, model_slug) pair.

    v4.2.1: --provider veo is a compat alias for --provider replicate with
    the VEO Fast tier default. Emits a deprecation warning.

    Returns a tuple (provider, model_slug). When the provider is unchanged
    (e.g. 'auto', 'kling', 'replicate'), both values are returned as-is.
    """
    if provider == "veo":
        import warnings
        warnings.warn(
            "--provider veo is deprecated. Use --provider replicate --model "
            "{google/veo-3.1-lite, google/veo-3.1-fast, google/veo-3.1} "
            "instead. This alias is honored for one release and will be "
            "removed in v4.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        # If user passed --provider veo without --model, default to Fast tier
        # (mid-tier balance per spike 5 findings). If they passed the Kling
        # default, override it — the intent of --provider veo is clearly VEO.
        if not model_slug or model_slug == "kwaivgi/kling-v3-video":
            model_slug = "google/veo-3.1-fast"
        return "replicate", model_slug
    return provider, model_slug


def main():
    parser = argparse.ArgumentParser(description="Generate video via Google VEO 3.1 REST API")
    parser.add_argument("--prompt", required=True, help="Video generation prompt")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION,
                        help=f"Duration in seconds. VEO 3.1 tiers: {{4,6,8}}. "
                             f"Kling v3 Std: any integer in [3, 15]. "
                             f"Scene Extension v2 (--video-input) uses 7. "
                             f"(default: {DEFAULT_DURATION})")
    parser.add_argument("--aspect-ratio", default=DEFAULT_RATIO,
                        help=f"Aspect ratio. VEO 3.1 tiers: 16:9 or 9:16. "
                             f"Kling v3 Std: 16:9, 9:16, or 1:1. "
                             f"(default: {DEFAULT_RATIO})")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION,
                        help=f"Resolution: 720p, 1080p, 4K. "
                             f"VEO Lite/Legacy and Kling v3 Std do not support 4K. "
                             f"Kling translates 720p→standard, 1080p→pro mode. "
                             f"(default: {DEFAULT_RESOLUTION})")
    parser.add_argument("--model", default=None,
                        help=f"Explicit model ID. If unset, resolved from --provider. "
                             f"Options: kwaivgi/kling-v3-video (default, Kling v3 Std), "
                             f"google/veo-3.1 (VEO Standard via Replicate), "
                             f"google/veo-3.1-fast (VEO Fast via Replicate), "
                             f"google/veo-3.1-lite (VEO Lite via Replicate), "
                             f"veo-3.1-generate-preview / veo-3.1-fast-generate-preview "
                             f"(Gemini preview API). Legacy Vertex IDs "
                             f"(veo-3.1-*-generate-001) are accepted and auto-translated "
                             f"to the Replicate slugs (deprecation warning, removed v4.3.0). "
                             f"(default: {DEFAULT_MODEL} via --provider auto)")
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "kling", "veo", "replicate"],
                        help="Video provider. 'auto' defaults to Kling v3 Std (v3.8.0+). "
                             "'kling' forces Kling v3 Std. 'replicate' is the explicit alias. "
                             "'veo' is a deprecated compat alias (auto-routes to replicate "
                             "with VEO Fast default; removed in v4.3.0). Per spike 5 findings, "
                             "Kling wins 8 of 15 shot types vs VEO 0, at 7.5x lower cost. "
                             "(default: auto)")
    parser.add_argument("--tier", default=None,
                        choices=["lite", "fast", "standard"],
                        help="VEO tier (used with --provider veo). 'lite' is cheapest "
                             "and recommended per spike 5 — Fast and Standard tier "
                             "premiums were imperceptible at 1fps sampling. "
                             "(default: lite when --provider veo)")
    parser.add_argument("--first-frame", default=None, help="Path to first frame image")
    parser.add_argument("--last-frame", default=None, help="Path to last frame image")
    parser.add_argument("--reference-image", nargs="+", default=None,
                        help="Reference image paths (up to 3). Preview Gemini API only; "
                             "Replicate-hosted models use --first-frame / --last-frame.")
    parser.add_argument("--video-input", default=None,
                        help="DEPRECATED in v4.2.1. Scene Extension v2 was a Vertex-only "
                             "feature and Vertex has been retired. For extended-shot "
                             "workflows, use video_sequence.py with the Kling shot-list "
                             "pipeline. Accepted by argparse for backwards compatibility "
                             "but will error out during validation.")
    parser.add_argument("--negative-prompt", default=None,
                        help="What to avoid in the generation (e.g. 'blurry, low quality, distorted')")
    parser.add_argument("--seed", type=int, default=None,
                        help="Integer seed for reproducible results")
    parser.add_argument("--api-key", default=None, help="Google AI API key (Gemini API backend)")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f"Seconds between polls (default: {DEFAULT_POLL_INTERVAL})")
    parser.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT,
                        help=f"Max wait seconds (default: {DEFAULT_MAX_WAIT})")
    parser.add_argument("--output", default=str(OUTPUT_DIR),
                        help=f"Output directory (default: {OUTPUT_DIR})")
    # Backend selection (v3.6.0). v4.2.1: 'vertex-ai' is deprecated and auto-
    # routes to 'replicate' with a DeprecationWarning. All VEO 3.1 traffic
    # goes through Replicate now.
    parser.add_argument("--backend", default=BACKEND_AUTO, choices=sorted(VALID_BACKENDS),
                        help=f"Which backend to use. 'auto' picks Replicate for "
                             f"slugs containing '/' (Kling, VEO-on-Replicate), Gemini "
                             f"API for preview IDs. 'vertex-ai' is deprecated and "
                             f"auto-routes to 'replicate'. (default: {BACKEND_AUTO})")
    # v4.2.1: Vertex credential flags retained so scripts that pass them don't
    # crash on unrecognized-argument; they're unused and emit a deprecation
    # warning when the user provides them.
    parser.add_argument("--vertex-api-key", default=None,
                        help="DEPRECATED in v4.2.1 — Vertex AI retired. Flag is ignored.")
    parser.add_argument("--vertex-project", default=None,
                        help="DEPRECATED in v4.2.1 — Vertex AI retired. Flag is ignored.")
    parser.add_argument("--vertex-location", default=None,
                        help="DEPRECATED in v4.2.1 — Vertex AI retired. Flag is ignored.")
    parser.add_argument("--replicate-key", default=None,
                        help="Replicate API token (for Kling v3 Std + VEO 3.1 family). "
                             "Loads from REPLICATE_API_TOKEN env or ~/.banana/config.json "
                             "replicate_api_token field if unset. Set via "
                             "`python3 skills/create-image/scripts/setup_mcp.py --replicate-key TOKEN`.")

    args = parser.parse_args()

    # v4.2.1: warn-and-ignore on deprecated Vertex credential flags.
    if args.vertex_api_key or args.vertex_project or args.vertex_location:
        import warnings
        warnings.warn(
            "--vertex-api-key / --vertex-project / --vertex-location are "
            "deprecated in v4.2.1 and ignored. VEO 3.1 now routes through "
            "Replicate; set --replicate-key or REPLICATE_API_TOKEN.",
            DeprecationWarning,
            stacklevel=2,
        )

    # v4.2.1: normalize --provider aliases (veo → replicate with Fast default).
    args.provider, args.model = _normalize_provider(args.provider, args.model)

    # v3.8.0: Resolve --provider to a concrete --model if --model wasn't
    # explicitly set. Explicit --model always wins — this lets power users
    # override the provider mapping without fighting argparse defaults.
    if args.model is None:
        if args.provider in ("auto", "kling"):
            args.model = "kwaivgi/kling-v3-video"
        elif args.provider == "replicate":
            # Bare --provider replicate without --model: default to VEO Fast
            # (balanced mid-tier option). Users who want Kling should use
            # --provider kling or pass --model explicitly.
            tier = args.tier or "fast"
            veo_tier_map = {
                "lite":     "google/veo-3.1-lite",
                "fast":     "google/veo-3.1-fast",
                "standard": "google/veo-3.1",
            }
            args.model = veo_tier_map[tier]

    # v4.2.1: translate legacy Vertex model IDs to Replicate slugs.
    # Deprecation warning lands on first use. Runs AFTER provider resolution
    # so --provider veo → --model google/veo-3.1-fast doesn't trigger a
    # bogus "legacy Vertex ID" warning.
    if args.model != _translate_vertex_model_id(args.model):
        import warnings
        new_slug = _translate_vertex_model_id(args.model)
        warnings.warn(
            f"Model ID {args.model!r} is a legacy Vertex identifier. "
            f"Translated to Replicate slug {new_slug!r}. "
            f"Update scripts to use the Replicate slug directly; Vertex "
            f"translation will be removed in v4.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        args.model = new_slug

    # Prompt length sanity check (VEO 3.1 = 1,024 token limit, English only).
    # Approximate: ~4 chars/token for English prose.
    prompt_len = len(args.prompt)
    if prompt_len > PROMPT_ERROR_CHARS:
        _error_exit(
            f"Prompt is {prompt_len} characters (~{prompt_len // 4} tokens). "
            f"VEO 3.1 limit is 1,024 tokens (~4,096 characters). "
            f"Shorten the prompt or split into multiple shots."
        )
    elif prompt_len > PROMPT_WARN_CHARS:
        _progress({
            "warning": "prompt_approaching_limit",
            "chars": prompt_len,
            "estimated_tokens": prompt_len // 4,
            "limit_tokens": 1024,
        })

    # Validate model first so later validations can be model-aware
    if args.model not in VALID_MODELS:
        _error_exit(
            f"Invalid model '{args.model}'. Valid: {sorted(VALID_MODELS)}. "
            f"Tip: use 'kwaivgi/kling-v3-video' for default Kling v3 Std, or "
            f"'google/veo-3.1-fast' for VEO Fast via Replicate."
        )

    # Resolve the backend up front so the remaining validations and
    # gates can be backend-aware.
    backend = _select_backend(args)

    # v4.2.1: Gemini-API preview path only accepts preview IDs. The Replicate
    # VEO family is handled by --backend auto routing (slugs with "/").
    if backend == BACKEND_GEMINI_API and "/" in args.model:
        _error_exit(
            f"'{args.model}' is a Replicate model slug and cannot be served "
            f"via the Gemini API. Drop --backend gemini-api (default "
            f"--backend auto will route this model through Replicate)."
        )

    # Duration validation. VEO 3.1 tiers accept {4, 6, 8}; Kling accepts [3, 15].
    valid_durations = _valid_durations(args.model)
    if args.duration not in valid_durations:
        _error_exit(
            f"Invalid duration {args.duration} for {args.model}. "
            f"Valid: {sorted(valid_durations)}."
        )

    # Aspect ratio validation. All VEO 3.1 tiers support {16:9, 9:16}.
    valid_ratios = _valid_ratios(args.model)
    if args.aspect_ratio not in valid_ratios:
        _error_exit(
            f"Invalid aspect ratio '{args.aspect_ratio}' for {args.model}. "
            f"Valid: {sorted(valid_ratios)}."
        )

    # Resolution validation (4K not available on Lite / Legacy / Kling)
    if args.resolution not in VALID_RESOLUTIONS:
        _error_exit(f"Invalid resolution '{args.resolution}'. Valid: {sorted(VALID_RESOLUTIONS)}")
    if args.resolution == "4K" and args.model in MODELS_WITHOUT_4K:
        _error_exit(
            f"{args.model} does not support 4K. "
            f"Use --resolution 1080p, or switch to 'google/veo-3.1' / "
            f"'google/veo-3.1-fast' (Replicate VEO Standard / Fast) for 4K output."
        )

    if args.reference_image and len(args.reference_image) > 3:
        _error_exit("Maximum 3 reference images allowed")

    # v4.2.1: Scene Extension v2 was a Vertex-only feature. Vertex is retired,
    # so --video-input is always an error now. Point users at video_sequence.py
    # for the recommended shot-list pipeline.
    if args.video_input:
        _error_exit(
            "--video-input (Scene Extension v2) was a Vertex-only feature and "
            "is unavailable in v4.2.1 (Vertex AI retired). For extended-shot "
            "workflows, use video_sequence.py with the Kling shot-list pipeline."
        )

    # Load credentials for whichever backend we're going to use.
    # v4.2.1: Vertex credentials path removed. Backends are Gemini API (preview
    # tier text-to-video only) and Replicate (Kling + VEO 3.1 family).
    api_key = None
    replicate_creds = None
    if backend == BACKEND_GEMINI_API:
        api_key = _load_api_key(args.api_key)
    else:  # BACKEND_REPLICATE
        try:
            replicate_creds = replicate.load_replicate_credentials(
                cli_token=args.replicate_key,
            )
        except replicate.ReplicateAuthError as e:
            _error_exit(str(e))
        _progress({
            "status": "backend_selected",
            "backend": BACKEND_REPLICATE,
            "model": args.model,
        })

    gen_start = time.time()

    # Submit + Poll. v4.2.1: Vertex-only service-agent retry loop removed.
    submit_kwargs = dict(
        prompt=args.prompt,
        model=args.model,
        duration=args.duration,
        ratio=args.aspect_ratio,
        resolution=args.resolution,
        first_frame=args.first_frame,
        last_frame=args.last_frame,
        ref_images=args.reference_image,
        negative_prompt=args.negative_prompt,
        seed=args.seed,
        video_input=args.video_input,
    )
    if backend == BACKEND_GEMINI_API:
        submit_kwargs["api_key"] = api_key

    operation_name = _submit_operation(
        backend=backend,
        replicate_creds=replicate_creds,
        **submit_kwargs,
    )
    poll_result = _poll_operation(
        backend=backend,
        operation_name=operation_name,
        api_key=api_key,
        replicate_creds=replicate_creds,
        model=args.model,
        interval=args.poll_interval,
        max_wait=args.max_wait,
    )

    video_path = _save_video(
        backend=backend,
        poll_result=poll_result,
        output_dir=args.output,
        api_key=api_key,
    )
    gen_time = round(time.time() - gen_start, 1)

    result = {
        "path": video_path,
        "model": args.model,
        "duration": args.duration,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        "prompt": args.prompt,
        "generation_time_seconds": gen_time,
        "backend": backend,
    }
    # The 48-hour download expiry only applies to the Gemini API path,
    # which returns a URI the plugin downloads (we already have the bytes
    # locally after _save_video, but users who keep manifests around might
    # try to re-fetch the URI later). Vertex returns video bytes inline
    # in the poll response — no URI, no expiry.
    if backend == BACKEND_GEMINI_API:
        result["download_expires_at"] = (
            datetime.now(timezone.utc) + timedelta(hours=DOWNLOAD_RETENTION_HOURS)
        ).isoformat()

    if args.first_frame:
        result["first_frame"] = args.first_frame
    if args.last_frame:
        result["last_frame"] = args.last_frame
    if args.video_input:
        result["video_input"] = args.video_input

    print(json.dumps(result, indent=2))

    # Log cost to ~/.banana/costs.json (v3.8.3+). Shell out to cost_tracker.py
    # to avoid cross-skill imports. v4.2.1: cost logging now passes resolution
    # + --duration-s + --audio-enabled separately for ALL models. _lookup_cost()
    # dispatches on which fields the model's pricing mode needs; unused fields
    # are silently ignored. This removes the old Kling-vs-legacy branch split
    # that was fragile (would miss a future non-Kling 2D-audio model) AND that
    # previously had a NameError bug — `model` without `args.` prefix — which
    # the outer try/except swallowed so every Kling cost log silently failed.
    # TODO(v4.2.x): thread a --no-audio CLI flag through to generate_audio=False.
    # Currently Kling always uses generate_audio=True (see build_kling_request_body
    # in scripts/backends/_replicate.py). When that changes, the hardcoded "true"
    # below needs to honor the actual user setting via args.<flag>.
    try:
        _cost_tracker = str(Path(__file__).resolve().parent.parent.parent / "create-image" / "scripts" / "cost_tracker.py")
        _prompt_summary = (args.prompt or "")[:80]
        subprocess.run(
            [
                sys.executable, _cost_tracker, "log",
                "--model", args.model,
                "--resolution", args.resolution,
                "--duration-s", str(args.duration),
                "--audio-enabled", "true",
                "--prompt", _prompt_summary,
            ],
            capture_output=True, timeout=5, check=False,
        )
    except Exception:
        pass  # Cost logging is best-effort; never block generation output

    if backend == BACKEND_GEMINI_API:
        print(
            f"Note: The source download URI expires in {DOWNLOAD_RETENTION_HOURS} hours. "
            f"The MP4 has been saved to disk at {video_path}.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
