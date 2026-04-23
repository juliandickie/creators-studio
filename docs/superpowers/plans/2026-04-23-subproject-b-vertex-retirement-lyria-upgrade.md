# Sub-Project B: Vertex Retirement + Lyria 3 Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire Vertex AI entirely from the plugin (delete `_vertex_backend.py`, remove inline Vertex calls from `audio_pipeline.py`), route VEO 3.1 via Replicate's `ReplicateBackend`, upgrade Lyria 2 → Lyria 3 as the within-Lyria default while keeping Lyria 2 and registering Lyria 3 Pro.

**Architecture:** Apply the v4.2.0 provider abstraction to the two remaining Vertex surfaces. Extend `_TASK_PARAM_MAPS` with `music-generation`, add three new pricing modes to `cost_tracker.py`, extend `_canonical.py` with a `duration_s.enum` validator. No new backend file — all routing goes through the existing `ReplicateBackend`. Zero behavior change for users who never touched `--provider veo` or `--music-source lyria`.

**Spec:** [docs/superpowers/specs/2026-04-23-subproject-b-vertex-retirement-lyria-upgrade-design.md](../specs/2026-04-23-subproject-b-vertex-retirement-lyria-upgrade-design.md)

**Tech Stack:** Python 3.12+ stdlib only (matches v4.2.0 floor). Tests use stdlib `unittest`. No new runtime or test-time dependencies.

**Branch:** Work happens on `feature/vertex-retirement-v4.2.1`. Main stays at v4.2.0 until the whole sub-project B is complete + tested + released as v4.2.1.

---

## Context for engineer picking this up cold

The plugin is `creators-studio` at v4.2.0. The v4.2.0 release shipped the provider abstraction foundation: a `ProviderBackend` ABC in `scripts/backends/_base.py`, a `ReplicateBackend` class in `scripts/backends/_replicate.py`, a model registry at `scripts/registry/models.json`, and two-stage routing in `scripts/routing.py`. The Kling, Fabric, DreamActor, and Recraft Vectorize models already route through `ReplicateBackend`.

Two Vertex AI surfaces still exist:

1. **`skills/create-video/scripts/_vertex_backend.py`** (958 lines) — used by `video_generate.py` for VEO 3.1 Lite/Fast/Standard video generation. Imported as `import _vertex_backend as vertex`.

2. **Inline Vertex calls inside `skills/create-video/scripts/audio_pipeline.py`** — constructs `{location}-aiplatform.googleapis.com` URLs directly for Lyria 2 (`lyria-002`) music generation. Does NOT import `_vertex_backend.py`.

Both surfaces have confirmed Replicate equivalents:

- VEO 3.1 Lite/Fast/Standard → `google/veo-3.1-lite`, `google/veo-3.1-fast`, `google/veo-3.1`
- Lyria 2 → `google/lyria-2` (same capabilities + same 30s clip length as Vertex Lyria 2)
- Lyria 3 → `google/lyria-3` (NEW — 30s clips, adds `images` input, adds vocal generation, $0.04/file vs Lyria 2's $0.06)
- Lyria 3 Pro → `google/lyria-3-pro` (NEW capability — full-length songs up to 3 min with structure tags, custom lyrics, timestamp control, $0.08/file)

**Authoritative source docs** (read these during implementation; do not re-verify from scratch):
- `dev-docs/google-veo-3.1-lite-llms.md` — VEO Lite spec + pricing
- `dev-docs/google-veo-3.1-fast-llms.md` — VEO Fast spec + pricing
- `dev-docs/google-veo-3.1-llms.md` — VEO Standard spec + pricing
- `dev-docs/google-lyria-2-llms.md` — Lyria 2 spec
- `dev-docs/google-lyria-3-llms.md` — Lyria 3 spec
- `dev-docs/google-lyria-3-pro-llms.md` — Lyria 3 Pro spec
- `dev-docs/elevenlabs-music.md` — ElevenLabs Music capability reference
- `dev-docs/kwaivgi-kling-v3-video-llms.md` — Kling v3 Video (for pricing correction)
- `dev-docs/kwaivgi-kling-v3-omni-video-llms.md` — Kling v3 Omni (for pricing correction)

**Key plugin rules (carry forward from v4.2.0):**

1. **Stdlib-only for runtime scripts.** `urllib.request`, `json`, `base64` only.
2. **`~/.banana/` config directory is frozen.** Do not rename to `.creators-studio`.
3. **Python 3.12+ floor.** Use PEP 604 unions (`X | None`), built-in generics (`list[int]`), `dataclass(slots=True)`, `match`/`case`, PEP 695 `type` aliases.
4. **Every family must register ≥2 models** (v4.2.0 multi-model principle).
5. **Backend code never leaks provider-specific field names into the orchestrator** — translation stays inside the backend class.

---

## File structure — every file created, modified, or deleted

### New files

```
references/models/
  lyria-2.md                       — Lyria 2 capabilities + negative_prompt USP
  lyria-3.md                       — Lyria 3 Clip + image-input + cheaper
  lyria-3-pro.md                   — Full-song generation + structure tags
  elevenlabs-music.md              — ElevenLabs Music (vocals/lyrics/multilingual/finetunes)

tests/
  test_lyria_migration.py          — Lyria routing + version resolution tests
  fixtures/replicate_veo_submit.json
  fixtures/replicate_veo_poll_success.json
  fixtures/replicate_lyria_submit.json
  fixtures/replicate_lyria_poll_success.json
```

### Modified files

```
scripts/backends/
  _canonical.py                    — add duration_s.enum validator shape
  _replicate.py                    — extend _TASK_PARAM_MAPS + per-model param filtering

scripts/registry/
  models.json                      — 7 new entries + 2 pricing corrections + family_defaults update

skills/create-image/scripts/
  cost_tracker.py                  — add 3 new pricing modes
  setup_mcp.py                     — remove Vertex CLI surface

skills/create-video/scripts/
  video_generate.py                — remove Vertex import + deprecation warning
  audio_pipeline.py                — Lyria refactor + lyrics intent detector + flags

tests/
  test_canonical.py                — add duration_s.enum validator tests
  test_registry.py                 — add new entries + multi-model principle check
  test_replicate_backend.py        — add music-generation + VEO submit tests

references/models/
  veo-3.1.md                       — replace placeholder with real content

references/providers/
  replicate.md                     — add VEO + Lyria to hosted-models list + new pricing modes

Top-level docs:
  CLAUDE.md                        — multi-model principle + VEO-via-Replicate + Lyria auto-route rules
  PROGRESS.md                      — Session 25 entry
  ROADMAP.md                       — music bake-off + Kling-vs-VEO re-eval + motion-control registration
  CHANGELOG.md                     — v4.2.1 entry
  README.md                        — version badge + What's New entry + architecture diagram
  .claude-plugin/plugin.json       — version 4.2.0 → 4.2.1
  CITATION.cff                     — version + date-released
```

### Deleted files

```
skills/create-video/scripts/_vertex_backend.py     — 958 lines, superseded by Replicate routing
```

---

## Phase 0 — Pre-flight

### Task 0: Create feature branch

**Files:** (git metadata only)

- [ ] **Step 1: Create and switch to feature branch**

```bash
cd /Users/juliandickie/code/creators-studio-project/creators-studio
git checkout -b feature/vertex-retirement-v4.2.1
git status
```

Expected: `On branch feature/vertex-retirement-v4.2.1`, nothing to commit.

- [ ] **Step 2: Verify spec is reachable from new branch**

```bash
ls docs/superpowers/specs/2026-04-23-subproject-b-vertex-retirement-lyria-upgrade-design.md
```

Expected: file exists.

- [ ] **Step 3: Baseline test suite (must be 74 passing before any changes)**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: `Ran 74 tests in Xs, OK`. If not 74 or not passing, STOP and diagnose before making changes.

---

## Phase 1 — Canonical schema extension (`duration_s.enum`)

### Task 1: Add `duration_s.enum` validator shape

**Files:**
- Test: `tests/test_canonical.py` (extend)
- Modify: `scripts/backends/_canonical.py`

**Context:** VEO 3.1 accepts only specific duration values `{4, 6, 8}`, not a range. The current `_canonical.py` validator only handles `duration_s: {min, max, integer}`. This task adds support for `duration_s: {enum: [...]}` as an alternative shape. Kling / Fabric / DreamActor continue using `min/max/integer` — no change to them.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_canonical.py` inside the `TestValidateConstraints` class (after the existing `test_duration_out_of_range_raises` test):

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m unittest tests.test_canonical -v 2>&1 | tail -20
```

Expected: three new `test_duration_enum_*` tests fail (CanonicalValidationError not raised as expected, or value accepted incorrectly).

- [ ] **Step 3: Extend the validator**

In `scripts/backends/_canonical.py`, locate the duration_s validation block (should look like):

```python
    # duration_s
    if (c := constraints.get("duration_s")) is not None and "duration_s" in params:
        v = params["duration_s"]
        if c.get("integer") and not isinstance(v, int):
            raise CanonicalValidationError(
                f"duration_s must be an integer; got {type(v).__name__} ({v!r})"
            )
        if (lo := c.get("min")) is not None and v < lo:
            raise CanonicalValidationError(f"duration_s={v} is below minimum {lo}")
        if (hi := c.get("max")) is not None and v > hi:
            raise CanonicalValidationError(f"duration_s={v} exceeds maximum {hi}")
```

Replace the inner body with:

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python3 -m unittest tests.test_canonical -v 2>&1 | tail -30
```

Expected: all canonical tests pass (~25 now, up from 21).

- [ ] **Step 5: Run full test suite to verify no regressions**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: 78 tests pass (74 + 4 new).

- [ ] **Step 6: Commit**

```bash
git add scripts/backends/_canonical.py tests/test_canonical.py
git commit -m "feat: add duration_s.enum validator shape to _canonical.py

VEO 3.1 accepts only {4, 6, 8} seconds, not a range. Extend the
canonical validator to support {enum: [...]} as an alternative to
the existing {min, max, integer} shape. Kling / Fabric / DreamActor
keep using the range shape unchanged."
```

---

## Phase 2 — Cost tracker pricing modes

### Task 2: Explore `cost_tracker.py` structure

**Files:** (read-only — planning)

- [ ] **Step 1: Find the pricing dispatch function**

```bash
grep -nE "def _lookup_cost|PRICING\s*=|per_second|per_call" skills/create-image/scripts/cost_tracker.py | head -20
```

Expected output includes `def _lookup_cost(...)` and the `PRICING` dict constant. Note the line numbers.

- [ ] **Step 2: Read the existing `_lookup_cost` implementation**

Open the file at the `_lookup_cost` line. Read the function body. You'll see a dispatch pattern like:

```python
def _lookup_cost(family, model, resolution):
    entry = PRICING.get(model)
    if not entry:
        return None
    mode = entry.get("mode") or "by_resolution"  # (approximation)
    if mode == "per_second":
        ...
    elif mode == "per_call":
        ...
    elif mode == "per_clip":
        ...
    else:  # by_resolution
        ...
```

The dispatch is keyed on `mode`. To add three new modes (`per_second_by_resolution`, `per_second_by_audio`, `per_second_by_resolution_and_audio`), add three new `elif` branches.

Note: the existing `cost_tracker.py` may also use the model's PRICING dict rather than the registry JSON. The v4.2.1 changes do NOT need to unify these — `cost_tracker.py` can continue using its own PRICING dict, or it can be updated to read from the registry. For this task, we add to the PRICING dict AND keep the registry as the source of truth for the backend path. Future cleanup can unify them.

### Task 3: Add `per_second_by_resolution` pricing mode

**Files:**
- Modify: `skills/create-image/scripts/cost_tracker.py`
- Test: extend existing cost_tracker tests or add minimal inline assertions

**Context:** Used by VEO 3.1 Lite. Pricing shape:
```json
{"mode": "per_second_by_resolution", "rates": {"720p": 0.05, "1080p": 0.08}}
```

- [ ] **Step 1: Add PRICING entry for `veo-3.1-lite`**

Locate the `PRICING` dict constant in `cost_tracker.py`. Add an entry:

```python
    "veo-3.1-lite": {
        "mode": "per_second_by_resolution",
        "rates": {"720p": 0.05, "1080p": 0.08},
    },
```

- [ ] **Step 2: Add dispatch branch in `_lookup_cost`**

In the dispatch chain, add a new `elif` branch (before the fallback `else`):

```python
    elif mode == "per_second_by_resolution":
        # resolution param (e.g., "720p") keys the rate; duration_s from resolution
        # (callers pass duration as the "resolution" field in log call — the
        # caller must ALSO know the pixel resolution separately. For v4.2.1,
        # we accept a compound format like "720p@8s" OR two separate fields.)
        # Convention: for per_second_by_resolution, 'resolution' is the pixel
        # resolution and duration is passed as an extra arg.
        # This task adopts an extended signature: _lookup_cost(family, model,
        # resolution, duration_s=None, audio_enabled=None).
        rate_map = entry["rates"]
        if resolution not in rate_map:
            return None
        if duration_s is None:
            return None
        return Decimal(str(rate_map[resolution])) * Decimal(str(duration_s))
```

- [ ] **Step 3: Extend `_lookup_cost` signature**

Update the function signature to accept `duration_s` and `audio_enabled`:

```python
def _lookup_cost(
    family: str,
    model: str,
    resolution: str,
    *,
    duration_s: float | None = None,
    audio_enabled: bool | None = None,
) -> Decimal | None:
    ...
```

Every existing call site keeps working because the new params are keyword-only with defaults. The existing `per_second` (Kling v4.2.0 entry — will be corrected in Task 8) path that passes duration as `resolution="8s"` still works.

- [ ] **Step 4: Add sanity test**

Append to `tests/test_registry.py` (or create a new minimal test file `tests/test_cost_tracker.py`):

```python
import sys, unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "create-image" / "scripts"),
)

import cost_tracker


class TestCostTrackerPerSecondByResolution(unittest.TestCase):
    def test_veo_lite_720p_8s(self):
        # Lite 720p: $0.05/s × 8s = $0.40
        cost = cost_tracker._lookup_cost(
            "video", "veo-3.1-lite", "720p", duration_s=8
        )
        self.assertEqual(cost, Decimal("0.40"))

    def test_veo_lite_1080p_8s(self):
        # Lite 1080p: $0.08/s × 8s = $0.64
        cost = cost_tracker._lookup_cost(
            "video", "veo-3.1-lite", "1080p", duration_s=8
        )
        self.assertEqual(cost, Decimal("0.64"))

    def test_unknown_resolution_returns_none(self):
        cost = cost_tracker._lookup_cost(
            "video", "veo-3.1-lite", "4K", duration_s=8
        )
        self.assertIsNone(cost)
```

- [ ] **Step 5: Run tests**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: all pass (81 tests).

- [ ] **Step 6: Commit**

```bash
git add skills/create-image/scripts/cost_tracker.py tests/test_cost_tracker.py
git commit -m "feat: add per_second_by_resolution pricing mode (VEO Lite)

cost_tracker._lookup_cost signature extended with duration_s and
audio_enabled keyword-only args. Existing callers unchanged.

VEO 3.1 Lite: \$0.05/s at 720p, \$0.08/s at 1080p. 3 tests pass."
```

### Task 4: Add `per_second_by_audio` pricing mode

**Files:**
- Modify: `skills/create-image/scripts/cost_tracker.py`
- Test: `tests/test_cost_tracker.py`

**Context:** Used by VEO 3.1 Fast and Standard. Pricing shape:
```json
{"mode": "per_second_by_audio", "rates": {"with_audio": 0.15, "without_audio": 0.10}}
```

- [ ] **Step 1: Add PRICING entries**

```python
    "veo-3.1-fast": {
        "mode": "per_second_by_audio",
        "rates": {"with_audio": 0.15, "without_audio": 0.10},
    },
    "veo-3.1": {
        "mode": "per_second_by_audio",
        "rates": {"with_audio": 0.40, "without_audio": 0.20},
    },
```

- [ ] **Step 2: Add dispatch branch**

```python
    elif mode == "per_second_by_audio":
        if audio_enabled is None or duration_s is None:
            return None
        key = "with_audio" if audio_enabled else "without_audio"
        rate = entry["rates"].get(key)
        if rate is None:
            return None
        return Decimal(str(rate)) * Decimal(str(duration_s))
```

- [ ] **Step 3: Add tests**

```python
class TestCostTrackerPerSecondByAudio(unittest.TestCase):
    def test_veo_fast_with_audio_8s(self):
        cost = cost_tracker._lookup_cost(
            "video", "veo-3.1-fast", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, Decimal("1.20"))  # $0.15 × 8

    def test_veo_fast_without_audio_8s(self):
        cost = cost_tracker._lookup_cost(
            "video", "veo-3.1-fast", "1080p",
            duration_s=8, audio_enabled=False,
        )
        self.assertEqual(cost, Decimal("0.80"))  # $0.10 × 8

    def test_veo_standard_with_audio_8s(self):
        cost = cost_tracker._lookup_cost(
            "video", "veo-3.1", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, Decimal("3.20"))  # $0.40 × 8

    def test_missing_audio_flag_returns_none(self):
        cost = cost_tracker._lookup_cost(
            "video", "veo-3.1-fast", "1080p", duration_s=8,
        )
        self.assertIsNone(cost)
```

- [ ] **Step 4: Run tests**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: 85 tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/create-image/scripts/cost_tracker.py tests/test_cost_tracker.py
git commit -m "feat: add per_second_by_audio pricing mode (VEO Fast + Standard)

VEO 3.1 Fast: \$0.15/s with audio, \$0.10/s without.
VEO 3.1 Standard: \$0.40/s with audio, \$0.20/s without.
4 tests pass."
```

### Task 5: Add `per_second_by_resolution_and_audio` pricing mode + correct Kling pricing

**Files:**
- Modify: `skills/create-image/scripts/cost_tracker.py`
- Test: `tests/test_cost_tracker.py`

**Context:** Used by Kling v3 Video and Kling v3 Omni. Two-dimensional pricing (resolution outer, audio inner). Replaces the incorrect `$0.02/s` flat rate that was seeded in v4.2.0 from an outdated source. Corrected rates from `dev-docs/kwaivgi-kling-v3-video-llms.md` and `dev-docs/kwaivgi-kling-v3-omni-video-llms.md`.

- [ ] **Step 1: Replace the old Kling PRICING entries**

Locate and DELETE the existing Kling entries in `PRICING` (likely `"kling-v3"` with `per_second` rate `0.02`, plus any `kwaivgi/kling-v3-video` alias). Replace with:

```python
    "kling-v3": {
        "mode": "per_second_by_resolution_and_audio",
        "rates": {
            "720p":  {"with_audio": 0.252, "without_audio": 0.168},
            "1080p": {"with_audio": 0.336, "without_audio": 0.224},
        },
    },
    "kling-v3-omni": {
        "mode": "per_second_by_resolution_and_audio",
        "rates": {
            "720p":  {"with_audio": 0.224, "without_audio": 0.168},
            "1080p": {"with_audio": 0.28,  "without_audio": 0.224},
        },
    },
```

- [ ] **Step 2: Add dispatch branch**

```python
    elif mode == "per_second_by_resolution_and_audio":
        if resolution is None or audio_enabled is None or duration_s is None:
            return None
        res_block = entry["rates"].get(resolution)
        if res_block is None:
            return None
        key = "with_audio" if audio_enabled else "without_audio"
        rate = res_block.get(key)
        if rate is None:
            return None
        return Decimal(str(rate)) * Decimal(str(duration_s))
```

- [ ] **Step 3: Add tests**

```python
class TestCostTrackerPerSecondByResolutionAndAudio(unittest.TestCase):
    def test_kling_v3_pro_audio_8s(self):
        # 1080p with audio: $0.336/s × 8s = $2.688
        cost = cost_tracker._lookup_cost(
            "video", "kling-v3", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, Decimal("2.688"))

    def test_kling_v3_standard_no_audio_8s(self):
        # 720p without audio: $0.168/s × 8s = $1.344
        cost = cost_tracker._lookup_cost(
            "video", "kling-v3", "720p",
            duration_s=8, audio_enabled=False,
        )
        self.assertEqual(cost, Decimal("1.344"))

    def test_kling_v3_omni_differs_from_v3_on_audio(self):
        # Omni pro-audio: $0.28 × 8 = $2.24 (cheaper than v3's $2.688)
        cost = cost_tracker._lookup_cost(
            "video", "kling-v3-omni", "1080p",
            duration_s=8, audio_enabled=True,
        )
        self.assertEqual(cost, Decimal("2.24"))

    def test_missing_fields_returns_none(self):
        # All three of resolution, audio_enabled, duration_s required
        cost = cost_tracker._lookup_cost(
            "video", "kling-v3", "1080p", duration_s=8,
        )
        self.assertIsNone(cost)
```

- [ ] **Step 4: Update callers that log Kling costs**

Find every call to `cost_tracker._lookup_cost` or the equivalent logging function that passes a Kling model. These were passing `resolution="8s"` (duration as the resolution field) under the old `per_second` mode. They now need to pass both `resolution="720p"|"1080p"` AND `duration_s=...` AND `audio_enabled=...`.

```bash
grep -rn "cost_tracker\|_lookup_cost\|log_cost" skills/create-video/scripts/ --include="*.py" | grep -iE "kling|replicate"
```

For each match, update the call to include the new kwargs. Example pattern in `video_generate.py`:

```python
# OLD (wrong — resolution was passed as "8s" abusing the resolution field)
subprocess.run([
    "python3", cost_tracker_path, "log",
    "--family", "video",
    "--model", "kling-v3",
    "--resolution", f"{duration}s",
], ...)

# NEW (correct — resolution is pixel res, duration and audio passed separately)
subprocess.run([
    "python3", cost_tracker_path, "log",
    "--family", "video",
    "--model", "kling-v3",
    "--resolution", resolution_str,          # "720p" or "1080p"
    "--duration-s", str(duration),
    "--audio-enabled", "true" if generate_audio else "false",
], ...)
```

The `cost_tracker.py log` CLI subcommand also needs to accept the new flags. Locate the argparse block in `cost_tracker.py` (search for `add_argument.*resolution`) and add:

```python
    log_parser.add_argument("--duration-s", type=float, default=None)
    log_parser.add_argument("--audio-enabled", choices=["true", "false"], default=None)
```

In the log subcommand handler, parse and pass:

```python
    duration_s = args.duration_s
    audio_enabled = None
    if args.audio_enabled is not None:
        audio_enabled = (args.audio_enabled == "true")
    cost = _lookup_cost(
        args.family, args.model, args.resolution,
        duration_s=duration_s, audio_enabled=audio_enabled,
    )
```

- [ ] **Step 5: Run tests**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: 89 tests pass.

- [ ] **Step 6: Smoke test cost_tracker CLI**

```bash
python3 skills/create-image/scripts/cost_tracker.py log \
    --family video --model kling-v3 --resolution 1080p \
    --duration-s 8 --audio-enabled true \
    --dry-run 2>&1 | head -5
```

(If `--dry-run` doesn't exist, just check the command doesn't crash; a real log write is fine in dev.)

Expected: cost computed as `$2.688`, written or printed.

- [ ] **Step 7: Commit**

```bash
git add skills/create-image/scripts/cost_tracker.py tests/test_cost_tracker.py skills/create-video/scripts/
git commit -m "feat: add per_second_by_resolution_and_audio mode + correct Kling pricing

v4.2.0 seeded Kling v3 in the PRICING dict with '{mode: per_second,
rate: 0.02}' — incorrect; the actual Replicate rate is 10-17x higher.
Corrected from dev-docs model cards:

  Kling v3 Video:
    720p no-audio:    \$0.168/s
    720p with-audio:  \$0.252/s
    1080p no-audio:   \$0.224/s
    1080p with-audio: \$0.336/s

  Kling v3 Omni (cheaper on audio):
    720p no-audio:    \$0.168/s
    720p with-audio:  \$0.224/s
    1080p no-audio:   \$0.224/s
    1080p with-audio: \$0.28/s

New pricing mode per_second_by_resolution_and_audio handles both
models. cost_tracker.py log subcommand extended with --duration-s and
--audio-enabled flags. Callers in video_generate.py updated to pass
pixel resolution + duration + audio flag separately instead of
encoding duration as the resolution field.

4 tests pass. Total: 89."
```

---

## Phase 3 — Registry expansion (models.json)

### Task 6: Add VEO 3.1 entries to registry

**Files:**
- Modify: `scripts/registry/models.json`

**Context:** Add three VEO entries to `models.models`. The registry's `canonical_constraints` block uses the new `duration_s: {enum: [...]}` shape from Task 1.

- [ ] **Step 1: Open `scripts/registry/models.json` and locate the `models` block**

The file has shape:
```json
{
  "version": 1,
  "family_defaults": {...},
  "models": {
    "kling-v3": {...},
    ...
  }
}
```

- [ ] **Step 2: Add three VEO entries to `models`**

Add after the `kling-v3-omni` entry:

```json
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
          "notes": "Cheapest VEO tier. Audio always on (no without_audio variant). No reference images, no video extension. 1080p requires exactly 8s duration. Kling v3 wins quality per v3.8.0 spike 5 but VEO Lite is ~4x CHEAPER per clip at 1080p."
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
          "notes": "Mid-tier VEO, optimized for generation speed. Up to 3 reference images. Opt-in backup via --provider replicate --model veo-3.1-fast."
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
          "capabilities": ["audio_generation", "audio_toggle", "reference_images", "last_frame", "video_extension", "4k_output"],
          "pricing": {
            "mode": "per_second_by_audio",
            "rates": {"with_audio": 0.40, "without_audio": 0.20},
            "currency": "USD"
          },
          "availability": "GA",
          "notes": "Highest-fidelity VEO. Only tier with 4K + video extension. Most expensive in the roster at $0.40/s with audio — use Kling v3 or VEO Lite for cost-sensitive workflows."
        }
      }
    },
```

- [ ] **Step 3: Validate JSON**

```bash
python3 -m json.tool scripts/registry/models.json > /dev/null && echo "valid"
```

Expected: `valid`.

- [ ] **Step 4: Run registry tests to verify load still works**

```bash
python3 -m unittest tests.test_registry -v 2>&1 | tail -5
```

Expected: all existing registry tests still pass.

### Task 7: Add Lyria + ElevenLabs Music entries

**Files:**
- Modify: `scripts/registry/models.json`

- [ ] **Step 1: Add four music-family entries after the VEO entries**

```json
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
          "notes": "Kept registered despite Lyria 3 default — uniquely supports negative_prompt exclusion. Auto-selected when --negative-prompt is set."
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
          "notes": "Auto-selected within Lyria family when prompt contains song structure tags / timestamps / explicit lyrics. Requires --confirm-upgrade when auto-routed (2x cost of Clip)."
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
          "notes": "Not yet refactored into ProviderBackend — audio_pipeline.py calls ElevenLabs directly. Registered so family_defaults.music is honest and the multi-model principle is upheld."
        }
      }
    }
```

### Task 8: Correct Kling v3 + v3 Omni registry pricing

**Files:**
- Modify: `scripts/registry/models.json`

- [ ] **Step 1: Update the existing `kling-v3` entry's `pricing` block**

Locate the existing `kling-v3` → `providers.replicate.pricing` block:

```json
        "pricing": {"mode": "per_second", "rate": 0.02, "currency": "USD"},
```

Replace with:

```json
        "pricing": {
          "mode": "per_second_by_resolution_and_audio",
          "rates": {
            "720p":  {"with_audio": 0.252, "without_audio": 0.168},
            "1080p": {"with_audio": 0.336, "without_audio": 0.224}
          },
          "currency": "USD"
        },
```

- [ ] **Step 2: Update the existing `kling-v3-omni` entry's `pricing` block**

Same location pattern on `kling-v3-omni`. Replace with:

```json
        "pricing": {
          "mode": "per_second_by_resolution_and_audio",
          "rates": {
            "720p":  {"with_audio": 0.224, "without_audio": 0.168},
            "1080p": {"with_audio": 0.28,  "without_audio": 0.224}
          },
          "currency": "USD"
        },
```

### Task 9: Update `family_defaults` and add music default

**Files:**
- Modify: `scripts/registry/models.json`

- [ ] **Step 1: Update `family_defaults` block**

Locate:

```json
  "family_defaults": {
    "image": "nano-banana-2",
    "video": "kling-v3"
  },
```

Replace with:

```json
  "family_defaults": {
    "image": "nano-banana-2",
    "video": "kling-v3",
    "music": "elevenlabs-music"
  },
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -m json.tool scripts/registry/models.json > /dev/null && echo "valid"
```

Expected: `valid`.

### Task 10: Write registry tests for new entries + multi-model principle

**Files:**
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_registry.py` a new class:

```python
class TestV42SubprojectBEntries(unittest.TestCase):
    """Verify sub-project B registry additions."""

    def setUp(self):
        self.r = reg.load_registry()

    def test_veo_3_1_tiers_registered(self):
        for mid in ("veo-3.1-lite", "veo-3.1-fast", "veo-3.1"):
            self.assertIn(mid, self.r.models, f"{mid} missing from registry")
            m = self.r.models[mid]
            self.assertEqual(m.family, "video")
            self.assertIn("replicate", m.providers)

    def test_veo_lite_uses_per_second_by_resolution(self):
        m = self.r.get_model("veo-3.1-lite")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_resolution")
        self.assertEqual(pricing["rates"]["720p"], 0.05)
        self.assertEqual(pricing["rates"]["1080p"], 0.08)

    def test_veo_fast_uses_per_second_by_audio(self):
        m = self.r.get_model("veo-3.1-fast")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_audio")
        self.assertEqual(pricing["rates"]["with_audio"], 0.15)
        self.assertEqual(pricing["rates"]["without_audio"], 0.10)

    def test_veo_standard_4k_in_resolutions(self):
        m = self.r.get_model("veo-3.1")
        self.assertIn("4K", m.canonical_constraints["resolutions"])

    def test_veo_lite_duration_is_enum(self):
        m = self.r.get_model("veo-3.1-lite")
        self.assertEqual(m.canonical_constraints["duration_s"], {"enum": [4, 6, 8]})

    def test_lyria_family_has_three_models(self):
        music_models = self.r.models_by_family("music")
        for mid in ("lyria-2", "lyria-3", "lyria-3-pro"):
            self.assertIn(mid, music_models, f"{mid} missing")

    def test_lyria_2_supports_negative_prompt(self):
        m = self.r.get_model("lyria-2")
        caps = m.providers["replicate"]["capabilities"]
        self.assertIn("negative_prompt", caps)

    def test_lyria_3_supports_reference_images(self):
        m = self.r.get_model("lyria-3")
        caps = m.providers["replicate"]["capabilities"]
        self.assertIn("reference_images", caps)

    def test_lyria_3_pro_supports_custom_lyrics(self):
        m = self.r.get_model("lyria-3-pro")
        caps = m.providers["replicate"]["capabilities"]
        self.assertIn("custom_lyrics", caps)

    def test_family_defaults_music_is_elevenlabs(self):
        self.assertEqual(self.r.family_default("music"), "elevenlabs-music")

    def test_elevenlabs_music_registered_with_direct_sentinel(self):
        m = self.r.get_model("elevenlabs-music")
        self.assertEqual(m.providers["elevenlabs"]["slug"], "(direct)")

    def test_kling_v3_pricing_corrected(self):
        m = self.r.get_model("kling-v3")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_resolution_and_audio")
        self.assertEqual(pricing["rates"]["1080p"]["with_audio"], 0.336)

    def test_kling_v3_omni_pricing_corrected(self):
        m = self.r.get_model("kling-v3-omni")
        pricing = m.providers["replicate"]["pricing"]
        self.assertEqual(pricing["mode"], "per_second_by_resolution_and_audio")
        self.assertEqual(pricing["rates"]["1080p"]["with_audio"], 0.28)

    def test_registry_validates(self):
        # family_defaults now points at elevenlabs-music which IS registered.
        self.r.validate()  # Should not raise


class TestMultiModelPrinciple(unittest.TestCase):
    """v4.2.1+: every family must register at least 2 models."""

    def setUp(self):
        self.r = reg.load_registry()

    def test_video_family_has_multiple_models(self):
        vs = self.r.models_by_family("video")
        self.assertGreaterEqual(len(vs), 2, f"video has only {vs}")

    def test_music_family_has_multiple_models(self):
        ms = self.r.models_by_family("music")
        self.assertGreaterEqual(len(ms), 2, f"music has only {ms}")
        # Expect 4: lyria-2, lyria-3, lyria-3-pro, elevenlabs-music
        self.assertGreaterEqual(len(ms), 4)

    def test_image_family_single_is_flagged_but_allowed(self):
        # v4.2.1 image family has nano-banana-2 + recraft-vectorize.
        # Recraft is a different task (vectorize), so text-to-image is
        # still single-model until sub-project C adds Kie.ai Imagen /
        # Seedream / Flux. This test documents the state; do NOT fail
        # because multi-model within-task coverage is a sub-project-C
        # commitment, not sub-project-B.
        text_to_image_models = [
            mid for mid in self.r.models_by_family("image")
            if "text-to-image" in self.r.models[mid].tasks
        ]
        self.assertGreaterEqual(len(text_to_image_models), 1)
```

- [ ] **Step 2: Run tests**

```bash
python3 -m unittest tests.test_registry -v 2>&1 | tail -20
```

Expected: all existing tests pass + 16 new tests pass (total ~27 in test_registry.py).

- [ ] **Step 3: Run full suite**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: 102+ tests pass.

- [ ] **Step 4: Commit Phase 3**

```bash
git add scripts/registry/models.json tests/test_registry.py
git commit -m "feat: register VEO 3.1 (x3), Lyria (x3), ElevenLabs Music + correct Kling pricing

Seven new registry entries in scripts/registry/models.json:
- veo-3.1-lite, veo-3.1-fast, veo-3.1 (video family, Replicate)
- lyria-2, lyria-3, lyria-3-pro (music family, Replicate)
- elevenlabs-music (music family, (direct) sentinel slug)

Corrections to existing entries:
- kling-v3 pricing: per_second 0.02 -> per_second_by_resolution_and_audio
  (correct rates from dev-docs/kwaivgi-kling-v3-video-llms.md)
- kling-v3-omni pricing: same mode, different rate table (cheaper on audio)

family_defaults adds music -> elevenlabs-music (matches v3.8.3 bake-off
verdict; ElevenLabs uses (direct) sentinel slug until refactored into
ProviderBackend in a future sub-project).

16 new registry tests + multi-model principle assertions. 102 tests total."
```

---

## Phase 4 — ReplicateBackend extensions (music-generation + VEO)

### Task 11: Add `music-generation` task to `_TASK_PARAM_MAPS`

**Files:**
- Modify: `scripts/backends/_replicate.py`

**Context:** The v4.2.0 `_TASK_PARAM_MAPS` has 4 entries: text-to-video, image-to-video, lipsync, vectorize. Adding music-generation lets `ReplicateBackend.submit()` handle the three Lyria models. Per-model quirks (Lyria 2 has negative_prompt, Lyria 3/3-Pro have images, neither Lyria 3 variant has negative_prompt) are handled via post-translation filtering.

- [ ] **Step 1: Find `_TASK_PARAM_MAPS` in `scripts/backends/_replicate.py`**

```bash
grep -n "_TASK_PARAM_MAPS" scripts/backends/_replicate.py | head -3
```

Locate the dict definition. You'll see entries for "text-to-video", "image-to-video", "lipsync", "vectorize".

- [ ] **Step 2: Add the music-generation entry**

Inside the `_TASK_PARAM_MAPS` dict, add:

```python
    "music-generation": {
        "prompt": "prompt",
        "negative_prompt": "negative_prompt",  # Lyria 2 only; filtered per-model below
        "reference_images": "images",          # Lyria 3 / 3 Pro only; filtered per-model
        "seed": "seed",                         # Lyria 2 only; filtered per-model
    },
```

- [ ] **Step 3: Extend `supported_tasks`**

Find the `ReplicateBackend.supported_tasks` class attribute. Add `"music-generation"`:

```python
    supported_tasks = {
        "text-to-image",
        "image-to-image",
        "text-to-video",
        "image-to-video",
        "lipsync",
        "vectorize",
        "music-generation",
    }
```

### Task 12: Add per-model param filtering

**Files:**
- Modify: `scripts/backends/_replicate.py`

**Context:** Some canonical params don't apply to every model that uses a given task. Lyria 3 doesn't accept `negative_prompt`; Lyria 2 doesn't accept `reference_images`. The backend filters these out silently with a WARN log when inappropriate.

- [ ] **Step 1: Add filter table + filter function**

Near `_TASK_PARAM_MAPS` in `_replicate.py`, add:

```python
# Per-model param drops: when the canonical request uses a param that the
# specific model doesn't support, silently filter it out and log a WARN.
# Structure: model_slug -> set of canonical_param names to drop.
_MODEL_PARAM_DROPS: dict[str, set[str]] = {
    # Lyria 3 + Pro accept prompt + images but NOT negative_prompt or seed.
    "google/lyria-3": {"negative_prompt", "seed"},
    "google/lyria-3-pro": {"negative_prompt", "seed"},
    # Lyria 2 accepts prompt + negative_prompt + seed but NOT images.
    "google/lyria-2": {"reference_images"},
}


def _filter_unsupported_params(
    model_slug: str, canonical_params: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Remove params the model doesn't support. Returns (filtered, dropped_keys).

    Callers can use dropped_keys to log a WARN explaining what was silently
    removed. Empty list if nothing was dropped.
    """
    drops = _MODEL_PARAM_DROPS.get(model_slug, set())
    filtered = {k: v for k, v in canonical_params.items() if k not in drops}
    dropped = sorted(k for k in canonical_params if k in drops)
    return filtered, dropped
```

- [ ] **Step 2: Wire the filter into `submit()`**

Find the `submit()` method. Near the top, after extracting canonical_params from arguments, add filtering:

```python
    def submit(
        self,
        *,
        task: str,
        model_slug: str,
        canonical_params: dict[str, Any],
        provider_opts: dict[str, Any],
        config: dict[str, Any],
    ) -> JobRef:
        api_key = self._api_key(config)

        if task not in _TASK_PARAM_MAPS:
            raise ProviderValidationError(
                f"Replicate backend does not handle task {task!r}. "
                f"Supported: {sorted(_TASK_PARAM_MAPS.keys())}"
            )

        # v4.2.1: filter out canonical params the specific model doesn't support,
        # logging a WARN. This lets callers pass a rich canonical payload
        # without knowing every model's exact surface.
        canonical_params, dropped = _filter_unsupported_params(model_slug, canonical_params)
        if dropped:
            _logger.warning(
                "Dropped unsupported params for %s: %s (these canonical params "
                "are not accepted by this model and were silently removed)",
                model_slug, dropped,
            )

        # ... existing translation logic follows
```

(`_logger` is already imported / defined in `_replicate.py`; the existing helpers use it.)

### Task 13: Write music-generation fixtures + tests

**Files:**
- Create: `tests/fixtures/replicate_lyria_submit.json`
- Create: `tests/fixtures/replicate_lyria_poll_success.json`
- Modify: `tests/test_replicate_backend.py`

- [ ] **Step 1: Create fixtures**

Write `tests/fixtures/replicate_lyria_submit.json`:

```json
{
  "id": "lyriaabc123",
  "model": "google/lyria-3",
  "input": {
    "prompt": "A mellow jazz track with saxophone"
  },
  "status": "starting",
  "created_at": "2026-04-23T15:00:00.000Z",
  "urls": {
    "cancel": "https://api.replicate.com/v1/predictions/lyriaabc123/cancel",
    "get": "https://api.replicate.com/v1/predictions/lyriaabc123"
  }
}
```

Write `tests/fixtures/replicate_lyria_poll_success.json`:

```json
{
  "id": "lyriaabc123",
  "status": "succeeded",
  "output": "https://replicate.delivery/xezq/lyria_output.mp3",
  "error": null,
  "created_at": "2026-04-23T15:00:00.000Z",
  "completed_at": "2026-04-23T15:00:45.000Z",
  "urls": {
    "cancel": "https://api.replicate.com/v1/predictions/lyriaabc123/cancel",
    "get": "https://api.replicate.com/v1/predictions/lyriaabc123"
  }
}
```

- [ ] **Step 2: Add music-generation tests to `test_replicate_backend.py`**

Append new test class to `tests/test_replicate_backend.py`:

```python
class TestMusicGenerationSubmit(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_3_translates_prompt(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        job_ref = self.backend.submit(
            task="music-generation",
            model_slug="google/lyria-3",
            canonical_params={"prompt": "jazz saxophone track"},
            provider_opts={},
            config=self.config,
        )
        self.assertEqual(job_ref.provider, "replicate")
        self.assertEqual(job_ref.external_id, "lyriaabc123")

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["prompt"], "jazz saxophone track")

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_2_preserves_negative_prompt(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="music-generation",
            model_slug="google/lyria-2",
            canonical_params={"prompt": "jazz", "negative_prompt": "drums"},
            provider_opts={},
            config=self.config,
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["prompt"], "jazz")
        self.assertEqual(body["input"]["negative_prompt"], "drums")

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_3_drops_negative_prompt_with_warning(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        with self.assertLogs("scripts.backends._replicate", level="WARNING") as ctx:
            self.backend.submit(
                task="music-generation",
                model_slug="google/lyria-3",
                canonical_params={"prompt": "jazz", "negative_prompt": "drums"},
                provider_opts={},
                config=self.config,
            )
        self.assertTrue(
            any("negative_prompt" in msg for msg in ctx.output),
            f"Expected WARN about negative_prompt drop; got: {ctx.output}",
        )

        # Verify it wasn't actually sent
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("negative_prompt", body["input"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_3_accepts_reference_images(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="music-generation",
            model_slug="google/lyria-3",
            canonical_params={
                "prompt": "jazz with visuals",
                "reference_images": ["data:image/png;base64,iVBO..."],
            },
            provider_opts={},
            config=self.config,
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        # canonical 'reference_images' -> provider 'images'
        self.assertIn("images", body["input"])

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_lyria_2_drops_reference_images_with_warning(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_lyria_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        with self.assertLogs("scripts.backends._replicate", level="WARNING") as ctx:
            self.backend.submit(
                task="music-generation",
                model_slug="google/lyria-2",
                canonical_params={
                    "prompt": "jazz with visuals",
                    "reference_images": ["data:image/png;base64,iVBO..."],
                },
                provider_opts={},
                config=self.config,
            )
        self.assertTrue(
            any("reference_images" in msg for msg in ctx.output),
            f"Expected WARN about reference_images drop; got: {ctx.output}",
        )
```

- [ ] **Step 3: Run tests**

```bash
python3 -m unittest tests.test_replicate_backend -v 2>&1 | tail -15
```

Expected: 5 new tests pass (total ~18 in test_replicate_backend.py).

- [ ] **Step 4: Commit**

```bash
git add scripts/backends/_replicate.py tests/test_replicate_backend.py tests/fixtures/replicate_lyria_*.json
git commit -m "feat: add music-generation task + per-model param filtering to ReplicateBackend

_TASK_PARAM_MAPS gains 'music-generation' with canonical params:
- prompt (all 3 Lyria variants)
- negative_prompt (Lyria 2 only; filtered with WARN for Lyria 3/Pro)
- reference_images -> 'images' (Lyria 3/Pro only; filtered with WARN for Lyria 2)
- seed (Lyria 2 only; filtered for Lyria 3/Pro)

New _MODEL_PARAM_DROPS table drives silent filtering: canonical request
can carry all params; submit() removes unsupported ones and logs a WARN.

5 new tests. Total ~107."
```

### Task 14: Write VEO fixtures + tests

**Files:**
- Create: `tests/fixtures/replicate_veo_submit.json`
- Create: `tests/fixtures/replicate_veo_poll_success.json`
- Modify: `tests/test_replicate_backend.py`

- [ ] **Step 1: Create fixtures**

Write `tests/fixtures/replicate_veo_submit.json`:

```json
{
  "id": "veoxyz789",
  "model": "google/veo-3.1-fast",
  "input": {
    "prompt": "A cinematic drone shot of a lighthouse at sunset",
    "duration": 8,
    "resolution": "720p",
    "aspect_ratio": "16:9"
  },
  "status": "starting",
  "created_at": "2026-04-23T15:00:00.000Z",
  "urls": {
    "cancel": "https://api.replicate.com/v1/predictions/veoxyz789/cancel",
    "get": "https://api.replicate.com/v1/predictions/veoxyz789"
  }
}
```

Write `tests/fixtures/replicate_veo_poll_success.json`:

```json
{
  "id": "veoxyz789",
  "status": "succeeded",
  "output": "https://replicate.delivery/xezq/veo_output.mp4",
  "error": null,
  "created_at": "2026-04-23T15:00:00.000Z",
  "completed_at": "2026-04-23T15:03:30.000Z",
  "metrics": {
    "predict_time": 210.0,
    "video_output_duration_seconds": 8.0
  },
  "urls": {
    "cancel": "https://api.replicate.com/v1/predictions/veoxyz789/cancel",
    "get": "https://api.replicate.com/v1/predictions/veoxyz789"
  }
}
```

- [ ] **Step 2: Add VEO submit tests**

Append to `test_replicate_backend.py`:

```python
class TestVEOSubmit(unittest.TestCase):
    def setUp(self):
        self.backend = _replicate.ReplicateBackend()
        self.config = {"providers": {"replicate": {"api_key": "r8_test"}}}

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_veo_text_to_video_translates_params(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_veo_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        job_ref = self.backend.submit(
            task="text-to-video",
            model_slug="google/veo-3.1-fast",
            canonical_params={
                "prompt": "A cinematic drone shot of a lighthouse at sunset",
                "duration_s": 8,
                "aspect_ratio": "16:9",
                "resolution": "720p",
            },
            provider_opts={},
            config=self.config,
        )
        self.assertEqual(job_ref.external_id, "veoxyz789")

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["input"]["duration"], 8)
        self.assertEqual(body["input"]["aspect_ratio"], "16:9")
        # For non-Kling models, resolution is passed through as-is (VEO accepts "720p" / "1080p")
        # Kling-specific resolution->mode translation only applies when slug starts with kwaivgi/kling-*

    @patch("scripts.backends._replicate.urllib.request.urlopen")
    def test_submit_veo_image_to_video(self, mock_urlopen):
        with open(str(FIXTURES / "replicate_veo_submit.json")) as f:
            mock_urlopen.return_value = _fake_urlopen_response(json.load(f), 201)

        self.backend.submit(
            task="image-to-video",
            model_slug="google/veo-3.1-fast",
            canonical_params={
                "prompt": "Animate this scene with gentle movement",
                "start_image": "https://example.com/input.jpg",
                "duration_s": 8,
                "aspect_ratio": "16:9",
            },
            provider_opts={},
            config=self.config,
        )

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        # VEO model card uses 'image' for image-to-video input — canonical
        # start_image might translate to 'image' for VEO but 'start_image'
        # for Kling. This test captures current behavior; adjust the
        # _TASK_PARAM_MAPS or add a per-model translator if VEO rejects.
        # For now: start_image passes through as 'start_image' (both work
        # on Replicate VEO per the model card's example using 'image' —
        # verify empirically in Phase 8 smoke test).
        self.assertIn("start_image", body["input"])
```

**Note to the engineer executing this plan:** if the smoke test in Phase 8 reveals that VEO on Replicate expects `image` rather than `start_image` for image-to-video, add a per-model field rename to the backend's translation step. Add that branch similar to the Kling resolution→mode translation:

```python
if model_slug.startswith("google/veo-3.1") and "start_image" in input_body:
    input_body["image"] = input_body.pop("start_image")
```

Document this in the VEO reference doc when you write it in Phase 9.

- [ ] **Step 3: Run tests**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: 109 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/replicate_veo_*.json tests/test_replicate_backend.py
git commit -m "test: add VEO submit fixtures + translation tests

Two test cases cover text-to-video and image-to-video canonical
translation for google/veo-3.1-fast. Existing _TASK_PARAM_MAPS
entries for 'text-to-video' and 'image-to-video' already handle
VEO without modification — the Kling-specific resolution->mode
translation only triggers on kwaivgi/kling-* slugs.

Flagged for Phase 8 smoke test: verify VEO accepts 'start_image'
or requires rename to 'image'. Add per-model rename if needed."
```

---

## Phase 5 — audio_pipeline.py Lyria migration

This phase is the biggest single refactor in sub-project B. It touches `audio_pipeline.py` in three places: (1) add the lyrics intent detector, (2) add the version resolver, (3) replace the Vertex call paths with ReplicateBackend calls.

### Task 15: Add `LyriaUpgradeGateError` + `detect_lyrics_intent` helpers

**Files:**
- Modify: `skills/create-video/scripts/audio_pipeline.py`
- Create: `tests/test_lyria_migration.py`

- [ ] **Step 1: Write the failing tests**

Write `tests/test_lyria_migration.py`:

```python
"""Tests for v4.2.1 Lyria migration in audio_pipeline.py:
- detect_lyrics_intent pattern matching
- resolve_lyria_version routing with --confirm-upgrade gate
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "create-video" / "scripts"),
)

import audio_pipeline


class TestDetectLyricsIntent(unittest.TestCase):
    def test_verse_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Verse] a song"))

    def test_chorus_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Chorus] sing along"))

    def test_bridge_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Bridge] middle 8"))

    def test_hook_tag_detected(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[Hook] catchy line"))

    def test_timestamp_detected(self):
        self.assertTrue(
            audio_pipeline.detect_lyrics_intent("[0:00 - 0:30] intro music"),
        )

    def test_plain_prompt_not_detected(self):
        self.assertFalse(
            audio_pipeline.detect_lyrics_intent("a jazz track with saxophone"),
        )

    def test_instrumental_only_overrides_verse_tag(self):
        # Explicit "instrumental only" should veto even if structure tags present
        self.assertFalse(
            audio_pipeline.detect_lyrics_intent(
                "instrumental only: [Verse] style arrangement"
            ),
        )

    def test_no_vocals_overrides(self):
        self.assertFalse(
            audio_pipeline.detect_lyrics_intent("[Verse] tag but no vocals"),
        )

    def test_case_insensitive(self):
        self.assertTrue(audio_pipeline.detect_lyrics_intent("[VERSE 1] caps"))


class TestResolveLyriaVersion(unittest.TestCase):
    def test_explicit_version_2_wins(self):
        result = audio_pipeline.resolve_lyria_version(
            "[Verse] lyrics here",
            explicit_version="2",
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-2")

    def test_explicit_version_3_wins_over_detection(self):
        # User explicitly picks Clip even though prompt triggers detection
        result = audio_pipeline.resolve_lyria_version(
            "[Verse] song structure",
            explicit_version="3",
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3")

    def test_explicit_version_3_pro_wins(self):
        result = audio_pipeline.resolve_lyria_version(
            "plain prompt",
            explicit_version="3-pro",
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3-pro")

    def test_negative_prompt_auto_routes_lyria_2(self):
        # Only Lyria 2 supports negative_prompt
        result = audio_pipeline.resolve_lyria_version(
            "jazz track",
            explicit_version=None,
            confirm_upgrade=False,
            has_negative_prompt=True,
        )
        self.assertEqual(result, "lyria-2")

    def test_plain_prompt_defaults_lyria_3(self):
        result = audio_pipeline.resolve_lyria_version(
            "a mellow jazz track",
            explicit_version=None,
            confirm_upgrade=False,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3")

    def test_lyrics_detected_without_confirm_raises(self):
        with self.assertRaises(audio_pipeline.LyriaUpgradeGateError):
            audio_pipeline.resolve_lyria_version(
                "[Verse] walking home",
                explicit_version=None,
                confirm_upgrade=False,
                has_negative_prompt=False,
            )

    def test_lyrics_detected_with_confirm_routes_to_pro(self):
        result = audio_pipeline.resolve_lyria_version(
            "[Verse] walking home",
            explicit_version=None,
            confirm_upgrade=True,
            has_negative_prompt=False,
        )
        self.assertEqual(result, "lyria-3-pro")

    def test_error_message_lists_three_options(self):
        try:
            audio_pipeline.resolve_lyria_version(
                "[Verse] walking home",
                explicit_version=None,
                confirm_upgrade=False,
                has_negative_prompt=False,
            )
            self.fail("Expected LyriaUpgradeGateError")
        except audio_pipeline.LyriaUpgradeGateError as e:
            msg = str(e)
            self.assertIn("--confirm-upgrade", msg)
            self.assertIn("--lyria-version 3", msg)
            self.assertIn("--lyria-version 3-pro", msg)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
python3 -m unittest tests.test_lyria_migration -v 2>&1 | tail -10
```

Expected: import errors or AttributeErrors — `detect_lyrics_intent`, `resolve_lyria_version`, `LyriaUpgradeGateError` don't exist yet.

- [ ] **Step 3: Add the helpers to `audio_pipeline.py`**

Near the top of `skills/create-video/scripts/audio_pipeline.py` (after existing imports but before the existing Lyria functions), add:

```python
import re


class LyriaUpgradeGateError(RuntimeError):
    """Raised when auto-detection routes to Lyria 3 Pro without --confirm-upgrade.

    Prevents silent 2x cost surprises when a user passes --music-source lyria
    without an explicit --lyria-version and the prompt contains song structure
    indicators that would otherwise auto-upgrade to the more expensive Pro model.
    """


# v4.2.1: Lyria auto-routing. Within the Lyria family, pick between
# Lyria 2 (negative_prompt use cases), Lyria 3 Clip (default), and
# Lyria 3 Pro (auto-selected when prompt contains song-structure markers,
# requires --confirm-upgrade).

_LYRIC_STRUCTURE_INDICATORS = frozenset({
    "[verse", "[chorus", "[bridge", "[hook",
    "[intro", "[outro", "[pre-chorus", "[refrain",
})
_TIMESTAMP_INDICATOR = re.compile(r"\[\d+:\d{2}\s*-\s*\d+:\d{2}\]")
_EXPLICIT_INSTRUMENTAL = frozenset({
    "instrumental only", "no vocals", "no lyrics",
})


def detect_lyrics_intent(prompt: str) -> bool:
    """Return True if the prompt appears to request a structured full-song
    generation (lyrics, verses, timestamps). Used for auto-routing Lyria 3
    Clip vs Lyria 3 Pro.

    Explicit 'instrumental only' / 'no vocals' / 'no lyrics' markers ALWAYS
    return False, even in the presence of structure tags — user intent to
    exclude vocals wins.
    """
    lower = prompt.lower()
    if any(ind in lower for ind in _EXPLICIT_INSTRUMENTAL):
        return False
    if any(ind in lower for ind in _LYRIC_STRUCTURE_INDICATORS):
        return True
    if _TIMESTAMP_INDICATOR.search(prompt):
        return True
    return False


_LYRIA_VERSION_MAP = {
    "2":     "lyria-2",
    "3":     "lyria-3",
    "3-pro": "lyria-3-pro",
}


def resolve_lyria_version(
    prompt: str,
    *,
    explicit_version: str | None,
    confirm_upgrade: bool,
    has_negative_prompt: bool,
) -> str:
    """Pick canonical Lyria model ID based on flags + prompt.

    Precedence:
      1. explicit_version ('2', '3', '3-pro') — always wins, no gate.
      2. has_negative_prompt — auto-route to lyria-2 (the only Lyria that
         accepts negative_prompt).
      3. detect_lyrics_intent(prompt) AND NOT confirm_upgrade — raise
         LyriaUpgradeGateError to prevent silent 2x cost upgrade.
      4. detect_lyrics_intent(prompt) AND confirm_upgrade — route to
         lyria-3-pro.
      5. Default — route to lyria-3 (Clip, cheapest).
    """
    if explicit_version is not None:
        if explicit_version not in _LYRIA_VERSION_MAP:
            raise ValueError(
                f"Invalid --lyria-version {explicit_version!r}. "
                f"Must be one of: {list(_LYRIA_VERSION_MAP.keys())}"
            )
        return _LYRIA_VERSION_MAP[explicit_version]

    if has_negative_prompt:
        return "lyria-2"

    if detect_lyrics_intent(prompt):
        if not confirm_upgrade:
            raise LyriaUpgradeGateError(
                "Detected song structure in prompt — full-song generation "
                "requires Lyria 3 Pro ($0.08/file vs Lyria 3 Clip $0.04/file).\n"
                "  - Pass --confirm-upgrade to proceed with Lyria 3 Pro.\n"
                "  - Pass --lyria-version 3 to force the cheaper Lyria 3 Clip.\n"
                "  - Pass --lyria-version 3-pro for explicit Pro (same as confirm)."
            )
        return "lyria-3-pro"

    return "lyria-3"
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python3 -m unittest tests.test_lyria_migration -v 2>&1 | tail -25
```

Expected: all 15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/create-video/scripts/audio_pipeline.py tests/test_lyria_migration.py
git commit -m "feat: add Lyria auto-routing helpers to audio_pipeline.py

- detect_lyrics_intent(prompt): pattern-match song-structure markers
  ([Verse], [Chorus], [Bridge], [Hook], [Intro], [Outro], [Pre-Chorus],
  [Refrain], timestamp ranges). Explicit 'instrumental only' / 'no
  vocals' / 'no lyrics' always returns False (user veto wins).

- resolve_lyria_version(): precedence explicit > negative_prompt ->
  Lyria 2 > lyrics intent + confirm_upgrade -> Lyria 3 Pro > default
  Lyria 3 Clip. Raises LyriaUpgradeGateError if auto-routing would
  upgrade to Pro without --confirm-upgrade (prevents silent 2x cost).

15 new tests in test_lyria_migration.py."
```

### Task 16: Replace Vertex Lyria calls with ReplicateBackend

**Files:**
- Modify: `skills/create-video/scripts/audio_pipeline.py`

**Context:** The current `generate_music_lyria()` and `generate_music_lyria_extended()` build Vertex URLs and call `{location}-aiplatform.googleapis.com` directly. Replace them with calls that use `ReplicateBackend` from the v4.2.0 abstraction.

This task is mechanical but has enough code that we'll do it in two commits (16a: the single-clip function, 16b: the extended-length function).

- [ ] **Step 1: Read the current `generate_music_lyria` function**

```bash
grep -n "^def generate_music_lyria\b\|^def generate_music_lyria_extended" skills/create-video/scripts/audio_pipeline.py
```

Open the file at those lines and read each function. Identify:
- Its argument signature
- Where it constructs the Vertex URL
- Where it calls urlopen
- Where it polls
- Where it parses the response
- Where it writes the output MP3

- [ ] **Step 2: Add sys.path + backend imports at the top of `audio_pipeline.py`**

After existing imports but before the existing Lyria code, add:

```python
# v4.2.1: Lyria migration to Replicate via the shared ProviderBackend
# abstraction (v4.2.0). See docs/superpowers/specs/2026-04-23-subproject-b-
# vertex-retirement-lyria-upgrade-design.md.
import sys as _sys
from pathlib import Path as _P

_plugin_root = str(_P(__file__).resolve().parent.parent.parent.parent)
if _plugin_root not in _sys.path:
    _sys.path.insert(0, _plugin_root)

from scripts.backends._replicate import ReplicateBackend as _ReplicateBackend
from scripts.backends._base import ProviderAuthError as _ProviderAuthError
from scripts.registry import registry as _reg
```

- [ ] **Step 3: Rewrite `generate_music_lyria()` to use ReplicateBackend**

Locate the existing function definition. Replace the body (keep the signature) with:

```python
def generate_music_lyria(
    prompt: str,
    *,
    negative_prompt: str | None = None,
    lyria_version: str | None = None,
    confirm_upgrade: bool = False,
    out_path: Path | None = None,
    seed: int | None = None,
    **kwargs,
) -> dict:
    """Generate a single 30-second Lyria clip via Replicate.

    Resolves which Lyria variant to use (2 / 3 / 3-pro) via
    resolve_lyria_version(), then submits through ReplicateBackend.

    kwargs swallow legacy arguments (e.g., 'project', 'location') for
    backward compat during the v4.2.1 transition. They are ignored —
    Replicate doesn't need Vertex project/location.
    """
    if kwargs:
        _logger.debug(
            "generate_music_lyria: ignoring legacy kwargs %s (Vertex context)",
            list(kwargs.keys()),
        )

    model_id = resolve_lyria_version(
        prompt,
        explicit_version=lyria_version,
        confirm_upgrade=confirm_upgrade,
        has_negative_prompt=(negative_prompt is not None),
    )

    registry = _reg.load_registry()
    model = registry.get_model(model_id)
    slug = model.providers["replicate"]["slug"]

    # Build canonical params — backend filters out ones the model doesn't support
    canonical_params: dict = {"prompt": prompt}
    if negative_prompt is not None:
        canonical_params["negative_prompt"] = negative_prompt
    if seed is not None:
        canonical_params["seed"] = seed

    # Load Replicate config — readable via the v4.2.0 migration shim
    # (providers.replicate.api_key OR legacy replicate_api_token)
    config = _load_banana_config()

    backend = _ReplicateBackend()

    try:
        job_ref = backend.submit(
            task="music-generation",
            model_slug=slug,
            canonical_params=canonical_params,
            provider_opts={},
            config=config,
        )
    except _ProviderAuthError as e:
        _error_exit(
            f"Replicate auth failed: {e}. "
            "Run setup_mcp.py to configure providers.replicate.api_key."
        )

    # Poll loop — reuse the existing polling cadence / timeout pattern
    _logger.info("Lyria submit accepted: %s (model=%s)", job_ref.external_id, model_id)
    poll_interval_s = 5.0
    max_wait_s = 300.0  # 5 min hard cap for single Lyria clip
    elapsed = 0.0

    while True:
        status = backend.poll(job_ref, config)
        if status.state == "succeeded":
            break
        if status.state in ("failed", "canceled"):
            _error_exit(
                f"Lyria generation {status.state}: {status.error or '(no error detail)'}"
            )
        if elapsed >= max_wait_s:
            _error_exit(
                f"Lyria generation timed out after {max_wait_s}s. Check Replicate dashboard."
            )
        import time
        time.sleep(poll_interval_s)
        elapsed += poll_interval_s

    # Download the output
    if out_path is None:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = DEFAULT_OUTPUT_DIR / f"music_{model_id}_{ts}.mp3"

    result = backend.parse_result(status, download_to=out_path)

    return {
        "source": "lyria",
        "model": model_id,
        "output_path": str(result.output_paths[0]),
        "output_urls": result.output_urls,
        "metadata": result.metadata,
        "provider": "replicate",
    }
```

- [ ] **Step 4: Verify the script still loads**

```bash
python3 skills/create-video/scripts/audio_pipeline.py --help 2>&1 | head -5
```

Expected: help text prints. If import errors, debug the sys.path shim.

- [ ] **Step 5: Run the full test suite**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: all tests still pass (the new generate_music_lyria is only called when user runs the CLI; no unit tests exercise the network path yet).

- [ ] **Step 6: Commit Task 16a**

```bash
git add skills/create-video/scripts/audio_pipeline.py
git commit -m "refactor: rewrite generate_music_lyria to use ReplicateBackend

Replaces the inline Vertex URL construction
({location}-aiplatform.googleapis.com) with a ReplicateBackend.submit()
+ poll + parse_result pipeline. Version resolution via
resolve_lyria_version() from Task 15. Legacy kwargs (project, location)
swallowed + logged for backward compat during transition.

Behavior change for users: --music-source lyria now produces output
from google/lyria-3 (Clip) by default instead of Vertex's lyria-002.
Callers can force the old model with --lyria-version 2."
```

### Task 17: Refactor `generate_music_lyria_extended` for the new model set

**Files:**
- Modify: `skills/create-video/scripts/audio_pipeline.py`

**Context:** This function chains N 30s Lyria calls + FFmpeg-crossfade to produce music longer than a single Lyria clip. With Lyria 3 Pro in the mix (native up to 3 min), chaining is unnecessary when the resolved version is Pro. For Lyria 2 and Lyria 3 Clip (both 30s fixed), chaining is still needed.

- [ ] **Step 1: Rewrite the extended function**

Replace the body of `generate_music_lyria_extended()`:

```python
def generate_music_lyria_extended(
    prompt: str,
    target_duration_sec: float,
    *,
    negative_prompt: str | None = None,
    lyria_version: str | None = None,
    confirm_upgrade: bool = False,
    out_path: Path | None = None,
    **kwargs,
) -> dict:
    """Generate Lyria music longer than a single 30s clip.

    Strategy:
      - If resolved model is lyria-3-pro: produce in ONE call (native up to 3 min).
        Pass target_duration_sec as a prompt hint (e.g., 'create a 90-second track').
      - If resolved model is lyria-3 or lyria-2: chain ceil(target / 30) clips via
        FFmpeg acrossfade=d=2, trim to exact target. Cost = N * clip_cost.
    """
    if kwargs:
        _logger.debug(
            "generate_music_lyria_extended: ignoring legacy kwargs %s",
            list(kwargs.keys()),
        )

    # Pre-resolve the version so we know whether to chain or single-call
    model_id = resolve_lyria_version(
        prompt,
        explicit_version=lyria_version,
        confirm_upgrade=confirm_upgrade,
        has_negative_prompt=(negative_prompt is not None),
    )

    if model_id == "lyria-3-pro":
        if target_duration_sec > 180:
            _error_exit(
                f"Lyria 3 Pro generates up to ~180s. Requested {target_duration_sec}s. "
                "Reduce target or use --lyria-version 3 for chained 30s clips."
            )
        # Augment prompt with duration hint — Lyria 3 Pro respects prompt-level duration
        duration_hint_prompt = (
            f"{prompt}\n\n(Generate approximately a {int(target_duration_sec)}-second track.)"
        )
        return generate_music_lyria(
            duration_hint_prompt,
            negative_prompt=negative_prompt,
            lyria_version="3-pro",  # already resolved; force explicit
            confirm_upgrade=True,   # already confirmed
            out_path=out_path,
        )

    # Chained path for Lyria 2 / Lyria 3 Clip (both 30s fixed)
    CLIP_LEN_S = 30.0
    CROSSFADE_S = 2.0
    # Each crossfade overlaps clips by CROSSFADE_S, so N clips produce
    # (CLIP_LEN_S + (N-1)*(CLIP_LEN_S - CROSSFADE_S)) seconds of output.
    # Solve for N given target: N = 1 + ceil((target - CLIP_LEN_S) / (CLIP_LEN_S - CROSSFADE_S))
    effective_clip_s = CLIP_LEN_S - CROSSFADE_S
    import math
    n_clips = 1 + max(0, math.ceil((target_duration_sec - CLIP_LEN_S) / effective_clip_s))

    _logger.info(
        "Extended Lyria: target=%.1fs, chaining %d x %s clips with %ss crossfade",
        target_duration_sec, n_clips, model_id, CROSSFADE_S,
    )

    # Generate N clips
    from datetime import datetime
    tmpdir = DEFAULT_OUTPUT_DIR / f"lyria_extended_{datetime.now():%Y%m%d_%H%M%S}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    clip_paths: list[Path] = []

    for i in range(n_clips):
        clip_path = tmpdir / f"clip_{i:02d}.mp3"
        _logger.info("  clip %d/%d -> %s", i + 1, n_clips, clip_path)
        generate_music_lyria(
            prompt,
            negative_prompt=negative_prompt,
            lyria_version=lyria_version,   # forces the same model for each chunk
            confirm_upgrade=True,           # already confirmed
            out_path=clip_path,
        )
        clip_paths.append(clip_path)

    # FFmpeg-chain with crossfade, then trim to exact target
    if out_path is None:
        out_path = DEFAULT_OUTPUT_DIR / f"music_{model_id}_extended_{datetime.now():%Y%m%d_%H%M%S}.mp3"

    _ffmpeg_chain_with_crossfade(
        clip_paths, out_path,
        crossfade_s=CROSSFADE_S,
        target_duration_s=target_duration_sec,
    )

    return {
        "source": "lyria",
        "model": model_id,
        "output_path": str(out_path),
        "chunks": len(clip_paths),
        "target_duration_s": target_duration_sec,
        "provider": "replicate",
    }
```

(The `_ffmpeg_chain_with_crossfade` helper already exists in `audio_pipeline.py` from the v3.7.4 work — it takes a list of clip paths, an output path, a crossfade duration, and a target duration. Keep using it unchanged.)

- [ ] **Step 2: Smoke test**

```bash
python3 skills/create-video/scripts/audio_pipeline.py --help 2>&1 | head -5
```

Expected: help prints cleanly.

- [ ] **Step 3: Run the full test suite**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: all tests still pass.

- [ ] **Step 4: Commit Task 17**

```bash
git add skills/create-video/scripts/audio_pipeline.py
git commit -m "refactor: generate_music_lyria_extended handles 3 Lyria variants

For Lyria 3 Pro (native up to 3 min): single call with duration hint
appended to the prompt. Pro respects prompt-level duration instructions.

For Lyria 2 or Lyria 3 Clip (both 30s fixed): chain N clips with
FFmpeg acrossfade=d=2 (existing _ffmpeg_chain_with_crossfade helper
from v3.7.4). N = 1 + ceil((target - 30) / 28).

Guards: target_duration_sec > 180 raises when resolved to Pro, telling
user to either reduce target or force --lyria-version 3 for chaining."
```

### Task 18: Remove Vertex URL construction + auth code

**Files:**
- Modify: `skills/create-video/scripts/audio_pipeline.py`

**Context:** The old `generate_music_lyria` / `_extended` referenced Vertex-specific helpers: building Vertex URLs, loading Vertex credentials, parsing Vertex response format. Now that the functions go through ReplicateBackend, these helpers are dead code.

- [ ] **Step 1: Find the Vertex-specific helpers to delete**

```bash
grep -n "aiplatform.googleapis.com\|vertex_api_key\|vertex_project_id\|vertex_location\|LYRIA_MODEL_ID" skills/create-video/scripts/audio_pipeline.py | head -20
```

Identify the constants + helper functions that are only used by the old Lyria path. Common candidates:
- `LYRIA_MODEL_ID = "lyria-002"` — no longer used (model ID comes from registry now)
- Any `_build_vertex_lyria_url()` helper
- Any `_load_vertex_creds()` helper or inline credential loader
- Any `_parse_vertex_audio_response()` helper

- [ ] **Step 2: Delete dead code**

For each identified helper/constant:
1. Verify it's only called from within the old Lyria code (now rewritten).
2. Delete it.
3. If a constant like `LYRIA_MODEL_ID` is referenced in log messages or config-key fallback, update the reference to use the registry lookup instead.

- [ ] **Step 3: Verify audio_pipeline.py still loads**

```bash
python3 skills/create-video/scripts/audio_pipeline.py --help 2>&1 | head -10
```

Expected: help prints. If NameError on a removed constant, find the remaining reference and clean it up.

- [ ] **Step 4: Full grep to confirm Vertex is gone from audio_pipeline**

```bash
grep -nE "vertex|aiplatform" skills/create-video/scripts/audio_pipeline.py | grep -v "^\s*#" | grep -v "^\s*\"\"\""
```

Expected: empty (or only docstring mentions like "(Vertex Lyria retired in v4.2.1)").

- [ ] **Step 5: Run full test suite**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add skills/create-video/scripts/audio_pipeline.py
git commit -m "refactor: remove Vertex URL construction + auth from audio_pipeline.py

Deleted helpers:
- LYRIA_MODEL_ID constant (model ID now comes from registry)
- Inline vertex_api_key / vertex_project_id / vertex_location loading
  (the new code uses providers.replicate.api_key via the v4.2.0
  migration shim in setup_mcp.py)
- Vertex URL builder
- Vertex response parser

audio_pipeline.py no longer references aiplatform.googleapis.com.
ElevenLabs code paths are untouched."
```

### Task 19: Add `--lyria-version` and `--confirm-upgrade` CLI flags

**Files:**
- Modify: `skills/create-video/scripts/audio_pipeline.py`

- [ ] **Step 1: Find the argparse block for `music` subcommand**

```bash
grep -n "add_parser.*music\|'music'\|\"music\"" skills/create-video/scripts/audio_pipeline.py | head -10
```

Locate the subparser definition.

- [ ] **Step 2: Add the two new flags to the `music` subparser**

```python
music_parser.add_argument(
    "--lyria-version",
    choices=["2", "3", "3-pro"],
    default=None,
    help="Force a specific Lyria variant: 2 (negative_prompt support), "
         "3 (Clip, 30s, default), 3-pro (full songs up to 3 min). Without "
         "this flag, auto-detection selects the right variant from the prompt.",
)
music_parser.add_argument(
    "--confirm-upgrade",
    action="store_true",
    default=False,
    help="Acknowledge the 2x cost upgrade when auto-detection would route "
         "to Lyria 3 Pro ($0.08/file vs $0.04/file for Clip). Required "
         "only when --lyria-version is not explicitly set AND the prompt "
         "contains song-structure markers like [Verse], [Chorus], timestamps.",
)
```

The same flags likely also need to appear on the `pipeline` subcommand if it calls Lyria internally. Add them there too.

- [ ] **Step 3: Thread the flags through to the call**

Find the music subcommand's handler function. Where it calls `generate_music_lyria` or `generate_music_lyria_extended`, pass the new args:

```python
def _cmd_music(args) -> int:
    # ... existing source-detection logic for "lyria" vs "elevenlabs"
    if source == "lyria":
        kwargs = {
            "negative_prompt": args.negative_prompt,
            "lyria_version": args.lyria_version,
            "confirm_upgrade": args.confirm_upgrade,
        }
        if args.length_ms and args.length_ms > 32000:
            result = generate_music_lyria_extended(
                args.prompt,
                target_duration_sec=args.length_ms / 1000.0,
                **kwargs,
                out_path=args.out,
            )
        else:
            result = generate_music_lyria(
                args.prompt,
                **kwargs,
                out_path=args.out,
            )
        # ...
```

Wrap the call in a try/except for `LyriaUpgradeGateError`:

```python
    try:
        result = generate_music_lyria(...)
    except LyriaUpgradeGateError as e:
        print(str(e), file=sys.stderr)
        return 2  # non-zero exit
```

- [ ] **Step 4: Smoke test with missing confirm (should fail with helpful error)**

```bash
python3 skills/create-video/scripts/audio_pipeline.py music \
    --prompt "[Verse] testing the gate" \
    --source lyria \
    --dry-run 2>&1 | head -10
```

Expected: the LyriaUpgradeGateError message, exit 2. (Or if `--dry-run` doesn't exist, just test without `--dry-run` with a fake API key; the gate should fire before any HTTP call.)

- [ ] **Step 5: Smoke test with --lyria-version 3 explicit (should skip gate)**

```bash
python3 skills/create-video/scripts/audio_pipeline.py music \
    --prompt "[Verse] testing the gate" \
    --source lyria --lyria-version 3 \
    --out /tmp/test.mp3 2>&1 | head -5
```

Expected: no gate error; proceeds to real Replicate call (will fail auth with a placeholder key, but that's a different error — proves the gate was skipped correctly).

- [ ] **Step 6: Commit**

```bash
git add skills/create-video/scripts/audio_pipeline.py
git commit -m "feat: add --lyria-version and --confirm-upgrade flags to audio_pipeline

New flags on 'music' and 'pipeline' subcommands:
  --lyria-version {2,3,3-pro}   Force a specific variant; bypasses auto-detect
  --confirm-upgrade              Acknowledge 2x cost bump when auto-detect
                                 would route to Pro

Handler catches LyriaUpgradeGateError and prints the 3-option help
message to stderr, exiting with code 2. Users in automation can pass
--lyria-version explicitly to suppress auto-detection entirely."
```

---

## Phase 6 — video_generate.py VEO migration

### Task 20: Remove `import _vertex_backend` + `_select_backend` simplification

**Files:**
- Modify: `skills/create-video/scripts/video_generate.py`

**Context:** `video_generate.py` currently has three backend paths: Gemini API (text-to-video via preview), Vertex AI (VEO + scene extension), Replicate (Kling + now VEO). After B, Vertex is gone — path simplifies to Gemini API + Replicate only.

- [ ] **Step 1: Find the Vertex references**

```bash
grep -nE "import _vertex_backend|vertex\.|_vertex_backend|--backend vertex-ai|_select_backend" \
    skills/create-video/scripts/video_generate.py | head -30
```

Note each line number. The `_select_backend()` function is the routing logic that picks between the three backends.

- [ ] **Step 2: Read `_select_backend` logic**

Open `video_generate.py` at the `_select_backend` line. Typical shape:

```python
def _select_backend(model_slug: str, args) -> str:
    if args.backend == "vertex-ai":
        return "vertex"
    if args.backend == "replicate" or "/" in model_slug:
        return "replicate"
    return "gemini"   # preview API
```

(Actual logic may differ slightly; read the real implementation.)

- [ ] **Step 3: Add a Vertex model-ID → Replicate slug translation table**

Before `_select_backend`, add:

```python
# v4.2.1: Vertex retirement. Map legacy Vertex model IDs to their Replicate
# equivalents so users passing --backend vertex-ai + Vertex-style model names
# continue to work (with a deprecation warning). The mapping is empirical —
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
    Pass-through for anything else (Kling slugs, already-Replicate VEO slugs)."""
    return _VERTEX_TO_REPLICATE_SLUG.get(model_slug, model_slug)
```

- [ ] **Step 4: Rewrite `_select_backend()` to drop Vertex**

```python
def _select_backend(model_slug: str, args) -> str:
    """Return one of: 'gemini', 'replicate'.

    v4.2.1: 'vertex' is removed. --backend vertex-ai is deprecated and
    auto-routes to 'replicate' after translating legacy Vertex model IDs
    to Replicate slugs.
    """
    explicit = getattr(args, "backend", None)

    if explicit == "vertex-ai":
        # Deprecation warning + auto-route
        import warnings
        warnings.warn(
            "--backend vertex-ai is deprecated. Vertex AI was retired in v4.2.1; "
            "VEO 3.1 now routes through Replicate. This flag is honored for one "
            "release and will be removed in v4.3.0. Use --backend replicate or "
            "remove the flag (auto-selects based on model slug).",
            DeprecationWarning,
            stacklevel=2,
        )
        return "replicate"

    if explicit == "replicate":
        return "replicate"
    if explicit == "gemini" or explicit == "gemini-api":
        return "gemini"

    # Auto-select from slug shape:
    #   owner/name         -> Replicate (Kling, VEO, Fabric, etc.)
    #   bare name          -> Gemini preview API
    if "/" in model_slug:
        return "replicate"
    return "gemini"
```

- [ ] **Step 5: Translate Vertex model IDs at entry point**

In the `main()` or wherever model_slug is first resolved, add translation:

```python
def main():
    args = _parse_args()
    # v4.2.1: translate legacy Vertex model IDs to Replicate slugs before
    # any routing logic sees them. Deprecation warning lands on first use.
    if args.model != _translate_vertex_model_id(args.model):
        import warnings
        warnings.warn(
            f"Model ID {args.model!r} is a legacy Vertex identifier. "
            f"Translated to Replicate slug "
            f"{_translate_vertex_model_id(args.model)!r}. "
            f"Update scripts to use the Replicate slug directly; Vertex "
            f"translation will be removed in v4.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        args.model = _translate_vertex_model_id(args.model)

    # ... existing routing logic
```

- [ ] **Step 6: Delete the `import _vertex_backend as vertex` line**

Locate the line:

```python
import _vertex_backend as vertex  # noqa: E402
```

(Plus any surrounding comment block explaining why it's imported.)

Delete the line and its comment. The `sys.path.insert` that preceded it can stay — other modules in the same directory may be imported the same way.

- [ ] **Step 7: Delete all `vertex.*` call sites**

Grep for call sites:

```bash
grep -n "^\s*vertex\." skills/create-video/scripts/video_generate.py | head -20
```

For each match, the code was dispatching to Vertex. Replace each Vertex call with the equivalent `_ReplicateBackend` call from the pattern already used for Kling in the file. If the replacement is complex (e.g., one callsite that had Vertex-specific retry logic), refactor carefully and add a comment explaining the migration.

Example transform:

```python
# BEFORE:
prediction = vertex.submit_veo_generation(
    api_key=vertex_creds.api_key,
    project=vertex_creds.project,
    location=vertex_creds.location,
    model=args.model,
    prompt=args.prompt,
    duration=args.duration,
)

# AFTER:
from scripts.backends._replicate import ReplicateBackend
backend = ReplicateBackend()
config = _load_banana_config()
job_ref = backend.submit(
    task="text-to-video" if not args.start_image else "image-to-video",
    model_slug=args.model,  # already translated by _translate_vertex_model_id()
    canonical_params={
        "prompt": args.prompt,
        "duration_s": args.duration,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        "audio_enabled": not args.no_audio,  # VEO Fast/Standard toggle
        **({"start_image": args.start_image} if args.start_image else {}),
    },
    provider_opts={},
    config=config,
)
prediction = {"id": job_ref.external_id, "urls": {"get": job_ref.poll_url}}
```

- [ ] **Step 8: Smoke test video_generate.py --help**

```bash
python3 skills/create-video/scripts/video_generate.py --help 2>&1 | head -20
```

Expected: help prints cleanly. No import errors.

- [ ] **Step 9: Full test suite**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add skills/create-video/scripts/video_generate.py
git commit -m "refactor: remove Vertex branch from video_generate.py

- Delete 'import _vertex_backend as vertex'
- _select_backend now returns 'gemini' or 'replicate' only
- --backend vertex-ai deprecated: logs warning + auto-routes to replicate
- Legacy Vertex model IDs (veo-3.1-generate-001 etc.) auto-translate to
  Replicate slugs (google/veo-3.1) with deprecation warning
- All vertex.* call sites replaced with ReplicateBackend.submit/poll

Users who pass --backend vertex-ai or veo-3.1-generate-001 continue to
work for one release; both paths removed in v4.3.0."
```

### Task 21: Deprecate `--provider veo` alias

**Files:**
- Modify: `skills/create-video/scripts/video_generate.py`

**Context:** `--provider veo` was the v4.2.0 compatibility alias that routed VEO through Vertex. In v4.2.1 it routes through Replicate with a Fast-tier default.

- [ ] **Step 1: Find the `--provider` argument handler**

```bash
grep -nE "add_argument.*provider|args\.provider" skills/create-video/scripts/video_generate.py | head -10
```

- [ ] **Step 2: Update the provider normalizer**

```python
def _normalize_provider(provider: str | None, model_slug: str) -> tuple[str | None, str]:
    """Resolve --provider alias to the canonical (provider, model_slug) pair.

    v4.2.1: --provider veo is a compat alias for --provider replicate with
    the VEO Fast tier default. Emits a deprecation warning.
    """
    if provider == "veo":
        import warnings
        warnings.warn(
            "--provider veo is deprecated. Use --provider replicate --model "
            "{veo-3.1-lite, veo-3.1-fast, veo-3.1} instead. This alias is "
            "honored for one release and will be removed in v4.3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        # If user passed --provider veo without --model, default to Fast tier
        if not model_slug or model_slug == "kwaivgi/kling-v3-video":
            model_slug = "google/veo-3.1-fast"
        return "replicate", model_slug
    return provider, model_slug
```

Wire it into `main()`:

```python
    args.provider, args.model = _normalize_provider(args.provider, args.model)
```

- [ ] **Step 3: Smoke test**

```bash
python3 skills/create-video/scripts/video_generate.py --help 2>&1 | head -10
```

Expected: help prints.

- [ ] **Step 4: Commit**

```bash
git add skills/create-video/scripts/video_generate.py
git commit -m "refactor: --provider veo deprecated to --provider replicate --model veo-3.1-fast

Compat alias logs a deprecation warning and auto-translates. When user
passes --provider veo without --model, defaults to veo-3.1-fast (mid-
tier balance of cost/quality). Removed in v4.3.0."
```

---

## Phase 7 — setup_mcp.py Vertex removal

### Task 22: Remove Vertex CLI flags from setup_mcp.py

**Files:**
- Modify: `skills/create-image/scripts/setup_mcp.py`

**Context:** The v4.2.0 config migration shim (`migrate_config_to_v4_2_0`) already reads legacy `vertex_*` keys into `providers.vertex.*`. This shim stays — it ensures users upgrading from v4.1.x don't lose config. What this task removes is the CLI interface for SETTING up Vertex, not reading existing config.

- [ ] **Step 1: Find Vertex CLI arguments and setup function**

```bash
grep -nE "vertex-api-key|vertex-project|vertex-location|setup_vertex|--vertex" \
    skills/create-image/scripts/setup_mcp.py
```

- [ ] **Step 2: Delete Vertex-specific CLI args**

Remove `--vertex-api-key`, `--vertex-project`, `--vertex-location` argparse declarations. Remove any conditional that dispatches based on these flags.

- [ ] **Step 3: Delete Vertex setup function**

If there's a `setup_vertex()` or similar function, delete it entirely. It's unreachable now that the CLI flags are gone.

- [ ] **Step 4: Preserve the migration shim**

`migrate_config_to_v4_2_0()` MUST stay — it's the graceful-upgrade path. It reads the old `vertex_*` keys and copies them to `providers.vertex.*` in the config. Nothing in v4.2.1 consumes `providers.vertex.*` at runtime, but the keys persist harmlessly for users who might roll back.

Verify the migration function is intact:

```bash
grep -n "migrate_config_to_v4_2_0\|vertex" skills/create-image/scripts/setup_mcp.py
```

Expected: the keymap and migration function still present; CLI handlers gone.

- [ ] **Step 5: Smoke test**

```bash
python3 skills/create-image/scripts/setup_mcp.py --help 2>&1 | head -15
```

Expected: help prints without `--vertex-*` flags listed.

- [ ] **Step 6: Run config migration tests**

```bash
python3 -m unittest tests.test_setup_mcp_migration -v 2>&1 | tail -10
```

Expected: all 7 migration tests still pass — the shim is unchanged.

- [ ] **Step 7: Commit**

```bash
git add skills/create-image/scripts/setup_mcp.py
git commit -m "refactor: remove Vertex CLI flags from setup_mcp.py

Deleted --vertex-api-key, --vertex-project, --vertex-location arguments
and any setup_vertex() helper. migrate_config_to_v4_2_0() retained —
old vertex_* keys still migrate to providers.vertex.* for graceful
upgrade. Nothing consumes providers.vertex.* at runtime in v4.2.1+."
```

---

## Phase 8 — Delete `_vertex_backend.py`

### Task 23: Final grep + delete

**Files:**
- Delete: `skills/create-video/scripts/_vertex_backend.py`

- [ ] **Step 1: Final check for any remaining imports**

```bash
grep -rn "from _vertex_backend\|import _vertex_backend" . --include="*.py" 2>&1 | grep -v "\.git"
```

Expected: empty. If any match: trace and remove before proceeding.

- [ ] **Step 2: Check for code references to `aiplatform.googleapis.com`**

```bash
grep -rn "aiplatform.googleapis.com" . --include="*.py" 2>&1 | grep -v "\.git" | grep -v "^\s*#" | grep -v "^\s*\"\"\""
```

Expected: empty. Only acceptable matches are doc comments mentioning the retired endpoint in historical context.

- [ ] **Step 3: Delete the file**

```bash
git rm skills/create-video/scripts/_vertex_backend.py
```

- [ ] **Step 4: Run all scripts' `--help` to catch any import issues**

```bash
for f in skills/create-video/scripts/video_generate.py \
         skills/create-video/scripts/video_lipsync.py \
         skills/create-video/scripts/video_sequence.py \
         skills/create-video/scripts/audio_pipeline.py \
         skills/create-image/scripts/vectorize.py \
         skills/create-image/scripts/generate.py \
         skills/create-image/scripts/edit.py \
         skills/create-image/scripts/setup_mcp.py; do
  echo "=== $f ==="
  python3 "$f" --help 2>&1 | head -2
done
```

Expected: every script prints help text. No import errors.

- [ ] **Step 5: Full test suite**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: ~109+ tests pass (same count as before — deletion doesn't change test count, but confirms no import breakage).

- [ ] **Step 6: Verify pycache cleanup**

```bash
find skills/create-video/scripts/__pycache__ -name "_vertex_backend*" -delete 2>/dev/null
ls skills/create-video/scripts/__pycache__/ 2>/dev/null | grep -i vertex
```

Expected: no matches (pycache for the deleted file cleaned up; gitignore keeps the dir untracked anyway).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: delete _vertex_backend.py (958 lines) — Vertex AI retired

Every consumer of _vertex_backend.py was migrated to ReplicateBackend
in prior commits (video_generate.py, audio_pipeline.py). The file is
now unreferenced and is safe to remove.

grep verification:
  grep -rn 'from _vertex_backend|import _vertex_backend' .  -> empty
  grep -rn 'aiplatform.googleapis.com' .                     -> empty

All scripts load via --help. Full test suite passes (109+ tests).
Vertex AI is entirely removed from the plugin."
```

---

## Phase 9 — Reference documentation

### Task 24: Replace `references/models/veo-3.1.md` placeholder

**Files:**
- Modify: `references/models/veo-3.1.md`

- [ ] **Step 1: Overwrite the placeholder**

The v4.2.0 release shipped `references/models/veo-3.1.md` as a placeholder. Replace its entire contents with:

```markdown
# Google VEO 3.1 (canonical model IDs: `veo-3.1-lite` / `veo-3.1-fast` / `veo-3.1`)

**Status:** Registered and reachable via Replicate. NOT the default — Kling v3 remains the video family default per the v3.8.0 spike 5 quality verdict. VEO is opt-in backup via `--provider replicate --model veo-3.1-{lite,fast,}`. A post-sub-project-C bake-off will re-evaluate the Kling-vs-VEO default in light of v4.2.1's corrected Kling pricing.

**Hosting providers:** Replicate (all three tiers). Vertex AI retired in v4.2.1.

## Three tiers at a glance

| Tier | Canonical ID | Replicate slug | Cost (8s @ 1080p + audio) | Unique capabilities |
|---|---|---|---|---|
| Lite | `veo-3.1-lite` | `google/veo-3.1-lite` | $0.64 | Cheapest; audio always on |
| Fast | `veo-3.1-fast` | `google/veo-3.1-fast` | $1.20 | Audio toggle; up to 3 reference images |
| Standard | `veo-3.1` | `google/veo-3.1` | $3.20 | 4K output; video extension; highest fidelity |

## Canonical constraints (enforced pre-HTTP)

All three tiers:
- `duration_s` ∈ {4, 6, 8} — enum, not range
- `aspect_ratio` ∈ {`16:9`, `9:16`} — no 1:1 support
- `resolution` ∈ {`720p`, `1080p`} for Lite/Fast; Standard adds `4K`

**Lite-specific conditional:** `resolution=1080p` requires `duration_s=8`. NOT machine-enforced by `_canonical.py` in v4.2.1 — Replicate's server-side rejection is the safety net. Documented in the registry entry's `canonical_constraints.conditional` field.

## Pricing breakdown

**VEO 3.1 Lite** — `per_second_by_resolution` mode:
- 720p: $0.05/s
- 1080p: $0.08/s (requires 8s duration)
- Audio is always on — no without-audio variant

**VEO 3.1 Fast** — `per_second_by_audio` mode:
- With audio: $0.15/s
- Without audio: $0.10/s

**VEO 3.1 Standard** — `per_second_by_audio` mode:
- With audio: $0.40/s
- Without audio: $0.20/s

## Capabilities per tier

**Lite:** text-to-video, image-to-video, 4/6/8 second durations, audio always on, 720p or 1080p. No reference images. No video extension.

**Fast:** text-to-video, image-to-video, 4/6/8 second durations, audio toggle, 720p or 1080p, up to 3 reference images for character/style consistency, frame-to-frame generation (start + end frames).

**Standard:** everything Fast does, plus 4K output and video extension (build longer narratives by chaining clips where the next one continues from the previous).

## Cost comparison (8s @ 1080p with audio)

| Model | Cost |
|---|---|
| **VEO 3.1 Lite** | **$0.64** (cheapest option at 1080p) |
| VEO 3.1 Fast | $1.20 |
| Kling v3 pro-audio | $2.69 |
| VEO 3.1 Standard | $3.20 (most expensive) |

The v3.8.0 narrative of "Kling is 7.5× cheaper than VEO" was based on an incorrect Kling price point; at the verified v4.2.1 rates, **VEO Lite is actually ~4× cheaper than Kling at comparable settings**. Queued for re-evaluation in a post-sub-project-C bake-off.

## Prompting tips (from Google dev-docs)

- Be specific: camera angles, lighting, mood, audio cues
- For image-to-video: describe the motion you want, not just what's in the image
- Audio cues in quotation marks render as dialogue; unquoted descriptions become ambient
- Reference images (Fast/Standard): clear, well-lit, subject-from-desired-angle

## Authoritative sources

- `dev-docs/google-veo-3.1-lite-llms.md`
- `dev-docs/google-veo-3.1-fast-llms.md`
- `dev-docs/google-veo-3.1-llms.md`
- Google Gemini API: https://ai.google.dev/gemini-api/docs
```

- [ ] **Step 2: Commit**

```bash
git add references/models/veo-3.1.md
git commit -m "docs: replace VEO 3.1 placeholder with real content

Full capability + pricing + constraint documentation for all three
tiers (Lite / Fast / Standard). Includes the corrected cost
comparison showing VEO Lite is ~4x cheaper than Kling at 1080p with
audio — inverting the v3.8.0 narrative. Queues re-evaluation for
post-sub-project-C bake-off."
```

### Task 25: Write `references/models/lyria-2.md`

**Files:**
- Create: `references/models/lyria-2.md`

```markdown
# Google Lyria 2 (canonical model ID: `lyria-2`)

**Status:** Registered for `--music-source lyria --lyria-version 2` and for auto-selection when `--negative-prompt` is provided. NOT the default — Lyria 3 Clip is the within-Lyria default as of v4.2.1 (cheaper + newer).

**Hosting providers:** Replicate (`google/lyria-2`). Vertex retired in v4.2.1.

## What makes it unique

Lyria 2 is the only Lyria variant on Replicate that accepts `negative_prompt`. This was the v3.8.3 justification for keeping Lyria in the plugin after ElevenLabs Music won the 12-genre bake-off — `negative_prompt` is Lyria 2's differentiator vs ElevenLabs Music (which has no equivalent exclusion param).

## Canonical constraints

- `duration_fixed_s: 30` — every Lyria 2 clip is exactly 30 seconds. Use `generate_music_lyria_extended` for longer tracks (chains N clips with FFmpeg crossfade).

## Supported canonical params

- `prompt` (required)
- `negative_prompt` (unique to Lyria 2)
- `seed`

**NOT supported:** `reference_images` (Lyria 3 / 3-Pro only)

## Pricing

`per_call` mode, $0.06 per 30-second clip.

## Auto-selection rules

The `audio_pipeline.py::resolve_lyria_version()` function auto-selects Lyria 2 when:
- User passes `--music-source lyria` AND sets `--negative-prompt "..."`, AND
- User does NOT pass `--lyria-version` explicitly

Users can force Lyria 2 even without `--negative-prompt` via `--lyria-version 2`.

## Authoritative source

`dev-docs/google-lyria-2-llms.md`
```

- [ ] Commit after writing.

### Task 26: Write `references/models/lyria-3.md`

**Files:**
- Create: `references/models/lyria-3.md`

```markdown
# Google Lyria 3 — Clip variant (canonical model ID: `lyria-3`)

**Status:** Default within Lyria family as of v4.2.1. Used when `--music-source lyria` is set and the prompt does NOT trigger auto-routing to Lyria 3 Pro (no song-structure tags) and no `--negative-prompt` is set.

**Hosting providers:** Replicate (`google/lyria-3`).

## Capabilities

- 30-second MP3 clips at 48kHz stereo
- Text-to-music generation
- **Reference images**: up to 10 images that inspire composition (NEW vs Lyria 2)
- **Vocal generation**: instructed via prompt; use "Instrumental only" to veto
- **Multilingual**: prompt in target language for lyrics in that language
- **Structure tags**: `[Verse]`, `[Chorus]`, etc. respected in the prompt

## Canonical constraints

- `duration_fixed_s: 30`

## Supported canonical params

- `prompt` (required)
- `reference_images` (0–10 images; NEW vs Lyria 2)

**NOT supported:** `negative_prompt`, `seed`

**Filtering behavior:** if a caller passes `negative_prompt` with `lyria-3`, `ReplicateBackend.submit()` silently drops it and logs a WARN via `_logger`. Same for `seed`.

## Pricing

`per_call` mode, $0.04 per 30-second clip. **Cheaper than Lyria 2** ($0.06) despite being the newer model.

## Prompting tips

- Be specific: genre, instruments, BPM, key, mood
- Use `[Verse]`, `[Chorus]`, `[Bridge]` tags to suggest structure — but note that a 30s clip has limited room for structure, so Pro is better for multi-section songs
- Explicit "Instrumental only, no vocals" vetoes vocal generation

## Cost comparison

| Variant | Cost | Duration | Best for |
|---|---|---|---|
| Lyria 2 | $0.06 | 30s | `negative_prompt` workflows |
| **Lyria 3 Clip** | **$0.04** | **30s** | **Default — short instrumental music, reference-image workflows** |
| Lyria 3 Pro | $0.08 | up to 3 min | Full songs with structure / lyrics |
| ElevenLabs Music | subscription | 3s–5 min | Plugin default (won 12-0 bake-off); vocals + finetunes |

## Authoritative source

`dev-docs/google-lyria-3-llms.md`
```

- [ ] Commit.

### Task 27: Write `references/models/lyria-3-pro.md`

**Files:**
- Create: `references/models/lyria-3-pro.md`

```markdown
# Google Lyria 3 Pro (canonical model ID: `lyria-3-pro`)

**Status:** Registered for opt-in and auto-routed use. NOT the default — ElevenLabs Music is the overall music default; Lyria 3 Clip is the within-Lyria default. Pro is auto-selected when user passes `--music-source lyria` with a prompt containing song-structure markers, AND confirms via `--confirm-upgrade` flag.

**Hosting providers:** Replicate (`google/lyria-3-pro`).

## What makes it unique

A full-song generator, not just a clip. Produces structured tracks up to ~3 minutes with verses, choruses, bridges, custom lyrics, and timestamp control. This is a meaningful capability gap vs Lyria 2 / Lyria 3 Clip (both 30-second fixed) and is closer in spirit to Suno (available after sub-project C) than to ElevenLabs Music.

## Capabilities

- MP3 audio up to ~3 minutes at 48kHz stereo
- Text-to-song with structure tags: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Hook]`, `[Intro]`, `[Outro]`
- Custom lyrics embedded in the prompt
- Timestamp control: `[0:00 - 0:30] Intro: soft piano` guides timing
- Reference images (up to 10) to inspire composition
- Multilingual
- Vocal generation with lyric following

## Canonical constraints

- `duration_max_s: 180` — aspirational; Google's model card says duration is "influenced by prompting" rather than strictly controlled.

## Supported canonical params

- `prompt` (required; contains the song structure, lyrics, and tempo/style direction)
- `reference_images` (0–10 images)

**NOT supported:** `negative_prompt`, `seed`

## Auto-selection rules (v4.2.1)

`audio_pipeline.py::resolve_lyria_version()` auto-routes to Lyria 3 Pro when:
1. User passed `--music-source lyria`
2. User did NOT pass `--lyria-version`
3. User did NOT pass `--negative-prompt`
4. Prompt contains song-structure markers detected by `detect_lyrics_intent()`: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Hook]`, `[Intro]`, `[Outro]`, `[Pre-Chorus]`, `[Refrain]`, or timestamp ranges like `[0:00 - 0:30]`
5. Prompt does NOT contain explicit instrumental markers (`"instrumental only"`, `"no vocals"`, `"no lyrics"`)
6. User passes `--confirm-upgrade` to acknowledge the 2× cost vs Lyria 3 Clip

Without `--confirm-upgrade`, the auto-detection raises `LyriaUpgradeGateError` with a 3-option help message. This prevents silent cost surprises.

## Pricing

`per_call` mode, $0.08 per file (up to ~3 min). Effective per-second rate for a full 3-minute song: ~$0.00044/s — dramatically cheaper than Lyria 3 Clip at per-second rates, but per-file pricing means short songs don't get a discount.

## Prompting tips (from the Google model card)

- Separate lyrics from musical direction. Example:
  ```
  [Verse 1]
  Walking through the neon glow,
  city lights reflect below

  [Chorus]
  We are the echoes in the night

  Genre: Dreamy indie pop. Mood: Nostalgic and uplifting. Tempo: 110 BPM.
  ```
- Timestamp control for precise timing:
  ```
  [0:00 - 0:15] Intro: Soft lo-fi beat
  [0:15 - 0:45] Verse: Warm Fender Rhodes piano
  [0:45 - 1:15] Chorus: Full arrangement with lush pads
  ```
- Include duration hint in prompt: `"Generate approximately a 2-minute track"`
- Iterate with Lyria 3 Clip first (cheaper, faster) to find a sound, then use Pro for the final full song

## Authoritative source

`dev-docs/google-lyria-3-pro-llms.md`
```

- [ ] Commit.

### Task 28: Write `references/models/elevenlabs-music.md`

**Files:**
- Create: `references/models/elevenlabs-music.md`

```markdown
# ElevenLabs Music (canonical model ID: `elevenlabs-music`)

**Status:** Overall music default (via `family_defaults.music` in the registry). Won the v3.8.3 12-genre blind A/B bake-off vs Lyria 2 with a 12-0 sweep. Used when user invokes music generation without `--music-source lyria`.

**Hosting providers:** ElevenLabs (`(direct)` sentinel slug). NOT routed through `ReplicateBackend` yet — `audio_pipeline.py` calls the ElevenLabs API directly via the existing helpers. Registered in the model registry so `family_defaults.music` has a target and the multi-model principle is upheld.

## Capabilities

- Vocals and/or instrumental (toggled via prompt)
- Lyrics editing per-section or whole-song
- Multilingual: English, Spanish, German, Japanese, and more
- Duration 3–5 minutes (wider range than any Lyria variant)
- **Music Finetunes** — fine-tune the model on your own tracks for brand consistency (Enterprise tier: IP-protected training)
- Curated Finetunes for global genres (Afro House, more)
- **Variant generation**: the ElevenLabs web app generates 1–4 variants from a single prompt. API support unconfirmed as of v4.2.1 — flagged for investigation when ElevenLabs is refactored into a `ProviderBackend`.

## Canonical constraints

- `duration_ms: {min: 3000, max: 300000}` — 3 seconds to 5 minutes

## Pricing

`subscription` mode — billed against the user's ElevenLabs subscription, not per-call USD. `cost_tracker.py` logs usage with $0 per-call cost; dollar totals come from the ElevenLabs dashboard.

## When to use

**ElevenLabs Music (default):**
- Full-length songs with vocals and lyrics
- Multi-lingual vocal tracks
- Brand-consistent music via Finetunes
- Any music need where you have an ElevenLabs subscription

**When to fall back to Lyria:**
- `--negative-prompt` exclusion (Lyria 2)
- Image-inspired music via `reference_images` (Lyria 3 / 3-Pro)
- Pay-per-call economics instead of subscription
- User doesn't have an ElevenLabs subscription

## Future refactor note

In v4.2.1, ElevenLabs Music is called directly from `audio_pipeline.py` without going through the `ProviderBackend` abstraction. A future sub-project refactors these into `scripts/backends/_elevenlabs.py` implementing `ProviderBackend`, unifying the audio surface with the video / image surfaces. The registry entry's `(direct)` sentinel slug is the placeholder for this.

## Music bake-off queued (post-sub-project-C)

A 4-way listening-test bake-off comparing ElevenLabs Music vs Lyria 3 Clip vs Lyria 3 Pro vs Suno (via Kie.ai) is planned for after sub-project C ships. Methodology in `ROADMAP.md` § Music bake-off.

## Authoritative source

`dev-docs/elevenlabs-music.md`
```

- [ ] Commit.

### Task 29: Update `references/providers/replicate.md`

**Files:**
- Modify: `references/providers/replicate.md`

- [ ] **Step 1: Add VEO + Lyria to the hosted-models list**

Find the "hosted models" section (or "pricing modes" section). Append:

```markdown
## v4.2.1 additions — VEO 3.1 + Lyria family

### VEO 3.1 (all three tiers)
- `google/veo-3.1-lite` — pricing mode `per_second_by_resolution`; $0.05/s (720p) or $0.08/s (1080p, 8s req'd); audio always on
- `google/veo-3.1-fast` — pricing mode `per_second_by_audio`; $0.15/s (with audio) or $0.10/s (without)
- `google/veo-3.1` — pricing mode `per_second_by_audio`; $0.40/s (with audio) or $0.20/s (without); 4K output + video extension

### Lyria family
- `google/lyria-2` — `per_call` $0.06; 30s fixed; negative_prompt + seed supported
- `google/lyria-3` — `per_call` $0.04; 30s fixed; reference_images supported (up to 10)
- `google/lyria-3-pro` — `per_call` $0.08; up to 3 min; structure tags + custom lyrics + timestamp control

## v4.2.1 pricing corrections

Kling v3 Video and Kling v3 Omni were originally seeded with `per_second: $0.02/s` in v4.2.0 — an outdated figure carried forward from `cost_tracker.py`. v4.2.1 corrects both with the verified Replicate rates:

- `kwaivgi/kling-v3-video` — `per_second_by_resolution_and_audio`
  - 720p: $0.168/s (no-audio) | $0.252/s (with-audio)
  - 1080p: $0.224/s (no-audio) | $0.336/s (with-audio)

- `kwaivgi/kling-v3-omni-video` — `per_second_by_resolution_and_audio` (slightly cheaper on audio than v3 Video)
  - 720p: $0.168/s (no-audio) | $0.224/s (with-audio)
  - 1080p: $0.224/s (no-audio) | $0.28/s (with-audio)

## New pricing modes introduced in v4.2.1

`cost_tracker.py::_lookup_cost()` gains three modes:

| Mode | Used by | Keying |
|---|---|---|
| `per_second_by_resolution` | VEO 3.1 Lite | resolution string → rate |
| `per_second_by_audio` | VEO 3.1 Fast + Standard | audio_enabled bool → rate |
| `per_second_by_resolution_and_audio` | Kling v3 + v3 Omni | (resolution, audio_enabled) → rate |

All three multiply the selected rate by `duration_s`.
```

- [ ] **Step 2: Commit**

```bash
git add references/providers/replicate.md
git commit -m "docs: update Replicate provider reference for v4.2.1

Added hosted-models entries for VEO 3.1 Lite/Fast/Standard and the
Lyria 2/3/3-Pro family. Documented the Kling v3 + v3 Omni pricing
corrections and the three new pricing modes
(per_second_by_resolution, per_second_by_audio,
per_second_by_resolution_and_audio)."
```

---

## Phase 10 — Meta-documentation updates

### Task 30: Update `CLAUDE.md` — key constraints + architecture notes

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add v4.2.1 entries to the "Key constraints" section**

Find the bottom of the `## Key constraints` section. Append:

```markdown
- **v4.2.1 Vertex retirement complete.** `skills/create-video/scripts/_vertex_backend.py` is deleted. VEO 3.1 (Lite/Fast/Standard) routes through `ReplicateBackend` via `google/veo-3.1-*` slugs. Lyria 2 → Lyria 3 upgraded as the within-Lyria default, with Lyria 2 and Lyria 3 Pro also registered. Audio_pipeline.py's Lyria code routes through `ReplicateBackend`; ElevenLabs code paths are untouched. The config migration shim in `setup_mcp.py` still reads legacy `vertex_*` keys (harmless — nothing consumes them).

- **v4.2.1 multi-model principle codified.** Every model family in the registry MUST register at least 2 models. Rationale: every previous default has been dethroned eventually (v3.8.0 Kling dethroned VEO; v3.8.3 ElevenLabs dethroned Lyria), so pre-registering alternatives means "new default" is a registry-entry change, not a code change. Image family currently has only one text-to-image model (nano-banana-2) — will get a second in sub-project C when Kie.ai brings Imagen/Seedream/Flux.

- **v4.2.1 Lyria auto-routing rule.** Within the Lyria family, `audio_pipeline.py::resolve_lyria_version()` picks Lyria 2 / 3 / 3-Pro based on flags + prompt content. Precedence: explicit `--lyria-version` > `--negative-prompt` (routes to Lyria 2) > `detect_lyrics_intent(prompt)` (routes to Lyria 3 Pro, requires `--confirm-upgrade`) > default Lyria 3 Clip. Auto-upgrade to Pro is HARD-GATED: without `--confirm-upgrade`, the pipeline aborts with a 3-option help message. Prevents silent 2x cost surprises.

- **v4.2.1 Kling pricing correction.** The v4.2.0 registry seeded Kling v3 with `per_second: $0.02/s` — incorrect (outdated source). Actual rates are 10-17x higher. v4.2.1 corrects to `per_second_by_resolution_and_audio` mode with verified rates from `dev-docs/kwaivgi-kling-v3-video-llms.md`. Kling v3 Omni rates similarly corrected (slightly cheaper on audio). This inverts the v3.8.0 "Kling 7.5x cheaper than VEO" claim — at verified rates, VEO Lite is ~4x cheaper than Kling at 1080p with audio. Queued: post-sub-project-C re-evaluation bake-off.

- **v4.2.1 three new pricing modes** in `cost_tracker.py`:
  - `per_second_by_resolution` — keyed by resolution string (VEO Lite)
  - `per_second_by_audio` — keyed by audio_enabled bool (VEO Fast + Standard)
  - `per_second_by_resolution_and_audio` — two-dimensional (Kling v3 + v3 Omni)
  Callers pass `resolution`, `audio_enabled`, and `duration_s` as kwargs to `cost_tracker._lookup_cost()`.

- **v4.2.1 canonical schema extension.** `scripts/backends/_canonical.py::validate_canonical_params` now accepts `duration_s: {enum: [...]}` as an alternative to `{min, max, integer}`. VEO uses enum `{4, 6, 8}`; Kling/Fabric/DreamActor continue using range. Mutually exclusive — backend picks based on which key is present.

- **v4.2.1 per-model param filtering in ReplicateBackend.** When a canonical request carries params that the specific model doesn't support (e.g., `negative_prompt` passed to Lyria 3), `_filter_unsupported_params()` silently drops them and logs a WARN via `_logger`. Callers can pass rich canonical payloads without knowing every model's exact surface. Drop table is `_MODEL_PARAM_DROPS` in `scripts/backends/_replicate.py`.
```

- [ ] **Step 2: Update file responsibilities table**

Find the file responsibilities table (starts around line 67 in CLAUDE.md). Update:

- DELETE the row for `skills/create-video/scripts/_vertex_backend.py` (file no longer exists).

- UPDATE the row for `scripts/registry/models.json` to note the expanded catalog: "12 canonical model entries: kling-v3, kling-v3-omni, fabric-1.0, dreamactor-m2.0, recraft-vectorize, nano-banana-2, veo-3.1-lite/fast/standard (v4.2.1), lyria-2/3/3-pro (v4.2.1), elevenlabs-music (v4.2.1 with (direct) sentinel slug)."

- UPDATE the row for `scripts/backends/_canonical.py`: "image normalizer + constraint validator (duration_s supports both `{min,max,integer}` and `{enum: [...]}` shapes as of v4.2.1)."

- UPDATE the row for `scripts/backends/_replicate.py`: "Replicate provider backend. v4.2.1 adds the `music-generation` task for Lyria routing and per-model param filtering via `_MODEL_PARAM_DROPS`. VEO 3.1 tiers route here after v4.2.1 Vertex retirement."

- UPDATE the row for `skills/create-video/scripts/audio_pipeline.py`: "v4.2.1 — Lyria code refactored to route through `ReplicateBackend`. New helpers: `detect_lyrics_intent()`, `resolve_lyria_version()`, `LyriaUpgradeGateError`. New CLI flags: `--lyria-version {2,3,3-pro}`, `--confirm-upgrade`. ElevenLabs code paths untouched."

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with v4.2.1 key constraints + file responsibilities

7 new Key constraints entries: Vertex retirement complete, multi-model
principle codified, Lyria auto-routing rule, Kling pricing correction,
three new pricing modes, canonical schema extension (duration_s.enum),
per-model param filtering.

File responsibilities table updated: deleted _vertex_backend.py row,
expanded registry entry to 12 canonical models, noted the v4.2.1
changes to _canonical.py, _replicate.py, and audio_pipeline.py."
```

### Task 31: Add Session 25 to `PROGRESS.md`

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Find the most recent session entry + append new session**

Before the `## Expansion Roadmap` section, above Session 24, add:

```markdown
### Session 25 (2026-04-23 → YYYY-MM-DD, continuing from Session 24) — v4.2.1 Sub-Project B: Vertex Retirement + Lyria 3 Upgrade

**Scope**: Finish the Vertex AI retirement started in v4.2.0. Delete `_vertex_backend.py` (958 lines). Route VEO 3.1 (all three tiers) through `ReplicateBackend` via `google/veo-3.1-*` slugs. Migrate `audio_pipeline.py` Lyria code from inline Vertex URL construction to `ReplicateBackend.submit()`. Upgrade Lyria 2 → Lyria 3 as within-Lyria default. Keep Lyria 2 registered for `negative_prompt` workflows. Add Lyria 3 Pro as a first-class model for full-song generation. Register ElevenLabs Music in the registry (with `(direct)` sentinel slug) to honor the multi-model principle even though ElevenLabs isn't yet a `ProviderBackend`.

**Design process**: 1 round of scope refinement in brainstorming session (spec at `docs/superpowers/specs/2026-04-23-subproject-b-vertex-retirement-lyria-upgrade-design.md`, 4 iterations). User confirmed the full Vertex+Lyria scope (not just VEO), the `--confirm-upgrade` hard-gate for auto-routing, and the multi-model principle. Kling v3 pricing correction surfaced during the spec review when the user shared `dev-docs/kwaivgi-kling-v3-video-llms.md` — the registry's `$0.02/s` figure was wrong; actual rates are 10-17x higher.

**What shipped**:

1. `scripts/backends/_canonical.py` — new `duration_s.enum` validator shape
2. `skills/create-image/scripts/cost_tracker.py` — three new pricing modes:
   `per_second_by_resolution`, `per_second_by_audio`,
   `per_second_by_resolution_and_audio`. `_lookup_cost()` signature
   extended with `duration_s` and `audio_enabled` kwargs.
3. `scripts/registry/models.json` — 7 new entries (VEO x3, Lyria x3, ElevenLabs Music) + 2 pricing corrections (Kling v3, v3 Omni) + `family_defaults.music = "elevenlabs-music"`.
4. `scripts/backends/_replicate.py` — `_TASK_PARAM_MAPS` gains `music-generation`; new `_MODEL_PARAM_DROPS` table drives per-model param filtering with WARN logging.
5. `skills/create-video/scripts/audio_pipeline.py` — `generate_music_lyria` + `generate_music_lyria_extended` refactored to use `ReplicateBackend`. New helpers: `detect_lyrics_intent()`, `resolve_lyria_version()`, `LyriaUpgradeGateError`. New CLI flags: `--lyria-version {2,3,3-pro}`, `--confirm-upgrade`.
6. `skills/create-video/scripts/video_generate.py` — Vertex import removed; `_select_backend()` simplified to `gemini`/`replicate`; `--backend vertex-ai` deprecated with auto-routing to Replicate; legacy Vertex model IDs (`veo-3.1-generate-001` etc.) auto-translate to Replicate slugs with deprecation warning.
7. `skills/create-image/scripts/setup_mcp.py` — Vertex CLI flags removed (`--vertex-api-key`, `--vertex-project`, `--vertex-location`). Migration shim for old config keys preserved.
8. `skills/create-video/scripts/_vertex_backend.py` — DELETED (958 lines).
9. Reference docs: `references/models/veo-3.1.md` (replaced placeholder with real content), new `lyria-2.md`, `lyria-3.md`, `lyria-3-pro.md`, `elevenlabs-music.md`. `references/providers/replicate.md` updated with VEO + Lyria + pricing modes.
10. Tests: new `tests/test_lyria_migration.py` (15 tests for detect_lyrics_intent + resolve_lyria_version). New `tests/test_cost_tracker.py` (11 tests for the three new pricing modes). Extensions to `test_canonical.py`, `test_registry.py`, `test_replicate_backend.py`. Total: ~120 tests (up from 74).

**Behavior changes for users**:

- `--music-source lyria` without `--lyria-version` now produces output from **Lyria 3 Clip** (via Replicate) instead of Lyria 2 (via Vertex). Cost drops from $0.06 to $0.04 per 30s clip. User may notice subtle quality difference — bake-off will quantify.
- `--music-source lyria --negative-prompt "drums"` auto-selects Lyria 2 (only variant that accepts `negative_prompt`). Keeps the exclusion feature alive.
- `--music-source lyria` with a prompt containing `[Verse]`, `[Chorus]`, or timestamp ranges aborts with a `LyriaUpgradeGateError` unless `--confirm-upgrade` is passed. Auto-routing would use Lyria 3 Pro at 2x the cost of Clip — user has to acknowledge explicitly.
- `--provider veo` still works but logs deprecation; routes through Replicate via `google/veo-3.1-fast`. Removed in v4.3.0.
- `--backend vertex-ai` same behavior. Removed in v4.3.0.
- Users with Vertex config (`vertex_api_key`, etc. in `~/.banana/config.json`) see zero errors. Keys are migrated to `providers.vertex.*` by the v4.2.0 shim and harmlessly ignored.

**Surprise finding — Kling pricing inversion**:

The v3.8.0 spike 5 narrative was "Kling v3 is 7.5x cheaper than VEO at comparable quality." That claim was based on `$0.02/s` for Kling, which turned out to be wrong (carried forward from an outdated source). At verified Replicate rates:

| 8s @ 1080p with audio | Cost |
|---|---|
| VEO 3.1 Lite | $0.64 |
| VEO 3.1 Fast | $1.20 |
| Kling v3 pro-audio | $2.69 |
| VEO 3.1 Standard | $3.20 |

VEO Lite is ~4× **cheaper** than Kling at comparable settings. Doesn't change v4.2.1's default (Kling quality still wins per the playback-verified 8-of-15 shot-type scoreboard), but queues a post-sub-project-C re-evaluation bake-off. The quality side might have changed too as VEO 3.1 shipped since spike 5.

**Session spend**: $0 (all tests HTTP-mocked; no real generation). **Cumulative: ~$1.10**.
```

- [ ] **Step 2: Commit**

```bash
git add PROGRESS.md
git commit -m "docs: add PROGRESS.md Session 25 entry for v4.2.1"
```

### Task 32: Update `ROADMAP.md`

**Files:**
- Modify: `ROADMAP.md`

- [ ] **Step 1: Mark sub-project B as shipped + add new queued items**

Find the row for `10n-B | v4.2.1 — **Vertex retirement ...` in the Priority Summary table. Change its status column from `**Next**` to `**✅ Shipped 2026-04-XX**` (fill in actual date).

Find row `10k-omg` / `10n-B` (wherever sub-project B is tracked) and add a follow-up row below it:

```markdown
| 10n-B-bake | v4.3.x+ — **Kling v3 vs VEO 3.1 Lite bake-off re-evaluation**. Triggered by v4.2.1 pricing correction: at verified rates, VEO Lite is ~4x CHEAPER than Kling at 1080p with audio. Original v3.8.0 spike 5 scoreboard assumed Kling was cheaper; with that premise inverted, a fresh 15-shot-type quality comparison is justified. Possible outcomes: (a) Kling quality still wins decisively → keep default, note VEO Lite as cost-optimized opt-in; (b) VEO Lite quality within 1-2 shots → flip default; (c) VEO Lite wins outright → flip default and promote to primary. | Medium | Medium | Queued (post-C) |
| 10n-C-music-bake | v4.3.x+ — **4-way music bake-off post-Suno**. Contenders: ElevenLabs Music, Lyria 3 Clip, Lyria 3 Pro, Suno (Kie.ai). 2-part methodology: Part 1 instrumental × 12 genres; Part 2 full songs with lyrics × 6 archetypes. Ideal-prompt format per contender to avoid handicapping. Methodology carries v3.7.2 F13: subjective listening only, not benchmark scores. Depends on sub-project C shipping Suno access. | Medium | Medium | Queued (post-C) |
| 10n-motion | v4.3.x+ — **Register Kling 3.0 motion-control**. `kwaivgi/kling-v3-motion-control` — transfers motion from a reference video onto a character from a reference image. $0.07/s (std) or $0.12/s (pro). Different canonical task shape than existing image-to-video; needs canonical-schema extension. Out of scope for B; registered as a future candidate. | Small | Low | Queued |
```

- [ ] **Step 2: Commit**

```bash
git add ROADMAP.md
git commit -m "docs: ROADMAP updates for v4.2.1 ship + post-C bake-off queue

- Mark sub-project B (v4.2.1) as shipped
- Queue Kling vs VEO Lite re-evaluation bake-off (triggered by v4.2.1
  pricing correction — VEO Lite is now ~4x cheaper than Kling at
  comparable settings, inverting the v3.8.0 cost narrative)
- Queue 4-way music bake-off (ElevenLabs / Lyria 3 Clip / Lyria 3 Pro /
  Suno) for post-sub-project-C
- Queue Kling 3.0 motion-control registration as future candidate"
```

---

## Phase 11 — Release (version bump → merge → tag → push → GitHub release)

### Task 33: Version bump across 3 files

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `README.md`
- Modify: `CITATION.cff`

- [ ] **Step 1: Bump plugin.json**

Open `.claude-plugin/plugin.json`. Change `"version"` from `"4.2.0"` to `"4.2.1"`.

- [ ] **Step 2: Bump README badge**

Open `README.md`. Find the line:

```markdown
[![Version](https://img.shields.io/badge/version-4.2.0-coral)](CHANGELOG.md)
```

Change `4.2.0` to `4.2.1`.

- [ ] **Step 3: Bump CITATION.cff**

Open `CITATION.cff`. Change:

```yaml
version: "4.2.0"
date-released: "2026-04-23"
```

to:

```yaml
version: "4.2.1"
date-released: "YYYY-MM-DD"   # fill in actual release date
```

### Task 34: Add CHANGELOG v4.2.1 entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Insert new entry at the top of the version list**

Below the intro paragraph, BEFORE the existing `## [4.2.0]` entry, add:

```markdown
## [4.2.1] - YYYY-MM-DD

### Headline

**Vertex AI retired. VEO 3.1 and Lyria 3 both on Replicate.** Sub-project B of the multi-provider roadmap. `_vertex_backend.py` deleted (958 lines). VEO 3.1 (all three tiers) routes through `ReplicateBackend` via `google/veo-3.1-*`. Lyria upgraded from Lyria 2 (Vertex) to Lyria 3 Clip (Replicate) as within-Lyria default — cheaper, newer, image-input support. Lyria 2 kept for `negative_prompt` workflows. Lyria 3 Pro registered for full-song generation. Zero user-visible behavior change for non-Vertex flows.

### Added

- **Three VEO 3.1 tiers** in the model registry: `veo-3.1-lite`, `veo-3.1-fast`, `veo-3.1`. All route through `ReplicateBackend`. Correct pricing per tier with resolution-keyed (Lite) and audio-keyed (Fast, Standard) modes.
- **Three Lyria variants** in the model registry: `lyria-2` ($0.06/clip, 30s, negative_prompt), `lyria-3` ($0.04/clip, 30s, reference_images), `lyria-3-pro` ($0.08/file, up to 3 min, structure tags + custom lyrics + timestamp control).
- **ElevenLabs Music** registered in the registry with `(direct)` sentinel slug — honoring the multi-model principle while the ElevenLabs backend refactor is deferred to a future sub-project.
- **Three new pricing modes** in `cost_tracker.py`:
  - `per_second_by_resolution` — keyed by resolution string
  - `per_second_by_audio` — keyed by audio_enabled bool
  - `per_second_by_resolution_and_audio` — two-dimensional
- **Canonical schema extension** — `_canonical.py::validate_canonical_params` accepts `duration_s: {enum: [...]}` as an alternative to `{min, max, integer}`. VEO uses enum; Kling / Fabric / DreamActor continue using range.
- **`music-generation` task type** wired into `ReplicateBackend._TASK_PARAM_MAPS`. Canonical params: `prompt`, `negative_prompt`, `reference_images`, `seed`. Per-model filtering via `_MODEL_PARAM_DROPS` silently drops unsupported params with WARN log.
- **Lyria auto-routing helpers** in `audio_pipeline.py`: `detect_lyrics_intent()`, `resolve_lyria_version()`, `LyriaUpgradeGateError`. Pattern-match song-structure markers to route between Lyria 3 Clip and Pro. Hard-gated via `--confirm-upgrade` flag to prevent silent 2x cost surprises.
- **New CLI flags** on `audio_pipeline.py music` and `pipeline` subcommands:
  - `--lyria-version {2,3,3-pro}` — force a specific Lyria variant
  - `--confirm-upgrade` — acknowledge 2x cost when auto-detection would upgrade to Pro
- **Test suite grew from 74 to ~120 tests** — stdlib `unittest`, zero new dependencies. New files: `test_lyria_migration.py`, `test_cost_tracker.py`.
- **Reference docs** for all new models:
  - `references/models/veo-3.1.md` — replaced v4.2.0 placeholder with full content
  - `references/models/lyria-2.md`, `lyria-3.md`, `lyria-3-pro.md`
  - `references/models/elevenlabs-music.md`

### Changed

- **`audio_pipeline.py` Lyria paths** — `generate_music_lyria` and `generate_music_lyria_extended` rewritten to use `ReplicateBackend.submit/poll/parse_result` instead of inline Vertex URL construction. Default within-Lyria model changes from Lyria 2 (`lyria-002`) to Lyria 3 Clip.
- **`video_generate.py` backend selector** — `_select_backend()` returns `gemini` or `replicate` only; the `vertex` branch is gone. `--backend vertex-ai` and `--provider veo` become deprecation aliases that auto-route to Replicate with deprecation warnings. Legacy Vertex model IDs (`veo-3.1-generate-001` etc.) auto-translate to Replicate slugs.
- **Kling v3 and v3 Omni pricing corrected** in the registry and `cost_tracker.py`. v4.2.0 shipped with `per_second: $0.02/s` from an outdated source; v4.2.1 uses `per_second_by_resolution_and_audio` with verified rates from `dev-docs/kwaivgi-kling-v3-*-llms.md`. See the Notes section below for the cost-narrative implication.
- **`setup_mcp.py`** — Vertex CLI flags (`--vertex-api-key`, `--vertex-project`, `--vertex-location`) removed. Config migration shim unchanged: existing users' `vertex_*` keys are still read into `providers.vertex.*` for graceful upgrade (harmless — nothing consumes them).
- **`family_defaults.music`** in registry set to `elevenlabs-music` (matches v3.8.3 12-0 bake-off verdict).

### Deprecated

- **`--backend vertex-ai`** (in `video_generate.py`) — honored for one release; removed in v4.3.0.
- **`--provider veo`** (in `video_generate.py`) — honored for one release; removed in v4.3.0. Users should pass `--provider replicate --model {veo-3.1-lite,veo-3.1-fast,veo-3.1}` explicitly.
- **Legacy Vertex model IDs** (`veo-3.1-generate-001` etc.) — auto-translate to Replicate slugs with deprecation warning; translation removed in v4.3.0.

### Removed

- **`skills/create-video/scripts/_vertex_backend.py`** — 958 lines. Every consumer migrated to `ReplicateBackend` in prior commits. Verified no imports remain.
- **Vertex setup CLI flags** in `setup_mcp.py`.
- **Inline `aiplatform.googleapis.com` URL construction** in `audio_pipeline.py`.

### Preserved (deliberately)

- **`~/.banana/` config directory path** — unchanged. Queued as v4.2.2 separately.
- **ElevenLabs TTS / music / voice-design code** — untouched. ElevenLabs-as-ProviderBackend is a future sub-project.
- **Gemini direct (`generate.py`, `edit.py`) code paths** — untouched. Gemini-as-ProviderBackend is a future sub-project.
- **`--music-source elevenlabs` behavior** — identical output for identical input.
- **Existing `--music-source lyria`** users see Lyria 3 Clip by default now instead of Lyria 2. Users who need Lyria 2 pass `--lyria-version 2`.
- **`@ycse/nanobanana-mcp` MCP package** — third-party dependency, not renamed.

### Notes

**Kling pricing correction — cost narrative inverted.** The v3.8.0 decision to default to Kling over VEO was partly justified by a "7.5× cheaper than VEO" claim based on an outdated `$0.02/s` Kling figure. At verified v4.2.1 rates for an 8-second 1080p clip with audio:

| Model | Cost |
|---|---|
| VEO 3.1 Lite | $0.64 |
| VEO 3.1 Fast | $1.20 |
| Kling v3 pro-audio | $2.69 |
| VEO 3.1 Standard | $3.20 |

VEO 3.1 Lite is now ~4× **cheaper** than Kling at comparable settings. Doesn't change v4.2.1's default (Kling's quality advantage per the 8-of-15 shot-type scoreboard stands), but queues a post-sub-project-C bake-off re-evaluation with fresh data.

### Deferred (explicit follow-up releases)

- **v4.2.2 — `~/.banana/` → `~/.creators-studio/` config rename** with auto-migration.
- **v4.3.0 — Sub-project C (Kie.ai backend + Suno music)**. Unlocks the 4-way music bake-off.
- **v4.3.x — Kling-vs-VEO default re-evaluation bake-off** (triggered by the v4.2.1 pricing correction).
- **v4.3.x — 4-way music bake-off** (ElevenLabs / Lyria 3 Clip / Lyria 3 Pro / Suno via Kie.ai), 2-part methodology.
- **v4.3.x+ — Kling 3.0 motion-control** registration as a new canonical task (motion transfer).
- **v4.4.0+ — Sub-project D (Hugging Face Inference Providers)**.

### Design documents

- Architecture spec: `docs/superpowers/specs/2026-04-23-subproject-b-vertex-retirement-lyria-upgrade-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-23-subproject-b-vertex-retirement-lyria-upgrade.md`
```

- [ ] **Step 2: Add link reference at the bottom**

Find the link-reference block at the end of `CHANGELOG.md`. Add above `[4.2.0]: ...`:

```markdown
[4.2.1]: https://github.com/juliandickie/creators-studio/releases/tag/v4.2.1
```

### Task 35: Add README "What's New" entry + architecture diagram update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add v4.2.1 Release History entry**

Find the Release History section with `<details>` blocks. Above the `v4.2.0` entry, add:

```markdown
<details>
<summary><b>🔌 v4.2.1 (current) — Vertex retirement + Lyria 3 upgrade · YYYY-MM-DD</b></summary>

Sub-project B of the provider-agnostic roadmap. Deleted `_vertex_backend.py` (958 lines). VEO 3.1 (all three tiers) and Lyria all route through Replicate now. Lyria upgraded from Lyria 2 → Lyria 3 Clip as the new within-Lyria default (30% cheaper, adds image-input support). Lyria 2 still available for `negative_prompt` workflows via `--lyria-version 2`. Lyria 3 Pro registered for full-song generation with structure tags, auto-selected when prompt contains `[Verse]` / `[Chorus]` / timestamp markers (gated by `--confirm-upgrade` to prevent 2x cost surprises). Bonus: Kling v3 pricing corrected (v4.2.0 figure was 10-17× too low) — VEO Lite turns out to be ~4× cheaper than Kling at 1080p with audio, inverting the v3.8.0 cost narrative. Bake-off to re-evaluate default queued for post-sub-project-C.

</details>
```

Downgrade the v4.2.0 entry from "current" by removing the `(current)` suffix.

- [ ] **Step 2: Update the architecture diagram**

Find the tree diagram in the Architecture section. Update:

- DELETE the line for `_vertex_backend.py` (file no longer exists).
- Update the scripts/ tree to show the expanded models.json catalog:

```
├── scripts/                           # v4.2.0+ shared provider abstraction
│   ├── backends/
│   │   ├── _base.py                   # ProviderBackend ABC + canonical types
│   │   ├── _canonical.py              # Image normalizer + constraint validator (duration_s.enum since v4.2.1)
│   │   └── _replicate.py              # Replicate backend (Kling, VEO, Fabric, Lyria, Recraft)
│   ├── registry/
│   │   ├── models.json                # 12 canonical models across image/video/music families
│   │   └── registry.py                # Typed loader + query API
│   └── routing.py                     # Two-stage model + provider resolution
```

Update `references/models/` list to include the new entries:

```
├── references/
│   ├── providers/
│   │   ├── replicate.md               # Extended v4.2.1 with VEO + Lyria
│   │   └── gemini-direct.md
│   └── models/
│       ├── kling-v3.md, kling-v3-omni.md
│       ├── nano-banana-2.md
│       ├── fabric-1.0.md, dreamactor-m2.0.md
│       ├── recraft-vectorize.md
│       ├── veo-3.1.md                 # v4.2.1 replaced placeholder with full content
│       ├── lyria-2.md, lyria-3.md, lyria-3-pro.md   # v4.2.1
│       └── elevenlabs-music.md        # v4.2.1
```

Update `skills/create-video/scripts/` to remove `_vertex_backend.py`:

```
├── skills/create-video/
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── video_generate.py          # v4.2.1: Vertex removed
│   │   ├── video_sequence.py
│   │   ├── video_lipsync.py
│   │   ├── video_extend.py            # DEPRECATED in v3.8.0
│   │   ├── audio_pipeline.py          # v4.2.1: Lyria via ReplicateBackend
│   │   └── video_stitch.py
│   └── references/                    # 9 video reference guides
```

### Task 36: Final validation

**Files:** (verification only)

- [ ] **Step 1: Version consistency**

```bash
grep -E '"version"|badge/version|^version:' .claude-plugin/plugin.json README.md CITATION.cff
```

Expected: `4.2.1` appears in all three files.

- [ ] **Step 2: Full test suite**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
```

Expected: `Ran ~120 tests, OK`.

- [ ] **Step 3: All scripts load**

```bash
for f in skills/create-video/scripts/video_generate.py \
         skills/create-video/scripts/video_lipsync.py \
         skills/create-video/scripts/video_sequence.py \
         skills/create-video/scripts/audio_pipeline.py \
         skills/create-image/scripts/vectorize.py \
         skills/create-image/scripts/generate.py \
         skills/create-image/scripts/edit.py \
         skills/create-image/scripts/setup_mcp.py; do
  echo "=== $f ==="
  python3 "$f" --help 2>&1 | head -1
done
```

Expected: every script prints a usage line. No import errors.

- [ ] **Step 4: Verify Vertex is gone**

```bash
grep -rn "_vertex_backend\|aiplatform.googleapis.com" . --include="*.py" 2>&1 | grep -v "\.git" | grep -v "^\s*#"
```

Expected: empty. Code references to Vertex should all be gone.

- [ ] **Step 5: Verify registry loads + family defaults**

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from scripts.registry import registry as r
reg = r.load_registry()
reg.validate()
print('Music family:', reg.models_by_family('music'))
print('Video family:', reg.models_by_family('video'))
print('Image family:', reg.models_by_family('image'))
print('Family defaults:', reg.family_defaults)
"
```

Expected:
```
Music family: ['lyria-2', 'lyria-3', 'lyria-3-pro', 'elevenlabs-music']
Video family: ['kling-v3', 'kling-v3-omni', 'fabric-1.0', 'dreamactor-m2.0', 'veo-3.1-lite', 'veo-3.1-fast', 'veo-3.1']
Image family: ['recraft-vectorize', 'nano-banana-2']
Family defaults: {'image': 'nano-banana-2', 'video': 'kling-v3', 'music': 'elevenlabs-music'}
```

- [ ] **Step 6: Commit the release prep**

```bash
git add .claude-plugin/plugin.json README.md CITATION.cff CHANGELOG.md
git commit -m "chore: bump version to 4.2.1

- plugin.json: 4.2.0 -> 4.2.1
- README badge + v4.2.1 Release History <details> entry
- README architecture diagram updated (removed _vertex_backend.py,
  added 5 new model references, expanded registry description)
- CITATION.cff: version + date-released
- CHANGELOG v4.2.1 entry with Added / Changed / Deprecated / Removed
  / Preserved sections and the Kling pricing-correction callout"
```

### Task 37: Scope review → merge → tag → push → release

**Files:** (git operations only)

- [ ] **Step 1: Final test pass + branch clean**

```bash
python3 -m unittest discover tests 2>&1 | tail -3
git status
```

Expected: all tests pass. `nothing to commit, working tree clean` on feature branch.

- [ ] **Step 2: Present scope review to user (per `feedback_release_checkin` memory rule)**

STOP before merging. Summarize for the user:

```
v4.2.1 scope review:
- _vertex_backend.py deleted (958 lines)
- VEO 3.1 all tiers route through Replicate
- Lyria family expanded: Lyria 2 (kept for negative_prompt), Lyria 3
  Clip (new default), Lyria 3 Pro (new — full songs)
- ElevenLabs Music registered in registry with (direct) sentinel
- Kling v3 + v3 Omni pricing corrected (v4.2.0 had wrong numbers)
- Three new pricing modes in cost_tracker.py
- Canonical duration_s.enum shape added
- Per-model param filtering in ReplicateBackend
- Lyria auto-routing with --confirm-upgrade hard gate
- ~120 tests passing (up from 74)
- Zero user-visible behavior change except the Lyria default upgrade

Proceed with merge to main + tag v4.2.1 + push + zip + gh release?
```

Wait for user approval. If changes are requested, address them before continuing.

- [ ] **Step 3: After user approves — merge feature branch to main**

```bash
git checkout main
git merge --no-ff feature/vertex-retirement-v4.2.1 -m "Merge feature/vertex-retirement-v4.2.1: v4.2.1 sub-project B

Vertex AI retired entirely. VEO 3.1 and Lyria route through Replicate
via the v4.2.0 provider abstraction. Lyria upgraded to Lyria 3 as
within-Lyria default; Lyria 2 kept for negative_prompt; Lyria 3 Pro
added for full-song generation.

Zero user-visible behavior change for non-Vertex flows.

Follow-ups queued:
- v4.2.2: ~/.banana/ -> ~/.creators-studio/ config rename
- v4.3.0: Sub-project C (Kie.ai backend + Suno)
- v4.3.x: Kling-vs-VEO re-evaluation bake-off
- v4.3.x: 4-way music bake-off
- v4.4.0+: Sub-project D (HF Inference Providers)"
```

- [ ] **Step 4: Tag v4.2.1**

```bash
git tag -a v4.2.1 -m "v4.2.1 — Vertex Retirement + Lyria 3 Upgrade (Sub-Project B)

Vertex AI is gone. VEO 3.1 (all tiers) and Lyria (2, 3, 3-Pro) route
through the v4.2.0 Replicate abstraction. Lyria 2 -> Lyria 3 Clip
default upgrade (30% cheaper, new image-input capability).

Plus a Kling v3 pricing correction that surfaces a surprising new
datapoint: VEO Lite is now ~4x cheaper than Kling at 1080p with
audio. Bake-off queued for post-sub-project-C.

See CHANGELOG.md for full details."
```

- [ ] **Step 5: Push main + tag**

```bash
git push origin main
git push origin v4.2.1
```

- [ ] **Step 6: Build release zip**

```bash
cd /Users/juliandickie/code/creators-studio-project/creators-studio
rm -f ../creators-studio-v4.2.1.zip
zip -r ../creators-studio-v4.2.1.zip . \
  -x ".git/*" ".DS_Store" "*/.DS_Store" "*__pycache__/*" "*.pyc" \
     ".github/*" "screenshots/*" "PROGRESS.md" "ROADMAP.md" \
     "CODEOWNERS" "CODE_OF_CONDUCT.md" "SECURITY.md" "CITATION.cff" \
     ".gitattributes" ".gitignore" ".claude/*" "spikes/*"
ls -lh ../creators-studio-v4.2.1.zip
```

Expected: zip file produced, size ~550-600 KB.

- [ ] **Step 7: Create GitHub release**

```bash
gh release create v4.2.1 \
  ../creators-studio-v4.2.1.zip \
  --title "v4.2.1 — Vertex Retirement + Lyria 3 Upgrade" \
  --notes "$(cat <<'EOF'
## Highlights

**Vertex AI retired entirely.** `_vertex_backend.py` deleted (958 lines). VEO 3.1 (Lite/Fast/Standard) and Lyria (2/3/3-Pro) all route through the v4.2.0 provider abstraction via `ReplicateBackend`. Zero behavior change for non-Vertex users.

This is **sub-project B** of the multi-provider roadmap.

## What landed

- **VEO 3.1 × 3 tiers** registered — cost-optimized routing based on tier + audio flag
- **Lyria upgrade** — Lyria 3 Clip as new within-Lyria default (30% cheaper than Lyria 2)
- **Lyria 3 Pro** registered as a first-class model — full-length songs with structure tags + custom lyrics + timestamp control, auto-selected when prompt contains `[Verse]`/`[Chorus]`/timestamp markers (gated by `--confirm-upgrade`)
- **Lyria 2** kept for `negative_prompt` workflows — auto-selected when `--negative-prompt` is passed
- **ElevenLabs Music** registered in the registry (honoring the multi-model principle)
- **Three new pricing modes** for cost tracker: `per_second_by_resolution`, `per_second_by_audio`, `per_second_by_resolution_and_audio`
- **Canonical schema extension** — `duration_s: {enum: [...]}` alongside the existing `{min, max, integer}` shape
- **Per-model param filtering** in ReplicateBackend — canonical requests can carry extras; backend silently drops unsupported with WARN log
- **Lyria auto-routing helpers** with `--confirm-upgrade` hard gate

## Surprise finding — cost narrative inversion

The v3.8.0 spike 5 narrative was "Kling is 7.5× cheaper than VEO." That was based on outdated pricing. At verified v4.2.1 rates for 8s @ 1080p with audio:

| Model | Cost |
|---|---|
| VEO 3.1 Lite | $0.64 |
| VEO 3.1 Fast | $1.20 |
| Kling v3 pro-audio | $2.69 |
| VEO 3.1 Standard | $3.20 |

VEO Lite is actually **~4× cheaper** than Kling at comparable settings. Default stays Kling (quality still wins per the 8/15 shot-type scoreboard), but a fresh bake-off is queued for post-sub-project-C.

## Next up

- **v4.2.2** — `~/.banana/` → `~/.creators-studio/` config dir rename with auto-migration
- **v4.3.0** — Sub-project C: Kie.ai backend + Suno music access
- **v4.3.x** — Kling-vs-VEO Lite default re-evaluation bake-off
- **v4.3.x** — 4-way music bake-off (ElevenLabs / Lyria 3 Clip / Lyria 3 Pro / Suno)

See [CHANGELOG.md](CHANGELOG.md) for full details.
EOF
)"
```

- [ ] **Step 8: Delete feature branch (local + remote)**

```bash
git branch -d feature/vertex-retirement-v4.2.1
git push origin --delete feature/vertex-retirement-v4.2.1 2>/dev/null || echo "(remote branch never pushed — OK)"
```

- [ ] **Step 9: Verify release**

```bash
gh release view v4.2.1 --json tagName,url,assets | python3 -m json.tool
git log --oneline -3
git branch --list
```

Expected: release shows with zip asset; main is at the merge commit; feature branch is gone.

---

## Self-review

### 1. Spec coverage check

| Spec section | Implementation task |
|---|---|
| §2.1 VEO migration — registry | Task 6 |
| §2.1 VEO migration — video_generate.py | Tasks 20–21 |
| §2.1 VEO migration — _vertex_backend.py deletion | Task 23 |
| §2.1 VEO migration — veo-3.1.md real content | Task 24 |
| §2.1 Lyria migration — registry | Task 7 |
| §2.1 Lyria migration — music-generation task | Task 11 |
| §2.1 Lyria migration — audio_pipeline.py refactor | Tasks 15–19 |
| §2.1 Lyria default upgrade | Task 15 `resolve_lyria_version` |
| §2.1 intent-aware routing | Task 15 |
| §2.1 `--lyria-version` + `--confirm-upgrade` flags | Task 19 |
| §2.1 ElevenLabs Music registry stub | Task 7 |
| §2.1 Config migration — remove Vertex CLI | Task 22 |
| §2.1 Documentation — model refs | Tasks 24–28 |
| §2.1 Documentation — provider ref update | Task 29 |
| §2.1 Documentation — bake-off roadmap | Task 32 |
| §2.1 Documentation — CLAUDE.md updates | Task 30 |
| §2.1 Documentation — PROGRESS Session 25 | Task 31 |
| §3.1 Registry entries — exact JSON | Tasks 6, 7, 8, 9 |
| §3.1b `duration_s.enum` canonical | Task 1 |
| §3.1c Three new pricing modes | Tasks 3, 4, 5 |
| §3.1d Kling pricing correction | Tasks 5 + 8 |
| §3.2 `music-generation` task | Task 11 |
| §3.3 lyrics intent routing | Task 15 |
| §3.3 `--confirm-upgrade` hard gate | Tasks 15, 19 |
| §3.4 `audio_pipeline.py` refactor | Tasks 16, 17, 18 |
| §3.5 `video_generate.py` migration | Tasks 20, 21 |
| §3.6 Quiet death for vertex config | Task 22 |
| §4 Multi-model principle | Tasks 7 (registration) + 30 (CLAUDE.md) |
| §5 Pricing mode additions | Tasks 3, 4, 5 |
| §6 Test coverage | Tasks 1, 3, 4, 5, 10, 13, 14, 15 |
| §7 Migration story for users | Tasks 20–22 (flags + shim preservation) |
| §8 Roadmap additions | Task 32 |
| §11 Success criteria | Task 36 (final validation) |

All spec sections have tasks. No gaps.

### 2. Placeholder scan

No `TBD` / `TODO` / "implement later" / "add validation" / "write tests for the above" in the plan. Every step has actual code or exact commands.

### 3. Type consistency

- `resolve_lyria_version` signature: `(prompt: str, *, explicit_version: str | None, confirm_upgrade: bool, has_negative_prompt: bool) -> str` — consistent across Task 15 (definition) + Task 16 (caller) + Task 17 (caller) + `test_lyria_migration.py` tests.
- `LyriaUpgradeGateError` referenced consistently in Task 15 (definition), Task 19 (handler), tests.
- `_MODEL_PARAM_DROPS: dict[str, set[str]]` defined in Task 12; used in Task 13 via mock log assertion.
- `_TASK_PARAM_MAPS["music-generation"]` keys (`prompt`, `negative_prompt`, `reference_images`, `seed`) are the same canonical names used in the registry entries (Task 7) and the tests (Task 13).
- `per_second_by_resolution`, `per_second_by_audio`, `per_second_by_resolution_and_audio` pricing mode strings consistent across Tasks 3, 4, 5 (cost_tracker), Tasks 6, 7, 8 (registry), and Task 10 (registry tests).

### 4. Execution sequencing

Tasks 1–5 (foundation: schema + pricing modes) must complete before Task 6+ (registry entries reference `duration_s.enum` and new pricing modes). Task 11 (music-generation task) must complete before Task 13 (music tests). Task 12 (per-model filtering) before Task 13 (tests assert WARN). Tasks 15–19 (audio_pipeline migration) must precede Task 18 (dead Vertex code deletion). Task 23 (delete `_vertex_backend.py`) must come last among code changes. Tasks 24–32 (docs) can run anytime after the code is stable. Tasks 33–37 (release) MUST come last, gated on user approval for the release step.

