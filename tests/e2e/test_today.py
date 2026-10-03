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
    covers("W-daily-next_lesson", "W-daily-next_lesson-2", "W-daily-see_the_quiz", "W-daily-key", "W-daily-keys_j",
           "W-daily-key-2", "W-daily-submit", "D-daily-save_entry-3", "D-daily-save_entry-4",
           "D-daily-save_entry-5", "D-daily-save_entry-6", "D-daily-save_entry-7",
           "W-daily-take_the_quiz_if_q_is_none_else_try_a_ne", "AI-daily-ask_json", "D-ui-save_entry")
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
        p.page.get_by_text("See the quiz", exact=True).click()
        assert flows.wait_text(p.page, "Your answer: It spins on its axis", 5), "the explanations are there"
        if p.page.get_by_role("button", name="Next lesson →").count():
            flows.button(p, "Next lesson →")
            assert flows.wait_text(p.page, f"Lesson {n + 1}", 10)
            continue
        flows.button(p, "See today's summary →")
        break
    assert flows.wait_text(p.page, "Today's done")
    t = text(p)
    assert f"All {n} lessons passed" in t and "Current streak: 1 day" in t
    entries = stored_entries(app, email)
    assert len(entries) == 1, entries
    stored = lessons_of(entries[0])
    assert entries[0]["completed"] is True
    assert len(stored) == n and all(s["completed"] and s["quiz"]["score"] == 100 for s in stored)
    assert t.count("· 100%") == n, "the summary's scores are the stored ones"


def test_a_failed_quiz_shows_what_was_missed_and_a_new_set(public_app, pages):
    covers("W-daily-see_what_you_missed", "W-daily-take_the_quiz_if_q_is_none_else_try_a_ne")
    app = public_app
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    flows.take_quiz(p, correct=False)
    t = text(p)
    assert "You need 80%" in t and "See what you missed" in t
    assert "Why it's marked wrong" in t and "A good answer" in t
    q = lessons_of(stored_entries(app, email)[0])[0]["quiz"]
    assert f"{q['score']}%" in t and q["score"] < 80
    app.reset_calls()
    flows.button(p, "Try a new quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    assert len(app.calls("quiz")) == 1


def test_answers_survive_a_reload(public_app, pages):
    covers("D-daily-save_entry-6", "W-daily-key")
    app = public_app
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    first = p.page.locator('[data-testid="stRadio"]').first
    flows.tap(p, first.get_by_text("Solar flares", exact=True))
    p.page.locator('textarea[placeholder^="Answer in a sentence"]').first.fill("Because it spins.")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    p.page.wait_for_timeout(500)
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Submit answers", 20)
    first = p.page.locator('[data-testid="stRadio"]').first
    assert first.locator("input:checked").count() == 1
    assert first.get_by_role("radio", name="Solar flares").is_checked(), "a chosen answer was lost on reload"
    assert p.page.locator('textarea[placeholder^="Answer in a sentence"]').first.input_value() == "Because it spins."


def test_submitting_with_open_questions_names_them(public_app, pages):
    covers("W-daily-submit")
    app = public_app
    p, _ = fresh(app, pages)
    flows.start_lesson(p)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    flows.button(p, "Submit answers")
    assert flows.wait_text(p.page, "Answer every question first (still open: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)")


def test_marking_fails_then_mark_my_answers(public_app, pages):
    covers("W-daily-mark_my_answers", "W-daily-coach_retry", "AI-quizgen-ask_json-4")
    app = public_app
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    app.set_llm(mode="500")                               # the marking call fails
    flows.idle(p.page)
    page = p.page
    for g in range(page.locator('[data-testid="stRadio"]').count()):
        flows.tap(p, page.locator('[data-testid="stRadio"]').nth(g).get_by_text("It spins on its axis", exact=True))
        page.wait_for_timeout(100)
    rights = ["The line Earth spins around", "One spin a day", "One trip around the Sun", "When the Sun comes into view"]
    for j in range(page.locator('[data-testid="stSelectbox"]').count()):
        flows.choose(p, page.locator('[data-testid="stSelectbox"]').nth(j), rights[j])
    for j in range(page.locator('textarea[placeholder^="Answer in a sentence"]').count()):
        page.locator('textarea[placeholder^="Answer in a sentence"]').nth(j).fill("Earth spins on its axis.")
        page.keyboard.press("Tab")
    flows.idle(page)
    flows.button(p, "Submit answers", wait=False)
    assert flows.wait_text(page, "busy", 40)
    assert "Your answers are saved" in text(p)
    stored = lessons_of(stored_entries(app, email)[0])[0]["quiz"]
    assert stored["answers"] is not None, "the answers were kept for marking"
    app.set_llm()
    flows.button(p, "Retry", wait=False)
    assert flows.wait_text(page, "Passed with 100%", 40)


def test_reflection_is_saved(public_app, pages):
    covers("W-daily-my_thoughts_on_the_question_to_explore_o", "W-daily-reflection", "W-daily-save_my_thoughts",
           "D-daily-save_entry-8")
    app = public_app
    p, email = fresh(app, pages)
    flows.start_lesson(p)
    p.page.get_by_text("My thoughts on the question to explore", exact=False).click()
    box = p.page.get_by_label("Question to explore")
    box.fill("  I think the air moves with us.  ")
    p.page.keyboard.press("Tab")
    flows.button(p, "Save my thoughts")
    assert flows.wait_text(p.page, "Saved.", 5)
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
