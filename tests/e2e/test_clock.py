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
    flows.go(p, app, "Record")
    flows.open_app(p, app, "/records")
    figures = p.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.figure')].map(f =>
        [f.querySelector('.figure-label').innerText.trim(), f.querySelector('.figure-value').innerText.replace(/\\s+/g, ' ').trim()]))""")
    assert figures["Current streak"] == "0 days" and figures["Longest streak"] == "2 days", figures


def test_three_rotations_never_repeat_a_passed_lesson(public_app, pages, clock):
    """Issue D: Fashion and Jewelry take turns. Day 1 (Fashion) passes Lesson 1
    only; each later Fashion day starts with the first lesson not passed, a
    passed one is never scheduled again, and every day keeps its own record."""
    covers("D-daily-save_entry", "W-daily-start_this_lesson")
    app = public_app
    start = date(2026, 11, 2)
    clock(start, "02:00:00")
    p = pages(width=1440)
    email = f"rot{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Fashion & Clothing", "Jewelry & Craft"))
    for day in range(6):                                   # 3 Fashion days, 3 Jewelry days
        clock(start + timedelta(days=day), "02:00:00")
        flows.open_app(p, app)
        flows.pass_lesson(p) if day in (0, 1, 2, 3) else flows.start_lesson(p)
    saved = entries(app, email)
    by_topic = {}
    for e in saved:
        lessons = e["lessons"] if not isinstance(e["lessons"], str) else json.loads(e["lessons"])
        by_topic.setdefault(e["topic"], []).append((e["date"], [(s["n"], s["completed"]) for s in lessons]))
    fashion = by_topic["fashion"]
    assert [d for d, _ in fashion] == [str(start), str(start + timedelta(days=2)), str(start + timedelta(days=4))]
    # day 1: lesson 1 passed (2, 3 not); day 3 starts at 2; day 5 starts at the first not passed after that
    assert [n for n, _ in fashion[0][1]] == [1, 2, 3] and fashion[0][1][0] == (1, True)
    assert fashion[1][1][0][0] == 2, fashion
    passed = {n for _, ls in fashion for n, c in ls if c}
    for _, ls in fashion[1:]:
        assert not any(n in passed and not c for n, c in ls), f"a passed lesson came back: {fashion}"
    later = [n for n, _ in fashion[2][1]]
    assert later[0] == min(n for n in range(1, 20) if n not in passed), fashion
    # one entry per day and subject, each keeping its own lessons
    assert len({(e["date"], e["topic"]) for e in saved}) == len(saved) == 6


def test_a_lesson_not_passed_continues_the_next_day_on_the_same_record(public_app, pages, clock):
    """D2: Lesson 1 is written and failed on day 1; on day 2 it comes back as
    it was (not written again), only a new quiz is made, and passing it
    writes the quiz and the chat back to day 1's lesson. Day 2 gets the
    credit (streak); day 1 stays not completed and says when it was passed.
    No lesson shows twice in Progress or search."""
    covers("D-daily-save_entry", "W-daily-start_this_lesson", "D-daily-save_day-2")
    app = public_app
    clock(D, "02:00:00")
    p = pages(width=1440)
    email = f"carry{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, pace="Light")                      # one lesson a day, one subject
    flows.open_app(p, app)
    page = p.page
    flows.start_lesson(p)
    page.get_by_placeholder("Ask about Lesson").fill("Why don't we feel it?")
    page.keyboard.press("Enter")
    assert flows.wait_text(page, "Good question", 30)
    flows.idle(page)
    flows.take_quiz(p, correct=False)                   # not passed on day 1
    nxt = D + timedelta(days=1)
    clock(nxt, "02:00:00")
    app.reset_calls()
    flows.open_app(p, app)
    assert flows.wait_text(page, f"{nxt:%B} {nxt.day}")
    text = page.evaluate("document.body.innerText")
    assert "Start this lesson" not in text and "Key Idea" in text, "the lesson comes back as it was"
    assert "Good question" in text, "with its chat"
    page.get_by_placeholder("Ask about Lesson").fill("And at the poles?")
    page.keyboard.press("Enter")
    assert flows.wait_text(page, "And at the poles?", 30)
    flows.idle(page)
    flows.take_quiz(p, correct=True, start="Try a new quiz")
    assert app.calls("lesson") == [], "the lesson wasn't written again"
    saved = entries(app, email)
    assert [e["date"] for e in saved] == [D.isoformat(), nxt.isoformat()]
    load = lambda e: e["lessons"] if not isinstance(e["lessons"], str) else json.loads(e["lessons"])  # noqa: E731
    first, second = load(saved[0])[0], load(saved[1])[0]
    assert first["lesson"] and not first["completed"] and first["passed_on"] == nxt.isoformat()
    assert [m["content"] for m in first["followups"] if m["role"] == "user"] == ["Why don't we feel it?", "And at the poles?"]
    assert first["quiz"]["attempts"] == 2 and first["quiz"]["best"] == 100, first["quiz"]
    assert second["from"] == D.isoformat() and second["completed"] is True
    assert not second.get("lesson") and not second.get("followups") and not second.get("quiz"), "no copy"
    assert saved[1]["completed"] is True and saved[0]["completed"] is False
    flows.button(p, "See today's summary →")
    assert flows.wait_text(page, "Current streak: 1 day")
    assert page.evaluate("() => [...document.querySelectorAll('.done-list .q')].map(e => e.innerText.trim())") == ["100%"], \
        "the summary shows the quiz from the original"
    # Progress: each lesson once per day, with where it came from / when it was passed
    flows.open_app(p, app, "/records")
    page.get_by_role("radio", name="Sessions").or_(page.get_by_role("button", name="Sessions", exact=True)).first.click()
    assert flows.wait_text(page, "2 sessions", 10)
    for d in (D, nxt):
        flows.open_panel(p, f"{d:%b} {d.day}, {d.year}")
    text = page.evaluate("document.body.innerText")
    assert f"from {D:%b} {D.day}" in text and f"passed on {nxt:%b} {nxt.day}" in text
    # search: the lesson is found once, on the day it was written
    flows.button(p, "Search", exact=False)
    box = page.get_by_placeholder("Lessons, subjects, books, your notes…")
    box.fill("rotation")
    box.press("Enter")
    flows.idle(page)
    assert flows.wait_text(page, "1 result", 5)
