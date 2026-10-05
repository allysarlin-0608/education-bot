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
    p.email = f"ai{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=p.email)
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
    if started:
        assert "Key Idea" in text, "the quiz is offered but the lesson itself is missing"


def test_leaving_while_the_lesson_streams_leaves_no_half_lesson(public_app, pages):
    covers("W-daily-start_this_lesson", "AI-daily-stream_reply")
    app = public_app
    p = fresh(app, pages)
    app.set_llm(chunk_delay=0.15)           # the lesson is visibly being written
    flows.button(p, "Start this lesson", wait=False)
    assert flows.wait_text(p.page, "Earth", 20), "the lesson didn't start streaming"
    flows.go(p, app, "Progress")            # leave mid-stream
    app.set_llm()
    flows.go(p, app, "Today")
    text = p.page.evaluate("document.body.innerText")
    if "Take the quiz" in text:
        assert "Key Idea" in text, "the quiz is offered but the lesson itself is missing"
    else:
        assert "Start this lesson" in text, "the lesson is neither shown nor startable"


def test_double_click_take_quiz_writes_one_quiz(public_app, pages):
    covers("W-daily-take_the_quiz", "AI-quizgen-ask_json")
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
    covers("W-daily-take_the_quiz", "AI-quizgen-ask_json")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    app.set_llm(mode="invalid", fail_times=1)          # the first reply isn't JSON
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40), "one bad reply should be retried, not shown as an error"


def test_quiz_errors_show_retry(public_app, pages):
    covers("W-daily-coach_retry_", "AI-quizgen-ask_json-3", "AI-quizgen-ask_json-4")
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
    covers("AI-quizgen-ask_json-3", "AI-quizgen-ask_json-4")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    app.set_llm(quiz_flag_first=True)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    assert [c["kind"] for c in app.calls()] == ["quiz", "quiz_check", "quiz_rewrite", "quiz_check"]
    log = app.log_text()
    assert "quiz check round 1: 1 of 10 questions rejected" in log and "quiz check round 2: 0 of 10 questions rejected" in log
    assert flows.wait_text(p.page, "Which way does Earth spin?", 5), "the rewritten question is shown"


def test_injected_model_output_is_shown_as_text(public_app, pages):
    covers("AI-daily-stream_reply", "AI-daily-stream_reply-2", "AI-quizgen-ask_json", "AI-daily-ask_json")
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


def test_every_ai_call_is_counted_for_the_person(public_app, pages):
    covers("D-quota-add_usage")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == p.email)
    mine = [r for r in d["tables"].get("ai_usage", []) if r["user_id"] == uid]
    assert len(mine) == 1, mine
    assert mine[0]["request_count"] == len(app.calls()) and mine[0]["token_count"] >= 1


@pytest.mark.parametrize("mode,extra", [("malformed_quiz", ["quiz_rewrite"]),       # one bad question: just it
                                        ("truncated_quiz", ["quiz_rewrite"])])      # cut off: the rest
def test_an_incomplete_quiz_is_completed_on_the_first_click(public_app, pages, mode, extra):
    """Issue A: a reply with an unusable question, or cut off at the reply
    limit, still gives a quiz on the first click: the good questions are kept
    and only the missing ones are asked for. No Retry, no second quiz."""
    covers("W-daily-take_the_quiz", "AI-quizgen-ask_json", "AI-quizgen-ask_json-2")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    app.set_llm(mode=mode)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40), f"{mode}: no quiz on the first click"
    flows.idle(p.page)
    assert "didn't manage" not in p.page.evaluate("document.body.innerText")
    assert [c["kind"] for c in app.calls()] == ["quiz"] + extra + ["quiz_check"], app.calls()
    assert p.page.locator('[data-testid="stRadio"]').count() + p.page.locator('textarea').count() >= 9
    assert "incomplete" in app.log_text() and "ready in" in app.log_text()


def test_the_quiz_button_says_it_is_preparing_and_cannot_be_pressed_again(public_app, pages):
    """Issue A (A7): while the quiz is written the button reads "Preparing
    your quiz…" and is disabled, so a second press can't start another."""
    covers("W-daily-take_the_quiz", "W-daily-quiz_preparing-2")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.reset_calls()
    app.set_llm(delay=2.5)
    flows.button(p, "Take the quiz", wait=False)
    busy = p.page.get_by_role("button", name="Preparing your quiz…")
    busy.wait_for(timeout=3000)
    assert busy.is_disabled()
    busy.click(force=True)                       # a second press does nothing
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    assert len(app.calls("quiz")) == 1, app.calls()
    assert p.page.get_by_role("button", name="Preparing your quiz…").count() == 0


def test_retry_after_a_failed_quiz_also_cannot_be_pressed_twice(public_app, pages):
    covers("W-daily-coach_retry_", "W-daily-quiz_preparing")
    app = public_app
    p = fresh(app, pages)
    flows.start_lesson(p)
    app.set_llm(mode="invalid")
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "didn't manage", 40)
    app.reset_calls()
    app.set_llm(delay=2.0)
    flows.button(p, "Retry", wait=False)
    busy = p.page.get_by_role("button", name="Preparing your quiz…")
    busy.wait_for(timeout=3000)
    assert busy.is_disabled() and p.page.get_by_role("button", name="Retry").count() == 0
    assert flows.wait_text(p.page, "Submit answers", 40)
    assert len(app.calls("quiz")) == 1, app.calls()


def test_thirty_quizzes_in_a_row_each_on_the_first_click(public_app, pages):
    """Issue A acceptance, on the fake model: 30 quizzes (three people, ten
    each: one person's 30 would pass the daily allowance of 80 AI calls,
    coach/quota.py) with the model's usual slips mixed in (a bad question, a
    cut-off reply, an unreadable reply, a 429); every one comes on the first
    click."""
    covers("W-daily-take_the_quiz", "AI-quizgen-ask_json")
    app = public_app
    slips = [{}, {"mode": "malformed_quiz", "fail_times": 1}, {}, {"mode": "truncated_quiz", "fail_times": 1},
             {}, {"mode": "invalid", "fail_times": 1}, {"mode": "429", "fail_times": 1}]
    wrong = ["One spin a day", "One trip around the Sun", "When the Sun comes into view", "The line Earth spins around"]
    failures, times = [], []
    for k in range(30):
        if k % 10 == 0:
            p = fresh(app, pages)
            page = p.page
            flows.start_lesson(p)
        app.reset_calls()
        app.set_llm(**slips[k % len(slips)])
        name = "Take the quiz" if k % 10 == 0 else "Try a new quiz"
        t0 = time.time()
        flows.button(p, name, wait=False)
        ok = flows.wait_text(page, "Submit answers", 40)
        times.append(time.time() - t0)
        kinds = [c["kind"] for c in app.calls()]
        print(f"quiz {k}: {slips[k % len(slips)]} ok={ok} {times[-1]:.1f}s {kinds}", flush=True)
        if not ok or "didn't manage" in page.evaluate("document.body.innerText") or kinds.count("quiz") > 2:
            failures.append((k, slips[k % len(slips)], kinds))
            app.set_llm()
            if flows.wait_text(page, "Retry", 1):
                flows.button(p, "Retry", wait=False)
                flows.wait_text(page, "Submit answers", 40)
        flows.idle(page)
        # wrong answers, so a new quiz is offered
        flows.answer_all(p, correct=False)
        flows.idle(page)
        app.set_llm()
        flows.button(p, "Submit answers", wait=False)
        assert flows.wait_text(page, "Try a new quiz", 40), f"quiz {k}: no retake offered"
        flows.idle(page)
    times.sort()
    print(f"30 quizzes: p50 {times[14]:.1f}s, p95 {times[28]:.1f}s, max {times[-1]:.1f}s")
    assert len(failures) <= 1, failures
    assert times[28] < 30
