# Bug log

Every issue found in the quality audit, logged when found. Severity: P0 data loss / wrong data / security /
crash / blocked · P1 broken feature, wrong numbers, lost input, pass criterion missed · P2 slow, janky,
confusing, layout · P3 cosmetic, copy.

Status: open · fixed (commit) · needs decision.

| ID | Sev | Page / flow | Summary | Status |
|---|---|---|---|---|
| BUG-001 | P1 | Today / quiz (all JSON AI calls) | An unreadable JSON reply showed an error at once, with no automatic retry | fixed (99fe100) |
| BUG-002 | P1 | All AI actions | No overall time limit: a hung or rate-limited request could keep the person waiting minutes | fixed (0e3f046) |
| BUG-003 | P0 | Today / sidebar (API key box) | The Groq key box could put the server's secret key into the page, and appeared in public mode | fixed (add6ad2) |
| BUG-004 | P3 | Reading (books from storage) | normalize_book fills missing dates with the server's date, not the learner's | fixed (cb7ed7d) |
| BUG-005 | P0 | Progress / Backup and restore (import) | A failed import deleted the existing records | fixed (ed7b280) |
| BUG-006 | P0 | Progress / import, and every page reading records | A backup with a field of the wrong type crashed the page | fixed (cb7ed7d) |
| BUG-007 | P2 | Progress / Backup and restore (import) | A file that isn't a backup showed a raw parser error | fixed (7b62327) |
| BUG-008 | P1 | Progress / Backup and restore (import) | Any size of file was read into memory on import | fixed |

## Details

### BUG-001 (P1) — An unreadable JSON reply showed an error at once, with no automatic retry
- **Page / flow:** Today / quiz (all JSON AI calls)
- **Status:** fixed (99fe100)
- **Steps to reproduce:** Take the quiz while the model's first reply isn't JSON (fake: mode=invalid, fail_times=1)
- **Expected:** One automatic retry, then the quiz (criterion 1.5)
- **Actual:** 'The coach didn't manage to reply this time' after one bad reply
- **Root cause:** llm.ask_json returned FAILED on the first parse failure
- **Fix:** ask_json asks once more on an unparseable reply, then the friendly error
- **Files changed:** coach/llm.py, tests/test_llm.py
- **Covered by:** tests/test_llm.py::test_bad_json_once_is_retried_automatically, tests/e2e/test_ai.py::test_an_unreadable_quiz_reply_is_retried_once_automatically

### BUG-002 (P1) — No overall time limit: a hung or rate-limited request could keep the person waiting minutes
- **Page / flow:** All AI actions
- **Status:** fixed (0e3f046)
- **Steps to reproduce:** Groq slow to answer (no timeout set: the client's default is 60 s) or repeated 429s with long retry-after
- **Expected:** A reply, or a clear message with Retry, within 30 s (criterion 1.2)
- **Actual:** Up to 60 s per attempt x 4 attempts plus up to 15 s waits between them
- **Root cause:** groq.Groq created without a timeout; retries counted, not timed
- **Fix:** 20 s timeout per request; retries stop once the next wait would pass ~28 s in all
- **Files changed:** coach/llm.py, tests/test_llm.py
- **Covered by:** tests/test_llm.py::test_retries_stop_within_the_time_budget, ::test_each_request_has_a_timeout, tests/e2e/test_ai.py::test_lesson_errors_show_a_message_and_retry_works


### BUG-004 (P3) — normalize_book fills missing dates with the server's date, not the learner's
- **Page / flow:** Reading (books from storage)
- **Status:** fixed (cb7ed7d)
- **Steps to reproduce:** A stored book without started_on/last_active_on is loaded on Streamlit Cloud (UTC) between 00:00 and 08:00 Taipei
- **Expected:** The learner's local date (ui.today())
- **Actual:** The previous day (server UTC date)
- **Root cause:** books.normalize_book calls new_book(date.today())

### BUG-003 (P0) — The Groq key box could put the server's secret key into the page, and appeared in public mode
- **Page / flow:** Today / sidebar (API key box)
- **Status:** fixed (add6ad2)
- **Steps to reproduce:** Personal app, GROQ_API_KEY set, groq package unavailable: open Today
- **Expected:** No secret ever reaches the page (1.6); a public app never offers a key box
- **Actual:** The password field's value was the server key (sent to the browser)
- **Root cause:** st.text_input(value=st.session_state.api_key), which holds the key from secrets; no mode check
- **Fix:** The box never shows a stored key (value empty); only a personal app shows it; with groq missing it shows only the note
- **Files changed:** views/daily.py, tests/test_app_password.py
- **Covered by:** tests/test_app_password.py::test_the_server_key_never_reaches_the_page

### BUG-005 (P0) — A failed import deleted the existing records
- **Page / flow:** Progress / Backup and restore (import)
- **Status:** fixed (ed7b280)
- **Steps to reproduce:** Progress → Backup and restore → import a backup while the database write fails (fake: /__fail POST learning_entries)
- **Expected:** Existing records kept; the failure reported (criterion 1.4 atomic writes)
- **Actual:** All existing learning_entries rows deleted
- **Root cause:** SupabaseStore.replace: DELETE all, then upsert
- **Fix:** Upsert first, then delete only the rows not in the backup, one by one
- **Files changed:** coach/storage.py, tests/test_storage.py
- **Covered by:** tests/test_storage.py::test_replace_writes_before_it_removes, tests/e2e/test_import.py::test_a_failed_import_keeps_the_records

### BUG-006 (P0) — A backup with a field of the wrong type crashed the page
- **Page / flow:** Progress / import, and every page reading records
- **Status:** fixed (cb7ed7d)
- **Steps to reproduce:** Import {"entries":[{"date":"2026-09-01","topic":"philosophy","session_number":"many"}]}
- **Expected:** Imported with the field ignored, or refused kindly; never a crash (1.6)
- **Actual:** TypeError traceback on Progress (core.level_for_session)
- **Root cause:** parse_log/normalize_book copied values without checking their types
- **Fix:** Type and range checks on every entry, lesson and book field; plan made consistent with chapters
- **Files changed:** coach/core.py, coach/books.py, tests/test_backup_validation.py
- **Covered by:** tests/test_backup_validation.py, tests/e2e/test_import.py::test_wrong_types_never_break_a_page

### BUG-007 (P2) — A file that isn't a backup showed a raw parser error
- **Page / flow:** Progress / Backup and restore (import)
- **Status:** fixed (7b62327)
- **Steps to reproduce:** Progress → Backup and restore → import a .json file that holds plain text, binary, a list or nothing, then Replace
- **Expected:** A plain message that the file isn't a backup and nothing changed (1.9/1.10)
- **Actual:** 'Import failed: Expecting value: line 1 column 1 (char 0)' or a raw validation message; binary files raised UnicodeDecodeError
- **Root cause:** The exception text was shown as-is; UnicodeDecodeError and RecursionError were not caught
- **Fix:** One clear message for any unreadable file; decode errors and deep nesting caught too
- **Files changed:** views/records.py, tests/e2e/test_import.py
- **Covered by:** tests/e2e/test_import.py::test_malformed_files_are_refused_kindly

### BUG-008 (P1) — Any size of file was read into memory on import
- **Page / flow:** Progress / Backup and restore (import)
- **Status:** fixed
- **Steps to reproduce:** Import a 25 MB JSON file
- **Expected:** Refused with a reason before reading it (1.6 import validation: huge)
- **Actual:** Read and parsed whole; server memory and time grow with the file
- **Root cause:** No size check before json.load
- **Fix:** Files over 20 MB are refused with a message; nothing is changed
- **Files changed:** views/records.py, tests/e2e/test_import.py
- **Covered by:** tests/e2e/test_import.py::test_a_huge_file_is_refused
