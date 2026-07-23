"""Pure renderers: a parsed ElevenLabs Scribe v2 response → readable formats.

Every function here is a PURE function of the parsed response dict. No network,
no filesystem, no global state. This is what makes the skill's core testable
offline and what makes re-rendering (speaker renames, added formats) free - the
API is called once, its JSON cached, and every human format is a render of that
cache.

Scribe response shape (only these keys are read; extras like `transcription_id`
and per-word `logprob` are tolerated and ignored):

    {
      "language_code": "eng",
      "language_probability": 1.0,
      "text": "One of the problems ...",
      "audio_duration_secs": 49.997,          # optional
      "words": [
        {"text": "One", "start": 0.1, "end": 0.3, "type": "word",
         "speaker_id": "speaker_0"},
        {"text": " ",   "start": 0.3, "end": 0.32, "type": "spacing", ...},
        {"text": "[laughs]", "start": 4.6, "end": 4.7, "type": "audio_event", ...},
        ...
      ]
    }

`type` is one of: "word", "spacing", "audio_event".
"""
from __future__ import annotations

import textwrap

# Subtitle segmentation defaults - tuned for comfortable reading speed, not turns.
DEFAULT_CUE_MAX_DUR = 7.0     # seconds
DEFAULT_CUE_MAX_CHARS = 42    # characters per cue
DEFAULT_CHAPTER_MIN_GAP = 2.0  # seconds of silence that starts a new chapter


# --------------------------------------------------------------------------- #
# Timecodes
# --------------------------------------------------------------------------- #
def fmt_time(seconds: float, style: str = "clock") -> str:
    """Format a timestamp.

    clock : "M:SS" or "H:MM:SS" (no leading zero on the largest unit) - markdown,
            chapters. Floors to whole seconds.
    hms   : "HH:MM:SS" zero-padded.
    srt   : "HH:MM:SS,mmm" (comma millis).
    vtt   : "HH:MM:SS.mmm" (dot millis).
    """
    seconds = max(0.0, float(seconds))
    if style in ("srt", "vtt"):
        total_ms = int(round(seconds * 1000))
        h, rem = divmod(total_ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1000)
        sep = "," if style == "srt" else "."
        return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"

    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if style == "hms":
        return f"{h:02d}:{m:02d}:{s:02d}"
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# --------------------------------------------------------------------------- #
# Speaker helpers
# --------------------------------------------------------------------------- #
def _norm_names(speaker_names: dict | None) -> dict[str, str]:
    """Normalise a speaker-name map so both "1" and "speaker_1" keys work."""
    if not speaker_names:
        return {}
    out: dict[str, str] = {}
    for k, v in speaker_names.items():
        key = str(k)
        if not key.startswith("speaker_"):
            key = f"speaker_{key}"
        out[key] = v
    return out


def _label(speaker_id: str, names: dict[str, str]) -> str:
    if speaker_id in names:
        return names[speaker_id]
    suffix = speaker_id.split("_")[-1]
    return f"Speaker {suffix}"


def _piece(word: dict) -> str:
    """The text a word contributes. Audio events get padding so they never fuse
    onto an adjacent word (`laughs]What` → `[laughs] What`)."""
    if word.get("type") == "audio_event":
        return f" {word['text']} "
    return word["text"]


def _clean(text: str) -> str:
    return " ".join(text.split())


# --------------------------------------------------------------------------- #
# Turn grouping (markdown, chapters) - folds contiguous same-speaker runs
# --------------------------------------------------------------------------- #
def group_turns(words: list[dict], speaker_names: dict | None = None) -> list[dict]:
    """Fold the flat word stream into contiguous same-speaker turns.

    Returns [{speaker_id, label, start, end, text}], audio events inlined.
    """
    names = _norm_names(speaker_names)
    turns: list[dict] = []
    for w in words:
        spk = w.get("speaker_id") or "speaker_0"
        if turns and turns[-1]["speaker_id"] == spk:
            turns[-1]["_buf"].append(_piece(w))
            turns[-1]["end"] = w.get("end", turns[-1]["end"])
        else:
            turns.append({
                "speaker_id": spk,
                "start": w.get("start", 0.0),
                "end": w.get("end", 0.0),
                "_buf": [_piece(w)],
            })
    result = []
    for t in turns:
        text = _clean("".join(t.pop("_buf")))
        if not text:
            continue
        t["text"] = text
        t["label"] = _label(t["speaker_id"], names)
        result.append(t)
    return result


# --------------------------------------------------------------------------- #
# Cue segmentation (SRT, VTT) - independent of speaker, serves reading speed
# --------------------------------------------------------------------------- #
def segment_cues(words: list[dict],
                 max_dur: float = DEFAULT_CUE_MAX_DUR,
                 max_chars: int = DEFAULT_CUE_MAX_CHARS) -> list[dict]:
    """Group words into subtitle cues bounded by duration and line length.

    Returns [{index, start, end, text}]. Speaker changes do NOT force a break -
    subtitle timing is about reading speed, not conversation structure.
    """
    cues: list[dict] = []
    cur: dict | None = None

    def close():
        nonlocal cur
        if cur is not None:
            cur["text"] = _clean("".join(cur["_buf"]))
            if cur["text"]:
                cues.append(cur)
        cur = None

    for w in words:
        if w.get("type") == "spacing":
            if cur is not None:
                cur["_buf"].append(w["text"])
            continue
        piece = w["text"]
        if cur is None:
            cur = {"start": w.get("start", 0.0), "end": w.get("end", 0.0),
                   "_buf": [piece]}
            continue
        prospective = len(_clean("".join(cur["_buf"]) + " " + piece))
        duration = w.get("end", cur["end"]) - cur["start"]
        if prospective > max_chars or duration > max_dur:
            close()
            cur = {"start": w.get("start", 0.0), "end": w.get("end", 0.0),
                   "_buf": [piece]}
        else:
            cur["_buf"].append(piece)
            cur["end"] = w.get("end", cur["end"])
    close()

    for i, c in enumerate(cues, 1):
        c["index"] = i
        del c["_buf"]
    return cues


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #
def render_markdown(data: dict, source_name: str | None = None,
                    speaker_names: dict | None = None, title: str | None = None) -> str:
    words = data.get("words", [])
    turns = group_turns(words, speaker_names)
    speakers = sorted({w.get("speaker_id") for w in words if w.get("speaker_id")})

    # H1 is the descriptive title when set (via retitle / --title); the Source
    # file line below always keeps the real video filename for reference.
    heading = title or source_name or "Transcript"
    lines = [f"# {heading}", ""]
    if source_name:
        lines.append(f"- Source file: `{source_name}`")
    dur = data.get("audio_duration_secs")
    if dur is not None:
        lines.append(f"- Duration: {fmt_time(dur, 'clock')}")
    lines.append("- Engine: ElevenLabs Scribe v2 (`scribe_v2`), batch")
    lc = data.get("language_code")
    if lc:
        lp = data.get("language_probability")
        conf = f" (confidence {lp})" if lp is not None else ""
        lines.append(f"- Language: {lc}{conf}")
    lines.append(f"- Speakers detected: {len(speakers)}")
    lines += ["", "## Transcript", ""]

    for t in turns:
        lines.append(f"**[{fmt_time(t['start'], 'clock')}] {t['label']}**")
        lines.append("")
        lines.append(t["text"])
        lines.append("")

    text = (data.get("text") or "").strip()
    if text:
        lines += ["## Continuous text", "", text, ""]
    return "\n".join(lines)


def render_srt(data: dict) -> str:
    cues = segment_cues(data.get("words", []))
    blocks = [
        f"{c['index']}\n"
        f"{fmt_time(c['start'], 'srt')} --> {fmt_time(c['end'], 'srt')}\n"
        f"{c['text']}"
        for c in cues
    ]
    return "\n\n".join(blocks) + "\n"


def render_vtt(data: dict) -> str:
    cues = segment_cues(data.get("words", []))
    blocks = [
        f"{fmt_time(c['start'], 'vtt')} --> {fmt_time(c['end'], 'vtt')}\n"
        f"{c['text']}"
        for c in cues
    ]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def render_chapters(data: dict, min_gap: float = DEFAULT_CHAPTER_MIN_GAP) -> str:
    """YouTube-ready chapters: markers at silence boundaries + per-chapter text.

    The script only finds the boundaries and emits a lead-snippet placeholder
    title; the orchestrator (SKILL.md) rewrites those into meaningful titles.
    The first marker is forced to 0:00 per YouTube's requirement.
    """
    # Coarse paragraphs, then split into chapters on real pauses.
    paras = segment_cues(data.get("words", []), max_dur=30.0, max_chars=240)
    if not paras:
        return ""

    chapters: list[dict] = []
    prev_end: float | None = None
    for p in paras:
        gap = (p["start"] - prev_end) if prev_end is not None else 0.0
        if not chapters or gap >= min_gap:
            chapters.append({"start": p["start"], "paras": [p["text"]]})
        else:
            chapters[-1]["paras"].append(p["text"])
        prev_end = p["end"]

    markers = []
    for i, ch in enumerate(chapters):
        start = 0.0 if i == 0 else ch["start"]
        title = ch["paras"][0][:60].rstrip()
        markers.append(f"{fmt_time(start, 'clock')} {title}")

    body = []
    for i, ch in enumerate(chapters):
        start = 0.0 if i == 0 else ch["start"]
        body.append(f"[{fmt_time(start, 'clock')}] " + " ".join(ch["paras"]))

    return "\n".join(markers) + "\n\n" + "\n\n".join(body) + "\n"


def render_plaintext(data: dict, width: int = 0) -> str:
    """The canonical `text` field, optionally wrapped. Zero markup."""
    text = (data.get("text") or "").strip()
    if width and width > 0:
        text = "\n".join(textwrap.fill(line, width=width) for line in text.split("\n"))
    return text + "\n"
