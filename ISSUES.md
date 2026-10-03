# GNOSIS — issue log (audit, October 2026)

One line per issue in the table; details below. Severity: P0 crash / data
loss / security / blocked flow · P1 wrong behaviour or content · P2 visual,
accessibility, architecture, performance · P3 polish. Earlier issues
(BUG-001 … BUG-030) are in BUGLOG.md.

| ID | Sev | Area | Issue | Status |
|---|---|---|---|---|
| ISS-001 | P0 | Deploy / architecture | Course map crash (`ui.open_course`): new pages ran on an old module after an update (BUG-030), and nothing checked before a push | fixed |
| ISS-002 | P2 | Code | `coach/place.py` had an invalid escape (`\/`) in a string: a warning now, an error in a later Python | fixed |

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
