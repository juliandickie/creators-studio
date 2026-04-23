"""Tests for scripts/backends/_canonical.py."""
import base64
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backends import _canonical


class TestNormalizeImage(unittest.TestCase):
    def test_path_to_data_uri(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
            tmp_path = Path(f.name)
        try:
            uri = _canonical.normalize_image_to_data_uri(tmp_path)
            self.assertTrue(uri.startswith("data:image/png;base64,"))
            decoded = base64.b64decode(uri.split(",", 1)[1])
            self.assertTrue(decoded.startswith(b"\x89PNG"))
        finally:
            tmp_path.unlink()

    def test_bytes_to_data_uri(self):
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
        uri = _canonical.normalize_image_to_data_uri(jpeg_bytes)
        self.assertTrue(uri.startswith("data:image/jpeg;base64,"))

    def test_data_uri_passes_through(self):
        existing = "data:image/webp;base64,UklGRg=="
        uri = _canonical.normalize_image_to_data_uri(existing)
        self.assertEqual(uri, existing)

    def test_http_url_raises(self):
        # normalize_to_data_uri shouldn't hit network; URL normalization is
        # a different function (normalize_image_to_url)
        with self.assertRaises(ValueError):
            _canonical.normalize_image_to_data_uri("https://example.com/img.png")

    def test_unsupported_bytes_raises(self):
        with self.assertRaises(ValueError):
            _canonical.normalize_image_to_data_uri(b"not a valid image header")

    def test_webp_detected_correctly(self):
        # WebP: "RIFF" + 4 bytes size + "WEBP"
        webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 24
        uri = _canonical.normalize_image_to_data_uri(webp)
        self.assertTrue(uri.startswith("data:image/webp;base64,"))

    def test_riff_non_webp_rejected(self):
        # RIFF but not WebP (e.g., WAV) should not sniff as image/webp
        wav = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 24
        with self.assertRaises(ValueError):
            _canonical.normalize_image_to_data_uri(wav)


class TestNormalizeImageToUrl(unittest.TestCase):
    def test_http_passes_through(self):
        u = _canonical.normalize_image_to_url("https://example.com/x.png")
        self.assertEqual(u, "https://example.com/x.png")

    def test_data_uri_passes_through(self):
        u = _canonical.normalize_image_to_url("data:image/png;base64,AAAA")
        self.assertEqual(u, "data:image/png;base64,AAAA")

    def test_path_raises(self):
        with self.assertRaises(ValueError):
            _canonical.normalize_image_to_url(Path("/tmp/x.png"))

    def test_bytes_raises(self):
        with self.assertRaises(ValueError):
            _canonical.normalize_image_to_url(b"\x89PNG")


class TestValidateConstraints(unittest.TestCase):
    def test_duration_in_range_passes(self):
        constraints = {"duration_s": {"min": 3, "max": 15, "integer": True}}
        # Should not raise
        _canonical.validate_canonical_params(
            constraints, {"duration_s": 8}
        )

    def test_duration_out_of_range_raises(self):
        constraints = {"duration_s": {"min": 3, "max": 15, "integer": True}}
        with self.assertRaises(_canonical.CanonicalValidationError):
            _canonical.validate_canonical_params(
                constraints, {"duration_s": 30}
            )

    def test_duration_non_integer_raises_when_integer_required(self):
        constraints = {"duration_s": {"min": 3, "max": 15, "integer": True}}
        with self.assertRaises(_canonical.CanonicalValidationError):
            _canonical.validate_canonical_params(
                constraints, {"duration_s": 8.5}
            )

    def test_duration_enum_accepts_allowed_value(self):
        constraints = {"duration_s": {"enum": [4, 6, 8]}}
        # Should not raise
        _canonical.validate_canonical_params(
            constraints, {"duration_s": 6}
        )

    def test_duration_enum_rejects_disallowed_value(self):
        constraints = {"duration_s": {"enum": [4, 6, 8]}}
        with self.assertRaises(_canonical.CanonicalValidationError):
            _canonical.validate_canonical_params(
                constraints, {"duration_s": 5}
            )

    def test_duration_enum_rejects_out_of_range(self):
        constraints = {"duration_s": {"enum": [4, 6, 8]}}
        with self.assertRaises(_canonical.CanonicalValidationError):
            _canonical.validate_canonical_params(
                constraints, {"duration_s": 10}
            )

    def test_duration_min_max_still_works(self):
        # Existing shape {min, max, integer} must still work after enum added
        constraints = {"duration_s": {"min": 3, "max": 15, "integer": True}}
        _canonical.validate_canonical_params(
            constraints, {"duration_s": 8}
        )
        with self.assertRaises(_canonical.CanonicalValidationError):
            _canonical.validate_canonical_params(
                constraints, {"duration_s": 20}
            )

    def test_aspect_ratio_valid(self):
        constraints = {"aspect_ratio": ["16:9", "9:16", "1:1"]}
        _canonical.validate_canonical_params(
            constraints, {"aspect_ratio": "16:9"}
        )

    def test_aspect_ratio_invalid(self):
        constraints = {"aspect_ratio": ["16:9", "9:16", "1:1"]}
        with self.assertRaises(_canonical.CanonicalValidationError):
            _canonical.validate_canonical_params(
                constraints, {"aspect_ratio": "4:3"}
            )

    def test_resolution_valid(self):
        constraints = {"resolutions": ["720p", "1080p"]}
        _canonical.validate_canonical_params(
            constraints, {"resolution": "720p"}
        )

    def test_prompt_length_ok(self):
        constraints = {"prompt_max_chars": 100}
        _canonical.validate_canonical_params(
            constraints, {"prompt": "short"}
        )

    def test_prompt_too_long_raises(self):
        constraints = {"prompt_max_chars": 10}
        with self.assertRaises(_canonical.CanonicalValidationError):
            _canonical.validate_canonical_params(
                constraints, {"prompt": "this is definitely more than ten characters"}
            )

    def test_missing_constraint_key_is_skipped(self):
        # If param is absent from request, constraint doesn't apply
        constraints = {"duration_s": {"min": 3, "max": 15, "integer": True}}
        _canonical.validate_canonical_params(constraints, {})  # no raise

    def test_unknown_constraint_key_ignored(self):
        # Forward-compat: unknown constraint keys don't crash validation
        constraints = {"future_constraint": "whatever"}
        _canonical.validate_canonical_params(constraints, {"prompt": "x"})


if __name__ == "__main__":
    unittest.main()
