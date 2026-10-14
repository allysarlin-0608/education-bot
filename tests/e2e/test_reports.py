"""Report a problem, in a real browser (audit stage 2): a learner reports a
lesson from Home in two taps; an admin sees it under Insights → Reported
problems, without who sent it."""
import time

import flows
from conftest import covers


def text(p):
    return p.page.evaluate("document.body.innerText")


def test_a_learner_reports_a_lesson_and_an_admin_sees_it(public_app, pages):
    covers("W-report_ui-menu", "W-report_ui-why", "W-report_ui-send")
    app = public_app
    app.set_llm()
    p = pages(width=390)
    email = f"report-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",))
    flows.start_lesson(p)
    flows.tap(p, p.page.locator('[class*="st-key-rep_lesson_"] button').first)
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_text("It's unclear", exact=True).last)
    flows.idle(p.page)
    flows.button(p, "Send")
    assert flows.wait_text(p.page, "Thanks. We'll check it.", 15)
    q = pages(width=1440)
    flows.admin_sign_in(q, app)
    if flows.wait_text(q.page, "Get started", 3):
        flows.onboard(q)
    flows.open_app(q, app, "/account")
    assert flows.wait_text(q.page, "Reported problems", 20)
    t = text(q)
    assert "It's unclear" in t and "the lesson" in t and email not in t.split("Reported problems")[1], "never who"


def test_an_ai_too_busy_is_counted_and_an_admin_sees_it(public_app, pages):
    """Before more people are invited: when the AI is too busy she is told to
    try again, and an admin sees under Insights → AI waits how often (never who)."""
    app = public_app
    app.set_llm()
    q = pages(width=1440)
    flows.admin_sign_in(q, app)
    if flows.wait_text(q.page, "Get started", 3):
        flows.onboard(q)
    flows.open_app(q, app, "/account")
    assert flows.wait_text(q.page, "AI waits", 20)
    before = busy_count(q)                    # (other tests on this server may have met a busy AI too)
    p = pages(width=1440)
    email = f"busy-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",))
    app.set_llm(mode="429")
    flows.open_app(p, app)
    flows.button(p, "Start this lesson", wait=False)
    assert flows.wait_text(p.page, "busy", 60)
    app.set_llm()
    flows.open_app(q, app, "/account")
    assert flows.wait_text(q.page, "AI waits", 20)
    part = text(q).split("AI waits")[1]
    assert "Too busy: told to try again" in part and busy_count(q) >= before + 1, part[:400]
    assert email not in part, "never who"


def busy_count(q):
    """How many people met a busy AI, as Insights says."""
    import re
    m = re.search(r"(\d+) (?:person|people) met it\. Many", text(q))     # ("Nobody met it": 0)
    return int(m.group(1)) if m else 0
