#!/usr/bin/env python3
"""Creators Studio -- Asset Registry

Manage persistent character, product, and object references for
consistent image generation across sessions.

Usage:
    assets.py list
    assets.py show NAME
    assets.py create NAME --type product --description "..." --reference ~/photo.jpg
    assets.py delete NAME --confirm
    assets.py add-image NAME --reference ~/new-photo.jpg
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# v4.2.2: import the migration helper from plugin-root scripts/paths.py.
_plugin_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)
from scripts.paths import assets_dir as _csd_assets  # noqa: E402

ASSETS_DIR = _csd_assets()
VALID_TYPES = {"character", "product", "equipment", "environment"}
MAX_IMAGE_SIZE = 7 * 1024 * 1024  # 7MB per Gemini API limit
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _ensure_dir():
    """Create assets directory if it doesn't exist."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_name(name):
    """Sanitize asset name for filesystem safety."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '-', name).strip('-').lower()


def _asset_path(name):
    """Get the full path for an asset JSON file."""
    return ASSETS_DIR / f"{_sanitize_name(name)}.json"


def _load_asset(path):
    """Load and parse an asset JSON file."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        return None


def _validate_image(path_str):
    """Validate an image file exists, is under 7MB, and is a supported format."""
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        print(f"Error: Image not found: {path}", file=sys.stderr)
        sys.exit(1)
    if path.stat().st_size > MAX_IMAGE_SIZE:
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"Error: Image too large: {path} ({size_mb:.1f}MB, max 7MB)", file=sys.stderr)
        sys.exit(1)
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        print(f"Error: Unsupported format: {path.suffix}. Use: {', '.join(sorted(SUPPORTED_FORMATS))}", file=sys.stderr)
        sys.exit(1)
    return str(path)


def cmd_list(args):
    """List all saved assets."""
    _ensure_dir()
    files = sorted(ASSETS_DIR.glob("*.json"))
    if not files:
        print("No assets saved yet.")
        print(f"  Create one: assets.py create NAME --type product --description \"...\" --reference ~/photo.jpg")
        return

    print(f"{'Name':<25} {'Type':<12} {'Images':<8} {'Description'}")
    print("-" * 80)
    for f in files:
        asset = _load_asset(f)
        if asset:
            name = asset.get("name", f.stem)
            atype = asset.get("type", "unknown")
            images = len(asset.get("reference_images", []))
            desc = asset.get("description", "")[:40]
            print(f"{name:<25} {atype:<12} {images:<8} {desc}")
    print(f"\n{len(files)} asset(s) saved.")


def cmd_show(args):
    """Show full asset details."""
    path = _asset_path(args.name)
    if not path.exists():
        print(f"Error: Asset '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)
    asset = _load_asset(path)
    if asset:
        print(json.dumps(asset, indent=2))


def cmd_create(args):
    """Create a new asset."""
    _ensure_dir()
    sanitized = _sanitize_name(args.name)
    path = _asset_path(sanitized)

    if path.exists() and not args.force:
        print(f"Error: Asset '{sanitized}' already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    if args.type not in VALID_TYPES:
        print(f"Error: Invalid type '{args.type}'. Valid: {', '.join(sorted(VALID_TYPES))}", file=sys.stderr)
        sys.exit(1)

    # Validate and resolve reference image paths
    reference_images = []
    if args.reference:
        for ref in args.reference:
            validated = _validate_image(ref)
            reference_images.append(validated)

    asset = {
        "name": sanitized,
        "type": args.type,
        "description": args.description or "",
        "reference_images": reference_images,
        "default_context": args.default_context or "",
        "consistency_notes": args.consistency_notes or "",
    }

    with open(path, "w") as f:
        json.dump(asset, f, indent=2)

    print(f"Asset '{sanitized}' created at {path}")
    print(f"  Type: {args.type}")
    print(f"  Images: {len(reference_images)}")
    if reference_images:
        for img in reference_images:
            print(f"    - {img}")


def cmd_delete(args):
    """Delete an asset."""
    if not args.confirm:
        print("Error: Pass --confirm to delete the asset.", file=sys.stderr)
        sys.exit(1)
    path = _asset_path(args.name)
    if not path.exists():
        print(f"Error: Asset '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)
    path.unlink()
    print(f"Asset '{args.name}' deleted.")


def cmd_add_image(args):
    """Add a reference image to an existing asset."""
    path = _asset_path(args.name)
    if not path.exists():
        print(f"Error: Asset '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)

    asset = _load_asset(path)
    if not asset:
        sys.exit(1)

    # Validate the new image
    validated = _validate_image(args.reference)

    # Check total image count (Gemini limit: 14 per request)
    current_count = len(asset.get("reference_images", []))
    if current_count >= 14:
        print(f"Error: Asset already has {current_count} images (Gemini max: 14 per request).", file=sys.stderr)
        sys.exit(1)

    # Check for duplicate
    if validated in asset.get("reference_images", []):
        print(f"Warning: Image already in asset: {validated}")
        return

    asset.setdefault("reference_images", []).append(validated)

    with open(path, "w") as f:
        json.dump(asset, f, indent=2)

    print(f"Added image to '{args.name}': {validated}")
    print(f"  Total images: {len(asset['reference_images'])}")


def main():
    parser = argparse.ArgumentParser(description="Creators Studio Asset Registry")
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    sub.add_parser("list", help="List all saved assets")

    # show
    p_show = sub.add_parser("show", help="Show asset details")
    p_show.add_argument("name", help="Asset name")

    # create
    p_create = sub.add_parser("create", help="Create a new asset")
    p_create.add_argument("name", help="Asset name (e.g., itero-scanner, alex)")
    p_create.add_argument("--type", required=True, choices=sorted(VALID_TYPES),
                          help="Asset type: character, product, equipment, environment")
    p_create.add_argument("--description", default="", help="Physical description of the asset")
    p_create.add_argument("--reference", action="append", default=[],
                          help="Path to reference image (can be repeated, max 14)")
    p_create.add_argument("--default-context", default="", help="Default setting/context for this asset")
    p_create.add_argument("--consistency-notes", default="",
                          help="Notes on what to always maintain (e.g., 'LED ring always illuminated')")
    p_create.add_argument("--force", action="store_true", help="Overwrite existing asset")

    # delete
    p_delete = sub.add_parser("delete", help="Delete an asset")
    p_delete.add_argument("name", help="Asset name")
    p_delete.add_argument("--confirm", action="store_true", help="Confirm deletion")

    # add-image
    p_add = sub.add_parser("add-image", help="Add a reference image to an existing asset")
    p_add.add_argument("name", help="Asset name")
    p_add.add_argument("--reference", required=True, help="Path to the image to add")

    args = parser.parse_args()
    cmds = {"list": cmd_list, "show": cmd_show, "create": cmd_create,
            "delete": cmd_delete, "add-image": cmd_add_image}
    cmds[args.command](args)


if __name__ == "__main__":
    main()
