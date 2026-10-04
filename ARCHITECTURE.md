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
| UI helpers | `coach/ui.py`, `topnav.py`, `sidebar.py`, `place.py`, `style.py`, `motion.py`, `glass.py`, `lesson_view.py`, `goalmaker.py` | session state, navigation, the dock, CSS, shared widgets | decide what counts as studied, passed or due |
| Config | `clock.py`, `appconfig.py` | the one clock (the learner's timezone, today, now) and the one way to read a setting | depend on Streamlit's UI or on any other module |
| Domain | `core.py`, `catalog.py`, `curriculum.py`, `course.py`, `review.py`, `quiz.py`, `steps.py`, `history.py`, `search.py`, `reading.py`, `books.py`, `settings.py`, `placement.py`, `paths.py`, `plans.py`, `metrics.py` | pure functions over the log, the syllabus and the settings: what today is, what's next, streaks, review cards, the course map | do I/O (they are unit-tested without a store) |
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
- **learning_paths** (`supabase/goals.sql`): her own goals, one row per
  (user, goal id `g-` + 8 hex), the path as JSON (`paths.parse_path`:
  title, outcome, level, units of lesson titles, her goal and why, status
  active/archived). A goal is a subject like the others everywhere
  (`catalog.py`): its id is the entry's `topic`, its syllabus is its path
  (`curriculum._load`), its name is the path's title; it joins her turns in
  `user_settings.subjects`. Its outline is fixed once its first lesson is
  written (lesson numbers are positions); before that she adjusts it freely.
- **learner_prefs** (`goals.sql`): her habit preferences (Phase 2).
- **usage_events** (`goals.sql`): per person, per day, a count of six events
  (visit, setup_done, goal_created, lesson_passed, reminder_shown,
  reminded_session), added only through
  `add_usage_event()`; admins read totals through `gnosis_metrics()`
  (Settings → Insights). No content is ever kept for these.
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
   the user and `coach.GENERATION`); `ui.refresh_settings()` then re-reads
   the settings every run (another tab may have changed them). Her goals are
   read from the session running now (`catalog.bind`), never held in a
   module: callbacks run before the page and see them too.
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
Progress re-reads the whole record on arrival (its figures and backup).

One definition per number, in `core`: a day studied (any entry), a day
completed (every entry that day completed), lessons passed (`lessons_in`),
a streak day (a lesson passed, or a reading check-in). Progress, the calendar, the month line and
the sidebar all use them.

## A goal of her own (Phase 1)

- **Making it** (`goalmaker.py`, used by the setup and `views/goal.py`): her
  words, why, where she is, how much time → one AI call
  (`paths.design_messages`, `tokens.PATH_MAX_TOKENS`) → `paths.read_design`:
  a path, or a kind answer (clarify, narrow, decline) with goals that fit.
  A goal too short or too vague is answered before any call
  (`paths.precheck`). The same answers are never designed twice (the reply
  is kept with the answers it was for, saved before anything is drawn); a
  goal may be asked about once more with her answer
  (`paths.DESIGN_ATTEMPTS`). Every call counts toward her daily allowance.
- **The draft** (her words, the reply, the path being adjusted) lives in
  `user_settings.onboarding` (`settings.goal_draft_of`), so a refresh or
  another tab keeps it. Adjusting (depth, shorter, skip/move a part, remove a
  lesson) never calls the AI.
- **Her turns**: a new goal goes first in the setup, and from the New goal
  page takes today's turn when today isn't started (`settings.add_goal`).
- **Lessons** for a goal (`core.goal_section`): her goal and reasons, the
  path, well-established knowledge only, sources named for important facts,
  no personal medical/legal/financial advice; lesson 1 is short with a small
  win. The public site uses a general learner profile
  (`prompts/learner_public.md`, `core.PUBLIC_EDITS`); the personal app's
  prompt is unchanged (`prompts/learner.md` + `core.md`).
- **Plans** (`plans.py`): what each plan would include; not enforced
  (`ENFORCED = False`), no page mentions plans.

## Coming back (Phase 2)

- **Streaks with rest days** (`streaks.py`): every 7 study days earn a rest
  day (2 kept at most); a missed day uses one by itself; a longer break ends
  the streak and keeps the rest days. Worked out from the record every
  time (never stored), so `core.current_streak`, Progress, Today's done
  card, the week and the sidebar always agree.
- **Habit rules** (`habit.py`, pure): a light day (one lesson), the welcome
  after 3+ days away with a recap, a short review catch-up on light or
  returning days (`ui.review_due`: every page counts the same cards), the
  reminder ("due" after her time on a day not yet studied, once a day),
  the week Monday to Sunday against the week before, milestones, and each
  subject's start against now. No AI call.
- **Preferences** (`prefs.py`, table `learner_prefs`, one row each): the
  reminder, the light day, the milestones and week already seen. Saved
  whole onto the row as stored now (`ui.update_prefs`); where the table
  isn't there yet the defaults apply and Settings says why.
- **Today's lesson count** comes from one place (`ui.units_today`: her pace,
  or one on a light day), so Today, the sidebar and the course map agree.
- Email reminders are designed, not switched on (`docs/EMAIL_REMINDERS.md`).

## Rules the code keeps (and tests that hold them)

- **Layers** (`tests/test_layers.py`): the domain modules are pure (no
  Streamlit, no database, no network); the data, auth and AI modules never
  import the UI helpers.
- **One clock** (`tests/test_clock.py`): only `clock.py` asks the system
  for the date; tests move time for the whole app by replacing
  `clock.today` / `clock.now_iso`.
- **Settings are saved whole**, so every save starts from the row as stored
  now (`ui.refresh_settings()` first: in Settings, the setup, the New goal
  page). Records are merged on write (`ui.save_day`).
- **Database calls** (`storage.SupabaseStore._request`): 3 s to connect,
  10 s to answer; a read is asked once more when the connection failed or
  the gateway answered 502/503/504 (never after a timeout: a slow database
  isn't asked twice); a write never is (it may have landed). Every failure
  becomes a `StorageError` (`coach/errors.py`: one class across a code
  reload) with a message fit to show; the details go to the log.
- **Local files** (personal mode): every read-change-write runs under one
  lock; a file that can't be read is reported and left as it is, never
  taken for an empty one.
- **Secrets**: none in the code or the log. No secrets file is normal (the
  environment is used); one that can't be read is logged as an error and
  the app fails closed.
- **Model calls** (`llm.py`): paced to the per-minute limit, retried on
  429/5xx within a deadline, counted toward the daily allowance; a failure
  is a friendly message and a Retry button, never a half-saved lesson.
- **Logs** (`coach/__init__.py`): one line per event, `[sid]` = a short tag
  of the Streamlit session (never a name, email or user id); never a
  secret, token or answer.

## Configuration

Secrets come from Streamlit secrets or the environment (`appconfig.get_setting`):
`SUPABASE_URL`, `SUPABASE_KEY` (the publishable key only; a secret key is
refused), `GROQ_API_KEY`, `APP_PASSWORD`, `APP_MODE=public`. None is ever
logged or shown. `.streamlit/config.toml` caps uploads at 20 MB.

## Visual system (quiet minimalism)

All in `coach/style.py`, tokens in `:root`; the existing typefaces are kept.
- **Solid and flat**: black, white and grey (`--env` the page, `--surface`
  one solid step of grey, `--surface-2` pressed); no glass, blur, gradient,
  glow or shadow. Colour only where it means something.
- **No borders by default**: `--line-1/2/3` are transparent; structure comes
  from type, spacing, alignment and a change of surface (the sidebar is
  `--surface`). `--rule` is the one hairline kept for a real need.
- **Geometry follows function**: structure, images and the rule under a
  choice are square; a button 6px (`--radius-small`), a field or the chat box
  8px (`--radius-field`), a menu or toast 8px, a dialog 12px; an avatar round.
- **Controls**: primary solid ink (one per screen), secondary a grey surface,
  tertiary words only; decorative icons removed (text says it). Fields are
  grey surfaces whose ink edge appears only in use.
- **Choices** (switches, the page bar): the chosen word in full ink over a
  2px ink rule. **Progress**: a 3px ink bar on `--track`.
- Motion only for continuity (no bounce or zoom); none under
  `prefers-reduced-motion`.

## Tests and deployment

- `tools/check.sh` (about 15 s): every unit test, the reference check
  (`tests/test_references.py`: every `module.name` the app uses exists), the
  page smoke test (`tests/test_pages_smoke.py`: every page and every way into
  the course map, through the real app, no browser), and the feature
  inventory check. Runs before every push (`.githooks/pre-push`; enable with
  `git config core.hooksPath .githooks`) and on GitHub
  (`.github/workflows/check.yml`).
- Coming back: `tests/test_habit.py` (rules over simulated days and weeks),
  `tests/test_habit_pages.py` (every new page and state), `tests/e2e/test_habit.py`.
- Goals: `tests/test_goals.py` (paths, catalog, turns, the prompt, the AI
  call rules, the numbers), `tests/test_goal_pages.py` (every goal page and
  flow, no browser), `tests/e2e/test_goals.py` (in a browser).
- `tests/e2e/` (Playwright, a fake Supabase and Groq, a settable clock):
  flows, two accounts, personas, odd input, accessibility, screenshots at
  390 / 820 / 1180 / 1440 light and dark, visual baselines
  (`UPDATE_BASELINE=1` to accept a deliberate change). Run with
  `python -m pytest -q tests/e2e`.
- Deploy: Streamlit Cloud pulls the branch; press **Reboot app** after an
  update so every session starts on the new code (`freshen()` covers the
  case where nobody does).
