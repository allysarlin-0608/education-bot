# GNOSIS — issue log (audit, October 2026)

One line per issue in the table; details below. Severity: P0 crash / data
loss / security / blocked flow · P1 wrong behaviour or content · P2 visual,
accessibility, architecture, performance · P3 polish. Earlier issues
(BUG-001 … BUG-030) are in BUGLOG.md.

| ID | Sev | Area | Issue | Status |
|---|---|---|---|---|
| ISS-001 | P0 | Deploy / architecture | Course map crash (`ui.open_course`): new pages ran on an old module after an update (BUG-030), and nothing checked before a push | fixed |
| ISS-002 | P2 | Code | `coach/place.py` had an invalid escape (`\/`) in a string: a warning now, an error in a later Python | fixed |
| ISS-003 | P1 | Today / Progress numbers | Only opening Today counted the day as "studied" when a lesson was carried over from the day before | fixed |
| ISS-004 | P2 | Security | Backup uploads could be up to 200 MB (Streamlit's default) | fixed |
| ISS-005 | P1 | Settings / Today | Adding a subject mid-day shifted the turns and swapped today's subject after the day had started | fixed |
| ISS-006 | P2 | Visual system | Lines, corners and surfaces had no global rule: 13 border values (0.5px and 1px mixed, the input edge used for dividers), 24 corner radii, shadows on surfaces that don't float | fixed |
| ISS-007 | P1 | Review | A new lesson's missed questions came back weeks late (taken for a lesson from before review) | fixed |
| ISS-008 | P1 | Review | Cards she deleted came back after a save (no cards left was read as "never had any") | fixed |
| ISS-009 | P1 | Data (local mode) | A save from an older tab wrote its whole log, wiping another tab's work | fixed |
| ISS-010 | P1 | Data / two devices | A carried-over lesson's day was saved from this session's old copy | fixed |
| ISS-011 | P1 | Settings / Progress | After a pace change mid-day, Today said the day was done and Progress never agreed | fixed |
| ISS-012 | P1 | Progress numbers | On a reading day, Days completed / the calendar / the month line disagreed, and a check-in counted as a lesson | fixed |
| ISS-013 | P2 | Today / Progress | A lesson that failed to start left the day counted as studied until a reload | fixed |
| ISS-014 | P2 | AI allowance | Streamed replies were counted at their maximum (~5,000 tokens) instead of what they used | fixed |
| ISS-015 | P2 | Performance | Settings gathered all her data (5 requests) on every click | fixed |
| ISS-016 | P2 | AI / reliability | The longest lesson prompt was 14 tokens from the request limit (an uncaught error past it) | fixed |
| ISS-017 | P2 | Tests | The page smoke test never loaded its seeded history (the log path was fixed at import) | fixed |
| ISS-018 | P2 | Wording | A subject's count read "of 3,000 overall" on Progress but "of 260 written so far" elsewhere | fixed |
| ISS-019 | P1 | Settings / data | "Download my data" failed when signed in (my ISS-015 fix ran the export where no one is signed in) | fixed |
| ISS-020 | P2 | Data (local mode) | A damaged local file was read as empty, and the next save kept only one entry | fixed |
| ISS-021 | P2 | Data / two devices | The quiz sheet saved a carried lesson's day from an old copy, undoing review grades made elsewhere | fixed |
| ISS-022 | P2 | Today / Progress | A question or quiz that failed (or a lesson cut off) left an unsaved day counted as studied | fixed |
| ISS-023 | P2 | Sidebar | The sidebar and bar could show an older count than Today on the same screen | fixed |
| ISS-024 | P1 | Data | Work a save failed on (a lesson written, a quiz passed) was replaced by the older stored day on the next run | fixed |
| ISS-025 | P2 | Data / two tabs | The quiz sheet (today's day) and Progress → Save my thoughts wrote an old copy of the whole day | fixed |
| ISS-026 | P2 | Settings | A data download gathered earlier stayed until saved, out of date | fixed |
| ISS-027 | P2 | Data (local mode) | A log file of the wrong shape crashed every page; settings files shared one temporary file | fixed |
| ISS-028 | P2 | Review | Cards made by a quiz submitted after midnight were dropped by the save | fixed |
| ISS-029 | P2 | Today / Progress | Saving empty thoughts made a day (Days studied +1, today's subject fixed) | fixed |
| ISS-030 | P2 | Progress | Progress and its backup showed this session's copy of the record, older than another device's saves | fixed |
| ISS-031 | P2 | Data / backup | A brief failure reading books on arriving at Progress emptied them (and a backup made then had none) | fixed |
| ISS-032 | P2 | Review | A card deleted in one tab came back when another tab saved the day | fixed |
| ISS-033 | P2 | Progress / cost | The record was re-read after the bar was drawn (different numbers), and twice when a session began on Progress | fixed |
| ISS-034 | P1 | Visual / iPad | Text ran into the text and buttons under it (Review → Collection cards; a course map unit's heading over its caption), worst on iPad Safari | fixed |
| ISS-035 | P2 | Tests | The iPad-landscape tests (1180) ran as a desktop with a mouse, and nothing checked for text drawn over text | fixed |
| ISS-036 | P1 | Settings / Setup on iPad | The subject list scrolled in a thin strip under the fixed subject picture on a wide, short screen (iPad on its side) | fixed |
| ISS-037 | P2 | Accessibility | The page's scrolling area showed no focus ring from the keyboard (hidden from the check by shadows inside it) | fixed |

## Details

### ISS-001 (P0) — Course map crash, and why nothing caught it
- **Where:** Today → Course map, Progress → Subjects → Course map (test site)
- **Reproduce:** a minimal Streamlit app: import a module at server start, change it and a page while no one is connected, open the page → `AttributeError` (scratch reproduction, then the same with the fix → the new code runs)
- **Root cause:** Streamlit re-reads page files every run but keeps imported modules; it reloads them only for sessions open when the files change. An update that arrived while no one was on the site gave new pages on the old `coach.ui`. The code in the repository was complete.
- **System cause:** nothing ran before a push that would fail on a page calling a name its module lacks, or on a button that crashes.
- **Fix:** `coach.freshen()` at the top of every run reloads every app module when any file is newer (BUG-030). Safeguards: `tests/test_references.py` checks every `module.name` the app uses exists; `tests/test_pages_smoke.py` loads every page in its main states and presses every way into the course map (and is shown to fail on the BUG-030 state); `tools/check.sh` runs them with every unit test before each push (`.githooks/pre-push`) and on GitHub (`.github/workflows/check.yml`).
- **Verified:** `tests/test_pages_smoke.py::test_the_smoke_would_have_caught_the_course_map_crash`; `tests/test_freshen.py`; e2e `test_course.py::test_every_way_in_on_every_device` at 390/820/1180/1440.
- **Siblings:** the reference check over every app file found no other missing name.

### ISS-002 (P2) — Invalid escape in a JavaScript regex inside Python
- **Where:** `coach/place.py` (the review dot's link match)
- **Root cause:** a JS regex `/\/review\/?$/` written inside a normal Python string
- **Fix:** a plain path comparison; `tests/test_references.py::test_no_file_relies_on_something_python_is_retiring` compiles every app file with warnings as errors

### ISS-003 (P1) — Opening Today made it a "day studied"
- **Where:** Progress → Days studied (and the calendar) after opening Today with a lesson carried over from an earlier day
- **Reproduce:** a learner's last lesson not passed; next day only open Today → Days studied grows by one (e2e: 11 instead of 10)
- **Root cause:** the page drew its quiz section from `day_entry()`, which creates today's entry in the record; with a carried lesson the page reaches that line on load, so viewing alone created the day
- **Fix:** the page draws from `shown_entry()` (the stored entry or the planned day, never added to the record); only actions call `day_entry()` (saving thoughts now too)
- **Verified:** `tests/e2e/test_personas.py` (day 10 and two weeks away: Days studied 10, streaks 10 / 0); Today and multi-day suites green

### ISS-004 (P2) — Backup uploads were limited only by Streamlit's 200 MB default
- **Fix:** `server.maxUploadSize = 20` (a year of lessons is about 2 MB)

### ISS-005 (P1) — Adding a subject swapped the day she had started
- **Where:** Settings → Subjects (add one) → Today
- **Reproduce:** two subjects, day 3 (philosophy's turn), pass a lesson, add a third subject → Today shows Fashion, a second subject the same day
- **Root cause:** the day's subject was computed from the settings alone (`days since setup % number of subjects`), so any change to the list moved every day, today included
- **Fix:** `settings.topic_for` takes the record: a day already started keeps the subject she started, if it is still one of hers; the new turns apply from the next day. Every page reads the subject through `ui.topic_for`, the one caller.
- **Verified:** `tests/test_settings.py::test_a_day_already_started_keeps_its_subject_when_one_is_added` (fails before the fix)

### ISS-006 (P2) — No global rule for lines, corners and surfaces
- **Root cause:** each page added its own border (0.5px or 1px, `--hair`, `--field-edge`, `--bk-sep` or a literal colour) and radius (10 to 28px), so the same kind of line looked different across pages and dividers used the input-edge colour
- **Fix (one rule, in `coach/style.py` `:root`, documented in ARCHITECTURE.md):** three line levels, all 1px — `--line-1` structural, `--line-2` secondary, `--line-3` interactive; `--surface` a tint with no shadow for quiet surfaces (day detail, the reader, the shelf); corners on one scale (12 controls / 16 surfaces / 20 floating / pill for segmented controls). Every 0.5px line and literal border colour is now a token; the old names (`--hair`, `--field-edge`) point at the new levels.
- **Verified:** screenshots at 390 / 820 / 1180 / 1440 light and dark; contrast and keyboard checks; visual baselines updated after review

### ISS-007 … ISS-018 — found by the independent review (a separate agent, fresh eyes)
Each one reproduced (the regression test fails before the fix, passes after) and fixed at its cause:
- **ISS-007 / ISS-008:** whether a lesson is "from before review" was read from a missing `cards` key, which both a new lesson and a lesson with every card deleted also had (an empty list was dropped on load). New lessons now carry `cards: []` from the start (`curriculum.new_slot`), and an empty list is kept on load. Tests: `test_review.py::test_a_new_lessons_missed_questions_come_back_tomorrow_whatever_came_before`, `::test_cards_she_deleted_stay_deleted_after_a_save`.
- **ISS-009:** the file store now writes one entry / one book into what is stored, like the database does. Test: `test_storage.py::test_file_store_keeps_what_another_tab_saved`.
- **ISS-010:** Today refreshes the day each carried lesson began, not only today. Test: `test_pages_smoke.py::test_a_carried_lesson_is_read_fresh_from_the_day_it_began`.
- **ISS-011:** changing the pace refits and saves today's started day (`ui.refit_today`), so every page reads the same stored day. Test: `test_pages_smoke.py::test_a_new_pace_reshapes_the_day_already_started_everywhere`.
- **ISS-012:** one definition of a completed day (every entry that day completed) and of lessons passed (`core.lessons_in`; a reading check-in is not a lesson), used by the figure, the calendar and the month line. Test: `test_history.py::test_a_day_with_reading_reads_the_same_in_every_figure`.
- **ISS-013:** a failed Start removes the day it had just made in memory. Test: `test_pages_smoke.py::test_a_lesson_that_couldnt_be_written_leaves_no_day_behind`.
- **ISS-014:** a streamed reply is counted when it ends, with Groq's reported usage (the estimate only when none comes). Test: `test_llm.py::test_a_streamed_reply_counts_what_it_used_not_its_ceiling`.
- **ISS-015:** the data download is gathered when pressed (Streamlit's deferred download).
- **ISS-016:** shorter clips on the history lines; a test builds the worst case for every subject and requires 150 tokens of room. Test: `test_coach_core.py::test_the_longest_lesson_prompt_fits_the_request_with_room`.
- **ISS-017:** `FileStore` reads `COACH_LOG_PATH` when it is made; the smoke test asserts the history it seeded is loaded.
- **ISS-018:** Progress → Subjects uses "N of M written so far", as the subject page does.

### ISS-019 … ISS-023 — found by the second independent review
- **ISS-019 (P1, a regression from ISS-015):** Streamlit's deferred download runs on a separate thread, where nobody is signed in, so the export failed. The export is now gathered in the page run when she presses Download my data, then saved with a second press (no export on other clicks). e2e: `test_privacy.py`, `test_settings.py::test_download_my_data_is_only_mine` updated to the two presses.
- **ISS-020:** saving into a file that can't be read now stops with an error and leaves the file as it is; saves to the local file take a lock and each write has its own temporary file. Test: `test_storage.py::test_a_file_that_cant_be_read_is_never_saved_over`.
- **ISS-021:** a carried lesson's day is saved by writing this page's copy of that lesson into the day as stored now; stored review cards win, only cards made today are added (`curriculum.merge_carried`). Test: `test_curriculum.py::test_a_carried_lesson_saved_from_an_old_copy_keeps_what_another_device_did`.
- **ISS-022 (generalises ISS-013):** one rule in `ui.refresh_entry`: a copy of a day that was never saved and has nothing done in it (`curriculum.worked_on`) is dropped, whichever action made it. Test: `test_pages_smoke.py::test_a_day_made_by_a_question_that_got_no_reply_is_dropped`.
- **ISS-023:** today's day is re-read once at the start of every run (gnosis.py), before the bar, the sidebar and the page.
- **Decided, not changed:** a day with only a reading check-in counts as completed (reading counts like any subject, as designed); if a lesson is also started that day, the day is completed when that lesson's day is.

### ISS-024 … ISS-027 — found by the third independent review
- **System cause (ISS-010, -021, -025):** a save wrote this session's whole copy of a day, and that copy can be old (another tab or device, a fragment that doesn't re-read). **One rule now, for every lesson save:** the day is written into what is stored now (`ui.save_day` → `curriculum.merge_day`); a lesson's stored copy wins when it has got further (`curriculum.progress_of`: passed, quiz attempts, quiz, written, questions), so progress is never undone; stored review cards win, this page only adds today's new ones; the day's other fields stay as stored except what the page changed (her thoughts). Tests: `test_curriculum.py::test_a_save_from_an_old_copy_never_undoes_a_pass_made_elsewhere`, `::test_thoughts_saved_from_progress_keep_what_was_saved_since`.
- **ISS-024:** a failed save marks the day unsaved; the re-read at the start of a run leaves an unsaved day as it is until a save succeeds. Test: `test_pages_smoke.py::test_work_a_save_failed_on_is_kept_until_it_is_saved` (fails without the guard).
- **ISS-026:** the gathered download is dropped when she leaves the page.
- **ISS-027:** reading a damaged log (not JSON, the wrong shape, not text) is a `StorageError` with a clear message, never a crash, and nothing is written over it; every local JSON file is written through one writer (`core.write_json`: its own temporary file, swapped in whole). Test: `test_storage.py::test_a_damaged_file_is_a_clear_error_not_a_crash`.

### ISS-028 … ISS-030 — found by the fourth independent review
- **ISS-028:** a merge kept the page's new cards only if dated "today" by the clock; a quiz opened before midnight and submitted after it made cards dated the day before. Cards are now compared with the day the page was opened (`page_day`), and a day a save failed on keeps every card the store doesn't have. Test: `test_curriculum.py::test_cards_made_by_a_quiz_submitted_after_midnight_are_kept`.
- **ISS-029:** Save my thoughts with nothing written and no day yet saves nothing. Test: `test_pages_smoke.py::test_saving_empty_thoughts_makes_no_day` (fails without the guard).
- **ISS-030:** arriving at Progress re-reads the whole record (`ui.refresh_log`, keeping days a save failed on). Test: `test_pages_smoke.py::test_progress_shows_what_another_device_saved_since` (fails without it).
- **Doc:** ARCHITECTURE.md now says a reading check-in counts as a streak day, as the code always did.

### ISS-031 … ISS-033 — found by the fifth independent review
- **ISS-031:** books that couldn't be read (`books_error`) are kept as this session holds them, never replaced by an empty list. Test: `test_pages_smoke.py::test_books_that_couldnt_be_read_are_not_taken_for_none` (fails without it).
- **ISS-032:** deleting a card notes its id on its lesson (`removed`, kept through saves and backups); a merge never brings back a card noted there. Test: `test_curriculum.py::test_a_card_deleted_in_another_tab_isnt_brought_back_by_a_merge`.
- **ISS-033:** the arrival re-read is done in gnosis.py before the bar and sidebar, and skipped when the record was loaded in the same run.

### ISS-034 — Text on top of text (reported on the iPad, Review → Collection)
- **Root cause:** Streamlit pulls every text block up by -1rem, to cancel a paragraph's own bottom margin. GNOSIS removes those margins (headings and paragraphs carry none), so the pull put the next line onto the text above it; Safari's slightly taller lines made it an overlap you could see. Separately, a collection card was three blocks stacked 4px apart.
- **Fix:** one global rule (`coach/style.py`): a text block keeps its height and ends where its last line ends. The collection card is now one block of text spaced by its own type (word, a quiet source line, the answer), then its actions.
- **Siblings:** the new check found the course map's unit heading over its "Lessons 1–5 · …" line; fixed by the same rule.
- **Safeguard (ISS-035):** every screenshot in `tests/e2e/test_screens.py` now fails on any two pieces of text whose boxes overlap, and the tests treat iPad landscape (1180) as a touch screen, as hers is.

### ISS-036 — The subject list squeezed under the subject picture (reported on the iPad)
- **Root cause:** the subject picture stays at the top while the list scrolls (sticky) and was sized for a tall screen (64-76% of the height, at least 460px); an iPad on its side is wide but short, so the list had a strip at the bottom. The list's rows reach 8px past the picture, so the mark of the subject in focus also showed beside the picture.
- **Fix:** a wide but short screen gets a picture a little under half the height (name and words kept, meta and credit lines give way); the picture's layer covers the list's full width; a breath under its links. Same in setup (onboarding), which shares it.
- **Verified:** screenshots at 1000×620 (iPad landscape), 1180×820 and 1440×900.

### ISS-037 — No focus ring on the page area
- The page's scrolling area takes the keyboard; it had no ring. The check passed before only because a shadow inside the area counted as a ring; with shadows gone the check saw it. It now has its own ring.

### ISS-038 … ISS-040 — found by the sixth independent review
- **ISS-038:** the settings (pace, subjects, levels) were read once per session, so a change made in another tab or device didn't reach this one until sign-in. They are re-read at the start of every run (`ui.refresh_settings`, gnosis.py). Test: `test_pages_smoke.py::test_settings_changed_in_another_tab_reach_this_one` (fails without it).
- **ISS-039:** the first lesson's kickoff saved this session's whole copy of the day, the one save left that didn't merge into what is stored. It now saves through `ui.save_day` like every other lesson save.
- **ISS-040:** a book whose stored or imported date wasn't a date (e.g. "soon") made Today and the reading shelf fail. A date that isn't one becomes the new book's (or none); a check-in's date likewise. Test: `test_books.py::test_a_book_with_a_date_that_isnt_one_still_opens` (fails without it).

### ISS-041 … ISS-043 — found while building Phase 1 (goals)
- **ISS-041:** her goals were held per thread, set at the start of each page run; a button's action (callback) runs before that, in a new thread, and saw none (Pause crashed). Goals are now read from the session running now (`catalog.bind` in `ui.py`). Test: `test_goal_pages.py::test_pausing_and_resuming_a_goal` (fails without it).
- **ISS-042:** every lesson on the public site was written for the personal app's learner (her name, age and plans). The public site now uses a general learner profile and her own goal and reasons; the personal app's prompt is unchanged. Tests: `test_goals.py::test_the_personal_app_prompt_is_unchanged`, `::test_a_goal_lesson_is_taught_from_her_words_with_sources`.
- **ISS-043:** a backup or account download from Supabase didn't include her own usage counts. It now does (`usage_events`).

### ISS-044 … ISS-049 — found by the independent review of Phase 1
- **ISS-044:** the New goal page and the setup saved her draft onto this tab's copy of her settings, undoing a change made in another tab (a subject, the pace, a goal). They now save onto the row as stored now. Test: `test_goal_pages.py::test_the_goal_page_saves_onto_what_another_tab_changed`.
- **ISS-045:** when her goals couldn't be read (a database hiccup), they dropped out of her turns: the next Settings change saved them away, and a goal-only learner got a lesson she never chose. Goals that couldn't be read are kept in her turns, she is told, and Today waits instead of teaching something else. Tests: `test_goals.py::test_goals_that_couldnt_be_read_stay_in_her_turns`, `test_goal_pages.py::test_a_goal_that_couldnt_be_read_is_never_replaced_by_another_lesson`.
- **ISS-046:** a path she cut below four lessons vanished from her draft, and Design my path then did nothing. A path she adjusts may go down to one lesson (the AI's must have four), and a path let go of is designed again. Tests: `test_goals.py::test_a_path_she_takes_down_to_one_lesson_is_still_hers`, `::test_a_path_let_go_of_is_designed_again_for_the_same_words`.
- **ISS-047:** a setup left half-way before goals existed reopened on another step (the steps were renumbered). Old drafts map to the same step. Test: `test_goals.py::test_a_setup_draft_from_before_goals_opens_on_the_same_step`.
- **ISS-048:** a usage count took its date from the browser, so the numbers could be skewed. The database now dates it (`add_usage_event(p_event)`); the goal form isn't offered while goals can't be saved (no AI call for nothing).
- **ISS-049:** the weekly lessons average rounded halves differently in the app and in the database (2.25). Both round halves up now. Test: `test_goals.py::test_the_weekly_average_rounds_as_the_database_does`.

### ISS-050 … ISS-054 — found by the engineering review (see docs/ENGINEERING_REVIEW.md)
- **ISS-050:** six separate clocks; the test clock left books and goals on the real date. One clock (`coach/clock.py`). Test: `test_clock.py`.
- **ISS-051:** a database blip failed a read outright; a slow database was waited on twice. Reads retried once on connection failure or 502/503/504 only; 3 s / 10 s timeouts. Tests: `test_storage.py`.
- **ISS-052:** a code reload mid-run could turn a handled database error into a traceback. `coach/errors.py`. Test: `test_reload_errors.py`.
- **ISS-053:** local file store: two saves at once could lose a settings row; a damaged settings or table file was taken for empty and overwritten. Locked and refused. Tests: `test_storage.py`.
- **ISS-054:** a malformed secrets file was silent; sign-in reads and the password gate swallowed every exception. Logged / narrowed. Tests: `test_appconfig.py`.
