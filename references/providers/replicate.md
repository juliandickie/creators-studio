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

`providers.replicate.pricing.mode` in the registry is one of:

- `per_second` — Kling ($0.02/s), Fabric ($0.15/s), DreamActor ($0.05/s)
- `per_call` — Recraft Vectorize ($0.01 flat)
- `by_resolution` — keyed by 512/1K/2K/4K

`/v1/predictions/{id}` responses include `metrics.predict_time` and `metrics.video_output_duration_seconds` but NO `metrics.cost_usd` — the plugin computes cost client-side from pricing mode + output duration.

## Known quirks

- **Kling `aspect_ratio` is ignored when `start_image` is provided.** Output uses start image's native aspect. Backend logs a WARNING but does not raise.
- **Multi-prompt sum must equal top-level duration.** `sum(shot.duration for shot in multi_prompt) == duration`.
- **Fabric pricing is on output duration, not wall time.** A cold start (~36s) does not increase cost.
- **Seedance rejects any human subject** with error `E005`. Seedance is NOT registered in the plugin as a default.

## Diagnose command

```
python3 -m scripts.backends._replicate diagnose
```

Pings `/v1/account` with the configured API key. Reports auth status without burning generation budget.

## Authoritative sources

- `dev-docs/replicate-openapi.json` — OpenAPI spec
- `dev-docs/replicate-mcp.md` — MCP server install guide
- `dev-docs/Replicate official AI models collection.md` — model catalog
