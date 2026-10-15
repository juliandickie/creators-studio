#!/usr/bin/env python3
"""`transcribe.py watch`: frames plus a Scribe transcript, so Claude can watch a video.

Frame selection (scene detection with a uniform fallback, even sampling to a
cap, near-duplicate removal, cue frames) and the yt-dlp download are adapted
from the watch plugin, https://github.com/bradautomates/claude-video, under the
MIT License below. Its caption, Whisper, WhisperX and Gemini paths are not
ported: the transcript comes from ElevenLabs Scribe through transcribe.py.

    MIT License

    Copyright (c) 2026 Bradley Bonanno

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import formats
import transcribe

MAX_FPS = 2.0
SCENE_THRESHOLD = 0.20
# Fewer distinct shots than this means a static video (talking head, screen
# recording), so scene detection falls back to uniform sampling.
SCENE_MIN_FRAMES = 8
MAX_READ_DIMENSION = 1998
# Near-duplicate removal: two frames whose 16x16 RGB thumbnails differ by at
# most 2.0 (mean per channel, 0-255) count as the same. Subtle text changes can
# be missed at this size; --no-dedup keeps every frame.
DEDUP_THUMB = 16
DEDUP_THRESHOLD = 2.0
DEFAULT_MAX_FRAMES = 100
DEFAULT_RESOLUTION = 512
WATCH_FORMATS = ("md", "srt", "vtt", "json")
DOWNLOAD_ROOT = Path.home() / "Documents" / "creators_watch"
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}
SHOWINFO_TS_RE = re.compile(r"pts_time:([^\s]+)")


# --------------------------------------------------------------------------- #
# Process helpers
# --------------------------------------------------------------------------- #
def diagnostic(value, limit: int = 3000) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "").strip()[-limit:]


def run_text(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"{cmd[0]} timed out: {diagnostic(exc.stderr)}") from None
    except OSError as exc:
        raise SystemExit(f"Cannot run {cmd[0]} ({type(exc).__name__}). Check it is installed.") from None


# --------------------------------------------------------------------------- #
# Time parsing
# --------------------------------------------------------------------------- #
def parse_time(value) -> float | None:
    """Parse a finite non-negative SS, MM:SS or HH:MM:SS time."""
    if value is None or str(value).strip() == "":
        return None
    try:
        parts = str(value).strip().split(":")
        if len(parts) > 3:
            raise ValueError()
        numbers = [float(p) for p in parts]
        if any(not math.isfinite(n) or n < 0 for n in numbers):
            raise ValueError()
        if len(parts) > 1 and (any(n >= 60 for n in numbers[1:])
                               or any(n != int(n) for n in numbers[:-1])):
            raise ValueError()
        return sum(n * 60 ** i for i, n in enumerate(reversed(numbers)))
    except ValueError:
        raise SystemExit(f"Invalid time {value!r}; expected SS, MM:SS or HH:MM:SS.") from None


def parse_timestamps(value: str | None) -> list[float]:
    if not value:
        return []
    return sorted({parse_time(t.strip()) for t in value.split(",") if t.strip()})


# --------------------------------------------------------------------------- #
# Download (URLs only)
# --------------------------------------------------------------------------- #
def is_url(source: str) -> bool:
    parsed = urlparse(source)
    return not source.startswith("-") and parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _ytdlp_hint(stderr: str) -> str:
    lower = stderr.lower()
    if any(s in lower for s in ("sign in", "login required", "confirm you're not a bot", "confirm you’re not a bot")):
        return "This source needs a login; download it yourself (e.g. PullTube) and watch the local file."
    if "429" in lower or "too many requests" in lower:
        return "The site is rate limiting; wait and retry."
    if re.search(r"\b403\b", lower) or "forbidden" in lower:
        return "No generic fix for a 403; update yt-dlp (brew upgrade yt-dlp) and retry once."
    return "Check the error above; updating yt-dlp (brew upgrade yt-dlp) fixes most site breakages."


def download_url(url: str, media_dir: Path) -> tuple[Path, dict]:
    """Download one video (720p cap) into media_dir, or reuse a prior download.

    The folder name is a hash of the URL, so a follow-up question on the same
    URL reuses the file and its cached transcript instead of paying again.
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    info_path = media_dir / "info.json"
    existing = [p for p in media_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS and p.stat().st_size]
    if existing and info_path.is_file():
        return existing[0], json.loads(info_path.read_text(encoding="utf-8"))

    print("[watch] downloading with yt-dlp…", file=sys.stderr)
    record = media_dir / "final-path.jsonl"
    record.unlink(missing_ok=True)
    prefix = str(media_dir.resolve()).replace("%", "%%")
    cmd = ["yt-dlp", "--no-playlist", "--windows-filenames", "-N", "8",
           "-f", "bv*[height<=720]+ba/b[height<=720]/bv+ba/b", "--merge-output-format", "mp4",
           "-o", f"{prefix}/%(title).80B [%(id)s].%(ext)s",
           "--no-write-subs", "--no-write-auto-subs",
           "--print-to-file", "after_move:%(filepath)j", str(record).replace("%", "%%"),
           "--print-to-file", "%(.{title,uploader,channel,duration,webpage_url})j",
           str(info_path).replace("%", "%%"),
           "--", url]
    result = run_text(cmd)
    if result.returncode != 0:
        raise SystemExit(f"yt-dlp failed (exit {result.returncode}): {diagnostic(result.stderr)}\n"
                         f"{_ytdlp_hint(result.stderr)}")
    try:
        lines = record.read_text(encoding="utf-8").splitlines()
        video = Path(json.loads(lines[-1])).resolve()
        if not video.is_relative_to(media_dir.resolve()) or not video.is_file() or not video.stat().st_size:
            raise ValueError()
        info = json.loads(info_path.read_text(encoding="utf-8").splitlines()[-1])
    except (OSError, ValueError, TypeError, IndexError):
        raise SystemExit("yt-dlp did not report one completed media file.") from None
    info_path.write_text(json.dumps(info), encoding="utf-8")
    record.unlink(missing_ok=True)
    return video, info


# --------------------------------------------------------------------------- #
# Probe
# --------------------------------------------------------------------------- #
def get_metadata(video_path: str) -> dict:
    result = run_text(["ffprobe", "-v", "error", "-print_format", "json",
                       "-show_format", "-show_streams", str(Path(video_path).resolve())], timeout=30)
    if result.returncode != 0:
        raise SystemExit(f"ffprobe failed: {diagnostic(result.stderr)}")
    try:
        data = json.loads(result.stdout)
        streams, fmt = data["streams"], data.get("format", {})
        video = next((s for s in streams if s.get("codec_type") == "video"
                      and not (s.get("disposition") or {}).get("attached_pic")), {})
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        # Stream durations avoid a container's nonzero start PTS inflating the length.
        elapsed = [float(s["duration"]) for s in (video, audio) if s.get("duration") not in (None, "N/A")]
        duration = max(elapsed) if elapsed else float(fmt.get("duration"))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError()
        return {"duration_seconds": duration, "width": video.get("width"), "height": video.get("height"),
                "codec": video.get("codec_name"), "has_audio": bool(audio), "has_video": bool(video)}
    except (ValueError, TypeError, KeyError, AttributeError, StopIteration):
        raise SystemExit(f"ffprobe returned no usable duration: {diagnostic(result.stderr)}") from None


# --------------------------------------------------------------------------- #
# Frame extraction
# --------------------------------------------------------------------------- #
def _scale_filter(resolution: int) -> str:
    return (f"scale=w='min({resolution},iw)':h='min({MAX_READ_DIMENSION},ih)':"
            "force_original_aspect_ratio=decrease:force_divisible_by=2")


@lru_cache(maxsize=1)
def sync_args() -> tuple[str, str]:
    """FFmpeg 5+ uses -fps_mode; older builds only know -vsync."""
    result = run_text(["ffmpeg", "-hide_banner", "-h", "full"], timeout=30)
    text = result.stdout + result.stderr
    if re.search(r"(?m)^\s*-fps_mode\b", text):
        return "-fps_mode", "vfr"
    if re.search(r"(?m)^\s*-vsync\b", text):
        return "-vsync", "vfr"
    raise SystemExit("ffmpeg advertises neither -fps_mode nor -vsync; check the FFmpeg install.")


def _emitted_frames(files: list[Path], stderr: str, offset: float, reason: str) -> list[dict]:
    """Pair each written JPEG with the source timestamp ffmpeg's showinfo logged."""
    stamps = [float(m.group(1)) for m in SHOWINFO_TS_RE.finditer(stderr)]
    if (len(stamps) < len(files) or any(not math.isfinite(t) for t in stamps)
            or any(b < a for a, b in zip(stamps, stamps[1:]))):
        raise SystemExit("ffmpeg output is missing valid frame timestamps; refusing to mislabel images.")
    return [{"index": i, "timestamp_seconds": round(offset + stamps[i], 6), "path": str(p), "reason": reason}
            for i, p in enumerate(files)]


def _clear(out_dir: Path, pattern: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob(pattern):
        f.unlink()


def auto_fps(duration: float, max_frames: int, focused: bool) -> tuple[float, int]:
    """Frame budget by length. A focused range samples denser: the user is zooming in."""
    if duration <= 0:
        return 1.0, 1
    if focused:
        bands = ((5, max(10, round(duration * 6))), (15, max(30, round(duration * 4))),
                 (30, 60), (60, 80))
    else:
        bands = ((30, max(12, round(duration))), (60, 40), (180, 60), (600, 80))
    target = next((n for limit, n in bands if duration <= limit), max_frames)
    target = min(max_frames, target)
    return min(target / duration, MAX_FPS), target


def extract_uniform(video: str, out_dir: Path, fps: float, max_frames: int,
                    start: float, end: float, resolution: int) -> list[dict]:
    rate = min(fps, MAX_FPS, max_frames / (end - start))
    _clear(out_dir, "frame_*.jpg")
    # select keeps the first real frame in each time bucket; the fps filter would shift pixels.
    vf = (f"select='isnan(prev_selected_t)+gt(floor(t*{rate:.17g}),floor(prev_selected_t*{rate:.17g}))',"
          f"{_scale_filter(resolution)},showinfo")
    result = run_text(["ffmpeg", "-hide_banner", "-loglevel", "info", "-y",
                       "-ss", f"{start:.6f}", "-to", f"{end:.6f}", "-i", str(Path(video).resolve()),
                       "-vf", vf, *sync_args(), "-frames:v", str(max_frames), "-q:v", "4",
                       str(out_dir / "frame_%04d.jpg")])
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg frame extraction failed: {diagnostic(result.stderr)}")
    files = sorted(out_dir.glob("frame_*.jpg"))
    if not files:
        raise SystemExit("ffmpeg produced no frames in the requested range")
    return _emitted_frames(files, result.stderr, start, "uniform")


def extract_scene_candidates(video: str, out_dir: Path, start: float, end: float,
                             resolution: int) -> list[dict]:
    """First frame plus every scene change across the whole range (uncapped)."""
    _clear(out_dir, "frame_*.jpg")
    vf = f"select='eq(n\\,0)+gt(scene\\,{SCENE_THRESHOLD})',{_scale_filter(resolution)},showinfo"
    result = run_text(["ffmpeg", "-hide_banner", "-loglevel", "info", "-y",
                       "-ss", f"{start:.6f}", "-to", f"{end:.6f}", "-i", str(Path(video).resolve()),
                       "-vf", vf, *sync_args(), "-q:v", "4", str(out_dir / "frame_%04d.jpg")])
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg scene extraction failed: {diagnostic(result.stderr)}")
    out = _emitted_frames(sorted(out_dir.glob("frame_*.jpg")), result.stderr, start, "scene-change")
    if out:
        out[0]["reason"] = "first-frame"
    return out


def _even_indices(count: int, n: int) -> list[int]:
    """n evenly spaced indices out of count, first and last kept."""
    if n >= count:
        return list(range(count))
    if n <= 1:
        return [0]
    return [round(i * (count - 1) / (n - 1)) for i in range(n)]


def _keep(candidates: list[dict], kept: list[dict]) -> list[dict]:
    """Delete the JPEGs not kept and reindex the survivors."""
    keep_paths = {k["path"] for k in kept}
    for c in candidates:
        if c["path"] not in keep_paths:
            Path(c["path"]).unlink(missing_ok=True)
    for i, f in enumerate(kept):
        f["index"] = i
    return kept


def even_sample(candidates: list[dict], n: int) -> list[dict]:
    return _keep(candidates, [candidates[i] for i in _even_indices(len(candidates), n)])


def _thumbs(paths: list[Path]) -> list[bytes]:
    """16x16 RGB thumbnail per frame in one ffmpeg pass. Empty list on any failure (dedup is skipped)."""
    m = re.match(r"(.*?)(\d+)(\.[A-Za-z0-9]+)$", paths[0].name) if paths else None
    if m is None:
        return []
    prefix, digits, ext = m.groups()
    pattern = str(paths[0].parent / f"{prefix}%0{len(digits)}d{ext}")
    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                                 "-start_number", str(int(digits)), "-i", pattern,
                                 "-vf", f"scale={DEDUP_THUMB}:{DEDUP_THUMB},format=rgb24",
                                 "-f", "rawvideo", "-"], capture_output=True)
    except OSError:
        return []
    chunk = DEDUP_THUMB * DEDUP_THUMB * 3
    if result.returncode != 0 or len(result.stdout) != chunk * len(paths):
        return []
    return [result.stdout[i * chunk:(i + 1) * chunk] for i in range(len(paths))]


def dedupe_by_deltas(candidates: list[dict], thumbs: list[bytes],
                     threshold: float = DEDUP_THRESHOLD) -> tuple[list[dict], int]:
    """Drop frames within threshold of the last kept frame. Unchanged if thumbs don't line up."""
    if len(thumbs) != len(candidates) or len(candidates) <= 1:
        return candidates, 0
    kept, last = [candidates[0]], thumbs[0]
    for cand, thumb in zip(candidates[1:], thumbs[1:]):
        if sum(abs(x - y) for x, y in zip(thumb, last)) / len(thumb) > threshold:
            kept.append(cand)
            last = thumb
    return _keep(candidates, kept), len(candidates) - len(kept)


def dedupe(candidates: list[dict]) -> tuple[list[dict], int]:
    if len(candidates) <= 1:
        return candidates, 0
    return dedupe_by_deltas(candidates, _thumbs([Path(c["path"]) for c in candidates]))


def extract_at_timestamps(video: str, out_dir: Path, times: list[float], max_frames: int,
                          start: float, end: float, resolution: int) -> tuple[list[dict], int]:
    """One frame at each requested time inside the range. Returns (frames, dropped_outside_range)."""
    _clear(out_dir, "cue_*.jpg")
    in_window = [t for t in times if start <= t <= end]
    points = [in_window[i] for i in _even_indices(len(in_window), max_frames)] if in_window else []
    out: list[dict] = []
    for t in points:
        path = out_dir / f"cue_{len(out):04d}.jpg"
        result = run_text(["ffmpeg", "-hide_banner", "-loglevel", "info", "-y",
                           "-ss", f"{t:.6f}", "-i", str(Path(video).resolve()), "-frames:v", "1",
                           "-vf", f"{_scale_filter(resolution)},showinfo",
                           *sync_args(), "-q:v", "4", str(path)])
        if result.returncode != 0:
            raise SystemExit(f"ffmpeg cue extraction failed: {diagnostic(result.stderr)}")
        if path.exists():
            frame = _emitted_frames([path], result.stderr, t, "cue")[0]
            frame["index"] = len(out)
            out.append(frame)
    return out, len(times) - len(in_window)


def select_frames(video: str, out_dir: Path, *, start: float, end: float,
                  focused: bool, max_frames: int, resolution: int, dedup: bool,
                  cue_times: list[float]) -> tuple[list[dict], dict]:
    """Cue frames first (they reserve budget), then scene frames, uniform if the video is static."""
    cues, dropped = (extract_at_timestamps(video, out_dir, cue_times, max_frames, start, end, resolution)
                     if cue_times else ([], 0))
    budget = max_frames - len(cues)
    info = {"engine": "none", "candidates": 0, "deduped": 0, "cues": len(cues),
            "cues_dropped": dropped, "budget": budget}
    frames: list[dict] = []
    if budget > 0:
        scene = extract_scene_candidates(video, out_dir, start, end, resolution)
        if len(scene) >= SCENE_MIN_FRAMES:
            kept, n = dedupe(scene) if dedup else (scene, 0)
            frames = even_sample(kept, budget)
            info.update(engine="scene", candidates=len(scene), deduped=n)
        else:
            fps, target = auto_fps(end - start, budget, focused)
            frames = extract_uniform(video, out_dir, fps, min(budget, target), start, end, resolution)
            info["candidates"] = len(frames)
            if dedup:
                frames, info["deduped"] = dedupe(frames)
            info["engine"] = "uniform"
    merged = sorted([*frames, *cues], key=lambda f: f["timestamp_seconds"])
    for i, f in enumerate(merged):
        f["index"] = i
    return merged, info


# --------------------------------------------------------------------------- #
# Transcript
# --------------------------------------------------------------------------- #
def find_cached(out_dir: Path, source_name: str, model: str) -> Path | None:
    """A cached Scribe JSON for this source and model, so a re-watch never re-charges."""
    if not out_dir.is_dir():
        return None
    for p in sorted(out_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (isinstance(data, dict) and data.get("_source_name") == source_name
                and data.get("_model", transcribe.DEFAULT_MODEL) == model):
            return p
    return None


def transcript_lines(data: dict, start: float | None = None, end: float | None = None) -> list[str]:
    """Short timestamped lines (subtitle-sized) so speech lines up with frame times."""
    names = formats._norm_names(data.get("_speaker_names"))
    runs: list[tuple[str, list[dict]]] = []
    for w in data.get("words", []):
        spk = w.get("speaker_id") or "speaker_0"
        if runs and runs[-1][0] == spk:
            runs[-1][1].append(w)
        else:
            runs.append((spk, [w]))
    multi = len({spk for spk, _ in runs}) > 1
    lines = []
    for spk, words in runs:
        label = f"{formats._label(spk, names)}: " if multi else ""
        for c in formats.segment_cues(words):
            if (start is None or c["end"] >= start) and (end is None or c["start"] <= end):
                lines.append(f"[{formats.fmt_time(c['start'])}] {label}{c['text']}")
    return lines


# --------------------------------------------------------------------------- #
# Command
# --------------------------------------------------------------------------- #
def cmd_watch(args) -> int:
    start_arg, end_arg = parse_time(args.start), parse_time(args.end)
    cue_times = parse_timestamps(args.timestamps)
    if args.max_frames < 1:
        raise SystemExit("--max-frames must be at least 1")
    if args.resolution < 2:
        raise SystemExit("--resolution must be at least 2 pixels")
    if start_arg is not None and end_arg is not None and end_arg <= start_arg:
        raise SystemExit("--end must be after --start")

    config = transcribe.load_config()
    keyterms = transcribe.run_keyterms(args, config)
    if keyterms is None:
        return 1

    info: dict = {}
    if is_url(args.source):
        root = Path(args.output_dir).expanduser() if args.output_dir else DOWNLOAD_ROOT
        media_dir = root / hashlib.sha1(args.source.encode()).hexdigest()[:10]
        video, info = download_url(args.source, media_dir)
        out_dir = media_dir / "transcripts"
    else:
        video = Path(args.source).expanduser().resolve()
        if not video.is_file():
            raise SystemExit(f"File not found: {video}")
        out_dir = Path(args.output_dir).expanduser() if args.output_dir else transcribe.default_out_dir(video)

    meta = get_metadata(str(video))
    duration = meta["duration_seconds"]
    if start_arg is not None and start_arg >= duration:
        raise SystemExit(f"--start {start_arg:.1f}s is past the end of the video ({duration:.1f}s)")
    start, end = start_arg or 0.0, min(end_arg, duration) if end_arg is not None else duration
    focused = start_arg is not None or end_arg is not None
    errors: list[str] = []

    # Transcript: cached JSON if this file was transcribed before, else one Scribe call.
    data, transcript_note = None, "no audio stream"
    if meta["has_audio"]:
        cached = find_cached(out_dir, video.name, args.model)
        try:
            if cached:
                transcript_note = f"cached, no API call ({cached.name})"
            else:
                print("[watch] transcribing with ElevenLabs Scribe…", file=sys.stderr)
                api_key = transcribe.get_api_key(args.api_key, config, transcribe.os.environ)
                res = transcribe.transcribe_file(
                    str(video), api_key=api_key, keyterms=keyterms, language=args.language,
                    diarize=True, out_dir=out_dir, fmts=WATCH_FORMATS,
                    speaker_names=transcribe.parse_speakers(args.speakers) or None, model=args.model)
                cached = Path(res["json"])
                transcript_note = f"new, {transcribe.MODELS[args.model]['label']}"
            data = json.loads(cached.read_text(encoding="utf-8"))
        except (SystemExit, RuntimeError, ValueError, OSError,
                urllib.error.HTTPError, urllib.error.URLError) as e:
            transcript_note = f"failed: {e}"
            errors.append(f"Transcript failed: {e}")

    # Frames into a disposable folder, deleted by the caller once viewed.
    frames, finfo, frames_dir = [], {}, None
    if meta["has_video"]:
        frames_dir = Path(tempfile.mkdtemp(prefix="cs-watch-"))
        try:
            frames, finfo = select_frames(str(video), frames_dir, start=start, end=end,
                                          focused=focused, max_frames=args.max_frames,
                                          resolution=args.resolution, dedup=not args.no_dedup,
                                          cue_times=cue_times)
        except SystemExit as e:
            errors.append(f"Frames failed: {e}")

    lines = transcript_lines(data, start if focused else None, end if focused else None) if data else []
    print(render_report(args.source, video, info, meta, start, end, focused, frames, finfo,
                        frames_dir, data, lines, transcript_note, out_dir, errors, args.resolution))
    return 1 if not frames and not lines else 0


def render_report(source, video, info, meta, start, end, focused, frames, finfo,
                  frames_dir, data, lines, transcript_note, out_dir, errors, resolution) -> str:
    t = formats.fmt_time
    duration = meta["duration_seconds"]
    out = ["# Watch report", "",
           f"- **Source:** {source}",
           f"- **Media:** `{video}`"]
    if info.get("title"):
        out.append(f"- **Title:** {info['title']}" + (f" ({info.get('uploader') or info.get('channel')})"
                                                     if info.get("uploader") or info.get("channel") else ""))
    out.append(f"- **Duration:** {t(duration)} ({duration:.1f}s)")
    if focused:
        out.append(f"- **Focus range:** {t(start)} to {t(end)}")
    if meta.get("width"):
        out.append(f"- **Resolution:** {meta['width']}x{meta['height']} ({meta.get('codec')})")
    if not meta["has_video"]:
        out.append("- **Frames:** none, the file has no video stream")
    elif finfo:
        note = f", near-duplicates dropped {finfo['deduped']}" if finfo.get("deduped") else ""
        cues = f", cue frames {finfo['cues']}" if finfo.get("cues") else ""
        cues += f" (outside the range {finfo['cues_dropped']})" if finfo.get("cues_dropped") else ""
        out.append(f"- **Frames:** {len(frames)} ({finfo['engine']}, {finfo['candidates']} candidates"
                   f"{note}{cues}), max {resolution}px wide")
    speakers = len({w.get("speaker_id") for w in (data or {}).get("words", []) if w.get("speaker_id")})
    lang = (data or {}).get("language_code")
    out.append(f"- **Transcript:** {transcript_note}"
               + (f", {lang}, {speakers} speaker(s), files in `{out_dir}`" if data else ""))
    if not focused and duration > 600:
        out += ["", f"> This is a {int(duration // 60)}-minute video, so frames are sparse. "
                    "Re-run with `--start` and `--end` to zoom into a section."]

    out += ["", "## Frames", ""]
    if frames:
        out += ["Read every frame below with the Read tool. `t=` is the time in the source video.", ""]
        # Tenths of a second, because dense sampling puts several frames in one second.
        out += [f"- `{f['path']}` (t={t(f['timestamp_seconds'])}.{int(f['timestamp_seconds'] * 10) % 10}, "
                f"{f['reason']})" for f in frames]
    else:
        out.append("_No frames extracted._")

    out += ["", "## Transcript", ""]
    if lines:
        out += ["```", *lines, "```"]
    elif data:
        out.append("_No speech in the selected range._")
    else:
        out.append(f"_{transcript_note.capitalize()}._")

    if errors:
        out += ["", "## Missing evidence", "", *[f"- {e}" for e in errors]]
    if frames_dir:
        out += ["", "---", f"_Frames folder: `{frames_dir}` - delete it after viewing._"]
    return "\n".join(out)
