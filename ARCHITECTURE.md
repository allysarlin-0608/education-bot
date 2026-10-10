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
| UI helpers | `coach/ui.py`, `topnav.py`, `sidebar.py`, `place.py`, `style.py`, `motion.py`, `glass.py`, `lesson_view.py`, `goalmaker.py`, `exercise.py`, `pathview.py` | session state, navigation, the dock, CSS, shared widgets | decide what counts as studied, passed or due |
| Config | `clock.py`, `appconfig.py` | the one clock (the learner's timezone, today, now) and the one way to read a setting | depend on Streamlit's UI or on any other module |
| Domain | `core.py`, `catalog.py`, `curriculum.py`, `course.py`, `review.py`, `quiz.py`, `steps.py`, `history.py`, `search.py`, `reading.py`, `books.py`, `settings.py`, `placement.py`, `paths.py`, `plans.py`, `metrics.py`, `mastery.py`, `practice.py` | pure functions over the log, the syllabus and the settings: what today is, what's next, streaks, review cards, the course map | do I/O (they are unit-tested without a store) |
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
- **learner_prefs** (`goals.sql`): her habit preferences (Phase 2),
  today's practice set where she left it (Phase 3), and the plan she chose
  in the setup (`plan_choice`).
- **learning_signals** (`mastery.sql`): per person, per day, a count of
  nine learning events (Phase 3, below), added only through
  `add_learning_signal()`; admins read totals through `gnosis_metrics()`.
- In a lesson's slot (Phase 3): `ev` (mastery evidence), `bank` (practice
  exercises written for it), `explain` (her last explanation and the reply).
- **usage_events** (`goals.sql`): per person, per day, a count of six events
  (visit, setup_done, goal_created, lesson_passed, reminder_shown,
  reminded_session), added only through
  `add_usage_event()`; admins read totals through `gnosis_metrics()`
  (Account → Insights). No content is ever kept for these.
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
- **Her turns**: a new goal goes first in the setup unless she moves it
  (Customize), and from the New goal page takes today's turn when today
  isn't started (`settings.add_goal`).
- **Lessons** for a goal (`core.goal_section`): her goal and reasons, the
  path, well-established knowledge only, sources named for important facts,
  no personal medical/legal/financial advice; lesson 1 is short with a small
  win. The public site uses a general learner profile
  (`prompts/learner_public.md`, `core.PUBLIC_EDITS`); the personal app's
  prompt is unchanged (`prompts/learner.md` + `core.md`).
- **Plans** (`plans.py`): what each plan would include; not enforced
  (`ENFORCED = False`). The setup shows them (below); prices are not set.

## The site's structure: the setup and the menu

**The setup** (`views/setup.py`, one decision a step; `route()` gives the
steps her answers call for, `settings.STEPS` names them all):

| # | Step | Does | Reuses |
|---|---|---|---|
| 1 | Welcome | what GNOSIS is | — |
| 2 | Plans | Free / Plus side by side, one chosen | `plans.py`, `choices.rows` |
| 3 | Courses & subjects | our subjects within the plan's limit; or a goal of her own (sub-step Your goal: the AI designs its path) | `stage`, `choices.rows`, `goalmaker.form` |
| 4 | Reading plan | only on a plan that includes it; optional | the reading toggle |
| 5 | Your selection | what she chose, each part changeable | `ob-summary` |
| 6 | Price summary | plan, what's included, extra costs (none), due today (0); no payment exists, nothing is charged | `plans.py` |
| 7 | Customize | time each day, how often (every day: fixed for now), the order of her turns (`settings.move_turn`), each subject's start (placement) | `choices.rows`, `choices.placement` |
| 8 | Your path | the order of her days, each course's first parts, her goal's path to adjust | `pathview.py`, `goalmaker.review` |
| 9 | Final review | everything, with ways back to change it | — |
| 10 | Start learning | `settings.finish` → her goal saved, settings saved (`onboarded_at`), `prefs.plan_choice` kept; her first day opens | `ui.save_path`, `ui.save_settings` |

The draft (`settings.draft_of`, version `DRAFT_VERSION`) is kept in
`user_settings.onboarding` at every answer, so Back, a change from the
review or a refresh never loses anything. Drafts from earlier setups open at
the same place under the new step names (`settings._step_of`). A plan that
doesn't include the reading plan switches it off in the draft. The chosen
plan is what she asked for (`prefs.plan_choice`), not a subscription: her
plan stays Free (`plans.plan_of`) until payments exist.

**The navigation** (`gnosis.py`, `coach/topnav.py`): the bar holds the pages
of every day (Home, Review, Reading, Record, Plan); **Menu** holds every part,
grouped (`topnav.SECTIONS`), each a link to the one page that does it:

| Section | Page | Concept |
|---|---|---|
| Home | `daily.py` (/) | today's lessons |
| Subjects & Courses | `subjects.py` (/courses) | the curriculum: every course |
| Learning Path | `path.py` (/path) | her sequence: the order of her days, where each course goes next |
| Learning Plan | `settings.py` (/settings) | her choices: subjects, goals, pace, levels, reminders, reading on/off |
| Reading Plan | `reading.py` (/reading) | when she has one (else the Menu points to Learning Plan) |
| Knowledge Map | `skills.py` (/skills) | what she knows, idea by idea |
| Assessments | `review.py`, `practice.py` | review and practice (quizzes live in each lesson) |
| Learning Record | `records.py` (/records), `week.py` | her history |
| Profile, Subscription & Account Settings | `account.py` (/account) | who she is, her plan as it is, her data, admin tools |

Not built yet, and listed in the Menu as "not available yet" (never as an
empty page): Knowledge Exploration, Examinations, Research, Research
Portfolio, Certificates. On a phone the bar holds Home, Review and Menu;
everything else is in the Menu by its full name.

**Plans** are hidden while `plans.SHOWN` is off (env `PLANS_SHOWN=1` shows
them): the setup then has no Plans or Price step and no plan row, and
Account has no Subscription section.

**State rules** (ISS-062…064): a finished setup is never given a draft
(`setup.put`); every run, a goal her settings name but the session lacks
re-reads the records (`ui.sync_goals`); an account with no turns goes back
to the setup, never to a fixed subject; a new goal starts from an empty
draft (`ui.clear_goal_draft`) and can't repeat one she has.

**Lessons' sources and diagrams**: no source the model names is shown
(`lesson_view.unsourced`); each lesson links to Wikipedia and Britannica
searches for its title (`lesson_view.check_links`). Diagram nodes get
readable labels (`lesson_view.humane`); one box or a tangle is left out.
The quiz checker reads the lesson (`quiz.check_request(questions, lesson)`).

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

## Knowing it, not just finishing it (Phase 3)

- **Ideas and mastery** (`mastery.py`, pure): each lesson is one idea, a
  unit groups them. Evidence (`slot["ev"]`: `{id, d, k, s}`, kinds quiz,
  recall, review, practice, explain, ask) is kept on the lesson's own slot,
  so it is saved, merged (`curriculum.merge_day` keeps every piece of both
  copies, whichever copy is further on) and backed up with the lesson. A
  lesson from before this has its evidence worked out from its best quiz
  and its review cards (`derived`) and stored once something is added
  (`seed`). From the evidence: strength (moves toward each score; a day's
  evidence of one kind is one piece), stability (grows with each success on
  a new day, halves after a failure) and a forgetting curve, so an idea
  fades when it isn't practised. Levels new / learning / solid (two
  successes on different days) / mastered (three, spread over a week or
  more); never more than one level up a day. No AI call; nothing new stored
  beyond the evidence.
- **Exercises** (`quiz.py`): seven kinds. Choice and scenario (with a note
  per wrong option: the mistake behind it), fill in the blank (variants
  accepted, a small typo forgiven, the words around the gap ignored), put
  in order and matching (part marks, naming what was out of place) are
  marked on the spot (`quiz.mark`, `quiz.mistake`); a short answer and an
  "apply it to your life" answer are marked by the model as right, partly
  right or wrong. A quiz has ten (never more than two for the model to
  mark); every keyed answer goes through the same checking call as before.
  One extra question on an earlier idea she finds hard (`practice.quiz_context`)
  is written in the same call, checked with the others, left out if
  flagged, and never counts toward the score (`quiz.counted`).
  `exercise.py` draws any kind and its feedback, the same in the quiz,
  Review and Practice.
- **Practice** (`practice.py`, `views/practice.py`): a short set on the ideas
  she knows least (`mastery.weakest`): at most two exercises an idea, ideas
  in turn, easier kinds first for an idea still being learned, harder for
  a fading one, an idea practised twice today rests. Exercises come from
  her own lessons (bank, latest quiz, missed questions: no call); only
  when an idea has none left does the model write some (write + check, two
  calls, once a day, `prefs.practice_made`), kept in the lesson's bank
  (`slot["bank"]`). The set is kept in her preferences (`prefs.practice`),
  so a refresh finds her place; an answer is taken once.
- **Explain it back** (Today, after a lesson is passed, once a day): one
  call marks it (what's right, what's missing, right/partly/wrong, at most
  one follow-up question), one more for her answer to that question.
  Empty, too short or nonsense explanations are answered with no call. Kept
  in `slot["explain"]`; its score is evidence.
- **The tutor** (questions under a lesson): the same one call, with
  `practice.TUTOR` added to its instructions: answer from the lesson, her
  goal and her record, stay on the subject, say plainly when unsure, and
  end with "Based on:" and "Confused:" lines that the page takes off and
  shows as a quiet line. A question that shows confusion is a little
  evidence ("ask") and brings the lesson's key idea back in Review tomorrow.
- **Lessons** are told the earlier ideas of the subject she is still shaky on
  (`practice.weak_titles`) to touch on once, in the same call.
- **Where it shows**: the skill map (`views/skills.py`), a level on each row
  of the course map, "Ideas mastered" and a line on Progress, "What you
  know" in the week, the idea's level and Practice on Today.
- **The numbers** (`metrics.SIGNALS`, table `learning_signals` from
  `supabase/mastery.sql`, counts only): missed → recovered (a mistake fixed
  on a later day), held / slipped (a solid idea asked again two weeks on),
  mastered, practice sets, explanations, questions to the coach and those
  showing confusion. Settings → Insights explains each.

## The platform we are moving to

Decided in `docs/ARCHITECTURE_ASSESSMENT.md` and `docs/adr/`. The plan:
- our own backend, `backend/`, built as one service with clear internal
  boundaries;
- our own PostgreSQL schema;
- our own sign-in;
- an AI gateway;
- TypeScript web and admin apps.

It replaces Supabase and Streamlit step by step, and the app keeps running
throughout.

Step M1 is done:
- the backend's skeleton;
- the relational schema with its migrations;
- repositories that store the record this app uses and give it back
  exactly;
- the checked importer out of Supabase.

Until step M2 switches this app onto it, this app still runs on Supabase as
described above.

**Rule from now on (ADR 0003, 0006):**
- no new code uses Supabase-specific features (PostgREST queries,
  row-level security, `auth.uid()`, RPCs), except to keep this app running
  until its step replaces them;
- any new external service goes behind one of our interfaces, with its
  reasons written down.

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
- Knowing it (Phase 3): `tests/test_mastery.py` (rising, fading, one level a
  day, old history, merging, the numbers), `tests/test_practice.py` (every
  kind of exercise right, wrong, partly, empty and nonsense; practice sets;
  explaining; the tutor's lines), `tests/test_mastery_pages.py`,
  `tests/e2e/test_mastery.py` (over simulated weeks), screenshots in
  `tests/e2e/test_screens.py::test_mastery_screens`.
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
