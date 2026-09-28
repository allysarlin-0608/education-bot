"""The date moving under an open page (the clock override: harness/app_entry.py):
a lesson started before midnight stays on its own day, the new day starts
fresh, and streaks count across the change."""
import itertools
import json
import time
from datetime import date, timedelta

import pytest

import flows
from conftest import covers

_n = itertools.count()
D = date(2026, 10, 14)


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def entries(app, email):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    return sorted((e for e in d["tables"]["learning_entries"] if e["user_id"] == uid), key=lambda e: e["date"])


def test_midnight_with_the_page_open(public_app, pages, clock):
    covers("D-daily-save_entry", "W-daily-start_this_lesson")
    app = public_app
    clock(D, "15:58:00")                            # 23:58 in Taipei
    p = pages(width=1440)
    email = f"clock{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy", "Astronomy"))
    flows.open_app(p, app)
    assert flows.wait_text(p.page, f"{D:%B} {D.day}")
    flows.pass_lesson(p)                            # one lesson passed on D
    clock(D + timedelta(days=1), "16:01:00")        # 00:01 the next day, same page
    flows.button(p, "Next lesson →")                # the next action happens after midnight
    flows.open_app(p, app)
    t = p.page.evaluate("document.body.innerText")
    nxt = D + timedelta(days=1)
    assert f"{nxt:%B} {nxt.day}" in t, "after midnight Today shows the new day"
    assert "Astronomy" in t, "the new day has the next subject in turn"
    saved = entries(app, email)
    assert [e["date"] for e in saved] == [D.isoformat()], "the lesson stays on the day it was taken"
    lessons = saved[0]["lessons"]
    lessons = json.loads(lessons) if isinstance(lessons, str) else lessons
    assert lessons[0]["completed"] is True
    flows.pass_lesson(p)                            # a lesson on the new day
    saved = entries(app, email)
    assert [e["date"] for e in saved] == [D.isoformat(), nxt.isoformat()]
    assert [e["topic"] for e in saved] == ["philosophy", "cosmos"]


def test_a_completed_day_then_the_next_morning(public_app, pages, clock):
    covers("W-daily-next_lesson-2")
    app = public_app
    clock(D, "10:00:00")
    p = pages(width=1440)
    email = f"clock{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, pace="Light")                  # one lesson a day
    flows.open_app(p, app)
    flows.pass_lesson(p)
    flows.button(p, "See today's summary →")
    assert flows.wait_text(p.page, "Current streak: 1 day")
    clock(D + timedelta(days=1), "01:00:00")
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Start this lesson"), "a new day starts fresh"
    flows.pass_lesson(p)
    flows.button(p, "See today's summary →")
    assert flows.wait_text(p.page, "Current streak: 2 days")
    clock(D + timedelta(days=3), "01:00:00")        # a day missed
    flows.go(p, app, "Progress")
    flows.open_app(p, app, "/records")
    figures = p.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.figure')].map(f =>
        [f.querySelector('.figure-label').innerText.trim(), f.querySelector('.figure-value').innerText.replace(/\\s+/g, ' ').trim()]))""")
    assert figures["Current streak"] == "0 days" and figures["Longest streak"] == "2 days", figures
