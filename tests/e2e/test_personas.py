"""Learners as they really come back: on day 10 with an unfinished lesson
and reviews due, and after two weeks away. Every page answers sensibly:
the unfinished lesson continues, reviews wait without a flood, streaks say
what happened, nothing crashes."""
import itertools
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

import flows
from conftest import covers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

_n = itertools.count()
TODAY = date(2026, 12, 7)


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def text(p):
    return p.page.evaluate("document.body.innerText")


@pytest.mark.parametrize("away", [0, 14], ids=["day 10, back the next day", "back after two weeks"])
def test_coming_back(public_app, pages, clock, away):
    covers("W-daily-today_review", "W-daily-start_this_lesson")
    app = public_app
    clock(TODAY, "02:00:00")
    p = pages(width=1180)
    email = f"back{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",))
    last = TODAY - timedelta(days=1 + away)
    entries = seed_history.build(last + timedelta(days=1), days=10, topics=("philosophy",), gaps=(), partial=())
    # the last day: a lesson written and its quiz failed, not passed
    final = entries[-1]
    lessons = final["lessons"] if not isinstance(final["lessons"], str) else json.loads(final["lessons"])
    lessons[-1]["completed"] = False
    lessons[-1]["quiz"]["score"] = lessons[-1]["quiz"]["best"] = 40
    final["lessons"], final["completed"] = lessons, False
    app.seed_entries(email, entries)
    open_n = lessons[-1]["n"]
    flows.open_app(p, app)
    t = text(p)
    assert f"Lesson {open_n}:" in t and "Start this lesson" not in t.split(f"Lesson {open_n}:")[1][:400], \
        "the unfinished lesson continues as it was (not written again)"
    flows.go(p, app, "Review")
    t = text(p)
    assert "to go today" in t or "Nothing due today" in t
    if "to go today" in t:
        left = int(t.split(" to go today")[0].split("·")[-1].strip())
        assert left <= 20, f"no flood after an absence: {left}"
    flows.go(p, app, "Progress")
    figures = p.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.figure')].map(f =>
        [f.querySelector('.figure-label').innerText.trim(), f.querySelector('.figure-value').innerText.replace(/\\s+/g, ' ').trim()]))""")
    # ten days with a lesson passed (the last one passed two of three); away two weeks breaks the streak
    assert figures["Current streak"] == ("0 days" if away else "10 days"), figures
    assert figures["Longest streak"] == "10 days", figures
    assert figures["Days studied"] == "10 days" and figures["Days completed"] == "9 days", \
        "only opening Today doesn't make it a day studied"
    flows.open_app(p, app, "/course?subject=philosophy")
    assert flows.wait_text(p.page, "lessons passed", 10)
    assert "Traceback" not in text(p)
