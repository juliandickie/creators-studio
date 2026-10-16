# Session Handoff - 2026-10-16 - /create-audio and the watch subcommand

**Previous handoff:** [SESSION-HANDOFF-2026-07-23.md](SESSION-HANDOFF-2026-07-23.md), the newest on `main`. A later one, `SESSION-HANDOFF-2026-07-27.md`, exists only on the local branch `docs/session-handoff-2026-07-27` (commit `cc9f2e1`, never pushed or merged), checked out detached in `.claude/worktrees/competent-elion-15e3fd`. That is another session's work and was not touched. See question 1.
**State verified as of:** 2026-10-16 14:00 AEST, session `897ecc59-4b3d-4558-b6fd-dc803957a33e`, checked against `git log`, `git status`, the GitHub releases and a full test run (269 tests, OK).

**In flight at close: nothing.** v4.7.0 and v4.8.0 are merged, tagged and released. This handoff lands as its own docs PR.

## Goal

Fewer plugins loaded at once. The third-party `watch` plugin is folded into creators-studio as a subcommand of `/create-transcript`, and the plugin gains audio-only generation (music and sound effects) as a new `/create-audio` skill.

## State (verified)

- **`main` is `6a31ebd`** (PR #22, v4.8.0), after `6b4ef3d` (PR #21, v4.7.0). Both are GitHub Releases with their zips.
- **v4.7.0, `/create-audio`.** A new skill for music, sound effects, narration, voices and mixing. It calls `skills/create-video/scripts/audio_pipeline.py`, which gained `generate_sfx()` and an `sfx` subcommand (ElevenLabs `POST /v1/sound-generation`, model `eleven_text_to_sound_v2`, 0.5 to 30 s, `prompt_influence` 0 to 1, default 0.3, optional loop). Tested live: a 2.000 s stereo file, peak -2.6 dB. 3 new tests in `tests/test_sfx.py`.
- **v4.8.0, `/create-transcript watch`.** `skills/create-transcript/scripts/watch.py` (567 lines, MIT notice for Bradley Bonanno's claude-video in the header) gives frames plus a Scribe transcript for a file or URL. Scene detection at 0.20 with a uniform fallback, even sampling to a cap of 100, 16x16 near-duplicate removal, cue frames, and a focus range with `--start` and `--end`. URLs download with yt-dlp (720p cap) to `~/Documents/creators_watch/<sha1(url)[:10]>/`. A cached Scribe JSON is reused when its source name and model match. 13 new tests in `tests/test_watch.py`. Tested on four inputs: a local clip with a cached transcript, a focus range with cue frames, a YouTube URL (fresh, then reused) and a silent 12-cut video.
- **The release script.** `scripts/dev/release-zip.sh` now excludes `.git`. In a worktree `.git` is a pointer file, and the 4.7.0 zip shipped it until it was stripped and re-uploaded.
- **Outside this repo.** The `watch` entry is removed from the outfit marketplace (`outfit` main `331f421`), the third-party plugin is uninstalled, and the interim `/watch` rule in `~/.claude/CLAUDE.md` is deleted.
- **Not ours, left alone.** The untracked `docs/dev-notes/2026-06-05-create-video-field-gaps.md` in the main checkout, and the `competent-elion-15e3fd` worktree.
- **This session's handoff** is on branch `docs/session-handoff-2026-10-16`. It also corrects the test count in `CLAUDE.md` (247 to 269).

## Decisions (final)

- **A new `/create-audio` skill**, not more flags on `/create-video` (Julian, the recommended option). Audio-only work gets its own entry point. The engine stays in `create-video/scripts/audio_pipeline.py`, so there is one audio code path.
- **`watch` is a subcommand of `/create-transcript`**, not a separate skill (Julian, the recommended option). It loads no extra skill.
- **Stdlib only, as everywhere in the plugin.** ffmpeg is required; yt-dlp only for URLs, reported by `transcribe.py status`.
- **Rejected.** Keeping the third-party `watch` plugin beside a CLAUDE.md rule. That was the interim step, and it is gone.

## Tried and failed (do not rediscover)

- **The auto-mode classifier blocks `gh pr merge`** as a merge without review. It went through once Julian wrote "Merge PR 21" in chat. Ask for the go in words.
- **zsh eats `$i:v`** as a colon modifier. Use `"${i}:v"` or Python.
- **A substring edit of `marketplace.json` failed the JSON check** on an inner `},`. Edit it line by line and re-parse.

## Julian's feedback (this session)

- "I am trying to minimise loading too many skills and plugins all the time." This is the reason for the fold-in.
- He needed audio only (music or sound effects) for a recent job, which is the reason for `/create-audio`.

## Recipes and footguns

- Tests, from the plugin root: `python3 -m unittest discover tests`. 269, no network.
- A sound effect: `python3 skills/create-video/scripts/audio_pipeline.py sfx --prompt "soft whoosh" --duration 2`.
- Watch: `python3 skills/create-transcript/scripts/transcribe.py watch "<file or URL>" [--keyterms "..."] [--start T --end T]`.
- **Release from a clean worktree of `main`**, never the main checkout: `scripts/dev/release-zip.sh <version>`. It zips the current folder and refuses a dirty tree.
- **Direct pushes to `main` are blocked**, and `validate` (seven gates) is a required check. Everything goes through a PR.
- **The desktop app can load the claude.ai account copy of a plugin** and miss a local update. Check what actually loaded before trusting a new skill.

## Open work (ranked)

1. **Restart Claude and confirm `/create-audio` and the `watch` subcommand appear**, in the CLI and the desktop app.
2. **Fill the v4.6.0 docs gaps.** No PROGRESS session, no ROADMAP row and no README release entry for v4.6.0 (the CHANGELOG is complete).
3. **`transcribe.py` `USER_AGENT` still says 4.5.0** (line 57). Bump it, or read it from `plugin.json`.
4. **Re-test `music` and `narrate`** in `audio_pipeline.py`. Only `sfx` was run live after the change.
5. **`watch` has no cookies or login support.** Login-only videos need PullTube or a manual download first.

The test download in `~/Documents/creators_watch/14fc847748` is already gone; the folder was empty at close.

## Questions for Julian

1. **The unmerged 27 July handoff branch.** `docs/session-handoff-2026-07-27` adds a handoff, a CI dev-note and a "Session 30" PROGRESS entry, and `main` now has its own Session 30 (15 October). Merge it with a renumber, archive it, or leave it?
2. **Cookies for `watch`.** Add a `--cookies-from-browser` option, or keep login-only videos on PullTube?

## Next-session kickoff prompt

```
Working directory: ~/code/creators-studio-project/creators-studio (the plugin repo, nested in
creators-studio-project, which is not in git). Work in a new worktree off origin/main under
.claude/worktrees/.

READ FIRST, in order, and treat these over any assumption:
1. docs/SESSION-HANDOFF-2026-10-16.md
2. CLAUDE.md (dev rules, file responsibilities, release checklist)
3. PROGRESS.md, the Session 30 entries

STATE, verified as of 2026-10-16 14:00 AEST: main 6a31ebd, v4.8.0 released (v4.7.0 before it).
/create-audio and /create-transcript watch shipped, 269 tests OK. Check with git log before trusting this.

DO NOT TOUCH: the untracked docs/dev-notes/2026-06-05-create-video-field-gaps.md, the
competent-elion-15e3fd worktree and the docs/session-handoff-2026-07-27 branch. Another session's work.

RULES: verify by running the real command and looking at the output, never a status line. Every
change through a PR, validate must be green. Never merge or release without Julian's go in words.
Stdlib only. No em or en dashes, straight quotes.

FIRST ACTION: confirm /create-audio and the watch subcommand load, then ask Julian the two questions
in the handoff and work the open list from item 2.
```
