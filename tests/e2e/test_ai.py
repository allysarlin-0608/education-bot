"""AI actions: loading states, errors with Retry, no duplicate calls, content checks."""
import itertools
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()


def fresh(app, pages, width=1440, **kw):
    """A new person, set up, on Today."""
    p = pages(width=width, **kw)
    flows.sign_in(p, app, email=f"ai{next(_n)}-{int(time.time() * 1000)}@example.com")
    flows.onboard(p)
    flows.open_app(p, app)
    app.set_llm()
    app.reset_calls()
    return p


def test_start_lesson_shows_progress_fast_and_writes_once(public_app, pages):
    covers("W-daily-start_this_lesson", "AI-daily-stream_reply")
    app = public_app
    p = fresh(app, pages)
    app.set_llm(delay=2.0)
    loc = p.page.get_by_role("button", name="Start this lesson", exact=True)
    total, feedback = flows.timed_click(p, "start_lesson", loc, lambda pg: "Take the quiz" in pg.evaluate("document.body.innerText"))
    assert feedback is not None and feedback < 100, f"no visible feedback within 100 ms ({feedback} ms)"
    assert len(app.calls("lesson")) == 1


def test_double_click_start_lesson_writes_it_once(public_app, pages):
    covers("W-daily-start_this_lesson")
    app = public_app
    p = fresh(app, pages)
    app.set_llm(delay=1.5)
    p.page.get_by_role("button", name="Start this lesson", exact=True).dblclick()
    assert flows.wait_text(p.page, "Take the quiz", 40)
    flows.idle(p.page)
    assert len(app.calls("lesson")) == 1, app.calls()


def test_clicking_elsewhere_while_a_lesson_is_written_loses_nothing(public_app, pages):
    covers("W-daily-start_this_lesson", "W-topnav-")
    app = public_app
    p = fresh(app, pages)
    app.set_llm(delay=3.0)
    flows.button(p, "Start this lesson", wait=False)
    p.page.wait_for_timeout(700)
    flows.go(p, app, "Progress")            # leave while it's being written
    app.set_llm()
    flows.go(p, app, "Today")
    text = p.page.evaluate("document.body.innerText")
    started = "Take the quiz" in text
    can_start = "Start this lesson" in text
    assert started or can_start, "the lesson is neither shown nor startable"
    if not started:
        # nothing half-written: the lesson area is empty only because it hasn't started
        assert "Quiz" not in text.split("Lesson 1:")[-1][:400], "a half-started lesson shows the quiz without a lesson"


def test_double_click_take_quiz_writes_one_quiz(public_app, pages):
    covers("W-daily-take_the_quiz", "AI-daily-ask_json")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    app.set_llm(delay=1.0)
    p.page.get_by_role("button", name="Take the quiz", exact=True).dblclick()
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    assert len(app.calls("quiz")) == 1, app.calls()


@pytest.mark.parametrize("mode,expect", [("429", "busy"), ("500", "busy"), ("timeout", "busy"),
                                         ("413", "didn't manage"), ("empty", "didn't manage"),
                                         ("broken_stream", "didn't manage")])
def test_lesson_errors_show_a_message_and_retry_works(public_app, pages, mode, expect):
    covers("W-daily-coach_retry_", "AI-daily-stream_reply")
    app = public_app
    p = fresh(app, pages)
    app.set_llm(mode=mode)
    t0 = time.time()
    flows.button(p, "Start this lesson", wait=False)
    assert flows.wait_text(p.page, expect, 35), f"{mode}: no friendly message"
    assert time.time() - t0 < 32, f"{mode}: the message took {time.time() - t0:.0f} s"
    text = p.page.evaluate("document.body.innerText")
    assert "Traceback" not in text and "Error code" not in text and "groq" not in text.lower()
    app.set_llm()
    flows.button(p, "Retry", wait=False)
    assert flows.wait_text(p.page, "Take the quiz", 40), f"{mode}: Retry didn't write the lesson"


def test_an_unreadable_quiz_reply_is_retried_once_automatically(public_app, pages):
    covers("W-daily-take_the_quiz", "AI-daily-ask_json")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    app.set_llm(mode="invalid", fail_times=1)          # the first reply isn't JSON
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40), "one bad reply should be retried, not shown as an error"


def test_quiz_errors_show_retry(public_app, pages):
    covers("W-daily-coach_retry_", "AI-daily-ask_json-2", "AI-daily-ask_json-3")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.set_llm(mode="invalid")                        # never readable
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "didn't manage", 40)
    app.set_llm()
    flows.button(p, "Retry", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)


def test_the_answer_check_rewrites_a_flagged_question(public_app, pages):
    covers("AI-daily-ask_json-2", "AI-daily-ask_json-3")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    app.set_llm(quiz_flag_first=True)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    assert [c["kind"] for c in app.calls()] == ["quiz", "quiz_check", "quiz_rewrite", "quiz_check"]
    assert flows.wait_text(p.page, "Which way does Earth spin?", 5), "the rewritten question is shown"


def test_injected_model_output_is_shown_as_text(public_app, pages):
    covers("AI-daily-stream_reply", "AI-daily-stream_reply-2", "AI-daily-ask_json", "AI-daily-ask_json-4")
    app = public_app
    p = fresh(app, pages)
    app.set_llm(inject=True)
    flows.start_lesson(p)
    page = p.page
    assert page.locator("img[src='x']").count() == 0, "an injected <img> was rendered"
    assert page.locator("a[href^='javascript:']").count() == 0, "an injected javascript: link was rendered"
    assert page.locator("script:has-text('alert(\"xss\")')").count() == 0
    # the chat reply too
    page.get_by_placeholder("Ask about Lesson").fill("Why don't we feel it?")
    page.keyboard.press("Enter")
    assert flows.wait_text(page, "Good question", 30)
    flows.idle(page)
    assert page.locator("img[src='x']").count() == 0 and page.locator("a[href^='javascript:']").count() == 0
    # the pages fixture fails the test if alert() ran


def test_lesson_text_has_no_raw_markers(public_app, pages):
    covers("AI-daily-stream_reply")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    text = p.page.evaluate("document.body.innerText")
    for bad in ("【", "】", "**", "##", "|---"):
        assert bad not in text, f"raw {bad!r} in the lesson as shown"
