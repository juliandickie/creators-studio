#!/usr/bin/env python3
"""
Validate that the Creators Studio MCP server is properly configured.

Checks:
1. Claude Code settings.json has the MCP entry
2. API key is present
3. Node.js/npx is available
4. Output directory exists or can be created

Usage:
    python3 validate_setup.py
"""

import json
import shutil
import sys
from pathlib import Path

# v4.2.2: import the migration helper from plugin-root scripts/paths.py.
_plugin_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)
from scripts.paths import creators_studio_dir as _csd, migration_status as _migration_status  # noqa: E402

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
MCP_NAME = "nanobanana-mcp"
OUTPUT_DIR = Path.home() / "Documents" / "creators_generated"


def check(label: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    return passed


def _print_migration_status() -> int:
    """Print v4.2.2 ~/.banana/ → ~/.creators-studio/ migration status. Used by --check-migration."""
    print("Creators Studio -- Config Directory Migration Status (v4.2.2+)")
    print("=" * 65)
    status = _migration_status()
    state_label = {
        "migrated":  "[OK]    Migration complete",
        "new_only":  "[OK]    Fresh v4.2.2+ install (no migration needed)",
        "old_only":  "[INFO]  Pre-v4.2.2 install — next plugin command will migrate",
        "none":      "[NEW]   First-ever install — run /create-image setup to begin",
    }[status["state"]]
    print(f"State:           {state_label}")
    print(f"New path:        {status['new_path']}    (exists: {status['new_exists']})")
    print(f"Old path:        {status['old_path']}    (exists: {status['old_exists']})")
    print()
    print("Recommendation:")
    for line in status["recommendation"].split(". "):
        if line.strip():
            print(f"  {line.strip().rstrip('.')}.")
    print()
    print("Notes:")
    print("  * The old directory (~/.banana/) is NEVER auto-deleted. After")
    print("    verifying the new path works (e.g., generate an image and")
    print("    confirm it logs to the new path's costs.json), you can")
    print("    safely run: rm -rf ~/.banana/")
    print("  * Migration is COPY (not move). Both directories may exist")
    print("    simultaneously during the transition period without divergence")
    print("    risk — all v4.2.2+ writes go to the new path.")
    return 0


def main() -> int:
    # v4.2.2: --check-migration shortcut
    if len(sys.argv) > 1 and sys.argv[1] == "--check-migration":
        return _print_migration_status()

    print("Creators Studio -- Setup Validation")
    print("=" * 40)
    results = []

    # 1. Settings file exists
    results.append(check(
        "Claude Code settings.json exists",
        SETTINGS_PATH.exists(),
        str(SETTINGS_PATH),
    ))

    if not SETTINGS_PATH.exists():
        print("\nCannot continue without settings.json.")
        return 1

    # 2. Load and parse settings
    try:
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
        results.append(check("settings.json is valid JSON", True))
    except json.JSONDecodeError as e:
        results.append(check("settings.json is valid JSON", False, str(e)))
        return 1

    # 3. MCP entry exists
    servers = settings.get("mcpServers", {})
    has_mcp = MCP_NAME in servers
    results.append(check(f"MCP server '{MCP_NAME}' configured", has_mcp))

    if has_mcp:
        mcp = servers[MCP_NAME]

        # 4. Command is npx
        results.append(check(
            "Command is 'npx'",
            mcp.get("command") == "npx",
            mcp.get("command", "(missing)"),
        ))

        # 5. Package is correct
        args = mcp.get("args", [])
        has_pkg = "@ycse/nanobanana-mcp" in args
        results.append(check(
            "Package is @ycse/nanobanana-mcp",
            has_pkg,
            str(args),
        ))

        # 6. API key present
        env = mcp.get("env", {})
        key = env.get("GOOGLE_AI_API_KEY", "")
        results.append(check(
            "GOOGLE_AI_API_KEY is set",
            bool(key),
            f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "(empty or short)",
        ))

        # 7. Model configured
        model = env.get("NANOBANANA_MODEL", "")
        results.append(check(
            "NANOBANANA_MODEL is set",
            bool(model),
            model or "(not set, will use package default)",
        ))

    # 8. Node.js/npx available
    has_npx = shutil.which("npx") is not None
    results.append(check(
        "npx is available in PATH",
        has_npx,
        shutil.which("npx") or "not found",
    ))

    # 9. Output directory
    if OUTPUT_DIR.exists():
        results.append(check("Output directory exists", True, str(OUTPUT_DIR)))
    else:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            results.append(check("Output directory created", True, str(OUTPUT_DIR)))
        except OSError as e:
            results.append(check("Output directory writable", False, str(e)))

    # 10. Optional tool checks (v4.1.0+) — do NOT fail validation; inform user
    # which features are available given what's installed.
    print()
    print("Optional tools (not required for generation, unlock specific features):")
    optional_tools = [
        ("ImageMagick (magick/convert)",
         shutil.which("magick") or shutil.which("convert"),
         "exact-dimension crop for /create-image social, post-processing pipelines, green-screen transparency"),
        ("ffmpeg",
         shutil.which("ffmpeg"),
         "/create-video audio pipeline, stitch, lipsync audio mixing, video concat/trim/convert"),
        ("cwebp (libwebp)",
         shutil.which("cwebp"),
         "efficient WebP encoding for /create-image formats (fallback path when ImageMagick is missing)"),
    ]
    for label, path, unlocks in optional_tools:
        mark = "✓" if path else "✗"
        status = str(path) if path else "not installed"
        print(f"  [{mark}] {label:32s} {status}")
        print(f"       unlocks: {unlocks}")

    missing_tools = [label for label, path, _ in optional_tools if not path]
    if missing_tools:
        print()
        print("  To install missing tools on macOS:")
        if any("ImageMagick" in t for t in missing_tools):
            print("    brew install imagemagick")
        if any("ffmpeg" in t for t in missing_tools):
            print("    brew install ffmpeg")
        if any("cwebp" in t for t in missing_tools):
            print("    brew install webp")

    # 11. ElevenLabs + Replicate + Vertex config (optional) — informational only.
    config_path = _csd() / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                banana_config = json.load(f)
        except (json.JSONDecodeError, OSError):
            banana_config = {}
        print()
        print("API credentials (features activated when keys are configured):")
        if banana_config.get("elevenlabs_api_key"):
            print(f"  [✓] ElevenLabs API key                → /create-video audio pipeline, voice design, TTS narration")
        else:
            print(f"  [✗] ElevenLabs API key                → not configured (audio pipeline + voice features unavailable)")
        if banana_config.get("replicate_api_token"):
            print(f"  [✓] Replicate API token               → Kling video, Fabric lipsync, Recraft vectorize, nano-banana-2 fallback")
        else:
            print(f"  [✗] Replicate API token               → not configured (video + lipsync + vectorize unavailable)")
        if banana_config.get("vertex_api_key"):
            print(f"  [✓] Vertex AI key                     → VEO backup, Lyria 2 music")
        else:
            print(f"  [✗] Vertex AI key                     → not configured (VEO + Lyria unavailable)")
        custom_voices = banana_config.get("custom_voices", {}) or {}
        if custom_voices:
            roles = ", ".join(sorted(custom_voices.keys()))
            print(f"  [i] Custom voices ({len(custom_voices)}): {roles}")

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"Results: {passed}/{total} required checks passed")

    if passed == total:
        print("Status: Ready to generate images!")
        return 0
    else:
        print("Status: Some checks failed. Fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
