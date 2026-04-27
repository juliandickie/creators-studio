# Session History Reference

> Load this when the user runs `/create-image history` or asks about their
> generation history or wants to export a gallery.

## Overview

Tracks all image generations in the current session. Each generation is logged with its prompt, settings, image path, and cost. Sessions can be exported as markdown galleries.

## Usage

```bash
# Log a generation (called automatically after each generation in Step 10)
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py log --prompt "full prompt" --image-path PATH --model MODEL --ratio RATIO --resolution RES --session-id SESSION_ID

# List entries in current session
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py list

# Show full details for one entry
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py show --index 3

# Export session as markdown gallery
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py export --format md --output ~/gallery.md

# List all past sessions
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py sessions
```

## Session IDs

Each Claude Code session gets a unique ID in the format `YYYYMMDD_HHMMSS_PID`. Generate this once at the start of a session and reuse it for all `log` calls.

If no `--session-id` is provided, commands default to the most recent session.

## Storage

Session files are stored in `~/.creators-studio/history/SESSION_ID.json`. Each file contains a JSON object with session metadata and an array of generation entries.

## Integration with Pipeline

After Step 11 (Return Results), also call history.py to log the generation:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/history.py log \
    --prompt "the crafted prompt" \
    --image-path /path/to/image.png \
    --model gemini-3.1-flash-image-preview \
    --ratio 16:9 \
    --resolution 2K \
    --domain Product \
    --cost 0.078 \
    --session-id SESSION_ID
```

## Export Format

The markdown export creates a visual gallery that Claude can render inline:

```markdown
# Session Gallery: 20260409_143000

## Image 1: coffee shop hero
![Image 1](/path/to/image.png)
- **Prompt:** A ceramic pour-over coffee vessel...
- **Settings:** gemini-3.1-flash-image-preview | 16:9 | 2K
- **Cost:** $0.078
```
