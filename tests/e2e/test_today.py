"""Today: a whole day of lessons, quizzes (pass, fail, missing answers,
marking errors), answers kept across a reload, the chat, the reflection,
reviewing an earlier lesson, locked lessons, and the subject's world.
Numbers shown are checked against what was stored."""
import itertools
import json
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()


def fresh(app, pages, width=1440, **kw):
    p = pages(width=width, **kw)
    email = f"today{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p)
    flows.open_app(p, app)
    app.set_llm()
    return p, email


def text(p):
    return p.page.evaluate("document.body.innerText")


def stored_entries(app, email):
    """Today's stored entries, from the database (public) or the file (personal)."""
    if app.mode == "public":
        d = app.get("/__dump")
        uid = next(u["id"] for u in d["users"] if u["email"] == email)
        return [e for e in d["tables"]["learning_entries"] if e["user_id"] == uid]
    data = json.loads((app.state / "learning_log.json").read_text())
    return data["entries"] if isinstance(data, dict) else data


def lessons_of(entry):
    raw = entry["lessons"]
    return json.loads(raw) if isinstance(raw, str) else raw


@pytest.mark.parametrize("mode", ["public", "personal"])
def test_a_whole_day(mode, pages, request):
    covers("W-daily-next_lesson", "W-daily-next_lesson-2", "W-daily-see_the_check", "W-daily-key", "W-daily-keys_j",
           "W-daily-key-2", "W-daily-submit", "D-daily-save_entry-3", "D-daily-save_entry-4",
           "D-daily-save_entry-5", "D-daily-save_entry-6", "D-daily-save_entry-7", "D-daily-save_day", "D-daily-save_day-3",
           "W-daily-take_check", "AI-daily-ask_json", "D-ui-save_entry")
    app = request.getfixturevalue(f"{mode}_app")
    if mode == "personal":
        (app.state / "learning_log.json").unlink(missing_ok=True)
        (app.state / "user_settings.json").unlink(missing_ok=True)
    p, email = fresh(app, pages)
    total = text(p).count("Lesson 1 of ")
    assert total, "the day's progress label"
    n = 0
    while True:
        flows.pass_lesson(p)
        n += 1
        t = text(p)
        assert "Passed with 100%" in t
        p.page.get_by_text("See the check", exact=True).click()
        assert flows.wait_text(p.page, "Your answer: It spins on its axis", 5), "the explanations are there"
        if p.page.get_by_role("button", name="Next lesson →").count():
            flows.button(p, "Next lesson →")
            assert flows.wait_text(p.page, f"Lesson {n + 1}", 10)
            continue
        flows.button(p, "Finish today →")
        break
    assert flows.wait_text(p.page, "Today's done")
    t = text(p)
    assert (f"All {n} lessons passed" if n > 1 else "The lesson is passed") in t
    assert "streak" not in t.lower(), "the streak is in the Learning Record, not Home"
    entries = stored_entries(app, email)
    assert len(entries) == 1, entries
    stored = lessons_of(entries[0])
    assert entries[0]["completed"] is True
    assert len(stored) == n and all(s["completed"] and s["quiz"]["score"] == 100 for s in stored)
    scores = p.page.evaluate("() => [...document.querySelectorAll('.done-list .q')].map(e => e.innerText.trim())")
    assert scores == ["100%"] * n, "the summary's scores are the stored ones"


def test_a_failed_quiz_shows_what_was_missed_and_a_new_set(public_app, pages):
    covers("W-daily-see_what_you_missed", "W-daily-take_check")
    app = public_app
    app.quiz_prep(False)                    # the new set written on the press, counted below
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    flows.take_quiz(p, correct=False)
    t = text(p)
    assert "You need 80%" in t and "See what you missed" in t
    assert "Read the lesson again" in t, "a way back to the lesson"
    q = lessons_of(stored_entries(app, email)[0])[0]["quiz"]
    assert f"{q['score']}%" in t and q["score"] < 80
    app.reset_calls()
    flows.button(p, "Try a new set", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    assert len(app.calls("quiz")) == 1


def test_answers_survive_a_reload(public_app, pages):
    covers("D-daily-save_entry-6", "W-daily-key")
    app = public_app
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    flows.to_check(p)
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    first = p.page.locator('[data-testid="stRadio"]').first
    flows.tap(p, first.get_by_text("Solar flares", exact=True))
    p.page.locator('input[placeholder="The missing word or phrase"]').first.fill("spin")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    p.page.wait_for_timeout(500)
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Submit answers", 20)
    first = p.page.locator('[data-testid="stRadio"]').first
    assert first.locator("input:checked").count() == 1
    assert first.get_by_role("radio", name="Solar flares").is_checked(), "a chosen answer was lost on reload"
    assert p.page.locator('input[placeholder="The missing word or phrase"]').first.input_value() == "spin"


def test_submitting_with_open_questions_names_them(public_app, pages):
    covers("W-daily-submit")
    app = public_app
    p, _ = fresh(app, pages)
    flows.start_lesson(p)
    flows.to_check(p)
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    flows.button(p, "Submit answers")
    assert flows.wait_text(p.page, "Answer every question first (still open: 1, 2, 3, 4, 5, 6)")


def test_marking_fails_then_mark_my_answers(public_app, pages):
    """A quiz from before, submitted with a written answer the marking of
    which didn't go through: marked when she presses, retried on a failure."""
    covers("W-daily-mark_my_answers", "W-daily-coach_retry", "AI-quizgen-ask_json-4")
    from datetime import date
    app = public_app
    day = date(2026, 11, 2)
    app.set_clock(day, "02:00:00")
    try:
        p, email = fresh(app, pages)
        qs = [{"type": "choice", "question": f"Seeded question {k + 1}?", "options": ["Right", "Wrong", "Also wrong", "No"],
               "answer": 0, "why": "Seeded."} for k in range(9)]
        qs.append({"type": "short", "question": "Why do we have day and night?", "answer": "Earth spins.", "why": "."})
        q = {"id": "old1", "version": 2, "questions": qs, "answers": [0] * 9 + ["Because Earth spins on its axis."],
             "marks": [1] * 9 + [None], "feedback": [""] * 10, "score": None, "attempts": 0, "best": None, "draft": None}
        slot = {"n": 1, "title": "What philosophy is", "unit": "", "kickoff": "k", "lesson": "【Key Idea】 Seeded key idea.",
                "followups": [], "completed": False, "quiz": q}
        app.seed_entries(email, [{"date": day.isoformat(), "topic": "philosophy", "session_number": 1, "level": "Beginner",
                                  "completed": False, "title": "", "followup_question": "", "reflection": "",
                                  "lesson": "", "followups": [], "kickoff": "", "lessons": [slot]}])
        flows.open_app(p, app)
        page = p.page
        assert flows.wait_text(page, "Your answers are saved", 20)
        app.set_llm(mode="500")                               # the marking call fails
        flows.button(p, "Mark my answers", wait=False)
        assert flows.wait_text(page, "busy", 40)
        app.set_llm()
        flows.button(p, "Retry", wait=False)
        assert flows.wait_text(page, "Passed with 100%", 40)
    finally:
        app.set_clock(None)


def test_reflection_is_saved(public_app, pages):
    covers("W-daily-reflect", "W-session_ui-jol", "D-daily-save_day-5")
    app = public_app
    p, email = fresh(app, pages)
    flows.pass_day(p)
    flows.reflect(p, "  I think the air moves with us.  ")
    assert stored_entries(app, email)[0]["reflection"] == "I think the air moves with us."


def test_chat_reply_is_saved_with_the_lesson(public_app, pages):
    covers("W-daily-ask_about_lesson", "D-daily-save_entry-2", "AI-daily-stream_reply-2")
    app = public_app
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    p.page.get_by_placeholder("Ask about Lesson").fill("Why don't we feel it?")
    p.page.keyboard.press("Enter")
    assert flows.wait_text(p.page, "Good question", 30)
    flows.idle(p.page)
    followups = lessons_of(stored_entries(app, email)[0])[0]["followups"]
    assert [m["role"] for m in followups] == ["user", "assistant"]
    assert followups[0]["content"] == "Why don't we feel it?"
    flows.open_app(p, app)                                # and it's still there after a reload
    assert flows.wait_text(p.page, "Good question", 10)


def test_blank_chat_message_is_ignored(public_app, pages):
    covers("W-daily-ask_about_lesson")
    app = public_app
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    p.page.get_by_placeholder("Ask about Lesson").fill("    ")
    p.page.keyboard.press("Enter")
    flows.idle(p.page)
    assert not app.calls("followup")


def test_steps_locked_review_and_back(public_app, pages):
    covers("W-daily-name", "W-daily-back_to_current", "W-daily-back_to_current-2")
    app = public_app
    p, _ = fresh(app, pages)
    steps = p.page.locator('.st-key-lesson_steps button, .st-key-lesson_steps_flow button')
    flows.tap(p, steps.nth(1))                            # locked
    assert flows.wait_text(p.page, "Unlocks after you pass Lesson", 5), "a locked lesson says why"
    assert "Lesson 1:" in text(p)
    flows.pass_lesson(p)
    flows.button(p, "Next lesson →")
    flows.tap(p, p.page.locator('.st-key-lesson_steps button, .st-key-lesson_steps_flow button').nth(0))
    flows.idle(p.page)
    assert flows.wait_text(p.page, "You're reviewing Lesson", 10)
    back = p.page.get_by_role("button", name="Back to Lesson", exact=False)
    flows.tap(p, back.first)
    flows.idle(p.page)
    assert "You're reviewing" not in text(p)


def test_enter_the_subjects_world(public_app, pages):
    covers("W-daily-today_world")
    app = public_app
    p, _ = fresh(app, pages)
    flows.button(p, "Enter Philosophy", exact=False)
    flows.idle(p.page)
    assert "/subject" in p.page.url and "subject=philosophy" in p.page.url


@pytest.mark.parametrize("width", [390, 768, 1024])
def test_a_lesson_and_quiz_on_touch_widths(public_app, pages, width):
    covers("W-daily-start_this_lesson", "W-daily-submit")
    app = public_app
    p, _ = fresh(app, pages, width=width)
    flows.pass_lesson(p)
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontal scroll"
