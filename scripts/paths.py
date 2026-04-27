#!/usr/bin/env python3
"""Creators Studio — User config directory paths (v4.2.2+).

Single source of truth for the canonical user state directory.

v4.2.2: the plugin's user state moved from ``~/.banana/`` (legacy, named
after the original ``banana-claude`` fork) to ``~/.creators-studio/`` to
match the v4.0.0 plugin rebrand. This module owns:

- :func:`creators_studio_dir` — returns the canonical directory path,
  triggering a copy-based migration from ``~/.banana/`` on first call
  if the new directory doesn't exist yet.
- Convenience accessors (:func:`config_path`, :func:`costs_path`,
  :func:`presets_dir`, etc.) for the common files / subdirs.

Migration safety properties:

- **Copy, not move.** ``~/.banana/`` is never deleted. If the migration
  is partial or fails, the original is intact for manual recovery.
- **Idempotent.** Calling :func:`creators_studio_dir` repeatedly is safe
  — once ``~/.creators-studio/`` exists, the migration short-circuits.
- **Symlink-preserving.** ``shutil.copytree(symlinks=True)`` keeps any
  symlinks in the user's old config dir intact.
- **Fallback on copy failure.** If the copy raises (permissions, disk
  full, etc.), the helper logs the error and returns the old path so
  the user still has access to their state.

Old plugin versions (v4.2.1 and earlier) hardcode ``~/.banana/``. Those
versions continue to read the old (preserved) directory after migration.
This is intentional — users running both versions side-by-side won't see
divergent state until they upgrade everywhere.

Usage from a script:

.. code-block:: python

    from pathlib import Path
    import sys
    _plugin_root = str(Path(__file__).resolve().parent.parent.parent.parent)
    if _plugin_root not in sys.path:
        sys.path.insert(0, _plugin_root)
    from scripts.paths import creators_studio_dir, config_path  # noqa: E402

    CONFIG_PATH = config_path()  # triggers migration on import

The shim path-segments-up varies by skill nesting depth; the existing
``scripts.backends._replicate`` import pattern in ``video_generate.py``
shows the canonical form.

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

# Module-level logger so callers can attach handlers / tests can use
# ``self.assertLogs(_replicate._logger, level="INFO")`` patterns.
_logger = logging.getLogger(__name__)

# Directory names. ``.creators-studio`` is the v4.2.2+ canonical name;
# ``.banana`` is the legacy name preserved for read-only fallback.
NEW_DIR_NAME = ".creators-studio"
OLD_DIR_NAME = ".banana"


def creators_studio_dir() -> Path:
    """Return the canonical user state directory.

    Resolution order (in priority):

    1. ``~/.creators-studio/`` exists → return it (migration already done
       OR fresh v4.2.2+ install).
    2. ``~/.banana/`` exists, ``~/.creators-studio/`` does NOT → copy old
       to new (preserving symlinks), then return ``~/.creators-studio/``.
       Old dir is preserved.
    3. Neither exists → create ``~/.creators-studio/`` and return it
       (first-ever install at v4.2.2+).

    If step 2's copy fails (permissions, disk full, etc.), logs the error
    and returns ``~/.banana/`` as a fallback so the caller can still read
    the user's state.

    Returns
    -------
    Path
        Absolute path to the canonical config directory. Always exists
        after this function returns (unless step 2 fell back to old, in
        which case ``~/.banana/`` exists).
    """
    new = Path.home() / NEW_DIR_NAME
    old = Path.home() / OLD_DIR_NAME

    if new.exists():
        return new

    if old.exists():
        try:
            shutil.copytree(old, new, symlinks=True)
            _logger.info(
                "Migrated %s -> %s (old directory preserved; safe to "
                "remove manually after verifying the new path works)",
                old, new,
            )
        except Exception as exc:  # broad catch is intentional — see below
            # Any exception during copy: log + fall back to old. We don't
            # want to break the user's tooling because of a permissions
            # quirk or a disk-space issue. They can always re-run later.
            _logger.error(
                "Migration of %s -> %s failed: %s. Falling back to old "
                "directory; the plugin will continue to read from there. "
                "Re-run any plugin command after resolving the issue to "
                "retry the migration.",
                old, new, exc,
            )
            return old
        return new

    # Neither exists — first-ever install. Create the new dir.
    new.mkdir(parents=True, exist_ok=True)
    return new


# ─── Convenience accessors for common paths ─────────────────────────
#
# These are thin wrappers around creators_studio_dir() / "<name>" for
# the files and subdirectories the plugin uses repeatedly. Each call
# triggers the migration check (idempotent), so call sites don't need
# to remember to call creators_studio_dir() first.


def config_path() -> Path:
    """Return ~/.creators-studio/config.json (the API keys file)."""
    return creators_studio_dir() / "config.json"


def costs_path() -> Path:
    """Return ~/.creators-studio/costs.json (the cost ledger)."""
    return creators_studio_dir() / "costs.json"


def presets_dir() -> Path:
    """Return ~/.creators-studio/presets/ (brand guides directory)."""
    return creators_studio_dir() / "presets"


def history_dir() -> Path:
    """Return ~/.creators-studio/history/ (session history)."""
    return creators_studio_dir() / "history"


def assets_dir() -> Path:
    """Return ~/.creators-studio/assets/ (registered images)."""
    return creators_studio_dir() / "assets"


def ab_preferences_path() -> Path:
    """Return ~/.creators-studio/ab_preferences.json (A/B test prefs)."""
    return creators_studio_dir() / "ab_preferences.json"


def ab_history_dir() -> Path:
    """Return ~/.creators-studio/ab_history/ (A/B test history)."""
    return creators_studio_dir() / "ab_history"


def analytics_path() -> Path:
    """Return ~/.creators-studio/analytics.html (default analytics output)."""
    return creators_studio_dir() / "analytics.html"


# ─── Migration status (for /create-image setup --check-migration) ───


def migration_status() -> dict:
    """Inspect the current migration state. Used by validate_setup.py.

    Returns a dict with these keys:
      - ``new_exists``: bool — does ~/.creators-studio/ exist?
      - ``old_exists``: bool — does ~/.banana/ exist?
      - ``state``: one of:
          * ``"migrated"`` — both exist (new is canonical, old is legacy)
          * ``"new_only"`` — only new exists (fresh v4.2.2+ install)
          * ``"old_only"`` — only old exists (next call migrates)
          * ``"none"`` — neither exists (first run never happened)
      - ``new_path``, ``old_path``: the two paths (always returned).
      - ``recommendation``: human-readable next-step suggestion.
    """
    new = Path.home() / NEW_DIR_NAME
    old = Path.home() / OLD_DIR_NAME

    new_exists = new.exists()
    old_exists = old.exists()

    if new_exists and old_exists:
        state = "migrated"
        recommendation = (
            f"Migration is complete. {new} is canonical. "
            f"You can manually remove {old} after verifying "
            f"the new path works for you (e.g., generate an image "
            f"and confirm it's logged correctly)."
        )
    elif new_exists:
        state = "new_only"
        recommendation = f"{new} is the canonical directory. No migration needed."
    elif old_exists:
        state = "old_only"
        recommendation = (
            f"You have a v4.2.1-or-earlier install. The next plugin "
            f"command will trigger a copy-based migration from {old} "
            f"to {new}. The old directory will be preserved."
        )
    else:
        state = "none"
        recommendation = (
            f"Neither {new} nor {old} exists. Run /create-image setup "
            f"to configure your API keys and create the directory."
        )

    return {
        "new_exists": new_exists,
        "old_exists": old_exists,
        "state": state,
        "new_path": str(new),
        "old_path": str(old),
        "recommendation": recommendation,
    }
