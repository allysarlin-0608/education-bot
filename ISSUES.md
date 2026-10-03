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
