# Session Handoff - 2026-07-23 - /create-transcript skill

**Previous handoff:** none (first handoff for this stream).
**State verified as of:** 2026-07-23, session `6348c586-38bd-496b-bf86-cae687696e3b`, checked against `git log`/`git status`, the GitHub PR list, the marketplace cache, and the delivered files on disk.

## Goal

Give the `creators-studio` plugin a speech-to-text capability (its first ingest feature) so downloaded videos can be transcribed with the plugin Julian already owns, instead of ad-hoc external tooling. Then extend it per Julian's follow-ups (per-video keyterm control, descriptive file/heading titles).

## State (verified)

**Everything is SHIPPED and MERGED to `main`. Nothing is pending, no WIP, no open PRs.**

- Repo: `~/code/creators-studio-project/creators-studio` (this is THE git repo). The parent `creators-studio-project/` is a workspace folder, NOT a git repo.
- Branch `main`, in sync with `origin/main`, working tree clean (only untracked file is `docs/dev-notes/2026-06-05-create-video-field-gaps.md`, a pre-existing note from another session - leave it).
- Version **4.5.0** (`.claude-plugin/plugin.json`, README badge, `CITATION.cff`, `transcribe.py` USER_AGENT all consistent).
- Test suite: **222 tests, all passing, all offline** (`python3 -m unittest discover tests`).
- Five PRs merged this session (newest first):
  - `#13` 01f8323 - descriptive titles (retitle + --title), v4.5.0
  - `#12` c98b05f - keyterm sets, v4.4.0
  - `#11` 5c61126 - repo-wide em/en dash cleanup + publish.sh trailer + .omc gitignore
  - `#10` 1f17376 - the /create-transcript skill (Scribe v2), v4.3.0
  - `#9` 05e156a - the design spec (docs)

**Installed plugin:** the marketplace cache at `~/.claude/plugins/cache/outfit/creators-studio/` now contains `4.2.3`, `4.4.0`, AND `4.5.0` dirs, so it caught up to source during the session. A FRESH session should therefore surface `/create-transcript` (and `creators-studio:create-transcript`) as a live command - the session-start available-skills list only listed create-image/create-video because it was captured before the cache refreshed. **Verify at next session start**; if the command is missing, update the installed plugin.

**Delivered transcripts** (real output, on disk at `~/Downloads/12_Existing_Project_Folders/PullTube/transcripts/`), descriptively renamed with the video name kept at the end, H1s matching:
- `Design Videos in Reverse From the Comment Section - Video by adley - 1280p.{md,srt,vtt,json}`
- `Do Not Make Customers Think - StoryBrand Clarity - Video by storybrand - 1280p.{md,json}`
- `Three Rules For Every Sentence - Harry Dry - Video by davidperell - 1436p.{md,json}`
- `Writing Simply Is Rewriting - Harry Dry - Video by davidperell - 1436p 1.{md,json}`
(These 4 were made/renamed before the retitle feature, so their JSON lacks `_title`/`_source_name`; H1s were hand-edited. Fine as delivered; if ever re-titled via the tool, pass `--source-name`.)

## What the skill does (quick map)

- `skills/create-transcript/scripts/transcribe.py` - CLI. Subcommands: `transcribe`, `rename` (speakers), `retitle` (title), `cost`, `status`. Reuses the ElevenLabs key at `~/.creators-studio/config.json`.
- `skills/create-transcript/scripts/formats.py` - PURE renderers (md/srt/vtt/chapters/txt), no network/fs. The core testable unit.
- Core principle: **one API call per file**; the raw Scribe JSON is cached and every format (and every rename/retitle/added-format) re-renders from that cache with no re-charge.
- Registry: `scribe-v2` in `scripts/registry/models.json`, `transcription` family, `mode: subscription, rate: null` (no fabricated price).

## Decisions (final; these supersede options discussed along the way)

- **New top-level skill**, not a `/create-video` subcommand. Reason: discoverability + create-video SKILL.md is already at a size ceiling.
- **`scribe_v2` batch only.** Realtime (`scribe_v2_realtime`) rejected - it is a live-audio WebSocket transport, irrelevant to files on disk.
- **No hardcoded price.** Registry + cost tracker treat Scribe as `subscription`/`rate: null`; `cost` reports audio-minutes. Rejected inventing a per-minute rate (the pinned docs only link out).
- **Keyterm SETS (per-video)** over a flat always-on list. Julian chose this to keep the +20% keyterm surcharge (and irrelevant bias) off videos that do not need it. Rejected: a flat standing `keyterms` list (hits every run) and a `--no-keyterms` off-switch (less flexible than named sets).
- **Descriptive titles via `retitle`** (H1 + `<title> - <video>` filename), video name kept at the end for search. `_title`/`_source_name` persisted so re-runs are idempotent.
- **Em/en dash cleanup was mechanical** (`" - "` substitution, numeric ranges to tight hyphen) but **PRESERVED `slides.py:91`'s `[—–-]` regex char class** and **EXCLUDED `tests/fixtures/*.json`** (captured real data). See dev-note.
- Publish trailer set to `Claude Opus 4.8`; `.omc/` added to `.gitignore`.

## Tried and failed (do not rediscover)

- Proving `rename`/`retitle` make no network call by monkeypatching `socket.socket` to raise - it breaks `ssl` at import time. Abandoned. Verify "no network" by patching `transcribe.urllib.request.urlopen` in tests, or by code path + sub-100ms timing.
- Shell dash detection with `grep $'—\|–'` is unreliable (quoting) - it falsely reported "NONE". Use a Python scan (`text.count('—')+text.count('–')`) instead.

## Julian's feedback / preferences (this session)

- Wanted the plugin he owns used, not external tooling: "use the latest scribe version two engine through the creators studio plugin".
- On keyterms: "how do I manage the keyterms to only be activated on specific videos" -> chose **named keyterm sets**.
- On filenames: "add to the front of the file names a better title description of what the transcript is and still leave the video file name at the end for reference and search."
- On headings: "Update each transcript's H1 heading to match - then update the skill to do that every time."
- Gated every merge explicitly ("merge #9", "merge #12", etc.) - never merge unasked.

## Recipes and footguns

- **Run the tests:** `cd <repo> && python3 -m unittest discover tests` (222, offline).
- **Open a PR:** `bash scripts/dev/publish.sh "type: title" "body"` from the repo root. It branches off `main`, `git add -u` (TRACKED files only - `git add` any NEW files explicitly first), commits with the Opus 4.8 trailer, pushes, opens the PR, and rolls local `main` back to `origin/main`. It leaves you ON the feature branch - `git checkout main` after.
- **Direct pushes to `main` are blocked** by the harness rail; everything lands via PR.
- **Cost ledger pollution:** `transcribe.py` logs each real transcription to `~/.creators-studio/costs.json` (shared "generations" ledger, like video/music). Test runs that call `cost_tracker.py log --model scribe-v2` write real entries - clean up any `scribe-v2` test entries afterward (a `.bak` is safe to make first).
- **Live-verify multipart:** unit tests with a patched socket cannot prove the real API accepts the hand-built multipart body (esp. repeated `keyterms` fields). One real short transcription is the only proof.
- **retitle on pre-4.5.0 caches:** those JSONs lack `_source_name`; pass `--source-name "Video ....webm"` or the title prefix can double on re-runs.
- **Future dash/punctuation sweep:** `slides.py:91` uses `[—–-]` as a functional separator matcher - it is the ONLY em/en dash left in the repo by design. Any mass punctuation edit MUST preserve it (and exclude `tests/fixtures/`). See `docs/dev-notes/2026-07-23-transcript-titles-and-dash-sweep.md`.

## Open work (ranked)

1. **(Julian, quick)** In a fresh session, confirm `/create-transcript` is a live command (cache now has 4.5.0). If missing, update the installed plugin from the marketplace.
2. **(Julian, quick)** Add the dental/agency `keyterm_sets` to `~/.creators-studio/config.json` (ready-to-paste seed in `skills/create-transcript/references/keyterms.md`). Until then keyterms only apply when passed ad-hoc.
3. **(optional)** Commit this handoff + the new dev-note via a small docs PR (both are currently untracked; `main` is protected so they need a PR to land).
4. **(optional)** Cut a GitHub Release + distribution zip for 4.5.0 via `scripts/dev/release-zip.sh 4.5.0` if distributing beyond `main`.

## Questions for Julian

1. Distribute 4.5.0 (GitHub Release / marketplace), or leave it on `main`?
2. Want the handoff + dev-note committed (docs PR), or left as local working-tree notes?

---

## Next-session kickoff prompt

> Working in `~/code/creators-studio-project/creators-studio` - THE git repo for the `creators-studio` Claude Code plugin. The parent `~/code/creators-studio-project/` is a workspace folder, not a repo.
>
> READ FIRST, in this order, and treat them over any assumption:
> 1. `docs/SESSION-HANDOFF-2026-07-23.md` (this handoff)
> 2. `CLAUDE.md` (repo dev rules, file responsibilities, Feature Completion Checklist)
> 3. `PROGRESS.md` (session history; latest is Session 29)
> 4. `docs/dev-notes/2026-07-23-transcript-titles-and-dash-sweep.md` (footguns)
>
> State (verified 2026-07-23, session 6348c586): `main` is clean and synced with `origin/main` at v4.5.0; PRs #9-#13 all merged; 0 open PRs; 222 tests pass (`python3 -m unittest discover tests`). The `/create-transcript` skill is DONE (Scribe v2 transcription, keyterm sets, descriptive titles). Untracked in the working tree: this handoff, the dated dev-note, and `docs/dev-notes/2026-06-05-create-video-field-gaps.md`.
>
> DO NOT TOUCH: `docs/dev-notes/2026-06-05-create-video-field-gaps.md` (another session's note). Don't re-audit the merged create-transcript work - it is trusted and done.
>
> FIRST ACTIONS:
> 1. Confirm `/create-transcript` is a live command (the marketplace cache now has 4.5.0). If missing, update the installed plugin.
> 2. If Julian wants keyterms active, add the dental/agency `keyterm_sets` from `skills/create-transcript/references/keyterms.md` into `~/.creators-studio/config.json`.
>
> Standing rules: land everything via `scripts/dev/publish.sh` PRs (direct pushes to `main` are blocked); never push/merge unasked; verify against the live rendered artifact, never a status line; Sonnet subagents for any fan-out; house formatting = no em/en dashes, no colons in headings (use " - "), straight quotes.

