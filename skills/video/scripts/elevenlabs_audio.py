#!/usr/bin/env python3
"""nano-banana-studio -- ElevenLabs audio replacement pipeline (v3.7.1)

Generates continuous TTS narration + Eleven Music background bed, mixes them
with FFmpeg side-chain ducking, and audio-swaps the result into a target video.
This is the v3.7.1 architecture validated empirically in spike 3 of the strategic
reset session — see ROADMAP.md and references/elevenlabs-audio.md for context.

The script's purpose is to solve the multi-clip music-bed seam problem in stitched
VEO sequences: when 4 separately-generated VEO clips are concatenated, each clip's
emergent music intro/outro creates audible seams every clip-duration. By generating
ONE continuous TTS track and ONE continuous music track and replacing the entire
audio bed, the seams disappear by construction.

Architecture:
    1. ElevenLabs TTS: POST /v1/text-to-speech/{voice_id} (eleven_v3 model, audio tags)
    2. Eleven Music: POST /v1/music (music_v1 model, instrumental, length-locked)
    3. FFmpeg mix:    sidechaincompress with apad for full-length ducked output
    4. FFmpeg swap:   -map 0:v -map 1:a -c:v copy lossless audio replacement
    5. Voice Design:  POST /v1/text-to-voice/design + POST /v1/text-to-voice for custom voices

Usage:
    elevenlabs_audio.py status                       Check API key + ffmpeg + voice library
    elevenlabs_audio.py narrate --text "..." [--voice ROLE] [--out PATH]
    elevenlabs_audio.py music --prompt "..." [--length-ms N] [--out PATH]
    elevenlabs_audio.py mix --narration N.mp3 --music M.mp3 --out OUT.mp3
    elevenlabs_audio.py swap --video V.mp4 --audio A.mp3 --out OUT.mp4
    elevenlabs_audio.py pipeline --video V.mp4 --text "..." --music-prompt "..." --out OUT.mp4
    elevenlabs_audio.py voice-design --description "..." [--name NAME] [--enhance]
    elevenlabs_audio.py voice-promote --generated-id ID --name NAME --role ROLE [--description "..."]
    elevenlabs_audio.py voice-list

The pipeline subcommand is the canonical end-to-end command — it takes a silent or
audio-bearing video, a narration script, and a music prompt, then runs all five
stages and writes a final MP4 with the new audio swapped in. The TTS and music API
calls run in parallel (concurrent.futures.ThreadPoolExecutor) to roughly halve the
user-perceived latency from ~19s sequential to ~12s parallel.

Configuration is read from ~/.banana/config.json:
    elevenlabs_api_key:        ElevenLabs API key (xi-api-key header)
    custom_voices:             Nested dict of role -> voice metadata (see schema below)

Custom voice schema (v3.7.1+):
    custom_voices: {
      "narrator": {
        "voice_id":      ElevenLabs permanent voice ID (string)
        "name":          Display name (string)
        "description":   Original design description (string)
        "source_type":   "designed" | "cloned" | "library"
        "design_method": For source_type=designed: "text_to_voice" | "remix"
        "model_id":      Model used to create the voice (eleven_ttv_v3, etc.)
        "guidance_scale":  Voice Design guidance value (0-30, default 5)
        "should_enhance":  Voice Design enhance flag (bool)
        "created_at":    ISO date
        "provider":      "elevenlabs" (forward-compatible for multi-provider future)
        "notes":         Free-form context (pacing observations, A/B history, etc.)
      },
      "character_a": { ... },
      ...
    }

Stdlib only — uses urllib.request for HTTP, concurrent.futures for parallelism,
subprocess for FFmpeg invocation. Zero pip dependencies, matching the plugin's
existing fallback-script pattern.
"""

import argparse
import base64
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".banana" / "config.json"
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "nano-banana-audio"

ELEVENLABS_API = "https://api.elevenlabs.io"

# TTS defaults — eleven_v3 with Natural stability mode (honors audio tags)
DEFAULT_TTS_MODEL = "eleven_v3"
DEFAULT_VOICE_SETTINGS = {
    "stability": 0.5,           # Natural mode (between Creative and Robust)
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}

# Music defaults — music_v1, instrumental only
DEFAULT_MUSIC_MODEL = "music_v1"
DEFAULT_MUSIC_LENGTH_MS = 32000

# Voice Design defaults — eleven_ttv_v3 (v3-native)
DEFAULT_TTV_MODEL = "eleven_ttv_v3"
DEFAULT_GUIDANCE_SCALE = 5

# FFmpeg sidechain compression parameters — empirically tuned in spike 3
SIDECHAIN_FILTER = (
    "[0:a]aformat=channel_layouts=stereo,apad=whole_dur={duration}[narration_padded];"
    "[1:a]volume=0.55[music_quiet];"
    "[music_quiet][narration_padded]sidechaincompress="
    "threshold=0.04:ratio=10:attack=15:release=350[ducked];"
    "[narration_padded][ducked]amix=inputs=2:duration=longest:weights='1.6 1.0'[mixed]"
)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    """Read ~/.banana/config.json. Returns {} if missing."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _error_exit(f"failed to read {CONFIG_PATH}: {e}")
        return {}  # unreachable, satisfies linter


def _atomic_write_config(config: dict) -> None:
    """Write config.json atomically: tempfile in same dir → fsync → rename."""
    config_dir = CONFIG_PATH.parent
    config_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(config_dir), prefix=".config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, 0o600)
        os.rename(tmp_path, CONFIG_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _get_api_key(cli_key: str | None = None) -> str:
    """Resolve API key: CLI flag → env var → config file."""
    if cli_key:
        return cli_key
    env_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if env_key:
        return env_key
    config = _load_config()
    cfg_key = config.get("elevenlabs_api_key")
    if cfg_key:
        return cfg_key
    _error_exit(
        "no ElevenLabs API key found. Set ELEVENLABS_API_KEY env var, "
        "pass --api-key, or add 'elevenlabs_api_key' to ~/.banana/config.json"
    )
    return ""  # unreachable


def _resolve_voice(role_or_id: str | None, config: dict | None = None) -> tuple[str, dict | None]:
    """Resolve a voice reference to (voice_id, metadata).

    Accepts:
      - A semantic role name (e.g. "narrator") → looked up in custom_voices
      - A literal ElevenLabs voice_id (any 20-char alphanumeric)
      - None → defaults to "narrator" role if it exists, else error

    Returns (voice_id, metadata_dict_or_None).
    """
    config = config or _load_config()
    custom = config.get("custom_voices", {}) or {}

    if role_or_id is None:
        # Default to narrator role if it exists
        if "narrator" in custom:
            meta = custom["narrator"]
            return meta["voice_id"], meta
        _error_exit(
            "no voice specified and no 'narrator' role in custom_voices. "
            "Pass --voice ROLE or --voice VOICE_ID, or design one with voice-design subcommand."
        )
        return "", None  # unreachable

    # Check if it's a known role first
    if role_or_id in custom:
        meta = custom[role_or_id]
        return meta["voice_id"], meta

    # Otherwise treat it as a literal voice_id
    return role_or_id, None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_post_json(url: str, body: dict, api_key: str, accept: str = "application/json", timeout: int = 180) -> bytes:
    """POST JSON body, return raw response bytes. Raises on HTTP error."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": accept,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_get_json(url: str, api_key: str, timeout: int = 30) -> dict:
    """GET JSON, return parsed dict. Raises on HTTP error."""
    req = urllib.request.Request(
        url,
        headers={"xi-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_error_message(e: urllib.error.HTTPError) -> str:
    """Extract a useful error message from an HTTPError, including ElevenLabs's
    structured `detail.message` when present and `detail.data.prompt_suggestion`
    when the music API returns a TOS guardrail rejection."""
    body_text = ""
    try:
        body_text = e.read().decode()
    except Exception:
        pass
    msg = f"HTTP {e.code}"
    try:
        body_json = json.loads(body_text)
        detail = body_json.get("detail", {})
        if isinstance(detail, dict):
            if "message" in detail:
                msg += f": {detail['message']}"
            suggestion = detail.get("data", {}).get("prompt_suggestion")
            if suggestion:
                msg += f" (API suggestion: {suggestion[:200]})"
        elif isinstance(detail, str):
            msg += f": {detail}"
    except (json.JSONDecodeError, AttributeError):
        if body_text:
            msg += f": {body_text[:300]}"
    return msg


def _error_exit(message: str, exit_code: int = 1) -> None:
    """Print a structured error JSON to stdout and exit. Plugin convention."""
    print(json.dumps({"error": True, "message": message}))
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Stage 1: TTS narration
# ---------------------------------------------------------------------------


def generate_narration(text: str, voice_id: str, api_key: str, model_id: str = DEFAULT_TTS_MODEL,
                       voice_settings: dict | None = None, output_path: Path | None = None) -> dict:
    """Call ElevenLabs TTS for a continuous narration. Returns a result dict.

    Default model is eleven_v3 with Natural stability — honors audio tags,
    selective capitalization, and ellipses for pacing control.
    """
    settings = voice_settings or DEFAULT_VOICE_SETTINGS
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"narration_{ts}.mp3"

    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": settings,
    }
    url = f"{ELEVENLABS_API}/v1/text-to-speech/{voice_id}"

    t0 = time.time()
    try:
        audio_bytes = _http_post_json(url, body, api_key, accept="audio/mpeg", timeout=180)
    except urllib.error.HTTPError as e:
        _error_exit(f"TTS failed: {_http_error_message(e)}")
    except Exception as e:
        _error_exit(f"TTS failed: {type(e).__name__}: {e}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    return {
        "path": str(output_path),
        "bytes": len(audio_bytes),
        "voice_id": voice_id,
        "model_id": model_id,
        "char_count": len(text),
        "elapsed_seconds": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------
# Stage 2: Music generation
# ---------------------------------------------------------------------------


def generate_music(prompt: str, api_key: str, length_ms: int = DEFAULT_MUSIC_LENGTH_MS,
                   force_instrumental: bool = True, model_id: str = DEFAULT_MUSIC_MODEL,
                   output_path: Path | None = None) -> dict:
    """Call Eleven Music for an instrumental background bed.

    Important: prompts must NOT name copyrighted creators or brands (e.g.
    "Annie Leibovitz", "BBC Earth"). The API blocks these with HTTP 400 and
    a `prompt_suggestion` in the response. Use generic descriptors only.
    Empirical finding from spike 3 v1 — see references/elevenlabs-audio.md.
    """
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"music_{ts}.mp3"

    body = {
        "prompt": prompt,
        "music_length_ms": length_ms,
        "model_id": model_id,
        "force_instrumental": force_instrumental,
    }
    url = f"{ELEVENLABS_API}/v1/music"

    t0 = time.time()
    try:
        audio_bytes = _http_post_json(url, body, api_key, accept="audio/mpeg", timeout=300)
    except urllib.error.HTTPError as e:
        _error_exit(f"music gen failed: {_http_error_message(e)}")
    except Exception as e:
        _error_exit(f"music gen failed: {type(e).__name__}: {e}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    return {
        "path": str(output_path),
        "bytes": len(audio_bytes),
        "model_id": model_id,
        "length_ms": length_ms,
        "force_instrumental": force_instrumental,
        "elapsed_seconds": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------
# Stage 3: FFmpeg mix (narration + music + ducking)
# ---------------------------------------------------------------------------


def _check_ffmpeg() -> str:
    """Return ffmpeg path or exit with error."""
    path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
    if not path:
        _error_exit("ffmpeg not found in PATH. Install via brew install ffmpeg (macOS) or apt install ffmpeg (Linux).")
    return path


def _probe_duration(path: str | Path) -> float:
    """Return media duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def mix_narration_with_music(narration_path: Path, music_path: Path,
                             output_path: Path | None = None,
                             duration: float | None = None) -> dict:
    """Mix narration over music with side-chain ducking (lossy → mp3 192k).

    The narration is padded with silence to match the music length so the
    sidechain trigger lasts the full duration; this prevents the music tail
    from being truncated when narration is shorter than music.
    """
    _check_ffmpeg()

    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"mix_{ts}.mp3"

    # Determine target duration: explicit param, music length, or narration length
    if duration is None:
        music_dur = _probe_duration(music_path)
        narr_dur = _probe_duration(narration_path)
        duration = max(music_dur, narr_dur)
    duration = max(duration, 1.0)

    filter_graph = SIDECHAIN_FILTER.format(duration=duration)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(narration_path),
        "-i", str(music_path),
        "-filter_complex", filter_graph,
        "-map", "[mixed]",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        str(output_path),
    ]

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _error_exit(f"ffmpeg mix failed: {result.stderr[-500:]}")

    return {
        "path": str(output_path),
        "bytes": output_path.stat().st_size,
        "duration_seconds": duration,
        "elapsed_seconds": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------
# Stage 4: FFmpeg audio-swap into video
# ---------------------------------------------------------------------------


def swap_audio_into_video(video_path: Path, audio_path: Path,
                          output_path: Path | None = None) -> dict:
    """Replace a video's audio track with the given audio file.

    Stream-copies the video (lossless, fast) and re-encodes audio to AAC for
    MP4 container compatibility. Uses -shortest to handle minor duration
    mismatches between video and audio (typically <100ms / 1 frame).
    """
    _check_ffmpeg()

    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"swapped_{ts}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _error_exit(f"ffmpeg audio-swap failed: {result.stderr[-500:]}")

    return {
        "path": str(output_path),
        "bytes": output_path.stat().st_size,
        "duration_seconds": _probe_duration(output_path),
        "elapsed_seconds": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------
# End-to-end pipeline (parallel TTS + music)
# ---------------------------------------------------------------------------


def pipeline(video_path: Path, narration_text: str, music_prompt: str,
             voice_id: str, api_key: str,
             output_path: Path | None = None,
             music_length_ms: int | None = None,
             tts_model: str = DEFAULT_TTS_MODEL,
             voice_settings: dict | None = None) -> dict:
    """Full v3.7.1 audio replacement: TTS + music in parallel, mix, swap.

    Returns a structured result with paths and timing for each stage. The TTS
    and music API calls run concurrently via ThreadPoolExecutor — they are
    independent so parallelization roughly halves the user-perceived latency
    (sequential is ~19s, parallel is ~12s).
    """
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"pipeline_{ts}.mp4"

    # Compute target music length from video duration if not specified
    if music_length_ms is None:
        video_duration = _probe_duration(video_path)
        music_length_ms = max(int(video_duration * 1000), 3000)

    # Stage A: parallel TTS + music generation
    pipeline_t0 = time.time()
    print(json.dumps({"status": "stage_a", "step": "parallel_api_calls",
                      "tts_chars": len(narration_text),
                      "music_length_ms": music_length_ms}), file=sys.stderr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        narr_future = executor.submit(
            generate_narration,
            text=narration_text,
            voice_id=voice_id,
            api_key=api_key,
            model_id=tts_model,
            voice_settings=voice_settings,
        )
        music_future = executor.submit(
            generate_music,
            prompt=music_prompt,
            api_key=api_key,
            length_ms=music_length_ms,
        )
        narr_result = narr_future.result()
        music_result = music_future.result()

    # Stage B: mix narration over music with ducking
    print(json.dumps({"status": "stage_b", "step": "ffmpeg_mix"}), file=sys.stderr)
    mix_result = mix_narration_with_music(
        narration_path=Path(narr_result["path"]),
        music_path=Path(music_result["path"]),
        duration=music_length_ms / 1000.0,
    )

    # Stage C: audio-swap into video
    print(json.dumps({"status": "stage_c", "step": "audio_swap"}), file=sys.stderr)
    swap_result = swap_audio_into_video(
        video_path=video_path,
        audio_path=Path(mix_result["path"]),
        output_path=output_path,
    )

    return {
        "final_path": str(output_path),
        "stages": {
            "narration": narr_result,
            "music": music_result,
            "mix": mix_result,
            "swap": swap_result,
        },
        "total_elapsed_seconds": round(time.time() - pipeline_t0, 2),
    }


# ---------------------------------------------------------------------------
# Voice Design (text-to-voice)
# ---------------------------------------------------------------------------


def design_voice(description: str, api_key: str, sample_text: str | None = None,
                 model_id: str = DEFAULT_TTV_MODEL,
                 guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
                 should_enhance: bool = False) -> dict:
    """Call /v1/text-to-voice/design to generate 3 candidate voice previews.

    Returns a dict with the previews list (each containing generated_voice_id
    and a saved-to-disk MP3 path). The user listens to the previews and picks
    one to promote via voice-promote.
    """
    if sample_text is None:
        sample_text = (
            "The seasons change across this valley, painting the forest in red and gold. "
            "The river runs cold here, fed by mountain springs that have flowed for ten thousand years. "
            "Soon the forest sleeps, conserving its strength as winter slowly settles into the hollows."
        )

    body = {
        "voice_description": description,
        "model_id": model_id,
        "text": sample_text,
        "auto_generate_text": False,
        "loudness": 0.5,
        "guidance_scale": guidance_scale,
        "should_enhance": should_enhance,
    }
    url = f"{ELEVENLABS_API}/v1/text-to-voice/design"

    try:
        raw = _http_post_json(url, body, api_key, accept="application/json", timeout=240)
        data = json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        _error_exit(f"voice design failed: {_http_error_message(e)}")
    except Exception as e:
        _error_exit(f"voice design failed: {type(e).__name__}: {e}")

    previews = data.get("previews") or data.get("voice_previews") or []
    if not previews:
        _error_exit(f"voice design returned no previews. Response keys: {list(data.keys())}")

    # Save each preview to disk
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    voice_dir = DEFAULT_OUTPUT_DIR / "voice-design" / time.strftime("%Y%m%d_%H%M%S")
    voice_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for i, p in enumerate(previews, start=1):
        gvid = p.get("generated_voice_id")
        audio_b64 = p.get("audio_base_64") or p.get("audio_base64") or p.get("audio")
        if not gvid or not audio_b64:
            continue
        audio_bytes = base64.b64decode(audio_b64)
        out = voice_dir / f"preview-{i}-{gvid[:12]}.mp3"
        with open(out, "wb") as f:
            f.write(audio_bytes)
        saved.append({
            "index": i,
            "generated_voice_id": gvid,
            "path": str(out),
            "bytes": len(audio_bytes),
        })

    # Save metadata file alongside the previews for later promote-step
    meta = {
        "voice_description": description,
        "sample_text": sample_text,
        "model_id": model_id,
        "guidance_scale": guidance_scale,
        "should_enhance": should_enhance,
        "previews": saved,
    }
    meta_path = voice_dir / "previews-metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return {
        "voice_dir": str(voice_dir),
        "metadata_path": str(meta_path),
        "previews": saved,
        "voice_description": description,
    }


def promote_voice(generated_voice_id: str, name: str, role: str, api_key: str,
                  description: str | None = None,
                  source_type: str = "designed",
                  design_method: str = "text_to_voice",
                  model_id: str = DEFAULT_TTV_MODEL,
                  guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
                  should_enhance: bool = False,
                  notes: str | None = None) -> dict:
    """POST /v1/text-to-voice to promote a preview to a permanent voice,
    then save the metadata to ~/.banana/config.json under custom_voices.{role}.
    """
    if description is None:
        description = name

    # Step 1: promote via API
    body = {
        "voice_name": name,
        "voice_description": description,
        "generated_voice_id": generated_voice_id,
    }
    url = f"{ELEVENLABS_API}/v1/text-to-voice"
    try:
        raw = _http_post_json(url, body, api_key, accept="application/json", timeout=60)
        data = json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        _error_exit(f"voice promote failed: {_http_error_message(e)}")
    except Exception as e:
        _error_exit(f"voice promote failed: {type(e).__name__}: {e}")

    permanent_voice_id = data.get("voice_id")
    if not permanent_voice_id:
        _error_exit(f"promote response missing voice_id. Response keys: {list(data.keys())}")

    # Step 2: save to config under custom_voices.{role}
    config = _load_config()
    custom = config.get("custom_voices", {}) or {}
    custom[role] = {
        "voice_id": permanent_voice_id,
        "name": name,
        "description": description,
        "source_type": source_type,
        "design_method": design_method,
        "model_id": model_id,
        "guidance_scale": guidance_scale,
        "should_enhance": should_enhance,
        "created_at": date.today().isoformat(),
        "provider": "elevenlabs",
        "notes": notes or "",
    }
    config["custom_voices"] = custom
    _atomic_write_config(config)

    return {
        "permanent_voice_id": permanent_voice_id,
        "role": role,
        "name": name,
        "config_path": str(CONFIG_PATH),
    }


def list_voices() -> dict:
    """List all custom voices from ~/.banana/config.json."""
    config = _load_config()
    custom = config.get("custom_voices", {}) or {}
    return {
        "config_path": str(CONFIG_PATH),
        "voice_count": len(custom),
        "voices": custom,
    }


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------


def status() -> dict:
    """Verify ElevenLabs API key, ffmpeg, and custom voice library."""
    result: dict = {"checks": []}

    # API key
    config = _load_config()
    has_key = bool(config.get("elevenlabs_api_key")) or bool(os.environ.get("ELEVENLABS_API_KEY"))
    result["checks"].append({"name": "elevenlabs_api_key", "ok": has_key})

    # API auth
    if has_key:
        try:
            api_key = _get_api_key()
            data = _http_get_json(f"{ELEVENLABS_API}/v1/user", api_key, timeout=15)
            sub = data.get("subscription", {})
            result["checks"].append({
                "name": "elevenlabs_auth",
                "ok": True,
                "tier": sub.get("tier", "unknown"),
                "character_limit": sub.get("character_limit"),
                "character_count": sub.get("character_count"),
            })
        except Exception as e:
            result["checks"].append({"name": "elevenlabs_auth", "ok": False, "error": str(e)})

    # ffmpeg
    ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
    result["checks"].append({"name": "ffmpeg", "ok": bool(ffmpeg_path), "path": ffmpeg_path})

    # ffprobe
    ffprobe_path = subprocess.run(["which", "ffprobe"], capture_output=True, text=True).stdout.strip()
    result["checks"].append({"name": "ffprobe", "ok": bool(ffprobe_path), "path": ffprobe_path})

    # Custom voices
    custom = config.get("custom_voices", {}) or {}
    result["checks"].append({
        "name": "custom_voices",
        "count": len(custom),
        "roles": sorted(custom.keys()),
    })

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ElevenLabs audio replacement pipeline for nano-banana-studio v3.7.1+",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # status
    sub.add_parser("status", help="Check API key, ffmpeg, and custom voice library")

    # narrate
    p_narr = sub.add_parser("narrate", help="Generate TTS narration from text")
    p_narr.add_argument("--text", required=True)
    p_narr.add_argument("--voice", help="Voice role name or literal voice_id (defaults to narrator role)")
    p_narr.add_argument("--model", default=DEFAULT_TTS_MODEL)
    p_narr.add_argument("--out", help="Output mp3 path (default: ~/Documents/nano-banana-audio/narration_TS.mp3)")
    p_narr.add_argument("--api-key")

    # music
    p_music = sub.add_parser("music", help="Generate Eleven Music background bed")
    p_music.add_argument("--prompt", required=True)
    p_music.add_argument("--length-ms", type=int, default=DEFAULT_MUSIC_LENGTH_MS)
    p_music.add_argument("--with-vocals", action="store_true",
                         help="Allow vocals (default is force_instrumental=True)")
    p_music.add_argument("--out")
    p_music.add_argument("--api-key")

    # mix
    p_mix = sub.add_parser("mix", help="FFmpeg mix narration + music with side-chain ducking")
    p_mix.add_argument("--narration", required=True)
    p_mix.add_argument("--music", required=True)
    p_mix.add_argument("--out")
    p_mix.add_argument("--duration", type=float,
                       help="Target output duration in seconds (defaults to longer of inputs)")

    # swap
    p_swap = sub.add_parser("swap", help="Audio-swap an audio track into a video")
    p_swap.add_argument("--video", required=True)
    p_swap.add_argument("--audio", required=True)
    p_swap.add_argument("--out")

    # pipeline (the canonical end-to-end command)
    p_pipe = sub.add_parser("pipeline", help="End-to-end: parallel TTS + music, mix, swap into video")
    p_pipe.add_argument("--video", required=True, help="Source video file (audio will be replaced)")
    p_pipe.add_argument("--text", required=True, help="Narration text (with audio tags, ellipses, CAPS as desired)")
    p_pipe.add_argument("--music-prompt", required=True,
                        help="Music description (no named creators/brands — they trigger TOS guardrail)")
    p_pipe.add_argument("--voice", help="Voice role or voice_id (default: narrator)")
    p_pipe.add_argument("--music-length-ms", type=int,
                        help="Music length in ms (default: matches video duration)")
    p_pipe.add_argument("--out", help="Final output mp4 path")
    p_pipe.add_argument("--tts-model", default=DEFAULT_TTS_MODEL)
    p_pipe.add_argument("--api-key")

    # voice-design
    p_vd = sub.add_parser("voice-design", help="Generate voice previews from a text description")
    p_vd.add_argument("--description", required=True, help="Voice description (20-1000 chars)")
    p_vd.add_argument("--sample-text", help="Sample text for the previews to speak")
    p_vd.add_argument("--model", default=DEFAULT_TTV_MODEL,
                      choices=["eleven_ttv_v3", "eleven_multilingual_ttv_v2"])
    p_vd.add_argument("--guidance-scale", type=float, default=DEFAULT_GUIDANCE_SCALE)
    p_vd.add_argument("--enhance", action="store_true", help="AI-expand the description")
    p_vd.add_argument("--api-key")

    # voice-promote
    p_vp = sub.add_parser("voice-promote", help="Promote a preview to a permanent saved voice")
    p_vp.add_argument("--generated-id", required=True, help="generated_voice_id from voice-design output")
    p_vp.add_argument("--name", required=True, help="Display name for the saved voice")
    p_vp.add_argument("--role", required=True,
                      help="Semantic role (e.g. narrator, character_a, brand_voice)")
    p_vp.add_argument("--description", help="Voice description (defaults to name)")
    p_vp.add_argument("--source-type", default="designed", choices=["designed", "cloned", "library"])
    p_vp.add_argument("--design-method", default="text_to_voice", choices=["text_to_voice", "remix"])
    p_vp.add_argument("--model", default=DEFAULT_TTV_MODEL)
    p_vp.add_argument("--guidance-scale", type=float, default=DEFAULT_GUIDANCE_SCALE)
    p_vp.add_argument("--should-enhance", action="store_true")
    p_vp.add_argument("--notes", help="Free-form context (pacing, A/B history, etc.)")
    p_vp.add_argument("--api-key")

    # voice-list
    sub.add_parser("voice-list", help="List custom voices saved in ~/.banana/config.json")

    args = parser.parse_args()

    # Dispatch
    if args.cmd == "status":
        result = status()
    elif args.cmd == "narrate":
        api_key = _get_api_key(args.api_key)
        voice_id, _ = _resolve_voice(args.voice)
        result = generate_narration(
            text=args.text,
            voice_id=voice_id,
            api_key=api_key,
            model_id=args.model,
            output_path=Path(args.out) if args.out else None,
        )
    elif args.cmd == "music":
        api_key = _get_api_key(args.api_key)
        result = generate_music(
            prompt=args.prompt,
            api_key=api_key,
            length_ms=args.length_ms,
            force_instrumental=not args.with_vocals,
            output_path=Path(args.out) if args.out else None,
        )
    elif args.cmd == "mix":
        result = mix_narration_with_music(
            narration_path=Path(args.narration),
            music_path=Path(args.music),
            output_path=Path(args.out) if args.out else None,
            duration=args.duration,
        )
    elif args.cmd == "swap":
        result = swap_audio_into_video(
            video_path=Path(args.video),
            audio_path=Path(args.audio),
            output_path=Path(args.out) if args.out else None,
        )
    elif args.cmd == "pipeline":
        api_key = _get_api_key(args.api_key)
        voice_id, _ = _resolve_voice(args.voice)
        result = pipeline(
            video_path=Path(args.video),
            narration_text=args.text,
            music_prompt=args.music_prompt,
            voice_id=voice_id,
            api_key=api_key,
            output_path=Path(args.out) if args.out else None,
            music_length_ms=args.music_length_ms,
            tts_model=args.tts_model,
        )
    elif args.cmd == "voice-design":
        api_key = _get_api_key(args.api_key)
        result = design_voice(
            description=args.description,
            api_key=api_key,
            sample_text=args.sample_text,
            model_id=args.model,
            guidance_scale=args.guidance_scale,
            should_enhance=args.enhance,
        )
    elif args.cmd == "voice-promote":
        api_key = _get_api_key(args.api_key)
        result = promote_voice(
            generated_voice_id=args.generated_id,
            name=args.name,
            role=args.role,
            api_key=api_key,
            description=args.description,
            source_type=args.source_type,
            design_method=args.design_method,
            model_id=args.model,
            guidance_scale=args.guidance_scale,
            should_enhance=args.should_enhance,
            notes=args.notes,
        )
    elif args.cmd == "voice-list":
        result = list_voices()
    else:
        parser.print_help()
        sys.exit(2)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
