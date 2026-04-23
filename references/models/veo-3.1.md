# Google VEO 3.1 (canonical model IDs: `veo-3.1-lite` / `veo-3.1-fast` / `veo-3.1`)

**Status:** Registered but NOT the default. VEO 3.1 remains opt-in backup via `--provider replicate --model veo-3.1-lite` (or `-fast`, standard). Per v3.8.0 spike 5 findings, Kling v3 wins 8 of 15 shot types to VEO Fast's 0, at 7.5× lower cost.

**Hosting providers (once sub-project B lands):** Replicate (`google/veo-3.1-lite`, `google/veo-3.1-fast`, `google/veo-3.1`). Vertex AI also hosts VEO but that path is being retired in sub-project B.

## Status in sub-project A

VEO entries are **NOT seeded in `models.json` during sub-project A.** That migration happens in sub-project B (Vertex retirement) when VEO callers are routed through `_replicate.py` instead of `_vertex_backend.py`.

Users who currently call VEO via the `--provider veo` flow continue working via the legacy path until sub-project B ships.

## Authoritative sources

- `skills/create-video/references/veo-models.md` (existing — current content source)
- Sub-project B plan (forthcoming): `docs/superpowers/plans/2026-MM-DD-subproject-b-vertex-retirement.md`
