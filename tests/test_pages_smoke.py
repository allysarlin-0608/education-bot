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
from coach import review, settings, storage, ui

PAGES = ["views/daily.py", "views/review.py", "views/reading.py", "views/records.py", "views/settings.py",
         "views/world.py", "views/course.py"]


def app(monkeypatch, tmp_path, *, history=True, reading=True, subjects=("philosophy", "cosmos")):
    for name in ("SUPABASE_URL", "SUPABASE_KEY", "APP_MODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    monkeypatch.setenv("COACH_LOG_PATH", str(tmp_path / "log.json"))
    monkeypatch.setenv("COACH_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("COACH_USER_ID", "smoke-owner")
    store = storage.make_store("", "", scoped=False, current_user=ui.personal_user_id)
    row = settings.blank(store._uid())
    row.update(subjects=list(subjects), units_per_day=3, subject_levels={}, reading_enabled=reading,
               onboarded_at=datetime.now(timezone.utc).isoformat())
    store.save_settings(row)
    if history:
        entries = seed_history.build(ui.today() - timedelta(days=1), days=20, topics=subjects)
        (tmp_path / "log.json").write_text(json.dumps({"version": 1, "entries": entries, "books": []}))
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
