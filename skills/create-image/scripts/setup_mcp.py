#!/usr/bin/env python3
"""
Setup script for Creators Studio MCP server in Claude Code.

Configures @ycse/nanobanana-mcp in Claude Code's settings.json
with the user's Google AI API key. Also manages Replicate backend config.

Usage:
    python3 setup_mcp.py                          # Interactive (prompts for key)
    python3 setup_mcp.py --key YOUR_KEY           # Non-interactive
    python3 setup_mcp.py --check                  # Verify existing MCP setup
    python3 setup_mcp.py --remove                 # Remove MCP configuration
    python3 setup_mcp.py --replicate-key TOKEN    # Set Replicate API token
    python3 setup_mcp.py --check-replicate        # Verify Replicate setup
    python3 setup_mcp.py --help                   # Show usage
"""

import json
import sys
import os
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
BANANA_CONFIG = Path.home() / ".banana" / "config.json"
MCP_NAME = "nanobanana-mcp"
MCP_PACKAGE = "@ycse/nanobanana-mcp"
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"


def load_settings() -> dict:
    """Load Claude Code settings.json."""
    if not SETTINGS_PATH.exists():
        return {}
    with open(SETTINGS_PATH, "r") as f:
        return json.load(f)


def save_settings(settings: dict) -> None:
    """Save Claude Code settings.json."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"Settings saved to {SETTINGS_PATH}")


def check_setup() -> bool:
    """Check if MCP is already configured."""
    settings = load_settings()
    servers = settings.get("mcpServers", {})
    if MCP_NAME in servers:
        env = servers[MCP_NAME].get("env", {})
        key = env.get("GOOGLE_AI_API_KEY", "")
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "(not set)"
        print(f"MCP server '{MCP_NAME}' is configured.")
        print(f"  Package: {MCP_PACKAGE}")
        print(f"  API Key: {masked}")
        print(f"  Model:   {env.get('NANOBANANA_MODEL', DEFAULT_MODEL)}")
        return True
    print(f"MCP server '{MCP_NAME}' is NOT configured.")
    return False


def remove_mcp() -> None:
    """Remove MCP configuration."""
    settings = load_settings()
    servers = settings.get("mcpServers", {})
    if MCP_NAME in servers:
        del servers[MCP_NAME]
        settings["mcpServers"] = servers
        save_settings(settings)
        print(f"Removed '{MCP_NAME}' from Claude Code settings.")
    else:
        print(f"'{MCP_NAME}' not found in settings.")


# ─── v4.2.0 config migration ────────────────────────────────────────────
#
# Before v4.2.0, API keys lived as flat top-level keys in ~/.banana/config.json:
#     {"replicate_api_token": "r8_...", "google_api_key": "AIza...", ...}
#
# As of v4.2.0, they live under a provider-scoped schema so the plugin can
# support additional marketplaces (Kie.ai, HF Inference Providers, ...) by
# adding more `providers.<name>.api_key` entries without schema churn:
#     {"providers": {"replicate": {"api_key": "r8_..."}, ...}}
#
# The migration shim runs on every load_banana_config() call so existing
# user configs keep working without forcing a re-paste of API keys. When
# the user next writes to config (e.g., via /create-video setup), the new
# schema is persisted. See spec §8.

_V4_2_0_KEYMAP = {
    "replicate_api_token":   ("replicate",  "api_key"),
    "google_api_key":        ("gemini",     "api_key"),
    "elevenlabs_api_key":    ("elevenlabs", "api_key"),
    "vertex_api_key":        ("vertex",     "api_key"),
    "vertex_project_id":     ("vertex",     "project_id"),
    "vertex_location":       ("vertex",     "location"),
    "kie_api_key":           ("kie",        "api_key"),     # future-proof for sub-project C
}


def migrate_config_to_v4_2_0(config):
    """Rewrite old flat API-key config into the v4.2.0 providers schema.

    Non-auth keys (custom_voices, named_creator_triggers, ...) pass through
    unchanged. When both old flat keys and the new providers.<name>.api_key
    form are present, NEW wins (explicit migration already happened once;
    old key is stale).

    Tolerates None/falsy input for defensive reasons — the config file may
    be absent or malformed during first-run.
    """
    if not config:
        return {}

    out = {}
    # Seed with existing providers block if present.
    existing_providers = config.get("providers") or {}
    if isinstance(existing_providers, dict):
        out["providers"] = {
            k: dict(v) if isinstance(v, dict) else v
            for k, v in existing_providers.items()
        }
    else:
        out["providers"] = {}

    # Copy all non-migrated keys verbatim.
    for k, v in config.items():
        if k in _V4_2_0_KEYMAP or k == "providers":
            continue
        out[k] = v

    # Apply migrations: only fill the new path if it isn't already set.
    for old_key, (provider, field) in _V4_2_0_KEYMAP.items():
        old_val = config.get(old_key)
        if old_val is None:
            continue
        prov_block = out["providers"].setdefault(provider, {})
        if field not in prov_block:  # NEW wins when both present
            prov_block[field] = old_val

    return out


def load_banana_config():
    if not BANANA_CONFIG.exists():
        return {}
    with open(BANANA_CONFIG, "r") as f:
        raw = json.load(f)
    # Auto-migrate on every read so old configs keep working.
    return migrate_config_to_v4_2_0(raw)


def save_banana_config(config):
    BANANA_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(BANANA_CONFIG, "w") as f:
        json.dump(config, f, indent=2)


def setup_replicate(api_token):
    if not api_token or not api_token.strip():
        print("Error: Replicate API token cannot be empty.")
        sys.exit(1)
    config = load_banana_config()
    config["replicate_api_token"] = api_token.strip()
    save_banana_config(config)
    print(f"Replicate API token saved to {BANANA_CONFIG}")
    print(f"Get a token at: https://replicate.com/account/api-tokens")


def check_replicate():
    config = load_banana_config()
    token = config.get("replicate_api_token", "")
    if token:
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "(set)"
        print(f"Replicate API token: {masked}")
        return True
    env_token = os.environ.get("REPLICATE_API_TOKEN", "")
    if env_token:
        masked = env_token[:8] + "..." + env_token[-4:] if len(env_token) > 12 else "(set)"
        print(f"Replicate API token (from env): {masked}")
        return True
    print("Replicate API token: NOT configured")
    print("  Set with: python3 setup_mcp.py --replicate-key YOUR_TOKEN")
    print("  Or set REPLICATE_API_TOKEN env var")
    return False


def setup_mcp(api_key: str) -> None:
    """Configure MCP server in Claude Code settings."""
    if not api_key or not api_key.strip():
        print("Error: API key cannot be empty.")
        sys.exit(1)

    api_key = api_key.strip()
    settings = load_settings()

    if "mcpServers" not in settings:
        settings["mcpServers"] = {}

    settings["mcpServers"][MCP_NAME] = {
        "command": "npx",
        "args": ["-y", MCP_PACKAGE],
        "env": {
            "GOOGLE_AI_API_KEY": api_key,
            "NANOBANANA_MODEL": DEFAULT_MODEL,
        },
    }

    save_settings(settings)

    # Also save to ~/.banana/config.json so fallback scripts can access it
    config = load_banana_config()
    config["google_ai_api_key"] = api_key
    save_banana_config(config)

    print(f"\nMCP server '{MCP_NAME}' configured successfully!")
    print(f"  Package: {MCP_PACKAGE}")
    print(f"  Model:   {DEFAULT_MODEL}")
    print(f"  API key saved to: {BANANA_CONFIG} (for fallback scripts)")
    print(f"\nRestart Claude Code for changes to take effect.")
    print(f"Generated images will be saved to: ~/Documents/creators_generated/")


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print("Usage: python3 setup_mcp.py [OPTIONS]")
        print()
        print("MCP Options:")
        print("  --key KEY              Provide Google AI API key non-interactively")
        print("  --check                Verify existing MCP setup")
        print("  --remove               Remove MCP configuration")
        print()
        print("Replicate Options:")
        print("  --replicate-key TOKEN  Set Replicate API token (stored in ~/.banana/config.json)")
        print("  --check-replicate      Verify Replicate setup")
        print()
        print("General:")
        print("  --help, -h             Show this help message")
        print()
        print("Get a free Google AI API key at: https://aistudio.google.com/apikey")
        print("Get a Replicate token at: https://replicate.com/account/api-tokens")
        sys.exit(0)

    if "--check-replicate" in args:
        check_replicate()
        return

    if "--check" in args:
        check_setup()
        return

    if "--remove" in args:
        remove_mcp()
        return

    # Handle --replicate-key
    for i, arg in enumerate(args):
        if arg == "--replicate-key" and i + 1 < len(args):
            setup_replicate(args[i + 1])
            return

    # Get API key
    api_key = None
    for i, arg in enumerate(args):
        if arg == "--key" and i + 1 < len(args):
            api_key = args[i + 1]
            break

    if not api_key:
        # Check environment
        api_key = os.environ.get("GOOGLE_AI_API_KEY")

    if not api_key:
        print("Creators Studio -- MCP Setup")
        print("=" * 40)
        print(f"\nGet your free API key at: https://aistudio.google.com/apikey")
        print()
        try:
            api_key = input("Enter your Google AI API key: ")
        except (EOFError, KeyboardInterrupt):
            print("\nError: No input received. Provide a key with --key or set GOOGLE_AI_API_KEY env var.")
            sys.exit(1)

    setup_mcp(api_key)


if __name__ == "__main__":
    main()
