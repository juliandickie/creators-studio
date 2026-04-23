# Replicate provider reference

**Purpose:** How the plugin talks to `api.replicate.com`. Auth, polling, error handling, Cloudflare quirks, and pricing model. Model-specific prompt engineering and capabilities live under `references/models/<model>.md`, not here.

**Source file:** `scripts/backends/_replicate.py` (class `ReplicateBackend`)

## Authentication

- HTTP Bearer token: `Authorization: Bearer r8_...`
- Stored at `~/.banana/config.json` under `providers.replicate.api_key`
- Migration shim reads the legacy flat key `replicate_api_token` for existing configs
- Get a key at <https://replicate.com/account/api-tokens>

## Endpoints

| Purpose | Method | URL |
|---|---|---|
| Auth check | GET | `https://api.replicate.com/v1/account` |
| Submit prediction | POST | `https://api.replicate.com/v1/models/{owner}/{name}/predictions` |
| Poll prediction | GET | `https://api.replicate.com/v1/predictions/{id}` |
| Cancel prediction | POST | `https://api.replicate.com/v1/predictions/{id}/cancel` |

## Status enum mapping

Replicate's `Prediction.status` has **6 values**; canonical enum has 5. Map:

| Replicate | Canonical |
|---|---|
| `starting` | `running` |
| `processing` | `running` |
| `succeeded` | `succeeded` |
| `failed` | `failed` |
| `canceled` | `canceled` |
| `aborted` | `failed` |

`aborted` is terminated before `predict()` is called (queue eviction, deadline exceeded). Treat as terminal failure — do not retry.

## Cloudflare / User-Agent rule

`api.replicate.com/v1/account` returns **HTTP 403 Cloudflare error 1010** on requests with the default Python urllib User-Agent. The backend sends on every request:

```
User-Agent: creators-studio/<version> (+https://github.com/juliandickie/creators-studio)
```

Applies to submit, poll, download, and auth check.

## Sync vs async submit

Replicate documents a `Prefer: wait=N` header for synchronous inline completion (N in [1, 60]). The plugin **omits** `Prefer` entirely for async-first semantics — Kling wall times are 3-6 minutes and polling is the canonical path. Do not use `Prefer: wait=0`; it's non-spec-compliant (regex is `^wait(=([1-9]|[1-9][0-9]|60))?$`).

## Pricing modes (for `cost_tracker.py`)

As of v4.2.1, the registry supports six pricing modes:

- `per_second` — Fabric ($0.15/s), DreamActor ($0.05/s). Flat rate per output second.
- `per_call` — Recraft Vectorize ($0.01 flat), Lyria 2 ($0.06), Lyria 3 ($0.04), Lyria 3 Pro ($0.08). Flat fee per generation call.
- `by_resolution` — Gemini image-gen keyed by 512/1K/2K/4K.
- `per_second_by_resolution` (v4.2.1) — VEO 3.1 Lite: $0.05/s at 720p, $0.08/s at 1080p.
- `per_second_by_audio` (v4.2.1) — VEO 3.1 Fast ($0.15 w/ audio, $0.10 w/o); VEO 3.1 Standard ($0.40 / $0.20).
- `per_second_by_resolution_and_audio` (v4.2.1) — Kling v3 + v3 Omni, two-dimensional rates. See `references/models/kling-v3.md`.
- `subscription` (v4.2.1) — ElevenLabs Music (billed against ElevenLabs subscription, logged at $0 per-call in the ledger).

**Kling v3 pricing correction (v4.2.1):** the v4.2.0 registry seeded Kling at `per_second: $0.02/s` — this was carried forward from an outdated source and was wrong. At the verified rates, Kling v3 pro-audio is $0.336/s (1080p, with audio). See the Kling cost comparison in `references/models/veo-3.1.md`.

`/v1/predictions/{id}` responses include `metrics.predict_time` and `metrics.video_output_duration_seconds` but NO `metrics.cost_usd` — the plugin computes cost client-side from pricing mode + output duration.

## Hosted models (v4.2.1 inventory)

- **Kling v3** (`kwaivgi/kling-v3-video`) — default video model; v3.8.0 spike 5 winner on quality
- **Kling v3 Omni** (`kwaivgi/kling-v3-omni-video`) — multimodal variant, slightly cheaper on audio than v3 Video
- **Fabric 1.0** (`veed/fabric-1.0`) — audio-driven talking-head lip-sync
- **DreamActor M2.0** (`bytedance/dreamactor-m2.0`) — motion transfer from video to image subject
- **Recraft Vectorize** (`recraft-ai/recraft-vectorize`) — raster to SVG
- **Nano Banana 2** (`google/nano-banana-2`) — fallback for image generation (Gemini direct is primary)
- **VEO 3.1 Lite / Fast / Standard** (`google/veo-3.1-lite/fast/`) — v4.2.1 Vertex retirement target, opt-in video backup
- **Lyria 2 / 3 / 3 Pro** (`google/lyria-2/3/3-pro`) — v4.2.1 music generation, used when `--music-source lyria`

## Known quirks

- **Kling `aspect_ratio` is ignored when `start_image` is provided.** Output uses start image's native aspect. Backend logs a WARNING but does not raise.
- **Multi-prompt sum must equal top-level duration.** `sum(shot.duration for shot in multi_prompt) == duration`.
- **Fabric pricing is on output duration, not wall time.** A cold start (~36s) does not increase cost.
- **Seedance rejects any human subject** with error `E005`. Seedance is NOT registered in the plugin as a default.
- **VEO 3.1 Lite: 1080p requires duration=8s** (conditional constraint; Replicate rejects server-side if violated).
- **Lyria 3 / 3 Pro drop `negative_prompt` silently** — only Lyria 2 supports it. `ReplicateBackend._filter_unsupported_params()` logs a WARN and removes the field before submit.

## Diagnose command

```
python3 -m scripts.backends._replicate diagnose
```

Pings `/v1/account` with the configured API key. Reports auth status without burning generation budget.

## Authoritative sources

- `dev-docs/replicate-openapi.json` — OpenAPI spec
- `dev-docs/replicate-mcp.md` — MCP server install guide
- `dev-docs/Replicate official AI models collection.md` — model catalog
