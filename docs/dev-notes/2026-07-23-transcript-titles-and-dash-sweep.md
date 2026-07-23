# Transcript titles + repo-wide dash sweep - learnings - 2026-07-23

Additive notes from the session that built `/create-transcript` (v4.3.0), keyterm sets (v4.4.0), and descriptive titles (v4.5.0), plus a repo-wide em/en dash cleanup. Same observation / why-it-matters / fix shape as the other dev-notes here. None are blockers - all the work shipped - but each cost a step a future session would also pay.

---

## 1. A future punctuation sweep will re-break `slides.py:91` (P1)

Observation. `skills/create-image/scripts/slides.py` line 91 parses slide headers with `pattern = r'##\s+Slide\s+(\S+)\s*[—–-]\s*(.+?)\n...'`. That `[—–-]` character class INTENTIONALLY matches em dash, en dash, OR hyphen as the title separator, so users' slide files keep parsing regardless of which dash they typed. After the v4.5.0 dash cleanup it is the **only** em/en dash left in the entire repo, on purpose.

Why it matters. Any future "clean up the dashes" or "normalise punctuation" mass-edit that blindly replaces `—`/`–` will corrupt this regex (turn `[—–-]` into `[-]` or worse), silently breaking slide parsing for any user file that uses an em/en dash separator. A blind `sed` would have done exactly this.

Fix / how it was handled. The cleanup script protected this line explicitly and excluded it from the transform. Before any future punctuation sweep: (a) grep for em/en dashes inside regex character classes `\[[^\]]*[—–][^\]]*\]` and inside `.split(/.replace(/re.*(...)` calls across `*.py *.sh *.js` and preserve those lines; (b) exclude `tests/fixtures/*.json` (captured real API responses - rewriting them makes the fixtures dishonest); (c) verify with the full test suite + `py_compile` + JSON-validate afterward; (d) detect residual dashes with a Python `text.count('—')+text.count('–')` scan, NOT a shell `grep $'—\|–'` (the shell quoting is unreliable and gave false "NONE").

---

## 2. The marketplace cache lags the source repo (P2)

Observation. Work happens in the source repo (`~/code/creators-studio-project/creators-studio`), but the plugin Julian actually runs is the installed marketplace copy at `~/.claude/plugins/cache/outfit/creators-studio/<version>/`. During this session the cache went from only `4.2.3` to holding `4.2.3`, `4.4.0`, and `4.5.0` - i.e. it refreshed on its own, but the session's available-skills list (captured at start) still only showed create-image/create-video, so `/create-transcript` was NOT invocable as a live command mid-session even though it was merged to `main`.

Why it matters. "It's merged" is not the same as "it's a live command." A new source skill only becomes a `/command` after the installed plugin catches up AND a fresh session loads it. When a user asks to "use the skill," run the source `transcribe.py` directly until a new session confirms the installed command exists.

Fix / how to check. At session start, look for `creators-studio:create-transcript` in the available-skills list, or check the cache: `ls ~/.claude/plugins/cache/outfit/creators-studio/`. Running the CLI from source (`python3 skills/create-transcript/scripts/transcribe.py ...`) always works regardless of installed version.

---

## 3. `transcribe.py` cost logging writes to the REAL ledger (P3)

Observation. `transcribe_file` calls `log_cost()`, which shells out to `cost_tracker.py log --model scribe-v2 ...`, writing a real entry to `~/.creators-studio/costs.json` (the shared "generations" ledger - video and music log there too, despite the `total_images` field name). Testing the skill (including a bare `cost_tracker.py log` smoke) pollutes Julian's real ledger.

Why it matters. Manual test runs left two phantom `scribe-v2` entries (one with a bogus `$0.039` from before the subscription pricing branch existed) that inflated `total_images` and `total_cost`.

Fix / how it was handled. `scribe-v2` is registered `{"subscription": True}` in `cost_tracker.PRICING` with an early `if model_pricing.get("subscription"): return 0.0` branch (logs 0.0 marginal cost, no unknown-model fallback). After manual testing, remove test `scribe-v2` entries and recompute totals from the surviving entries (make a `.bak` first). The existing `TestCostLoggingSmoke` avoids this by pointing `HOME` at a temp dir - do the same in any new ledger-writing test.

---

## 4. Descriptive-title idempotency depends on `_source_name` (P3)

Observation. `retitle` (v4.5.0) renames outputs to `<title> - <source stem>.<ext>` and re-derives the source stem from `data["_source_name"]` stored in the cache at transcribe time, NOT from the current (possibly already-prefixed) filename. That is what keeps re-titling idempotent (no `Second - First - Video...` stacking).

Why it matters. Caches produced BEFORE v4.5.0 (including the 4 clips delivered this session) have no `_source_name`; retitling them via the tool would fall back to the current stem and double-prefix. The delivered files' H1s were hand-edited instead.

Fix. For a pre-4.5.0 cache, pass `retitle --source-name "Video ....webm"`. New transcriptions always store `_source_name`, so this only affects legacy caches.
