"""Creators Studio — Canonical param validation and image normalization.

Sits between the orchestrator and backend: validates canonical_params
against a model's canonical_constraints BEFORE any HTTP call, and
normalizes CanonicalImage inputs to forms backends accept.

Stdlib only. Python 3.12+.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any


class CanonicalValidationError(Exception):
    """A canonical parameter violates the model's canonical constraints."""


# ─── Image normalization ─────────────────────────────────────────────────

# Recognized magic bytes for stdlib-only format sniffing.
_MAGIC_BYTES_TO_MIME: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff",      "image/jpeg"),
    (b"GIF87a",            "image/gif"),
    (b"GIF89a",            "image/gif"),
    (b"RIFF",              "image/webp"),  # WebP starts with RIFF....WEBP; verified below
]


def _sniff_mime_from_bytes(data: bytes) -> str:
    for magic, mime in _MAGIC_BYTES_TO_MIME:
        if data.startswith(magic):
            # Extra WEBP check: RIFF container could also be WAV etc.
            if magic == b"RIFF":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return "image/webp"
                continue
            return mime
    raise ValueError("could not sniff image MIME from magic bytes")


def normalize_image_to_data_uri(img: Path | str | bytes) -> str:
    """Convert any CanonicalImage form to a data URI.

    Accepts:
      - Path — read bytes, sniff MIME, encode
      - bytes — sniff MIME, encode
      - str starting with 'data:' — pass through
      - str starting with 'http://' or 'https://' — RAISES (different function)
    """
    if isinstance(img, Path):
        data = img.read_bytes()
        mime = mimetypes.guess_type(str(img))[0] or _sniff_mime_from_bytes(data)
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    if isinstance(img, bytes):
        mime = _sniff_mime_from_bytes(img)
        return f"data:{mime};base64,{base64.b64encode(img).decode('ascii')}"

    if isinstance(img, str):
        if img.startswith("data:"):
            return img
        if img.startswith(("http://", "https://")):
            raise ValueError(
                "normalize_image_to_data_uri was given an HTTP URL; use "
                "normalize_image_to_url() for backends that prefer URLs"
            )
        raise ValueError(f"unrecognized string image form: {img[:40]!r}")

    raise TypeError(f"unsupported image type: {type(img).__name__}")


def normalize_image_to_url(img: Path | str | bytes) -> str:
    """Convert CanonicalImage to a URL form, if possible.

    Pass-through for HTTP URLs. Data URIs pass through too (most backends
    accept them where they accept URLs). Path/bytes would require an
    uploader, which this function doesn't do — it raises to signal the
    backend should use the data-URI path instead.
    """
    if isinstance(img, str) and img.startswith(("http://", "https://", "data:")):
        return img
    raise ValueError(
        "cannot convert Path/bytes to URL without an uploader; "
        "use normalize_image_to_data_uri() or implement upload in the backend"
    )


# ─── Constraint validation ───────────────────────────────────────────────


def validate_canonical_params(
    constraints: dict[str, Any],
    params: dict[str, Any],
) -> None:
    """Validate params against constraints. Raises CanonicalValidationError.

    Constraint keys recognized:
      duration_s          — {min, max, integer?}
      aspect_ratio        — list of allowed strings
      resolutions         — list of allowed strings, checked against 'resolution' param
      prompt_max_chars    — int, checked against 'prompt' param
      max_input_bytes     — int, checked against source_image byte length
      max_input_pixels    — int, NOT validated here (requires PIL — deferred)
      input_dim_range     — {min_px, max_px}, NOT validated here (requires PIL — deferred)

    Unknown constraint keys are silently ignored (forward-compatible).
    Missing params are skipped (the constraint doesn't apply).
    """
    # duration_s
    if (c := constraints.get("duration_s")) is not None and "duration_s" in params:
        v = params["duration_s"]
        if "enum" in c:
            # Enum shape: {enum: [4, 6, 8]} — only listed values allowed.
            if v not in c["enum"]:
                raise CanonicalValidationError(
                    f"duration_s={v} not in allowed values {c['enum']}"
                )
        else:
            # Range shape: {min, max, integer?}
            if c.get("integer") and not isinstance(v, int):
                raise CanonicalValidationError(
                    f"duration_s must be an integer; got {type(v).__name__} ({v!r})"
                )
            if (lo := c.get("min")) is not None and v < lo:
                raise CanonicalValidationError(f"duration_s={v} is below minimum {lo}")
            if (hi := c.get("max")) is not None and v > hi:
                raise CanonicalValidationError(f"duration_s={v} exceeds maximum {hi}")

    # aspect_ratio
    if (c := constraints.get("aspect_ratio")) is not None and "aspect_ratio" in params:
        if params["aspect_ratio"] not in c:
            raise CanonicalValidationError(
                f"aspect_ratio={params['aspect_ratio']!r} not in allowed {c}"
            )

    # resolution
    if (c := constraints.get("resolutions")) is not None and "resolution" in params:
        if params["resolution"] not in c:
            raise CanonicalValidationError(
                f"resolution={params['resolution']!r} not in allowed {c}"
            )

    # prompt_max_chars
    if (c := constraints.get("prompt_max_chars")) is not None and "prompt" in params:
        if len(params["prompt"]) > c:
            raise CanonicalValidationError(
                f"prompt length {len(params['prompt'])} exceeds maximum {c}"
            )

    # max_input_bytes (applies when source_image is bytes or Path)
    if (c := constraints.get("max_input_bytes")) is not None and "source_image" in params:
        img = params["source_image"]
        match img:
            case Path():
                size = img.stat().st_size
            case bytes():
                size = len(img)
            case _:
                return  # URL/data-URI — skip byte-size check
        if size > c:
            raise CanonicalValidationError(
                f"source_image size {size} exceeds maximum {c}"
            )
