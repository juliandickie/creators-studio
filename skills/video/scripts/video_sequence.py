#!/usr/bin/env python3
"""Banana Claude -- Multi-Shot Sequence Production Pipeline

Break scripts into shot lists, generate storyboard frame pairs using the
image generation API, batch-generate video clips via VEO, and stitch them
together with FFmpeg.  Uses only Python stdlib + subprocess.

Subcommands:
    video_sequence.py plan --script "30-second product launch ad" --target 30
                           [--preset NAME] [--output shot-list.json]
    video_sequence.py storyboard --plan shot-list.json [--api-key KEY]
                                  [--output DIR]
    video_sequence.py estimate --plan shot-list.json
    video_sequence.py generate --storyboard DIR [--api-key KEY] [--output DIR]
    video_sequence.py stitch --clips DIR --output final.mp4
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# v3.6.2: sequence output lives under ~/Documents/nano-banana-sequences/
# so users can Quick Look (Space key) individual shots from Finder. The
# previous /tmp location was hidden on macOS and forced users to open a
# terminal to inspect their own output.
OUTPUT_BASE = Path.home() / "Documents" / "nano-banana-sequences"
# Kept as a fallback pointer for the legacy location that existed in v3.4.x
# through v3.6.1 — referenced in docs so users of old plans can find them.
LEGACY_OUTPUT_BASE = Path.home() / "Documents" / "nanobanana_generated"
COST_STORYBOARD_FRAME = 0.078   # per 2K frame
AVG_SHOT_DURATION = 7           # seconds, for shot-count estimation
MIN_SHOTS = 2
DEFAULT_SHOT_DURATION = 8
MAX_SHOT_DURATION = 8

# Default model for sequences. Individual shots (shot["model"]) and
# sequence-level overrides (plan["model"]) take precedence over this.
#
# v3.8.0+: Kling v3 Std replaces VEO 3.1 Standard as the default after
# spike 5 decisively proved Kling wins 8 of 15 playback-verified shot
# types to VEO Fast's 0, at 7.5x lower cost. VEO remains callable as an
# opt-in backup via the `veo-backup` quality tier.
DEFAULT_SEQUENCE_MODEL = "kwaivgi/kling-v3-video"
DEFAULT_SEQUENCE_RESOLUTION = "1080p"

# Quality-tier CLI flag maps to concrete model IDs.
#
# v3.8.0: All auto-selected tiers route to Kling v3 Std. Kling's flat
# $0.16/8s (pro mode 1080p) is cheap enough to serve BOTH draft and
# premium tiers — no point in a separate draft tier when the premium
# tier is already ~3x cheaper than VEO Lite. VEO is the only alternative
# and ships as the `veo-backup` tier requiring explicit user opt-in.
#
# Historical note: v3.6.0-v3.7.x used a 5-tier VEO-only ladder (draft,
# fast, standard, lite, legacy). v3.8.0 collapses the draft/fast/standard/
# premium tiers into Kling because the Kling quality delta is invisible
# at most viewing conditions and the cost math no longer justifies the
# split. The `lite` and `legacy` aliases are preserved for backward
# compat with pre-v3.8.0 shot plans but point to Kling, not VEO.
QUALITY_TIER_MODELS = {
    "draft": "kwaivgi/kling-v3-video",        # Kling Std at $0.16/8s
    "fast": "kwaivgi/kling-v3-video",         # same model, same price
    "standard": "kwaivgi/kling-v3-video",     # default tier
    "premium": "kwaivgi/kling-v3-video",      # Kling IS the premium
    # Backward-compat aliases — point to Kling, NOT VEO, per v3.8.0 default
    "lite": "kwaivgi/kling-v3-video",
    "legacy": "kwaivgi/kling-v3-video",
    # Opt-in VEO backup. Requires explicit --quality-tier veo-backup and
    # acknowledgment that spike 5 found VEO's multi-shot workflows produce
    # glitches. VEO Lite is used as the cheapest VEO path; Fast and Standard
    # tier premiums were imperceptible at 1fps sampling (spike 5 Phase 2B).
    "veo-backup": "veo-3.1-lite-generate-001",
}

# Per-clip pricing (v3.8.0+). Kling uses flat-per-clip pricing based on
# duration, not per-second like VEO. The keys below match both VEO model
# IDs (priced per-second) and Kling's slug (priced per-clip). _veo_cost()
# below dispatches on the key shape.
#
# Kling pricing source: Kling v3 Std model card + spike 5 observed costs.
#   8 s @ pro mode (1080p): $0.16
#   15 s @ pro mode (1080p): ~$0.30
#   Approximate linear scaling at ~$0.02/s for the 3-15 range.
_VEO_PER_SECOND = {
    "veo-3.1-generate-preview": 0.40,
    "veo-3.1-generate-001": 0.40,
    "veo-3.1-fast-generate-preview": 0.15,
    "veo-3.1-fast-generate-001": 0.15,
    "veo-3.1-lite-generate-001": 0.05,
    "veo-3.0-generate-001": 0.15,
}
_KLING_PER_SECOND = {
    # Kling v3 Std at pro mode (1080p) — our default. $0.16/8s = $0.02/s.
    # Slightly higher effective rate at 3-6 s (fixed per-call overhead) but
    # the difference is rounding-noise for the plugin's budget math.
    "kwaivgi/kling-v3-video": 0.02,
}

SHOT_TYPES = (
    "establishing", "content", "medium", "closeup",
    "product", "transition", "cutaway", "broll",
)

# v3.6.3: shot-type semantic defaults. When cmd_plan creates a shot
# skeleton, it looks up the type in this table and pre-fills duration,
# camera hint, and use_veo_interpolation if the fields aren't explicitly
# set. Claude can still override any of these downstream — the defaults
# exist so that a bare `plan --script "..."` produces sensible output
# without Claude having to remember cinematography conventions for
# every shot type.
#
# Rationale per field:
#   duration — cinematographer rule of thumb for how long each shot
#              type reads on screen before the viewer loses interest
#   camera_hint — starting-point camera move; Claude refines it
#   use_veo_interpolation — True for shots that cut away to unrelated
#              material, where pinning an end frame over-constrains
#              the motion (validated by the coffee shop demo Shot 1)
SHOT_TYPE_DEFAULTS = {
    "establishing": {
        "duration": 8,
        "camera_hint": "slow dolly forward or wide aerial reveal",
        "use_veo_interpolation": True,  # cuts to unrelated next shot
    },
    "content": {
        "duration": 8,
        "camera_hint": "static medium shot or subtle handheld",
        "use_veo_interpolation": False,
    },
    "medium": {
        "duration": 6,
        "camera_hint": "static medium shot with gentle rack focus",
        "use_veo_interpolation": False,
    },
    "closeup": {
        "duration": 6,
        "camera_hint": "tight close-up, shallow depth of field",
        "use_veo_interpolation": False,
    },
    "product": {
        "duration": 8,
        "camera_hint": "slow orbit or push-in with macro framing",
        "use_veo_interpolation": False,
    },
    "transition": {
        "duration": 4,
        "camera_hint": "whip pan, match cut, or light flare transition",
        "use_veo_interpolation": True,  # by definition bridges two different shots
    },
    "cutaway": {
        "duration": 4,
        "camera_hint": "brief detail insert, static or slow push",
        "use_veo_interpolation": True,
    },
    "broll": {
        "duration": 6,
        "camera_hint": "handheld or drifting observational",
        "use_veo_interpolation": True,
    },
}


def _shot_defaults(shot_type):
    """Return the default field dict for a given shot type.

    Falls back to the "content" defaults when the type is unknown so
    that hand-edited plans with non-canonical type labels still get
    sensible behavior instead of KeyError.
    """
    return SHOT_TYPE_DEFAULTS.get(shot_type, SHOT_TYPE_DEFAULTS["content"])


def _veo_cost(model, duration_seconds):
    """Local per-clip cost lookup. Mirrors cost_tracker._veo_cost but
    stdlib-only, and v3.8.0+ handles both Kling (slug with "/") and VEO
    (plain model ID) rates. Returns None for unknown models so callers can
    decide whether to treat unknown as zero-cost or opaque."""
    # Kling: model slug contains "/"
    if "/" in model:
        rate = _KLING_PER_SECOND.get(model)
        if rate is None:
            return None
        return round(rate * duration_seconds, 4)
    # VEO: plain model ID
    rate = _VEO_PER_SECOND.get(model)
    if rate is None:
        return None
    return round(rate * duration_seconds, 4)


def _resolve_shot_model(shot, plan, override=None):
    """3-level cascade: CLI override → shot["model"] → plan["model"] → default."""
    return (
        override
        or shot.get("model")
        or plan.get("model")
        or DEFAULT_SEQUENCE_MODEL
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_exit(message):
    """Print JSON error to stdout and exit."""
    print(json.dumps({"error": True, "message": message}))
    sys.exit(1)


def _progress(data):
    """Print progress JSON to stderr."""
    print(json.dumps(data), file=sys.stderr)


def _load_api_key(cli_key):
    """Load API key: CLI -> env -> config.json."""
    api_key = (
        cli_key
        or os.environ.get("GOOGLE_AI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not api_key:
        config_path = Path.home() / ".banana" / "config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    api_key = json.load(f).get("google_ai_api_key", "")
            except (json.JSONDecodeError, OSError):
                pass
    if not api_key:
        _error_exit(
            "No API key. Run /banana setup, set GOOGLE_AI_API_KEY env, "
            "or pass --api-key"
        )
    return api_key


def _load_plan(path):
    """Load a shot-list JSON plan from *path*."""
    p = Path(path)
    if not p.exists():
        _error_exit(f"Plan file not found: {path}")
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        _error_exit(f"Failed to read plan: {exc}")


def _save_plan(path, plan):
    """Write *plan* dict to *path* as formatted JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(plan, f, indent=2)
    return str(p.resolve())


def _default_output(suffix, project_name=None):
    """Return a timestamped output directory under OUTPUT_BASE.

    v3.6.2: if *project_name* is set, the layout is

        ~/Documents/nano-banana-sequences/<project_name>/<suffix>/

    so all stages of a single project (plan / storyboard / clips /
    final.mp4) cluster under one directory visible from Finder.
    If *project_name* is None (e.g. ad-hoc runs without a named
    project), fall back to the timestamped sibling layout:

        ~/Documents/nano-banana-sequences/sequence_<suffix>_<ts>/
    """
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    if project_name:
        return str(OUTPUT_BASE / _sanitize_project_name(project_name) / suffix)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(OUTPUT_BASE / f"sequence_{suffix}_{ts}")


def _sha256_file(path):
    """Return SHA-256 hex digest of *path*, or None if it doesn't exist.

    Used by the v3.6.3 plan-hash-tracking pipeline to detect when a frame
    has been regenerated since the last review. Reads in 64 KB chunks so
    large PNG files don't blow up memory.
    """
    import hashlib
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# v3.6.3: the review sheet embeds a machine-readable footer block
# containing the plan path, the storyboard dir, and the SHA-256 of
# each frame at the time the review was generated. cmd_generate reads
# this block and compares against current frame hashes on disk; if
# any differ, the review is "stale" and generate aborts unless
# --skip-review is passed. The block is wrapped in HTML comments so
# it doesn't render in markdown previews.
REVIEW_SHEET_MANIFEST_START = "<!-- BEGIN REVIEW MANIFEST v1 -->"
REVIEW_SHEET_MANIFEST_END = "<!-- END REVIEW MANIFEST v1 -->"


def _parse_review_manifest(review_sheet_text):
    """Extract the embedded machine-readable manifest block from a review sheet.

    Returns a dict with keys `plan`, `storyboard_dir`, `frames`
    (mapping shot number → {"start": sha256, "end": sha256|null}), or
    None if no manifest block is found. Unknown keys are preserved so
    future versions can add fields without breaking old parsers.
    """
    start = review_sheet_text.find(REVIEW_SHEET_MANIFEST_START)
    end = review_sheet_text.find(REVIEW_SHEET_MANIFEST_END)
    if start < 0 or end < 0 or end <= start:
        return None
    block = review_sheet_text[start + len(REVIEW_SHEET_MANIFEST_START):end]
    # The block is wrapped in an HTML comment so markdown previews
    # ignore it. Inside is a fenced code block with the JSON payload.
    # We tolerate either a raw JSON body or one wrapped in ```json fences.
    block = block.strip()
    if block.startswith("```json"):
        block = block[len("```json"):].strip()
    if block.endswith("```"):
        block = block[:-len("```")].strip()
    if block.startswith("```"):
        block = block[len("```"):].strip()
    try:
        return json.loads(block)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_review_manifest(plan, storyboard_dir, plan_path):
    """Build the machine-readable manifest dict embedded in REVIEW-SHEET.md.

    Called by _build_review_sheet. Records the current plan path, the
    storyboard dir, and a per-shot frame-hash map. cmd_generate compares
    this against current disk state to detect stale reviews.
    """
    storyboard_path = Path(storyboard_dir).resolve()
    frames = {}
    for shot in plan.get("shots", []):
        num = shot["number"]
        start_file = storyboard_path / f"start-{num:02d}.png"
        end_file = storyboard_path / f"end-{num:02d}.png"
        use_interpolation = bool(shot.get("use_veo_interpolation"))
        frames[str(num)] = {
            "start": _sha256_file(start_file),
            "end": None if use_interpolation else _sha256_file(end_file),
            "use_veo_interpolation": use_interpolation,
        }
    return {
        "version": 1,
        "plan": str(Path(plan_path).resolve()),
        "storyboard_dir": str(storyboard_path),
        "frames": frames,
    }


def _load_review_manifest(storyboard_dir):
    """Read REVIEW-SHEET.md from *storyboard_dir* and return its manifest.

    Returns None if no review sheet exists or the manifest can't be parsed.
    Callers should treat None as "no valid review" and either abort
    (cmd_generate without --skip-review) or skip the check.
    """
    review_path = Path(storyboard_dir) / "REVIEW-SHEET.md"
    if not review_path.exists():
        return None
    try:
        with open(review_path) as f:
            text = f.read()
    except OSError:
        return None
    return _parse_review_manifest(text)


def _check_review_freshness(plan, storyboard_dir):
    """Compare the current disk state against the embedded review manifest.

    Returns a dict:
        {"status": "ok"}                  — review is fresh, proceed
        {"status": "missing"}             — no REVIEW-SHEET.md at all
        {"status": "unparseable"}         — review exists but manifest can't be read
        {"status": "stale",
         "drifted_shots": [1, 3]}         — frame hashes differ for these shots

    Intended for cmd_generate's gate check. Callers translate the
    returned status into either a progress event (ok) or an _error_exit
    (anything else) unless --skip-review is set.
    """
    manifest = _load_review_manifest(storyboard_dir)
    if manifest is None:
        return {"status": "missing"}
    if not isinstance(manifest, dict) or "frames" not in manifest:
        return {"status": "unparseable"}

    current = _build_review_manifest(plan, storyboard_dir, manifest.get("plan", ""))
    drifted = []
    for num_str, recorded in manifest.get("frames", {}).items():
        now = current["frames"].get(num_str)
        if now is None:
            drifted.append(int(num_str))
            continue
        if recorded.get("start") != now.get("start"):
            drifted.append(int(num_str))
            continue
        # end can legitimately be None (use_veo_interpolation)
        if recorded.get("end") != now.get("end"):
            drifted.append(int(num_str))
            continue

    if drifted:
        return {"status": "stale", "drifted_shots": sorted(set(drifted))}
    return {"status": "ok"}


def _parse_shots_filter(spec):
    """Parse a `--shots 1,3,5` or `--shots 2-4` filter into a set of ints.

    Returns None when *spec* is None/empty (meaning "all shots").
    Accepts comma-separated values and hyphen ranges, e.g. "1,3-5,7".
    Raises _error_exit on garbled input so typos surface immediately.
    """
    if not spec:
        return None
    result = set()
    for piece in spec.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece:
            try:
                lo, hi = piece.split("-", 1)
                lo_i = int(lo.strip())
                hi_i = int(hi.strip())
            except ValueError:
                _error_exit(f"Invalid --shots range '{piece}' (expected e.g. '3-5')")
            if lo_i > hi_i:
                _error_exit(f"Invalid --shots range '{piece}' (low > high)")
            result.update(range(lo_i, hi_i + 1))
        else:
            try:
                result.add(int(piece))
            except ValueError:
                _error_exit(f"Invalid --shots value '{piece}' (expected integer or range)")
    return result or None


def _sanitize_project_name(name):
    """Return a filesystem-safe slug for *name* (kebab-case, alnum only).

    Used by _default_output() to build per-project subdirs. Strips
    anything that isn't [a-zA-Z0-9._-] and lowercases the rest so
    plans with display names like "Golden Bean Cafe — 30s" become
    "golden-bean-cafe-30s" on disk.
    """
    import re
    slug = re.sub(r"[^\w.-]+", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "sequence"


def _run_script(script_path, args, api_key):
    """Run a Python helper script, inject --api-key, return parsed JSON stdout."""
    cmd = [sys.executable, str(script_path)] + args
    if api_key:
        cmd += ["--api-key", api_key]

    _progress({"running": str(script_path.name), "args": args})

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        _error_exit(f"Script timed out: {script_path.name}")
    except FileNotFoundError:
        _error_exit(f"Script not found: {script_path}")

    if proc.returncode != 0:
        # Try to parse the child's JSON error
        try:
            err = json.loads(proc.stdout)
            _error_exit(err.get("message", proc.stdout.strip()))
        except (json.JSONDecodeError, ValueError):
            _error_exit(
                f"{script_path.name} failed (exit {proc.returncode}): "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )

    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        _error_exit(
            f"Non-JSON output from {script_path.name}: "
            f"{proc.stdout[:300]}"
        )


def _resolve_script(relative_parts):
    """Resolve a script path relative to this file's location.

    *relative_parts* is a list like ["banana", "scripts", "generate.py"]
    which becomes  <this_dir>/../../banana/scripts/generate.py
    """
    base = Path(__file__).resolve().parent.parent.parent
    return base.joinpath(*relative_parts)


def _copy_file(src, dst):
    """Copy *src* to *dst*, creating parent dirs."""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))
    return str(Path(dst).resolve())


# ---------------------------------------------------------------------------
# Subcommand: plan
# ---------------------------------------------------------------------------

def cmd_plan(args):
    """Create a shot-list structure from a script description and target duration."""
    target = args.target
    if target < 4:
        _error_exit("Target duration must be at least 4 seconds")

    # v3.6.3: parse the optional --shot-types override. The user can
    # supply a comma-separated list of shot types that map 1:1 to the
    # generated shots, e.g. `--shot-types establishing,medium,closeup,product`
    # for a classic 4-beat commercial structure. Unknown types fall
    # through to the "content" defaults in SHOT_TYPE_DEFAULTS.
    shot_types_arg = getattr(args, "shot_types", None)
    if shot_types_arg:
        shot_type_list = [t.strip() for t in shot_types_arg.split(",") if t.strip()]
    else:
        shot_type_list = []

    shot_count = max(MIN_SHOTS, target // AVG_SHOT_DURATION)
    # If the user supplied shot types, the shot count is determined by
    # that list — their intent wins over the target-duration heuristic.
    if shot_type_list:
        shot_count = len(shot_type_list)

    # Distribute duration across shots. If shot types are provided, let
    # SHOT_TYPE_DEFAULTS suggest per-shot durations and then scale the
    # result to match the target total. Without types, use the original
    # even-split logic that's been in the script since v3.3.0.
    shots = []

    if shot_type_list:
        # Start with each shot's default duration, then rescale so the
        # sum matches target. Rounding-drift absorbs into the last shot.
        raw_durs = [_shot_defaults(t)["duration"] for t in shot_type_list]
        raw_total = sum(raw_durs) or 1
        scaled = [max(4, round(d * target / raw_total)) for d in raw_durs]
        # Snap the last shot to whatever's needed to hit target exactly,
        # clamped to the 4..MAX_SHOT_DURATION envelope.
        drift = target - sum(scaled[:-1])
        scaled[-1] = max(4, min(MAX_SHOT_DURATION, drift))
        # If clamping mangled the total, accept the drift — it's a draft
        # pass; the user can adjust durations by hand in the plan.json.
        durations = scaled
    else:
        durations = []
        remaining = target
        for i in range(shot_count):
            is_last = i == shot_count - 1
            if is_last:
                d = min(MAX_SHOT_DURATION, remaining)
            else:
                d = min(DEFAULT_SHOT_DURATION, remaining - (shot_count - i - 1))
                d = max(4, d)
            durations.append(d)
            remaining -= d

    for i in range(shot_count):
        shot_type = shot_type_list[i] if shot_type_list else "content"
        defaults = _shot_defaults(shot_type)
        dur = durations[i]

        shots.append({
            "number": i + 1,
            "duration": dur,
            "type": shot_type,
            # v3.6.3: prefill camera hint from shot-type defaults. Claude
            # can overwrite this in the SKILL.md plan step; the default
            # just gives a starting point.
            "camera": defaults.get("camera_hint", ""),
            "subject": "",
            "action": "",
            "setting": "",
            "audio": "",
            "prompt": "",
            "start_frame_prompt": "",
            "end_frame_prompt": "",
            "consistency_notes": "",
            # Optional per-shot overrides. Empty string = fall back to the
            # sequence-level model/resolution at generate time.
            "model": "",
            "resolution": "",
            # v3.6.2: when True, the generate stage drops --last-frame and
            # lets VEO pick its own ending. Useful for shots that cut away
            # to unrelated material (e.g. establishing → cut to interior)
            # where pinning a specific end frame over-constrains the motion.
            # v3.6.3: default is now picked from the shot-type table —
            # establishing/transition/cutaway/broll all default True
            # because those shot types by definition don't have fixed
            # endings. content/medium/closeup/product default False.
            "use_veo_interpolation": defaults.get("use_veo_interpolation", False),
            "status": "planned",
        })

    # v3.6.3: storyboard cost depends on how many shots need an end frame.
    # Shots with use_veo_interpolation skip the end frame entirely.
    end_frames_needed = sum(1 for s in shots if not s["use_veo_interpolation"])
    storyboard_cost = (shot_count + end_frames_needed) * COST_STORYBOARD_FRAME
    # Sequence-level model used for the estimate. May be overridden later by
    # --quality-tier at generate time.
    sequence_model = DEFAULT_SEQUENCE_MODEL
    video_cost = sum(_veo_cost(sequence_model, s["duration"]) or 0.0 for s in shots)

    plan = {
        "script": args.script,
        "target_duration": target,
        "preset": getattr(args, "preset", None),
        "model": sequence_model,
        "resolution": DEFAULT_SEQUENCE_RESOLUTION,
        "shot_count": shot_count,
        "shots": shots,
        "estimated_cost": {
            "storyboard_frames": round(storyboard_cost, 2),
            "video_clips": round(video_cost, 2),
            "total": round(storyboard_cost + video_cost, 2),
            "model": sequence_model,
        },
    }

    output_path = args.output or _default_output("plan") + "/shot-list.json"
    saved = _save_plan(output_path, plan)

    result = {
        "plan_path": saved,
        "shots": shot_count,
        "target_duration": target,
        "estimated_cost": plan["estimated_cost"],
    }
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: storyboard
# ---------------------------------------------------------------------------

def cmd_storyboard(args):
    """Generate start/end frame image pairs for each shot."""
    plan = _load_plan(args.plan)
    api_key = _load_api_key(args.api_key)
    output_dir = Path(args.output or _default_output("storyboard"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save a copy of the plan into the storyboard dir for later reference
    _save_plan(output_dir / "plan.json", plan)

    generate_script = _resolve_script(["banana", "scripts", "generate.py"])
    if not generate_script.exists():
        _error_exit(f"Image generation script not found: {generate_script}")

    results = []
    frames_generated = 0
    total_cost = 0.0

    # v3.6.2: parse --shots (comma-separated shot numbers) to limit
    # regeneration to a subset. Empty/None means "all shots". Saves
    # money when only one frame has a bug but the rest are approved.
    shots_filter = _parse_shots_filter(getattr(args, "shots", None))

    for shot in plan["shots"]:
        num = shot["number"]

        if shots_filter is not None and num not in shots_filter:
            continue

        if not shot.get("start_frame_prompt"):
            _progress({
                "skipped": num,
                "reason": "missing start_frame_prompt",
            })
            continue

        # v3.6.2: shots with use_veo_interpolation=True only need a
        # start frame. Missing end_frame_prompt is OK for those shots;
        # required for everything else.
        use_interpolation = bool(shot.get("use_veo_interpolation"))
        if not use_interpolation and not shot.get("end_frame_prompt"):
            _progress({
                "skipped": num,
                "reason": "missing end_frame_prompt (set use_veo_interpolation=true to allow first-frame-only)",
            })
            continue

        _progress({"status": "generating_storyboard", "shot": num, "frame": "start"})

        # Generate start frame
        start_result = _run_script(generate_script, [
            "--prompt", shot["start_frame_prompt"],
            "--aspect-ratio", "16:9",
            "--resolution", "2K",
        ], api_key)

        start_src = start_result.get("path", "")
        start_dst = str(output_dir / f"start-{num:02d}.png")
        if start_src and Path(start_src).exists():
            _copy_file(start_src, start_dst)
        else:
            _progress({"warning": f"No output for shot {num} start frame"})
            continue

        frames_generated += 1
        total_cost += COST_STORYBOARD_FRAME

        # Only generate the end frame when the shot isn't using VEO
        # interpolation. Shots that drop the end frame save ~$0.08/frame
        # on the storyboard cost too, not just the video cost.
        end_dst = None
        if not use_interpolation:
            _progress({"status": "generating_storyboard", "shot": num, "frame": "end"})

            end_result = _run_script(generate_script, [
                "--prompt", shot["end_frame_prompt"],
                "--aspect-ratio", "16:9",
                "--resolution", "2K",
            ], api_key)

            end_src = end_result.get("path", "")
            end_dst = str(output_dir / f"end-{num:02d}.png")
            if end_src and Path(end_src).exists():
                _copy_file(end_src, end_dst)
            else:
                _progress({"warning": f"No output for shot {num} end frame"})
                continue

            frames_generated += 1
            total_cost += COST_STORYBOARD_FRAME

        results.append({
            "shot": num,
            "start_frame": start_dst,
            "end_frame": end_dst,
            "use_veo_interpolation": use_interpolation,
        })

    # Save storyboard manifest
    manifest = {
        "plan": args.plan,
        "storyboard_dir": str(output_dir.resolve()),
        "frames": results,
        "frames_generated": frames_generated,
        "shots": len(results),
        "cost": round(total_cost, 2),
    }
    _save_plan(output_dir / "storyboard.json", manifest)

    print(json.dumps({
        "storyboard_dir": str(output_dir.resolve()),
        "frames_generated": frames_generated,
        "shots": len(results),
        "cost": round(total_cost, 2),
    }, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: estimate
# ---------------------------------------------------------------------------

def cmd_estimate(args):
    """Print cost estimate from an existing plan.

    Honors per-shot, sequence-level, and --quality-tier model overrides.
    Shows a per-tier breakdown so users see why draft-then-final saves money.
    """
    plan = _load_plan(args.plan)
    shots = plan.get("shots", [])
    shot_count = len(shots)

    filled = sum(
        1 for s in shots
        if s.get("start_frame_prompt") and s.get("end_frame_prompt")
    )

    storyboard_cost = shot_count * 2 * COST_STORYBOARD_FRAME
    total_duration = sum(s.get("duration", DEFAULT_SHOT_DURATION) for s in shots)

    override = QUALITY_TIER_MODELS.get(getattr(args, "quality_tier", None))

    # Tier breakdown: { model: {"shots": N, "duration": S, "cost": C} }
    breakdown = {}
    video_cost = 0.0
    for shot in shots:
        duration = shot.get("duration", DEFAULT_SHOT_DURATION)
        model = _resolve_shot_model(shot, plan, override=override)
        per_shot = _veo_cost(model, duration) or 0.0
        video_cost += per_shot
        entry = breakdown.setdefault(model, {"shots": 0, "duration": 0, "cost": 0.0})
        entry["shots"] += 1
        entry["duration"] += duration
        entry["cost"] = round(entry["cost"] + per_shot, 4)

    result = {
        "shots": shot_count,
        "shots_ready": filled,
        "total_duration": total_duration,
        "estimated_cost": {
            "storyboard_frames": round(storyboard_cost, 2),
            "video_clips": round(video_cost, 2),
            "total": round(storyboard_cost + video_cost, 2),
            "per_model": breakdown,
        },
    }
    if override:
        result["quality_tier_override"] = override
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: review (v3.6.2)
# ---------------------------------------------------------------------------

def _relpath_for_markdown(target, base):
    """Return a markdown-friendly relative path from *base* to *target*.

    Falls back to the absolute path if *target* is on a different
    filesystem root than *base* (Python's PurePath.relative_to raises
    in that case). Always uses forward slashes so the markdown preview
    renders on macOS + Linux + iOS identically.
    """
    try:
        return str(Path(target).resolve().relative_to(Path(base).resolve())).replace("\\", "/")
    except ValueError:
        return str(Path(target).resolve())


def _build_review_sheet(plan, storyboard_dir, *, override_model=None, plan_path=None):
    """Return a REVIEW-SHEET.md string for *plan* against *storyboard_dir*.

    Layout per shot (markdown):

        ## Shot N — <type> (Xs)
        **Mode:** first-and-last-frame | first-frame-only (use_veo_interpolation=true)
        **Model:** veo-... **Resolution:** 1080p **Cost:** $X.XX
        **Frames:**
        ![start](start-01.png) ![end](end-01.png)  ← or just start
        **Prompt:**
        > (full VEO prompt text, quoted)
        **Consistency notes:** ...

    Plus a header block with the sequence totals and a Plan freshness
    footer noting which frames are present/missing on disk.
    """
    from datetime import datetime as _dt  # avoid top-level name clash

    storyboard_path = Path(storyboard_dir).resolve()
    shots = plan.get("shots", [])
    shot_count = len(shots)
    sequence_model = plan.get("model") or DEFAULT_SEQUENCE_MODEL
    sequence_resolution = plan.get("resolution") or DEFAULT_SEQUENCE_RESOLUTION

    # Totals across the sequence.
    total_duration = sum(s.get("duration", DEFAULT_SHOT_DURATION) for s in shots)
    storyboard_cost = 0.0
    video_cost = 0.0
    ready = 0
    missing_frames = []

    lines = []
    lines.append(f"# {plan.get('script', 'Sequence')} — REVIEW SHEET")
    lines.append("")
    lines.append(
        f"_Generated by `video_sequence.py review` on "
        f"{_dt.now().strftime('%Y-%m-%d %H:%M:%S')}._ "
        f"Review all frames and prompts before approving generate pass."
    )
    lines.append("")
    lines.append(
        f"- **Target duration:** {plan.get('target_duration', total_duration)}s"
    )
    lines.append(f"- **Shot count:** {shot_count}")
    lines.append(f"- **Sequence model (default):** `{sequence_model}`")
    lines.append(f"- **Sequence resolution (default):** {sequence_resolution}")
    if override_model:
        lines.append(f"- **Quality tier override:** `{override_model}`")
    lines.append(f"- **Storyboard directory:** `{storyboard_path}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    for shot in shots:
        num = shot["number"]
        duration = shot.get("duration", DEFAULT_SHOT_DURATION)
        shot_type = shot.get("type", "content") or "content"
        model = _resolve_shot_model(shot, plan, override=override_model)
        resolution = shot.get("resolution") or sequence_resolution
        use_interpolation = bool(shot.get("use_veo_interpolation"))
        per_shot_cost = _veo_cost(model, duration) or 0.0
        video_cost += per_shot_cost

        # Frame file presence check.
        start_file = storyboard_path / f"start-{num:02d}.png"
        end_file = storyboard_path / f"end-{num:02d}.png"
        start_present = start_file.exists()
        end_required = not use_interpolation
        end_present = end_file.exists() if end_required else None

        # Count storyboard cost only for frames that should exist.
        storyboard_cost += COST_STORYBOARD_FRAME  # start
        if end_required:
            storyboard_cost += COST_STORYBOARD_FRAME

        # Ready status: must have a prompt AND the start frame AND
        # (if end_required) the end frame.
        ready_shot = (
            bool(shot.get("prompt"))
            and start_present
            and (not end_required or end_present)
        )
        if ready_shot:
            ready += 1
        else:
            reasons = []
            if not shot.get("prompt"):
                reasons.append("no prompt")
            if not start_present:
                reasons.append("start frame missing")
            if end_required and not end_present:
                reasons.append("end frame missing")
            missing_frames.append((num, reasons))

        mode_label = (
            "first-frame-only (VEO interpolates ending)"
            if use_interpolation
            else "first-and-last-frame interpolation"
        )
        status_badge = "✅" if ready_shot else "⚠️"

        lines.append(
            f"## Shot {num} — {shot_type} ({duration}s) {status_badge}"
        )
        lines.append("")
        lines.append(
            f"**Mode:** {mode_label}  "
            f"**Model:** `{model}`  "
            f"**Resolution:** {resolution}  "
            f"**Cost:** ${per_shot_cost:.2f}"
        )
        lines.append("")

        # Frames
        lines.append("**Frames:**")
        lines.append("")
        start_md_path = _relpath_for_markdown(start_file, storyboard_path)
        if start_present:
            lines.append(f"![start-{num:02d}]({start_md_path}) <!-- start frame -->")
        else:
            lines.append(f"_⚠️ start frame missing at_ `{start_md_path}`")
        if end_required:
            end_md_path = _relpath_for_markdown(end_file, storyboard_path)
            if end_present:
                lines.append(f"![end-{num:02d}]({end_md_path}) <!-- end frame -->")
            else:
                lines.append(f"_⚠️ end frame missing at_ `{end_md_path}`")
        else:
            lines.append("_(no end frame — VEO interpolates ending)_")
        lines.append("")

        # Prompt
        prompt = shot.get("prompt", "").strip()
        if prompt:
            lines.append("**VEO prompt:**")
            lines.append("")
            for pline in prompt.splitlines() or [""]:
                lines.append(f"> {pline}" if pline else ">")
            lines.append("")
        else:
            lines.append("**VEO prompt:** _⚠️ empty — shot will be skipped at generate time_")
            lines.append("")

        # Storyboard prompts (optional, shown for the approval gate)
        sfp = shot.get("start_frame_prompt", "").strip()
        efp = shot.get("end_frame_prompt", "").strip()
        if sfp or efp:
            lines.append("<details><summary>Storyboard prompts</summary>")
            lines.append("")
            if sfp:
                lines.append("**Start frame prompt:**")
                lines.append("")
                lines.append(f"```\n{sfp}\n```")
                lines.append("")
            if efp and end_required:
                lines.append("**End frame prompt:**")
                lines.append("")
                lines.append(f"```\n{efp}\n```")
                lines.append("")
            lines.append("</details>")
            lines.append("")

        # Consistency notes
        notes = shot.get("consistency_notes", "").strip()
        if notes:
            lines.append(f"**Consistency notes:** {notes}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Summary footer
    lines.append("## Sequence totals")
    lines.append("")
    lines.append(f"- **Total duration:** {total_duration}s")
    lines.append(f"- **Shots ready:** {ready} / {shot_count}")
    lines.append(f"- **Storyboard cost:** ${storyboard_cost:.2f}")
    lines.append(f"- **Video cost (at selected models):** ${video_cost:.2f}")
    lines.append(f"- **Total cost:** ${storyboard_cost + video_cost:.2f}")
    lines.append("")
    if missing_frames:
        lines.append("### ⚠️ Gaps blocking generate")
        lines.append("")
        for num, reasons in missing_frames:
            lines.append(f"- Shot {num}: {', '.join(reasons)}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "_This review sheet is the approval gate between `storyboard` and "
        "`generate`. Once every shot shows ✅ above, run "
        "`video_sequence.py generate --storyboard <dir>` to kick off the "
        "clip generation pass. Use `--quality-tier draft` for the Lite "
        "first pass if you want to see motion before committing to the "
        "final Standard render._"
    )
    lines.append("")

    # v3.6.3: machine-readable manifest block for the generate gate.
    # cmd_generate reads this to detect frame drift since the review was
    # written. Wrapped in HTML comments so it doesn't render in markdown
    # previews. Do not edit by hand — regenerate via `video_sequence.py
    # review` if you change the storyboard.
    manifest = _build_review_manifest(plan, storyboard_dir, plan_path or "")
    lines.append(REVIEW_SHEET_MANIFEST_START)
    lines.append("```json")
    lines.append(json.dumps(manifest, indent=2))
    lines.append("```")
    lines.append(REVIEW_SHEET_MANIFEST_END)
    lines.append("")
    return "\n".join(lines)


def cmd_review(args):
    """Generate REVIEW-SHEET.md for an existing plan + storyboard dir.

    The review sheet is the human-readable artifact that interleaves
    each shot's storyboard frames, VEO prompt, cost estimate, and
    parameters into a single markdown file you can open in Quick Look
    or a markdown preview. Intended to be the approval gate between
    the `storyboard` and `generate` stages of the pipeline.

    v3.6.2 ships the review sheet as a stand-alone subcommand. It
    doesn't block `generate` yet — a `--skip-review` / mandatory-gate
    integration is v3.6.3 scope. For now, running `review` writes the
    file and leaves enforcement to human discipline.
    """
    plan = _load_plan(args.plan)
    storyboard_dir = Path(args.storyboard)
    if not storyboard_dir.is_dir():
        _error_exit(f"Storyboard directory not found: {storyboard_dir}")

    override = QUALITY_TIER_MODELS.get(getattr(args, "quality_tier", None))

    content = _build_review_sheet(
        plan,
        storyboard_dir,
        override_model=override,
        plan_path=args.plan,
    )

    output_path = Path(args.output) if args.output else storyboard_dir / "REVIEW-SHEET.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(content)

    # Emit a JSON status + the path so shell callers can open it.
    print(json.dumps({
        "review_sheet": str(output_path.resolve()),
        "shots": len(plan.get("shots", [])),
        "storyboard_dir": str(storyboard_dir.resolve()),
        "plan_path": str(Path(args.plan).resolve()),
    }, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: generate
# ---------------------------------------------------------------------------

def cmd_generate(args):
    """Generate video clips from approved storyboard frames."""
    storyboard_dir = Path(args.storyboard)
    if not storyboard_dir.is_dir():
        _error_exit(f"Storyboard directory not found: {storyboard_dir}")

    # Try to load the plan from the storyboard dir or a separate path
    plan_path = storyboard_dir / "plan.json"
    if not plan_path.exists():
        manifest_path = storyboard_dir / "storyboard.json"
        if manifest_path.exists():
            manifest = _load_plan(manifest_path)
            alt = manifest.get("plan")
            if alt and Path(alt).exists():
                plan_path = Path(alt)

    if not plan_path.exists():
        _error_exit(
            f"No plan.json in storyboard dir. "
            f"Run 'storyboard' first or place plan.json in {storyboard_dir}"
        )

    plan = _load_plan(plan_path)

    # v3.6.3: mandatory review gate. cmd_generate refuses to run if
    # REVIEW-SHEET.md is missing, unparseable, or has frame hashes that
    # drift from the current storyboard. --skip-review bypasses the
    # check for CI and automation paths. The gate costs nothing to run
    # and prevents the most expensive category of mistake: generating a
    # $12 Standard clip against a frame that was regenerated after the
    # review was written.
    if not getattr(args, "skip_review", False):
        freshness = _check_review_freshness(plan, storyboard_dir)
        status = freshness["status"]
        if status == "missing":
            _error_exit(
                "No REVIEW-SHEET.md found in the storyboard directory. "
                "v3.6.3 makes review a mandatory stage between storyboard "
                "and generate. Run:\n"
                f"  python3 video_sequence.py review --plan {plan_path} "
                f"--storyboard {storyboard_dir}\n"
                "Then re-run generate. Pass --skip-review to bypass this "
                "check (for CI or automation only — it disables the safety "
                "net that catches frame drift)."
            )
        if status == "unparseable":
            _error_exit(
                "REVIEW-SHEET.md exists but its embedded manifest block "
                "cannot be parsed. Regenerate with:\n"
                f"  python3 video_sequence.py review --plan {plan_path} "
                f"--storyboard {storyboard_dir}\n"
                "or pass --skip-review to bypass the check."
            )
        if status == "stale":
            drifted = freshness.get("drifted_shots", [])
            _error_exit(
                f"REVIEW-SHEET.md is stale — shot(s) "
                f"{', '.join(str(n) for n in drifted)} have frame hashes "
                f"that differ from the recorded review. Someone regenerated "
                f"one or more storyboard frames after the review was written. "
                f"Regenerate the review sheet:\n"
                f"  python3 video_sequence.py review --plan {plan_path} "
                f"--storyboard {storyboard_dir}\n"
                f"Then re-inspect and re-run generate. Pass --skip-review "
                f"if you know what you're doing."
            )
        _progress({"status": "review_gate_ok", "path": str((Path(storyboard_dir) / "REVIEW-SHEET.md").resolve())})
    else:
        _progress({"status": "review_gate_skipped", "reason": "--skip-review"})

    api_key = _load_api_key(args.api_key)
    output_dir = Path(args.output or _default_output("clips"))
    output_dir.mkdir(parents=True, exist_ok=True)

    video_script = Path(__file__).resolve().parent / "video_generate.py"
    if not video_script.exists():
        _error_exit(f"Video generation script not found: {video_script}")

    override = QUALITY_TIER_MODELS.get(getattr(args, "quality_tier", None))
    sequence_resolution = plan.get("resolution") or DEFAULT_SEQUENCE_RESOLUTION

    results = []
    total_cost = 0.0
    total_duration = 0

    for shot in plan["shots"]:
        num = shot["number"]
        prompt = shot.get("prompt", "")
        if not prompt:
            _progress({"skipped": num, "reason": "no prompt"})
            continue

        start_frame = storyboard_dir / f"start-{num:02d}.png"
        end_frame = storyboard_dir / f"end-{num:02d}.png"

        # v3.6.2: `use_veo_interpolation: true` on the shot means VEO
        # picks its own ending. We still require a start frame but the
        # end frame is optional (and dropped from the generate call).
        use_interpolation = bool(shot.get("use_veo_interpolation"))

        if not start_frame.exists():
            _progress({"skipped": num, "reason": "missing start frame"})
            continue
        if not use_interpolation and not end_frame.exists():
            _progress({"skipped": num, "reason": "missing end frame (set use_veo_interpolation=true to allow first-frame-only)"})
            continue

        duration = shot.get("duration", DEFAULT_SHOT_DURATION)
        model = _resolve_shot_model(shot, plan, override=override)
        resolution = shot.get("resolution") or sequence_resolution

        _progress({
            "status": "generating_clip",
            "shot": num,
            "duration": duration,
            "model": model,
            "resolution": resolution,
            "mode": "first-frame-only" if use_interpolation else "first-and-last-frame",
        })

        cmd_args = [
            "--prompt", prompt,
            "--model", model,
            "--duration", str(duration),
            "--aspect-ratio", "16:9",
            "--resolution", resolution,
            "--first-frame", str(start_frame),
        ]
        if not use_interpolation:
            cmd_args.extend(["--last-frame", str(end_frame)])

        result = _run_script(video_script, cmd_args, api_key)

        # Rename output to sequential clip file
        src_path = result.get("path", "")
        clip_dst = str(output_dir / f"clip-{num:02d}.mp4")
        if src_path and Path(src_path).exists():
            _copy_file(src_path, clip_dst)
        else:
            _progress({"warning": f"No video output for shot {num}"})
            continue

        per_shot_cost = _veo_cost(model, duration) or 0.0
        total_cost += per_shot_cost
        total_duration += duration

        results.append({
            "shot": num,
            "clip": clip_dst,
            "duration": duration,
            "model": model,
            "resolution": resolution,
            "cost": round(per_shot_cost, 4),
        })

    # Save generation manifest
    manifest = {
        "clips_dir": str(output_dir.resolve()),
        "clips": results,
        "clips_generated": len(results),
        "total_duration": total_duration,
        "cost": round(total_cost, 2),
    }
    _save_plan(output_dir / "generate.json", manifest)

    print(json.dumps({
        "clips_dir": str(output_dir.resolve()),
        "clips_generated": len(results),
        "total_duration": total_duration,
        "cost": round(total_cost, 2),
    }, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: stitch
# ---------------------------------------------------------------------------

def cmd_stitch(args):
    """Concatenate clips in order using FFmpeg."""
    clips_dir = Path(args.clips)
    if not clips_dir.is_dir():
        _error_exit(f"Clips directory not found: {clips_dir}")

    clips = sorted(clips_dir.glob("clip-*.mp4"))
    if not clips:
        _error_exit(f"No clip-*.mp4 files found in {clips_dir}")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        _error_exit("FFmpeg not found. Install: brew install ffmpeg")

    # Build concat file list
    list_file = clips_dir / "concat.txt"
    with open(list_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip.resolve()}'\n")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    _progress({"status": "stitching", "clips": len(clips), "output": str(output)})

    try:
        proc = subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        list_file.unlink(missing_ok=True)
        _error_exit("FFmpeg timed out during stitching")

    # Clean up concat list
    list_file.unlink(missing_ok=True)

    if proc.returncode != 0:
        _error_exit(f"FFmpeg failed: {proc.stderr.strip()}")

    # Probe duration with ffprobe if available
    total_duration = 0
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            probe = subprocess.run(
                [
                    ffprobe, "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                total_duration = round(float(probe.stdout.strip()))
        except (subprocess.TimeoutExpired, ValueError):
            pass

    result = {
        "output": str(output.resolve()),
        "duration": total_duration,
        "clips": len(clips),
    }
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Multi-shot video sequence production pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- plan --
    p_plan = subparsers.add_parser("plan", help="Create a shot-list structure")
    p_plan.add_argument(
        "--script", required=True,
        help="Script description (e.g. '30-second product launch ad')",
    )
    p_plan.add_argument(
        "--target", type=int, required=True,
        help="Target total duration in seconds",
    )
    p_plan.add_argument("--preset", default=None, help="Brand preset name")
    p_plan.add_argument("--output", default=None, help="Output path for shot-list.json")
    p_plan.add_argument(
        "--shot-types", default=None,
        help=(
            "v3.6.3+: comma-separated list of shot types for the "
            "generated skeleton, e.g. "
            "'establishing,medium,closeup,product' for a 4-beat "
            "commercial. Each type pre-fills duration, camera hint, "
            "and use_veo_interpolation defaults from SHOT_TYPE_DEFAULTS. "
            "When set, shot count is determined by this list and "
            "durations are rescaled to hit --target. Known types: "
            + ", ".join(SHOT_TYPES) + "."
        ),
    )

    # -- storyboard --
    p_sb = subparsers.add_parser(
        "storyboard", help="Generate start/end frame pairs for each shot",
    )
    p_sb.add_argument("--plan", required=True, help="Path to shot-list.json")
    p_sb.add_argument("--api-key", default=None, help="Google AI API key")
    p_sb.add_argument("--output", default=None, help="Output directory for frames")
    p_sb.add_argument(
        "--shots", default=None,
        help=(
            "Comma-separated shot numbers (or ranges) to regenerate, "
            "e.g. '1,3,5' or '2-4' or '1,3-5,7'. Default: regenerate "
            "all shots. Use to iterate on a single frame without paying "
            "for the whole storyboard again."
        ),
    )

    # -- estimate --
    p_est = subparsers.add_parser("estimate", help="Print cost estimate from plan")
    p_est.add_argument("--plan", required=True, help="Path to shot-list.json")
    p_est.add_argument(
        "--quality-tier",
        choices=["draft", "fast", "standard", "premium", "lite", "legacy", "veo-backup"],
        default=None,
        help=(
            "Override model for all shots. v3.8.0+: draft/fast/standard/"
            "premium/lite/legacy all point to Kling v3 Std (flat $0.16/8s). "
            "veo-backup routes to VEO 3.1 Lite — opt-in only, see spike 5 findings."
        ),
    )

    # -- generate --
    p_gen = subparsers.add_parser(
        "generate", help="Generate video clips from storyboard frames",
    )
    p_gen.add_argument(
        "--storyboard", required=True, help="Storyboard directory with frames",
    )
    p_gen.add_argument("--api-key", default=None, help="Google AI API key")
    p_gen.add_argument("--output", default=None, help="Output directory for clips")
    p_gen.add_argument(
        "--quality-tier",
        choices=["draft", "fast", "standard", "premium", "lite", "legacy", "veo-backup"],
        default=None,
        help=(
            "Override model for all shots. v3.8.0+: draft/fast/standard/"
            "premium/lite/legacy ALL route to Kling v3 Std ($0.16/8s flat). "
            "Kling's quality is cheap enough that a separate draft tier no "
            "longer makes sense. veo-backup is the opt-in VEO 3.1 Lite path "
            "for workflows that specifically want VEO output reviewed against "
            "Kling — requires vertex_api_key in ~/.banana/config.json and "
            "you should review the spike 5 findings at "
            "spikes/v3.8.0-provider-bakeoff/writeup/v3.8.0-bakeoff-findings.md "
            "before committing to VEO for production work. "
            "See references/video-sequences.md for the workflow guide."
        ),
    )
    p_gen.add_argument(
        "--skip-review", action="store_true",
        help=(
            "v3.6.3+: bypass the mandatory review gate. By default, "
            "generate refuses to run unless a valid REVIEW-SHEET.md "
            "exists in the storyboard dir AND its embedded frame "
            "hashes match the current storyboard. --skip-review is "
            "intended for CI and automation paths that know what "
            "they're doing — it disables the safety net that catches "
            "frame drift. Prefer running `video_sequence.py review` "
            "first for interactive use."
        ),
    )

    # -- review (v3.6.2) --
    p_rev = subparsers.add_parser(
        "review",
        help=(
            "Generate REVIEW-SHEET.md interleaving each shot's frames, "
            "VEO prompt, cost, and parameters. The human approval gate "
            "between storyboard and generate."
        ),
    )
    p_rev.add_argument("--plan", required=True, help="Path to shot-list.json")
    p_rev.add_argument(
        "--storyboard", required=True,
        help="Storyboard directory (containing start-NN.png / end-NN.png frames)",
    )
    p_rev.add_argument(
        "--output", default=None,
        help="Path for the generated REVIEW-SHEET.md (default: <storyboard>/REVIEW-SHEET.md)",
    )
    p_rev.add_argument(
        "--quality-tier",
        choices=["draft", "fast", "standard", "premium", "lite", "legacy", "veo-backup"],
        default=None,
        help="Preview the cost breakdown at this tier (matches generate --quality-tier)",
    )

    # -- stitch --
    p_stitch = subparsers.add_parser(
        "stitch", help="Concatenate clips into final video with FFmpeg",
    )
    p_stitch.add_argument("--clips", required=True, help="Directory containing clip-*.mp4")
    p_stitch.add_argument("--output", required=True, help="Output file path (e.g. final.mp4)")

    args = parser.parse_args()

    dispatch = {
        "plan": cmd_plan,
        "storyboard": cmd_storyboard,
        "estimate": cmd_estimate,
        "review": cmd_review,
        "generate": cmd_generate,
        "stitch": cmd_stitch,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
