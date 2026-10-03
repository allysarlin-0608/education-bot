"""Review (spaced repetition) in the browser: cards from a failed quiz and a
saved point come back the next day; Today shows how many are due; answers
are checked without the model; the collection searches, pauses, deletes;
reviewing alone doesn't count for the streak."""
import itertools
import json
import time
from datetime import date, timedelta

import pytest

import flows
from conftest import covers

_n = itertools.count()
D = date(2026, 11, 9)


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def cards_of(app, email):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    out = []
    for e in d["tables"]["learning_entries"]:
        if e["user_id"] == uid:
            lessons = e["lessons"] if not isinstance(e["lessons"], str) else json.loads(e["lessons"])
            for s in lessons:
                out += s.get("cards") or []
    return out


@pytest.mark.parametrize("width", [1180, 390])
def test_review_the_next_day(public_app, pages, clock, width):
    covers("W-daily-today_review", "W-review-check", "W-daily-save_menu", "W-daily-save_point", "W-review-rv_view",
           "W-review-key", "W-review-rv_show", "W-review-rv_yes", "W-review-rv_next", "W-records-prog_review_open",
           "W-review-rv_query", "W-review-rv_kind", "W-review-rv_pause", "W-review-rv_del", "W-review-rv_del_yes",
           "D-review-save_entry", "D-review-save_entry-2", "D-review-save_entry-3")
    app = public_app
    clock(D, "02:00:00")
    p = pages(width=width)
    email = f"rev{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, pace="Light")
    flows.open_app(p, app)
    page = p.page
    flows.start_lesson(p)
    # save the key idea for review
    flows.tap(p, page.get_by_role("button", name="Save for review"))
    flows.tap(p, page.get_by_role("button", name="Key idea"))
    assert flows.wait_text(page, "Saved for review", 10)
    flows.idle(page)
    flows.take_quiz(p, correct=False)                  # every question missed
    cards = cards_of(app, email)
    assert sorted({c["kind"] for c in cards}) == ["point", "question"]
    assert "Review ·" not in page.evaluate("document.body.innerText"), "nothing is due on the day itself"
    # the next day
    clock(D + timedelta(days=1), "02:00:00")
    app.reset_calls()
    flows.open_app(p, app)
    n = len([c for c in cards])
    assert flows.wait_text(page, f"Review · {n} cards due", 10)
    flows.button(p, f"Review · {n} cards due", exact=False)
    assert "/review" in page.url and flows.wait_text(page, f"{n} left today", 10)
    # a choice question: wrong on purpose, then right ones
    first = True
    for _ in range(n):
        flows.idle(page)
        boxes = page.locator('[data-testid="stSelectbox"]')
        if page.locator('[data-testid="stRadio"]').count() == 0 and boxes.count():
            rights = ["The line Earth spins around", "One spin a day", "One trip around the Sun", "When the Sun comes into view"]
            for j in range(boxes.count()):
                flows.choose(p, boxes.nth(j), rights[j])
            flows.button(p, "Check")
            assert flows.wait_text(page, "Right.", 10)
        elif page.locator('[data-testid="stRadio"]').count() == 0:
            flows.button(p, "Show the answer")
            flows.button(p, "I knew it")
        else:
            radio = page.locator('[data-testid="stRadio"]').first
            opt = "Solar flares" if first else "It spins on its axis"
            target = radio.get_by_text(opt, exact=True)
            if target.count() == 0:
                target = radio.locator("label").first
            flows.tap(p, target)
            flows.button(p, "Check")
            assert flows.wait_text(page, "Not quite." if first else "Right.", 10)
            first = False
        flows.idle(page)
        nxt = "Next card" if "Next card" in page.evaluate("document.body.innerText") else "Finish"
        flows.button(p, nxt)
        flows.idle(page)
    assert flows.wait_text(page, "All reviewed for today", 10)
    assert app.calls() == [], "reviews make no model calls"
    reviewed = cards_of(app, email)
    assert all(c["last"] == (D + timedelta(days=1)).isoformat() for c in reviewed)
    assert sum(c["box"] == 0 for c in reviewed) >= 1 and sum(c["box"] == 1 for c in reviewed) >= 1
    # reviewing doesn't make the day count for the streak
    flows.go(p, app, "Progress")
    figures = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.figure')].map(f =>
        [f.querySelector('.figure-label').innerText.trim(), f.querySelector('.figure-value').innerText.replace(/\\s+/g, ' ').trim()]))""")
    assert figures["Current streak"] == "0 days", figures
    # the collection: search, pause, delete
    flows.button(p, f"Review collection · {n} cards", exact=False)
    assert "/review" in page.url
    page.get_by_role("button", name="Collection").or_(page.get_by_role("radio", name="Collection")).first.click()
    flows.idle(page)
    box = page.get_by_label("Search your collection")
    box.fill("day and night")
    box.press("Enter")
    flows.idle(page)
    assert flows.wait_text(page, "of %d cards" % n, 5)
    flows.button(p, "Pause", exact=True)
    flows.idle(page)
    assert flows.wait_text(page, "1 paused", 10)
    flows.button(p, "Delete", exact=True)
    flows.button(p, "Delete it")
    flows.idle(page)
    assert len(cards_of(app, email)) == n - 1


def test_matching_recall_not_yet_keep_and_show_more(public_app, pages, clock):
    covers("W-review-x", "W-review-check-2", "W-review-rv_no", "W-review-rv_back", "W-review-rv_del_no",
           "W-review-rv_show_more")
    app = public_app
    clock(D, "02:00:00")
    p = pages(width=1440)
    email = f"rev{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p)
    due = (D - timedelta(days=1)).isoformat()
    base = {"box": 0, "due": due, "added": due, "last": None, "reviews": 0, "lapses": 0, "paused": False,
            "topic": "philosophy", "n": 1}
    match = {"type": "match", "question": "Match each term to its meaning.", "left": ["Axis", "Orbit"],
             "right": ["One trip around the Sun", "The line Earth spins around"], "key": [1, 0], "why": ""}
    cards = [dict(base, id="m1", kind="question", front=match["question"], back="x", question=match),
             dict(base, id="w1", kind="word", front="axis", back="the line it spins around")]
    cards += [dict(base, id=f"p{k}", kind="point", front=f"Point {k:02d}", back="b", due="2026-12-01") for k in range(33)]
    slot = {"n": 1, "title": "What philosophy is", "unit": "", "kickoff": "k", "lesson": "x", "followups": [],
            "completed": True, "quiz": None, "cards": cards}
    app.seed_entries(email, [{"date": due, "topic": "philosophy", "session_number": 1, "level": "Beginner",
                              "completed": True, "title": "", "followup_question": "", "reflection": "",
                              "lesson": "", "followups": [], "kickoff": "", "lessons": [slot]}])
    flows.open_app(p, app, "/review")
    page = p.page
    assert flows.wait_text(page, "2 left today", 15)
    boxes = page.locator('[data-testid="stSelectbox"]')
    flows.choose(p, boxes.nth(0), "The line Earth spins around")
    flows.choose(p, boxes.nth(1), "One trip around the Sun")
    flows.button(p, "Check")
    assert flows.wait_text(page, "Right.", 10)
    flows.button(p, "Next card")
    flows.button(p, "Show the answer")
    flows.button(p, "Not yet")
    assert flows.wait_text(page, "Not quite.", 10) and flows.wait_text(page, "comes back tomorrow", 5)
    flows.button(p, "Finish")
    assert flows.wait_text(page, "All reviewed for today", 10)
    flows.button(p, "Back to Today", exact=False)
    assert flows.wait_text(page, "Start this lesson", 15) or flows.wait_text(page, "Today's done", 5)
    flows.open_app(p, app, "/review")
    page.get_by_role("button", name="Collection").or_(page.get_by_role("radio", name="Collection")).first.click()
    flows.idle(page)
    assert flows.wait_text(page, "35 of 35 cards", 10)
    flows.button(p, "Show more")
    assert flows.wait_text(page, "Point 32", 10)
    page.locator(".st-key-rv_acts_p0 button", has_text="Delete").click()
    flows.button(p, "Keep it")
    flows.idle(page)
    assert flows.wait_text(page, "35 of 35 cards", 10)
