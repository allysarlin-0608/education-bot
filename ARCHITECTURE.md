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
| UI helpers | `coach/ui.py`, `topnav.py`, `sidebar.py`, `place.py`, `style.py`, `motion.py`, `glass.py`, `lesson_view.py`, `goalmaker.py`, `exercise.py`, `weekview.py`, `report_ui.py`, `session_ui.py`, `practice_nav.py` | session state, navigation, the dock, CSS, shared widgets | decide what counts as studied, passed or due |
| Config | `clock.py`, `appconfig.py` | the one clock (the learner's timezone, today, now) and the one way to read a setting | depend on Streamlit's UI or on any other module |
| Domain | `core.py`, `catalog.py`, `curriculum.py`, `course.py`, `review.py`, `quiz.py`, `steps.py`, `history.py`, `search.py`, `reading.py`, `books.py`, `settings.py`, `placement.py`, `paths.py`, `directions.py`, `plans.py`, `metrics.py`, `mastery.py`, `practice.py`, `unitcheck.py`, `mathcourse.py`, `learner.py`, `session.py`, `progression.py`, `diagnostic.py`, `capstone.py`, `attempts.py`, `experiments.py`, `learnmetrics.py` | pure functions over the log, the syllabus and the settings: what today is, what's next, streaks, review cards, the course map | do I/O (they are unit-tested without a store) |
| AI | `llm.py`, `quizgen.py`, `quizprep.py`, `lessonprep.py`, `itembank.py`, `quota.py`, `prompts/`, `system_prompt.md` | every model call: lessons, quizzes (with checking and repair), chat; per-minute pacing; the daily allowance | run without counting toward the allowance |
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
  onboarding. `subjects` is her cycle of turns: the turn moves on when she
  studies, not with the calendar (`settings.topic_for`: up to today, the turn
  after the last one she studied, `settings.last_turn`; after today, one turn
  a day from today's). A day she skips doesn't skip a goal. A day already
  started keeps its subject when subjects change (the new turns start
  tomorrow); a new pace reshapes today's remaining
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
  today's practice set where she left it (Phase 3), who she said she is in
  the setup (`identity`, at most 60 characters; changeable in Account), and
  a plan chosen in an earlier setup (`plan_choice`). Stored as JSON: no
  schema change.
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
  words (a whole field in a word or two is fine: it gets an overview of its
  main parts), where she is, how much time → one AI call
  (`paths.design_messages`, `tokens.PATH_MAX_TOKENS`) → `paths.read_design`:
  a path, or a kind answer (clarify, narrow, decline) with goals that fit.
  A goal too short or too long is answered before any call
  (`paths.precheck`). The same answers are never designed twice (the reply
  is kept with the answers it was for, saved before anything is drawn); a
  goal may be asked about once more with her answer
  (`paths.DESIGN_ATTEMPTS`). Every call counts toward her daily allowance.
- **The draft** (her words, the reply, the path being adjusted) lives in
  `user_settings.onboarding` (`settings.goal_draft_of`), so a refresh or
  another tab keeps it. Then `goalmaker.scope`: all of it, or only the parts
  she ticks (`paths.keep_units`, from the designed outline: nothing is lost),
  and `goalmaker.purpose`: what it's for (goals that fit who she is, her own
  words, or "all of it"), saved as the path's `why`. Neither calls the AI.
- **Her turns**: a goal from the setup is her first turn; from the New goal
  page it takes today's turn when today isn't started (`settings.add_goal`).
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
| 1 | About you | who she is (Student, Working adult, Changing careers, Retired, Learning for the love of it, or her words); skipped only by ticking "I know exactly what I want to learn". Kept as `prefs.identity`, changeable in Account | `directions.IDENTITIES`, `choices.rows` |
| 2 | What to learn | her words; ideas shown first fit who she is (`directions.IDEAS`); "I don't know yet" → Explore | `goalmaker.form` |
| 2b | Find a topic | broad directions (Languages, Math, Natural science, Society, Arts, Technology), then narrower, a third level where useful; the last choice becomes her words and is designed at once | `directions.narrower`, `directions.topic_of` |
| 3 | All of it, or some parts | the outline and its number of lessons; all of it, or tick the parts | `goalmaker.scope` |
| 4 | What it's for | goals that fit who she is, her words, or (ticked) "I want to learn all of it" | `goalmaker.purpose`, `directions.purposes` |
| 5 | Confirm | one sentence of everything, each part changeable and straight back; pace is Steady (3 a day), changeable in Goals & Settings; Start learning → `settings.finish`, her goal saved with its purpose, `prefs.identity` kept; her first day opens | `ui.save_path`, `ui.save_settings` |

One AI call per goal (the outline). Our built-in subjects are not offered to
new learners; anyone already learning one keeps them (Goals & Settings'
Subjects section and Courses' "More subjects" show only when
`settings.builtin_offered`). Reading and the placement check are no longer
asked in the setup (both stay in Goals & Settings).

The draft (`settings.draft_of`, version `DRAFT_VERSION` 3) is kept in
`user_settings.onboarding` at every answer, so Back, a change from Confirm
or a refresh never loses anything. Drafts from earlier setups open at the
nearest new step (`settings.MOVED`, `settings._step_of`). The setup's
widgets are always drawn from the draft (not from a widget's remembered
value), so a step left and come back to shows her answers as kept.

**The navigation** (`gnosis.py`, `coach/topnav.py`): the bar holds the pages
of every day (Home, Review, Reading, Record, Goals); **Menu** holds every part,
grouped (`topnav.SECTIONS`: Learn, Practice, Progress, You), each a link to
the one page that does it. Each name says one thing (ISS-088), and each
thing is in one place (ISS-098): Courses is what she learns and what comes
next in each, Goals & Settings is what she learns and which day it comes on
(Your days), and the Learning Record is her history and her week. The old
addresses /path (Schedule) and /week (Your week) still work: they open
Goals & Settings and the Record's week tab.

| Section | Page | Concept |
|---|---|---|
| Home | `daily.py` (/) | today's lessons; with more than one turn, today's and tomorrow's and a way to change the order |
| Courses | `subjects.py` (/courses) | every course of hers, its progress, the lesson that comes next, its course map |
| Goals & Settings | `settings.py` (/settings) | her goals (pause, resume, remove, bring back), the order of her days, pace, levels, reminders, reading on/off |
| Reading Plan | `reading.py` (/reading) | when she has one (else the Menu points to Goals & Settings) |
| Knowledge Map | `skills.py` (/skills) | what she knows, idea by idea |
| Review, Practice | `review.py`, `practice.py` | review and practice (quizzes live in each lesson) |
| Unit check | `unit.py` (/unit, not in the Menu) | a finished unit's check, from the course map and Home |
| Math Curriculum | `math.py` (/math; Menu → Learn, and Courses → To browse) | the math curriculum from zero to research, to browse: phases, units, prerequisites, sources |
| Learning Record | `records.py` (/records) | her history; its second tab is her week in review (`coach/weekview.py`) |
| Account | `account.py` (/account) | who she is, her plan as it is, her data, admin and test tools |

The Menu never runs off the screen: its list is capped at the screen's
height below the bar and scrolls inside itself. On a phone the bar sits a
little left of centre so the avatar keeps a clear gap from Streamlit's own ⋮.

Not built yet, and listed in the Menu as "not available yet" (never as an
empty page): Knowledge Exploration, Examinations, Research, Research
Portfolio, Certificates. On a phone the bar holds Home, Review and Menu;
everything else is in the Menu by its full name.

**Plans** are hidden while `plans.SHOWN` is off (env `PLANS_SHOWN=1` shows
them): Account then has a Subscription section. The setup never asks for a plan.

**State rules** (ISS-062…064): a finished setup is never given a draft
(`setup.put`); every run, a goal her settings name but the session lacks
re-reads the records (`ui.sync_goals`); an account with no turns goes back
to the setup, never to a fixed subject; a new goal starts from an empty
draft (`ui.clear_goal_draft`) and can't repeat one she has.

**Polish rules** (ISS-072…080): a page that fails shows `ui.calm_failure`
(never a raw error; `GNOSIS_RAISE_ERRORS=1` in the tests); a new page or
setup step opens at its top (`motion.py`); while a run is in progress the
main buttons take no second press (CSS on `data-test-script-state`); the
Menu holds only what works (`GNOSIS_SHOW_COMING=1` previews the rest); a
goal can be paused, resumed and removed (status `removed`: off her list,
its lessons kept).

**Audit stage 1** (ISS-092, ISS-093): her turns move with study, not the
calendar (above); the AI allowance holds when it can't be read
(`quota.blocked`: no call, a calm message; it once let the call through); every
AI call logs `ai_call outcome=ok|busy|failed wait_s=… retries=…`, so the AI's
capacity can be measured from the logs before more people are invited.

**Lesson objectives** (ISS-097): the outline's one AI call also gives each
lesson an objective (what she can do after it, one checkable action), kept
beside its title (`units[i]["objectives"]`, read by `paths.objective`,
`catalog.goal_objective`; kept in line when parts are ticked or the path is
trimmed). It goes into the lesson's instructions (`core._syllabus_lines`) and
the quiz's (`practice.quiz_context` → `quiz._context`: at least three
questions check it), and shows at the top of the lesson (Home, course map).
Paths designed before objectives work as before. No extra AI call; the
outline's reply may be a little longer (`tokens.PATH_MAX_TOKENS` 3400).

**Audit stage 2** (ISS-094…096):
- *Search* (`coach/search.py`): every word must appear; an English word
  matches the start of a word ("art" never finds "start"), Chinese, Japanese
  and Korean anywhere; results best first (a title counts more than a unit,
  more than the text), then newest. It also finds her goals, the lessons
  still to come in her courses (from the syllabus or the goal's path) and her
  review cards; each opens where it lives (a day, a book, a course map, Review).
- *Report a problem* (`coach/report_ui.py`, `coach/reports.py`): under each
  lesson on Home, and with a quiz's results ("Report a question"): a reason
  and an optional note. Stored in `content_reports` (supabase/reports.sql:
  added through `add_content_report`, read by admins through
  `content_reports_summary`, deleted with the account); a reported question's
  review card goes and is never made again (`review.drop_question`; `review._add`
  skips removed ids). Admins see the count, the rate per 100 lessons passed,
  the reasons and the latest reports under Account → Insights. Our own
  backend (ApiStore) says it isn't available there yet.
- *AI waits* (`supabase/ai_health.sql`, ISS-100): every AI call that ended
  busy (she was told to try again), failed, or answered after more than
  `metrics.SLOW_S` (15 s) is counted for her, per day (`llm._outcome` →
  `metrics.wait_kind` → `quota.note_wait` → `add_ai_wait`; counts only, at
  most 500 a day, deleted with her account; a failure to count is logged,
  never shown). Admins see under Account → Insights → AI waits how many
  calls were answered (from `ai_usage`), how many were busy, failed or slow,
  how many people met each, and the busiest days (`ai_health_summary`, never
  who). Read it before inviting more people: many "busy" means the AI plan
  is too small. Not in ApiStore (ADR 0008).
- *Math curriculum* (`data/math_curriculum_zh-Hant.json`, `coach/mathcourse.py`,
  `views/math.py` at /math, ISS-106): a curriculum to browse, not one of
  her courses (it isn't scheduled, quizzed or counted). The file is the one
  source: 9 phases (L0–L8, 160 units), each unit with its title, summary
  and learning outcomes (in Chinese and in English), practice focus,
  prerequisite ids and source ids; the sources list (811: title,
  organization, link, coverage, licence and use) and how they may be used. `mathcourse`
  reads it once and answers the page (units by id, a unit's prerequisites,
  the units that need it, its sources); `mathcourse.check()` holds the file
  together (every prerequisite and source named exists, ids unique, no
  loop) and runs with the unit tests. The page: each phase an expander
  (its id, title, level, how many units); opened, its goal and its units;
  a prerequisite is a link that opens its phase and brings that unit into
  view (`?unit=L4-03`, so it can be shared); sources open in a new tab; all
  the sources, the scope note and the terms of use close the page. Its
  words are the file's (Traditional Chinese); the page's own labels are
  the site's English. No AI call, nothing stored. To change the
  curriculum, edit the file: the tests say if a link is broken.
- *Mathematics, the subject* (ISS-107): the same curriculum taught day by
  day like every other subject. `coach/curriculum/math.txt` is its
  syllabus, written from the JSON by `tools/math_syllabus.py` (check.sh
  fails when it is out of date): a unit per curriculum unit, headed
  "<id> <English title>", and a lesson per learning outcome (536, its
  English text), every unit after the units it needs. The lesson's
  neighbours are named in its prompt shortened to 60 characters (an
  outcome is a whole sentence; the prompt is near its budget). A lesson's
  level is its phase's (`mathcourse.level_of`: L0–L1 Beginner, L2–L3
  Intermediate, L4 on Advanced; `curriculum.level_for(n, topic)`), and the
  lesson's model is also told its unit's summary and practice focus from
  the JSON (`mathcourse.lesson_lines`, in `core._syllabus_lines`); its
  topic section is `prompts/topics/math.md` (worked examples, LaTeX, open
  problems never presented as proved). Its object is drawn for the app
  (`art/pythagoras.py`). Like the other subjects it is offered in Goals &
  Settings to someone already learning one of them; anyone can add it
  from the curriculum page ("Add Mathematics to my days"), and its course
  map leads back to the curriculum at the unit she is in. Same AI calls
  per lesson as any subject: one subject a day, so no extra cost per
  learner.
- *Unit check* (`coach/unitcheck.py`, `views/unit.py` at /unit, ISS-099):
  once every lesson of a unit is passed, ten questions from that unit's
  lessons (each lesson's quiz, its practice bank, the questions she missed;
  the kinds marked at once), taken from every lesson in turn; never one she
  reported (the ids in a lesson's `removed`). No AI call. 80% passes; a new
  set as often as she likes (a set is fixed by its attempt number, so a rerun
  never changes it). The result is a small field on the unit's last lesson,
  `slot["unit_check"]` = {attempts, best, passed_on, last_on}: kept in her
  record (and backups), merged like the other per-lesson extras
  (`curriculum._extras`), not in ApiStore (ADR 0008). What a set showed
  goes back to each lesson asked about (`unitcheck.by_lesson`): a piece of
  "recall" evidence for the Knowledge Map (its average mark there) and a
  review card for each question missed (`review.add_missed`); each day
  touched is re-read and saved once. Reached from the course
  map (under each finished unit; the one just finished in sight) and from
  Home's list for a week after a unit is finished, until first taken.
- *Nightly browser tests* (`.github/workflows/e2e-nightly.yml`): the main
  journeys every night at 01:40 Taipei and on demand, with screenshots of
  what failed; the full suite stays a manual run.

**Fourth round** (ISS-084…091):
- *Check it yourself* searches what the lesson teaches: its title without the
  question around it (`lesson_view.check_query`: "What is an investment and
  why it matters" → "investment"), never a section heading or the goal's name.
- *A goal she already has*, in other words (`paths.similar`: the same words in
  any order, or one inside the other; CJK by pairs of characters), is offered
  before any AI call on Add a goal: continue it (resumed and given its turn if
  paused or removed), or say it's different; the very same title is never
  added twice.
- *Removing a goal* (any goal, with a confirmation that says what happens):
  out of her turns and her list, status `removed`; nothing is deleted. Its
  lessons stay in her record; its review cards and practice stop
  (`catalog.removed`, used by `review.due`, `review.next_due`,
  `mastery.weakest`); Removed goals → Bring back (paused). The only turn she
  has can't be removed.
- *The outline's counts* follow every tick at the top
  (`goalmaker.scope_line`: lessons, parts, study days at her pace); the last
  ticked part can't be unticked.
- *Her days in turn*: `settings.days_ahead` (the coming days) and
  `settings.order_from` (her cycle in a new order); Goals & Settings → Your
  days moves one earlier or later. A day already started keeps its subject,
  and the one she studied last stays last (the turn after it is today's). A
  goal added (`settings.add_goal`) comes right after the one she studied last. After adding a goal, the page says when
  its first turn is and shows the coming days.
- *Old content*: a quiz carries the rules it was written under in its id
  (`quiz.VERSION`, "v2-…", so every store keeps it with no schema change). A
  quiz written under older rules and not answered is written again when she
  starts it (attempts and best carry over); one with answers started is hers
  to finish or swap ("Use the new quiz"); one she answered is her record,
  unchanged. A lesson carried over from an earlier day and not passed can be
  rewritten on request ("Rewrite this lesson": one AI call; her questions and
  progress stay; its unanswered quiz is retired with `quiz.retire`).
- *Running the setup again* (`settings.rerun`, Account → Test the setup; on
  the public site for admins, or everyone with `GNOSIS_TEST_TOOLS=1`; never in
  the personal app): the setup opens as for a new learner; nothing is
  deleted; what she chooses comes first, then her turns as they were
  (`draft["keep"]`), her pace, levels and reading plan kept. `tests/e2e/test_journeys.py` walks the whole journey at
three widths.

**Lessons' sources and diagrams**: no source the model names is shown
(`lesson_view.unsourced`); each lesson links to Wikipedia and Britannica
searches for what it teaches (`lesson_view.check_links`, `check_query`). Diagram nodes get
readable labels (`lesson_view.humane`); one box or a tangle is left out.
The quiz checker reads the lesson (`quiz.check_request(questions, lesson)`).

**What a lesson shows** (`lesson_view.sections`, ISS-102): a section with
nothing in it is never a card (a "Disclaimer" heading once its line became
the footnote), a section that is only a disclaimer or notice is a footnote
(one disclaimer, never two), and the Topic section (the title again) is
shown only as the lesson's level, small above it. The stored text is
unchanged: the quiz, search and history read it as before.

**A quiz ready when she wants it** (`coach/quizprep.py`, ISS-101): writing
and checking a quiz is several calls in a row (`quizgen.make`), and the
per-minute token allowance often makes the first wait for the lesson's own
call to age out: over a minute after "Take the quiz". So the same work starts
in a background thread as soon as the lesson is on Home (and again after a
quiz she didn't pass), with her session's Streamlit context (her allowance,
her store). "Take the quiz" takes the prepared, checked questions at once,
waits only for what is left ("Finishing your quiz…"), or writes one as before
if nothing was prepared or it failed. One job per session, lesson and
attempt, handed out once, kept for 3 hours. Nothing about what is asked or
checked changes; the only extra cost is a quiz prepared for a lesson opened
and left. Measured with a slow model (8 s a call, one question rewritten):
pressed at once 31.6 s, after 45 s of reading 0.4 s
(`tests/e2e/test_quiz_wait.py`). Off with `GNOSIS_QUIZ_PREP=0` (the unit
tests; the browser tests run with it on).

**Quiz quality** (ISS-103): the writer and the checker are both told a
keyed answer may never go against a rule, number or definition the lesson
gives, no two questions may test the same point, and no fact that holds in
one country only (a law, an agency, an insurance or tax scheme) unless the
question names the country (the checker sends back any that breaks one).
Plain repeats are also caught in code at no cost (`quiz.alike`: two
questions of one kind with nearly all the same words, or the same right
answer to much the same question; words in half the quiz or more don't
count; `quiz.distinct` keeps the first) and the missing one is asked for.
Only plain repeats: a choice and an explain-it question on one idea are two
ways to test it. A question she reports is remembered with its lesson
(`slot["reported"]`, at most 10, via `review.drop_question`), and that
lesson's next quiz is told not to ask it again and to avoid what made it
wrong (`practice.quiz_context` → `quiz._context`).

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

## The learning system (ISS-110; docs/LEARNING_DESIGN.md)

Built from the evidence on how people learn, and measured on whether they do.

- **The learner model** (`learner.py`, `mastery.py`): each idea (a lesson;
  in mathematics one learning outcome) has P(L), the chance it is learned,
  by Bayesian knowledge tracing over its evidence (guess and slip by kind,
  soft evidence for part marks), and a memory by the FSRS forgetting curve.
  Levels: solid = learned (P(L) >= 0.8) and still remembered (>= 82%) on two
  days; mastered = P(L) >= 0.95, >= 90% remembered, three successes over a
  week; a miss means it has to hold again on another day. The model changed
  on `mastery.SWITCH`: an idea with evidence from before never shows less
  than the old model gives it until she gets it wrong after the change.
- **Review** (`review.py`): FSRS-4.5 per card (stability, difficulty), rated
  by right/wrong and how sure she was; the next review when recall would
  fall to 90% (85% in one experiment arm); a miss is relearned the next day;
  an error she was sure of comes back first. Box-only cards get their box's
  stability the next time they're answered (nothing rewritten before).
- **Today's session** (`session.py`, `session_ui.py`, `views/daily.py`):
  warm-up (due cards, the closest to forgotten first; weakest ideas' items;
  a week-old diagnostic spot check) while the lesson is written in the
  background (`lessonprep.py`); the lesson with two 【Quick Check】 blocks it
  writes itself (hint, a second try, the note behind each wrong option);
  guided practice (a worked problem with gaps, then a problem of her own;
  problem first for a known idea or in the fading arm); the six-question
  check (all marked locally, confidence on each); the day's close: mixed
  practice on earlier ideas (interleaved or blocked by the day's arm),
  explaining it back against a rubric, and a reflection with a judgment of
  learning. Slot state: `slot["session"]` (stage, quick checks, guided);
  the day's sets: `prefs["warmup"]`, `prefs["mixed"]`. A five-minute day
  (warm-up + mixed, no lesson) counts for the streak (`prefs["brief_days"]`
  → `log["brief_days"]` → `core.streak_dates`).
- **The check and its practice** (`quiz.py`, `quizgen.py`): one call writes
  six check items (choice, scenario, blank, order or another scenario,
  match, spot the mistake) and two practice items (steps, problem), each
  with a difficulty and a hint; one checking call vets all, including
  alignment with the lesson's objective; a flagged practice item is dropped,
  never rewritten. Quiz `VERSION` 3; older quizzes are read and marked as
  before (their two written answers by the model).
- **Through a path** (`progression.py`, `diagnostic.py`, `capstone.py`,
  `itembank.py`): a unit others build on (math: its prerequisites; else the
  unit before) must be cleared (its unit check passed, skipped as known,
  too few questions to check, or finished before the change) before the
  next unit opens; a missed check offers practice on the ideas missed, then
  a fresh set. Where to start: an adaptive check over the prerequisite graph
  (at most eight questions, written three answers ahead, shared for the math
  curriculum in `shared_items`), skipping the known units' lessons once she
  chooses (`prefs["diag"]`, told to the record as `log["skipped"]`, done in
  `curriculum.completed_numbers`). A finished goal (or math phase) opens its
  capstone: a brief with a rubric, her work, feedback per criterion.
- **Measuring it** (`attempts.py`, `experiments.py`, `learnmetrics.py`,
  `views/learning.py`, `tools/learning_report.py`, `tools/fit_models.py`):
  one row per answer in `learning_attempts` (never the text), experiment arms
  by hash (within-learner where possible), the dashboard for admins (first
  tries, delayed retention, known a week later, calibration, where sessions
  stop, experiments with confidence intervals) and its CSV.
- **Pages**: Practice (practice set, review cards, collection: three tabs,
  `practice_nav.py`) is in the bar where Review was; the learning map
  (`views/course.py`) holds what the Knowledge Map showed (`/skills`
  redirects); `/start` (where to start), `/capstone`, `/learning` (admins).
- **Schema**: `supabase/learning_v2.sql` (test database, adds only):
  `learning_attempts`, `shared_items`, `shared_item_reports` and their
  functions. Until it is run, answers aren't recorded and questions aren't
  shared; nothing else changes.

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

**Paused (ADR 0008, audit P2-5).** The app stays on Supabase for now.
`backend/` and ApiStore keep passing their tests but get no new features:
new stored data goes to the file store and Supabase only (ApiStore says it
isn't available there yet). Revisit when Supabase no longer fits, our own
sign-in is needed, or many more learners are invited.

**Rule from now on (ADR 0003, 0006):**
- no new code uses Supabase-specific features (PostgREST queries,
  row-level security, `auth.uid()`, RPCs), except to keep this app running
  until its step replaces them;
- any new external service goes behind one of our interfaces, with its
  reasons written down.

## Her language (ISS-108)

The site, her lessons, quizzes and the coach's answers are in the language
she picks (Goals & Settings → Language; also on the sign-in page and the
setup's first step). Before she picks, her browser's language is used
(`st.context.locale`), else English.

- **Sentences** (`coach/i18n.py`): the English sentence in the code is the
  key. `tr("…{n}…", n=3)` shows it in her language; `trn(one, many, n)`
  for counts; `N_("…")` marks a sentence kept as data and shown later with
  `tr(value)`; `tr_in(lang, …)` for a given language. A missing
  translation falls back to English, never to an error. Words kept as data
  (subject names, levels, weekdays, placement questions…) are listed in
  `i18n.texts()`.
- **Option widgets keep English values**: a selectbox or pills shows
  `format_func=tr` and stores the English value, so settings and records
  never depend on the language. (One exception, the Account page's "Who you
  are": Streamlit's test harness can't read a keyed selectbox whose
  format_func translates, so it lists translated labels and maps back.)
- **Dates** only through `i18n.weekday / month / day_long / day_short /
  date_long / month_year / relative_day` (never `%A`/`%B`).
- **Catalogs**: `coach/locales/<code>.json`, one file per language: all 16
  (English, Traditional and Simplified Chinese, Hindi, Spanish, Arabic,
  French, Bengali, Portuguese, Russian, Indonesian, Urdu, German, Japanese,
  Marathi, Telugu).
  `python tools/i18n.py` lists every sentence in the code and, per
  language, what is missing and any translation whose `{parts}` or HTML
  tags differ from the English (`tests/test_i18n.py` fails on either).
  A language is offered (`i18n.offered()`) once its file exists.
- **The model** (`llm._prepare` → `i18n.for_model`): every system prompt
  is told to write in her language. The section markers the app reads
  (【Topic】, 【Key Idea】…), JSON keys, the vocabulary table's header and
  the level words stay in English, so parsing is the same in every
  language; `lesson_view` shows the headings translated. About 90 more
  tokens a request; the longest lesson request still fits the budget
  (`tests/test_budget.py`, per language). A lesson already written keeps
  the language it was written in.
- **The page**: `i18n.page_html()` sets `<html lang>` and, for Arabic and
  Urdu, `data-dir="rtl"`: style.py (`RTL`) then runs the page's content and
  the sidebar right to left. Not `dir` on the whole document: that moved
  Streamlit's sidebar over the page on a phone. Browser-side words (the subject stage's hints in
  `motion.py`) come from `motion.words_script()`, sent on every run after
  her language is known.
- **Her choice** is `language` in her preferences (`learner_prefs`, JSON:
  no schema change).
- **Not translated yet**: the built-in subjects' syllabus titles (English
  content), the reading plan's chat messages (`coach/books.py`), the
  admin Insights page, sources and image credits.

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
- The learning system (ISS-110): `tests/test_learner.py` (the knowledge
  tracing and memory model), `tests/test_session_loop.py` (quick checks,
  guided practice and its fading, warm-up and mixed sets, the gate, the
  diagnostic, the capstone), `tests/test_progression_pages.py`,
  `tests/test_learnmetrics.py`; in a browser `tests/e2e/test_learning_loop.py`
  (the first day and the next at all four widths, light and dark; a busy day
  and coming back; where to start and the shared bank; the gate and its
  corrective path; the capstone; the learning dashboard), screenshots
  `L01`–`L41`. In the browser tests written before it, `flows.open_app`
  skips Home's warm-up (they are about what comes after it).
- `tests/e2e/` (Playwright, a fake Supabase and Groq, a settable clock):
  flows, two accounts, personas, odd input, accessibility, screenshots at
  390 / 820 / 1180 / 1440 light and dark, visual baselines
  (`UPDATE_BASELINE=1` to accept a deliberate change). Run with
  `python -m pytest -q tests/e2e`.
- Deploy: Streamlit Cloud pulls the branch; press **Reboot app** after an
  update so every session starts on the new code (`freshen()` covers the
  case where nobody does).
