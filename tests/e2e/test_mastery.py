"""Phase 3 in a real browser, over simulated days and weeks: an idea rising
from learning to solid, fading when it isn't practised and coming back
with practice; every kind of exercise answered wrong, partly right and
right, with the specific mistake; the question on an earlier shaky idea;
explaining it back (good, poor, empty, once a day); the tutor on and off
topic, unsure and spotting confusion; practice that writes new exercises
once a day, survives a failure, a refresh and a double click; the numbers."""
import itertools
import json
import time
from datetime import date, timedelta

import pytest

import flows
from conftest import covers

_n = itertools.count()
D = date(2026, 11, 2)
L1 = "The kinds of questions philosophy asks"


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def text(p):
    return p.page.evaluate("document.body.innerText")


def person(app, pages, width=1180, pace=None):
    p = pages(width=width)
    email = f"mastery{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",), pace=pace)
    flows.open_app(p, app)                  # (setup ends in the subject's world: Today is one step on)
    return p, email


def day(clock, d, hhmm="10:00"):
    hh, mm = map(int, hhmm.split(":"))
    clock(d, f"{(hh - 8) % 24:02d}:{mm:02d}:00")


def uid_of(app, email):
    return next(u["id"] for u in app.get("/__dump")["users"] if u["email"] == email)


def entries(app, email):
    uid = uid_of(app, email)
    return [e for e in app.get("/__dump")["tables"]["learning_entries"] if e["user_id"] == uid]


def slots(app, email):
    out = {}
    for e in sorted(entries(app, email), key=lambda e: e["date"]):
        for s in json.loads(e["lessons"]) if isinstance(e["lessons"], str) else e["lessons"]:
            if not s.get("from"):
                out[s["n"]] = s
    return out


def signals(app, email):
    uid = uid_of(app, email)
    rows = app.get("/__dump")["tables"].get("learning_signals", [])
    out = {}
    for r in rows:
        if r["user_id"] == uid:
            out[r["event"]] = out.get(r["event"], 0) + r["count"]
    return out


def skill_of(p, app, title):
    """The skill map's word for one idea."""
    flows.open_app(p, app, "/skills")
    assert flows.wait_text(p.page, "Knowledge Map")
    row = p.page.locator(".sk-ideas li", has_text=title).first
    return row.locator(".sk-chip").inner_text().strip()


def review_all(p):
    """Answer every review card due, right."""
    page = p.page
    for _ in range(30):
        flows.idle(page)
        t = text(p)
        if "All reviewed for today" in t or "Nothing due today" in t:
            return
        if "Next card" in t or ("Finish" in t and "Right." in t):
            flows.button(p, "Next card" if "Next card" in t else "Finish")
            continue
        if page.get_by_role("button", name="Show the answer").count():
            flows.button(p, "Show the answer")
            flows.button(p, "I knew it")
            continue
        flows.answer_all(p, correct=True)
        flows.button(p, "Check")
    raise AssertionError("review never finished")


def test_an_idea_rises_fades_and_practice_brings_it_back(public_app, pages, clock):
    covers("W-daily-today_skills", "W-skills-sk_course", "W-daily-today_practice", "W-practice-pr_start",
           "W-practice-check", "W-practice-pr_next", "W-practice-pr_map", "W-practice-pr_today",
           "D-practice-save_day", "W-skills-sk_practice")
    app = public_app
    app.set_llm()
    day(clock, D)
    p, email = person(app, pages, pace="Light")
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "This idea: Learning"), "one quiz: learning, said plainly"
    assert skill_of(p, app, L1) == "Learning"
    # the next day: its review cards, all known → it held on another day: solid
    day(clock, D + timedelta(days=1))
    flows.open_app(p, app, "/review")
    review_all(p)
    assert skill_of(p, app, L1) == "Solid"
    flows.button(p, "Course map")
    assert flows.wait_text(p.page, "lessons passed")
    assert p.page.locator(".cm-row .sk-chip", has_text="Solid").count() >= 1, "the course map shows it too"
    # three weeks without it: it fades, and Today offers practice
    day(clock, D + timedelta(days=22))
    assert skill_of(p, app, L1) == "Learning · fading"
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Practice · 1 idea to strengthen")
    flows.button(p, "Practice · 1 idea to strengthen", exact=False)
    assert flows.wait_text(p.page, "FOCUS FOR TODAY") and L1 in text(p) and "2 short exercises" in text(p)
    app.reset_calls()
    flows.button(p, "Start practice", wait=False)
    assert flows.wait_text(p.page, "0 of 2 done", 20)
    assert app.calls() == [], "exercises from her own lessons: no AI call"
    flows.answer_all(p, correct=True)
    check = p.page.get_by_role("button", name="Check")
    check.dblclick()                                          # a double click marks it once
    assert flows.wait_text(p.page, "Right.", 10)
    flows.open_app(p, app, "/practice")                       # a refresh: her place is kept
    assert flows.wait_text(p.page, "1 of 2 done", 15)
    flows.answer_all(p, correct=True)
    flows.button(p, "Check")
    flows.button(p, "See how it went")
    assert flows.wait_text(p.page, "Practice done")
    t = text(p)
    assert "2 of 2 right" in t and "Learning → Solid" in t, t[:800]
    ev = [e for e in slots(app, email)[1]["ev"] if e["k"] == "practice"]
    assert len(ev) == 2, f"one piece of evidence per answer, never two: {ev}"
    assert signals(app, email).get("practice_done") == 1
    assert "That's all the practice ready for today" in text(p), "twice an idea a day: never a loop on one"
    flows.button(p, "Knowledge map")
    assert flows.wait_text(p.page, "Knowledge Map")


def test_every_kind_answered_wrong_or_partly_says_exactly_what_was_wrong(public_app, pages, clock):
    covers("W-daily-quiz_answers", "W-exercise-key", "W-exercise-keys_j", "W-exercise-key-2", "W-exercise-key-3")
    app = public_app
    app.set_llm()
    day(clock, D)
    p, email = person(app, pages, width=390, pace="Light")
    flows.start_lesson(p)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    t = text(p).upper()
    for kind in ("MULTIPLE CHOICE", "SCENARIO", "FILL IN THE BLANK", "PUT IN ORDER", "MATCHING",
                 "IN YOUR OWN WORDS", "APPLY IT TO YOUR LIFE"):
        assert kind in t, f"{kind} missing"
    flows.answer_all(p, correct=False)
    areas = p.page.locator('textarea[placeholder^="Answer in a sentence"]')
    areas.first.fill("The Sun goes away at the end of each day.")      # partly right
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    flows.button(p, "Submit answers", wait=False)
    assert flows.wait_text(p.page, "You need 80%", 40)
    t = text(p)
    assert "You chose “Solar flares”: Flares don't cause night. The answer is “It spins on its axis”." in t
    assert "You wrote “banana”; the word that fits is “axis”." in t
    assert "out of place. The order is: Taipei turns toward the Sun → The Sun rises in Taipei" in t
    assert "0 of 4 pairs right" in t and "“Axis” goes with “The line Earth spins around”" in t
    assert "What's missing: On the right track" in t, "partly right, and what to add"
    assert "Why it's marked wrong: It doesn't mention Earth's spin." in t
    assert "◐" in t and "✗" in t
    stored = slots(app, email)[1]["quiz"]
    assert 0.5 in stored["marks"], "a partly right answer is half a point"
    assert signals(app, email).get("missed") == 1


def test_a_shaky_earlier_idea_comes_back_in_the_next_lessons_quiz(public_app, pages, clock):
    covers("W-daily-recall")
    app = public_app
    app.set_llm()
    day(clock, D)
    p, email = person(app, pages, width=1440)
    flows.start_lesson(p)
    flows.take_quiz(p, correct=False)                         # lesson 1 shaky: wrong first...
    flows.take_quiz(p, correct=True, start="Try a new quiz")  # ...then passed
    flows.button(p, "Next lesson →")
    app.reset_calls()
    flows.start_lesson(p)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    assert flows.wait_text(p.page, f"From an earlier lesson (Lesson 1: {L1})"), "one question on the shaky idea"
    assert len(app.calls("quiz")) == 1, "in the same call"
    flows.answer_all(p, correct=True)
    flows.button(p, "Submit answers", wait=False)
    assert flows.wait_text(p.page, "Passed with 100%", 40), "it never changes the score"
    s = slots(app, email)
    assert any(e["k"] == "recall" for e in s[1]["ev"]), "it counted for lesson 1's idea"
    assert all(not q.get("from") for c in s[2].get("cards", []) for q in [c.get("question") or {}])


def test_explaining_it_back_good_poor_empty_and_once_a_day(public_app, pages, clock):
    covers("W-daily-explain_send", "W-daily-explain_reply_send", "W-daily-explain", "W-daily-explain_wait",
           "W-daily-explain_reply", "W-daily-explain_reply_wait", "AI-daily-ask_json-2", "AI-daily-ask_json-3")
    app = public_app
    app.set_llm()
    day(clock, D)
    p, email = person(app, pages, width=820)
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "EXPLAIN IT BACK") or flows.wait_text(p.page, "Explain it back")
    box = p.page.locator(".st-key-explain_back textarea")
    app.reset_calls()
    flows.button(p, "Get feedback")
    assert flows.wait_text(p.page, "Write a few sentences first")
    box.fill("It is spin.")
    p.page.keyboard.press("Tab")
    flows.button(p, "Get feedback")
    assert flows.wait_text(p.page, "A little more, please")
    assert app.calls() == [], "empty or too short: no AI call"
    box.fill("Day and night happen because the Earth keeps spinning on its axis, so each place turns to the Sun.")
    p.page.keyboard.press("Tab")
    flows.button(p, "Get feedback", wait=False)
    assert flows.wait_text(p.page, "Clear and correct.", 30)
    assert flows.wait_text(p.page, "One question: Why don't we feel the spin?")
    reply = p.page.locator(".st-key-explain_back textarea")
    reply.fill("Because the spin is smooth and steady.")
    p.page.keyboard.press("Tab")
    flows.button(p, "Send", wait=False)
    assert flows.wait_text(p.page, "Yes: the spin is smooth and steady.", 30)
    assert len(app.calls("explain")) == 1 and len(app.calls("explain_follow")) == 1
    kept = slots(app, email)[1]["explain"]                    # kept with the lesson (the course map shows it)
    assert kept["reply_feedback"]["score"] == 1.0 and kept["feedback"]["question"]
    # lesson 2, the same day: one explanation a day
    flows.button(p, "Next lesson →")
    flows.pass_lesson(p)
    assert "Get feedback" not in text(p), "once a day"
    # the next day, a poor one
    day(clock, D + timedelta(days=1))
    flows.open_app(p, app)
    flows.pass_lesson(p)
    box = p.page.locator(".st-key-explain_back textarea")
    box.fill("Turtles are lovely animals that swim slowly in warm seas.")
    p.page.keyboard.press("Tab")
    flows.button(p, "Get feedback", wait=False)
    assert flows.wait_text(p.page, "Not there yet.", 30)
    assert "What to add: Say what causes day and night" in text(p)
    s = slots(app, email)
    assert [e["s"] for e in s[1]["ev"] if e["k"] == "explain"] == [1.0, 1.0]
    assert signals(app, email).get("explained") == 2


def test_the_explain_call_failing_keeps_her_words_and_offers_retry(public_app, pages, clock):
    covers("W-daily-coach_retry_explain")
    app = public_app
    app.set_llm()
    day(clock, D)
    p, email = person(app, pages, width=1180, pace="Light")
    flows.pass_lesson(p)
    words = "Earth spins on its axis, so the Sun seems to rise and set each day."
    p.page.locator(".st-key-explain_back textarea").fill(words)
    p.page.keyboard.press("Tab")
    app.set_llm(mode="500", fail_kinds=["explain"])
    flows.button(p, "Get feedback", wait=False)
    assert flows.wait_text(p.page, "Retry", 40)
    app.set_llm()
    flows.button(p, "Retry", wait=False)
    assert flows.wait_text(p.page, "Clear and correct.", 30)
    assert slots(app, email)[1]["explain"]["text"] == words


def test_the_tutor_grounds_its_answers_and_hears_confusion(public_app, pages, clock):
    covers("W-daily-chat")
    app = public_app
    app.set_llm()
    day(clock, D)
    p, email = person(app, pages, width=1180, pace="Light")
    flows.start_lesson(p)

    def ask(q, expect):
        box = p.page.locator('[data-testid="stChatInputTextArea"]')
        box.fill(q)
        box.press("Enter")
        assert flows.wait_text(p.page, expect, 30), f"{q!r}: {expect!r}"
        flows.idle(p.page)

    ask("Why don't we feel it moving?", "Based on this lesson: Key Idea")
    assert "Confused:" not in text(p) and "Based on: Key Idea" not in text(p), "its own lines never show raw"
    ask("Do you like pizza?", "Goes beyond this lesson.")
    ask("What is the exact speed of the spin?", "The coach isn't sure about this one")
    ask("So a day comes from the orbit, right?", "a day comes from the spin, not the orbit")
    s = slots(app, email)[1]
    assert [e["k"] for e in s["ev"]] == ["ask"], "the confused question counted, a little"
    key = [c for c in s["cards"] if c["kind"] == "point" and c["front"].startswith("Key idea")]
    assert key and key[0]["due"] == (D + timedelta(days=1)).isoformat(), "its key idea comes back tomorrow"
    sig = signals(app, email)
    assert sig.get("tutor_question") == 4 and sig.get("tutor_confused") == 1


def seed_old_lesson(app, email, n=1, on=D):
    """A lesson passed before quizzes were kept (no questions to reuse), still shaky."""
    entry = {"date": on.isoformat(), "topic": "philosophy", "title": "Lessons 1–1", "completed": True,
             "lessons": [{"n": n, "title": L1, "unit": "What philosophy is", "kickoff": "",
                          "lesson": "【Key Idea】 Philosophy asks what is real, what we can know and how to live.",
                          "followups": [], "completed": True, "quiz": None, "cards": [],
                          "ev": [{"id": "seed1", "d": on.isoformat(), "k": "quiz", "s": 0.6}]}]}
    app.seed_entries(email, [entry])


def test_practice_writes_new_exercises_once_a_day_when_none_are_left(public_app, pages, clock):
    covers("AI-practice-ask_json", "AI-practice-ask_json-2", "W-practice-pr_wait")
    app = public_app
    app.set_llm()
    day(clock, D + timedelta(days=3))
    p, email = person(app, pages, width=390, pace="Light")
    seed_old_lesson(app, email)
    flows.open_app(p, app, "/practice")
    assert flows.wait_text(p.page, "FOCUS FOR TODAY")
    app.reset_calls()
    flows.button(p, "Start practice", wait=False)
    assert flows.wait_text(p.page, "0 of 2 done", 30)
    flows.idle(p.page)
    assert [c["kind"] for c in app.calls()] == ["practice_make", "quiz_check"], "write, then check: two calls"
    assert "New practice 1" in text(p)
    for _ in range(2):
        flows.answer_all(p, correct=True)
        flows.button(p, "Check")
        flows.button(p, "Next" if "Next" in text(p) else "See how it went")
    assert flows.wait_text(p.page, "Practice done")
    assert len(slots(app, email)[1].get("bank", [])) == 2, "kept for next time"
    assert flows.wait_text(p.page, "That's all the practice ready for today"), "no more today, said plainly"
    assert p.page.get_by_role("button", name="Another set").count() == 0
    assert app.calls("practice_make") == [] or len(app.calls("practice_make")) == 1, "once a day"


def test_practice_writing_failing_is_said_kindly(public_app, pages, clock):
    app = public_app
    app.set_llm(mode="500", fail_kinds=["practice_make"])
    day(clock, D + timedelta(days=3))
    p, email = person(app, pages, width=1440, pace="Light")
    seed_old_lesson(app, email)
    flows.open_app(p, app, "/practice")
    flows.button(p, "Start practice", wait=False)
    assert flows.wait_text(p.page, "busy", 40) or flows.wait_text(p.page, "couldn't", 5)
    assert "Traceback" not in text(p)
    app.set_llm()


def test_the_numbers_an_admin_sees_include_learning(public_app, pages):
    covers("W-records-prog_skills_open", "W-week-wk_skills")
    app = public_app
    p = pages(width=1440)
    flows.admin_sign_in(p, app)
    if flows.wait_text(p.page, "Get started", 3):
        flows.onboard(p)
    flows.open_app(p, app, "/account")
    assert flows.wait_text(p.page, "Insights")
    t = text(p)
    for row in ("Ideas got wrong, then right later", "Still known after two weeks", "Ideas mastered",
                "Practice sets finished", "Ideas explained back", "Questions to the coach"):
        assert row in t, row
