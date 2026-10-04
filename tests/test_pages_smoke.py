"""Every page loads, in the states that matter, in a second or two and with
no browser: the check that runs before anything is pushed (tools/check.sh).

It runs the real app (gnosis.py) on a local file store and fails on any
exception a page raises, the kind of error that otherwise only shows when
someone opens the page (the course map's AttributeError, BUG-030)."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from streamlit.testing.v1 import AppTest

import seed_history
from coach import core, review, settings, storage, ui

PAGES = ["views/daily.py", "views/review.py", "views/reading.py", "views/records.py", "views/settings.py",
         "views/world.py", "views/course.py"]


def app(monkeypatch, tmp_path, *, history=True, reading=True, subjects=("philosophy", "cosmos"), entries=None, pace=3,
        paths=(), onboarding=None, onboarded=True):
    for name in ("SUPABASE_URL", "SUPABASE_KEY", "APP_MODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    monkeypatch.setenv("COACH_LOG_PATH", str(tmp_path / "log.json"))
    monkeypatch.setenv("COACH_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("COACH_USER_ID", "smoke-owner")
    store = storage.make_store("", "", scoped=False, current_user=ui.personal_user_id)
    row = settings.blank(store._uid())
    row.update(subjects=list(subjects), units_per_day=pace, subject_levels={}, reading_enabled=reading,
               onboarded_at=datetime.now(timezone.utc).isoformat() if onboarded else None, onboarding=onboarding)
    store.save_settings(row)
    if history and entries is None:
        entries = seed_history.build(ui.today() - timedelta(days=1), days=20,
                                     topics=[t for t in subjects if t in settings.SUBJECTS])
    if entries is not None or paths:
        (tmp_path / "log.json").write_text(json.dumps({"version": 1, "entries": entries or [], "books": [],
                                                       "paths": list(paths)}))
    at = AppTest.from_file("../gnosis.py", default_timeout=30)
    at.session_state["coach_authed"] = True
    return at.run()


def loads(at, page, **params):
    for k, v in params.items():
        at.query_params[k] = v
    at.switch_page(page).run()
    assert not at.exception, f"{page}: {[e.value for e in at.exception]}"
    return at


@pytest.mark.parametrize("history", [False, True], ids=["new", "with history"])
def test_every_page_loads(monkeypatch, tmp_path, history):
    at = app(monkeypatch, tmp_path, history=history)
    assert not at.exception, [e.value for e in at.exception]
    assert bool(at.session_state["coach_log"]["entries"]) == history, "the seeded history is the one loaded"
    for page in PAGES:
        loads(at, page)
    for subject in settings.SUBJECTS:                  # every subject's world and course map
        loads(at, "views/world.py", subject=subject)
        loads(at, "views/course.py", subject=subject)


def test_review_with_cards_due_and_the_collection(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "today", lambda: review.LEGACY_FROM + timedelta(days=3))
    at = app(monkeypatch, tmp_path)
    loads(at, "views/review.py")
    assert any("to go today" in str(h.proto) for h in at.get("html")) or at.markdown, "a card is shown"
    at.session_state["rv_view"] = "Collection"
    loads(at, "views/review.py")


def test_today_with_the_quiz_open_and_the_day_done(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    log = at.session_state["coach_log"]
    today = ui.today().isoformat()
    topic = settings.topic_for(at.session_state["coach_settings"], ui.today(), ui.TIMEZONE)
    done = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=(topic,))
    for e in done:
        e["date"] = today
    log["entries"] = [e for e in log["entries"] if e["date"] != today] + done
    loads(at, "views/daily.py")


def test_a_subject_address_that_isnt_one_is_corrected(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/course.py", subject="../../etc")
    loads(at, "views/world.py", subject="<script>")


def test_dates_are_real(monkeypatch, tmp_path):
    assert isinstance(ui.today(), date)


def press(at, page, key, **state):
    for k, v in state.items():
        at.session_state[k] = v
    loads(at, page)
    at.button(key=key).click().run()
    assert not at.exception, f"{page} {key}: {[e.value for e in at.exception]}"


def test_every_way_into_the_course_map_works(monkeypatch, tmp_path):
    """BUG-030 was raised by the button, not the page: press each one."""
    at = app(monkeypatch, tmp_path)
    press(at, "views/daily.py", "today_course")
    press(at, "views/records.py", "prog_course_philosophy", prog_view="Subjects")
    press(at, "views/settings.py", "set_course")
    at.query_params["subject"] = "cosmos"
    press(at, "views/world.py", "w_course")
    at.query_params["subject"] = settings.topic_for(at.session_state["coach_settings"], ui.today(), ui.TIMEZONE)
    press(at, "views/course.py", "cm_continue")         # today's subject: Continue goes to Today


def test_the_smoke_would_have_caught_the_course_map_crash(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    monkeypatch.delattr(ui, "open_course")             # the deployed state of BUG-030
    loads(at, "views/daily.py")
    at.button(key="today_course").click().run()
    assert at.exception and "open_course" in at.exception[0].value


def test_a_carried_lesson_is_read_fresh_from_the_day_it_began(monkeypatch, tmp_path):
    """ISS-010: a lesson carried over is saved back to the day it began; that
    day must be read as stored now, not as this session first loaded it (the
    phone passed it meanwhile)."""
    entries = seed_history.build(ui.today(), days=1, topics=("philosophy",), gaps=(), partial=(1,))
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=entries)
    loads(at, "views/daily.py")
    began = (ui.today() - timedelta(days=1)).isoformat()
    stored = json.loads((tmp_path / "log.json").read_text())
    slot = stored["entries"][0]["lessons"][1]                  # lesson 2: not passed yesterday
    slot["followups"] = [{"role": "user", "content": "asked on the phone"}]
    (tmp_path / "log.json").write_text(json.dumps(stored))
    loads(at, "views/daily.py")
    mine = next(e for e in at.session_state["coach_log"]["entries"] if e["date"] == began)
    assert mine["lessons"][1]["followups"] == slot["followups"]



def test_a_new_pace_reshapes_the_day_already_started_everywhere(monkeypatch, tmp_path):
    """ISS-011: pace 5 → 1 with lesson 1 passed: Today said the day was done,
    Progress kept it as 1 of 5 for good (the stored day never changed)."""
    entries = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=("philosophy",), per_day=5,
                                 gaps=(), partial=(1,))           # today: 5 lessons, 1 passed
    for s in entries[0]["lessons"][1:]:
        s.update(kickoff="", lesson="")                               # the others not begun
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=entries, pace=5)
    loads(at, "views/settings.py")
    at.button(key="pick_setpace_1").click().run()
    assert not at.exception, [e.value for e in at.exception]
    day = json.loads((tmp_path / "log.json").read_text())["entries"][0]
    assert [s["n"] for s in day["lessons"]] == [1] and day["completed"]
    log = at.session_state["coach_log"]
    assert ui.today().isoformat() in {d.isoformat() for d in core.completed_dates(log)}   # Progress agrees


def test_a_lesson_that_couldnt_be_written_leaves_no_day_behind(monkeypatch, tmp_path):
    """ISS-013: Start failed (the daily limit, a network error): nothing was
    saved, but the day stayed in this session's record as one studied."""
    from coach import llm
    monkeypatch.setattr(llm, "stream_reply", lambda *a, **k: (None, "You've reached today's limit."))
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/daily.py")
    next(b for b in at.button if b.label == "Start this lesson").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["coach_log"]["entries"] == []
    assert at.session_state["coach_retry"]["kind"] == "kickoff"           # and she can try again


def test_a_day_made_by_a_question_that_got_no_reply_is_dropped(monkeypatch, tmp_path):
    """ISS-013, every path: a carried lesson's question or quiz that failed
    (or a lesson cut off mid-way) had made today's day in memory only."""
    from coach import core, curriculum
    entries = seed_history.build(ui.today(), days=1, topics=("philosophy",), gaps=(), partial=(1,))
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=entries)
    loads(at, "views/daily.py")
    log = at.session_state["coach_log"]
    made = core.start_entry(log, ui.today(), "philosophy")             # what day_entry() does first
    made["lessons"] = curriculum.day_plan(log, "philosophy", None, 3)    # links to yesterday's lessons
    loads(at, "views/daily.py")
    assert [e["date"] for e in at.session_state["coach_log"]["entries"]] == [entries[0]["date"]]


def test_work_a_save_failed_on_is_kept_until_it_is_saved(monkeypatch, tmp_path):
    """ISS-024: a lesson written but not saved (the database was down) was
    replaced by the older stored day on the very next run."""
    entries = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=("philosophy",),
                                 gaps=(), partial=(1,))
    for s in entries[0]["lessons"][1:]:
        s.update(kickoff="", lesson="", completed=False, quiz=None)
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=entries)
    loads(at, "views/daily.py")
    day = next(e for e in at.session_state["coach_log"]["entries"] if e["date"] == ui.today().isoformat())
    day["lessons"][1]["lesson"] = "written, then the save failed"
    at.session_state["coach_unsaved"] = {(day["date"], day["topic"])}      # what ui.save_entry records
    loads(at, "views/daily.py")
    day = next(e for e in at.session_state["coach_log"]["entries"] if e["date"] == ui.today().isoformat())
    assert day["lessons"][1]["lesson"] == "written, then the save failed"



def test_saving_empty_thoughts_makes_no_day(monkeypatch, tmp_path):
    """ISS-029: Save my thoughts with nothing written, before any lesson, saved
    an empty day: Days studied +1 and today's subject fixed."""
    entries = seed_history.build(ui.today(), days=1, topics=("philosophy",), gaps=(), partial=(1,))
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=entries)   # a lesson carried from yesterday
    loads(at, "views/daily.py")
    next(b for b in at.button if b.label == "Save my thoughts").click().run()
    assert not at.exception, [e.value for e in at.exception]
    today = ui.today().isoformat()
    assert all(e["date"] != today for e in at.session_state["coach_log"]["entries"])
    assert all(e["date"] != today for e in json.loads((tmp_path / "log.json").read_text())["entries"])


def test_progress_shows_what_another_device_saved_since(monkeypatch, tmp_path):
    """ISS-030: Progress (its figures and its backup) showed this session's
    copy of the record, older than what another device had saved."""
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/daily.py")
    elsewhere = seed_history.build(ui.today(), days=2, topics=("philosophy",), gaps=(), partial=())
    (tmp_path / "log.json").write_text(json.dumps({"version": 1, "entries": elsewhere, "books": []}))
    loads(at, "views/records.py")
    assert len(at.session_state["coach_log"]["entries"]) == 2


def test_books_that_couldnt_be_read_are_not_taken_for_none(monkeypatch, tmp_path):
    """ISS-031: a brief failure reading the books on arriving at Progress
    emptied them, and a backup made then had no books."""
    from coach import storage as st_mod
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/daily.py")
    from coach import books
    book = books.new_book(ui.today())
    at.session_state["coach_log"]["books"] = [book]
    store = at.session_state["coach_store"]
    monkeypatch.setattr(type(store), "books_error", "the books couldn't be read", raising=False)
    loads(at, "views/records.py")
    assert [b["id"] for b in at.session_state["coach_log"]["books"]] == [book["id"]]


def test_settings_changed_in_another_tab_reach_this_one(monkeypatch, tmp_path):
    """A pace changed in Settings in one tab was undone by another tab still
    on the old pace (its settings were read once a session)."""
    at = app(monkeypatch, tmp_path, history=False, pace=5)
    loads(at, "views/daily.py")
    stored = json.loads((tmp_path / "settings.json").read_text())
    stored["user_settings"][0]["units_per_day"] = 1                 # the other tab
    (tmp_path / "settings.json").write_text(json.dumps(stored))
    loads(at, "views/daily.py")
    assert at.session_state["coach_settings"]["units_per_day"] == 1
