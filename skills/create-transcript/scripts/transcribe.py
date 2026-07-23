#!/usr/bin/env python3
"""creators-studio - /create-transcript speech-to-text runner.

Transcribes audio/video via ElevenLabs Scribe v2 (batch), caches the raw JSON,
and renders every requested human format from that cache. The API is called
exactly once per source file; renames and added formats regenerate from the
cached JSON and never re-charge.

Subcommands:
    transcribe <file|dir>   Transcribe a file or (with --batch / a dir) a folder.
    rename --json X.json    Re-render formats from cache with named speakers.
    cost <file|dir>         Estimate audio-minutes before running (no price).
    status                  Check API key + ffmpeg/ffprobe + config keyterms.

Auth resolution order (same as audio_pipeline.py):
    --api-key  >  $ELEVENLABS_API_KEY / $XI_API_KEY  >  config elevenlabs_api_key

Stdlib only. Pairs with formats.py (pure renderers) in this directory.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import formats  # noqa: E402  (sibling module)

# ElevenLabs Scribe v2 batch endpoint.
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
API_MODEL_ID = "scribe_v2"          # API model_id (underscore)
REGISTRY_MODEL = "scribe-v2"        # registry / cost-tracker id (hyphen)
USER_AGENT = "creators-studio/4.5.0 (+https://github.com/juliandickie/creators-studio)"

MEDIA_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
              ".webm", ".mp4", ".mov", ".mkv", ".m4v", ".wmv", ".avi"}
ALL_FORMATS = ("md", "srt", "vtt", "chapters", "txt", "json")
DEFAULT_FORMATS = ("md", "json")    # SKILL.md widens to srt/vtt for video sources

# Documented ElevenLabs keyterm rules (dev-docs/elevenlabs-llms-full.txt).
KEYTERM_MAX = 1000
KEYTERM_MAX_CHARS = 50
KEYTERM_FORBIDDEN = set("<>{}[]\\")
KEYTERM_SURCHARGE_NOTE = "keyterms add a documented +20% surcharge on base transcription cost"
KEYTERM_MIN_BILL_NOTE = ">100 keyterms forces a 20s minimum billable duration per request"

# Small, empty-safe shipped default. Julian's standing vocabulary lives in
# ~/.creators-studio/config.json (transcription.keyterms) - see keyterms.md.
DEFAULT_KEYTERMS: list[str] = []


class NoAudioStreamError(Exception):
    """Raised when a source file has no audio to transcribe - fail loud."""


# --------------------------------------------------------------------------- #
# Config + auth (pure where possible)
# --------------------------------------------------------------------------- #
def _config_path() -> Path:
    """~/.creators-studio/config.json via the plugin's single source of truth,
    with a stdlib fallback if paths.py isn't importable in isolation."""
    try:
        root_scripts = Path(__file__).resolve().parents[3] / "scripts"
        sys.path.insert(0, str(root_scripts))
        import paths  # type: ignore
        return paths.config_path()
    except Exception:
        return Path.home() / ".creators-studio" / "config.json"


def load_config() -> dict:
    p = _config_path()
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def get_api_key(cli_key: str | None, config: dict, environ: dict) -> str:
    """Resolve the ElevenLabs key. Pure - inject environ/config for testing."""
    if cli_key:
        return cli_key
    for var in ("ELEVENLABS_API_KEY", "XI_API_KEY"):
        if environ.get(var):
            return environ[var]
    key = config.get("elevenlabs_api_key")
    if key:
        return key
    raise SystemExit(
        "ERROR: no ElevenLabs API key found. Set ELEVENLABS_API_KEY, pass "
        "--api-key, or add 'elevenlabs_api_key' to ~/.creators-studio/config.json"
    )


# --------------------------------------------------------------------------- #
# Keyterms - three-tier merge + sanitisation (pure)
# --------------------------------------------------------------------------- #
def sanitize_keyterms(terms: list[str]) -> tuple[list[str], list[str]]:
    """Enforce the documented Scribe keyterm rules. Returns (kept, dropped)."""
    kept: list[str] = []
    dropped: list[str] = []
    for raw in terms:
        t = raw.strip()
        if not t:
            continue
        if len(t) >= KEYTERM_MAX_CHARS:
            dropped.append(f"{t!r} (>= {KEYTERM_MAX_CHARS} chars)")
            continue
        if any(c in KEYTERM_FORBIDDEN for c in t):
            dropped.append(f"{t!r} (forbidden character)")
            continue
        if len(t.split()) > 5:
            dropped.append(f"{t!r} (> 5 words)")
            continue
        if t not in kept:
            kept.append(t)
    return kept[:KEYTERM_MAX], dropped


def resolve_keyterm_sets(set_names: str | None, config: dict) -> tuple[list[str], list[str]]:
    """Expand named --keyterm-set values into their terms.

    Named sets live under config.transcription.keyterm_sets. Returns
    (terms, unknown_set_names) so the caller can fail loud on a typo'd set name
    instead of silently transcribing with no bias applied.
    """
    available = config.get("transcription", {}).get("keyterm_sets", {}) or {}
    names = [s.strip() for s in set_names.split(",")] if set_names else []
    terms: list[str] = []
    unknown: list[str] = []
    for n in (n for n in names if n):
        if n in available:
            for t in (available[n] or []):
                if t and t not in terms:
                    terms.append(t)
        else:
            unknown.append(n)
    return terms, unknown


def resolve_keyterms(cli_keyterms: str | None, set_terms: list[str] | None = None,
                     replace: bool = False, config: dict | None = None) -> list[str]:
    """Merge every keyterm source into the final deduped, sanitised list.

    Union priority: ad-hoc --keyterms, then activated --keyterm-set terms, then
    the always-on config base (transcription.keyterms), then the shipped default.
    With replace=True (--keyterms-replace) only the terms named THIS run are used
    (ad-hoc flags + activated sets); the always-on base and default are skipped.
    That is the per-video escape hatch from a standing list.
    """
    config = config or {}
    cli = [k.strip() for k in cli_keyterms.split(",")] if cli_keyterms else []
    cli = [k for k in cli if k]
    sets = list(set_terms or [])
    base = config.get("transcription", {}).get("keyterms", []) or []

    sources = (cli, sets) if replace else (cli, sets, base, DEFAULT_KEYTERMS)
    merged: list[str] = []
    for source in sources:
        for k in source:
            if k and k not in merged:
                merged.append(k)
    kept, _ = sanitize_keyterms(merged)
    return kept


# --------------------------------------------------------------------------- #
# Speakers (pure)
# --------------------------------------------------------------------------- #
def parse_speakers(spec: str | None) -> dict[str, str]:
    """'0=Julian,1=Dr Ahmad' -> {'speaker_0': 'Julian', 'speaker_1': 'Dr Ahmad'}."""
    out: dict[str, str] = {}
    if not spec:
        return out
    for pair in spec.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            continue
        if not k.startswith("speaker_"):
            k = f"speaker_{k}"
        out[k] = v
    return out


# --------------------------------------------------------------------------- #
# Multipart (pure body build + thin network send)
# --------------------------------------------------------------------------- #
def build_multipart(fields: dict, files: list[tuple[str, str, bytes]]) -> tuple[str, bytes]:
    """Build a multipart/form-data body. A list-valued field is emitted as
    repeated parts (how Scribe expects the `keyterms` array). Returns
    (content_type, body_bytes). Pure - unit-testable without a socket."""
    boundary = "----creatorsstudio" + uuid.uuid4().hex
    buf = bytearray()

    def add_field(name: str, value: str) -> None:
        buf.extend(f"--{boundary}\r\n".encode())
        buf.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.extend(f"{value}\r\n".encode())

    for name, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                add_field(name, str(item))
        elif isinstance(value, bool):
            add_field(name, "true" if value else "false")
        else:
            add_field(name, str(value))

    for name, filename, content in files:
        buf.extend(f"--{boundary}\r\n".encode())
        buf.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            .encode()
        )
        buf.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        buf.extend(content)
        buf.extend(b"\r\n")

    buf.extend(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", bytes(buf)


def post_multipart(url: str, fields: dict, files: list[tuple[str, str, bytes]],
                   api_key: str, timeout: int = 600) -> dict:
    content_type, body = build_multipart(fields, files)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("xi-api-key", api_key)
    req.add_header("Content-Type", content_type)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------- #
# Media prep (subprocess + pure parse)
# --------------------------------------------------------------------------- #
def parse_probe(probe: dict) -> tuple[float, bool]:
    """Pure. (duration_secs, has_audio) from an ffprobe -of json payload."""
    streams = probe.get("streams", []) or []
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    try:
        duration = float(probe.get("format", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    return duration, has_audio


def probe_media(path: str) -> tuple[float, bool]:
    cmd = ["ffprobe", "-v", "error", "-show_entries",
           "format=duration:stream=codec_type", "-of", "json", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr.strip()}")
    return parse_probe(json.loads(r.stdout or "{}"))


def extract_audio(path: str, workdir: Path) -> Path:
    """Demux to mono 16 kHz MP3 - lossless for Scribe (it resamples to 16 kHz),
    ~20x smaller upload than shipping a video container."""
    out = workdir / (Path(path).stem + ".mp3")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", path,
           "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k",
           str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on {path}: {r.stderr.strip()}")
    return out


# --------------------------------------------------------------------------- #
# Rendering + cost log
# --------------------------------------------------------------------------- #
def write_formats(data: dict, stem: str, out_dir: Path, fmts, source_name: str,
                  speaker_names: dict | None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def emit(name: str, content: str) -> None:
        p = out_dir / f"{stem}.{name}"
        p.write_text(content)
        written.append(p)

    for fmt in fmts:
        if fmt == "json":
            emit("json", json.dumps(data, indent=2))
        elif fmt == "md":
            emit("md", formats.render_markdown(data, source_name=source_name,
                                               speaker_names=speaker_names,
                                               title=data.get("_title")))
        elif fmt == "srt":
            emit("srt", formats.render_srt(data))
        elif fmt == "vtt":
            emit("vtt", formats.render_vtt(data))
        elif fmt == "chapters":
            (out_dir / f"{stem}.chapters.txt").write_text(formats.render_chapters(data))
            written.append(out_dir / f"{stem}.chapters.txt")
        elif fmt == "txt":
            emit("txt", formats.render_plaintext(data))
    return written


def log_cost(duration_secs: float) -> None:
    """Non-blocking usage log. Scribe is subscription-billed, so this records
    audio-seconds, not dollars. A logging failure never blocks output."""
    try:
        tracker = Path(__file__).resolve().parents[2] / "create-image" / "scripts" / "cost_tracker.py"
        if not tracker.exists():
            return
        subprocess.run(
            [sys.executable, str(tracker), "log", "--model", REGISTRY_MODEL,
             "--resolution", f"{int(round(duration_secs))}s",
             "--prompt", "speech-to-text"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Core: transcribe one file
# --------------------------------------------------------------------------- #
def transcribe_file(path: str, *, api_key: str, keyterms: list[str], language: str | None,
                    diarize: bool, out_dir: Path, fmts, speaker_names: dict | None,
                    title: str | None = None) -> dict:
    duration, has_audio = probe_media(path)
    if not has_audio:
        raise NoAudioStreamError(f"{path} has no audio stream - nothing to transcribe")

    with tempfile.TemporaryDirectory(prefix="cs-stt-") as tmp:
        audio = extract_audio(path, Path(tmp))
        fields: dict = {
            "model_id": API_MODEL_ID,
            "diarize": diarize,
            "tag_audio_events": True,
            "timestamps_granularity": "word",
        }
        if language:
            fields["language_code"] = language
        if keyterms:
            fields["keyterms"] = keyterms
        files = [("file", audio.name, audio.read_bytes())]
        data = post_multipart(ELEVENLABS_STT_URL, fields, files, api_key)

    data["_source_name"] = Path(path).name
    if speaker_names:
        data["_speaker_names"] = speaker_names
    if title:
        data["_title"] = title

    source_stem = Path(path).stem
    out_stem = f"{title} - {source_stem}" if title else source_stem
    written = write_formats(data, out_stem, out_dir, fmts, Path(path).name, speaker_names)
    log_cost(data.get("audio_duration_secs", duration))

    speakers = sorted({w.get("speaker_id") for w in data.get("words", []) if w.get("speaker_id")})
    return {
        "source": path,
        "duration_secs": data.get("audio_duration_secs", duration),
        "language": data.get("language_code"),
        "speakers": len(speakers),
        "formats": [p.name for p in written],
        "json": str(out_dir / f"{out_stem}.json"),
        "status": "ok",
    }


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def discover_media(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*")
                  if p.is_file() and p.suffix.lower() in MEDIA_EXTS
                  and "transcripts" not in p.parts)


def default_out_dir(target: Path) -> Path:
    base = target.parent if target.is_file() else target
    return base / "transcripts"


# --------------------------------------------------------------------------- #
# Subcommand handlers
# --------------------------------------------------------------------------- #
def cmd_transcribe(args) -> int:
    config = load_config()
    api_key = get_api_key(args.api_key, config, os.environ)
    set_terms, unknown_sets = resolve_keyterm_sets(args.keyterm_set, config)
    if unknown_sets:
        available = sorted((config.get("transcription", {}).get("keyterm_sets", {}) or {}))
        print(f"ERROR: unknown keyterm set(s): {', '.join(unknown_sets)}. "
              f"Available: {', '.join(available) if available else '(none defined in config)'}",
              file=sys.stderr)
        return 1
    keyterms = resolve_keyterms(args.keyterms, set_terms, args.keyterms_replace, config)
    fmts = _parse_formats(args.formats)
    speaker_names = parse_speakers(args.speakers) or None

    target = Path(args.target).expanduser()
    if not target.exists():
        print(f"ERROR: not found: {target}", file=sys.stderr)
        return 1
    media = discover_media(target)
    if not media:
        print(f"ERROR: no audio/video files found under {target}", file=sys.stderr)
        return 1

    out_dir = Path(args.output_dir).expanduser() if args.output_dir else default_out_dir(target)

    if keyterms:
        via = f" via set(s) {args.keyterm_set}" if args.keyterm_set else ""
        print(f"Keyterms active ({len(keyterms)}){via}: {', '.join(keyterms[:8])}"
              f"{'...' if len(keyterms) > 8 else ''}")
        print(f"  NOTE: {KEYTERM_SURCHARGE_NOTE}.")
        if len(keyterms) > 100:
            print(f"  NOTE: {KEYTERM_MIN_BILL_NOTE}.")

    results = []
    for i, m in enumerate(media, 1):
        label = f"[{i}/{len(media)}] {m.name}"
        try:
            print(f"{label} - transcribing…")
            res = transcribe_file(
                str(m), api_key=api_key, keyterms=keyterms, language=args.language,
                diarize=not args.no_diarize, out_dir=out_dir, fmts=fmts,
                speaker_names=speaker_names, title=(args.title if len(media) == 1 else None),
            )
            results.append(res)
            print(f"{label} - ok ({res['speakers']} speaker(s), "
                  f"{formats.fmt_time(res['duration_secs'], 'clock')}, "
                  f"{len(res['formats'])} files)")
        except (NoAudioStreamError, RuntimeError, urllib.error.HTTPError,
                urllib.error.URLError) as e:
            results.append({"source": str(m), "status": "fail", "error": str(e)})
            print(f"{label} - FAILED: {e}", file=sys.stderr)

    return _summarize(results, out_dir)


def cmd_rename(args) -> int:
    json_path = Path(args.json).expanduser()
    if not json_path.exists():
        print(f"ERROR: not found: {json_path}", file=sys.stderr)
        return 1
    data = json.loads(json_path.read_text())
    speaker_names = parse_speakers(args.speakers)
    if not speaker_names:
        print("ERROR: --speakers is required, e.g. --speakers \"0=Julian,1=Dr Ahmad\"",
              file=sys.stderr)
        return 1
    data["_speaker_names"] = {**data.get("_speaker_names", {}), **speaker_names}
    json_path.write_text(json.dumps(data, indent=2))

    fmts = _parse_formats(args.formats) if args.formats else \
        [f for f in ALL_FORMATS if (json_path.parent / f"{json_path.stem}.{f}").exists()
         or f in ("md",)]
    # Always at least refresh markdown; re-render whatever formats already exist.
    stem = json_path.stem
    source_name = args.source_name or f"{stem}"
    written = write_formats(data, stem, json_path.parent,
                            [f for f in fmts if f != "json"], source_name, speaker_names)
    print(f"Re-rendered {len(written)} file(s) with named speakers "
          f"({', '.join(f'{k}={v}' for k, v in speaker_names.items())}):")
    for p in written:
        print(f"  {p}")
    print("No API call made - regenerated from cached JSON.")
    return 0


def existing_formats(out_dir: Path, stem: str) -> list[str]:
    """Which output formats currently exist on disk for a given stem."""
    checks = {"md": f"{stem}.md", "srt": f"{stem}.srt", "vtt": f"{stem}.vtt",
              "json": f"{stem}.json", "txt": f"{stem}.txt",
              "chapters": f"{stem}.chapters.txt"}
    return [fmt for fmt, name in checks.items() if (out_dir / name).exists()]


def _format_path(out_dir: Path, stem: str, fmt: str) -> Path:
    return out_dir / (f"{stem}.chapters.txt" if fmt == "chapters" else f"{stem}.{fmt}")


def cmd_retitle(args) -> int:
    """Apply a descriptive title from cache: set the markdown H1 and prefix every
    co-located output filename with '<title> - '. No API call - re-renders from
    the cached JSON. The real video filename is kept as the tail of the name and
    in the Source file line."""
    json_path = Path(args.json).expanduser()
    if not json_path.exists():
        print(f"ERROR: not found: {json_path}", file=sys.stderr)
        return 1
    title = (args.title or "").strip()
    if not title:
        print("ERROR: --title is required.", file=sys.stderr)
        return 1

    data = json.loads(json_path.read_text())
    data["_title"] = title
    src_name = args.source_name or data.get("_source_name")
    if src_name:
        data["_source_name"] = src_name
        source_stem = Path(src_name).stem
    else:
        # Pre-4.5.0 cache with no stored source name: fall back to the current
        # stem. Pass --source-name to avoid a doubled title prefix on re-runs.
        source_stem = json_path.stem

    out_dir = json_path.parent
    cur_stem = json_path.stem
    new_stem = f"{title} - {source_stem}"
    speaker_names = data.get("_speaker_names")

    fmts = existing_formats(out_dir, cur_stem)
    if "json" not in fmts:
        fmts.append("json")

    written = write_formats(data, new_stem, out_dir, fmts, src_name or source_stem, speaker_names)

    if new_stem != cur_stem:
        for fmt in fmts:
            old = _format_path(out_dir, cur_stem, fmt)
            new = _format_path(out_dir, new_stem, fmt)
            if old.exists() and old.resolve() != new.resolve():
                old.unlink()

    print(f"Retitled to \"{title}\" - {len(written)} file(s) re-rendered (H1 + filename):")
    for p in written:
        print(f"  {p.name}")
    print("No API call made - regenerated from cached JSON.")
    return 0


def cmd_cost(args) -> int:
    target = Path(args.target).expanduser()
    if not target.exists():
        print(f"ERROR: not found: {target}", file=sys.stderr)
        return 1
    media = discover_media(target)
    total = 0.0
    rows = []
    for m in media:
        try:
            dur, has_audio = probe_media(str(m))
        except RuntimeError as e:
            rows.append((m.name, "ERR", str(e)))
            continue
        if not has_audio:
            rows.append((m.name, "no-audio", ""))
            continue
        total += dur
        rows.append((m.name, formats.fmt_time(dur, "clock"), ""))
    print(f"Files: {len(media)}")
    for name, dur, note in rows:
        print(f"  {dur:>10}  {name}  {note}")
    print(f"\nTotal audio: {formats.fmt_time(total, 'clock')} "
          f"({total/60:.1f} min, {total:.0f}s)")
    print("Scribe v2 is subscription/credit billed per second of audio; the plugin "
          "does not hardcode a per-minute price. See your ElevenLabs plan for the rate.")
    return 0


def cmd_status(args) -> int:
    config = load_config()
    ok = True
    try:
        get_api_key(args.api_key, config, os.environ)
        print("ElevenLabs API key: found")
    except SystemExit:
        ok = False
        print("ElevenLabs API key: MISSING (set ELEVENLABS_API_KEY or config)")
    for tool in ("ffmpeg", "ffprobe"):
        found = subprocess.run(["which", tool], capture_output=True, text=True).returncode == 0
        print(f"{tool}: {'found' if found else 'MISSING'}")
        ok = ok and found
    cfg_terms = config.get("transcription", {}).get("keyterms", []) or []
    print(f"Config keyterms (always-on): {len(cfg_terms)}"
          + (f" ({', '.join(cfg_terms[:6])}{'...' if len(cfg_terms) > 6 else ''})" if cfg_terms else ""))
    cfg_sets = config.get("transcription", {}).get("keyterm_sets", {}) or {}
    if cfg_sets:
        print("Keyterm sets: "
              + ", ".join(f"{name} ({len(terms or [])})" for name, terms in cfg_sets.items()))
    else:
        print("Keyterm sets: none defined (add transcription.keyterm_sets to config)")
    print(f"Model: {API_MODEL_ID}  |  formats: {', '.join(ALL_FORMATS)}")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# Helpers + arg parsing
# --------------------------------------------------------------------------- #
def _parse_formats(spec: str | None):
    if not spec:
        return list(DEFAULT_FORMATS)
    if spec.strip().lower() == "all":
        return list(ALL_FORMATS)
    chosen = [f.strip().lower() for f in spec.split(",") if f.strip()]
    bad = [f for f in chosen if f not in ALL_FORMATS]
    if bad:
        raise SystemExit(f"ERROR: unknown format(s): {', '.join(bad)}. "
                         f"Choose from: {', '.join(ALL_FORMATS)}")
    if "json" not in chosen:
        chosen.append("json")   # cache is always written
    return chosen


def _summarize(results: list[dict], out_dir: Path) -> int:
    ok = [r for r in results if r.get("status") == "ok"]
    fail = [r for r in results if r.get("status") == "fail"]
    print("\n" + "=" * 60)
    print(f"Transcribed {len(ok)}/{len(results)} file(s) → {out_dir}")
    for r in ok:
        print(f"  ✓ {Path(r['source']).name}  "
              f"{formats.fmt_time(r['duration_secs'], 'clock')}  "
              f"{r['speakers']} spk  [{', '.join(r['formats'])}]")
    for r in fail:
        print(f"  ✗ {Path(r['source']).name} - {r['error']}")
    if fail:
        print(f"\n{len(fail)} file(s) FAILED - see errors above.")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="transcribe.py",
        description="Transcribe audio/video via ElevenLabs Scribe v2 and render "
                    "markdown / SRT / VTT / chapters / plaintext from a cached JSON.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcribe", help="Transcribe a file or folder.")
    t.add_argument("target", help="Audio/video file, or a directory (with --batch).")
    t.add_argument("--formats", help=f"Comma list from {','.join(ALL_FORMATS)} or 'all'. "
                                     f"Default: {','.join(DEFAULT_FORMATS)} (json always written).")
    t.add_argument("--keyterms", help="Comma-separated ad-hoc bias terms (brand/product names).")
    t.add_argument("--keyterm-set",
                   help="Activate named keyterm set(s) from config.transcription.keyterm_sets, "
                        "comma-separated (e.g. 'dental' or 'dental,agency'). See status for available sets.")
    t.add_argument("--keyterms-replace", action="store_true",
                   help="Use only the terms named this run (--keyterms + --keyterm-set), "
                        "ignoring the always-on config keyterms list.")
    t.add_argument("--language", help="ISO-639 code (e.g. eng). Default: auto-detect.")
    t.add_argument("--speakers", help='Name speakers, e.g. "0=Julian,1=Dr Ahmad".')
    t.add_argument("--output-dir", help="Where to write outputs. Default: <source>/transcripts.")
    t.add_argument("--batch", action="store_true", help="Treat a directory target as a batch.")
    t.add_argument("--no-diarize", action="store_true", help="Disable speaker separation.")
    t.add_argument("--title", help="Descriptive title for the H1 and filename prefix "
                                   "(single file only). Usually applied afterwards via retitle.")
    t.add_argument("--api-key", help="Override ElevenLabs key.")
    t.set_defaults(func=cmd_transcribe)

    r = sub.add_parser("rename", help="Re-render formats from cache with named speakers.")
    r.add_argument("--json", required=True, help="Cached <name>.json to re-render.")
    r.add_argument("--speakers", required=True, help='e.g. "0=Julian,1=Dr Ahmad".')
    r.add_argument("--formats", help="Formats to re-render (default: those already present).")
    r.add_argument("--source-name", help="Source filename for the markdown header.")
    r.set_defaults(func=cmd_rename)

    rt = sub.add_parser("retitle", help="Set a descriptive H1 + filename prefix from cache "
                                        "(keeps the video name at the end). No API call.")
    rt.add_argument("--json", required=True, help="Cached <name>.json to retitle.")
    rt.add_argument("--title", required=True, help='Descriptive title, e.g. "Design Videos in Reverse".')
    rt.add_argument("--source-name", help="Original video filename (for pre-4.5.0 caches "
                                          "with no stored source name).")
    rt.set_defaults(func=cmd_retitle)

    c = sub.add_parser("cost", help="Estimate audio-minutes before running.")
    c.add_argument("target", help="File or directory.")
    c.set_defaults(func=cmd_cost)

    s = sub.add_parser("status", help="Check key + ffmpeg + config.")
    s.add_argument("--api-key", help="Override ElevenLabs key.")
    s.set_defaults(func=cmd_status)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    known = {"transcribe", "rename", "retitle", "cost", "status"}
    # Ergonomic bare form: `transcribe.py foo.mp4` == `transcribe.py transcribe foo.mp4`.
    if argv and argv[0] not in known and not argv[0].startswith("-"):
        argv.insert(0, "transcribe")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
