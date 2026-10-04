# GNOSIS — engineering review (discovery, baseline, risks, plan)

Written before any change of this pass; the changes made since are listed
at the end. ARCHITECTURE.md is the living description of the system; this
file is the record of the review.

## 1. System model

**Shape.** One Streamlit 1.64 app (`streamlit_app.py` → `st.App` with the
sign-in routes → `gnosis.py`, run on every interaction), 47 modules, ~13,400
lines. Two modes: *public* (Supabase Auth + Postgres with row-level
security, Groq for the model) and *personal* (a password, local JSON files).

**A run (every click).** `coach.freshen()` (reload modules if new code is on
disk) → style → the gate (`auth.gate` / `ui.require_password`) →
`ui.init_state()` (records and settings loaded once per session) →
`ui.refresh_settings()` (settings as stored now) → a daily "visit" count →
the page list → today's entry re-read (`ui.refresh_entry`) → top bar,
sidebar → the page.

**A lesson (the main write path).** Today → *Start this lesson* →
`daily.run_kickoff` → `core.build_system_prompt` → `llm.stream_reply`
(quota, pacing, retries) → `ui.save_day` → `curriculum.merge_day` (written
into the day as stored now; a lesson never moves back) → `storage.save_entry`
(upsert one row) → rerun. Quizzes (`quizgen` → `quiz`), review cards
(`review`), reading (`reading`/`books`) and goals (`goalmaker`/`paths`) follow
the same pattern: a view orchestrates, pure modules decide, `ui.save_*`
persists through one of two stores.

**Layers (measured: imports).**

| Layer | Modules | Fan-in (most used) |
|---|---|---|
| Pages | `views/*` (9) | — |
| UI helpers | `ui` (17), `sidebar`, `topnav`, `place`, `style`, `motion`, `glass`, `progress_bar`, `rolling`, `lesson_view`, `choices`, `stage`, `visuals`, `goalmaker` | `ui` 17 |
| Domain (pure) | `core` (16), `catalog` (16), `settings` (15), `curriculum` (10), `review`, `quiz`, `paths`, `course`, `history`, `search`, `books`, `steps`, `placement`, `metrics`, `plans` | |
| AI | `llm`, `quizgen`, `quota`, `tokens`, `prompts/` | |
| Data / auth | `storage`, `auth`, `supa_auth`, `session_cookie`, `routes` | |

No import cycles at module level. Three deferred imports break would-be
cycles (`core`↔`catalog`, `curriculum`→`catalog`/`review`); they are
deliberate and commented.

**State.** 73 `st.session_state` keys. Persisted state has one owner each:
her records `coach_log` (entries, books, goals) and settings
`coach_settings`, written only through `ui.save_entry / save_day /
save_book / save_path / save_settings`. The store is the source of truth;
the session holds a copy re-read where another tab may have changed it
(today's entry and the settings every run, the whole record on arriving at
Progress). Page state uses a per-page prefix (`ob_`, `set_`, `prog_`, `rv_`,
`book_`, `goal_`, `auth_`).

**Data.** Supabase tables: `learning_entries` (user, date, topic → JSON
lessons), `user_settings`, `reading_books`, `learning_paths`, `ai_usage`,
`usage_events`, `allowed_users`, `app_admins`, `users`. Every row is read
and written as the signed-in user (RLS); counters only through
security-definer functions. Both stores implement the same 22 operations.
Saves are upserts; a day is merged, never overwritten from an old copy.

## 2. Baseline (before this pass)

- `tools/check.sh`: 574 unit/page tests pass; feature inventory 228/228.
- Browser suite (`tests/e2e`, 214 tests, 1 h 36 min): 209 pass. The 5
  failures were the suite's own: a test still expecting the pre-goal
  wording ("Keep at least one subject.") and the Progress visual baseline
  predating a test-data fix (old lessons now show their review cards).
  Both corrected; the rerun of the affected files passes.
- Lint (pyflakes): app code clean; 10 unused imports in tests and tools.
- Page compute time (local store, 20 days of history): 28–73 ms a page.
  The cost of a click is the database: two small reads a run (settings,
  today's entry), more on Progress.

## 3. Risk register (found in discovery)

| # | Risk | Evidence | Severity |
|---|---|---|---|
| R1 | **No single clock.** "Today" and "now" are computed in six places (`ui.today`, `books._local_today` with its own timezone read, `settings.now_iso`, `paths.now_iso`, `storage._now`, `storage` inline). The test clock moves only two of them, so books and goals keep the real date under a moved clock; a future timezone change must be made in two places. | `grep datetime.now` | Medium |
| R2 | **Configuration lives in the UI module.** `get_setting` and `TIMEZONE` are in `ui`, so the auth and data modules (`auth`, `supa_auth`, `session_cookie`, `quota`) import the UI helper module to read a secret. | import graph | Medium (coupling) |
| R3 | **A database blip fails a read outright.** Every run makes two reads; one dropped connection or a 502/503/504 shows an error (or, at sign-in, stops the page) though the same read a moment later would work. Reads are safe to repeat; writes are not all (the usage counter). | `storage._request` | Medium |
| R4 | **Logs can't be tied to one session.** An error in the log has no way to tell which session (or which of a person's actions) it came from. | log census | Medium (operability) |
| R5 | **A silent `except Exception: pass`** where the password gate notes the page asked for. | `ui.require_password` | Low |
| R6 | Unused imports in tests/tools. | pyflakes | Low |

Checked and found sound (no change): duplicate actions (design, kickoff,
quiz: guarded by saved state and signatures), concurrent saves (merge on
write), secrets (never logged; publishable key only; the secret key is
refused), escaping of user and AI text, RLS and security-definer functions,
timeouts on every network call, the model's retries and pacing.

Not changed on purpose: `style.py` (2,100 lines of CSS: large but one
concern, covered by screenshots), `views/daily.py` (the page orchestrates;
its rules already live in `curriculum`, `quiz`, `review`, `steps`), the
two-store design.

## 4. Plan (each step small, verified, then the next)

1. One clock (`coach/clock.py`): the learner's timezone, `today()`,
   `now_iso()`; every module reads time from it; the test clock patches one
   place. (R1)
2. Configuration out of the UI (`coach/config.py`: `get_setting`); the
   auth, data and quota modules stop importing `ui`. (R2)
3. Reads retried once on a transient failure; writes never. (R3)
4. A session tag on every log line (a short, anonymous id). (R4)
5. Narrow the silent catch; remove unused imports. (R5, R6)
6. Hostile review, user flows in a browser, docs.

## 5. Changes made (each verified by the full check, then committed)

| Step | Change | Verified by |
|---|---|---|
| R1 | `coach/clock.py`: every date and timestamp; the test clock patches it alone | `tests/test_clock.py` (fails on the old code: six separate clocks) |
| R2 | `coach/appconfig.py`: settings read without the UI module; a malformed secrets file now surfaces | `tests/test_layers.py` |
| R3 | A read retried once on a dropped connection or 502/503/504; writes never; 4xx/500 never | `tests/test_storage.py` (blip, persistent failure, write, refusal) |
| R4 | `[sid]` session tag on every log line | `tests/test_logging.py` |
| R5 | No silent catch at the password gate; sign-in reads catch Streamlit's own errors only | page tests |
| R6 | Unused imports removed | pyflakes clean |
| Review | Setup finishes onto the stored settings (as every settings save does); admin status never cached as "no" before the store exists | page and account tests |
