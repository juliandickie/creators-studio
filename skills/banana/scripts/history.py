#!/usr/bin/env python3
"""Banana Claude -- Session History Tracker

Track image generation history per session and provide gallery/export features.

Usage:
    history.py log --prompt "..." --image-path PATH --model MODEL --ratio RATIO --resolution RES
    history.py list [--session-id ID] [--limit 20]
    history.py show --index N [--session-id ID]
    history.py export --format md [--session-id ID] [--output PATH]
    history.py sessions [--limit 10]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HISTORY_DIR = Path.home() / ".banana" / "history"


def _get_history_dir():
    """Return the history directory, creating it if needed."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR


def _get_latest_session_id():
    """Scan history dir for the most recent session file."""
    hist = _get_history_dir()
    files = sorted(hist.glob("*.json"), key=lambda f: f.stem, reverse=True)
    if not files:
        print("Error: No session history found.", file=sys.stderr)
        sys.exit(1)
    return files[0].stem


def _load_session(session_id):
    """Load a session JSON file, return dict."""
    path = _get_history_dir() / f"{session_id}.json"
    if not path.exists():
        print(f"Error: Session '{session_id}' not found.", file=sys.stderr)
        sys.exit(1)
    with open(path, "r") as f:
        return json.load(f)


def _save_session(session_id, data):
    """Atomic write: write to .tmp then rename."""
    hist = _get_history_dir()
    tmp_path = hist / f"{session_id}.json.tmp"
    final_path = hist / f"{session_id}.json"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(str(tmp_path), str(final_path))


def _generate_session_id():
    """Generate session ID: YYYYMMDD_HHMMSS_PID."""
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"


def cmd_log(args):
    """Append an entry to a session, print JSON confirmation."""
    session_id = args.session_id or _generate_session_id()
    hist = _get_history_dir()
    path = hist / f"{session_id}.json"

    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = {
            "session_id": session_id,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "entries": [],
        }

    index = len(data["entries"]) + 1
    entry = {
        "index": index,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompt": args.prompt,
        "user_brief": args.user_brief or "",
        "image_path": args.image_path,
        "model": args.model,
        "aspect_ratio": args.ratio,
        "resolution": args.resolution,
        "domain_mode": args.domain or "",
        "preset": args.preset or "",
        "cost": args.cost or 0.0,
        "tags": [],
    }
    data["entries"].append(entry)
    _save_session(session_id, data)

    print(json.dumps({"session_id": session_id, "index": index, "logged": True}))


def cmd_list(args):
    """Print JSON array of entries for a session."""
    session_id = args.session_id or _get_latest_session_id()
    data = _load_session(session_id)

    entries = data["entries"]
    limit = args.limit or 20
    entries = entries[-limit:]

    items = []
    total_cost = 0.0
    for e in data["entries"]:
        total_cost += e.get("cost", 0.0)
    for e in entries:
        items.append({
            "index": e["index"],
            "timestamp": e["timestamp"],
            "brief": e.get("user_brief") or e["prompt"][:60],
            "path": e["image_path"],
            "cost": e.get("cost", 0.0),
        })

    result = {
        "session_id": session_id,
        "entries": items,
        "total_entries": len(data["entries"]),
        "total_cost": round(total_cost, 4),
    }
    print(json.dumps(result, indent=2))


def cmd_show(args):
    """Print full JSON for one entry by index."""
    session_id = args.session_id or _get_latest_session_id()
    data = _load_session(session_id)

    for entry in data["entries"]:
        if entry["index"] == args.index:
            print(json.dumps(entry, indent=2))
            return

    print(f"Error: No entry with index {args.index} in session '{session_id}'.", file=sys.stderr)
    sys.exit(1)


def cmd_export(args):
    """Generate a markdown gallery for a session."""
    session_id = args.session_id or _get_latest_session_id()
    data = _load_session(session_id)

    lines = [f"# Session Gallery: {session_id}", ""]
    for e in data["entries"]:
        brief = e.get("user_brief") or e["prompt"][:60]
        lines.append(f"## Image {e['index']}: {brief}")
        lines.append(f"![Image {e['index']}]({e['image_path']})")
        lines.append(f"- **Prompt:** {e['prompt']}")
        lines.append(f"- **Model:** {e['model']} | **Ratio:** {e['aspect_ratio']} | **Resolution:** {e['resolution']}")
        if e.get("domain_mode") or e.get("preset"):
            parts = []
            if e.get("domain_mode"):
                parts.append(f"**Domain:** {e['domain_mode']}")
            if e.get("preset"):
                parts.append(f"**Preset:** {e['preset']}")
            lines.append(f"- {' | '.join(parts)}")
        if e.get("cost"):
            lines.append(f"- **Cost:** ${e['cost']:.3f}")
        lines.append("")

    md = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(md)
        print(json.dumps({"exported": True, "path": args.output, "entries": len(data["entries"])}))
    else:
        print(md)


def cmd_sessions(args):
    """List all session files with date, entry count, total cost."""
    hist = _get_history_dir()
    files = sorted(hist.glob("*.json"), key=lambda f: f.stem, reverse=True)
    limit = args.limit or 10
    files = files[:limit]

    sessions = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            total_cost = sum(e.get("cost", 0.0) for e in data.get("entries", []))
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "created": data.get("created", "")[:10],
                "entries": len(data.get("entries", [])),
                "total_cost": round(total_cost, 4),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    result = {"sessions": sessions, "total_sessions": len(list(hist.glob("*.json")))}
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Banana Claude Session History")
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="Log a generation to session history")
    p_log.add_argument("--prompt", required=True, help="Full generation prompt")
    p_log.add_argument("--image-path", required=True, help="Path to generated image")
    p_log.add_argument("--model", required=True, help="Model ID")
    p_log.add_argument("--ratio", required=True, help="Aspect ratio (e.g. 16:9)")
    p_log.add_argument("--resolution", required=True, help="Resolution (512, 1K, 2K, 4K)")
    p_log.add_argument("--domain", help="Domain mode (e.g. Product, Portrait)")
    p_log.add_argument("--preset", help="Brand Style Guide preset name")
    p_log.add_argument("--cost", type=float, help="Generation cost in USD")
    p_log.add_argument("--session-id", help="Session ID (auto-generated if omitted)")
    p_log.add_argument("--user-brief", help="Original user request summary")

    # list
    p_list = sub.add_parser("list", help="List session entries")
    p_list.add_argument("--session-id", help="Session ID (latest if omitted)")
    p_list.add_argument("--limit", type=int, default=20, help="Max entries to show")

    # show
    p_show = sub.add_parser("show", help="Show full details for one entry")
    p_show.add_argument("--index", required=True, type=int, help="Entry index number")
    p_show.add_argument("--session-id", help="Session ID (latest if omitted)")

    # export
    p_export = sub.add_parser("export", help="Export session as markdown gallery")
    p_export.add_argument("--format", default="md", choices=["md"], help="Export format")
    p_export.add_argument("--session-id", help="Session ID (latest if omitted)")
    p_export.add_argument("--output", help="Output file path (stdout if omitted)")

    # sessions
    p_sessions = sub.add_parser("sessions", help="List all sessions")
    p_sessions.add_argument("--limit", type=int, default=10, help="Max sessions to show")

    args = parser.parse_args()
    cmds = {
        "log": cmd_log, "list": cmd_list, "show": cmd_show,
        "export": cmd_export, "sessions": cmd_sessions,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
