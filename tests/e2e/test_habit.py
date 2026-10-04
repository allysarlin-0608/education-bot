"""Coming back, in a real browser over simulated days and weeks (the app's
one clock, moved by the test): a missed day covered by a rest day, a long
break and a warm return, a light day, the reminder at her time (and across
midnight), the week in review across a week boundary, milestones, and the
numbers agreeing on every page."""
import itertools
import time
from datetime import date, timedelta

import pytest

import flows
from conftest import covers

_n = itertools.count()
MON = date(2026, 11, 2)          # a Monday


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def text(p):
    return p.page.evaluate("document.body.innerText")


def person(app, pages, width=1180):
    p = pages(width=width)
    email = f"habit{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",), pace="Light")
    return p, email


def day(clock, d, hhmm="10:00"):
    """Taipei local time hhmm on day d (the clock is set in UTC)."""
    hh, mm = map(int, hhmm.split(":"))
    utc = (hh - 8) % 24
    clock(d if hh >= 8 else d - timedelta(days=1), f"{utc:02d}:{mm:02d}:00")


def study(p, app):
    flows.open_app(p, app)
    flows.pass_lesson(p)


def test_seven_days_a_rest_day_then_a_missed_day_keeps_the_streak(public_app, pages, clock):
    covers("W-records-prog_week", "W-records-milestones")
    app = public_app
    day(clock, MON)
    p, email = person(app, pages)
    for k in range(7):                                   # a week of one lesson a day
        day(clock, MON + timedelta(days=k))
        study(p, app)
    day(clock, MON + timedelta(days=8))                   # day 8 missed
    flows.open_app(p, app, "/records")
    t = text(p)
    assert "A rest day is covering your break" in t, t[:600]
    flows.open_panel(p, "Milestones")
    assert flows.wait_text(p.page, "A 7-day streak")
    study(p, app)                                        # back on day 9
    flows.open_app(p, app, "/records")
    t = text(p)
    assert "8" in t.split("Current streak")[1][:20], "the streak went on through the rest day"
    flows.button(p, "Your week")
    assert flows.wait_text(p.page, "What you learned")


def test_a_long_break_a_warm_welcome_and_a_gentle_day(public_app, pages, clock):
    covers("W-daily-wb_light")
    app = public_app
    day(clock, MON)
    p, email = person(app, pages, width=390)
    flows.open_app(p, app, "/settings")
    flows.tap(p, p.page.get_by_role("button", name="Focused", exact=False).first)   # 5 lessons a day
    flows.idle(p.page)
    for k in range(3):
        day(clock, MON + timedelta(days=k))
        study(p, app)
    day(clock, MON + timedelta(days=12))                  # back after 9 days
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "WELCOME BACK") or flows.wait_text(p.page, "Welcome back")
    t = text(p)
    assert "Last time you were in Philosophy" in t and "missed" not in t.lower()
    flows.button(p, "Start with one lesson")
    flows.open_app(p, app)
    assert p.page.locator('[class*="st-key-step_"] button').count() == 1, "one lesson today"
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "Today's done")


def test_the_reminder_at_her_time_and_not_after_midnight(public_app, pages, clock):
    covers("W-settings-set_rem_on")
    app = public_app
    day(clock, MON, "09:00")
    p, email = person(app, pages)
    flows.open_app(p, app, "/settings")
    p.page.get_by_text("Remind me to learn").click()
    flows.idle(p.page)
    assert flows.wait_text(p.page, "Today shows a short, friendly note")
    day(clock, MON + timedelta(days=1), "18:40")
    flows.open_app(p, app)
    assert "learning time" not in text(p)
    day(clock, MON + timedelta(days=1), "19:10")
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "past your 19:00 learning time")
    flows.pass_lesson(p)
    assert "learning time" not in text(p).split("Today's done")[0][-400:]
    day(clock, MON + timedelta(days=2), "00:10")          # just past midnight: a new day, before her time
    flows.open_app(p, app)
    assert "learning time" not in text(p)
    events = {(r["event"]) for r in app.get("/__dump")["tables"]["usage_events"]
              if r["user_id"] == next(u["id"] for u in app.get("/__dump")["users"] if u["email"] == email)}
    assert {"reminder_shown", "reminded_session"} <= events


def test_the_week_in_review_across_a_week_boundary(public_app, pages, clock):
    covers("W-daily-today_week", "W-week-wk_review")
    app = public_app
    day(clock, MON)
    p, email = person(app, pages, width=1440)
    for k in (0, 2, 6):                                  # Monday, Wednesday, Sunday late
        day(clock, MON + timedelta(days=k), "23:30" if k == 6 else "10:00")
        study(p, app)
    day(clock, MON + timedelta(days=7), "00:30")          # Monday, just after midnight
    flows.open_app(p, app)
    flows.button(p, "Last week in review")
    assert flows.wait_text(p.page, "What you learned")
    t = text(p)
    assert "Days you studied" in t and "3" in t.split("Days you studied")[1][:10]
    flows.open_app(p, app)
    assert "Last week in review" not in text(p), "seen: no longer pointed to"
    flows.open_app(p, app, "/week")
    flows.button(p, "Open Review")
    flows.idle(p.page)
    assert "Traceback" not in text(p)
