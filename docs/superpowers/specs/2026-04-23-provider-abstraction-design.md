# Provider-Agnostic Creator Studio Architecture

**Status:** Approved design, pending implementation
**Date:** 2026-04-23
**Scope:** Architecture foundation (sub-project A). Sub-projects B (Vertex retirement), C (Kie.ai backend), and D (Hugging Face Inference Providers backend) are follow-on plans that apply this spec.

## 1. Context and motivation

The plugin currently wires three model-serving surfaces directly: Google Gemini API (for Nano Banana images), Vertex AI (for VEO + Lyria), and Replicate (for Kling, Fabric, DreamActor, Recraft, Nano Banana 2 via `google/nano-banana-2`). Each is coded against a specific backend's request/response shape. When a user wants to bring a different marketplace — Kie.ai (they already pay them), Hugging Face Inference Providers (a meta-aggregator covering 17 underlying providers), fal.ai, or a future outlier — the work is not "one new file." It is a refactor of every script that calls a provider.

This spec defines the abstraction that turns "add a new marketplace" into a one-file task and makes the plugin genuinely marketplace-neutral, matching the v4.0.0 rebrand intent ("model-agnostic on purpose"). It also makes "a new model released / an existing model upgraded" a registry entry rather than an orchestrator edit, which matters because models churn constantly (Seedance 1080p, GPT Image 2, Kling 3.0, Nano Banana 2, etc.).

**Non-goals for this spec:**

- Shipping Kie.ai, HF Inference Providers, or any other new backend. Those are separate plans that *apply* this spec.
- Retiring Vertex AI. That is sub-project B — a separate plan that ships in parallel.
- Cross-provider fallback chains ("try Replicate, on 429 retry Kie"). Interesting future work; YAGNI for v1.
- Per-call cost-comparison routing ("always pick the cheapest provider that can serve this model"). Deferred.
- Changing the `~/.banana/` config directory name. v4.0.0 rule: user state path is stable.
- Integrating Higgsfield.ai. Appears to be a consumer SaaS with no public API; re-evaluate if they ship one.

## 2. Architecture overview

Five layers, each with one responsibility:

```
/create-image | /create-video | /create-audio        ← User commands
                   ↓
SKILL.md orchestrator + scripts/*.py                  ← Speaks CANONICAL task params only
                   ↓
Canonical task schema                                 ← 9 task types, stable per-task param set
                   ↓
Provider backend                                      ← Translates canonical → provider-specific,
(scripts/backends/_<provider>.py                       submits HTTP, polls, parses response back
 implements ProviderBackend interface)                 to canonical.
                   ↓
Model registry (scripts/registry/models.json)         ← Canonical model ID → provider slugs +
                                                         constraints + pricing + capabilities
                   ↓
External provider APIs                                ← Replicate, Kie, HF, Gemini, ElevenLabs...
```

The orchestrator layer never sees provider-specific field names. A call to generate an image-to-video clip with Kling v3 on Replicate and the same call on Kie.ai differ only in which backend object is instantiated — the canonical params flowing in are identical.

## 3. Three-layer catalog

Two *independent* reference catalogs plus a code-level registry.

### 3.1 File layout

```
creators-studio/
├── scripts/
│   ├── registry/
│   │   ├── models.json              ← Single source of truth: canonical IDs,
│   │   │                              providers, constraints, pricing, capabilities
│   │   └── registry.py              ← Load, query, validate registry
│   └── backends/
│       ├── _base.py                 ← ProviderBackend ABC + canonical types
│       ├── _replicate.py            ← Refactored from current _replicate_backend.py
│       ├── _kie.py                  ← Sub-project C
│       ├── _hf.py                   ← Sub-project D
│       ├── _gemini_direct.py        ← Refactored from scripts/generate.py + edit.py
│       └── _elevenlabs.py           ← Refactored from audio_pipeline.py internals
├── references/
│   ├── providers/                   ← AUTH, polling, error codes, pricing, Cloudflare quirks
│   │   ├── replicate.md
│   │   ├── kie.md
│   │   ├── hf.md
│   │   ├── gemini-direct.md
│   │   └── elevenlabs.md
│   └── models/                      ← Prompt engineering, capabilities, constraints, verdict
│       ├── kling-v3.md
│       ├── kling-v3-omni.md
│       ├── veo-3.1.md
│       ├── sora-2.md
│       ├── nano-banana-2.md
│       ├── imagen-4.md
│       ├── seedream-5.md
│       ├── gpt-image-2.md
│       ├── flux-2.md
│       └── suno.md
```

### 3.2 Why two catalogs, not one

Providers churn on one axis: Replicate tightens Cloudflare rules, Kie changes auth headers, HF adds a new underlying provider. These changes apply to *every model that provider hosts*. Coupling them into per-model docs forces N edits for one provider change.

Models churn on another axis: Seedance hits 1080p, GPT releases Image 2, Kling ships a safer content filter. These changes apply to *every provider that hosts that model*. Coupling them into per-provider docs forces N edits for one model upgrade.

Two catalogs → each change is localized.

### 3.3 Provider × Model intersection

The "how does Provider X call Model Y" detail — field names, slug, encoding quirks — lives **inside the provider backend code**, not in the reference docs. Example: `_replicate.py` knows that Kling v3 uses `start_image` and expects a data URI; `_kie.py` knows the same model uses `image_url` and expects a public URL. Neither detail leaks into the user-facing docs or the orchestrator.

## 4. Canonical task schema (Option B — hybrid with escape hatch)

### 4.1 Task types

Nine primary tasks, each with a stable canonical param set:

| Task ID | Required | Optional |
|---|---|---|
| `text-to-image` | prompt | aspect_ratio, seed, negative_prompt, reference_images[], count, resolution |
| `image-to-image` | prompt, source_image | aspect_ratio, seed, strength, mask |
| `text-to-video` | prompt | duration_s, aspect_ratio, resolution, seed, audio_enabled |
| `image-to-video` | prompt, start_image | end_image, duration_s, aspect_ratio, resolution, seed |
| `text-to-speech` | text, voice_id | language, stability, similarity_boost, speed |
| `music-generation` | prompt | duration_ms, negative_prompt, seed |
| `lipsync` | image, audio | resolution |
| `video-edit` | source_video, prompt | seed |
| `vectorize` | source_image | (Recraft) |

### 4.2 Canonical image encoding

The single biggest velocity leverage point. Any canonical image param (`source_image`, `start_image`, `end_image`, `reference_images[]`, `image` for lipsync) accepts a `CanonicalImage` — a tagged union:

```python
CanonicalImage = Union[
    Path,           # local file
    HttpUrl,        # str starting with http:// or https://
    DataUri,        # str starting with data:
    bytes,          # raw image bytes
]
```

The backend's `_normalize_image(img)` helper discriminates on type/prefix and converts to whatever the provider API accepts (Replicate prefers data URI for small images and public URL for large; Kie is URL-first; Gemini direct takes base64 in `inlineData`). Orchestrator code passes any form; backend handles the rest. MIME type sniffing happens in the helper, not in the orchestrator.

### 4.3 Escape hatch

Every task accepts `provider_opts: dict` — a passthrough for provider-unique features. CLI surface: `--opts '{"multi_prompt": [...]}'`. The backend merges `provider_opts` into its HTTP payload *after* canonical translation, so canonical values take precedence but provider-unique flags still reach the API.

Examples of legitimate `provider_opts` use:
- Kling's `multi_prompt` JSON array for multi-shot generation
- Kling motion-control keypoints
- VEO's `enhance_prompt: true`
- Fabric's resolution enum (if canonical `resolution` ever diverges)
- Any genuinely provider-unique feature that shouldn't force a canonical schema change

This is the explicit trade-off of Option B: users get uniformity for the 90% case, full power for the 10%.

### 4.4 Canonical response shape

All backends return `TaskResult`:

```python
@dataclass
class TaskResult:
    output_paths: list[Path]          # Downloaded local files
    output_urls: list[str]            # Signed URLs from provider (may expire)
    metadata: dict                    # {duration_s, resolution, aspect, seed_used, ...}
    provider_metadata: dict           # Raw provider response for debugging / audit
    cost: Optional[Decimal]           # If backend can compute; None if not
    task_id: str                      # Provider's prediction/task ID (for logs)
```

Callers can always reach `provider_metadata` for provider-specific fields without breaking the canonical contract.

## 5. Model registry entry shape

```json
{
  "id": "kling-v3",
  "display_name": "Kling Video 3.0",
  "family": "video",
  "tasks": ["text-to-video", "image-to-video"],
  "doc": "references/models/kling-v3.md",
  "canonical_constraints": {
    "aspect_ratio": ["16:9", "9:16", "1:1"],
    "duration_s": {"min": 3, "max": 15, "integer": true},
    "resolutions": ["720p", "1080p"]
  },
  "providers": {
    "replicate": {
      "slug": "kwaivgi/kling-v3-video",
      "capabilities": ["audio_generation", "multi_prompt", "start_image", "end_image", "negative_prompt"],
      "pricing": {"mode": "per_second", "rate": 0.02, "currency": "USD"},
      "availability": "GA",
      "notes": "aspect_ratio ignored when start_image provided; sum of multi_prompt durations must equal top-level duration"
    },
    "kie": {
      "slug": "market/kling/kling-3-0",
      "capabilities": ["audio_generation", "multi_prompt"],
      "pricing": {"mode": "per_call", "rate": null, "currency": "USD"},
      "availability": "GA",
      "notes": "Kie.ai pricing via credits; rate not advertised per-call"
    }
  }
}
```

### 5.1 Registry responsibilities

- **Enumerate canonical models.** Each model has one canonical ID (`kling-v3`, `veo-3.1-fast`, `nano-banana-2`, `gpt-image-2`, etc.). The ID is plugin-internal; it is what the orchestrator and user talk about.
- **List which providers host each model** under `providers.<name>` with the provider-specific slug, pricing, availability, and notes.
- **Declare canonical constraints** that the orchestrator enforces BEFORE calling any backend (e.g., duration out of range fails fast without burning an API call). Provider-level constraints that differ from canonical go in `providers.<name>.notes` or are enforced in the backend.
- **Record pricing mode** — `per_second`, `per_call`, `per_clip`, or resolution-keyed — for `cost_tracker.py` dispatch. Matches the four-mode pattern already in use as of v4.1.0.

### 5.2 Adding a new model

When Seedance 1080p, GPT Image 2, Kling 4, or any new model ships:

1. Add an entry to `registry/models.json`.
2. Add a `references/models/<model>.md` with prompt engineering guidance.
3. If the model introduces a genuinely novel capability (e.g., GPT Image 2's new editing mode), either extend the canonical schema OR document it in the entry's `provider_opts` examples.
4. Ship it. Zero orchestrator changes. No SKILL.md edits. No new CLI flags.

### 5.3 Multiple image models are first-class

The plugin's legacy center-of-gravity is Gemini Nano Banana. That stays — but it's one model among peers in the registry. `gpt-image-2`, `imagen-4`, `seedream-5`, `flux-2`, and any future model sit alongside with equal status. The user can switch the default image model via `config.defaults.image_model = "gpt-image-2"` without any code changes on our side. Each model has its own reference doc capturing its prompt engineering quirks (Seedream prefers X, Flux prefers Y, GPT Image 2 supports Z).

## 6. Provider backend interface (`scripts/backends/_base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

# --- Canonical types -----------------------------------------------------

@dataclass
class JobRef:
    """Opaque handle to an in-flight async job."""
    provider: str                    # "replicate"
    external_id: str                 # Provider's task/prediction ID
    poll_url: str                    # URL to GET for status
    raw: dict                        # Full submit response, for debugging

@dataclass
class JobStatus:
    state: str                       # "pending" | "running" | "succeeded" | "failed" | "canceled"
    output: Optional[dict]           # Provider-specific output blob, populated on success
    error: Optional[str]
    raw: dict

@dataclass
class TaskResult:
    output_paths: list[Path]
    output_urls: list[str]
    metadata: dict
    provider_metadata: dict
    cost: Optional[Decimal]
    task_id: str

@dataclass
class AuthStatus:
    ok: bool
    message: str
    provider: str

# --- Provider interface --------------------------------------------------

class ProviderBackend(ABC):
    """A single provider's implementation of the canonical task contract.

    Each backend is a pure data-translation layer plus HTTP plumbing. No
    global state. Stdlib only (urllib.request, json, base64). Follows the
    pattern proven by the existing _replicate_backend.py.
    """

    name: str                        # "replicate"
    supported_tasks: set[str]        # {"text-to-image", "image-to-video", ...}

    @abstractmethod
    def auth_check(self, config: dict) -> AuthStatus:
        """Ping the provider's cheapest read endpoint with the configured
        API key. Used by /setup and /status commands. Must not burn any
        billable generation budget."""

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
        provider_opts, POST to the provider's submit endpoint, return an
        opaque JobRef.

        Raises ProviderValidationError on canonical violation (before HTTP),
        ProviderHTTPError on transport/API failure, ProviderAuthError on
        401/403.
        """

    @abstractmethod
    def poll(self, job_ref: JobRef, config: dict) -> JobStatus:
        """GET the provider's status endpoint. Called on a caller-managed
        loop; backend does not block or sleep internally. Maps provider
        state enum to canonical state (e.g., Replicate's 6-value enum
        including 'aborted' maps to canonical 5-value)."""

    @abstractmethod
    def parse_result(self, job_status: JobStatus, *, download_to: Path) -> TaskResult:
        """When job_status.state == 'succeeded', download the output file(s)
        to download_to, compute/lookup cost, return TaskResult."""
```

### 6.1 What the refactor of `_replicate_backend.py` looks like

Current `_replicate_backend.py` is already ~75% shaped correctly — pure data translation, stdlib only, no global state. The refactor:

- Extract the abstract interface into `_base.py`.
- Rename `_replicate_backend.py` → `_replicate.py`.
- Move per-model validation (e.g., `validate_kling_params`) into either backend-local helpers or the canonical-enforcement layer.
- Move model registry entries (currently dict constants in `_replicate_backend.py`) into `registry/models.json`.
- Keep the diagnose + smoke-test CLIs — they're valuable for debugging.

No behavior change for callers during this refactor. All existing flows (`video_generate.py`, `video_lipsync.py`, `vectorize.py`) continue to work.

## 7. Routing policy

Two independent resolutions happen per command: **which model** and **which provider for that model**.

### 7.1 Model resolution

1. Explicit `--model <id>` flag wins (e.g., `--model gpt-image-2`).
2. Else `config.defaults.<family>_model` (e.g., `defaults.video_model = "kling-v3"`).
3. Else the registry's declared default for that family (set in `models.json` as a top-level `family_defaults` block, e.g., `{"image": "nano-banana-2", "video": "kling-v3", "music": "elevenlabs-music"}`).

### 7.2 Provider resolution (given a resolved model)

1. **Explicit flag wins.** `--provider kie` → use Kie. If Kie doesn't host the resolved model, error clearly with the list of providers that do.
2. **Task-family default.** Read `config.defaults.<family>` (e.g., `defaults.video = "replicate"`). If that provider hosts the resolved model, use it.
3. **Global default.** Read `config.default_provider`. If that provider hosts the resolved model, use it.
4. **First-with-key.** Iterate the model's `providers` dict in **JSON insertion order** (preserved by Python's stdlib `json.load` since 3.7). Use the first provider in that order that has a configured API key.
5. **No match → clear error.** `"Kling v3 is available on Replicate and Kie.ai, but neither has an API key configured. Run /create-video setup."`

**Resolution interaction:** provider-level defaults are checked FIRST for routing; if the resolved model isn't hosted on that provider, we don't fall back silently — we surface the mismatch so the user can either override or reconfigure. Silent fallback hides provider-host availability gaps that users need to know about.

## 8. Config schema and migration

### 8.1 New schema (additive to existing `~/.banana/config.json`)

```json
{
  "providers": {
    "replicate": {"api_key": "r8_..."},
    "kie":       {"api_key": "kie_..."},
    "gemini":    {"api_key": "AIza..."},
    "elevenlabs":{"api_key": "sk_..."}
  },
  "default_provider": "replicate",
  "defaults": {
    "image": "gemini",
    "image_model": "nano-banana-2",
    "video": "replicate",
    "video_model": "kling-v3",
    "music": "elevenlabs",
    "music_model": "elevenlabs-music"
  }
}
```

Two levels of defaults: **provider-per-family** (`defaults.video`) and **model-per-family** (`defaults.video_model`). The model-level default is optional; if absent, orchestrator picks the registry's default for that family.

### 8.2 Migration shim

Old flat keys are read-compatible:

| Old key | New path |
|---|---|
| `replicate_api_token` | `providers.replicate.api_key` |
| `google_api_key` | `providers.gemini.api_key` |
| `elevenlabs_api_key` | `providers.elevenlabs.api_key` |
| `vertex_api_key`, `vertex_project_id`, `vertex_location` | `providers.vertex.*` (if we keep Vertex; otherwise drop in sub-project B) |
| `custom_voices.*` | unchanged (ElevenLabs-specific; stays at current path) |
| `named_creator_triggers` | unchanged |

`setup_mcp.py` on first run after upgrade detects old keys and rewrites to new shape. Old path remains readable for rollback safety for one version.

**Hard rule (per v4.0.0 constraint):** the config directory stays at `~/.banana/`. The plugin's external identity is `creators-studio`; the user-state path is frozen.

## 9. Addition workflows (the goal — small PRs)

### 9.1 Adding a new model

1. Add entry to `registry/models.json`.
2. Add `references/models/<model>.md`.
3. (Rare) If novel canonical capability, extend `_base.py` task schema.
4. Ship.

### 9.2 Adding a new provider

1. New file: `scripts/backends/_<provider>.py` implementing `ProviderBackend`.
2. New reference: `references/providers/<provider>.md`.
3. Add `providers.<name>` entries to relevant `models.json` entries.
4. Add `<name>` key prompt to `setup_mcp.py`.
5. Add pricing lookup branch to `cost_tracker.py` (if the provider has a novel pricing mode).
6. Ship.

Both workflows are deliberately small. The measure of this spec's success: when Kling v4 ships, it's a 3-file PR. When fal.ai becomes worth adding, it's a 5-file PR.

## 10. Backward compatibility

- `~/.banana/` config path — **unchanged**.
- Flat config keys — readable via migration shim; new writes go to `providers.<name>.api_key`.
- Old `--backend replicate|vertex|gemini` flag — deprecated alias for `--provider`, logs a one-line deprecation warning on use, still works for at least one major version.
- Existing `/create-image` and `/create-video` commands — surface-compatible. `--provider` flag is new and optional; no other user-visible changes.
- Existing `kwaivgi/kling-v3-video` model slug constant in `_replicate_backend.py` continues to resolve correctly during the refactor (migration is mechanical, not behavioral).
- The `@ycse/nanobanana-mcp` MCP package name is NOT renamed — it's a third-party upstream dependency the plugin doesn't own.

## 11. Sub-project decomposition

This spec defines architecture (sub-project A). Three sibling sub-projects apply it:

### 11.1 Sub-project A (THIS spec — architecture foundation)

**Deliverables (minimum to ship A):**
- `scripts/backends/_base.py` with `ProviderBackend` ABC + canonical types (`JobRef`, `JobStatus`, `TaskResult`, `AuthStatus`) + exception hierarchy (`ProviderValidationError`, `ProviderHTTPError`, `ProviderAuthError`)
- `scripts/registry/models.json` seeded with all currently-used models (Kling v3, Kling v3 Omni, VEO 3.1 Lite/Fast/Std, Nano Banana 2, Fabric 1.0, DreamActor M2.0, Recraft Vectorize, Lyria 3, ElevenLabs TTS/Music — the models the plugin currently actually uses)
- `scripts/registry/registry.py` — load, query, validate the registry at startup
- **Refactor of `scripts/create-video/scripts/_replicate_backend.py` → `scripts/backends/_replicate.py`** implementing the new interface. This is the only concrete backend shipped in A. It's already ~75% shaped correctly, so the refactor is mechanical.
- Canonical-enforcement layer (`scripts/backends/_canonical.py`): a thin wrapper between orchestrator and backend that validates `canonical_params` against the registry's `canonical_constraints` BEFORE the backend's HTTP call
- Routing policy implementation (`scripts/routing.py`): resolves `{task, model_id, user_flags}` → backend instance
- Config schema migration in `setup_mcp.py`: reads old flat keys, writes new `providers.<name>.api_key` shape, keeps old keys readable for one version
- `references/providers/replicate.md` (new): auth, polling, Cloudflare User-Agent rule, 6-value status enum, error codes, pricing per model family
- `references/providers/gemini-direct.md` (new): documentation-only placeholder describing the Gemini direct API surface (no backend refactor in A — the existing `generate.py` and `edit.py` stay untouched and continue to work via their current code path; they'll be refactored into `_gemini_direct.py` in a follow-up)
- Model references: split current `kling-models.md` / `veo-models.md` / `gemini-models.md` into per-model files under `references/models/`. This is a mechanical reshuffling; content survives as-is
- `CLAUDE.md` + `PROGRESS.md` + `ROADMAP.md` updates
- **Zero behavior change for end users** — all existing commands (`/create-image generate`, `/create-video generate`, etc.) produce identical output from identical inputs

**Explicitly NOT in sub-project A (deferred to follow-ups):**
- Refactor of direct-Gemini scripts (`generate.py`, `edit.py`) into `_gemini_direct.py` — the refactor is mechanical and can ship later without blocking anything. Listed in §3.1 file layout as target state.
- Refactor of `audio_pipeline.py` into `_elevenlabs.py` — ElevenLabs has substantial surface (TTS, music, voice design, cloning, mixing) that warrants its own planning pass. Listed in §3.1 file layout as target state.
- Any concrete backend other than Replicate. Sub-projects C (Kie), D (HF) are separate plans.

### 11.2 Sub-project B — Vertex retirement (independent; can ship in parallel)

Separate plan. Route VEO 3.1 (all tiers) via `_replicate.py` using `google/veo-3.1-lite`, `google/veo-3.1-fast`, `google/veo-3.1`. Route Lyria 3 via `_replicate.py` using `google/lyria-3`. Delete `_vertex_backend.py`. Remove `vertex_*` config keys from setup flow. Depends on A only in that registry must exist; can start once A's registry + Replicate backend are in place.

### 11.3 Sub-project C — Kie.ai backend (depends on A)

Separate plan. New file `scripts/backends/_kie.py` implementing `ProviderBackend`. Read `dev-docs/kie.ai.llms.txt` + follow deeper API docs to ground the implementation. Add Kie `providers.kie` entries to registry for all supported models. Add Suno as `music-generation` capability (Kie-exclusive — not on Replicate). Add Kie API key prompt to `setup_mcp.py`. Add Kie pricing to `cost_tracker.py`.

### 11.4 Sub-project D — Hugging Face Inference Providers backend (depends on A; optional / future)

Separate plan. New file `scripts/backends/_hf.py` implementing `ProviderBackend` against HF Inference Providers task endpoints. Gated on confirming HF supports image-to-video (not just text-to-video) — the plugin relies heavily on `start_image` workflows. If supported, one backend unlocks 17 underlying inference providers.

## 12. Open questions and known unknowns

- **Kie.ai API polling vs callback architecture.** Kie's docs emphasize webhook callbacks. The plugin's current paradigm is polling. Sub-project C will either adapt to polling (if Kie supports it) or introduce a lightweight polling fallback around the callback URL. To be determined during sub-project C.
- **HF Inference Providers image-to-video coverage.** The HF task index lists `text-to-video` and `image-to-image` but not `image-to-video` explicitly. Needs a deeper docs read during sub-project D.
- **Higgsfield API availability.** Not confirmed to exist based on the provided sitemap file. If an API ships, the architecture supports it with no changes; if not, out of scope.
- **Per-model pricing capture for Kie.** Kie uses a credit system rather than per-call USD; the cost tracker may need a new pricing mode (`credits` with a USD conversion rate stored in config).
- **Registry format — JSON vs YAML vs Python module.** Starting with JSON for stdlib simplicity + PR-review readability. If the registry grows complex enough that JSON becomes painful, revisit.

## 13. Success criteria

This spec succeeds if, six months after shipping:

1. Adding a new model (e.g., Kling 4 when it ships) is a 3-file PR: registry entry + model reference + maybe one provider backend tweak.
2. Adding a new provider (e.g., fal.ai if it becomes relevant) is a 5-file PR: backend implementation + provider reference + registry entries + setup prompt + cost tracker branch.
3. A user with Replicate-only keys sees no behavior change from today.
4. A user with Kie-only keys can run the same commands with `--provider kie` and reach Kling, Sora 2, Suno, etc.
5. The `~/.banana/` config path has not moved; API keys configured before the upgrade still work.
6. `SKILL.md` files do not contain any Replicate-specific, Kie-specific, or Gemini-specific field names.
