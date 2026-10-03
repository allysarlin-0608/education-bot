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
