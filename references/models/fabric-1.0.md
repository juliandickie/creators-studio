# VEED Fabric 1.0 (canonical model ID: `fabric-1.0`)

**Hosting providers:** Replicate (`veed/fabric-1.0`).

**Registry entry:** `scripts/registry/models.json` → `models.fabric-1.0`

## What it does

Audio-driven lip-sync. Input: one image + one audio file. Output: the image's face lip-synced to the audio. Mouth region ONLY — no body animation, no camera movement, no emotional direction beyond audio prosody.

## Why the plugin has it

Closes the gap where Kling doesn't accept external audio input — custom-designed ElevenLabs voices from `audio_pipeline.py narrate` had no way to reach a visible character's face. Fabric pairs the two.

## Canonical constraints

- `resolution` ∈ {`480p`, `720p`} (no 1080p or 4K)
- `duration_s` ≤ 60 (driven by audio length)
- `image` formats: jpg, jpeg, png
- `audio` formats: mp3, wav, m4a, aac

## Pricing

`per_second_by_resolution` mode — **480p is ~47% cheaper than 720p**:

| Resolution | Rate | 7s clip | 8s clip | 60s clip (max) |
|---|---|---|---|---|
| **480p** | `$0.08`/s | $0.56 | $0.64 | $4.80 |
| **720p** | `$0.15`/s | $1.05 | $1.20 | $9.00 |

Cold-start adds ~36s wall time on the first call of a batch but NOT cost — Replicate bills Fabric on output duration, not GPU wall time.

**Source:** Replicate's official Fabric 1.0 model card (verified 2026-04-27). The 720p rate was also empirically verified in v3.8.1 via three runs on 2026-04-15 (see "Empirical verification" below). The 480p rate was assumed equal in v3.8.1; the 2026-04-27 pricing patch corrects it.

**Comparisons (720p):** Fabric at `$0.15`/s is ~7.5× more expensive per second than Kling v3 ($0.02/s) and ~3× more expensive per second than VEO Lite at 720p ($0.05/s). At 480p, Fabric closes the gap to VEO Lite (`$0.08`/s vs `$0.05`/s) but still costs more — Fabric remains a premium, not a discount. Justified only when you need a custom-designed ElevenLabs voice paired with a visible face — Kling and VEO can't do that.

**Cost-tracker integration:** `video_lipsync.py` automatically shells out to `cost_tracker.py log` after every successful run, passing the actual resolution and output duration. The cost ledger at `~/.creators-studio/costs.json` will reflect the correct rate per call.

## Canonical 2-step workflow

```
audio_pipeline.py narrate --voice brand_voice --out /tmp/narr.mp3
  → video_lipsync.py --image face.png --audio /tmp/narr.mp3
```

## Empirical verification

**720p runs** (2026-04-15, three successful predictions, all $0.15/s):
- `w36styf3c9rmw0cxj3cbyvnxz8` — 8s @ 720p, $1.20, cold start
- `j3qp5ndaanrmr0cxj4qrnrhhf4` — 7s @ 720p, $1.05, warm
- `55qej5ghs1rmw0cxj4wr1wjgdg` — 7s @ 720p, $1.05, warm

**480p**: not yet empirically verified by this project. Rate is canonical from Replicate's official model card (`replicate.com/veed/fabric-1.0` → "Pricing" section, 2026-04-27). A future verification run is a useful follow-up but not blocking — the rate is authoritative from the source.

## Authoritative source

`dev-docs/veed-fabric-1.0-llms.md` (full model card) plus the live pricing block at https://replicate.com/veed/fabric-1.0 (re-fetch on every Fabric pricing review — Replicate occasionally adjusts rates).
