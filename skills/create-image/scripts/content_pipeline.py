#!/usr/bin/env python3
"""Creators Studio -- Content Pipeline Orchestrator

Produce a complete content package from a single idea by chaining existing
scripts (generate.py, social.py, multiformat.py, slides.py).

Uses only Python stdlib + subprocess (calls other scripts).

Usage:
    content_pipeline.py plan --idea "product launch hero" --outputs hero,social,email,formats
    content_pipeline.py plan --idea "wireless earbuds" --outputs hero,social --preset tech-saas
    content_pipeline.py generate --plan path/to/plan.json [--api-key KEY]
    content_pipeline.py status --plan path/to/plan.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent

# v4.2.2: import the migration helper from plugin-root scripts/paths.py.
_plugin_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)
from scripts.paths import config_path as _csd_config  # noqa: E402

OUTPUT_DIR = Path.home() / "Documents" / "creators_generated"
CONFIG_PATH = _csd_config()

DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_RATIO = "16:9"
DEFAULT_RESOLUTION = "4K"

PRICING = {
    "gemini-3.1-flash-image-preview": {"512": 0.020, "1K": 0.039, "2K": 0.078, "4K": 0.156},
    "gemini-2.5-flash-image": {"512": 0.020, "1K": 0.039},
}

OUTPUT_TYPES = {
    "hero": {
        "description": "Hero image at max resolution",
        "script": "generate.py",
        "default_ratio": "16:9",
        "default_resolution": "4K",
        "api_calls": 1,
    },
    "social": {
        "description": "Social media pack (top 6 platforms)",
        "script": "social.py",
        "default_platforms": "ig-feed,ig-story,fb-feed,li-landscape,x-landscape,yt-thumb",
        "api_calls": 4,  # grouped by ratio
    },
    "email": {
        "description": "Email header banner (600px wide)",
        "script": "multiformat.py",
        "source": "hero",  # converts from hero, no API call
        "api_calls": 0,
    },
    "formats": {
        "description": "Multi-format pack (PNG/WebP/JPEG at 4K/2K/1K)",
        "script": "multiformat.py",
        "source": "hero",
        "api_calls": 0,
    },
    "video": {
        "description": "Product reveal video clip (8s, 16:9)",
        "script": "../../video/scripts/video_generate.py",
        "source": "hero",  # uses hero image as first frame
        "default_duration": "8",
        "default_ratio": "16:9",
        "default_resolution": "1080p",
        "api_calls": 1,
    },
    "deck": {
        "description": "Slide deck backgrounds (requires separate slide prompts)",
        "script": "slides.py",
        "api_calls": "variable",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_api_key(cli_key):
    """Resolve API key: CLI arg -> env var -> config.json."""
    if cli_key:
        return cli_key
    env_key = os.environ.get("GOOGLE_AI_API_KEY")
    if env_key:
        return env_key
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        key = cfg.get("google_ai_api_key") or cfg.get("api_key")
        if key:
            return key
    return None


def _run_script(script_name, args, api_key=None):
    """Run a sibling script via subprocess, return parsed JSON result."""
    cmd = [sys.executable, str(_SCRIPT_DIR / script_name)] + args
    env = os.environ.copy()
    if api_key:
        env["GOOGLE_AI_API_KEY"] = api_key
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        return {"error": True, "message": result.stderr.strip() or result.stdout.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": True, "message": f"Non-JSON output: {result.stdout[:500]}"}


def _estimate_cost(outputs, resolution, model=None):
    """Calculate total estimated cost and API call count."""
    model = model or DEFAULT_MODEL
    pricing = PRICING.get(model, {})
    per_image = pricing.get(resolution, pricing.get("4K", 0.156))

    total_calls = 0
    total_cost = 0.0
    for out in outputs:
        spec = OUTPUT_TYPES[out]
        calls = spec["api_calls"]
        if calls == "variable":
            calls = 0  # deck cost unknown until prompts provided
        total_calls += calls
        total_cost += calls * per_image

    return total_calls, round(total_cost, 3)


def _load_plan(plan_path):
    """Load a plan.json file."""
    with open(plan_path, "r") as f:
        return json.load(f)


def _save_plan(plan):
    """Save plan.json back to its output_dir."""
    plan_path = Path(plan["output_dir"]) / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)


def _build_manifest(plan):
    """Build manifest.json from a completed plan."""
    outputs = {}
    total_cost = 0.0
    total_files = 0

    for step in plan["steps"]:
        if step["status"] != "completed" or not step.get("result"):
            continue
        result = step["result"]
        step_cost = result.get("cost", 0)
        total_cost += step_cost

        if step["type"] in ("social", "formats"):
            files = result.get("files", result.get("images", []))
            total_files += len(files)
            outputs[step["type"]] = {"files": files, "cost": step_cost}
        else:
            path = result.get("path", result.get("image", ""))
            if path:
                total_files += 1
            outputs[step["type"]] = {"path": path, "cost": step_cost}

    return {
        "idea": plan["idea"],
        "preset": plan.get("preset"),
        "created": plan["created"],
        "completed": datetime.now(timezone.utc).isoformat(),
        "total_cost": round(total_cost, 3),
        "total_files": total_files,
        "outputs": outputs,
    }


def _save_manifest(output_dir, manifest):
    """Write manifest.json to the content output directory."""
    manifest_path = Path(output_dir) / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def _build_step_args(step_type, idea, ratio, resolution, preset, platforms):
    """Build the CLI args list for a given step type."""
    if step_type == "hero":
        args = ["--prompt", idea, "--aspect-ratio", ratio, "--resolution", resolution]
        if preset:
            args += ["--preset", preset]
        return args

    if step_type == "social":
        args = ["generate", "--prompt", idea, "--platforms", platforms]
        if preset:
            args += ["--preset", preset]
        return args

    if step_type == "email":
        # Convert hero to email-size PNG + JPEG at 1K
        return ["convert", "--input", "HERO_PATH", "--formats", "png,jpeg", "--sizes", "1k"]

    if step_type == "formats":
        return ["convert", "--input", "HERO_PATH", "--formats", "png,webp,jpeg", "--sizes", "4k,2k,1k"]

    if step_type == "video":
        # Video uses hero image as first frame for animation
        return ["--prompt", idea, "--first-frame", "HERO_PATH",
                "--duration", "8", "--aspect-ratio", ratio, "--resolution", "1080p"]

    if step_type == "deck":
        # Deck requires a prompts file; placeholder until user provides one
        return ["estimate", "--prompts", "PROMPTS_PATH"]

    return []


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_plan(args):
    """Generate an execution plan and write plan.json."""
    idea = args.idea
    outputs = [o.strip() for o in args.outputs.split(",")]
    preset = getattr(args, "preset", None)
    ratio = getattr(args, "ratio", None) or DEFAULT_RATIO
    resolution = getattr(args, "resolution", None) or DEFAULT_RESOLUTION
    platforms = OUTPUT_TYPES["social"]["default_platforms"]

    # Validate requested outputs
    invalid = [o for o in outputs if o not in OUTPUT_TYPES]
    if invalid:
        json.dump({"error": True, "message": f"Unknown output types: {', '.join(invalid)}",
                    "valid_types": list(OUTPUT_TYPES.keys())}, sys.stdout, indent=2)
        sys.exit(1)

    total_calls, total_cost = _estimate_cost(outputs, resolution)
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    output_dir = str(OUTPUT_DIR / f"content_{ts_str}")

    # Build steps with dependency tracking
    steps = []
    step_num = 0
    for out in outputs:
        step_num += 1
        spec = OUTPUT_TYPES[out]
        step = {
            "step": step_num,
            "type": out,
            "script": spec["script"],
            "args": _build_step_args(out, idea, ratio, resolution, preset, platforms),
            "status": "pending",
            "depends_on": None,
            "result": None,
        }
        # email and formats depend on hero
        if spec.get("source") == "hero" and "hero" in outputs:
            hero_step = next((s for s in steps if s["type"] == "hero"), None)
            if hero_step:
                step["depends_on"] = hero_step["step"]
        steps.append(step)

    plan = {
        "idea": idea,
        "preset": preset,
        "ratio": ratio,
        "resolution": resolution,
        "model": DEFAULT_MODEL,
        "created": ts.isoformat(),
        "estimated_api_calls": total_calls,
        "estimated_cost": total_cost,
        "output_dir": output_dir,
        "steps": steps,
    }

    # Write plan.json
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    _save_plan(plan)

    json.dump(plan, sys.stdout, indent=2)


def cmd_generate(args):
    """Execute a plan step by step, writing results to plan.json."""
    plan = _load_plan(args.plan)
    api_key = _load_api_key(getattr(args, "api_key", None))

    if not api_key:
        json.dump({"error": True, "message": "No API key found. Pass --api-key, set "
                   "GOOGLE_AI_API_KEY, or configure via setup_mcp.py"}, sys.stdout, indent=2)
        sys.exit(1)

    output_dir = Path(plan["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    for step in plan["steps"]:
        if step["status"] == "completed":
            continue

        # Check dependencies
        if step.get("depends_on"):
            dep = next((s for s in plan["steps"] if s["step"] == step["depends_on"]), None)
            if dep and dep["status"] != "completed":
                step["status"] = "blocked"
                _save_plan(plan)
                continue
            # Replace HERO_PATH placeholder with actual path from dependency
            if dep and dep.get("result"):
                hero_path = dep["result"].get("path", dep["result"].get("image", ""))
                step["args"] = [a.replace("HERO_PATH", hero_path) for a in step["args"]]

        step["status"] = "running"
        _save_plan(plan)

        result = _run_script(step["script"], step["args"], api_key)

        if result.get("error"):
            step["status"] = "failed"
            step["result"] = result
        else:
            step["status"] = "completed"
            step["result"] = result

        _save_plan(plan)

    # Build and save manifest
    manifest = _build_manifest(plan)
    _save_manifest(plan["output_dir"], manifest)

    # Final summary
    completed = sum(1 for s in plan["steps"] if s["status"] == "completed")
    failed = sum(1 for s in plan["steps"] if s["status"] == "failed")
    blocked = sum(1 for s in plan["steps"] if s["status"] == "blocked")

    summary = {
        "plan": str(Path(plan["output_dir"]) / "plan.json"),
        "manifest": str(Path(plan["output_dir"]) / "manifest.json"),
        "steps_completed": completed,
        "steps_failed": failed,
        "steps_blocked": blocked,
        "total_cost": manifest["total_cost"],
        "total_files": manifest["total_files"],
    }
    json.dump(summary, sys.stdout, indent=2)


def cmd_status(args):
    """Read plan.json and report current status."""
    plan = _load_plan(args.plan)

    steps_summary = []
    for step in plan["steps"]:
        entry = {
            "step": step["step"],
            "type": step["type"],
            "status": step["status"],
        }
        if step["status"] == "failed" and step.get("result"):
            entry["error"] = step["result"].get("message", "")
        if step["status"] == "completed" and step.get("result"):
            entry["path"] = step["result"].get("path", step["result"].get("image"))
        steps_summary.append(entry)

    completed = sum(1 for s in plan["steps"] if s["status"] == "completed")
    total = len(plan["steps"])

    status = {
        "idea": plan["idea"],
        "created": plan["created"],
        "output_dir": plan["output_dir"],
        "progress": f"{completed}/{total}",
        "estimated_cost": plan["estimated_cost"],
        "steps": steps_summary,
    }
    json.dump(status, sys.stdout, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Content pipeline orchestrator -- produce a complete content "
                    "package from a single idea."
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # -- plan --
    p_plan = subs.add_parser("plan", help="Generate an execution plan")
    p_plan.add_argument("--idea", required=True, help="Creative idea or prompt")
    p_plan.add_argument("--outputs", required=True,
                        help="Comma-separated output types: hero,social,email,formats,deck")
    p_plan.add_argument("--preset", help="Brand Style Guide preset name")
    p_plan.add_argument("--ratio", help=f"Aspect ratio for hero (default: {DEFAULT_RATIO})")
    p_plan.add_argument("--resolution", help=f"Resolution tier (default: {DEFAULT_RESOLUTION})")

    # -- generate --
    p_gen = subs.add_parser("generate", help="Execute a plan")
    p_gen.add_argument("--plan", required=True, help="Path to plan.json")
    p_gen.add_argument("--api-key", dest="api_key", help="Google AI API key override")

    # -- status --
    p_stat = subs.add_parser("status", help="Show plan status")
    p_stat.add_argument("--plan", required=True, help="Path to plan.json")

    args = parser.parse_args()

    if args.command == "plan":
        cmd_plan(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
