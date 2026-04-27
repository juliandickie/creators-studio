# CLAUDE.md -- Development context for creators-studio

This file is read by Claude Code when working inside this repository.

**Start every session by reading `PROGRESS.md`** -- it has full development
history, design decisions, and next steps.

## Third-party API reference (workspace-level)

Full LLMS documentation for integrated and evaluated third-party APIs lives at
`../dev-docs/` (workspace root, one level above this repo). **Always check
`../CLAUDE.md`'s dev-docs inventory BEFORE** updating prompt-engineering
references, answering model-capability questions, or planning an empirical
spike — the authoritative answer is often already pinned locally.

Specifically:
- **`../dev-docs/nano-banana-image-generation.md`** is the official Google
  Gemini 3.1 Flash Image prompting guide. Consult it before editing
  `skills/create-image/references/prompt-engineering.md` or making any claim about
  Gemini 3.1 behaviour. Spike 6 in v3.7.3 would have been unnecessary if this
  file had been read first — the "describe the scene, don't list keywords"
  rule was already in the official guide.
- **`../dev-docs/google-nano-banana-2-llms.md`** is the Replicate model card
  confirming the Replicate `google/nano-banana-2` is the same
  `gemini-3.1-flash-image-preview` model as the direct Gemini API path.
- **`../dev-docs/elevenlabs-best-practices.md`** is the condensed ElevenLabs
  prompt-engineering guide — consult before tuning narration tags or voice
  design prompts.

Other files in `dev-docs/` cover ElevenLabs (full API), Google ADK (reference
only — not adopted), Replicate (OpenAPI schema + MCP server install guide),
and ByteDance Seedance 2.0 (v3.8.0 bake-off candidate). Most are large — query
via Explore subagent, not Read. **The full inventory and when-to-consult table
is the single source of truth in `../CLAUDE.md`** — do not duplicate it here.

## What this repo is

`creators-studio` is a Claude Code **plugin** that enables AI image generation
using Google's Gemini Nano Banana models via MCP. Claude acts as a Creative
Director: it interprets intent, selects domain expertise, constructs
optimized prompts, and orchestrates Gemini API calls.

## Plugin structure

This repo follows the official Claude Code plugin layout:
- `.claude-plugin/plugin.json` -- Plugin manifest
- `.claude-plugin/marketplace.json` -- Marketplace catalog for distribution
- `skills/create-image/` -- The main skill (SKILL.md + references + scripts)
- `agents/` -- Subagents (brief-constructor)

## Model status (as of March 2026)

- `gemini-3.1-flash-image-preview` -- **Active default.** Nano Banana 2.
- `gemini-2.5-flash-image` -- **Active.** Nano Banana original. Budget/free tier.
- `gemini-3-pro-image-preview` -- **DEAD.** Shut down March 9, 2026. Do not use.

## How to test changes

1. Test as plugin: `claude --plugin-dir .`
2. Or install from GitHub via the marketplace: `claude plugin marketplace add juliandickie/creators-studio` then `claude plugin install creators-studio@creators-studio-marketplace`
3. Test basic generation: `/create-image generate "a red apple on a white table"`
4. Test domain routing: `/create-image generate "product shot for headphones"`
5. Test editing: `/create-image edit [path] "make the background blurry"`
6. Verify output image files exist at the logged path
7. Check cost log if cost_tracker.py is active

## Publishing changes

**Direct pushes to `main` are blocked by the Claude Code harness's default safety rail.** Every change to this repo lands via Pull Request, even when authored by the maintainer. The flow is:

1. Make edits in your working tree (don't pre-create a branch — the script does it).
2. Run `scripts/dev/publish.sh "docs: short title"` — see the script header for full options.
3. The script: derives a kebab-case branch name (`docs/short-title`), creates the branch, stages tracked files only (no `git add -A`), commits with the Co-Authored-By trailer, pushes, opens a `gh` PR, and prints the PR URL.
4. Review on GitHub and merge (squash recommended for single-commit PRs).
5. Locally: `git checkout main && git pull origin main && git branch -D <feature-branch>` to clean up.

**Two scripts exist** (both in `scripts/dev/`, both stdlib bash, no extra deps beyond `git`/`gh`/`jq`/`zip`):

| Script | When to use |
|---|---|
| `scripts/dev/publish.sh "<title>" [body]` | Any docs/infra/feature change that doesn't bump the version. The everyday "land my edits" command. |
| `scripts/dev/release-zip.sh <version> [notes]` | After a version-bump commit has merged to main: builds the distribution zip and creates a GitHub Release with it attached. Refuses to run if the version doesn't match `plugin.json` or if the CHANGELOG section is missing. |

**Branch hygiene:** delete merged feature branches promptly. Single-commit PRs that go through squash-merge can be deleted immediately (no history is lost — the squashed commit is identical to the branch's commit). Multi-commit feature branches: wait 24-72 hours after merge so the granular sub-commits remain inspectable in case of post-merge regression. The `commit-commands:clean_gone` skill cleans up any branch whose remote tracking branch has been deleted (`[gone]` status in `git branch -vv`).

## File responsibilities

| File | Purpose |
|---|---|
| `skills/create-image/SKILL.md` | Main orchestrator. Edit to change Claude's behavior. |
| `skills/create-image/references/gemini-models.md` | Model roster, routing table, resolution tables, input limits. Update when Google releases new models. |
| `skills/create-image/references/prompt-engineering.md` | The prompt construction system: 5-component formula, 11 domain modes, PEEL strategy, brand guide integration. Update when Google publishes new guidance. |
| `skills/create-image/references/mcp-tools.md` | MCP tool parameter reference. Update when Google changes the API. |
| `skills/create-image/references/replicate.md` | Replicate backend API reference (`google/nano-banana-2`). |
| `skills/create-image/references/presets.md` | Brand Style Guide schema (17 fields, 8 optional for brand guides). |
| `skills/create-image/references/social-platforms.md` | **v4.1.2+** 87 image placement specs across 16 platforms (restored Pinterest/Threads/Snapchat/Google Ads/Spotify + added Telegram/Signal/WhatsApp/ManyChat/BlueSky). Max-quality upload dimensions. Loaded by `/create-image social`. |
| `skills/create-video/references/social-platforms.md` | **v4.1.2+ (NEW)** 37 video placement specs across 14 platforms with `duration_min_s` and `duration_max_s` per placement. Data-only reference in v4.1.2; consumed by `/create-video social` (planned v4.2.0). BlueSky specs best-guess; Signal and ManyChat have no native video. |
| `skills/create-image/references/brand-builder.md` | Brand guide creation flow (learn → refine → preview → save). Loaded by `/create-image brand`. |
| `skills/create-image/scripts/social.py` | Social media batch generation (generate, list, info). Groups by ratio to avoid duplicate API calls. |
| `skills/create-image/references/setup.md` | Setup, install, update, status, sharing guide. Loaded on demand by `/create-image setup/status/update`. |
| `skills/create-image/presets/*.json` | 12 example brand guide presets. Copy to `~/.banana/presets/` to use. |
| `skills/create-image/scripts/slides.py` | Slide deck batch generation (generate, estimate, template subcommands). |
| `skills/create-image/scripts/generate.py` | Direct Gemini API fallback for generation. Uses urllib.request (stdlib). |
| `skills/create-image/scripts/edit.py` | Direct Gemini API fallback for editing. Uses urllib.request (stdlib). |
| `skills/create-image/scripts/replicate_generate.py` | Replicate API fallback for generation. Uses urllib.request (stdlib). |
| `skills/create-image/scripts/replicate_edit.py` | Replicate API fallback for editing. Uses urllib.request (stdlib). |
| `skills/create-image/references/asset-registry.md` | How to detect, load, and use persistent assets in generation. |
| `skills/create-image/references/reverse-prompt.md` | Image → 5-Component Formula prompt extraction methodology. |
| `skills/create-image/references/brand-book.md` | Brand book generator guide (tiers, formats, color specs). |
| `skills/create-image/scripts/brandbook.py` | Brand book generator (markdown + pptx + html output). |
| `skills/create-image/scripts/pantone_lookup.py` | Color conversion: Hex → RGB → CMYK → nearest Pantone (156 colors). |
| `skills/create-image/scripts/assets.py` | Asset registry CRUD (list, show, create, delete, add-image). |
| `skills/create-image/scripts/presets.py` | Brand Style Guide CRUD (list, show, create, delete). |
| `skills/create-image/scripts/content_pipeline.py` | Multi-modal content pipeline orchestrator. |
| `skills/create-image/references/content-pipeline.md` | Content pipeline output types, dependencies, cost estimation. |
| `skills/create-image/scripts/analytics.py` | Analytics dashboard (HTML with SVG charts, cost/usage/quota). |
| `skills/create-image/references/analytics.md` | Analytics dashboard sections, data sources, chart types. |
| `skills/create-image/scripts/deckbuilder.py` | Slide deck builder (.pptx with brand styling, 3 layouts). |
| `skills/create-image/references/deck-builder.md` | Deck assembly, layouts, preset integration, logo handling. |
| `skills/create-image/scripts/abtester.py` | A/B prompt variation tester with preference tracking. |
| `skills/create-image/references/ab-testing.md` | A/B variation styles, rating system, preferences. |
| `skills/create-image/scripts/history.py` | Session generation history (log, list, show, export, sessions). |
| `skills/create-image/references/session-history.md` | Session history tracking, gallery export, session ID management. |
| `skills/create-image/scripts/multiformat.py` | Multi-format image converter (PNG/WebP/JPEG at 4K/2K/1K/512). |
| `skills/create-image/references/multi-format.md` | Multi-format conversion guide (sizes, formats, prerequisites). |
| `skills/create-image/scripts/batch.py` | CSV batch workflow parser with cost estimates. |
| `skills/create-image/scripts/vectorize.py` | **v4.1.0** Raster → SVG vectorization via Recraft Vectorize on Replicate ($0.01/call). Cross-skill imports `_replicate_backend.py` from `skills/create-video/scripts/`. Pre-flight size validation, poll loop, SVG download. |
| `skills/create-image/references/vectorize.md` | **v4.1.0** Reference for `/create-image vectorize`: canonical workflow, best-practice vectorization prompts, model constraints (5 MB / 16 MP / 256-4096 px), cost model, troubleshooting. Authoritative source: `dev-docs/recraft-ai-recraft-vectorize-llms.md`. |
| `skills/create-image/scripts/cost_tracker.py` | Cost logging and summaries (log, summary, today, estimate). |
| `skills/create-image/scripts/setup_mcp.py` | MCP + Replicate key configuration. Stores keys in ~/.banana/config.json. |
| `skills/create-image/scripts/validate_setup.py` | Installation and setup verification checks. |
| `skills/create-image/references/cost-tracking.md` | Pricing table, free tier limits, usage tracking guide. |
| `skills/create-image/references/post-processing.md` | ImageMagick/FFmpeg pipelines, green screen transparency, format conversion. |
| `skills/create-video/SKILL.md` | Video Creative Director orchestrator. Defaults to Kling v3 Std as of v3.8.0; VEO is opt-in backup via `--provider veo`. |
| `skills/create-video/scripts/video_generate.py` | Async video generation with polling. Routes between Gemini API (VEO preview), Vertex AI (VEO GA + image-to-video + Scene Ext v2), and **Replicate (Kling v3 Std, v3.8.0+ default)** via `--backend` dispatch. |
| `skills/create-video/scripts/_vertex_backend.py` | **DELETED in v4.2.1.** Vertex AI retired. VEO 3.1 now routes through `scripts/backends/_replicate.py` via `google/veo-3.1-*` slugs. Config migration shim in `setup_mcp.py` still reads legacy `vertex_*` keys harmlessly for graceful upgrade. |
| `skills/create-video/scripts/_replicate_backend.py` | **v3.8.0+ (Fabric added v3.8.1)** — Pure data translation helper for Replicate predictions API. Hosts both Kling v3 Std (video) and Fabric 1.0 (lip-sync) model registry entries. Kling: multi_prompt/duration/aspect/mode validation. Fabric: resolution (480p/720p) + image/audio format validation + `audio_path_to_data_uri` helper. Response parsers handle the full 6-value status enum (including `aborted`). HTTP helpers use `Authorization: Bearer` + `User-Agent: creators-studio/...` to avoid Cloudflare rejection on `/v1/account`. `--diagnose` CLI pings the free account endpoint and lists registered models per-family. Stdlib only. |
| `skills/create-video/scripts/video_lipsync.py` | **v3.8.1+** — Standalone runner for Fabric 1.0 audio-driven lip-sync. Argparse: `--image FACE --audio AUDIO [--resolution 480p\|720p]`. Imports `_replicate_backend` for HTTP plumbing + validation + data-URI encoding — zero duplicated Replicate logic. Poll loop, download, and save follow the same pattern as `video_generate.py::_poll_replicate`. Closes the v3.8.0 gap where VEO-generated speech couldn't be paired with audio_pipeline.py custom voices. See `references/lipsync.md` for the 2-step narrate→lipsync workflow. |
| `skills/create-video/scripts/video_sequence.py` | Multi-shot sequence pipeline (plan → storyboard → generate → stitch). As of v3.8.0, all auto-selected quality tiers (draft/fast/standard/premium/lite/legacy) route to Kling v3 Std. `veo-backup` tier is opt-in VEO 3.1 Lite. |
| `skills/create-video/scripts/video_extend.py` | **DEPRECATED in v3.8.0.** Requires `--acknowledge-veo-limitations` flag or exits with code 2. Per spike 5 Phase 2C, VEO extended workflows produce glitches and inconsistent actors at 30s. Use `video_sequence.py` with Kling shot list for extended workflows instead. |
| `skills/create-video/references/kling-models.md` | **v3.8.0+ (Seedance retest appended v3.8.1)** — Kling v3 Std default model, capabilities, multi_prompt JSON schema, pricing ($0.16/8s pro mode), extended workflows via shot-list pipeline, known limitations (English+Chinese audio only, character variation across separate generations). v3.8.1 appends the Seedance 2.0 retest verdict: **permanently rejected for human-subject workflows** (E005 filter consistent across all tested human subjects; only non-human mascots pass). Authoritative source: `dev-docs/kwaivgi-kling-v3-video-llms.md`. |
| `skills/create-video/references/lipsync.md` | **v3.8.1+** — Fabric 1.0 audio-driven lip-sync reference: why the subcommand exists (closes the VEO external-audio gap), capabilities table (480p/720p, 60s max, mp3/wav/m4a/aac, jpg/jpeg/png), canonical 2-step workflow (`audio_pipeline.py narrate` → `video_lipsync.py`), cost comparison vs Kling/VEO alternatives, known limitations (mouth region only, no camera movement, no emotional direction beyond audio prosody). Authoritative source: `dev-docs/veed-fabric-1.0-llms.md`. |
| `skills/create-video/references/veo-models.md` | VEO model specs, pricing, rate limits, **v3.8.0 "BACKUP ONLY" status** with spike 5 scoreboard, 5 Vertex API constraints discovered in Phase 2, Lite/Fast/Standard tier comparison findings, Backend Availability (Gemini API vs Vertex AI), auth setup. |
| `skills/create-video/references/video-prompt-engineering.md` | 5-Part Video Framework, templates, camera motion vocabulary. |
| `skills/create-video/scripts/audio_pipeline.py` | **v3.7.1+v3.7.2, refactored in v4.2.1** — Multi-provider audio replacement pipeline. Subcommands: `pipeline`, `narrate`, `music --source lyria\|elevenlabs`, `mix`, `swap`, `voice-design`, `voice-promote`, `voice-list`, `status`. v4.2.1 adds Lyria routing helpers (`detect_lyrics_intent()`, `resolve_lyria_version()`, `LyriaUpgradeGateError`) + CLI flags `--lyria-version {2,3,3-pro}` + `--confirm-upgrade`. Lyria code migrated from inline Vertex URLs to `ReplicateBackend`. ElevenLabs code paths untouched. Stdlib only. |
| `skills/create-video/references/audio-pipeline.md` | **v3.7.1+v3.7.2** — Reference for the audio replacement architecture (renamed from `elevenlabs-audio.md` in v3.7.2). Covers Lyria + ElevenLabs music providers with the 5-way bake-off results, voice management (design → promote → use), prompt engineering for both TTS and music, FFmpeg parameter rationale, custom voice schema, cost model. |
| `agents/brief-constructor.md` | Subagent for prompt construction. |
| `scripts/backends/_base.py` | **v4.2.0** Provider-agnostic abstraction — `ProviderBackend` ABC + canonical types (`JobRef`, `JobStatus`, `TaskResult`, `AuthStatus`, `CanonicalImage` union) + exception hierarchy (`ProviderError`/Validation/HTTP/Auth). Contract every backend implements. Stdlib only, typing.X forms for 3.6+ compat. |
| `scripts/backends/_canonical.py` | **v4.2.0** Image normalizer (`Path`/`bytes`/URL/data-URI → data URI, with stdlib MIME sniffing) + constraint validator (duration_s, aspect_ratio, resolutions, prompt_max_chars, max_input_bytes). v4.2.1 adds `duration_s: {enum: [...]}` shape alongside `{min, max, integer}` for VEO's discrete `{4,6,8}` durations. Runs BEFORE any HTTP call. Stdlib only. |
| `scripts/backends/_replicate.py` | **v4.2.0** Replicate provider backend. v4.2.1 adds `music-generation` task type (for Lyria routing), `_MODEL_PARAM_DROPS` + `_filter_unsupported_params()` helper for per-model canonical-param filtering (e.g., drop `negative_prompt` for Lyria 3 with WARN log). Retains all legacy helpers (`validate_kling_params`, `build_kling_request_body`, `replicate_post/_get`, parse_replicate_* ) PLUS the `ReplicateBackend` class implementing the ABC. |
| `scripts/registry/models.json` | **v4.2.0 expanded in v4.2.1** — Single-source-of-truth model registry: 13 canonical models across image/video/music families. v4.2.0 seeded 6 models; v4.2.1 added VEO 3.1 (Lite/Fast/Standard), Lyria family (2, 3, 3-Pro), and ElevenLabs Music (with `(direct)` sentinel slug). v4.2.1 also corrected Kling v3 + v3 Omni pricing (the v4.2.0 `per_second: 0.02` was carried from an outdated source). `family_defaults.music = elevenlabs-music`. |
| `scripts/registry/registry.py` | **v4.2.0** Registry loader + typed query API (`load_registry()`, `get_model()`, `models_by_family()`, `providers_for_model()`, `family_default()`, `validate()`). Stdlib only. |
| `scripts/routing.py` | **v4.2.0** Two-stage routing: (1) `resolve_model()` — explicit `--model` > config `defaults.<family>_model` > registry `family_defaults[family]`. (2) `resolve_provider()` — explicit `--provider` > config `defaults.<family>` > `default_provider` > first-with-configured-api-key in registry insertion order. |
| `tests/test_*.py` | **v4.2.0** Test suite (stdlib `unittest`, zero pip deps, 74 tests). Run with `python3 -m unittest discover tests`. HTTP mocked via `urllib.request.urlopen` patch; no network required. Fixtures at `tests/fixtures/*.json`. |
| `references/providers/replicate.md` | **v4.2.0** Provider reference: auth, polling, Cloudflare User-Agent rule, 6-value status enum, pricing modes. Provider references live at plugin-root to be shared across skills. |
| `references/models/*.md` | **v4.2.0** Per-model references (capabilities, prompt quirks, constraints, authoritative source). Follow-up to sub-project A — initial references seeded from the existing `skills/create-*/references/*-models.md` files as they're migrated. |
| `references/models/pixverse-v6.md` | **2026-04-27** PixVerse V6 reference (Replicate `pixverse/pixverse-v6`). 4-tier resolution pricing (360p/540p/720p/1080p × audio toggle), up to 15s output, native multilingual text-in-video, multi-shot via `generate_multi_clip_switch` boolean (different shape from Kling's `multi_prompt` array). Registered in `scripts/registry/models.json` and `cost_tracker.py` PRICING dict; backend wiring (canonical-param translation in `_replicate.py`) deferred. Source: `dev-docs/pixverse-pixverse-v6-llms.md`. |
| `scripts/dev/publish.sh` | Bash helper for the everyday PR flow: derives a kebab-case branch name from the commit title, stages tracked files only (`git add -u`, never `-A`), commits with the Co-Authored-By trailer, pushes, opens a `gh` PR. Rolls local main back to `origin/main` if the user accidentally committed there. Stdlib bash only — needs `git` + `gh`. See "Publishing changes" section above. |
| `scripts/dev/release-zip.sh` | Bash helper for version releases: validates the version arg matches `plugin.json` AND that a `## [X.Y.Z]` section exists in CHANGELOG.md before doing anything destructive. Builds the distribution zip with the canonical exclude list (the same list documented in step 11 of the Feature Completion Checklist). Then runs `gh release create` with the zip attached. Stdlib bash only — needs `git` + `gh` + `jq` + `zip`. Tags `origin/main` HEAD; refuses to run on a dirty working tree. |

## Scripts use stdlib only

All scripts use Python's `urllib.request` to call APIs directly. They have ZERO pip dependencies by design. Do NOT add `google-genai`, `requests`, or `replicate` as dependencies — the stdlib approach keeps installation frictionless for users who just want to run the plugin.

### Python version floor

**As of v4.2.0: Python 3.12+.**

Previous floor was 3.6+, inherited from the 2023-era `banana-claude` fork. That constraint is retired — most users run 3.12+ today, and 3.12 gives us modern syntax (PEP 604 unions `X | None`, built-in generics `list[int]`, `dataclass(slots=True)`, `match`/`case` patterns, `type` aliases via PEP 695).

**What this means in practice:**
- New code (`scripts/backends/`, `scripts/registry/`, `scripts/routing.py`, `tests/`) uses modern syntax.
- Existing per-skill scripts (`skills/create-image/scripts/*.py`, `skills/create-video/scripts/*.py`) keep their current Python idiom — don't touch them purely to modernize. Modernize lazily when editing for other reasons.
- If Python 3.12 becomes unavailable for a user (e.g., stuck on a locked-down corporate box), that's a re-evaluation signal — not a constraint on new code.

## Key constraints

- `imageSize` parameter values must be UPPERCASE on the Gemini API: "1K", "2K", "4K". Lowercase fails silently.
- **Vertex AI uses lowercase `"4k"` for VEO `resolution`**, while the Gemini API and the plugin's existing image-gen scripts use uppercase `"4K"`. `_vertex_backend.build_vertex_request_body()` normalizes `"4K" → "4k"` at the request boundary so callers can keep using the uppercase convention. Don't change the plugin convention.
- Gemini generates ONE image per API call. There is no batch parameter.
- No negative prompt parameter exists. Use semantic reframing in the prompt.
- `responseModalities` must explicitly include "IMAGE" or the API returns text only.
- **Describe the scene, don't list keywords.** Gemini 3.1's core strength is narrative understanding — prose beats tag lists. (Google's official Gemini 3.1 Flash Image prompting guide, verified 2026-04-15.)
- **Don't name publication formats** in prompts: `"Vanity Fair magazine cover style"`, `"National Geographic cover story"`, `"Wallpaper* editorial"`, etc. Gemini 3.1 renders the output as a literal magazine cover with masthead typography and headline text overlays. This supersedes the v3.6.x "use prestigious context anchors" rule, which was empirically shown to be harmful in spike 6 (2026-04-15). See `skills/create-image/references/prompt-engineering.md` → "Prompt Patterns That Don't Help".
- The old "banned keywords" list (`"8K"`, `"masterpiece"`, `"ultra-realistic"`, `"high resolution"`) is useless on Gemini 3.1 but not harmful. Cut them to save tokens; don't panic if a user's source prompt contains them.
- NEVER mention "logo" in Presentation mode prompts -- the model generates unwanted logo artifacts. Describe the area as "clean negative space" instead. Logos are composited in presentation software.
- Brand Style Guide fields in presets are optional -- old presets without them continue to work.
- Fallback chain: MCP (primary) -> Direct Gemini API -> Replicate.
- **v3.7.1 audio architecture**: For multi-clip stitched VEO sequences that need narration or seam-free music, use `elevenlabs_audio.py pipeline` to replace the entire audio bed instead of relying on VEO's emergent audio. VEO's clip-locked music intro/outro envelopes create audible seams when concatenated; the v3.7.1 pipeline replaces them with a single continuous track. See `skills/create-video/references/elevenlabs-audio.md`.
- **v3.7.1 narration line-length rule**: For VEO native narration, target line word count = `duration_seconds × (voice_wpm / 60)`. ~16 words for an 8s clip at native VEO narrator pace (~120 wpm). Shorter lines trigger a known failure mode where VEO sings the line to fill time. Per-voice WPM differs (Daniel ~137, Nano Banana Narrator ~159) — see F8 in `references/video-audio.md`.
- **v3.7.1 narrator + visible character constraint**: When a human is visible in the VEO frame, prompting `"A narrator says..."` will cause VEO to lip-sync them to the line regardless of `NOT speaking, mouth closed` constraints. Workarounds: (a) frame the human without face visible, (b) use the v3.7.1 audio replacement pipeline to override VEO's lip-synced audio. See F1-F2 in `references/video-audio.md`.
- **Eleven Music API blocks named-creator/brand prompts**. Returns HTTP 400 with `bad_prompt` and a `prompt_suggestion`. This is music-API-specific — image generation prompts welcome creator names. Strip named-creator references from music prompts before sending. See F6 in `references/video-audio.md`.
- **Custom voice schema** (v3.7.1+): `~/.banana/config.json` `custom_voices.{role}` is the canonical location. Role-keyed (narrator, character_a, etc.), supports three creation paths via `source_type` discriminator (designed | cloned | library), provider-pluggable for future second-provider support.
- **v3.8.3 music provider default is ElevenLabs Music**, flipped from Lyria 2 after a 12-genre blind A/B bake-off (session 19, 2026-04-16) produced a decisive **ElevenLabs 12-0 sweep**. Every genre winner was "clear with a definite difference in quality and interpretation" per user. The v3.7.2 spike 4 Lyria win was a genre-specific anomaly on the single cinematic-documentary genre tested (both were close on that one). Lyria remains available via `--music-source lyria` — use it when `negative_prompt` exclusion is needed (ElevenLabs has no equivalent) or when the user lacks an ElevenLabs subscription. Lyria is $0.06/call fixed, 32.768s clip duration, reuses the existing `vertex_api_key` + `vertex_project_id` + `vertex_location` from VEO setup. See `references/audio-pipeline.md` for the full bake-off results and decision matrix.
- **Both music APIs (Lyria and Eleven Music) reject prompts containing named copyrighted creators or brands** (e.g. "Annie Leibovitz", "BBC Earth"). This is music-API-specific — image generation prompts welcome creator names. Strip named-creator references from music prompts before sending. See F6 in `references/video-audio.md`.
- **Audio gen model quality is uncorrelated with spec-sheet metrics** (F13 in `references/video-audio.md`). Spike 4 5-way bake-off proved this: Stable Audio 2.5 had the strongest specs but was rated worst by listening test; Lyria won despite being slower than Stable Audio. **Always evaluate new audio providers via subjective listening, not benchmark comparison.**
- **v3.7.4 stereo mix rule**: `audio_pipeline.py`'s `SIDECHAIN_FILTER` uses `aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0` on the narration branch (NOT `aformat=channel_layouts=stereo` alone). FFmpeg's `aformat` sets metadata but does not upmix mono sources to stereo — the v3.7.1 filter produced "stereo container with silent right channel" that sounded like speaker-left-only narration on headphones. The canonical mono-to-stereo upmix is `pan=stereo|c0=c0|c1=c0`, and the `mix_narration_with_music` ffmpeg invocation also passes `-ac 2` to lock the output channel count. Do not revert to the v3.7.1 pattern.
- **v3.7.4 client-side named-creator strip**: `audio_pipeline.py` maintains a `NAMED_CREATOR_TRIGGERS` list (20+ entries across photographers, publications, composers, broadcasters, pop artists) and strips any case-insensitive match from music prompts before sending to Lyria or ElevenLabs Music. This replaces the "don't name creators" user-side rule with a client-side safety net. Users can bypass with `--allow-creators` (e.g. to test whether the upstream filter has relaxed for a specific term or to handle false positives like the word "Drake" in a duck-themed prompt). The list lives in one place and covers both providers.
- **v3.7.4 Lyria long-music path**: when `length_ms > 32768` and `source=lyria`, `generate_music()` auto-routes to `generate_music_lyria_extended()` which makes N Lyria calls, chains them with FFmpeg `acrossfade=d=2:c1=tri:c2=tri`, trims to exact target. Cost: N × $0.06. For 90s = 3 calls = $0.18. If cost predictability matters over per-clip-control, fall back to `--music-source elevenlabs` which handles any length up to 600000ms in a single subscription-billed call.
- **v3.7.4 Instant Voice Cloning**: the `voice-clone` subcommand uploads 30+ seconds of audio (single file or directory of files) to `POST /v1/voices/add` via a new `_http_post_multipart()` stdlib helper. Result persists to `custom_voices.{role}` with `source_type=cloned` and `design_method=ivc`. If the response contains `requires_verification: true`, the voice is persisted but unusable until the user completes the ElevenLabs voice captcha in the dashboard. **Professional Voice Cloning (PVC) is NOT implemented** — deferred to v3.7.5+ as a separate subcommand since it needs 30+ minutes of audio + Creator+ plan + a multi-step fine-tuning workflow. The `source_type=cloned` enum value is shared between IVC and future PVC.
- **v3.7.4 auto-measured per-voice WPM**: `voice-promote` and `voice-clone` now auto-measure WPM after creation by generating a 38-word neutral reference phrase, probing the MP3 duration with ffprobe, computing `word_count / (duration_sec / 60)`, and persisting to `custom_voices.{role}.wpm`. The retroactive `voice-measure --role ROLE` subcommand measures existing pre-v3.7.4 voices. This replaces the hardcoded `Daniel ~137, Nano Banana Narrator ~159` values in the v3.7.1 line-length calibration rule (F8 in `references/video-audio.md`). The Creative Director skill should read `custom_voices.{role}.wpm` directly rather than guessing at per-voice pace. Measurement cost is negligible (one TTS call). Auto-measure is SKIPPED on voice-clone when `requires_verification: true` — run `voice-measure` manually after completing the captcha.
- **v3.8.0 default video model is Kling v3 Std** (`kwaivgi/kling-v3-video` via Replicate), replacing VEO 3.1 Standard. Per spike 5 (94 generations, ~$53 total spend): Kling wins 8 of 15 playback-verified shot types to VEO Fast's 0, is 7.5× cheaper per 8s clip, and produces coherent 30s narratives where VEO's extended workflow produces "glitches, inconsistent actors, horrible" (user verdict 2026-04-15). VEO remains callable as opt-in backup via `--provider veo --tier {lite|fast|standard}`. Full spike findings at `spikes/v3.8.0-provider-bakeoff/writeup/v3.8.0-bakeoff-findings.md`.
- **v3.8.0 Kling parameter constraints** (all from the Kling v3 Std model card at `dev-docs/kwaivgi-kling-v3-video-llms.md`, enforced client-side by `_replicate_backend.validate_kling_params()`): aspect_ratio ∈ {16:9, 9:16, **1:1**} — Kling is the only plugin-registered model with 1:1 support; duration integer in [3, 15]; mode ∈ {standard (720p), pro (1080p)} — no 4K support; multi_prompt is a JSON array STRING with max 6 shots, min 1s per shot, and **sum of shot durations MUST equal the top-level `duration`** parameter (hardest rule, easy to miss); `end_image` requires `start_image`; start_image max 10 MB; prompt/negative_prompt max 2500 chars.
- **v3.8.0 Kling audio limitation**: per the model card's "Limitations" section, audio generation works best in English and Chinese only. Other languages are unverified. For non-English-or-Chinese workflows, generate with `generate_audio: false` and use `audio_pipeline.py` with ElevenLabs TTS + Lyria music for the audio bed.
- **v3.8.0 `aspect_ratio` + `start_image` mutual exclusion**: when both are provided to Kling, `aspect_ratio` is IGNORED and the output uses the start image's native aspect ratio. `validate_kling_params()` logs a WARNING but does not raise. The SKILL.md orchestrator instructs Claude to offer cropping/padding the start image if the aspect conflict matters to the user.
- **v3.8.0 Replicate Cloudflare + User-Agent**: `api.replicate.com/v1/account` returns HTTP 403 (Cloudflare error code 1010) on requests with the default Python-urllib User-Agent. `_replicate_backend.py` sends `User-Agent: creators-studio/3.8.0 (+https://github.com/juliandickie/creators-studio)` on every request to avoid the WAF heuristic. The existing image-gen `replicate_generate.py` does NOT set a User-Agent and works only because `/v1/models/.../predictions` endpoints have more lenient Cloudflare rules — adding User-Agent to that script is a candidate v3.8.x hardening.
- **v3.8.0 `Prefer: wait=0` is non-spec-compliant**: Replicate's OpenAPI regex is `^wait(=([1-9]|[1-9][0-9]|60))?$`, so `wait=0` doesn't match. The spike's `lib/replicate_client.py` used `wait=0` and it happened to work. `_replicate_backend.py` omits the `Prefer` header entirely for async-first semantic (correct for Kling's 3-6 min wall times). If a future use case needs sync mode, use `wait=N` with N ∈ [1, 60].
- **v3.8.0 Replicate Prediction.status has 6 values, not 5**: the spike's client only handles `starting | processing | succeeded | failed | canceled`. The OpenAPI schema explicitly adds `aborted` (terminated before `predict()` is called, e.g., queue eviction or deadline). `_replicate_backend.parse_replicate_poll_response()` maps `aborted` to the "failed" bucket — if we missed this, the poll loop would spin forever on aborted predictions.
- **v3.8.0 `video_extend.py` is deprecated**: hard gate via `--acknowledge-veo-limitations` flag. Running without the flag exits with code 2 and a JSON message pointing users at `video_sequence.py` with the Kling shot-list pipeline. Per spike 5 Phase 2C, VEO's Scene Extension v2 + keyframe fallback produces glitches and inconsistent actors at 30s — user verdict: "horrible, do not use". This is hard-gated, not just warned, to prevent accidental use.
- **v3.8.0 Kling chain helper deferred**: the spike's `extended_run.py` proved last-frame-chaining Kling calls works for single-continuous-long-shot workflows, but the existing `video_sequence.py` shot-list pipeline already handles extended workflows via independent Kling calls per shot. A dedicated Kling chain helper is deferred to v3.8.x if a specific single-continuous-30s use case emerges.
- **v3.8.1 Fabric 1.0 lip-sync via `/create-video lipsync`**: new standalone `video_lipsync.py` runner for VEED Fabric 1.0 (`veed/fabric-1.0` on Replicate). Takes image + audio + resolution ∈ {480p, 720p}, produces a talking-head MP4 where the face is lip-synced to the audio. Closes the v3.8.0 gap where VEO generated speech internally and Kling didn't accept audio input — so custom-designed ElevenLabs voices from `audio_pipeline.py narrate` had no way to reach a visible character's face. The recommended flow is 2-step: `audio_pipeline.py narrate --voice brand_voice --out /tmp/narr.mp3` → `video_lipsync.py --image face.png --audio /tmp/narr.mp3`. See `references/lipsync.md`.
- **v3.8.1 Fabric 1.0 constraints (pricing patched 2026-04-27)**: input formats image ∈ {jpg, jpeg, png}, audio ∈ {mp3, wav, m4a, aac}. Output resolution ∈ {480p, 720p} (no 1080p or 4K). Max duration 60 seconds (driven by audio length). No prompt parameter — Fabric ONLY animates the face, nothing else in the frame. No camera movement, no body animation, no emotional direction beyond audio prosody. Cost is **resolution-keyed**: `$0.08`/s at 480p and `$0.15`/s at 720p (authoritative from Replicate's official Fabric 1.0 model card, verified 2026-04-27). The 720p rate was also empirically verified 2026-04-15 via 3 dashboard-confirmed runs (`w36styf3c9rmw0cxj3cbyvnxz8` 8s@720p $1.20, `j3qp5ndaanrmr0cxj4qrnrhhf4` 7s@720p $1.05, `55qej5ghs1rmw0cxj4wr1wjgdg` 7s@720p $1.05); the v3.8.1 doc assumed 480p was equal to 720p — the 2026-04-27 patch corrects that. **480p is ~47% cheaper than 720p** — for drafts, social previews, and internal reels, default to 480p. Linear formulas: `cost(480p) ≈ $0.08 × output_duration_seconds` (7s = $0.56, 8s = $0.64, 60s max = $4.80); `cost(720p) ≈ $0.15 × output_duration_seconds` (7s = $1.05, 8s = $1.20, 60s max = $9.00). Cold-start adds ~36s wall time but does NOT increase cost (Replicate bills Fabric on output duration, not GPU wall time). Replicate's API still doesn't expose per-prediction `cost_usd` — `/v1/predictions/<id>` has `metrics.predict_time` and `metrics.video_output_duration_seconds` only; the authoritative pricing source is the model-card "Pricing" block at `replicate.com/veed/fabric-1.0` (re-fetch on every Fabric pricing review). **Comparison vs alternatives**: at 720p Fabric is ~7.5× more expensive per second than Kling v3 ($0.02/s) and ~3× more than VEO Lite at 720p ($0.05/s); at 480p Fabric closes the gap to VEO Lite ($0.08/s vs $0.05/s) but still costs more. Justified only when you need a custom-designed ElevenLabs voice paired with a visible face — Kling and VEO can't do that. The registry uses `pricing.mode = per_second_by_resolution` with `rates = {"480p": 0.08, "720p": 0.15}`; `cost_tracker.py` looks up via `_lookup_cost(model, resolution, duration_s=N)`. `video_lipsync.py` shells out to `cost_tracker.py log --resolution {480p|720p} --duration-s <output_seconds>` (the previous duration-as-resolution hack was removed in the 2026-04-27 patch). See `skills/create-video/references/lipsync.md` §Empirical verification and `references/models/fabric-1.0.md` for the full data.
- **v3.8.1 User-Agent hardening applied to image-gen Replicate scripts**: `skills/create-image/scripts/replicate_generate.py` and `replicate_edit.py` now send `User-Agent: creators-studio/3.8.1 (+https://github.com/juliandickie/creators-studio)` on every Replicate request. Defensive fix — the image-gen scripts currently work without User-Agent, but the video-side `_replicate_backend.py` hit HTTP 403 Cloudflare error 1010 on `/v1/account` without it. The same edge rules could tighten on `/v1/models/.../predictions` at any time; the UA header is forward-compatible hardening.
- **v3.8.1 Seedance 2.0 retest verdict — permanently rejected**: The user-requested retest (3 diverse Phase 2 subjects: woman in home office, woman athlete, cartoon robot mascot) completed 2026-04-15. Results: 2 of 3 FAILED with `E005 — input/output flagged as sensitive` on both human subjects (talking head AND athlete). Only the non-human cartoon robot mascot succeeded. Pattern is consistent with Phase 1's rejection on the bearded-man subject: **any human subject triggers the ByteDance safety filter**. Seedance is NOT wired into the plugin as a default, backup, or tertiary provider — it's unusable for the plugin's primary workflows (human subjects, product demos, talking heads, social content). Retest spend: $0.14 + $0.48 (anchors). Documented in `references/kling-models.md` "Seedance 2.0 retest outcome (v3.8.1)" section.
- **v3.8.1 Vertex smoke-test subcommand on `_vertex_backend.py`**: new `smoke-test` subparser (sibling to `diagnose`) that validates spike 5 Phase 2 Vertex API constraints via 3 FREE probes: (1) preview-ID → 404, (2) invalid aspect ratio "1:1" → HTTP 400, (3) Gemini auth ping. **Only free probes** — an earlier design accidentally burned ~$3.60 by submitting minimal valid VEO requests that passed validation at submit time but generated real videos. The fix: only use probes that reject at URL resolution (404) or synchronously at submit validation. The other 2 constraints (GA -001 reachability, duration {4,6,8}) are documented in the output as "requires budget to verify" rather than auto-tested.
- **v3.8.1 empirical finding — Vertex drift from spike 5 Phase 2**: During the smoke-test design, Vertex accepted `durationSeconds=5` on VEO 3.1 Lite GA -001 instead of rejecting it synchronously as spike 5 Phase 2 observed. This suggests either (a) the duration constraint has relaxed on this Vertex project, (b) validation moved from synchronous to asynchronous. Either way, the spike 5 finding "Vertex validates durations synchronously at submit time" is no longer reliable as of 2026-04-15. The v3.8.1 smoke test does NOT test duration to avoid the billing trap; this drift is documented in `references/veo-models.md` and in the smoke-test's "untested constraints" output section.

- **v3.8.2 Kling start_image is a conditional identity lock**: when `start_image` is provided AND the text prompt describes the same character (matching age, gender, hair, clothing, setting), Kling preserves character identity through the full clip at 1072×1928 pro mode. When the prompt describes a DIFFERENT character, Kling morphs completely toward the prompted character within 5 seconds — the start_image only affects frame 0. Prompt engineering is the critical variable for cross-clip character consistency. Empirically verified in session 19 (2026-04-16) via 6-run spike: 2 matched-prompt runs preserved identity perfectly, 2 mismatched-prompt runs morphed completely, 2 DreamActor comparison runs preserved identity at lower res (694×1242) and 2.5× higher cost ($0.05/s vs $0.02/s). DreamActor remains valuable only for real-footage-to-avatar workflows (mapping a generated character onto filmed human motion). Works for both human and non-human subjects (robot mascot proven in spike 5 Phase 2 test_11, user-confirmed session 19). See `skills/create-video/references/kling-models.md` §Character Consistency via start_image.

- **v3.8.4 Replicate video cost-tracking dispatch**: `cost_tracker.py::_lookup_cost()` now branches on which key is present in the model's PRICING entry — `per_second` (Replicate video models: Kling $0.02/s, DreamActor $0.05/s, Fabric $0.15/s), `per_clip` (Lyria $0.06, fixed 32.768s), or resolution-keyed (Gemini image-gen: 512/1K/2K/4K). For per-second models, callers pass duration as the `resolution` string (e.g. `"8s"`). `video_generate.py` and `video_lipsync.py` shell out to `cost_tracker.py log` after successful runs via `subprocess.run(..., capture_output=True, timeout=5)` with a bare `except: pass` — **cost logging never blocks generation output**. The Lyria `per_clip` branch was previously unreachable dead code (fell through to 1K image pricing); it's now live and correct. **(Subsequent change, 2026-04-27 Fabric pricing patch: Fabric switched from `per_second` to `per_second_by_resolution` mode — see the v3.8.1 entry above. Kling Std and DreamActor are still per_second; v4.2.1 corrected Kling v3 + v3 Omni to `per_second_by_resolution_and_audio` separately.)**

- **v3.8.4 strip-list trigger-list precedence** (three-tier): `audio_pipeline.py::strip_named_creators()` looks up triggers in this order: (1) explicit `triggers=` parameter (caller override), (2) `named_creator_triggers` list in `~/.banana/config.json` (user override, NEW in v3.8.4), (3) hardcoded `NAMED_CREATOR_TRIGGERS` default. Users add custom strip terms without editing the script. After stripping a creator name, wrapper phrases (`"in the style of"`, `"inspired by"`, `"reminiscent of"`, `"like"`, `"à la"`, `"a la"`, `"channeling"`, `"evoking"`) are cleaned up via case-insensitive regex — so `"in the style of Hans Zimmer, warm strings"` becomes `"warm strings"` instead of the v3.8.3 dangling-fragment output `"in the style of , warm strings"`.

- **v4.0.0 rebrand is model-agnostic on purpose**: the plugin identity is now `creators-studio` (was `nano-banana-studio`), commands are `/create-image` and `/create-video` (was `/banana` and `/video`), skill dirs are `skills/create-image/` and `skills/create-video/` (was `skills/banana/` and `skills/video/`). Tagline: *Imagine · Direct · Generate — Creative Engine for Claude Code.* The rename decouples the plugin from any one model provider so future best-in-class swaps (like v3.8.0's VEO→Kling, v3.8.3's Lyria→ElevenLabs) don't require another rebrand. **DO NOT reintroduce the old names in new code or docs** — if a reference to `/banana` or `nano-banana-studio` appears anywhere, treat it as stale and update it. Google model identifiers (`google/nano-banana-2`, `gemini-3.1-flash-image-preview`) are explicitly preserved — those are Google's brand, not the plugin's.

- **v4.0.0 backward-compat boundary**: `~/.banana/` config directory is **intentionally NOT renamed** — API keys (Google, Replicate, ElevenLabs, Vertex), custom voices, custom preset overrides, cost ledger, and session history all stay at the existing path. Renaming user state on upgrade would force every existing user to re-paste API keys and re-design custom voices. The slight asymmetry of a "Creators Studio" plugin writing to `~/.banana/` is the correct trade-off. `@ycse/nanobanana-mcp` package name is also unchanged — it's a third-party upstream dependency the plugin doesn't own. **Product branding can be renamed freely; touch user state carefully.**

- **v4.1.0 `per_call` pricing mode**: `cost_tracker.py::_lookup_cost()` now dispatches on four pricing keys: `per_call` (Recraft Vectorize $0.01, resolution ignored), `per_clip` (Lyria $0.06, resolution ignored), `per_second` (Kling/DreamActor/Fabric/VEO — duration passed as resolution like `"8s"`), and resolution-keyed (Gemini image-gen — `"512"`/`"1K"`/`"2K"`/`"4K"`). When logging a Recraft call, pass `--resolution N/A`. This is the simplest pricing mode — flat fee regardless of input dimensions. **(Subsequent additions: v4.2.1 added `per_second_by_resolution`, `per_second_by_audio`, and `per_second_by_resolution_and_audio` modes for VEO and Kling. The 2026-04-27 Fabric pricing patch moved Fabric out of `per_second` into `per_second_by_resolution`. The current dispatch supports 7 modes total.)**

- **v4.1.0 social dimension-enforcer contract**: `social.py::resize_for_platform()` returns a structured dict with `method` ∈ {`resize_only`, `resize_and_crop`, `copy_fallback`}, `tool` ∈ {`magick`, `convert`, `sips`, `None`}, `source_dimensions`, `output_dimensions`, and `warning`. **`copy_fallback` means the output file has WRONG dimensions** (source was copied unchanged because neither magick nor sips could handle the ratio-change crop) — the SKILL.md orchestrator must surface the warning to the user and present the 3-option choice (install / proceed / cancel) before shipping those files. Never silently accept a `copy_fallback` result.

- **v4.1.0 `RECRAFT_IMAGE_MIME_MAP` is deliberately separate from `IMAGE_MIME_MAP`**: Recraft accepts PNG/JPG/WEBP per its model card; Kling's `IMAGE_MIME_MAP` intentionally excludes WEBP because the Kling model card doesn't list it. Keeping them separate avoids weakening Kling's validation just to widen Recraft's. When adding a new Replicate model, default to a model-specific MIME map rather than extending the shared one.

- **v4.1.0 SKILL.md §Step 9.5 rule for missing-tool degradation**: when a script returns `method: "copy_fallback"` or a non-null `warning` field pointing at a missing optional tool, present the user the 3-option pattern (install / proceed degraded / cancel) instead of silently accepting. Also do this proactively before `/create-image social` calls with aggressive ratio shifts (9:16, 21:9, 4:1) — shell `which magick`; if missing, prompt before generating. The principle: **never silently degrade on missing tools**. See `scripts/validate_setup.py` for the canonical tool list and what each unlocks.

- **v4.1.0 cross-skill import pattern**: `skills/create-image/scripts/vectorize.py` imports `_replicate_backend` from `skills/create-video/scripts/` via a `sys.path.insert()` shim. This is the approved pattern for image-side Replicate integrations that want to reuse the shared HTTP/auth/poll plumbing without duplicating code. The relative path is predictable (both skills are siblings under `skills/`). When adding future image-side Replicate features (e.g., background removal, outpainting), use the same pattern rather than forking `_replicate_backend.py`.

- **v4.1.2 social platform scope is 87 image placements across 16 platforms**: Instagram, Facebook, YouTube, LinkedIn, Twitter/X, TikTok, Pinterest, Threads, Snapchat, Google Ads, Spotify, Telegram, Signal, WhatsApp, ManyChat, BlueSky. v4.1.1's 6-platform narrowing was reversed in v4.1.2 after user feedback ("expand, don't narrow"). The video side mirrors this scope in `skills/create-video/references/social-platforms.md` with 37 video placements across 14 platforms (Signal + ManyChat don't have native video). Image specs live in the image skill; video specs live in the video skill. A unified `/social-pack` command combining both is on the roadmap.

- **v4.1.2 default `--mode` flipped to `complete`** for `/create-image social`: text-rendering is allowed by default. Claude infers whether text should render from the prompt/application context rather than auto-suppressing. Users who want text-free output pass `--mode image-only`, which now also appends an explicit `"NO text, NO logos, NO typography"` clause to the prompt (not just the response modality). The v4.1.1 default was backwards for the social command since finished social assets typically need text. Image-generation commands OUTSIDE `/create-image social` already defaulted to text+image modalities — no flip needed there.

- **v4.1.2 non-standard target ratio handling**: social placements whose true aspect isn't in Gemini's 14-ratio set (e.g. TikTok Branded Hashtag Banner 5:1, Twitter/X Header 3:1, LinkedIn Company Cover 5.9:1, Facebook Cover 2.7:1, Snapchat Story Ad Tile 1:1.67) generate at the closest-supported ratio (picking the one with smallest expected crop loss) and rely on `resize_for_platform()` to trim to exact pixel dimensions. Each such placement documents its generation ratio and trim % in the PLATFORMS dict `notes` field. **Never invent new aspect ratios for Gemini** — the 14 supported are: `1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, 1:4, 4:1, 1:8, 8:1` (per `dev-docs/google-nano-banana-2-llms.md`).

- **v4.1.2 BlueSky specs are best-guess, flagged for verification**. BlueSky isn't in the SOP doc (January 2026); current specs (profile 400×400, banner 3000×1000, feed 1080×1080 / 1080×1350) are based on community conventions. Verify against official BlueSky docs or the BlueSky Atproto spec before relying on exact dimensions in production. Placement `notes` field flags this explicitly.

- **v4.1.2 `/create-video social` is deferred to v4.2.0** but its spec catalogue ships in v4.1.2. The full 37-placement × 14-platform table lives in `skills/create-video/references/social-platforms.md` with `duration_min_s` and `duration_max_s` per placement. v4.2.0's CLI will read from this reference + a forthcoming `PLATFORMS_VIDEO` dict in a new `skills/create-video/scripts/social.py`. The runtime routing will use Kling v3 Std for clips ≤ 15s, Kling shot-list pipeline for > 15s, and VEO 3.1 as opt-in backup.

- **v4.2.0 provider abstraction rule**: skill orchestrator code (SKILL.md + `skills/*/scripts/*.py`) MUST NOT reference provider-specific field names (`start_image`, `multi_prompt`, `image_url`, etc.). Orchestrators pass **canonical params** only; backends translate internally. Provider-unique features reach the API via `provider_opts` escape hatch (merged after canonical translation in `ReplicateBackend.submit()`). See `docs/superpowers/specs/2026-04-23-provider-abstraction-design.md` and `docs/superpowers/plans/2026-04-23-provider-abstraction-subproject-a.md`.

- **v4.2.0 adding a new model.** Add an entry to `scripts/registry/models.json`. Add `references/models/<id>.md`. If the model introduces a novel canonical capability, extend `scripts/backends/_base.py` task schema and `scripts/backends/_canonical.py` enforcement. That's the PR — zero orchestrator edits.

- **v4.2.0 adding a new provider** (Kie.ai = sub-project C, HF Inference Providers = sub-project D, future marketplaces). New file `scripts/backends/_<provider>.py` implementing `ProviderBackend`. Add `references/providers/<provider>.md`. Add `providers.<name>` entries to relevant models in `models.json`. Add a key prompt to `setup_mcp.py`. Add pricing lookup to `cost_tracker.py` if the provider has a novel pricing mode.

- **v4.2.0 plugin-root `scripts/` directory.** Shared abstraction code lives at `scripts/` at the plugin root — NOT per-skill. Skills reach in via a sys.path shim to `plugin_root`. This supersedes the v4.1.0 cross-skill pattern (which routed through `skills/create-video/scripts/`). `skills/<name>/scripts/*.py` stays skill-specific; `scripts/*.py` is shared infrastructure. The `.gitignore` exclusion of `/scripts/` (from the pre-v4.0.0 nano-banana era) was removed.

- **v4.2.0 config schema** is `providers.<name>.api_key` (and `providers.vertex.project_id` etc.). Old flat keys (`replicate_api_token`, `google_api_key`, `elevenlabs_api_key`, `vertex_*`) are still readable via `setup_mcp.migrate_config_to_v4_2_0()` which runs on every `load_banana_config()` call. When both old and new forms are present, NEW wins. `~/.banana/` directory path is unchanged per the v4.0.0 user-state-boundary rule. New writes go to the v4.2.0 schema.

- **v4.2.0 testing rule.** Tests use stdlib `unittest` (zero new runtime or dev dependencies). Run from plugin root: `python3 -m unittest discover tests`. HTTP calls are mocked via `urllib.request.urlopen` patch — no network required. Fixtures live at `tests/fixtures/*.json`. Before committing any change to `scripts/backends/` or `scripts/registry/` or `scripts/routing.py` or the migrated call sites (`video_generate.py`, `video_lipsync.py`, `vectorize.py`), run the test suite.

- **v4.2.0 ReplicateBackend is the only concrete backend shipped in sub-project A.** Gemini direct (`generate.py` + `edit.py`) and ElevenLabs (`audio_pipeline.py`) continue to use their existing direct-call code paths — they are NOT yet refactored into `scripts/backends/_gemini_direct.py` / `_elevenlabs.py`. Those refactors are follow-ups, not blocking. Zero behavior change for users of any current command.

- **v4.2.0 model registry `family_defaults`** only covers `image` (→ nano-banana-2) and `video` (→ kling-v3) in A. `music` and `speech` families are added when ElevenLabs is refactored into a backend (follow-up). Until then, existing `audio_pipeline.py` flows are outside the registry/routing system and work unchanged.

- **v4.2.1 Vertex retirement complete.** `skills/create-video/scripts/_vertex_backend.py` is deleted. VEO 3.1 (Lite/Fast/Standard) routes through `ReplicateBackend` via `google/veo-3.1-*` slugs. Lyria 2 → Lyria 3 upgraded as the within-Lyria default; Lyria 2 kept for `negative_prompt`; Lyria 3 Pro registered for full-song generation. `audio_pipeline.py` Lyria code routes through `ReplicateBackend`; ElevenLabs code paths are untouched. The config migration shim in `setup_mcp.py` still reads legacy `vertex_*` keys (harmless — nothing consumes them).

- **v4.2.1 multi-model principle codified.** Every model family in the registry MUST register at least 2 models. Rationale: every previous default has been dethroned eventually (v3.8.0 Kling dethroned VEO; v3.8.3 ElevenLabs dethroned Lyria), so pre-registering alternatives means "new default" is a registry-entry change, not a code change. Current state: video (7 models), music (4 models), image (2 models — but only 1 text-to-image until sub-project C adds Imagen/Seedream/Flux from Kie.ai).

- **v4.2.1 Lyria auto-routing rule.** Within the Lyria family, `audio_pipeline.py::resolve_lyria_version()` picks Lyria 2 / 3 / 3-Pro based on flags + prompt content. Precedence: explicit `--lyria-version` > `--negative-prompt` (routes to Lyria 2) > `detect_lyrics_intent(prompt)` (routes to Lyria 3 Pro, requires `--confirm-upgrade`) > default Lyria 3 Clip. Auto-upgrade to Pro is HARD-GATED: without `--confirm-upgrade`, the pipeline aborts with a 3-option help message. Prevents silent 2x cost surprises.

- **v4.2.1 Kling pricing correction.** The v4.2.0 registry seeded Kling v3 with `per_second: $0.02/s` — incorrect (outdated source). Actual rates are 10-17x higher. v4.2.1 corrects to `per_second_by_resolution_and_audio` mode with verified rates from `dev-docs/kwaivgi-kling-v3-video-llms.md`. Kling v3 Omni rates similarly corrected (slightly cheaper on audio). **This inverts the v3.8.0 "Kling 7.5x cheaper than VEO" claim** — at verified rates, VEO Lite is ~4x cheaper than Kling at 1080p with audio. Queued: post-sub-project-C re-evaluation bake-off.

- **v4.2.1 three new pricing modes** in `cost_tracker.py` (key-as-discriminator, matching the existing pattern):
  - `per_second_by_resolution` — keyed by resolution string (VEO Lite)
  - `per_second_by_audio` — keyed by audio_enabled bool (VEO Fast + Standard)
  - `per_second_by_resolution_and_audio` — two-dimensional (Kling v3 + v3 Omni)
  `_lookup_cost()` gains keyword-only `duration_s` + `audio_enabled` kwargs. CLI surface: `--duration-s` + `--audio-enabled` flags on the `log` and `estimate` subcommands.

- **v4.2.1 canonical schema extension.** `scripts/backends/_canonical.py::validate_canonical_params` now accepts `duration_s: {enum: [...]}` as an alternative to `{min, max, integer}`. VEO uses enum `{4, 6, 8}`; Kling/Fabric/DreamActor continue using range. Mutually exclusive — backend picks based on which key is present.

- **v4.2.1 per-model param filtering in ReplicateBackend.** When a canonical request carries params that the specific model doesn't support (e.g., `negative_prompt` passed to Lyria 3), `_filter_unsupported_params()` silently drops them and logs a WARN via `_logger`. Callers can pass rich canonical payloads without knowing every model's exact surface. Drop table is `_MODEL_PARAM_DROPS` in `scripts/backends/_replicate.py`. Current drops: `google/lyria-3` and `google/lyria-3-pro` drop `negative_prompt + seed`; `google/lyria-2` drops `reference_images`.

- **v4.2.1 VEO deprecation aliases.** `--backend vertex-ai` and `--provider veo` continue to work but log a one-line deprecation warning and auto-route to Replicate. Legacy Vertex model IDs (`veo-3.1-generate-001` etc.) auto-translate to Replicate slugs via `_VERTEX_TO_REPLICATE_SLUG` map in `video_generate.py`. All three compatibility paths are removed in v4.3.0.

## Upstream tracking

Originally forked from https://github.com/AgriciDaniel/banana-claude (v1.4.1 baseline), now an independent project.

To check for upstream changes:
```bash
git fetch upstream
git diff upstream/main
```

Our additions over upstream: Replicate backend, Presentation mode, Brand Style Guides,
research-driven prompt improvements (5-Input Creative Brief, PEEL strategy, Edit-First,
Progressive Enhancement, expanded character consistency, multilingual support).

## Installation

Test locally: `claude --plugin-dir .` or standalone: `bash install.sh`

## Feature Completion Checklist

**MANDATORY: After completing ANY feature or significant change, run through this
entire checklist before committing.** Do not skip items. Do not batch them for later.

### 1. Version Bump (ALL 3 files)

| File | What to update |
|------|---------------|
| `.claude-plugin/plugin.json` | `"version"` field |
| `README.md` | Version badge number in shields.io URL |
| `CITATION.cff` | `version` field + `date-released` to today |

Do NOT set version in `marketplace.json` -- it conflicts with `plugin.json`.
SKILL.md no longer carries version -- `plugin.json` is the authoritative source.

### 2. Documentation Updates

| File | What to update |
|------|---------------|
| `CHANGELOG.md` | Add new `## [X.Y.Z]` section with Added/Changed/Fixed. Add link reference at bottom. |
| `README.md` | Update "What's New in This Fork" section if feature is user-facing. Update architecture diagram if new files created. Update commands table if new commands added. |
| `PROGRESS.md` | Add session entry with numbered list of what was done. Update priority table if roadmap item completed. Update version in header. |
| `ROADMAP.md` | Mark completed features. Update version reference. |
| `CLAUDE.md` | Update file responsibilities table if new files created. Update key constraints if new rules added. |

### 3. README "What's New in This Fork" Check (IMPORTANT — frequently missed)

If the feature is user-facing, it MUST appear in the README "What's New in This Fork" section.
Each feature gets a `### Feature Name (vX.Y.Z)` heading.

**CRITICAL — README subsections are sales copy, not changelog entries.** The README is the plugin's sales page. The job of a What's New subsection is to convince a prospective user that the feature is valuable in the time it takes to read 1–3 sentences. Detailed decision trees, bullet lists of every change, empirical findings, cost breakdowns, and implementation notes all belong in CHANGELOG.md / PROGRESS.md / ROADMAP.md — **not** in README.

| Pattern | Belongs in |
|---|---|
| "Feature X lets you do Y so that Z." (1–3 sentences, ≤100 words) | README |
| "Five more deferred-bucket items — the theme is..." followed by 5 bullets | CHANGELOG |
| Empirical spike findings, file-size variance, cost tables | CHANGELOG + PROGRESS |
| Setup walkthrough, config field names, CLI flag lists | Reference docs + CHANGELOG |
| Internal rationale ("the coffee shop demo surfaced...") | PROGRESS |
| "Why [decision]" / "What this unlocks" paragraphs | PROGRESS or the reference doc |

**Target length:** match the style of the v2.x entries (`### Asset Registry (v1.8.0)`, `### Analytics Dashboard (v2.6.0)`, etc.) — 1–3 sentences, value-forward, no sub-bullets unless the feature genuinely ships multiple user-facing capabilities worth naming separately (e.g. v3.7.1 shipped both the audio pipeline AND custom voice design — two distinct value props, so two short paragraphs is OK).

**Rule of thumb:** if a user would read the README subsection and think "that's the *news*, not a *summary*," it's too long. Cut it in half and move the details to CHANGELOG.

**Retrospective correction:** v3.6.0–v3.6.3 README subsections were written as mini-changelogs with 5-7 bullets each and were slimmed to 1-3 sentences in v3.7.3. Do not regenerate that mistake on future releases — check this section before writing the What's New paragraph.

### 4. Command Sync Check (IMPORTANT — frequently missed)

Every command in SKILL.md Quick Reference table MUST also appear in:
- **README.md Commands table** — exact same commands and descriptions
- **README.md Quick Start section** — include examples for major new commands

Run this to verify:
```bash
echo "=== SKILL.md ===" && grep '| `/create-image' skills/create-image/SKILL.md
echo "=== README ===" && grep '| `/create-image' README.md
```
If they don't match, update README before committing.

### 5. README Architecture Diagram Check (IMPORTANT — frequently missed)

If ANY new files were created (scripts, references, presets, etc.), the architecture
tree diagram in README.md MUST be updated to include them. Also verify the version
number and SKILL.md line count in the diagram are current.

Run this to compare:
```bash
echo "=== Diagram files ===" && grep '│' README.md | grep -oE '[a-z_-]+\.(md|py|json)' | sort
echo "=== Actual files ===" && (ls skills/create-image/references/ skills/create-image/scripts/) | sort
```
If the lists don't match, update the diagram.

### 6. Cross-File Consistency Check (versions, models, ratios)

After all edits, verify these match across files:
- **Version number** identical in all 3 version files (plugin.json, README.md badge, CITATION.cff)
- **File list** in CLAUDE.md file responsibilities table matches what exists on disk
- **Model names** and **rate limits** consistent across gemini-models.md, cost-tracking.md, mcp-tools.md
- **Aspect ratios** consistent across gemini-models.md, replicate.md, generate.py, replicate_generate.py

### 7. New Script Checks

If any new Python scripts were created:
- `chmod +x` — all scripts in `scripts/` must be executable
- Verify they compile: `python3 -c "import py_compile; py_compile.compile('path', doraise=True)"`
- Test `--help` works

### 8. SKILL.md Size Check

```bash
wc -l skills/create-image/SKILL.md  # Must stay under 500 lines
```

Current: ~200 lines (lean orchestrator pattern). If approaching 300+, extract to reference files.

### 9. Memory File

Update `~/.claude/projects/.../memory/project_creators_studio_workflow.md` if:
- Version changed
- New key constraints added
- Architecture changed (e.g., new skill files, new reference files)

### 10. Git Commit + Push (via PR)

**Direct pushes to `main` are blocked.** Land changes via PR using the helper script:

```bash
scripts/dev/publish.sh "feat: short title describing the change"
# or
scripts/dev/publish.sh "fix: short title" "Multi-line PR body."
```

Use Conventional Commit prefixes — they drive the branch name:
- `feat:` for new features → branch `feat/<slug>`
- `fix:` for bug fixes → branch `fix/<slug>`
- `docs:` for documentation only → branch `docs/<slug>`
- `refactor:` for restructuring → branch `refactor/<slug>`
- `chore:` for housekeeping → branch `chore/<slug>`

The script stages ONLY tracked files (never `git add -A`), opens the PR with the Co-Authored-By trailer, and prints the PR URL. After merge, run `git checkout main && git pull && git branch -D <feature-branch>` to clean up.

### 11. GitHub Release + Distribution Zips (on version bumps)

After the version-bump commit has merged to `main`, run:

```bash
scripts/dev/release-zip.sh 4.2.2
# or with custom release notes:
scripts/dev/release-zip.sh 4.2.2 "Marketplace install flow + provider abstraction patch."
```

The script validates: (a) the version arg matches `plugin.json`, (b) a `## [X.Y.Z]` section exists in `CHANGELOG.md`, (c) working tree is clean, (d) local `main` matches `origin/main`, (e) the release tag doesn't already exist. Then it builds the distribution zip with the canonical exclude list (`.git/`, `screenshots/`, `__pycache__`, `PROGRESS.md`, `ROADMAP.md`, `tests/`, `dev-docs/`, `spikes/`, `scripts/dev/`, etc) and runs `gh release create` with the zip attached.

**NOTE: skill-only zips (`banana-skill-vX.Y.Z.zip`) are no longer built as of v3.8.4.** The plugin requires the full plugin structure to function (two skills, agents, `.claude-plugin/` manifest). Historical skill-only zips at the workspace root are archived build artifacts — do not delete.

If you ever need to bypass the script (e.g., to debug a failing pre-flight check), the underlying commands it runs are:

```bash
zip -r ../creators-studio-vX.Y.Z.zip . -x ".git/*" ".DS_Store" "*/.DS_Store" \
  "*__pycache__/*" "*.pyc" ".github/*" "screenshots/*" "PROGRESS.md" \
  "ROADMAP.md" "CODEOWNERS" "CODE_OF_CONDUCT.md" "SECURITY.md" \
  "CITATION.cff" ".gitattributes" ".gitignore" ".claude/*" "spikes/*" \
  "tests/*" "dev-docs/*" "scripts/dev/*"
gh release create vX.Y.Z ../creators-studio-vX.Y.Z.zip \
  --title "vX.Y.Z" --notes "See CHANGELOG.md for details"
```

## Plugin development notes

- `.claude-plugin/` contains ONLY `plugin.json` and `marketplace.json`. Never put skills, agents, or commands in this directory.
- `skills/` and `agents/` must be at plugin root (not inside `.claude-plugin/`).
- Plugin variable `${CLAUDE_PLUGIN_ROOT}` resolves to the plugin cache directory. Use for hook commands and MCP configs.
- SKILL.md uses `${CLAUDE_SKILL_DIR}` for script paths -- this is a semantic marker Claude interprets based on context.
- Relative paths in SKILL.md (`references/`, `scripts/`) resolve relative to SKILL.md location.
- Test locally with `claude --plugin-dir .` (loads plugin without installing).
- After changes, run `/reload-plugins` in Claude Code to pick up updates without restarting.
- Validate with `claude plugin validate .` or `/plugin validate .` before releasing.

### marketplace.json maintenance constraints (verified against the 2026 spec)

**Authoritative reference:** [https://code.claude.com/docs/en/plugin-marketplaces](https://code.claude.com/docs/en/plugin-marketplaces). Always re-fetch before making schema changes — the spec evolves.

- `owner` only allows `name` (required) and `email` (optional). Do NOT add `url`, `homepage`, or any other field — `claude plugin validate` will pass them silently today but they're not in the spec and may break.
- `metadata` only allows `description`, `version`, and `pluginRoot`. Do NOT add `homepage` (validator silently accepts but it's non-spec).
- Do NOT include `"$schema"` at the top level. The official `claude-plugins-official` repo includes it, but the validator currently rejects it (issue #9686). Once that issue is fixed and the URL serves a real schema, this rule can flip.
- Do NOT set `version` on a plugin entry inside `marketplace.json` — `plugin.json`'s `version` always wins silently, so a stale marketplace `version` would mask an updated plugin version. Single-source from `plugin.json`.
- The plugin entry's `source` should stay `"./"` for this repo. Paths resolve relative to the directory CONTAINING `.claude-plugin/`, not to `.claude-plugin/` itself — and our `.claude-plugin/marketplace.json` sits at the plugin root, so `"./"` correctly points at the plugin.
- After any marketplace.json edit, run `claude plugin validate .` from the plugin root before committing.

### Branch hygiene

- Direct pushes to `main` are blocked by the harness. Use `scripts/dev/publish.sh` for the PR flow. Direct pushes to feature branches are fine.
- Delete merged feature branches promptly. GitHub auto-deletes the remote branch on merge (Settings → General → "Automatically delete head branches" is enabled). Locally, run `git checkout main && git pull && git branch -D <feature-branch>`.
- The `commit-commands:clean_gone` skill cleans up any local branch whose remote tracking branch has been deleted (`[gone]` status). Use it whenever the local branch list grows beyond `main`.
- Multi-commit feature branches that go through squash-merge: wait 24-72 hours after merge before deleting locally — the squashed commit on main loses the granular sub-commit history, and the feature branch is the only local copy.
