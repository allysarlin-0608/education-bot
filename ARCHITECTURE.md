# GNOSIS — architecture

A daily learning coach: one subject a day, a few short lessons, a quiz to
pass each one, spaced review of what was learnt, a reading plan, and a
record of every day. Streamlit app, Supabase for accounts and data, Groq for
the model.

## Layers

| Layer | Where | Does | Must not |
|---|---|---|---|
| Entry | `streamlit_app.py`, `gnosis.py` | `st.App` with the sign-in routes; every run: `coach.freshen()`, style, the gate (password or account), the page list | hold logic of its own |
| Pages (UI) | `views/*.py` | draw one page from the session's data; call domain functions; save through `coach.ui` | talk to Supabase or Groq directly; compute progress |
| UI helpers | `coach/ui.py`, `topnav.py`, `sidebar.py`, `place.py`, `style.py`, `motion.py`, `glass.py`, `lesson_view.py` | session state, navigation, the dock, CSS, shared widgets | decide what counts as studied, passed or due |
| Domain | `core.py`, `curriculum.py`, `course.py`, `review.py`, `quiz.py`, `steps.py`, `history.py`, `search.py`, `reading.py`, `books.py`, `settings.py`, `placement.py` | pure functions over the log, the syllabus and the settings: what today is, what's next, streaks, review cards, the course map | do I/O (they are unit-tested without a store) |
| AI | `llm.py`, `quizgen.py`, `quota.py`, `prompts/`, `system_prompt.md` | every model call: lessons, quizzes (with checking and repair), chat; per-minute pacing; the daily allowance | run without counting toward the allowance |
| Data | `storage.py` (file store and Supabase store), `supa_auth.py`, `auth.py`, `session_cookie.py`, `routes.py` | read/write entries, books, settings, usage; sign-in, sessions, invites | trust anything the browser sends without the signed-in user's token |
| Schema | `supabase/*.sql` | tables, row-level security, the usage function | be changed without the owner's approval |

## Data

- **learning_entries**: one row per (user, date, subject). `lessons` is a
  JSON list of slots: `{n, title, unit, lesson, quiz, followups, completed,
  cards}`. A lesson carried to a later day leaves a link slot
  `{n, from, completed}` with no content; the original gets `passed_on`.
  Review cards live in the slot (`cards`); cards for lessons from before the
  review system are worked out from the record (`review.LEGACY_FROM`) and
  stored only when acted on.
- **user_settings**: subjects, lessons per day, levels, reading on/off,
  onboarding. A day already started keeps its subject when subjects change
  (the new turns start tomorrow); a new pace reshapes today's remaining
  lessons at once and saves the day (`ui.refit_today`).
- **reading_books**, **ai_usage**, **allowed_users** (invites), **app_admins**.
- Row-level security: every table is read and written only as the signed-in
  user; `ai_usage` only grows (a security-definer function adds to it).
- Personal mode (no Supabase) keeps the same shapes in local JSON files.

## A run

1. `coach.freshen()`: if any `coach/*.py` file is newer than the loaded
   module, reload every app module (BUG-030: an update that arrived while
   nobody was connected left new pages on old modules).
2. `style.inject()`; the gate: the app password (personal) or the account
   session cookie and the invite list (public).
3. `ui.init_state()` loads the log and settings once per session (keyed by
   the user and `coach.GENERATION`).
4. `st.navigation(..., position="hidden")` runs the page; the top bar is our
   own (`topnav.py`), the chat dock is placed by `place.py`.

Pages never create a day's entry by being viewed: only actions (start,
answer, pass, save thoughts) call `day_entry()` (ISS-003), and a start that
fails leaves nothing behind (a never-saved day with nothing done is dropped
on the next run, ISS-022). Every save writes one entry onto what is stored
now; each run first re-reads today (gnosis.py), Today also each day a
carried lesson began. Lesson saves are merges, not overwrites: a day is
written into the day as stored now (`ui.save_day` → `curriculum.merge_day`),
a lesson never moves back (`progress_of`), stored review cards win. A day a
save failed on is kept as it is (not re-read) until a save succeeds.

One definition per number, in `core`: a day studied (any entry), a day
completed (every entry that day completed), lessons passed (`lessons_in`),
a streak day (a lesson passed). Progress, the calendar, the month line and
the sidebar all use them.

## Configuration

Secrets come from Streamlit secrets or the environment (`ui.get_setting`):
`SUPABASE_URL`, `SUPABASE_KEY` (the publishable key only; a secret key is
refused), `GROQ_API_KEY`, `APP_PASSWORD`, `APP_MODE=public`. None is ever
logged or shown. `.streamlit/config.toml` caps uploads at 20 MB.

## Visual system (Quiet Precision)

All in `coach/style.py`, tokens in `:root`:
- **Lines, three levels, all 1px**: `--line-1` structural (sections, the
  header), `--line-2` secondary (rows inside a list), `--line-3`
  interactive (fields, outlined buttons); focus adds `--outline`.
- **Surfaces**: a tint (`--surface`) without a shadow; only what floats
  (menus, the dock, dialogs, toasts) is lifted.
- **Corners**: `--radius-small` 12 controls, `--radius-medium` 16 surfaces
  and images, `--radius-large` 20 floating things, pill only for segmented
  controls, tags and dots.
- Grey only; type carries the hierarchy; motion only for continuity, and
  none under `prefers-reduced-motion`.

## Tests and deployment

- `tools/check.sh` (about 15 s): every unit test, the reference check
  (`tests/test_references.py`: every `module.name` the app uses exists), the
  page smoke test (`tests/test_pages_smoke.py`: every page and every way into
  the course map, through the real app, no browser), and the feature
  inventory check. Runs before every push (`.githooks/pre-push`; enable with
  `git config core.hooksPath .githooks`) and on GitHub
  (`.github/workflows/check.yml`).
- `tests/e2e/` (Playwright, a fake Supabase and Groq, a settable clock):
  flows, two accounts, personas, odd input, accessibility, screenshots at
  390 / 820 / 1180 / 1440 light and dark, visual baselines
  (`UPDATE_BASELINE=1` to accept a deliberate change). Run with
  `python -m pytest -q tests/e2e`.
- Deploy: Streamlit Cloud pulls the branch; press **Reboot app** after an
  update so every session starts on the new code (`freshen()` covers the
  case where nobody does).
