# Sub-Project B: Vertex Retirement + Lyria 3 Upgrade

**Status:** Approved design, pending implementation
**Date:** 2026-04-23
**Target release:** v4.2.1
**Parent spec:** [2026-04-23-provider-abstraction-design.md](./2026-04-23-provider-abstraction-design.md) (sub-project A, shipped v4.2.0)

## 1. Context and motivation

Sub-project A (v4.2.0) shipped the `ProviderBackend` abstraction, model registry, and routing. The Replicate backend was refactored as the first concrete provider. Vertex AI remained in place as an opt-in backup for VEO 3.1 video generation and as the production path for Lyria 2 music generation.

Sub-project B finishes the Vertex retirement. Every Vertex-hosted model currently in use (VEO 3.1 Lite/Fast/Standard, Lyria 2) has a Replicate equivalent available as of the v4.2.0 research round. Retiring Vertex removes 958 lines of `_vertex_backend.py` plus embedded Vertex calls in `audio_pipeline.py`, eliminates the service-agent provisioning tax, and brings all video and music models under the single provider abstraction the v4.2.0 spec defined.

Alongside the retirement, B upgrades Lyria from v2 (`lyria-002`) to v3 as the within-Lyria default. Lyria 3 is cheaper per call ($0.04 vs $0.06), generates at the same 30s clip length, adds image-input conditioning (up to 10 reference images), and adds vocal generation. Lyria 2 stays registered for the one job Lyria 3 cannot do — `negative_prompt`-based exclusion, the differentiator that kept Lyria in the plugin after v3.8.3's ElevenLabs 12-0 bake-off win. Lyria 3 Pro — a genuinely different product generating full-length songs up to 3 minutes with structure tags and custom lyrics — is registered as a first-class model from day 1.

ElevenLabs Music remains the overall music default per the v3.8.3 verdict. Nothing user-visible changes about default music generation; the Lyria changes are internal to `--music-source lyria` workflows.

**Non-goals for this spec:**

- Refactoring ElevenLabs into a `ProviderBackend` implementation. ElevenLabs keeps its current direct-call code path in `audio_pipeline.py`. That refactor is a separate future sub-project.
- Refactoring Gemini direct (`generate.py`, `edit.py`) into `_gemini_direct.py`. Carried over from v4.2.0 as non-blocking.
- Renaming `~/.banana/` → `~/.creators-studio/`. Queued as v4.2.2.
- Running the music bake-off. Queued as a post-sub-project-C roadmap item.
- Adopting Lyria 3 Pro as a defaulted model. It's registered and reachable; the bake-off determines defaults.

## 2. Scope

### 2.1 What ships in v4.2.1

**VEO migration:**
- Register three VEO 3.1 tiers in the model registry: `veo-3.1-lite`, `veo-3.1-fast`, `veo-3.1`.
- Route all VEO traffic through `ReplicateBackend` using `google/veo-3.1-*` slugs.
- Replace the `--backend vertex-ai` flow in `video_generate.py` with Replicate routing.
- Delete `skills/create-video/scripts/_vertex_backend.py` (958 lines).
- Replace the placeholder `references/models/veo-3.1.md` written in v4.2.0 with real content covering all three tiers.

**Lyria migration + upgrade:**
- Register `lyria-2`, `lyria-3`, and `lyria-3-pro` in the model registry.
- Wire `music-generation` into `ReplicateBackend._TASK_PARAM_MAPS` (the canonical task type listed in the v4.2.0 spec but not yet implemented).
- Refactor `audio_pipeline.py` Lyria code (`generate_music_lyria`, `generate_music_lyria_extended`) to delegate to `ReplicateBackend` instead of constructing Vertex URLs inline.
- Default within-Lyria version → `lyria-3` (was `lyria-002`).
- Add intent-aware routing within the Lyria family: prompt with song structure tags / timestamps / explicit lyrics auto-routes to `lyria-3-pro`; otherwise stays on `lyria-3`.
- Add `--lyria-version {2,3,3-pro}` CLI flag to `audio_pipeline.py music` for explicit override.
- Register `elevenlabs-music` in the model registry as a placeholder with `slug: "(direct)"`, honoring the multi-model principle even though its runtime path is still direct-call from `audio_pipeline.py`.

**Config migration:**
- Remove Vertex setup prompts from `setup_mcp.py` CLI (`--vertex-api-key`, `--vertex-project`, `--vertex-location`).
- Keep the migration shim's `vertex_*` → `providers.vertex.*` path — writes still round-trip for existing users, just no longer consumed by any backend. Quiet death, not a forced re-setup.

**Documentation:**
- Replace the `references/models/veo-3.1.md` placeholder from v4.2.0 with real content covering all three tiers.
- Add `references/models/lyria-2.md`, `references/models/lyria-3.md`, `references/models/lyria-3-pro.md`, `references/models/elevenlabs-music.md`.
- Update `references/providers/replicate.md` — add VEO + Lyria to the hosted-models list and the pricing modes section.
- Add music bake-off plan + multi-model principle to `ROADMAP.md`.
- Update `CLAUDE.md` key constraints: document intent-aware Lyria routing, the multi-model-principle rule, VEO now routing through Replicate.
- Add Session 25 entry to `PROGRESS.md` summarizing B.

### 2.2 What this spec explicitly does NOT do

- No bake-off — the decision to run a 4-way ElevenLabs / Lyria 3 / Lyria 3 Pro / Suno comparison is queued for after sub-project C ships and makes Suno accessible.
- No ElevenLabs backend refactor.
- No Gemini direct backend refactor.
- No config directory rename.
- No changes to `--music-source elevenlabs` behavior (which is the plugin default and handles both instrumental and lyrics natively per the ElevenLabs Music API).
- No changes to Kling, Fabric, DreamActor, Recraft routing (all already through Replicate).

## 3. Architecture delta

### 3.1 Registry additions

Seven new entries in `scripts/registry/models.json`:

```json
{
  "veo-3.1-lite": {
    "display_name": "Google VEO 3.1 Lite",
    "family": "video",
    "tasks": ["text-to-video", "image-to-video"],
    "doc": "references/models/veo-3.1.md",
    "canonical_constraints": {
      "duration_s": {"enum": [4, 6, 8]},
      "aspect_ratio": ["16:9", "9:16"],
      "resolutions": ["720p", "1080p"],
      "conditional": "resolution=1080p requires duration_s=8"
    },
    "providers": {
      "replicate": {
        "slug": "google/veo-3.1-lite",
        "capabilities": ["audio_generation", "last_frame"],
        "pricing": {
          "mode": "per_second_by_resolution",
          "rates": {"720p": 0.05, "1080p": 0.08},
          "currency": "USD"
        },
        "availability": "GA",
        "notes": "Cheapest VEO tier. Audio always on (no without_audio variant). Does NOT support reference images or video extension. 1080p requires exactly 8-second duration. Per v3.8.0 spike 5, Kling v3 wins 8/15 shot types at ~7x lower cost; VEO is opt-in backup only."
      }
    }
  },
  "veo-3.1-fast": {
    "display_name": "Google VEO 3.1 Fast",
    "family": "video",
    "tasks": ["text-to-video", "image-to-video"],
    "doc": "references/models/veo-3.1.md",
    "canonical_constraints": {
      "duration_s": {"enum": [4, 6, 8]},
      "aspect_ratio": ["16:9", "9:16"],
      "resolutions": ["720p", "1080p"]
    },
    "providers": {
      "replicate": {
        "slug": "google/veo-3.1-fast",
        "capabilities": ["audio_generation", "audio_toggle", "reference_images", "last_frame"],
        "pricing": {
          "mode": "per_second_by_audio",
          "rates": {"with_audio": 0.15, "without_audio": 0.10},
          "currency": "USD"
        },
        "availability": "GA",
        "notes": "Mid-tier VEO, optimized for generation speed. Supports up to 3 reference images and frame-to-frame generation. Opt-in backup via --provider replicate --model veo-3.1-fast."
      }
    }
  },
  "veo-3.1": {
    "display_name": "Google VEO 3.1 Standard",
    "family": "video",
    "tasks": ["text-to-video", "image-to-video"],
    "doc": "references/models/veo-3.1.md",
    "canonical_constraints": {
      "duration_s": {"enum": [4, 6, 8]},
      "aspect_ratio": ["16:9", "9:16"],
      "resolutions": ["720p", "1080p", "4K"]
    },
    "providers": {
      "replicate": {
        "slug": "google/veo-3.1",
        "capabilities": ["audio_generation", "audio_toggle", "reference_images", "last_frame", "video_extension", "4k_output", "higher_fidelity"],
        "pricing": {
          "mode": "per_second_by_audio",
          "rates": {"with_audio": 0.40, "without_audio": 0.20},
          "currency": "USD"
        },
        "availability": "GA",
        "notes": "Highest-fidelity VEO tier. Only tier supporting 4K output and video extension. Up to 3 reference images. Most expensive in the roster at $0.40/s with audio — use Kling v3 for cost-sensitive workflows."
      }
    }
  },
  "lyria-2": {
    "display_name": "Google Lyria 2",
    "family": "music",
    "tasks": ["music-generation"],
    "doc": "references/models/lyria-2.md",
    "canonical_constraints": {
      "duration_fixed_s": 30
    },
    "providers": {
      "replicate": {
        "slug": "google/lyria-2",
        "capabilities": ["negative_prompt", "seed"],
        "pricing": {"mode": "per_call", "rate": 0.06, "currency": "USD"},
        "availability": "GA",
        "notes": "Kept registered despite Lyria 3 default because it uniquely supports negative_prompt exclusion."
      }
    }
  },
  "lyria-3": {
    "display_name": "Google Lyria 3 (Clip)",
    "family": "music",
    "tasks": ["music-generation"],
    "doc": "references/models/lyria-3.md",
    "canonical_constraints": {
      "duration_fixed_s": 30
    },
    "providers": {
      "replicate": {
        "slug": "google/lyria-3",
        "capabilities": ["reference_images", "vocals", "multilingual", "structure_tags"],
        "pricing": {"mode": "per_call", "rate": 0.04, "currency": "USD"},
        "availability": "GA",
        "notes": "Default within Lyria family. 30s clip only — use lyria-3-pro for full songs. No negative_prompt."
      }
    }
  },
  "lyria-3-pro": {
    "display_name": "Google Lyria 3 Pro",
    "family": "music",
    "tasks": ["music-generation"],
    "doc": "references/models/lyria-3-pro.md",
    "canonical_constraints": {
      "duration_max_s": 180
    },
    "providers": {
      "replicate": {
        "slug": "google/lyria-3-pro",
        "capabilities": ["reference_images", "vocals", "custom_lyrics", "structure_tags", "timestamp_control", "multilingual"],
        "pricing": {"mode": "per_call", "rate": 0.08, "currency": "USD"},
        "availability": "GA",
        "notes": "Auto-selected within Lyria family when prompt contains song structure tags, timestamps, or explicit lyrics."
      }
    }
  },
  "elevenlabs-music": {
    "display_name": "ElevenLabs Music",
    "family": "music",
    "tasks": ["music-generation"],
    "doc": "references/models/elevenlabs-music.md",
    "canonical_constraints": {
      "duration_ms": {"min": 3000, "max": 300000}
    },
    "providers": {
      "elevenlabs": {
        "slug": "(direct)",
        "capabilities": ["vocals", "lyrics_editing", "multilingual", "music_finetunes", "subscription_billed"],
        "pricing": {"mode": "subscription", "rate": null, "currency": "USD"},
        "availability": "GA",
        "notes": "Not yet refactored into ProviderBackend. audio_pipeline.py calls ElevenLabs directly. Registered so family_defaults.music is honest."
      }
    }
  }
}
```

And the `family_defaults` block updates:

```json
{
  "family_defaults": {
    "image": "nano-banana-2",
    "video": "kling-v3",
    "music": "elevenlabs-music"
  }
}
```

### 3.1b Canonical schema extensions

Two small additions to `_canonical.py::validate_canonical_params()` to support the VEO constraint shapes:

**`duration_s: {enum: [...]}`** — alternative to the existing `{min, max, integer}` shape. Matches VEO's "only 4, 6, or 8 seconds accepted." Implementation:

```python
c = constraints.get("duration_s")
if c is not None and "duration_s" in params:
    v = params["duration_s"]
    if "enum" in c:
        if v not in c["enum"]:
            raise CanonicalValidationError(
                f"duration_s={v} not in allowed values {c['enum']}"
            )
    else:
        # existing min/max/integer path
        ...
```

Kling / Fabric / DreamActor keep using the `{min, max, integer}` shape — no change.

**Conditional constraints note.** VEO 3.1 Lite has a cross-field rule: `resolution=1080p` requires `duration_s=8`. This is NOT enforced by the canonical layer (which validates fields independently). Instead, `ReplicateBackend` submits the request and trusts Replicate to reject invalid combinations with a clear 400. The registry's `canonical_constraints.conditional` field documents the rule for human readers but isn't machine-enforced in B. If user error rates are high, a follow-up release can add a cross-field validator.

### 3.1c Pricing mode additions for `cost_tracker.py`

Two new pricing modes join the existing four (`per_call`, `per_clip`, `per_second`, `by_resolution`):

**`per_second_by_resolution`** — used by VEO 3.1 Lite. Dispatch logic:

```python
def _cost_per_second_by_resolution(pricing: dict, resolution: str, duration_s: float) -> Decimal:
    rate = Decimal(str(pricing["rates"][resolution]))
    return rate * Decimal(str(duration_s))
```

**`per_second_by_audio`** — used by VEO 3.1 Fast and VEO 3.1 Standard. Dispatch logic:

```python
def _cost_per_second_by_audio(pricing: dict, audio_enabled: bool, duration_s: float) -> Decimal:
    key = "with_audio" if audio_enabled else "without_audio"
    rate = Decimal(str(pricing["rates"][key]))
    return rate * Decimal(str(duration_s))
```

Callers (`video_generate.py` after Replicate success) pass `duration_s` + either `resolution` or `audio_enabled` alongside the log-cost subprocess call, same pattern as existing `per_second` Kling cost logging.

### 3.2 Canonical task type: `music-generation`

New entry in `ReplicateBackend._TASK_PARAM_MAPS`:

```python
"music-generation": {
    "prompt": "prompt",
    "negative_prompt": "negative_prompt",    # Lyria 2 only; backend logs warning if
                                              # passed to Lyria 3 / 3 Pro
    "reference_images": "images",             # Lyria 3 / 3 Pro; 0-10 images
    "seed": "seed",                           # Lyria 2 only
},
```

`ReplicateBackend.supported_tasks` gains `"music-generation"`.

### 3.3 Intent-aware Lyria routing

Lives in `audio_pipeline.py` (orchestrator), not in the backend. Backend stays model-agnostic; orchestrator decides which Lyria variant to ask for.

```python
import re

LYRIC_STRUCTURE_INDICATORS = {
    "[verse", "[chorus", "[bridge", "[hook",
    "[intro", "[outro", "[pre-chorus", "[refrain",
}
TIMESTAMP_INDICATOR = re.compile(r"\[\d+:\d{2}\s*-\s*\d+:\d{2}\]")
EXPLICIT_INSTRUMENTAL = {
    "instrumental only", "no vocals", "no lyrics", "instrumental",
}


def detect_lyrics_intent(prompt: str) -> bool:
    """Return True if the prompt appears to request a full song with lyrics
    and/or structure. Used for auto-routing Lyria 3 Clip vs Lyria 3 Pro."""
    lower = prompt.lower()
    if any(ind in lower for ind in EXPLICIT_INSTRUMENTAL):
        return False
    if any(ind in lower for ind in LYRIC_STRUCTURE_INDICATORS):
        return True
    if TIMESTAMP_INDICATOR.search(prompt):
        return True
    return False


def resolve_lyria_version(prompt: str, explicit_version: str | None) -> str:
    """Given a prompt (and optional --lyria-version override), return the
    canonical model ID to use: 'lyria-2', 'lyria-3', or 'lyria-3-pro'."""
    if explicit_version is not None:
        return {"2": "lyria-2", "3": "lyria-3", "3-pro": "lyria-3-pro"}[explicit_version]
    if detect_lyrics_intent(prompt):
        return "lyria-3-pro"
    return "lyria-3"
```

**Cost visibility:** when auto-routing resolves to `lyria-3-pro`, log one line:

```
[audio] Detected song structure in prompt; routing to Lyria 3 Pro ($0.08/file vs Lyria 3 Clip $0.04). Pass --lyria-version 3 to force the cheaper variant.
```

### 3.4 `audio_pipeline.py` refactor — what changes

Minimal surface-area change. User-facing CLI stays identical except for the new optional `--lyria-version` flag.

**Before (current Vertex-based code in `audio_pipeline.py`):**
- `generate_music_lyria(prompt, negative_prompt, out_path, ...)` builds Vertex URL, calls `{location}-aiplatform.googleapis.com`, polls, downloads.
- `generate_music_lyria_extended(prompt, target_duration_sec, ...)` loops N calls of the above and FFmpeg-crossfades them into a single track for lengths > 32.768s.
- Both functions compute auth from `~/.banana/config.json` → `vertex_api_key` / `vertex_project_id` / `vertex_location`.

**After (Replicate-based via `ReplicateBackend`):**
- Each function becomes a thin adapter:

```python
from scripts.backends._replicate import ReplicateBackend
from scripts.registry import registry as _reg

def generate_music_lyria(prompt, negative_prompt=None, out_path=None,
                         lyria_version=None, ...):
    model_id = resolve_lyria_version(prompt, lyria_version)
    registry = _reg.load_registry()
    model = registry.get_model(model_id)
    slug = model.providers["replicate"]["slug"]

    canonical_params = {"prompt": prompt}
    if negative_prompt and model_id == "lyria-2":
        canonical_params["negative_prompt"] = negative_prompt
    elif negative_prompt:
        _log.warning(f"negative_prompt ignored; {model_id} does not support it.")

    backend = ReplicateBackend()
    config = _load_config()                   # reads providers.replicate.api_key
    job = backend.submit(
        task="music-generation",
        model_slug=slug,
        canonical_params=canonical_params,
        provider_opts={},
        config=config,
    )
    # Poll loop (existing pattern, same as video_generate.py)
    ...
    result = backend.parse_result(status, download_to=out_path)
    return result
```

- `generate_music_lyria_extended` keeps its FFmpeg-crossfade logic; only the per-chunk call changes. Crossfade math moves from a 32.768s per-chunk assumption to 30s (Lyria 2 and Lyria 3 Clip both produce 30s; Lyria 3 Pro is not chained — if user needs >30s on Pro, they pass `--duration-ms 120000` and Pro handles it in one call).
- ElevenLabs code paths in `audio_pipeline.py` — UNTOUCHED.

### 3.5 `video_generate.py` migration

Three changes:

1. **Import deletion:** remove `import _vertex_backend as vertex` (line 34). The sys.path shim above it (line 33: `sys.path.insert(0, str(Path(__file__).resolve().parent))`) stays — nothing else relies on it.
2. **`_select_backend()` simplification:** the function that currently dispatches between Gemini API, Vertex, and Replicate based on the model slug now has one fewer branch. The "Vertex" path goes away; VEO slugs starting with `google/veo-3.1-*` route to Replicate.
3. **Flag deprecation:** `--backend vertex-ai` becomes a deprecated alias. When passed, log:

```
WARNING: --backend vertex-ai is deprecated. Vertex AI was retired in v4.2.1; VEO 3.1 now routes through Replicate. The flag is honored for one release and will be removed in v4.3.0.
```

Then silently route to `--backend replicate` internally.

`--provider veo` similarly becomes `--provider replicate --model veo-3.1-{lite,fast,}`. If user passes `--provider veo` without `--model`, default to `veo-3.1-fast`.

### 3.6 Vertex config migration — quiet death

`setup_mcp.migrate_config_to_v4_2_0()` (shipped v4.2.0) already handles the schema shim. In B, the `vertex_*` keys get read into `providers.vertex.*` as before — nothing consumes them now, but they don't error either. Users with existing configs see zero errors.

`setup_mcp.py`'s CLI prompts for `--vertex-*` flags are removed. Existing users who run `/create-video setup` again won't be asked about Vertex anymore.

Future cleanup (not in B): once we're confident no user is reaching the `providers.vertex.*` block, it can be pruned on the next config write. For B, we let sleeping bytes lie.

## 4. Multi-model principle (codified)

Ratifying the rule the user stated during design:

> "We definitely always want to keep a multi-model approach for every application because you just don't know every time a new model gets released. The previous default could get dethroned."

**Rule (added to `CLAUDE.md` key constraints):** every model family with a registry entry MUST have at least two registered models, so the plugin always has a fallback when a new default emerges. Registration is cheap — providers can share a slug, pricing entries are compact, reference docs can be placeholders.

**What this looks like per family in v4.2.1:**

- Image: `nano-banana-2` (default), `recraft-vectorize` (vectorize-only) — add second text-to-image model as soon as sub-project C brings Kie.ai Imagen/Seedream/Flux online.
- Video: `kling-v3` (default), `kling-v3-omni`, `veo-3.1-lite/fast/standard`, `fabric-1.0` (lipsync), `dreamactor-m2.0` — fully covered.
- Music: `elevenlabs-music` (default), `lyria-2`, `lyria-3`, `lyria-3-pro`, + `suno` after sub-project C.

## 5. Cost tracker additions

`cost_tracker.py`'s `_lookup_cost()` already handles the three pricing modes in the registry (`per_second`, `per_call`, `by_resolution`). One new mode joins:

- `subscription` — returns `Decimal("0")` because the call is billed against the user's ElevenLabs subscription, not per-call USD. The caller can still log usage for volume tracking even if dollars-per-call is zero.

Ledger entries look like:

```
2026-05-01T14:23:12  video   veo-3.1-fast        per_second  8s   $0.80
2026-05-01T14:25:44  music   lyria-3             per_call    30s  $0.04
2026-05-01T14:27:12  music   lyria-3-pro         per_call    90s  $0.08
2026-05-01T14:31:05  music   elevenlabs-music    sub         120s $0.00
```

## 6. Test coverage

### 6.1 New tests

- `tests/test_lyria_migration.py` (new file):
  - `test_detect_lyrics_intent_with_verse_tag` — `"[Verse] a song"` → True
  - `test_detect_lyrics_intent_with_timestamp` — `"[0:00 - 0:30] intro"` → True
  - `test_detect_lyrics_intent_with_instrumental_only` — `"chill lo-fi, instrumental only"` → False
  - `test_detect_lyrics_intent_plain_prompt` — `"a jazz track with saxophone"` → False
  - `test_resolve_lyria_version_explicit_wins` — `--lyria-version 2` with song-tags prompt → `lyria-2`
  - `test_resolve_lyria_version_auto_pro` — song-tags prompt, no flag → `lyria-3-pro`
  - `test_resolve_lyria_version_default_clip` — plain prompt, no flag → `lyria-3`

- `tests/test_replicate_backend.py` additions:
  - `test_submit_music_generation_lyria_3_translates_params` — prompt + reference_images → Replicate body
  - `test_submit_music_generation_lyria_2_preserves_negative_prompt` — negative_prompt passes through
  - `test_submit_music_generation_lyria_3_drops_negative_prompt_with_warning` — mock logger asserting WARNING

- `tests/test_replicate_backend.py` VEO additions:
  - `test_submit_text_to_video_veo_lite_translates_params`
  - Fixture: `tests/fixtures/replicate_veo_submit.json`

- `tests/test_registry.py`:
  - `test_lyria_family_has_three_models` — assert lyria-2, lyria-3, lyria-3-pro all present
  - `test_veo_3_1_lite_fast_standard_registered`
  - `test_family_defaults_music_is_elevenlabs` — confirms v4.2.1 family_defaults update
  - `test_multi_model_principle` — every family has ≥2 registered models

### 6.2 Regression coverage

- Existing 74 tests continue to pass unchanged.
- Expected total after B: ~90 tests.

### 6.3 Deleted tests

- None. `_vertex_backend.py` didn't have dedicated tests in v4.2.0 (was a tech-debt gap). No test file to delete.

## 7. Migration story for users

**Existing user on v4.2.0 with Vertex configured:**
1. Upgrades to v4.2.1.
2. `/create-video setup` no longer asks about Vertex.
3. Existing `~/.banana/config.json` still has `vertex_api_key` + `vertex_project_id` + `vertex_location` — harmlessly ignored.
4. `/create-video generate --prompt "..." --provider veo` continues to work but logs a deprecation notice; routes to Replicate via `google/veo-3.1-fast`.
5. `/create-video audio music --prompt "..." --source lyria` — was silently using Lyria 2 on Vertex; now silently uses Lyria 3 on Replicate. User may notice a subtle quality difference (bake-off will quantify).
6. `/create-video audio music --prompt "..." --source lyria --negative-prompt "saxophone"` — still works, but orchestrator notices `negative_prompt` and routes to Lyria 2 automatically (keeping the exclusion feature alive).

**Existing user on v4.2.0 who never used Vertex:**
- Zero change.

## 8. Roadmap additions (post-B)

Added to `ROADMAP.md`:

### Music bake-off (queued post-sub-project-C)

**Dependencies:** Sub-project C (Kie.ai backend, which adds Suno access).

**Methodology:**

**Part 1 — Instrumental, 12 genres.**
Each contender receives its native-format prompt with explicit "Instrumental only" tag.

| Contender | Prompt format |
|---|---|
| ElevenLabs Music | ElevenLabs-native phrasing |
| Lyria 3 Clip | Concise, 1-2 sentences with "Instrumental only, no vocals" |
| Lyria 3 Pro | Structured, `[Intro] [Verse]` with "Instrumental only" |
| Suno (via Kie.ai) | Suno-native (format investigated as part of bake-off) |

Blind A/B listening across all pairs. Winner = new within-family default for instrumental music.

**Part 2 — Full songs with lyrics, 6 archetypes.**
Archetypes: pop verse/chorus, lo-fi chill, cinematic orchestral with vocals, indie folk, hip-hop, electronic.

| Contender | Lyrics handling |
|---|---|
| ElevenLabs Music | Native prompt with section-level lyric editing; up to 5 min, multilingual |
| Lyria 3 Clip | Excluded (30s fixed cap) |
| Lyria 3 Pro | Structured `[Verse]/[Chorus]/[Bridge]` + timestamp control; up to ~3 min |
| Suno (via Kie.ai) | Suno-native lyric input |

Blind A/B listening. Winner = new auto-route target when `detect_lyrics_intent(prompt) == True`.

**Methodology rule (carried from v3.7.2 F13):** subjective listening test only. Benchmark metrics / spec-sheet quality is uncorrelated with subjective audio quality. Ideal config per contender prevents handicapping.

**Qualitative considerations flagged but not scored:**
- ElevenLabs Music Finetunes — custom model training on user audio. No Lyria/Suno equivalent. Relevant to brand-consistency workflows beyond the bake-off.
- Duration cap — ElevenLabs 5 min, Lyria 3 Pro ~3 min, Suno (TBD).
- Pricing — reported separately; bake-off is about quality per contender at its ideal config.

## 9. Implementation phases (high-level — detailed in plan)

The writing-plans skill will produce a detailed task-by-task breakdown. High-level phases:

- **Phase 1:** Registry additions (seven new entries). One commit. All tests still pass.
- **Phase 2:** `music-generation` task wiring in `ReplicateBackend`. Unit tests for the three Lyria variants' param translation.
- **Phase 3:** VEO routing in `ReplicateBackend` + VEO fixtures/tests. `video_generate.py` updated to route Vertex → Replicate. Deprecation warning on `--backend vertex-ai`.
- **Phase 4:** `audio_pipeline.py` Lyria migration. `detect_lyrics_intent()` + `resolve_lyria_version()` helpers. Unit tests.
- **Phase 5:** Delete `_vertex_backend.py`. Remove Vertex setup prompts from `setup_mcp.py`. Verify no remaining references.
- **Phase 6:** Documentation — model reference docs for VEO + Lyria family + ElevenLabs Music. Update `references/providers/replicate.md`. Update `CLAUDE.md` key constraints. Update `PROGRESS.md` Session 25. Update `ROADMAP.md` with music bake-off and multi-model principle.
- **Phase 7:** Version bump (4.2.0 → 4.2.1), CHANGELOG entry, README badge + release-history block, architecture diagram (small — mainly the deletion of `_vertex_backend.py`).
- **Phase 8:** Release merge + tag + push + GitHub release. Explicit user-approval gate per the `feedback_release_checkin` memory rule.

## 10. Open questions and known unknowns

- **Lyria 3 `reference_images` capability in canonical schema.** The existing `_base.py` doesn't define `reference_images` as a canonical param for `music-generation`. Plan needs to decide whether to extend the canonical schema or route `reference_images` through `provider_opts`. Lyria 3 / Pro accept up to 10 images; Lyria 2 doesn't support them.
- **Lyria 3 Pro duration control.** The model card says duration is "influenced by prompting" (not strictly controlled). Our canonical `duration_max_s: 180` is aspirational. If users need precise length, the bake-off will surface this.
- **Replicate Lyria `negative_prompt` behavior at different prompt lengths.** Lyria 2 accepts it, Lyria 3 / Pro don't. The orchestrator warning is sufficient for the default case, but an unknown is whether Lyria 3 silently incorporates negative-prompt text into the audio (hallucinating it as a topic) vs ignoring it. Plan verifies empirically.
- **ElevenLabs Music variant generation.** The ElevenLabs web app offers generating 1-4 variants from a single prompt in one call. API support is not confirmed in the public docs. When ElevenLabs is eventually refactored into `_elevenlabs.py` (future sub-project), investigate whether the API exposes this feature. If yes, register it as a canonical `count` parameter on the `music-generation` task. Not blocking for B.
- **VEO conditional constraint enforcement.** VEO 3.1 Lite's `1080p requires duration_s=8` rule is documented in the registry `canonical_constraints.conditional` field but not machine-enforced in B. Relying on Replicate's server-side rejection. If error rates are high post-launch, a future release adds a cross-field validator to `_canonical.py`.

## 11. Success criteria

This spec succeeds if, after v4.2.1 ships:

1. `skills/create-video/scripts/_vertex_backend.py` no longer exists.
2. `grep -rn "aiplatform.googleapis.com" skills/ scripts/` returns no matches (the inline Vertex URL in `audio_pipeline.py` is gone).
3. All 90+ tests pass.
4. `/create-video generate --prompt "..." --provider veo` produces a video (routing through Replicate) with zero user-visible behavior change compared to v4.2.0 Vertex routing.
5. `/create-video audio music --prompt "A mellow jazz track" --source lyria` produces a 30s Lyria 3 clip via Replicate. Auto-route did not trigger (no lyric indicators).
6. `/create-video audio music --prompt "[Verse 1] walking home tonight [Chorus] oh can't you see" --source lyria` produces a full song via Lyria 3 Pro. Auto-route logged the routing decision and cost bump.
7. `/create-video audio music --prompt "..." --source lyria --negative-prompt "drums"` produces a Lyria 2 clip (auto-selected because `negative_prompt` was set). The `negative_prompt` landed in the Replicate request body.
8. Existing v4.2.0 user with `vertex_api_key` in config can upgrade without changing any config; no errors, no forced re-setup.
9. Music bake-off queued in `ROADMAP.md` with 4 contenders and 2-part methodology documented.

## 12. Out of scope, deferred to later releases

- **v4.2.2 — `~/.banana/` → `~/.creators-studio/` config dir rename.** Queued in v4.2.0 release ROADMAP. Unrelated to B.
- **v4.3.0 — Sub-project C (Kie.ai backend + Suno).** Unblocks the music bake-off.
- **v4.3.x or later — Music bake-off execution + new default ratification.** Methodology and contenders locked in this spec; actual listening test is a separate session.
- **v4.4.0+ — Sub-project D (Hugging Face Inference Providers).** Same dependency graph as v4.2.0 established.
- **Future sub-project — ElevenLabs `_elevenlabs.py` ProviderBackend refactor.** Removes the `(direct)` sentinel slug from the registry entry. Unblocks running ElevenLabs-hosted workflows through the routing layer.
- **Future sub-project — Gemini direct `_gemini_direct.py` ProviderBackend refactor.** Same pattern.
