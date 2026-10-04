"""The coming-back pages without a browser (part of the check before every
push): Today after a break, a light day, the reminder at her time, a
milestone, the week in review, reminders in Settings, rest days on Progress."""
import html
import json
from datetime import datetime, timedelta

import pytest

import seed_history
from coach import clock, core, habit, prefs, ui
from test_pages_smoke import app, loads

TZ = clock.TIMEZONE


def texts(at):
    return html.unescape(" ".join(str(h.proto) for h in at.get("html")) + " ".join(m.value for m in at.markdown)
                         + " ".join(str(b.proto.label) for b in at.button))


def has(at, key) -> bool:
    try:
        at.button(key=key)
    except KeyError:
        return False
    return True


def stored_prefs(tmp_path):
    rows = json.loads((tmp_path / "learner_prefs.json").read_text()) if (tmp_path / "learner_prefs.json").exists() else []
    return prefs.normalize(rows[0]["data"]) if rows else prefs.blank()


def history_until(last_day, days=20, topics=("philosophy", "cosmos")):
    return seed_history.build(last_day + timedelta(days=1), days=days, topics=topics, gaps=(), partial=())


@pytest.fixture
def at_time(monkeypatch):
    def set_now(hh, mm=0):
        t = ui.today()
        monkeypatch.setattr(clock, "now", lambda: datetime(t.year, t.month, t.day, hh, mm, tzinfo=TZ))
    return set_now


def test_after_a_break_today_welcomes_her_back_and_offers_a_gentle_day(monkeypatch, tmp_path):
    # covers: W-daily-wb_light
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=9)))
    loads(at, "views/daily.py")
    t = texts(at)
    assert "Welcome back" in t and "Last time you were in" in t
    assert "missed" not in t.lower() and "streak" not in t.split("Welcome back")[1][:200].lower(), "no guilt"
    at.button(key="wb_light").click().run()
    assert not at.exception and stored_prefs(tmp_path)["light_day"] == ui.today().isoformat()
    loads(at, "views/daily.py")
    assert len([b for b in at.button if str(b.key).startswith("step_")]) == 1, "today is one lesson"


def test_a_busy_day_can_be_made_light_and_back(monkeypatch, tmp_path):
    # covers: W-daily-light_on, W-daily-light_off
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1)))
    loads(at, "views/daily.py")
    steps = lambda: len([b for b in at.button if str(b.key).startswith("step_")])    # noqa: E731
    assert steps() == 3 and has(at, "light_on")
    at.button(key="light_on").click().run()
    loads(at, "views/daily.py")
    assert steps() == 1 and has(at, "light_off") and "A light day" in texts(at)
    at.button(key="light_off").click().run()
    loads(at, "views/daily.py")
    assert steps() == 3


def test_the_reminder_shows_once_its_time_has_come(monkeypatch, tmp_path, at_time):
    # covers: W-settings-set_rem_on
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1)))
    loads(at, "views/settings.py")
    at.toggle(key="set_rem_on").set_value(True).run()
    assert stored_prefs(tmp_path)["reminder_on"] and stored_prefs(tmp_path)["reminder_time"] == prefs.DEFAULT_TIME
    at_time(18, 30)
    loads(at, "views/daily.py")
    assert "learning time" not in texts(at)
    at_time(19, 5)
    loads(at, "views/daily.py")
    assert "past your 19:00 learning time" in texts(at)
    assert stored_prefs(tmp_path)["reminded_on"] == ui.today().isoformat(), "once a day"
    loads(at, "views/daily.py")
    assert "past your 19:00 learning time" in texts(at), "it stays for the day, without counting again"


def test_reminders_off_by_default_and_the_time_can_change(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/settings.py")
    assert "Off." in texts(at) and not stored_prefs(tmp_path)["reminder_on"]
    at.toggle(key="set_rem_on").set_value(True).run()
    from datetime import time as dtime
    at.time_input(key="set_rem_time").set_value(dtime(7, 30)).run()
    assert stored_prefs(tmp_path)["reminder_time"] == "07:30"
    at.toggle(key="set_rem_on").set_value(False).run()
    assert not stored_prefs(tmp_path)["reminder_on"]


def test_milestones_already_earned_are_not_news_but_a_new_one_is(monkeypatch, tmp_path):
    # covers: W-daily-ms_seen
    entries = history_until(ui.today() - timedelta(days=1), days=8, topics=("philosophy",))
    at = app(monkeypatch, tmp_path, entries=entries)
    loads(at, "views/daily.py")
    assert not has(at, "ms_seen"), "on her first visit what she had already earned isn't announced"
    p = stored_prefs(tmp_path)
    assert p["seen_init"] and "streak-7" in p["seen"]
    p["seen"] = [k for k in p["seen"] if k != "lessons-10"]       # as if she had just passed her 10th lesson
    (tmp_path / "learner_prefs.json").write_text(json.dumps([{"user_id": "smoke-owner", "data": p}]))
    at.session_state["coach_prefs"] = p
    loads(at, "views/daily.py")
    assert "10 lessons passed" in texts(at)
    at.button(key="ms_seen").click().run()
    loads(at, "views/daily.py")
    assert not has(at, "ms_seen") and "lessons-10" in stored_prefs(tmp_path)["seen"]


def test_the_week_in_review_this_week_and_last(monkeypatch, tmp_path):
    # covers: W-week-wk_which
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1), days=14))
    loads(at, "views/daily.py")
    if habit.week(at.session_state["coach_log"], habit.week_of(ui.today()) - timedelta(days=7), ui.today())["lessons"]:
        assert has(at, "today_week"), "a new week points to the last one"
    loads(at, "views/week.py")
    t = texts(at)
    assert "Your week" in t and "What you learned" in t and "For the week ahead" in t
    at.segmented_control(key="wk_which").set_value("Last week").run()
    assert not at.exception and "Days you studied" in texts(at)
    assert stored_prefs(tmp_path)["week_seen"] == habit.week_key(habit.week_of(ui.today()) - timedelta(days=7))
    loads(at, "views/daily.py")
    assert not has(at, "today_week"), "seen: Today stops pointing to it"


def test_rest_days_on_progress_and_one_streak_everywhere(monkeypatch, tmp_path):
    today = ui.today()
    entries = history_until(today - timedelta(days=3), days=15, topics=("philosophy",))   # 2 missed, 2 rest days
    at = app(monkeypatch, tmp_path, entries=entries)
    loads(at, "views/records.py")
    log = at.session_state["coach_log"]
    s = habit.streaks.walk(core.streak_dates(log), today)
    t = texts(at)
    assert s["current"] == 15 and s["covering"] == 2 and "rest days are covering your break" in t
    assert core.current_streak(log, today) == s["current"], "the figure on Progress is this walk"
    assert any("_rest" in str(b.key) for b in at.button), "rest days are marked on the calendar"
    loads(at, "views/course.py", subject="philosophy")
    assert "Started" in texts(at) and "lessons passed" in texts(at)


def test_without_the_new_table_everything_else_works(monkeypatch, tmp_path):
    from coach import storage
    def missing(self):
        raise storage.StorageError("the database isn't responding right now", status=404)
    monkeypatch.setattr(storage.FileStore, "load_prefs", missing)
    at = app(monkeypatch, tmp_path, entries=history_until(ui.today() - timedelta(days=1)))
    for page in ("views/daily.py", "views/records.py", "views/week.py", "views/settings.py"):
        loads(at, page)
    assert "one more table" in texts(at)
    at.toggle(key="set_rem_on").set_value(True).run()
    assert not at.exception
