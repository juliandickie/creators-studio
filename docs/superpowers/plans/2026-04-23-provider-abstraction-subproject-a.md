# Provider-Agnostic Architecture — Sub-Project A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement sub-project A from the provider-agnostic architecture spec — the foundation layer that turns "add a new marketplace" into a one-file task.

**Architecture:** Introduce a `ProviderBackend` ABC + canonical task schema + model registry. Refactor the existing `_replicate_backend.py` (already ~75% correctly shaped) to implement the new interface. No new concrete backends ship in A; that's sub-projects C (Kie.ai) and D (HF Inference Providers). Zero behavior change for end users.

**Spec:** [docs/superpowers/specs/2026-04-23-provider-abstraction-design.md](../specs/2026-04-23-provider-abstraction-design.md)

**Tech Stack:** Python 3.6+ stdlib only (matches plugin's zero-pip-dependencies runtime rule). Tests use stdlib `unittest`. No new runtime or test-time dependencies.

**Branch:** Work happens on `feature/provider-abstraction-v4.2.0`. Main stays at v4.1.3 until the whole sub-project A is complete + tested + released as v4.2.0.

---

## Context for engineer picking this up cold

The plugin is `creators-studio`, a Claude Code plugin for AI image + video + audio generation. It currently wires three provider surfaces directly:

- **Gemini direct API** for Nano Banana 2 images (via `skills/create-image/scripts/generate.py` + `edit.py`)
- **Vertex AI** for VEO video + Lyria music (via `skills/create-video/scripts/_vertex_backend.py`)
- **Replicate** for Kling video, Fabric lip-sync, DreamActor, Recraft Vectorize, and Nano Banana 2 fallback (via `skills/create-video/scripts/_replicate_backend.py` + `skills/create-image/scripts/replicate_generate.py`)

Users have asked to bring their own marketplace — some pay Kie.ai, some pay Hugging Face Inference Providers, some want fal.ai. Adding each one today means a refactor of every script that calls a provider. This plan builds the abstraction so adding the Nth marketplace is a ~new-file task.

**Key plugin rules (from `CLAUDE.md`):**

1. **Stdlib-only for runtime scripts.** `urllib.request`, `json`, `base64` only. Never add `google-genai`, `requests`, or `replicate`.
2. **`~/.banana/` config directory is frozen.** v4.0.0 rebrand rule — don't rename user state even though product is now `creators-studio`.
3. **SKILL.md files stay lean** — orchestration lives there, detail lives in references. Under 500 lines.
4. **Fallback chain is: MCP primary → direct Gemini API → Replicate.** This ordering survives the refactor.
5. **`kwaivgi/kling-v3-video` is the current default video model** (per v3.8.0 bakeoff). Do not change default behavior.
6. **Vertex AI's VEO is NOT getting retired in this plan.** That's sub-project B. Vertex stays a backend in A; its model registry entries will be added later when B ships.

**Current file map (what exists before this plan starts):**

```
creators-studio/
├── skills/
│   ├── create-image/
│   │   ├── SKILL.md
│   │   ├── references/ (gemini-models.md, prompt-engineering.md, replicate.md, etc.)
│   │   └── scripts/ (generate.py, edit.py, replicate_generate.py, replicate_edit.py, vectorize.py, social.py, ...)
│   └── create-video/
│       ├── SKILL.md
│       ├── references/ (kling-models.md, veo-models.md, lipsync.md, audio-pipeline.md, ...)
│       └── scripts/ (_replicate_backend.py, _vertex_backend.py, video_generate.py, video_lipsync.py, video_sequence.py, audio_pipeline.py, ...)
├── agents/brief-constructor.md
└── .claude-plugin/plugin.json (v4.1.3)
```

**Key file to read first for context:** `skills/create-video/scripts/_replicate_backend.py`. It's ~700 lines, pure data-translation layer, stdlib-only. The refactor in Phase 5 transforms this file; everything in Phases 1-4 leads up to it.

---

## File structure (every file created or modified)

### New files (plugin root — new directory `scripts/` at plugin root level, not per-skill)

- `scripts/__init__.py` — empty, makes it a package
- `scripts/backends/__init__.py` — empty
- `scripts/backends/_base.py` — `ProviderBackend` ABC + canonical types + exceptions
- `scripts/backends/_canonical.py` — canonical image normalizer + constraint validator
- `scripts/backends/_replicate.py` — moved and refactored from `skills/create-video/scripts/_replicate_backend.py`
- `scripts/registry/__init__.py` — empty
- `scripts/registry/models.json` — model registry data (JSON, not Python, for easy edits)
- `scripts/registry/registry.py` — load, validate, query
- `scripts/routing.py` — model + provider resolution
- `references/providers/replicate.md` — Replicate auth, polling, Cloudflare quirks, pricing
- `references/providers/gemini-direct.md` — Gemini direct API reference (no code refactor in A — doc placeholder)
- `references/models/kling-v3.md` — split from current `kling-models.md`
- `references/models/kling-v3-omni.md` — new (was not a first-class entry before)
- `references/models/veo-3.1.md` — placeholder, content comes in sub-project B
- `references/models/nano-banana-2.md` — split from current `gemini-models.md`
- `references/models/fabric-1.0.md` — migrated from `skills/create-video/references/lipsync.md`
- `references/models/dreamactor-m2.0.md` — new
- `references/models/recraft-vectorize.md` — migrated from `skills/create-image/references/vectorize.md`
- `tests/__init__.py` — empty
- `tests/test_base.py` — unittest for `_base.py` types
- `tests/test_canonical.py` — unittest for `_canonical.py` validator + normalizer
- `tests/test_registry.py` — unittest for registry load + query
- `tests/test_routing.py` — unittest for routing resolution
- `tests/test_replicate_backend.py` — unittest for the refactored `_replicate.py`
- `tests/fixtures/replicate_kling_submit.json` — frozen sample response
- `tests/fixtures/replicate_kling_poll_success.json` — frozen sample response
- `tests/fixtures/replicate_kling_poll_failed.json` — frozen sample response
- `tests/fixtures/replicate_fabric_submit.json` — frozen sample response

### Modified files

- `skills/create-image/scripts/vectorize.py` — update sys.path shim to import from new plugin-root location
- `skills/create-image/scripts/setup_mcp.py` — add new schema writer + migration shim for old flat keys
- `skills/create-video/scripts/video_generate.py` — call new backend interface instead of `_replicate_backend` directly
- `skills/create-video/scripts/video_lipsync.py` — call new backend interface
- `skills/create-video/scripts/video_sequence.py` — call new backend interface
- `CLAUDE.md` — update file responsibilities table, add new architecture constraints
- `PROGRESS.md` — add session entry for v4.2.0
- `ROADMAP.md` — mark sub-project A done, reference spec for B/C/D
- `CHANGELOG.md` — add v4.2.0 entry
- `README.md` — What's New in This Fork entry, architecture diagram update, commands table (no new commands but --provider flag is new)
- `.claude-plugin/plugin.json` — version bump to 4.2.0
- `CITATION.cff` — version + date-released

### Deleted files

- `skills/create-video/scripts/_replicate_backend.py` — moved to plugin-root `scripts/backends/_replicate.py`. The deletion + new file happen in the same commit so git recognizes it as a move.

---

## Pre-flight

### Task 0: Create feature branch

**Files:** (none — git metadata only)

- [ ] **Step 1: Create and switch to feature branch**

```bash
cd /Users/juliandickie/code/creators-studio-project/creators-studio
git checkout -b feature/provider-abstraction-v4.2.0
git status
```

Expected: `On branch feature/provider-abstraction-v4.2.0`, nothing to commit.

- [ ] **Step 2: Verify spec is reachable from new branch**

```bash
ls docs/superpowers/specs/2026-04-23-provider-abstraction-design.md
```

Expected: file exists (it was committed to main at `b983b61` before branching).

---

## Phase 1 — Foundation types (`_base.py`)

### Task 1: Create empty package directories + test infrastructure scaffolding

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/backends/__init__.py`
- Create: `scripts/registry/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`

- [ ] **Step 1: Create the package dirs with empty init files**

```bash
mkdir -p scripts/backends scripts/registry tests/fixtures
touch scripts/__init__.py scripts/backends/__init__.py scripts/registry/__init__.py tests/__init__.py tests/fixtures/.gitkeep
```

- [ ] **Step 2: Verify structure**

```bash
find scripts tests -type f | sort
```

Expected output:
```
scripts/__init__.py
scripts/backends/__init__.py
scripts/registry/__init__.py
tests/__init__.py
tests/fixtures/.gitkeep
```

- [ ] **Step 3: Verify Python imports the new packages**

```bash
python3 -c "import scripts; import scripts.backends; import scripts.registry; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add scripts/__init__.py scripts/backends/__init__.py scripts/registry/__init__.py tests/__init__.py tests/fixtures/.gitkeep
git commit -m "chore: scaffold scripts/ and tests/ package dirs for provider abstraction"
```

### Task 2: Write failing test for canonical dataclass types

**Files:**
- Test: `tests/test_base.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_base.py`:

```python
"""Tests for scripts/backends/_base.py canonical types."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

# Add plugin root to path so we can import scripts.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backends import _base


class TestCanonicalTypes(unittest.TestCase):
    def test_job_ref_has_required_fields(self):
        ref = _base.JobRef(
            provider="replicate",
            external_id="abc123",
            poll_url="https://api.replicate.com/v1/predictions/abc123",
            raw={"id": "abc123"},
        )
        self.assertEqual(ref.provider, "replicate")
        self.assertEqual(ref.external_id, "abc123")

    def test_job_status_states_are_canonical(self):
        # Canonical 5 states: pending | running | succeeded | failed | canceled
        for state in ("pending", "running", "succeeded", "failed", "canceled"):
            status = _base.JobStatus(state=state, output=None, error=None, raw={})
            self.assertEqual(status.state, state)

    def test_task_result_cost_is_optional(self):
        result = _base.TaskResult(
            output_paths=[Path("/tmp/out.mp4")],
            output_urls=["https://example.com/out.mp4"],
            metadata={"duration_s": 8},
            provider_metadata={"prediction_id": "abc123"},
            cost=Decimal("0.16"),
            task_id="abc123",
        )
        self.assertEqual(result.cost, Decimal("0.16"))

        result_no_cost = _base.TaskResult(
            output_paths=[], output_urls=[], metadata={},
            provider_metadata={}, cost=None, task_id="xyz",
        )
        self.assertIsNone(result_no_cost.cost)

    def test_auth_status_bool(self):
        ok = _base.AuthStatus(ok=True, message="authenticated", provider="replicate")
        self.assertTrue(ok.ok)
        bad = _base.AuthStatus(ok=False, message="401 Unauthorized", provider="kie")
        self.assertFalse(bad.ok)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest tests.test_base -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.backends._base'` OR `ImportError: cannot import name '_base'`. All 4 tests fail in collection.

### Task 3: Implement canonical dataclasses in `_base.py`

**Files:**
- Create: `scripts/backends/_base.py`

- [ ] **Step 1: Write the minimal implementation**

Write `scripts/backends/_base.py`:

```python
"""Creators Studio — Provider backend abstraction.

This module defines the canonical types and abstract base class that every
provider backend must implement. It is the contract layer between the skill
orchestrators and concrete providers (Replicate, Kie.ai, HF Inference
Providers, Gemini direct, ElevenLabs, ...).

See docs/superpowers/specs/2026-04-23-provider-abstraction-design.md.

Runtime dependencies: stdlib only (abc, dataclasses, decimal, pathlib,
typing). Never import google-genai, requests, replicate, or any pip package.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Union


# ─── Canonical dataclasses ──────────────────────────────────────────────


@dataclass
class JobRef:
    """Opaque handle to an in-flight async generation job.

    Backends return this from submit(). Callers treat it as opaque and pass
    it to poll() and parse_result() without introspecting fields.
    """
    provider: str
    external_id: str
    poll_url: str
    raw: dict


@dataclass
class JobStatus:
    """Canonical job state, unified across provider-specific enums.

    Canonical states (5 values):
      pending   — submitted but not yet started (e.g., queued)
      running   — actively generating
      succeeded — finished, output is available
      failed    — finished with an error (including timeouts, content filter)
      canceled  — explicitly canceled by the caller or the platform

    Provider-specific states map to one of these. Example: Replicate's
    6-value enum (starting | processing | succeeded | failed | canceled |
    aborted) maps 'aborted' to 'failed' since both signal terminal failure
    with no output.
    """
    state: str
    output: Optional[dict]
    error: Optional[str]
    raw: dict


@dataclass
class TaskResult:
    """Canonical result returned to orchestrator / caller code.

    output_paths are the downloaded local file paths.
    output_urls are the provider-hosted URLs (may expire).
    metadata holds canonical keys (duration_s, resolution, aspect, seed_used).
    provider_metadata holds the raw provider response for debugging/audit.
    cost may be None if the backend can't compute it cheaply.
    """
    output_paths: list[Path]
    output_urls: list[str]
    metadata: dict
    provider_metadata: dict
    cost: Optional[Decimal]
    task_id: str


@dataclass
class AuthStatus:
    """Result of a provider's auth_check ping."""
    ok: bool
    message: str
    provider: str


# Canonical image param: any of four forms. Backends normalize internally.
CanonicalImage = Union[Path, str, bytes]


# ─── Exception hierarchy ─────────────────────────────────────────────────


class ProviderError(Exception):
    """Base class for all provider backend errors."""


class ProviderValidationError(ProviderError):
    """Canonical params failed validation before any HTTP call. No budget burned."""


class ProviderHTTPError(ProviderError):
    """HTTP-level failure (5xx, timeout, malformed response). Retryable in some cases."""


class ProviderAuthError(ProviderError):
    """401/403 — the configured API key is missing, invalid, or lacks permission."""


# ─── Provider backend ABC ────────────────────────────────────────────────


class ProviderBackend(ABC):
    """Contract every provider backend must satisfy.

    Backends are pure data-translation layers with HTTP plumbing. They have
    no global state, no sleeps, no blocking polls. Callers manage the poll
    loop and the download destination.
    """

    name: str = ""                       # "replicate"
    supported_tasks: set[str] = field(default_factory=set)  # type: ignore[assignment]

    @abstractmethod
    def auth_check(self, config: dict) -> AuthStatus:
        """Ping the provider's cheapest read endpoint (e.g., /account) to
        verify the API key works. Must not burn billable generation budget.
        """

    @abstractmethod
    def submit(
        self,
        *,
        task: str,
        model_slug: str,
        canonical_params: dict,
        provider_opts: dict,
        config: dict,
    ) -> JobRef:
        """Translate canonical_params to provider-specific shape, merge
        provider_opts (caller's escape-hatch overrides), POST to the
        provider's submit endpoint, return a JobRef.

        Raises:
            ProviderValidationError — canonical_params fail validation
                BEFORE any HTTP call. No budget burned.
            ProviderAuthError — 401/403 from provider.
            ProviderHTTPError — other HTTP-level failures.
        """

    @abstractmethod
    def poll(self, job_ref: JobRef, config: dict) -> JobStatus:
        """GET the provider's status endpoint. Returns canonical JobStatus.

        Does not block, sleep, or loop. Caller is responsible for polling
        cadence.
        """

    @abstractmethod
    def parse_result(self, job_status: JobStatus, *, download_to: Path) -> TaskResult:
        """When job_status.state == 'succeeded', download output files to
        download_to, compute or look up cost, return canonical TaskResult.

        Raises:
            ProviderError — if called with a non-succeeded job_status.
            ProviderHTTPError — if download fails.
        """
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
python3 -m unittest tests.test_base -v
```

Expected: all 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/backends/_base.py tests/test_base.py
git commit -m "feat: add ProviderBackend ABC and canonical types"
```

---

## Phase 2 — Model registry

### Task 4: Seed `models.json` with currently-used models

**Files:**
- Create: `scripts/registry/models.json`

- [ ] **Step 1: Write the registry seed**

Write `scripts/registry/models.json`:

```json
{
  "version": 1,
  "family_defaults": {
    "image": "nano-banana-2",
    "video": "kling-v3",
    "music": "elevenlabs-music",
    "speech": "elevenlabs-tts"
  },
  "models": {
    "kling-v3": {
      "display_name": "Kling Video 3.0",
      "family": "video",
      "tasks": ["text-to-video", "image-to-video"],
      "doc": "references/models/kling-v3.md",
      "canonical_constraints": {
        "aspect_ratio": ["16:9", "9:16", "1:1"],
        "duration_s": {"min": 3, "max": 15, "integer": true},
        "resolutions": ["720p", "1080p"],
        "prompt_max_chars": 2500
      },
      "providers": {
        "replicate": {
          "slug": "kwaivgi/kling-v3-video",
          "capabilities": ["audio_generation", "multi_prompt", "start_image", "end_image", "negative_prompt"],
          "pricing": {"mode": "per_second", "rate": 0.02, "currency": "USD"},
          "availability": "GA",
          "notes": "aspect_ratio ignored when start_image provided; sum of multi_prompt durations must equal top-level duration"
        }
      }
    },
    "kling-v3-omni": {
      "display_name": "Kling Video 3.0 Omni",
      "family": "video",
      "tasks": ["text-to-video", "image-to-video", "video-edit"],
      "doc": "references/models/kling-v3-omni.md",
      "canonical_constraints": {
        "aspect_ratio": ["16:9", "9:16", "1:1"],
        "duration_s": {"min": 3, "max": 15, "integer": true},
        "resolutions": ["720p", "1080p"],
        "prompt_max_chars": 2500
      },
      "providers": {
        "replicate": {
          "slug": "kwaivgi/kling-v3-omni-video",
          "capabilities": ["audio_generation", "multi_prompt", "start_image", "end_image", "negative_prompt", "reference_images", "video_editing"],
          "pricing": {"mode": "per_second", "rate": 0.02, "currency": "USD"},
          "availability": "GA",
          "notes": "Supports reference_images array for multimodal conditioning"
        }
      }
    },
    "fabric-1.0": {
      "display_name": "VEED Fabric 1.0",
      "family": "video",
      "tasks": ["lipsync"],
      "doc": "references/models/fabric-1.0.md",
      "canonical_constraints": {
        "resolutions": ["480p", "720p"],
        "duration_s": {"min": 1, "max": 60}
      },
      "providers": {
        "replicate": {
          "slug": "veed/fabric-1.0",
          "capabilities": ["audio_driven_lipsync"],
          "pricing": {"mode": "per_second", "rate": 0.15, "currency": "USD"},
          "availability": "GA",
          "notes": "Cost is per second of output duration (driven by audio length). No prompt parameter. Mouth region only."
        }
      }
    },
    "dreamactor-m2.0": {
      "display_name": "ByteDance DreamActor M2.0",
      "family": "video",
      "tasks": ["image-to-video"],
      "doc": "references/models/dreamactor-m2.0.md",
      "canonical_constraints": {
        "duration_s": {"min": 1, "max": 30}
      },
      "providers": {
        "replicate": {
          "slug": "bytedance/dreamactor-m2.0",
          "capabilities": ["motion_transfer", "character_animation"],
          "pricing": {"mode": "per_second", "rate": 0.05, "currency": "USD"},
          "availability": "GA",
          "notes": "Requires driving video input. Preserves character identity from start_image at lower res than Kling."
        }
      }
    },
    "recraft-vectorize": {
      "display_name": "Recraft Vectorize",
      "family": "image",
      "tasks": ["vectorize"],
      "doc": "references/models/recraft-vectorize.md",
      "canonical_constraints": {
        "max_input_bytes": 5242880,
        "max_input_pixels": 16777216,
        "input_dim_range": {"min_px": 256, "max_px": 4096}
      },
      "providers": {
        "replicate": {
          "slug": "recraft-ai/recraft-vectorize",
          "capabilities": ["raster_to_svg"],
          "pricing": {"mode": "per_call", "rate": 0.01, "currency": "USD"},
          "availability": "GA",
          "notes": "Flat fee regardless of input dimensions within constraints"
        }
      }
    },
    "nano-banana-2": {
      "display_name": "Google Nano Banana 2 (Gemini 3.1 Flash Image)",
      "family": "image",
      "tasks": ["text-to-image", "image-to-image"],
      "doc": "references/models/nano-banana-2.md",
      "canonical_constraints": {
        "aspect_ratio": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "1:4", "4:1", "1:8", "8:1"],
        "resolutions": ["512", "1K", "2K", "4K"]
      },
      "providers": {
        "gemini-direct": {
          "slug": "gemini-3.1-flash-image-preview",
          "capabilities": ["text_to_image", "image_editing", "reference_images", "multilingual"],
          "pricing": {"mode": "by_resolution", "rates": {"512": 0.0005, "1K": 0.002, "2K": 0.008, "4K": 0.032}, "currency": "USD"},
          "availability": "GA",
          "notes": "Primary backend; uses API key from providers.gemini.api_key"
        },
        "replicate": {
          "slug": "google/nano-banana-2",
          "capabilities": ["text_to_image", "image_editing"],
          "pricing": {"mode": "by_resolution", "rates": {"1K": 0.003}, "currency": "USD"},
          "availability": "GA",
          "notes": "Fallback path when Gemini direct or MCP unavailable"
        }
      }
    }
  }
}
```

- [ ] **Step 2: Verify JSON is valid**

```bash
python3 -m json.tool scripts/registry/models.json > /dev/null && echo "valid"
```

Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add scripts/registry/models.json
git commit -m "feat: seed model registry with currently-used models"
```

### Task 5: Write failing test for registry loader

**Files:**
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_registry.py`:

```python
"""Tests for scripts/registry/registry.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.registry import registry as reg


class TestRegistryLoad(unittest.TestCase):
    def test_load_default_registry(self):
        r = reg.load_registry()
        self.assertEqual(r.version, 1)
        self.assertIn("kling-v3", r.models)

    def test_family_defaults_present(self):
        r = reg.load_registry()
        self.assertEqual(r.family_defaults["video"], "kling-v3")
        self.assertEqual(r.family_defaults["image"], "nano-banana-2")

    def test_model_entry_has_providers(self):
        r = reg.load_registry()
        kling = r.models["kling-v3"]
        self.assertIn("replicate", kling.providers)
        self.assertEqual(kling.providers["replicate"]["slug"], "kwaivgi/kling-v3-video")


class TestRegistryQuery(unittest.TestCase):
    def setUp(self):
        self.r = reg.load_registry()

    def test_get_model_by_id(self):
        m = self.r.get_model("kling-v3")
        self.assertEqual(m.display_name, "Kling Video 3.0")

    def test_get_model_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.r.get_model("does-not-exist")

    def test_models_by_family(self):
        videos = self.r.models_by_family("video")
        self.assertIn("kling-v3", videos)
        self.assertIn("fabric-1.0", videos)
        self.assertNotIn("nano-banana-2", videos)

    def test_providers_for_model(self):
        provs = self.r.providers_for_model("kling-v3")
        self.assertEqual(provs, ["replicate"])
        provs = self.r.providers_for_model("nano-banana-2")
        self.assertIn("gemini-direct", provs)
        self.assertIn("replicate", provs)

    def test_provider_order_preserved(self):
        # gemini-direct must appear BEFORE replicate for nano-banana-2
        # because it's listed first in models.json (routing fallback order)
        provs = self.r.providers_for_model("nano-banana-2")
        self.assertLess(provs.index("gemini-direct"), provs.index("replicate"))


class TestRegistryValidate(unittest.TestCase):
    def test_validate_passes_for_default(self):
        r = reg.load_registry()
        # Should not raise
        r.validate()

    def test_validate_catches_missing_family_default(self):
        # Inject a family default that doesn't exist in models
        r = reg.load_registry()
        r.family_defaults["image"] = "does-not-exist"
        with self.assertRaises(reg.RegistryValidationError):
            r.validate()

    def test_validate_catches_model_with_no_providers(self):
        r = reg.load_registry()
        r.models["kling-v3"].providers.clear()
        with self.assertRaises(reg.RegistryValidationError):
            r.validate()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
python3 -m unittest tests.test_registry -v
```

Expected: `ImportError: cannot import name 'registry'` — registry.py doesn't exist yet.

### Task 6: Implement `registry.py`

**Files:**
- Create: `scripts/registry/registry.py`

- [ ] **Step 1: Write the implementation**

Write `scripts/registry/registry.py`:

```python
"""Creators Studio — Model registry loader and query API.

Loads the JSON registry at scripts/registry/models.json and exposes a typed
query API. The registry is the single source of truth for canonical model
IDs, which providers host each model, capabilities, pricing, and canonical
constraints.

Stdlib only.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class RegistryValidationError(Exception):
    """Registry failed structural validation."""


@dataclass
class ModelEntry:
    id: str
    display_name: str
    family: str
    tasks: list[str]
    doc: str
    canonical_constraints: dict
    providers: dict  # name -> {slug, capabilities, pricing, availability, notes}


@dataclass
class Registry:
    version: int
    family_defaults: dict
    models: dict  # id -> ModelEntry

    def get_model(self, model_id: str) -> ModelEntry:
        if model_id not in self.models:
            raise KeyError(f"unknown model id: {model_id!r}")
        return self.models[model_id]

    def models_by_family(self, family: str) -> list[str]:
        return [mid for mid, m in self.models.items() if m.family == family]

    def providers_for_model(self, model_id: str) -> list[str]:
        """Return provider names in registry insertion order (matters for routing fallback)."""
        return list(self.get_model(model_id).providers.keys())

    def family_default(self, family: str) -> Optional[str]:
        return self.family_defaults.get(family)

    def validate(self) -> None:
        """Structural validation. Raises RegistryValidationError on problems."""
        # Every family default must point at an existing model.
        for family, model_id in self.family_defaults.items():
            if model_id not in self.models:
                raise RegistryValidationError(
                    f"family_defaults[{family!r}] = {model_id!r} but no such model exists"
                )
            if self.models[model_id].family != family:
                raise RegistryValidationError(
                    f"family_defaults[{family!r}] = {model_id!r} but that model's family is "
                    f"{self.models[model_id].family!r}"
                )
        # Every model must have at least one provider.
        for mid, m in self.models.items():
            if not m.providers:
                raise RegistryValidationError(f"model {mid!r} has no providers")
            for pname, pinfo in m.providers.items():
                if "slug" not in pinfo:
                    raise RegistryValidationError(
                        f"model {mid!r} provider {pname!r} missing 'slug'"
                    )


_DEFAULT_PATH = Path(__file__).parent / "models.json"


def load_registry(path: Optional[Path] = None) -> Registry:
    """Load the registry JSON and return a typed Registry."""
    p = path or _DEFAULT_PATH
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)

    models: dict = {}
    for mid, m in raw.get("models", {}).items():
        models[mid] = ModelEntry(
            id=mid,
            display_name=m["display_name"],
            family=m["family"],
            tasks=list(m["tasks"]),
            doc=m.get("doc", ""),
            canonical_constraints=dict(m.get("canonical_constraints", {})),
            providers=dict(m.get("providers", {})),
        )

    return Registry(
        version=raw.get("version", 1),
        family_defaults=dict(raw.get("family_defaults", {})),
        models=models,
    )
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
python3 -m unittest tests.test_registry -v
```

Expected: all 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/registry/registry.py tests/test_registry.py
git commit -m "feat: add registry loader with validation and query API"
```

---

## Phase 3 — Canonical enforcement (`_canonical.py`)

### Task 7: Write failing test for `CanonicalImage` normalizer

**Files:**
- Test: `tests/test_canonical.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_canonical.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
python3 -m unittest tests.test_canonical -v
```

Expected: all tests fail on import of `_canonical`.

### Task 8: Implement `_canonical.py`

**Files:**
- Create: `scripts/backends/_canonical.py`

- [ ] **Step 1: Write the implementation**

Write `scripts/backends/_canonical.py`:

```python
"""Creators Studio — Canonical param validation and image normalization.

Sits between the orchestrator and backend: validates canonical_params
against a model's canonical_constraints BEFORE any HTTP call, and
normalizes CanonicalImage inputs to forms backends accept.

Stdlib only.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any, Union


class CanonicalValidationError(Exception):
    """A canonical parameter violates the model's canonical constraints."""


# ─── Image normalization ─────────────────────────────────────────────────

# Recognized magic bytes for stdlib-only format sniffing.
_MAGIC_BYTES_TO_MIME = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff",      "image/jpeg"),
    (b"GIF87a",            "image/gif"),
    (b"GIF89a",            "image/gif"),
    (b"RIFF",              "image/webp"),  # WebP starts with RIFF....WEBP
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


def normalize_image_to_data_uri(img: Union[Path, str, bytes]) -> str:
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

    raise TypeError(f"unsupported image type: {type(img)}")


def normalize_image_to_url(img: Union[Path, str, bytes]) -> str:
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
    constraints: dict, params: dict,
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
    c = constraints.get("duration_s")
    if c is not None and "duration_s" in params:
        v = params["duration_s"]
        if c.get("integer") and not isinstance(v, int):
            raise CanonicalValidationError(
                f"duration_s must be an integer; got {type(v).__name__} ({v!r})"
            )
        lo, hi = c.get("min"), c.get("max")
        if lo is not None and v < lo:
            raise CanonicalValidationError(
                f"duration_s={v} is below minimum {lo}"
            )
        if hi is not None and v > hi:
            raise CanonicalValidationError(
                f"duration_s={v} exceeds maximum {hi}"
            )

    # aspect_ratio
    c = constraints.get("aspect_ratio")
    if c is not None and "aspect_ratio" in params:
        if params["aspect_ratio"] not in c:
            raise CanonicalValidationError(
                f"aspect_ratio={params['aspect_ratio']!r} not in allowed {c}"
            )

    # resolution
    c = constraints.get("resolutions")
    if c is not None and "resolution" in params:
        if params["resolution"] not in c:
            raise CanonicalValidationError(
                f"resolution={params['resolution']!r} not in allowed {c}"
            )

    # prompt_max_chars
    c = constraints.get("prompt_max_chars")
    if c is not None and "prompt" in params:
        if len(params["prompt"]) > c:
            raise CanonicalValidationError(
                f"prompt length {len(params['prompt'])} exceeds maximum {c}"
            )

    # max_input_bytes (applies when source_image is bytes or Path)
    c = constraints.get("max_input_bytes")
    if c is not None and "source_image" in params:
        img = params["source_image"]
        size: int
        if isinstance(img, Path):
            size = img.stat().st_size
        elif isinstance(img, bytes):
            size = len(img)
        else:
            return  # URL/data-URI — skip byte-size check
        if size > c:
            raise CanonicalValidationError(
                f"source_image size {size} exceeds maximum {c}"
            )
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
python3 -m unittest tests.test_canonical -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/backends/_canonical.py tests/test_canonical.py
git commit -m "feat: add canonical image normalizer and constraint validator"
```

---

## Phase 4 — Routing (`routing.py`)

### Task 9: Write failing test for model + provider routing

**Files:**
- Test: `tests/test_routing.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_routing.py`:

```python
"""Tests for scripts/routing.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import routing
from scripts.registry import registry as reg


class TestModelResolution(unittest.TestCase):
    def setUp(self):
        self.r = reg.load_registry()

    def test_explicit_model_wins(self):
        resolved = routing.resolve_model(
            self.r, family="video", explicit_model="kling-v3-omni", config={}
        )
        self.assertEqual(resolved, "kling-v3-omni")

    def test_config_default_model(self):
        resolved = routing.resolve_model(
            self.r, family="video", explicit_model=None,
            config={"defaults": {"video_model": "kling-v3-omni"}},
        )
        self.assertEqual(resolved, "kling-v3-omni")

    def test_registry_family_default(self):
        resolved = routing.resolve_model(
            self.r, family="video", explicit_model=None, config={},
        )
        self.assertEqual(resolved, "kling-v3")  # from family_defaults in models.json

    def test_unknown_model_raises(self):
        with self.assertRaises(routing.RoutingError):
            routing.resolve_model(
                self.r, family="video", explicit_model="does-not-exist", config={},
            )


class TestProviderResolution(unittest.TestCase):
    def setUp(self):
        self.r = reg.load_registry()

    def test_explicit_provider_wins_when_hosts_model(self):
        prov = routing.resolve_provider(
            self.r, model_id="nano-banana-2", explicit_provider="replicate",
            config={"providers": {"replicate": {"api_key": "r8_x"}}},
        )
        self.assertEqual(prov, "replicate")

    def test_explicit_provider_not_hosting_model_raises(self):
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_provider(
                self.r, model_id="kling-v3", explicit_provider="gemini-direct",
                config={"providers": {"gemini-direct": {"api_key": "x"}}},
            )
        self.assertIn("not available on gemini-direct", str(ctx.exception))

    def test_family_default_wins_when_hosts_model(self):
        prov = routing.resolve_provider(
            self.r, model_id="kling-v3", explicit_provider=None,
            config={
                "defaults": {"video": "replicate"},
                "providers": {"replicate": {"api_key": "r8_x"}},
            },
        )
        self.assertEqual(prov, "replicate")

    def test_global_default_used_when_hosts_model(self):
        prov = routing.resolve_provider(
            self.r, model_id="kling-v3", explicit_provider=None,
            config={
                "default_provider": "replicate",
                "providers": {"replicate": {"api_key": "r8_x"}},
            },
        )
        self.assertEqual(prov, "replicate")

    def test_first_with_key_fallback(self):
        # No defaults set; registry order is gemini-direct, replicate for nano-banana-2
        # Only replicate has a key -> should pick replicate
        prov = routing.resolve_provider(
            self.r, model_id="nano-banana-2", explicit_provider=None,
            config={"providers": {"replicate": {"api_key": "r8_x"}}},
        )
        self.assertEqual(prov, "replicate")

    def test_first_with_key_respects_registry_order(self):
        # Both keys configured; registry lists gemini-direct first -> pick it
        prov = routing.resolve_provider(
            self.r, model_id="nano-banana-2", explicit_provider=None,
            config={
                "providers": {
                    "gemini-direct": {"api_key": "AIza"},
                    "replicate": {"api_key": "r8_x"},
                },
            },
        )
        self.assertEqual(prov, "gemini-direct")

    def test_no_key_configured_raises(self):
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_provider(
                self.r, model_id="kling-v3", explicit_provider=None, config={},
            )
        self.assertIn("no API key", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
python3 -m unittest tests.test_routing -v
```

Expected: fails on import of `routing`.

### Task 10: Implement `routing.py`

**Files:**
- Create: `scripts/routing.py`

- [ ] **Step 1: Write the implementation**

Write `scripts/routing.py`:

```python
"""Creators Studio — Model + provider routing resolution.

Given the registry, user flags, and user config, resolve which model and
which provider to use. Two independent resolutions: model first, then
provider-for-that-model.

Stdlib only.
"""

from typing import Optional

from scripts.registry.registry import Registry


class RoutingError(Exception):
    """Resolution could not produce a valid (model, provider) pair."""


def resolve_model(
    registry: Registry,
    *,
    family: str,
    explicit_model: Optional[str],
    config: dict,
) -> str:
    """Pick canonical model ID based on flag > config > registry default.

    Raises RoutingError if explicit_model names an unknown model, or if no
    default is configured and the registry has none for this family.
    """
    if explicit_model is not None:
        if explicit_model not in registry.models:
            raise RoutingError(
                f"unknown model: {explicit_model!r}. Known models: "
                f"{sorted(registry.models.keys())}"
            )
        return explicit_model

    cfg_default = config.get("defaults", {}).get(f"{family}_model")
    if cfg_default is not None:
        if cfg_default not in registry.models:
            raise RoutingError(
                f"config defaults.{family}_model = {cfg_default!r} but no such model"
            )
        return cfg_default

    reg_default = registry.family_default(family)
    if reg_default is not None:
        return reg_default

    raise RoutingError(
        f"no model could be resolved for family={family!r} "
        f"(no explicit, no config default, no registry default)"
    )


def resolve_provider(
    registry: Registry,
    *,
    model_id: str,
    explicit_provider: Optional[str],
    config: dict,
) -> str:
    """Pick provider to use for this model based on flag > family default >
    global default > first-with-configured-key.

    Raises RoutingError if the explicit provider doesn't host the model, or
    if no provider with a configured API key hosts the model.
    """
    model = registry.get_model(model_id)
    hosts = list(model.providers.keys())  # insertion order = routing fallback order
    configured_keys = {
        name for name, info in config.get("providers", {}).items()
        if info.get("api_key")
    }

    # 1. Explicit flag wins — but only if provider hosts the model.
    if explicit_provider is not None:
        if explicit_provider not in hosts:
            raise RoutingError(
                f"{model_id} is not available on {explicit_provider}. "
                f"Available on: {hosts}"
            )
        return explicit_provider

    # 2. Task-family default.
    family_default = config.get("defaults", {}).get(model.family)
    if family_default is not None and family_default in hosts:
        return family_default

    # 3. Global default.
    global_default = config.get("default_provider")
    if global_default is not None and global_default in hosts:
        return global_default

    # 4. First-with-key in registry insertion order.
    for provider_name in hosts:
        if provider_name in configured_keys:
            return provider_name

    raise RoutingError(
        f"{model_id} is available on {hosts}, but no API key is configured "
        f"for any of those providers. Run /create-{'video' if model.family == 'video' else 'image'} setup."
    )
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
python3 -m unittest tests.test_routing -v
```

Expected: all 11 tests PASS.

- [ ] **Step 3: Run all tests so far to verify no regressions**

```bash
python3 -m unittest discover tests -v
```

Expected: all tests PASS (Phases 1-4 combined: ~23 tests).

- [ ] **Step 4: Commit**

```bash
git add scripts/routing.py tests/test_routing.py
git commit -m "feat: add model + provider routing resolution"
```

---

## Phase 5 — Replicate backend refactor

### Task 11: Copy `_replicate_backend.py` to new location (verbatim)

**Files:**
- Create: `scripts/backends/_replicate.py` (content copied from existing file)
- (existing `skills/create-video/scripts/_replicate_backend.py` stays in place for now — will be deleted in Task 15)

- [ ] **Step 1: Copy the file**

```bash
cp skills/create-video/scripts/_replicate_backend.py scripts/backends/_replicate.py
```

- [ ] **Step 2: Update the module docstring to reflect new location**

Edit the docstring at the top of `scripts/backends/_replicate.py`. Replace lines 1-60 (the existing docstring) with:

```python
#!/usr/bin/env python3
"""Creators Studio — Replicate provider backend.

Implements the ProviderBackend interface for Replicate (api.replicate.com).
Hosts model registry entries for Kling v3, Kling v3 Omni, Fabric 1.0,
DreamActor M2.0, and Recraft Vectorize — every Replicate-hosted model the
plugin currently uses.

Pure data-translation layer. No global state. Stdlib only (urllib.request,
base64, json). Inherits from ProviderBackend ABC in scripts/backends/_base.py.

Auth: Replicate uses HTTP Bearer tokens. Stored at
providers.replicate.api_key in ~/.banana/config.json.

Canonical state mapping: Replicate's 6-value Prediction.status enum
(starting | processing | succeeded | failed | canceled | aborted) maps to
canonical JobStatus.state via:
    starting, processing       -> running
    succeeded                  -> succeeded
    failed, canceled, aborted  -> failed / canceled

User-Agent hardening: every request sends
    User-Agent: creators-studio/4.2.0 (+https://github.com/juliandickie/creators-studio)
to avoid Cloudflare WAF rejection on /v1/account.

Run `python3 -m scripts.backends._replicate diagnose` to verify auth works.
"""
```

- [ ] **Step 3: Verify the new file parses**

```bash
python3 -c "import ast; ast.parse(open('scripts/backends/_replicate.py').read()); print('syntax ok')"
```

Expected: `syntax ok`

- [ ] **Step 4: Commit (interim — verbatim move)**

```bash
git add scripts/backends/_replicate.py
git commit -m "refactor: copy _replicate_backend.py to scripts/backends/_replicate.py (pre-interface-refactor)"
```

### Task 12: Add ReplicateBackend class implementing the ABC

**Files:**
- Modify: `scripts/backends/_replicate.py`
- Test: `tests/test_replicate_backend.py`
- Fixture: `tests/fixtures/replicate_kling_submit.json`
- Fixture: `tests/fixtures/replicate_kling_poll_success.json`

- [ ] **Step 1: Capture frozen sample responses into fixtures**

Write `tests/fixtures/replicate_kling_submit.json`:

```json
{
  "id": "abcdef1234567890",
  "model": "kwaivgi/kling-v3-video",
  "version": "kling-v3",
  "input": {
    "prompt": "a cinematic product shot",
    "duration": 8,
    "aspect_ratio": "16:9",
    "mode": "pro"
  },
  "status": "starting",
  "created_at": "2026-04-23T15:00:00.000Z",
  "urls": {
    "cancel": "https://api.replicate.com/v1/predictions/abcdef1234567890/cancel",
    "get": "https://api.replicate.com/v1/predictions/abcdef1234567890"
  }
}
```

Write `tests/fixtures/replicate_kling_poll_success.json`:

```json
{
  "id": "abcdef1234567890",
  "status": "succeeded",
  "output": "https://replicate.delivery/xezq/output.mp4",
  "error": null,
  "logs": "",
  "created_at": "2026-04-23T15:00:00.000Z",
  "completed_at": "2026-04-23T15:04:32.000Z",
  "metrics": {
    "predict_time": 272.0,
    "video_output_duration_seconds": 8.0
  },
  "urls": {
    "cancel": "https://api.replicate.com/v1/predictions/abcdef1234567890/cancel",
    "get": "https://api.replicate.com/v1/predictions/abcdef1234567890"
  }
}
```

- [ ] **Step 2: Write failing test for ReplicateBackend class**

Write `tests/test_replicate_backend.py`:

```python
"""Tests for scripts/backends/_replicate.py — the ReplicateBackend class.

HTTP calls are mocked via urllib.request.urlopen so tests run offline.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backends import _base, _replicate

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_urlopen_response(payload: dict, status_code: int = 200):
    """Build a mock that mimics urllib.request.urlopen()'s return value."""
    m = MagicMock()
    m.read.return_value = json.dumps(payload).encode("utf-8")
    m.status = status_code
    m.getcode = MagicMock(return_value=status_code)
    m.__enter__.return_value = m
    m.__exit__.return_value = False
    return m


class TestReplicateBackendContract(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()

    def test_backend_is_provider_backend(self):
        self.assertIsInstance(self.backend, _base.ProviderBackend)

    def test_backend_name_is_replicate(self):
        self.assertEqual(self.backend.name, "replicate")

    def test_supports_expected_tasks(self):
        # Tasks the plugin actually uses on Replicate today
        expected = {"text-to-video", "image-to-video", "lipsync", "vectorize"}
        self.assertTrue(expected.issubset(self.backend.supported_tasks))


class TestReplicateSubmitKling(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_text_to_video_translates_params(self, mock_urlopen):
        with open(FIXTURES / "replicate_kling_submit.json") as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        job_ref = self.backend.submit(
            task="text-to-video",
            model_slug="kwaivgi/kling-v3-video",
            canonical_params={
                "prompt": "a cinematic product shot",
                "duration_s": 8,
                "aspect_ratio": "16:9",
                "resolution": "1080p",
            },
            provider_opts={},
            config=self.config,
        )

        self.assertIsInstance(job_ref, _base.JobRef)
        self.assertEqual(job_ref.provider, "replicate")
        self.assertEqual(job_ref.external_id, "abcdef1234567890")
        self.assertTrue(job_ref.poll_url.startswith("https://api.replicate.com"))

        # Verify the request body translated canonical -> provider-specific
        call_args = mock_urlopen.call_args
        request = call_args.args[0] if call_args.args else call_args.kwargs["url"]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["prompt"], "a cinematic product shot")
        self.assertEqual(body["input"]["duration"], 8)  # duration_s -> duration
        self.assertEqual(body["input"]["aspect_ratio"], "16:9")
        self.assertEqual(body["input"]["mode"], "pro")  # 1080p -> pro mode

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_merges_provider_opts_after_canonical(self, mock_urlopen):
        with open(FIXTURES / "replicate_kling_submit.json") as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="text-to-video",
            model_slug="kwaivgi/kling-v3-video",
            canonical_params={
                "prompt": "test",
                "duration_s": 8,
                "aspect_ratio": "16:9",
            },
            provider_opts={"multi_prompt": "[...]", "generate_audio": False},
            config=self.config,
        )

        request = mock_urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        # provider_opts must land in input
        self.assertEqual(body["input"]["multi_prompt"], "[...]")
        self.assertEqual(body["input"]["generate_audio"], False)
        # canonical still present (not overridden by provider_opts that weren't set)
        self.assertEqual(body["input"]["duration"], 8)

    def test_submit_raises_auth_error_without_key(self):
        with self.assertRaises(_base.ProviderAuthError):
            self.backend.submit(
                task="text-to-video",
                model_slug="kwaivgi/kling-v3-video",
                canonical_params={"prompt": "test"},
                provider_opts={},
                config={},  # no API key
            )


class TestReplicatePollStateMapping(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.job_ref = _base.JobRef(
            provider="replicate",
            external_id="abc",
            poll_url="https://api.replicate.com/v1/predictions/abc",
            raw={},
        )
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    def _check_state(self, provider_state, canonical_state):
        with patch("scripts.backends._replicate.urllib.request.urlopen") as m:
            m.return_value = _fake_urlopen_response({
                "id": "abc",
                "status": provider_state,
                "output": None,
                "error": None,
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            })
            status = self.backend.poll(self.job_ref, self.config)
            self.assertEqual(
                status.state, canonical_state,
                f"provider {provider_state!r} should map to canonical {canonical_state!r}",
            )

    def test_starting_maps_to_running(self):
        self._check_state("starting", "running")

    def test_processing_maps_to_running(self):
        self._check_state("processing", "running")

    def test_succeeded_maps_to_succeeded(self):
        self._check_state("succeeded", "succeeded")

    def test_failed_maps_to_failed(self):
        self._check_state("failed", "failed")

    def test_canceled_maps_to_canceled(self):
        self._check_state("canceled", "canceled")

    def test_aborted_maps_to_failed(self):
        self._check_state("aborted", "failed")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run to verify failure**

```bash
python3 -m unittest tests.test_replicate_backend -v
```

Expected: fails because `ReplicateBackend` class doesn't exist yet in `_replicate.py`.

- [ ] **Step 4: Add the ReplicateBackend class to `_replicate.py`**

Open `scripts/backends/_replicate.py` and APPEND to the end of the file (leaving existing module-level functions intact as helpers used by the class):

```python


# ═══════════════════════════════════════════════════════════════════════
# ProviderBackend implementation (new interface — adapts existing helpers)
# ═══════════════════════════════════════════════════════════════════════

from scripts.backends._base import (
    AuthStatus,
    JobRef,
    JobStatus,
    ProviderAuthError,
    ProviderBackend,
    ProviderHTTPError,
    ProviderValidationError,
    TaskResult,
)
from decimal import Decimal
from pathlib import Path as _Path


# Canonical task -> provider-specific param translator table.
# Indexed by task; each entry maps canonical_param_name -> provider_field_name.
# Provider-specific field names stay LOCAL to this module (never leak to orchestrator).
_TASK_PARAM_MAPS = {
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
    if resolution == "720p":
        return "standard"
    if resolution == "1080p":
        return "pro"
    raise ProviderValidationError(f"Kling does not support resolution={resolution!r}")


def _replicate_state_to_canonical(provider_state: str) -> str:
    """Map Replicate's 6-value enum to canonical 5-state JobStatus.state."""
    if provider_state in ("starting", "processing"):
        return "running"
    if provider_state == "succeeded":
        return "succeeded"
    if provider_state == "canceled":
        return "canceled"
    if provider_state in ("failed", "aborted"):
        return "failed"
    # Unknown provider state — treat as running so poll loop continues
    return "running"


class ReplicateBackend(ProviderBackend):
    """Replicate implementation of the ProviderBackend contract."""

    name = "replicate"
    supported_tasks = {
        "text-to-image",
        "image-to-image",
        "text-to-video",
        "image-to-video",
        "lipsync",
        "vectorize",
    }

    _USER_AGENT = "creators-studio/4.2.0 (+https://github.com/juliandickie/creators-studio)"

    def _api_key(self, config: dict) -> str:
        key = (
            config.get("providers", {}).get("replicate", {}).get("api_key")
            # Migration shim — old flat key
            or config.get("replicate_api_token")
        )
        if not key:
            raise ProviderAuthError(
                "No Replicate API key configured. "
                "Set providers.replicate.api_key in ~/.banana/config.json "
                "or run /create-video setup."
            )
        return key

    def auth_check(self, config: dict) -> AuthStatus:
        try:
            api_key = self._api_key(config)
        except ProviderAuthError as e:
            return AuthStatus(ok=False, message=str(e), provider=self.name)

        req = urllib.request.Request(
            "https://api.replicate.com/v1/account",
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": self._USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return AuthStatus(
                        ok=True,
                        message=f"Authenticated (HTTP {resp.status})",
                        provider=self.name,
                    )
                return AuthStatus(
                    ok=False,
                    message=f"Unexpected status: HTTP {resp.status}",
                    provider=self.name,
                )
        except urllib.error.HTTPError as e:
            return AuthStatus(
                ok=False, message=f"HTTP {e.code}: {e.reason}", provider=self.name
            )
        except Exception as e:
            return AuthStatus(ok=False, message=str(e), provider=self.name)

    def submit(
        self,
        *,
        task: str,
        model_slug: str,
        canonical_params: dict,
        provider_opts: dict,
        config: dict,
    ) -> JobRef:
        api_key = self._api_key(config)

        if task not in _TASK_PARAM_MAPS:
            raise ProviderValidationError(
                f"Replicate backend does not handle task {task!r}. "
                f"Supported: {sorted(_TASK_PARAM_MAPS.keys())}"
            )

        # Translate canonical params to Replicate's input schema.
        param_map = _TASK_PARAM_MAPS[task]
        input_body: dict = {}
        for canon_key, prov_key in param_map.items():
            if canon_key in canonical_params:
                input_body[prov_key] = canonical_params[canon_key]

        # Kling-specific: resolution -> mode translation
        if model_slug.startswith("kwaivgi/kling-") and "resolution" in canonical_params:
            input_body["mode"] = _resolution_to_kling_mode(canonical_params["resolution"])

        # Merge provider_opts LAST so they can shadow auto-derived fields.
        input_body.update(provider_opts)

        url = f"https://api.replicate.com/v1/models/{model_slug}/predictions"
        req = urllib.request.Request(
            url,
            data=json.dumps({"input": input_body}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": self._USER_AGENT,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (401, 403):
                raise ProviderAuthError(f"Replicate auth failed ({e.code}): {body}")
            raise ProviderHTTPError(f"Replicate submit failed ({e.code}): {body}")
        except Exception as e:
            raise ProviderHTTPError(f"Replicate submit transport error: {e}")

        return JobRef(
            provider=self.name,
            external_id=raw["id"],
            poll_url=raw.get("urls", {}).get(
                "get", f"https://api.replicate.com/v1/predictions/{raw['id']}"
            ),
            raw=raw,
        )

    def poll(self, job_ref: JobRef, config: dict) -> JobStatus:
        api_key = self._api_key(config)
        req = urllib.request.Request(
            job_ref.poll_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": self._USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise ProviderAuthError(f"Replicate poll auth failed ({e.code})")
            raise ProviderHTTPError(f"Replicate poll failed ({e.code})")
        except Exception as e:
            raise ProviderHTTPError(f"Replicate poll transport error: {e}")

        return JobStatus(
            state=_replicate_state_to_canonical(raw.get("status", "")),
            output={"output": raw.get("output")} if raw.get("output") is not None else None,
            error=raw.get("error"),
            raw=raw,
        )

    def parse_result(self, job_status: JobStatus, *, download_to: _Path) -> TaskResult:
        if job_status.state != "succeeded":
            from scripts.backends._base import ProviderError
            raise ProviderError(
                f"parse_result called on non-succeeded job (state={job_status.state!r})"
            )

        output = job_status.output["output"] if job_status.output else None
        output_urls: list = []
        if isinstance(output, str):
            output_urls = [output]
        elif isinstance(output, list):
            output_urls = [u for u in output if isinstance(u, str)]

        download_to = _Path(download_to)
        download_to.parent.mkdir(parents=True, exist_ok=True)
        output_paths: list = []
        for i, url in enumerate(output_urls):
            dest = download_to if i == 0 else download_to.with_name(
                f"{download_to.stem}_{i}{download_to.suffix}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": self._USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
                f.write(resp.read())
            output_paths.append(dest)

        raw = job_status.raw or {}
        metrics = raw.get("metrics", {}) if isinstance(raw, dict) else {}
        duration_s = metrics.get("video_output_duration_seconds")

        return TaskResult(
            output_paths=output_paths,
            output_urls=output_urls,
            metadata={"duration_s": duration_s} if duration_s is not None else {},
            provider_metadata=raw,
            cost=None,  # Cost computed by cost_tracker.py using duration + pricing mode
            task_id=raw.get("id", ""),
        )
```

- [ ] **Step 5: Run tests to verify pass**

```bash
python3 -m unittest tests.test_replicate_backend -v
```

Expected: all 11 tests PASS.

- [ ] **Step 6: Run all tests so far**

```bash
python3 -m unittest discover tests -v
```

Expected: all ~34 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/backends/_replicate.py tests/test_replicate_backend.py tests/fixtures/replicate_kling_submit.json tests/fixtures/replicate_kling_poll_success.json
git commit -m "feat: add ReplicateBackend class implementing ProviderBackend contract"
```

---

## Phase 6 — Call-site integration (rewire existing scripts)

### Task 13: Update `video_generate.py` to use the new backend

**Files:**
- Modify: `skills/create-video/scripts/video_generate.py`

**Context:** Currently imports `_replicate_backend` relative. Needs to (1) update import path, (2) call `ReplicateBackend` class instance methods instead of module-level helpers. The goal is zero behavior change — every current CLI invocation produces the same output.

- [ ] **Step 1: Read the current import block and routing logic in video_generate.py**

```bash
grep -n "_replicate_backend\|_vertex_backend" skills/create-video/scripts/video_generate.py
```

Note the line numbers of every reference — these are the call sites that need updating.

- [ ] **Step 2: Add sys.path shim and new backend import at the top of video_generate.py**

Find the current import block (should be near the top after the docstring). Before the existing `from _replicate_backend import ...` line, add:

```python
# Plugin-root shim for shared abstraction (scripts/backends, scripts/registry, scripts/routing)
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent.parent.parent))
from scripts.backends._replicate import ReplicateBackend as _ReplicateBackend
from scripts.registry import registry as _registry
from scripts import routing as _routing
```

Leave the existing `from _replicate_backend import ...` line in place — we're adding, not replacing, in this task.

- [ ] **Step 3: Add a helper that bridges old-style calls to new backend**

Find the function that currently constructs a Replicate prediction request (likely named something like `_submit_replicate` or inline in `run()`). Just above it, add:

```python
def _backend_submit_via_new_interface(
    *, task: str, model_slug: str, canonical_params: dict, provider_opts: dict, config: dict
):
    """v4.2.0 bridge: call the new ReplicateBackend instead of the module-level helpers.

    This lets us migrate call-by-call without breaking everything at once.
    When all call sites are migrated, the old module-level helpers in
    _replicate_backend.py can be deleted.
    """
    backend = _ReplicateBackend()
    return backend.submit(
        task=task,
        model_slug=model_slug,
        canonical_params=canonical_params,
        provider_opts=provider_opts,
        config=config,
    )
```

- [ ] **Step 4: Switch ONE call site as a proof-of-concept**

Find the primary Kling submit path (the one used by `--backend replicate` in the existing flow). Replace that one call with `_backend_submit_via_new_interface(...)`. Build the `canonical_params` dict from the user's CLI flags (duration, aspect_ratio, resolution, prompt).

Example — if the current code looks like:

```python
pred = submit_kling_prediction(
    prompt=args.prompt,
    duration=args.duration,
    aspect_ratio=args.aspect_ratio,
    mode="pro" if args.resolution == "1080p" else "standard",
    api_key=config["replicate_api_token"],
)
```

Change it to:

```python
job_ref = _backend_submit_via_new_interface(
    task="text-to-video" if not args.start_image else "image-to-video",
    model_slug="kwaivgi/kling-v3-video",
    canonical_params={
        "prompt": args.prompt,
        "duration_s": args.duration,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        **({"start_image": args.start_image} if args.start_image else {}),
    },
    provider_opts={},
    config=config,
)
# job_ref.external_id is what the rest of the flow needs
pred = {"id": job_ref.external_id, "urls": {"get": job_ref.poll_url}}  # adapter to old shape
```

- [ ] **Step 5: Run video_generate.py --help to verify it still loads**

```bash
python3 skills/create-video/scripts/video_generate.py --help 2>&1 | head -30
```

Expected: help text prints without import errors. If there's an `ImportError` or `ModuleNotFoundError`, fix the sys.path shim (the path math assumes 4 levels up from the script — adjust if the tree differs).

- [ ] **Step 6: Commit**

```bash
git add skills/create-video/scripts/video_generate.py
git commit -m "refactor: bridge video_generate.py Kling submit to new backend interface"
```

### Task 14: Update `video_lipsync.py` and `video_sequence.py`

**Files:**
- Modify: `skills/create-video/scripts/video_lipsync.py`
- Modify: `skills/create-video/scripts/video_sequence.py`

- [ ] **Step 1: Read both files' current imports**

```bash
grep -n "_replicate_backend\|audio_path_to_data_uri\|submit\|poll" skills/create-video/scripts/video_lipsync.py skills/create-video/scripts/video_sequence.py | head -40
```

- [ ] **Step 2: Add the same sys.path + backend import shim to both files**

At the top of each file, after existing imports, add:

```python
# v4.2.0 bridge to shared ReplicateBackend
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent.parent.parent))
from scripts.backends._replicate import ReplicateBackend as _ReplicateBackend
```

- [ ] **Step 3: video_lipsync.py — switch the Fabric submit call**

Find the code that currently submits the Fabric prediction. Replace it with:

```python
backend = _ReplicateBackend()
job_ref = backend.submit(
    task="lipsync",
    model_slug="veed/fabric-1.0",
    canonical_params={
        "image": Path(args.image),
        "audio": Path(args.audio),
        "resolution": args.resolution,
    },
    provider_opts={},
    config=config,
)
```

Update the polling path to use `backend.poll(job_ref, config)` and the download to use `backend.parse_result(job_status, download_to=Path(args.output))`.

- [ ] **Step 4: video_sequence.py — switch every Kling submit call**

The multi-shot pipeline submits multiple Kling predictions sequentially (one per shot). For each submit site, switch to the new backend (same pattern as Task 13's Step 4). If there is a single helper that multiple paths call, update the helper once.

- [ ] **Step 5: Verify both scripts still load**

```bash
python3 skills/create-video/scripts/video_lipsync.py --help 2>&1 | head -10
python3 skills/create-video/scripts/video_sequence.py --help 2>&1 | head -10
```

Expected: both print help without errors.

- [ ] **Step 6: Commit**

```bash
git add skills/create-video/scripts/video_lipsync.py skills/create-video/scripts/video_sequence.py
git commit -m "refactor: bridge video_lipsync and video_sequence to new backend interface"
```

### Task 15: Update `vectorize.py` and delete the old `_replicate_backend.py`

**Files:**
- Modify: `skills/create-image/scripts/vectorize.py`
- Delete: `skills/create-video/scripts/_replicate_backend.py`

- [ ] **Step 1: Update vectorize.py's cross-skill import shim**

Find the existing sys.path.insert that reaches into `skills/create-video/scripts/` for `_replicate_backend`. Change the path math to reach the plugin root's `scripts/backends/` instead:

Before:
```python
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent.parent / "create-video" / "scripts"))
from _replicate_backend import ...
```

After:
```python
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent.parent.parent))
from scripts.backends._replicate import ReplicateBackend
```

Update the vectorize submit/poll calls to use the class methods.

- [ ] **Step 2: Run vectorize --help to verify**

```bash
python3 skills/create-image/scripts/vectorize.py --help 2>&1 | head -20
```

Expected: help text prints without errors.

- [ ] **Step 3: Verify nothing still imports the old file**

```bash
grep -rn "_replicate_backend" skills/ scripts/ tests/ 2>&1 | grep -v "\.md:" | grep -v "Binary file"
```

Expected: empty output (no code references to the old module remain).

- [ ] **Step 4: Delete the old file**

```bash
git rm skills/create-video/scripts/_replicate_backend.py
```

- [ ] **Step 5: Run every script's --help to verify nothing broke**

```bash
for f in skills/create-video/scripts/video_generate.py skills/create-video/scripts/video_lipsync.py skills/create-video/scripts/video_sequence.py skills/create-image/scripts/vectorize.py; do
  echo "=== $f ==="
  python3 "$f" --help 2>&1 | head -3
done
```

Expected: all four print help text without errors.

- [ ] **Step 6: Run the full test suite**

```bash
python3 -m unittest discover tests -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add skills/create-image/scripts/vectorize.py skills/create-video/scripts/_replicate_backend.py
git commit -m "refactor: delete skills/create-video/scripts/_replicate_backend.py (superseded by scripts/backends/_replicate.py)"
```

---

## Phase 7 — Config schema + migration

### Task 16: Write failing test for config migration

**Files:**
- Test: `tests/test_setup_mcp_migration.py`
- Modify: `skills/create-image/scripts/setup_mcp.py`

- [ ] **Step 1: Write the test**

Write `tests/test_setup_mcp_migration.py`:

```python
"""Tests for setup_mcp.py config migration shim (v4.2.0)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "create-image" / "scripts"))

import setup_mcp


class TestMigrateOldFlatKeys(unittest.TestCase):
    def test_old_flat_keys_are_migrated(self):
        old = {
            "replicate_api_token": "r8_old",
            "google_api_key": "AIza_old",
            "elevenlabs_api_key": "sk_old",
        }
        new = setup_mcp.migrate_config_to_v4_2_0(old)
        self.assertEqual(new["providers"]["replicate"]["api_key"], "r8_old")
        self.assertEqual(new["providers"]["gemini"]["api_key"], "AIza_old")
        self.assertEqual(new["providers"]["elevenlabs"]["api_key"], "sk_old")

    def test_already_migrated_passes_through(self):
        already = {
            "providers": {
                "replicate": {"api_key": "r8_new"},
                "gemini": {"api_key": "AIza_new"},
            }
        }
        new = setup_mcp.migrate_config_to_v4_2_0(already)
        self.assertEqual(new["providers"]["replicate"]["api_key"], "r8_new")

    def test_mixed_schema_prefers_new(self):
        mixed = {
            "replicate_api_token": "r8_old",
            "providers": {"replicate": {"api_key": "r8_new"}},
        }
        new = setup_mcp.migrate_config_to_v4_2_0(mixed)
        # New wins over old when both present
        self.assertEqual(new["providers"]["replicate"]["api_key"], "r8_new")

    def test_non_api_keys_preserved(self):
        old = {
            "replicate_api_token": "r8_old",
            "custom_voices": {"narrator": {"voice_id": "abc"}},
            "named_creator_triggers": ["Annie Leibovitz"],
        }
        new = setup_mcp.migrate_config_to_v4_2_0(old)
        # Keys unrelated to provider auth pass through unchanged
        self.assertEqual(new["custom_voices"], {"narrator": {"voice_id": "abc"}})
        self.assertEqual(new["named_creator_triggers"], ["Annie Leibovitz"])

    def test_vertex_keys_grouped_under_vertex_provider(self):
        old = {
            "vertex_api_key": "ya29.x",
            "vertex_project_id": "my-project",
            "vertex_location": "us-central1",
        }
        new = setup_mcp.migrate_config_to_v4_2_0(old)
        self.assertEqual(new["providers"]["vertex"]["api_key"], "ya29.x")
        self.assertEqual(new["providers"]["vertex"]["project_id"], "my-project")
        self.assertEqual(new["providers"]["vertex"]["location"], "us-central1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
python3 -m unittest tests.test_setup_mcp_migration -v
```

Expected: `AttributeError: module 'setup_mcp' has no attribute 'migrate_config_to_v4_2_0'`.

### Task 17: Implement `migrate_config_to_v4_2_0` in setup_mcp.py

**Files:**
- Modify: `skills/create-image/scripts/setup_mcp.py`

- [ ] **Step 1: Add the migration function**

Find a location near the top of `setup_mcp.py` (after imports, before the main CLI block). Add:

```python
# ─── v4.2.0 config migration ────────────────────────────────────────────

_OLD_TO_NEW_KEYMAP = {
    "replicate_api_token":   ("replicate",  "api_key"),
    "google_api_key":        ("gemini",     "api_key"),
    "elevenlabs_api_key":    ("elevenlabs", "api_key"),
    "vertex_api_key":        ("vertex",     "api_key"),
    "vertex_project_id":     ("vertex",     "project_id"),
    "vertex_location":       ("vertex",     "location"),
    "kie_api_key":           ("kie",        "api_key"),   # future-proof for sub-project C
}


def migrate_config_to_v4_2_0(config: dict) -> dict:
    """Rewrite old flat API-key config into the v4.2.0 providers.<name>.<field> shape.

    Non-auth keys (custom_voices, named_creator_triggers, etc.) pass through
    unchanged. When both old and new forms are present, NEW wins (explicit
    migration already happened; old key is stale).
    """
    out: dict = {}
    # Start with a deep-ish copy of existing `providers` block if present.
    existing_providers = config.get("providers", {})
    if isinstance(existing_providers, dict):
        out["providers"] = {k: dict(v) if isinstance(v, dict) else v
                            for k, v in existing_providers.items()}
    else:
        out["providers"] = {}

    # Copy all non-migrated keys verbatim.
    for k, v in config.items():
        if k in _OLD_TO_NEW_KEYMAP or k == "providers":
            continue
        out[k] = v

    # Apply migrations: only fill in the new path if it isn't already set.
    for old_key, (provider, field) in _OLD_TO_NEW_KEYMAP.items():
        old_val = config.get(old_key)
        if old_val is None:
            continue
        prov_block = out["providers"].setdefault(provider, {})
        if field not in prov_block:  # NEW wins when both present
            prov_block[field] = old_val

    return out
```

- [ ] **Step 2: Run tests to verify pass**

```bash
python3 -m unittest tests.test_setup_mcp_migration -v
```

Expected: all 5 tests PASS.

- [ ] **Step 3: Wire the migration into the actual setup flow**

In `setup_mcp.py`, find where `~/.banana/config.json` is read on startup. After reading, apply the migration. Something like:

```python
# ~/.banana/config.json load
with open(CONFIG_PATH) as f:
    config = json.load(f)

# v4.2.0: auto-migrate old flat schema on every read
config = migrate_config_to_v4_2_0(config)
```

And find where config is written — after writing, the config is already in new shape (no conversion needed on write).

- [ ] **Step 4: Commit**

```bash
git add skills/create-image/scripts/setup_mcp.py tests/test_setup_mcp_migration.py
git commit -m "feat: add v4.2.0 config migration shim for provider-scoped schema"
```

---

## Phase 8 — Documentation

### Task 18: Write `references/providers/replicate.md`

**Files:**
- Create: `references/providers/replicate.md`

- [ ] **Step 1: Write the provider reference**

Write `references/providers/replicate.md`:

```markdown
# Replicate provider reference

**Purpose:** How the plugin talks to `api.replicate.com`. Auth, polling, error handling, Cloudflare quirks, and pricing model. Model-specific prompt engineering and capabilities live under `references/models/<model>.md`, not here.

**Source file:** `scripts/backends/_replicate.py` (class `ReplicateBackend`)

## Authentication

- HTTP Bearer token: `Authorization: Bearer r8_...`
- Key is stored at `~/.banana/config.json` → `providers.replicate.api_key`
- Migration shim reads the legacy flat key `replicate_api_token` too
- Get a key at <https://replicate.com/account/api-tokens>

## Endpoints

| Purpose | Method | URL |
|---|---|---|
| Auth check | GET | `https://api.replicate.com/v1/account` |
| Submit prediction | POST | `https://api.replicate.com/v1/models/{owner}/{name}/predictions` |
| Poll prediction | GET | `https://api.replicate.com/v1/predictions/{id}` |
| Cancel prediction | POST | `https://api.replicate.com/v1/predictions/{id}/cancel` |

## Status enum mapping

Replicate's `Prediction.status` has **6 values**; the plugin's canonical enum has 5. Mapping:

| Replicate | Canonical |
|---|---|
| `starting` | `running` |
| `processing` | `running` |
| `succeeded` | `succeeded` |
| `failed` | `failed` |
| `canceled` | `canceled` |
| `aborted` | `failed` |

`aborted` is terminated before `predict()` is called (e.g., queue eviction, deadline exceeded). It signals terminal failure — do not treat as retryable.

## Cloudflare / User-Agent rule

`api.replicate.com/v1/account` returns **HTTP 403 Cloudflare error 1010** on requests with the default Python urllib User-Agent. The backend MUST send:

```
User-Agent: creators-studio/<version> (+https://github.com/juliandickie/creators-studio)
```

This header is set on every Replicate request (submit, poll, download, auth check) — not just `/account`.

## Sync vs async submit

Replicate's OpenAPI documents a `Prefer: wait=N` header for synchronous inline completion (N in [1, 60]). The plugin **omits** `Prefer` entirely for async-first semantics, since Kling wall times are 3-6 minutes. Polling is the canonical path.

**Do not use `Prefer: wait=0`** — it's non-spec-compliant (Replicate's regex is `^wait(=([1-9]|[1-9][0-9]|60))?$`) and only works by accident.

## Pricing modes (for `cost_tracker.py`)

Replicate's pricing varies by model. The registry's `providers.replicate.pricing.mode` is one of:

- `per_second` — Kling ($0.02/s), Fabric ($0.15/s), DreamActor ($0.05/s), VEO tiers (varies)
- `per_call` — Recraft Vectorize ($0.01 flat)
- `by_resolution` — Nano Banana 2 (keyed by 512/1K/2K/4K)

`/v1/predictions/{id}` responses include `metrics.predict_time` and `metrics.video_output_duration_seconds` but NO `metrics.cost_usd` — the plugin computes cost client-side from the pricing mode + output duration.

## Known quirks

- **Kling `aspect_ratio` is ignored when `start_image` is provided.** The output uses the start image's native aspect. The backend logs a WARNING but does not raise.
- **Multi-prompt sum must equal top-level duration.** `sum(shot.duration for shot in multi_prompt) == duration`. Enforced client-side in the Kling-specific validator.
- **Fabric pricing is on output duration, not wall time.** A cold start (~36s) does not increase cost.
- **Seedance rejects any human subject** with error `E005 — input/output flagged as sensitive`. Seedance is NOT registered in the plugin as a default (see spec §11).

## Diagnose command

```
python3 -m scripts.backends._replicate diagnose
```

Pings `/v1/account` with the configured API key, reports auth status without burning any generation budget.
```

- [ ] **Step 2: Commit**

```bash
git add references/providers/replicate.md
git commit -m "docs: add Replicate provider reference (auth, polling, Cloudflare, pricing)"
```

### Task 19: Write `references/providers/gemini-direct.md` (placeholder — backend refactor deferred)

**Files:**
- Create: `references/providers/gemini-direct.md`

- [ ] **Step 1: Write the reference**

Write `references/providers/gemini-direct.md`:

```markdown
# Gemini direct API provider reference

**Purpose:** How the plugin talks directly to `generativelanguage.googleapis.com` for Nano Banana 2 image generation and editing. Separate from Vertex AI (which is a different provider, used for VEO + Lyria).

**Source files (current, pre-refactor):**

- `skills/create-image/scripts/generate.py` — text-to-image
- `skills/create-image/scripts/edit.py` — image-to-image editing

**Refactor status:** In sub-project A, Gemini direct remains wired through the legacy scripts. A future follow-up migrates these into `scripts/backends/_gemini_direct.py` implementing the `ProviderBackend` interface. The legacy code paths continue working unchanged until then.

## Authentication

- API key query param: `?key=AIza...`
- Stored at `~/.banana/config.json` → `providers.gemini.api_key`
- Migration shim reads legacy `google_api_key` too
- Get a key at <https://aistudio.google.com/apikey>

## Endpoints

- Generate: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}`
- Current default model: `gemini-3.1-flash-image-preview` (Nano Banana 2)

## Critical parameter rules (carry-over from existing plugin constraints)

- `imageSize` values are UPPERCASE on the Gemini API: `"1K"`, `"2K"`, `"4K"`. Lowercase fails silently.
- Gemini generates ONE image per API call. No batch parameter.
- No negative prompt parameter. Use semantic reframing in the prompt instead.
- `responseModalities` MUST explicitly include `"IMAGE"` or the API returns text only.
- **Describe the scene, don't list keywords.** Gemini 3.1's strength is narrative understanding.
- **Don't name publication formats in prompts** ("Vanity Fair magazine cover") — the model renders a literal magazine cover.
- NEVER mention "logo" in Presentation mode prompts — generates unwanted logo artifacts. Say "clean negative space" instead.

See `skills/create-image/references/prompt-engineering.md` for the full prompt construction system.

## Fallback chain

Primary: MCP (via the `@ycse/nanobanana-mcp` package) → Direct Gemini API → Replicate `google/nano-banana-2`.

This ordering survives the v4.2.0 refactor. Future `_gemini_direct.py` backend will participate in routing at the "Direct Gemini API" tier.
```

- [ ] **Step 2: Commit**

```bash
git add references/providers/gemini-direct.md
git commit -m "docs: add Gemini direct provider reference placeholder (backend refactor deferred)"
```

### Task 20: Split `kling-models.md` into `references/models/kling-v3.md` + `kling-v3-omni.md`

**Files:**
- Create: `references/models/kling-v3.md`
- Create: `references/models/kling-v3-omni.md`
- (Leave `skills/create-video/references/kling-models.md` in place — the old path is still referenced by legacy call sites. It will be deprecated in a future cleanup pass.)

- [ ] **Step 1: Read the current `kling-models.md`**

```bash
wc -l skills/create-video/references/kling-models.md
head -80 skills/create-video/references/kling-models.md
```

- [ ] **Step 2: Write `references/models/kling-v3.md`**

Write `references/models/kling-v3.md`:

```markdown
# Kling Video 3.0 (canonical model ID: `kling-v3`)

**Hosting providers:** Replicate (`kwaivgi/kling-v3-video`). Kie.ai support deferred to sub-project C.

**Registry entry:** `scripts/registry/models.json` → `models.kling-v3`

## Capabilities

- Text-to-video (5-15s clips)
- Image-to-video via `start_image` (first-frame reference)
- `end_image` for interpolation (requires `start_image`)
- Native audio generation (English + Chinese; other languages unverified)
- Multi-shot via `multi_prompt` JSON array (max 6 shots per call)
- Negative prompts

## Canonical constraints (enforced pre-HTTP)

- `aspect_ratio` ∈ {`16:9`, `9:16`, `1:1`}
- `duration_s` integer in [3, 15]
- `resolution` ∈ {`720p`, `1080p`} (maps to Kling `mode: standard | pro` inside the backend)
- `prompt` and `negative_prompt` max 2500 chars

## Pricing (via Replicate)

- `per_second` mode, $0.02 / second of output
- 8s clip at 1080p = $0.16
- 15s clip at 1080p = $0.30

## Character consistency via `start_image`

**Conditional identity lock** (empirically verified session 19, 2026-04-16):

- When `start_image` AND prompt describe the SAME character (matching age, gender, hair, clothing, setting), Kling preserves character identity through the full clip at 1072×1928 pro mode.
- When the prompt describes a DIFFERENT character, Kling morphs completely toward the prompted character within 5 seconds — the `start_image` only affects frame 0.
- **Prompt engineering is the critical variable for cross-clip character consistency.** Describe the character precisely in every shot's prompt when using start_image.
- Works for both human and non-human subjects.

## Audio language limitation

Per the model card, audio generation works best in English and Chinese only. Other languages unverified. For non-English-or-Chinese workflows, generate with `provider_opts: {"generate_audio": false}` and use `audio_pipeline.py` for the audio bed.

## Multi-shot schema (provider_opts only)

`multi_prompt` is a JSON array STRING (not a list) passed via `provider_opts`. Max 6 shots per call. Sum of shot durations MUST equal the top-level `duration` parameter.

```python
canonical_params={"prompt": "overall scene", "duration_s": 12, ...}
provider_opts={
    "multi_prompt": json.dumps([
        {"prompt": "shot 1 description", "duration": 4},
        {"prompt": "shot 2 description", "duration": 4},
        {"prompt": "shot 3 description", "duration": 4},
    ])
}
```

## Known quirks

- `aspect_ratio` silently ignored when `start_image` is provided; output uses start image's native aspect.
- `end_image` requires `start_image`; standalone `end_image` is not accepted.
- `start_image` max 10 MB; PNG / JPG / JPEG accepted (WebP intentionally excluded).

## Authoritative source

`dev-docs/kwaivgi-kling-v3-video-llms.md` — model card from Replicate.
```

- [ ] **Step 3: Write `references/models/kling-v3-omni.md`**

Write `references/models/kling-v3-omni.md`:

```markdown
# Kling Video 3.0 Omni (canonical model ID: `kling-v3-omni`)

**Hosting providers:** Replicate (`kwaivgi/kling-v3-omni-video`).

**Registry entry:** `scripts/registry/models.json` → `models.kling-v3-omni`

## Capabilities (in addition to all Kling v3 capabilities)

- **Reference images** — multimodal conditioning via `reference_images` array
- **Video editing** — takes an input video and applies natural-language edits (camera, style, subject swaps) while preserving motion and timing
- Everything Kling v3 does (text-to-video, image-to-video, multi-shot, native audio)

## When to use v3-omni vs v3

- **Use v3-omni for:** reference-image-driven style transfer, video editing workflows, multimodal inputs beyond start_image.
- **Use v3 for:** straightforward text-to-video and image-to-video. Cheaper nothing (same per-second rate), simpler API surface.

## Pricing

Same as Kling v3: `per_second` mode, $0.02/s.

## Constraints

Same canonical constraints as Kling v3 (see `kling-v3.md`).

## Authoritative source

`dev-docs/kwaivgi-kling-v3-omni-video-llms.md` — model card from Replicate.
```

- [ ] **Step 4: Commit**

```bash
git add references/models/kling-v3.md references/models/kling-v3-omni.md
git commit -m "docs: split kling-models.md into per-model references"
```

### Task 21: Write remaining model references (`nano-banana-2`, `fabric-1.0`, `dreamactor-m2.0`, `recraft-vectorize`, `veo-3.1`)

**Files:**
- Create: `references/models/nano-banana-2.md`
- Create: `references/models/fabric-1.0.md`
- Create: `references/models/dreamactor-m2.0.md`
- Create: `references/models/recraft-vectorize.md`
- Create: `references/models/veo-3.1.md`

- [ ] **Step 1: Write `references/models/nano-banana-2.md`** (summary — detailed prompt engineering stays in `skills/create-image/references/prompt-engineering.md`)

```markdown
# Google Nano Banana 2 (canonical model ID: `nano-banana-2`)

**Underlying model:** `gemini-3.1-flash-image-preview`

**Hosting providers:**

- `gemini-direct` — slug `gemini-3.1-flash-image-preview`, via Google AI Studio API (primary)
- `replicate` — slug `google/nano-banana-2` (fallback)

**Registry entry:** `scripts/registry/models.json` → `models.nano-banana-2`

## Capabilities

- Text-to-image generation
- Image-to-image editing with reference images
- Multilingual prompts
- 14 supported aspect ratios
- Resolutions: 512, 1K, 2K, 4K (Gemini direct only; Replicate supports 1K)

## Pricing

- **Gemini direct:** `by_resolution` — $0.0005 (512) / $0.002 (1K) / $0.008 (2K) / $0.032 (4K) per call
- **Replicate:** `by_resolution` — $0.003 (1K)

## Prompt engineering

See `skills/create-image/references/prompt-engineering.md` — 5-component formula, 11 domain modes, PEEL strategy, brand guide integration. All prompt engineering applies to this model whether it's served via Gemini direct or Replicate.

## Critical parameter rules

- `imageSize` values UPPERCASE on Gemini: `"1K"`, `"2K"`, `"4K"`
- ONE image per API call (no batch)
- `responseModalities` must include `"IMAGE"`
- No negative prompt — use semantic reframing

## Authoritative sources

- `dev-docs/nano-banana-image-generation.md` — Google's official Gemini 3.1 Flash Image prompting guide
- `dev-docs/google-nano-banana-2-llms.md` — Replicate model card
```

- [ ] **Step 2: Write `references/models/fabric-1.0.md`** (migrated content from `skills/create-video/references/lipsync.md`)

```markdown
# VEED Fabric 1.0 (canonical model ID: `fabric-1.0`)

**Hosting providers:** Replicate (`veed/fabric-1.0`).

**Registry entry:** `scripts/registry/models.json` → `models.fabric-1.0`

## What it does

Audio-driven lip-sync. Input: one image + one audio file. Output: the image's face lip-synced to the audio. Mouth region ONLY — no body animation, no camera movement, no emotional direction beyond audio prosody.

## Why the plugin has it

Closes the v3.8.0 gap where Kling doesn't accept external audio, so custom-designed ElevenLabs voices from `audio_pipeline.py narrate` had no way to reach a visible character's face.

## Canonical constraints

- `resolution` ∈ {`480p`, `720p`} (no 1080p or 4K)
- `duration_s` ≤ 60 (driven by audio length)
- `image` formats: jpg, jpeg, png
- `audio` formats: mp3, wav, m4a, aac

## Pricing

`per_second` mode, ~$0.15 per second of output video. Cold-start adds ~36s wall time but NOT cost (Replicate bills on output duration, not GPU wall time).

- 7s clip: ~$1.05
- 8s clip: ~$1.20
- 60s clip (max): ~$9.00

**Note:** Fabric is ~2.5× more expensive per second than Kling v3 ($0.02/s) and ~7.5× more expensive than VEO Lite ($0.05/s-equivalent). Still the only path to pair custom ElevenLabs voice with a visible face.

## Canonical 2-step workflow

```
audio_pipeline.py narrate --voice brand_voice --out /tmp/narr.mp3
  → video_lipsync.py --image face.png --audio /tmp/narr.mp3
```

## Authoritative source

`dev-docs/veed-fabric-1.0-llms.md`
```

- [ ] **Step 3: Write `references/models/dreamactor-m2.0.md`**

```markdown
# ByteDance DreamActor M2.0 (canonical model ID: `dreamactor-m2.0`)

**Hosting providers:** Replicate (`bytedance/dreamactor-m2.0`).

**Registry entry:** `scripts/registry/models.json` → `models.dreamactor-m2.0`

## What it does

Motion transfer / character animation. Input: one image + a driving video. Output: the image's subject animated with the driving video's motion, facial expressions, and lip movements. Works on humans, cartoons, animals, non-humans.

## Canonical constraints

- `duration_s` ≤ 30 (driven by driving video length)
- Output resolution up to 2048×1440 (model-side cap)

## Pricing

`per_second` mode, $0.05/s.

## When to use

**Use DreamActor for:** real-footage-to-avatar workflows (mapping a generated character onto filmed human motion).

**Don't use DreamActor for:** cross-clip character consistency in text-to-video — Kling v3 with `start_image` + matched prompts does this at higher resolution (1072×1928 vs 694×1242) and 2.5× lower cost ($0.02/s vs $0.05/s). Session 19 spike (2026-04-16) confirmed this.

## Authoritative source

`dev-docs/bytedance-dreamactor-m2.0-llms.md`
```

- [ ] **Step 4: Write `references/models/recraft-vectorize.md`**

```markdown
# Recraft Vectorize (canonical model ID: `recraft-vectorize`)

**Hosting providers:** Replicate (`recraft-ai/recraft-vectorize`).

**Registry entry:** `scripts/registry/models.json` → `models.recraft-vectorize`

## What it does

Raster (PNG/JPG/WebP) → SVG vectorization. Used by `/create-image vectorize`.

## Canonical constraints

- Input size ≤ 5 MB
- Input resolution ≤ 16 MP (16,777,216 pixels)
- Input dimensions: 256 px to 4096 px per side
- Accepts: PNG, JPG, WebP

## Pricing

`per_call` mode, $0.01 flat regardless of input dimensions.

## Authoritative source

`dev-docs/recraft-ai-recraft-vectorize-llms.md`
```

- [ ] **Step 5: Write `references/models/veo-3.1.md`** (placeholder — detailed content comes with sub-project B)

```markdown
# Google VEO 3.1 (canonical model ID: `veo-3.1-lite` / `veo-3.1-fast` / `veo-3.1`)

**Status:** Registered but NOT the default. VEO 3.1 remains opt-in backup via `--provider ... --model veo-3.1-fast` (or whichever tier). Per v3.8.0 spike 5 findings, Kling v3 wins 8 of 15 shot types to VEO Fast's 0, at 7.5× lower cost.

**Hosting providers:** Replicate (`google/veo-3.1-lite`, `google/veo-3.1-fast`, `google/veo-3.1`). Vertex AI also hosts VEO but that path is being retired in sub-project B.

**Registry entry:** `scripts/registry/models.json` → `models.veo-3.1-lite` / `models.veo-3.1-fast` / `models.veo-3.1` (entries added in sub-project B when Vertex-for-VEO is retired).

## Status in sub-project A

VEO entries are NOT seeded in `models.json` during sub-project A — that migration is done in sub-project B (Vertex retirement). Users who currently call VEO via the `_vertex_backend.py` flow continue working via the legacy path.

## Authoritative sources

- `skills/create-video/references/veo-models.md` (existing — migrated content destination)
- Sub-project B spec: follow-up plan covering VEO via Replicate
```

- [ ] **Step 6: Commit**

```bash
git add references/models/nano-banana-2.md references/models/fabric-1.0.md references/models/dreamactor-m2.0.md references/models/recraft-vectorize.md references/models/veo-3.1.md
git commit -m "docs: add per-model references for nano-banana-2, fabric, dreamactor, recraft, veo placeholder"
```

---

## Phase 9 — Meta-documentation updates

### Task 22: Update `CLAUDE.md` with new architecture notes

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read the current CLAUDE.md file responsibilities table**

```bash
grep -n "^| \`scripts" CLAUDE.md | head -10
```

- [ ] **Step 2: Add entries for new files**

In the `## File responsibilities` table, add the following rows in the appropriate alphabetical position (or grouped under a new "Provider abstraction (v4.2.0)" subsection):

```markdown
| `scripts/backends/_base.py` | **v4.2.0** Provider-agnostic abstraction: `ProviderBackend` ABC + canonical types (`JobRef`, `JobStatus`, `TaskResult`, `AuthStatus`) + exception hierarchy. Contract every provider backend implements. Stdlib only. |
| `scripts/backends/_canonical.py` | **v4.2.0** Canonical image normalizer (`Path`/`bytes`/URL/data-URI → data URI) + constraint validator (duration, aspect, resolution, prompt length). Runs BEFORE any HTTP call so bad params don't burn budget. |
| `scripts/backends/_replicate.py` | **v4.2.0** Replicate provider backend implementing `ProviderBackend`. Replaces `skills/create-video/scripts/_replicate_backend.py` (deleted). Hosts Kling v3, Kling v3 Omni, Fabric 1.0, DreamActor M2.0, Recraft Vectorize. Diagnose + smoke-test CLIs preserved. |
| `scripts/registry/models.json` | **v4.2.0** Single-source-of-truth model registry. Canonical model IDs, hosting providers, capabilities, canonical constraints, pricing. Add an entry when a new model ships; edit an entry when a model upgrades. |
| `scripts/registry/registry.py` | **v4.2.0** Registry loader + query API (typed dataclasses, validation). Import via `from scripts.registry import registry`. |
| `scripts/routing.py` | **v4.2.0** Two-stage resolution: (1) model (explicit flag > config default > registry family default), (2) provider for that model (explicit flag > family default > global default > first-with-key). Single source of routing logic. |
| `tests/test_*.py` | **v4.2.0** New unittest-based test suite (stdlib `unittest`). Run with `python3 -m unittest discover tests`. HTTP calls mocked via `urllib.request.urlopen` patches. |
| `references/providers/replicate.md` | **v4.2.0** Replicate auth, polling, Cloudflare User-Agent rule, 6-value status enum, pricing modes. |
| `references/providers/gemini-direct.md` | **v4.2.0** Gemini direct API reference (backend refactor into `_gemini_direct.py` deferred to follow-up). |
| `references/models/*.md` | **v4.2.0** Per-model references: capabilities, constraints, prompt quirks, pricing, authoritative-source citations. Lives alongside provider references for clean separation. |
```

Find existing entries for deleted/renamed files and remove or update them:

- Remove: `skills/create-video/scripts/_replicate_backend.py` row — file deleted.
- Update `skills/create-video/references/kling-models.md` row to note content migrated to `references/models/kling-v3.md` + `kling-v3-omni.md`.

- [ ] **Step 3: Add new key constraints to the `## Key constraints` section**

At the bottom of the Key constraints list, append:

```markdown
- **v4.2.0 Provider abstraction rule.** Skill orchestrator code (SKILL.md + `scripts/*.py`) MUST NOT reference provider-specific field names (`start_image`, `multi_prompt`, `image_url`, etc.). Orchestrators pass canonical params only; backends translate. If a new feature needs a provider-unique field, either extend the canonical schema (discuss first) or use `provider_opts` as the escape hatch.

- **v4.2.0 Adding a new model.** Add an entry to `scripts/registry/models.json`. Add `references/models/<id>.md`. If a novel canonical capability is needed, extend `scripts/backends/_base.py` task schema and the enforcement in `scripts/backends/_canonical.py`. That's the PR — no orchestrator changes.

- **v4.2.0 Adding a new provider.** New file `scripts/backends/_<provider>.py` implementing `ProviderBackend`. Add `references/providers/<provider>.md`. Add `providers.<name>` entries to relevant models in `models.json`. Add a key prompt to `setup_mcp.py`. Add pricing lookup to `cost_tracker.py` if the provider has a novel pricing mode. That's the PR.

- **v4.2.0 Plugin-root `scripts/` directory.** Shared abstraction code lives at `scripts/` at the plugin root (not per-skill). Skills reach in via sys.path shim. This supersedes the v4.1.0 cross-skill pattern (which routed through `skills/create-video/scripts/`). `skills/<name>/scripts/*.py` stays skill-specific; `scripts/*.py` is shared.

- **v4.2.0 Config schema.** New shape is `providers.<name>.api_key` (and `providers.vertex.project_id` etc.). Old flat keys (`replicate_api_token`, `google_api_key`, `elevenlabs_api_key`, `vertex_*`) readable via migration shim in `setup_mcp.py`. `~/.banana/` path is unchanged per the v4.0.0 config-boundary rule.

- **v4.2.0 Testing.** Tests use stdlib `unittest`. Run `python3 -m unittest discover tests` from the plugin root. HTTP calls are mocked via `urllib.request.urlopen` patches; no network required. Fixtures live at `tests/fixtures/*.json`. Before committing any change to `scripts/` or `skills/*/scripts/`, run the test suite.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with v4.2.0 architecture constraints"
```

### Task 23: Update `PROGRESS.md` with session entry

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Append a new session entry to PROGRESS.md**

Find the most recent session entry. Above it (PROGRESS.md is typically chronological with newest first), add:

```markdown
## Session YY — v4.2.0 Provider Abstraction Foundation (2026-04-23 to YYYY-MM-DD)

**Status:** Complete. Sub-project A of the provider-agnostic architecture plan.

**Shipped:**
1. `scripts/backends/_base.py` — `ProviderBackend` ABC + canonical types + exception hierarchy
2. `scripts/backends/_canonical.py` — image normalizer + constraint validator
3. `scripts/registry/models.json` + `registry.py` — canonical model registry with 6 seeded models (kling-v3, kling-v3-omni, fabric-1.0, dreamactor-m2.0, recraft-vectorize, nano-banana-2)
4. `scripts/routing.py` — two-stage model + provider resolution
5. `scripts/backends/_replicate.py` — Replicate backend refactored from the old `_replicate_backend.py`, now implementing the new interface
6. Call sites migrated: `video_generate.py`, `video_lipsync.py`, `video_sequence.py`, `vectorize.py`
7. Config migration shim in `setup_mcp.py` — old flat keys readable, new writes use provider-scoped schema
8. Test suite introduced: `tests/test_*.py` (stdlib unittest, zero pip deps)
9. Per-model and per-provider references created under `references/models/` and `references/providers/`

**Zero behavior change** for end users — all existing commands produce identical output.

**Follow-ups:**
- Sub-project B: retire `_vertex_backend.py`, route VEO + Lyria via Replicate (separate plan)
- Sub-project C: `_kie.py` backend with Suno music capability (separate plan, depends on A)
- Sub-project D: `_hf.py` backend for Hugging Face Inference Providers (optional, depends on A)
- Refactor `generate.py` + `edit.py` → `_gemini_direct.py` (follow-up to A, not blocking anything)
- Refactor `audio_pipeline.py` internals → `_elevenlabs.py` (follow-up, larger-scope)

**Key files added (paths relative to plugin root):**
- `scripts/backends/_base.py`
- `scripts/backends/_canonical.py`
- `scripts/backends/_replicate.py`
- `scripts/registry/models.json`
- `scripts/registry/registry.py`
- `scripts/routing.py`
- `references/providers/replicate.md`
- `references/providers/gemini-direct.md`
- `references/models/kling-v3.md`
- `references/models/kling-v3-omni.md`
- `references/models/nano-banana-2.md`
- `references/models/fabric-1.0.md`
- `references/models/dreamactor-m2.0.md`
- `references/models/recraft-vectorize.md`
- `references/models/veo-3.1.md` (placeholder)
- `tests/test_base.py`, `tests/test_canonical.py`, `tests/test_registry.py`, `tests/test_routing.py`, `tests/test_replicate_backend.py`, `tests/test_setup_mcp_migration.py`
- `tests/fixtures/replicate_kling_submit.json`, `tests/fixtures/replicate_kling_poll_success.json`
- `docs/superpowers/specs/2026-04-23-provider-abstraction-design.md`
- `docs/superpowers/plans/2026-04-23-provider-abstraction-subproject-a.md`

**Key files deleted:**
- `skills/create-video/scripts/_replicate_backend.py` (moved to plugin-root `scripts/backends/_replicate.py`)
```

- [ ] **Step 2: Update ROADMAP.md — mark sub-project A done**

Open `ROADMAP.md`. Find any line referencing the provider abstraction, multi-provider support, or Kie.ai integration. Add or update to reflect:

```markdown
### v4.2.0 (2026-04-XX) — Provider Abstraction Foundation

**Shipped:** Sub-project A of the provider-agnostic architecture. `ProviderBackend` ABC + model registry + routing. Zero behavior change; sets up the abstraction for Kie.ai, HF Inference Providers, and future marketplaces to land as single-file additions.

**Next (planned):**
- **v4.2.1 — Sub-project B: Vertex retirement via Replicate** — route VEO 3.1 (all tiers) and Lyria 3 through `_replicate.py`; delete `_vertex_backend.py`.
- **v4.3.0 — Sub-project C: Kie.ai backend** — adds Suno music as a new capability. `--provider kie` option for users who pay Kie.
- **v4.4.0 — Sub-project D: Hugging Face Inference Providers backend** — one backend unlocks 17 underlying inference providers for text-to-image and text-to-video.
```

- [ ] **Step 3: Commit**

```bash
git add PROGRESS.md ROADMAP.md
git commit -m "docs: update PROGRESS.md and ROADMAP.md for v4.2.0 sub-project A"
```

---

## Phase 10 — Version bump and release

### Task 24: Version bump + CHANGELOG

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `README.md`
- Modify: `CITATION.cff`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump version in `plugin.json`**

Open `.claude-plugin/plugin.json`. Change the `version` field:

```json
"version": "4.2.0"
```

- [ ] **Step 2: Bump badge in README.md**

Find the version badge in `README.md` (it looks like `![Version](https://img.shields.io/badge/version-4.1.3-...)`). Update to `4.2.0`.

- [ ] **Step 3: Bump CITATION.cff**

Open `CITATION.cff`. Change:

```yaml
version: 4.2.0
date-released: 2026-04-XX
```

(Use the actual release date.)

- [ ] **Step 4: Add CHANGELOG entry**

Open `CHANGELOG.md`. Add at the top (under the intro):

```markdown
## [4.2.0] — 2026-04-XX

### Added
- Provider-agnostic architecture foundation (sub-project A of the multi-marketplace roadmap). New `scripts/backends/_base.py` defines a `ProviderBackend` ABC that every provider implements; canonical task types live there too.
- Model registry at `scripts/registry/models.json`: single source of truth for canonical model IDs, hosting providers, capabilities, canonical constraints, and pricing modes. Adding a new model is a registry-entry PR.
- Canonical image normalizer (`scripts/backends/_canonical.py`): `Path` / `bytes` / URL / data-URI all accepted by backends; each backend normalizes internally.
- Two-stage routing resolution (`scripts/routing.py`): model first (explicit flag > config default > registry default), provider second (explicit flag > family default > global default > first-with-key).
- Config schema `providers.<name>.api_key`; migration shim reads old flat keys (`replicate_api_token`, `google_api_key`, `elevenlabs_api_key`, `vertex_*`).
- Per-provider references under `references/providers/` and per-model references under `references/models/` — two independent catalogs, each changing on its own cycle.
- Test suite under `tests/` (stdlib `unittest`, no new dependencies). Run via `python3 -m unittest discover tests`.

### Changed
- `skills/create-video/scripts/_replicate_backend.py` moved to `scripts/backends/_replicate.py` and refactored to implement `ProviderBackend`. Callers (`video_generate.py`, `video_lipsync.py`, `video_sequence.py`, `vectorize.py`) updated.
- Shared abstraction code now lives at plugin root `scripts/` (not per-skill). Supersedes v4.1.0 cross-skill import pattern.

### Deprecated
- Old flat config keys (`replicate_api_token`, etc.) still readable but written-through as `providers.<name>.api_key` on first write. Expected removal: v4.4.0.

### Preserved (deliberately)
- `~/.banana/` config directory (v4.0.0 user-state-boundary rule).
- Zero behavior change for end users — all existing commands produce identical output.
- Fallback chain: MCP → Direct Gemini API → Replicate.

### Not in this release (separate plans)
- Sub-project B — Vertex retirement via Replicate (planned v4.2.1).
- Sub-project C — Kie.ai backend + Suno music capability (planned v4.3.0).
- Sub-project D — Hugging Face Inference Providers backend (planned v4.4.0).

[4.2.0]: https://github.com/juliandickie/creators-studio/compare/v4.1.3...v4.2.0
```

- [ ] **Step 5: Add a "What's New" README entry (short, sales-copy style per CLAUDE.md rule)**

Find the `## What's New in This Fork` section in `README.md`. Add at the top (newest first):

```markdown
### Provider Abstraction Foundation (v4.2.0)

The plugin is now marketplace-agnostic. Bring your own API key for Replicate today, and the architecture makes adding Kie.ai, Hugging Face Inference Providers, or any future marketplace a one-file change. Same commands, same behavior — but now the plumbing scales to the Nth provider.
```

Under 3 sentences — follows the CLAUDE.md "What's New" rule.

- [ ] **Step 6: Commit version bump**

```bash
git add .claude-plugin/plugin.json README.md CITATION.cff CHANGELOG.md
git commit -m "chore: bump version to 4.2.0"
```

### Task 25: Final validation — Feature Completion Checklist

**Files:** (no changes — verification only)

- [ ] **Step 1: Run the full test suite one more time**

```bash
python3 -m unittest discover tests -v
```

Expected: all tests PASS (should be ~40+ tests across 6 test files).

- [ ] **Step 2: Verify no references to old paths or old module names remain**

```bash
grep -rn "_replicate_backend\|create-video/scripts/_replicate_backend" skills/ scripts/ tests/ 2>&1 | grep -v "Binary file" | grep -v ".md:"
```

Expected: empty output (only doc comments or commit messages may reference the old module name).

- [ ] **Step 3: Verify every script's `--help` still works**

```bash
for f in skills/create-video/scripts/video_generate.py \
         skills/create-video/scripts/video_lipsync.py \
         skills/create-video/scripts/video_sequence.py \
         skills/create-image/scripts/vectorize.py \
         skills/create-image/scripts/generate.py \
         skills/create-image/scripts/edit.py; do
  echo "=== $f ==="
  python3 "$f" --help 2>&1 | head -3
done
```

Expected: all six print help text without import errors.

- [ ] **Step 4: Verify SKILL.md size is still under 500 lines**

```bash
wc -l skills/create-image/SKILL.md skills/create-video/SKILL.md
```

Expected: both under 500.

- [ ] **Step 5: Verify version consistency across files**

```bash
grep -E '"version"|version-[0-9]+\.[0-9]+\.[0-9]+|version: [0-9]' .claude-plugin/plugin.json README.md CITATION.cff
```

Expected: `4.2.0` appears consistently in plugin.json (JSON), README.md (badge), CITATION.cff (yaml).

- [ ] **Step 6: Run `claude plugin validate .` if available**

```bash
claude plugin validate . 2>&1 || echo "claude CLI not available in this env — skip"
```

Expected: either `valid` or the "skip" fallback.

### Task 26: Merge the feature branch and tag the release

**Files:** (git operations only)

- [ ] **Step 1: Verify branch is clean**

```bash
git status
```

Expected: `nothing to commit, working tree clean` on branch `feature/provider-abstraction-v4.2.0`.

- [ ] **Step 2: Present a final scope review to the user (per memory rule)**

> **STOP.** Before merging/pushing/tagging, surface a scope review summarizing what's landed in v4.2.0 and get explicit user approval. This is the release commit, so the `feedback_release_checkin` rule applies.

Summary to present to user:

```
v4.2.0 scope review:
- Architecture foundation (sub-project A) complete
- 6 models seeded in registry (Kling v3, Kling v3 Omni, Fabric 1.0, DreamActor M2.0, Recraft Vectorize, Nano Banana 2)
- 1 concrete backend shipped (_replicate.py); Vertex, Kie, HF deferred to B/C/D
- Legacy call sites migrated with zero behavior change
- Test suite introduced (stdlib unittest, ~40+ tests, zero pip deps)
- Config migration shim handles old flat keys
- ~.banana/ path unchanged (user-state boundary preserved)

Proceed with merge to main + tag v4.2.0 + push + zip/release?
```

Wait for user approval. If changes are requested, make them before continuing.

- [ ] **Step 3: After user approves — merge to main**

```bash
git checkout main
git merge --no-ff feature/provider-abstraction-v4.2.0 -m "Merge feature/provider-abstraction-v4.2.0: v4.2.0 provider abstraction foundation"
```

- [ ] **Step 4: Tag the release**

```bash
git tag -a v4.2.0 -m "v4.2.0 — Provider abstraction foundation (sub-project A)"
```

- [ ] **Step 5: Push main and the tag**

```bash
git push origin main
git push origin v4.2.0
```

- [ ] **Step 6: Build the release zip per CLAUDE.md checklist #11**

```bash
cd /Users/juliandickie/code/creators-studio-project/creators-studio
zip -r ../creators-studio-v4.2.0.zip . -x ".git/*" ".DS_Store" "*/.DS_Store" \
  "*__pycache__/*" "*.pyc" ".github/*" "screenshots/*" "PROGRESS.md" \
  "ROADMAP.md" "CODEOWNERS" "CODE_OF_CONDUCT.md" "SECURITY.md" \
  "CITATION.cff" ".gitattributes" ".gitignore" ".claude/*" "spikes/*"
```

- [ ] **Step 7: Create GitHub release**

```bash
gh release create v4.2.0 \
  ../creators-studio-v4.2.0.zip \
  --title "v4.2.0 — Provider Abstraction Foundation" \
  --notes "See CHANGELOG.md for details. Sub-project A of the multi-marketplace roadmap."
```

- [ ] **Step 8: Delete the feature branch (local + remote)**

```bash
git branch -d feature/provider-abstraction-v4.2.0
git push origin --delete feature/provider-abstraction-v4.2.0 2>/dev/null || true
```

---

## Self-review checklist (performed after writing this plan)

**1. Spec coverage:** Every requirement from the spec maps to a task:

| Spec requirement | Task |
|---|---|
| §3.1 file layout (scripts/, backends/, registry/, tests/) | Task 1 |
| §3.1 registry/models.json seeded | Task 4 |
| §3.2 two independent catalogs (providers/ + models/) | Tasks 18-21 |
| §4.1 nine canonical task types | Tasks 3 (base types), 12 (translation table) |
| §4.2 CanonicalImage encoding (Path/URL/bytes/data-URI) | Tasks 7-8 |
| §4.3 provider_opts escape hatch | Tasks 12 (merge semantics), test at Task 12 Step 2 |
| §4.4 TaskResult canonical response | Tasks 2-3 |
| §5 model registry entry shape | Task 4 |
| §5.2 adding a new model — tested implicitly by seed entries | Task 4 |
| §5.3 multiple image models first-class — nano-banana-2 in seed | Task 4 |
| §6 ProviderBackend ABC | Task 3 |
| §7 routing (two-stage resolution) | Tasks 9-10 |
| §8 config schema + migration | Tasks 16-17 |
| §10 backward compat (old keys readable, ~/.banana/ unchanged) | Task 17 |
| §11.1 sub-project A deliverables | All tasks |
| §13 success criteria (zero behavior change) | Tasks 13-15 (smoke tests) + Task 25 (final validation) |

**2. Placeholder scan:** No `TODO`, `TBD`, "implement later", "fill in details" in the plan. No step that says "write tests for the above" without showing the test code. Every code block is complete.

**3. Type consistency:** `ProviderBackend.submit` signature is identical across Task 3 (definition), Task 12 (implementation), Task 13 (call site). Canonical field names (`duration_s`, `aspect_ratio`, `start_image`, `resolution`) are identical in the registry (Task 4), validator (Task 8), routing (Task 10), and backend (Task 12). `JobRef`, `JobStatus`, `TaskResult`, `AuthStatus` match between `_base.py` (Task 3), test file (Task 2), and backend implementation (Task 12).

**4. Execution sequencing:** Task order respects dependencies. Task 12 depends on Tasks 3 (base) + 4 (registry entries) + 8 (canonical). Tasks 13-15 depend on Task 12. Tasks 22-23 depend on all preceding tasks (meta-docs come last).
