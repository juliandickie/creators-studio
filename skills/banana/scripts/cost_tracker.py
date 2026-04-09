#!/usr/bin/env python3
"""Banana Claude -- Cost Tracker

Track image generation costs, view summaries, and estimate batch costs.

Usage:
    cost_tracker.py log --model MODEL --resolution RES --prompt "summary"
    cost_tracker.py summary
    cost_tracker.py today
    cost_tracker.py estimate --model MODEL --resolution RES --count N
    cost_tracker.py reset --confirm
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path.home() / ".banana" / "costs.json"

# Cost per image in USD (approximate, based on ~1,290 output tokens)
PRICING = {
    "gemini-3.1-flash-image-preview": {
        "512": 0.020,
        "1K": 0.039,
        "2K": 0.078,
        "4K": 0.156,
    },
    "gemini-2.5-flash-image": {
        "512": 0.020,
        "1K": 0.039,
    },
    "replicate/nano-banana-2": {
        "512": 0.050,
        "1K": 0.050,
        "2K": 0.050,
        "4K": 0.050,
    },
    # VEO video models (keyed by duration instead of resolution).
    # Rates per Google Cloud Vertex AI pricing (April 2026):
    #   Standard: $0.40/sec with audio
    #   Fast:     $0.15/sec with audio
    #   Lite:     $0.05/sec (720p; 1080p not explicitly documented)
    #   Legacy 3.0: no explicit doc; treated same as Fast
    # Both preview and GA (-001) IDs are listed so plans from any era resolve.
    "veo-3.1-generate-preview": {
        "4s": 1.60, "6s": 2.40, "8s": 3.20,
        "per_second": 0.40,
    },
    "veo-3.1-generate-001": {
        "4s": 1.60, "6s": 2.40, "8s": 3.20,
        "per_second": 0.40,
    },
    "veo-3.1-fast-generate-preview": {
        "4s": 0.60, "6s": 0.90, "8s": 1.20,
        "per_second": 0.15,
    },
    "veo-3.1-fast-generate-001": {
        "4s": 0.60, "6s": 0.90, "8s": 1.20,
        "per_second": 0.15,
    },
    # Lite supports 5-60s duration range; use per_second for variable durations.
    # TODO: verify 1080p Lite pricing -- doc only explicitly states 720p rate.
    "veo-3.1-lite-generate-001": {
        "4s": 0.20, "6s": 0.30, "8s": 0.40,
        "per_second": 0.05,
    },
    # Legacy VEO 3.0 -- pricing not explicitly documented; assume Fast-tier parity.
    "veo-3.0-generate-001": {
        "4s": 0.60, "6s": 0.90, "8s": 1.20,
        "per_second": 0.15,
    },
}


def _veo_cost(model, duration_seconds, with_audio=True):
    """Look up VEO generation cost for a model + duration.

    Returns a float USD cost, or None if the model is unknown.

    - Standard durations {4,6,8} use fixed-tier lookup.
    - Non-standard durations (e.g. Lite 5-60s) fall back to per_second * duration.
    - Audio is assumed on; the script does not yet support audio-off generation.
    """
    del with_audio  # reserved for future audio-off pricing
    pricing = PRICING.get(model)
    if not pricing:
        return None
    key = f"{int(duration_seconds)}s"
    if key in pricing:
        return pricing[key]
    per_sec = pricing.get("per_second")
    if per_sec is None:
        return None
    return round(per_sec * duration_seconds, 4)

# Batch API gets 50% discount
BATCH_DISCOUNT = 0.5


def _load_ledger():
    """Load the cost ledger from disk."""
    if not LEDGER_PATH.exists():
        return {"total_cost": 0.0, "total_images": 0, "entries": [], "daily": {}}
    with open(LEDGER_PATH, "r") as f:
        return json.load(f)


def _save_ledger(ledger):
    """Save the cost ledger to disk."""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)


def _lookup_cost(model, resolution, batch=False):
    """Look up cost for a model+resolution combination."""
    model_pricing = PRICING.get(model)
    if not model_pricing:
        # Try partial match
        for key in PRICING:
            if key in model or model in key:
                model_pricing = PRICING[key]
                break
    if not model_pricing:
        print(f"Warning: Unknown model '{model}', using 3.1 Flash pricing", file=sys.stderr)
        model_pricing = PRICING["gemini-3.1-flash-image-preview"]

    valid_resolutions = {"512", "1K", "2K", "4K"}
    if resolution not in valid_resolutions:
        print(f"Warning: Unknown resolution '{resolution}', using 1K pricing", file=sys.stderr)
    cost = model_pricing.get(resolution, model_pricing.get("1K", 0.039))
    if batch:
        cost *= BATCH_DISCOUNT
    return cost


def cmd_log(args):
    """Log a generation to the ledger."""
    ledger = _load_ledger()
    cost = _lookup_cost(args.model, args.resolution, getattr(args, "batch", False))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    entry = {
        "ts": now,
        "model": args.model,
        "res": args.resolution,
        "cost": cost,
        "prompt": args.prompt[:100],
    }

    ledger["entries"].append(entry)
    ledger["total_cost"] = round(ledger["total_cost"] + cost, 4)
    ledger["total_images"] += 1

    if today not in ledger["daily"]:
        ledger["daily"][today] = {"count": 0, "cost": 0.0}
    ledger["daily"][today]["count"] += 1
    ledger["daily"][today]["cost"] = round(ledger["daily"][today]["cost"] + cost, 4)

    _save_ledger(ledger)
    print(json.dumps({"logged": True, "cost": cost, "total_cost": ledger["total_cost"],
                       "total_images": ledger["total_images"]}))


def cmd_summary(args):
    """Show cost summary."""
    ledger = _load_ledger()
    print(f"Total images: {ledger['total_images']}")
    print(f"Total cost:   ${ledger['total_cost']:.3f}")
    print()

    daily = ledger.get("daily", {})
    if daily:
        # Show last 7 days
        sorted_days = sorted(daily.keys(), reverse=True)[:7]
        print("Last 7 days:")
        for day in sorted_days:
            d = daily[day]
            print(f"  {day}: {d['count']} images, ${d['cost']:.3f}")
    else:
        print("No usage recorded yet.")


def cmd_today(args):
    """Show today's usage."""
    ledger = _load_ledger()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = ledger.get("daily", {}).get(today, {"count": 0, "cost": 0.0})
    print(f"Today ({today}): {daily['count']} images, ${daily['cost']:.3f}")


def cmd_estimate(args):
    """Estimate cost for a batch."""
    cost_per = _lookup_cost(args.model, args.resolution, getattr(args, "batch", False))
    total = round(cost_per * args.count, 3)
    print(f"Model:      {args.model}")
    print(f"Resolution: {args.resolution}")
    print(f"Count:      {args.count}")
    print(f"Cost/image: ${cost_per:.3f}")
    print(f"Total est:  ${total:.3f}")
    if not getattr(args, "batch", False):
        batch_total = round(cost_per * BATCH_DISCOUNT * args.count, 3)
        print(f"Batch est:  ${batch_total:.3f} (50% discount)")


def cmd_reset(args):
    """Reset the ledger."""
    if not args.confirm:
        print("Error: Pass --confirm to reset the cost ledger.", file=sys.stderr)
        sys.exit(1)
    _save_ledger({"total_cost": 0.0, "total_images": 0, "entries": [], "daily": {}})
    print("Cost ledger reset.")


def main():
    parser = argparse.ArgumentParser(description="Banana Claude Cost Tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="Log a generation")
    p_log.add_argument("--model", required=True, help="Model ID")
    p_log.add_argument("--resolution", required=True, help="Resolution (512, 1K, 2K, 4K)")
    p_log.add_argument("--prompt", required=True, help="Brief prompt description")
    p_log.add_argument("--batch", action="store_true", help="Batch API (50%% discount)")

    # summary
    sub.add_parser("summary", help="Show cost summary")

    # today
    sub.add_parser("today", help="Show today's usage")

    # estimate
    p_est = sub.add_parser("estimate", help="Estimate batch cost")
    p_est.add_argument("--model", required=True, help="Model ID")
    p_est.add_argument("--resolution", required=True, help="Resolution (512, 1K, 2K, 4K)")
    p_est.add_argument("--count", required=True, type=int, help="Number of images")
    p_est.add_argument("--batch", action="store_true", help="Use batch pricing (50%% discount)")

    # reset
    p_reset = sub.add_parser("reset", help="Reset cost ledger")
    p_reset.add_argument("--confirm", action="store_true", help="Confirm reset")

    args = parser.parse_args()
    cmds = {"log": cmd_log, "summary": cmd_summary, "today": cmd_today,
            "estimate": cmd_estimate, "reset": cmd_reset}
    cmds[args.command](args)


if __name__ == "__main__":
    main()
