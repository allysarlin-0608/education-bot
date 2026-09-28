"""The same person in two tabs (or on two devices): nothing is written
twice, and one tab never erases what the other did."""
import itertools
import json
import time

import flows
from conftest import covers

_n = itertools.count()


def lessons(app, email):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    rows = [e for e in d["tables"]["learning_entries"] if e["user_id"] == uid]
    if not rows:
        return []
    raw = rows[0]["lessons"]
    return json.loads(raw) if isinstance(raw, str) else raw


def two_tabs(app, pages):
    email = f"tabs{next(_n)}-{int(time.time() * 1000)}@example.com"
    a = pages(width=1440)
    flows.sign_in(a, app, email=email)
    flows.onboard(a)
    flows.open_app(a, app)
    b = pages(width=1440)
    flows.public_sign_in(b, app, email, create=False)
    flows.open_app(b, app)
    assert flows.wait_text(b.page, "Start this lesson")
    return a, b, email


def test_a_lesson_started_in_one_tab_isnt_written_again_in_the_other(public_app, pages):
    covers("W-daily-start_this_lesson", "AI-daily-stream_reply")
    app = public_app
    a, b, email = two_tabs(app, pages)
    app.reset_calls()
    flows.start_lesson(a)
    first = lessons(app, email)[0]["lesson"]
    flows.button(b, "Start this lesson", wait=False)     # B still shows the button from before
    flows.idle(b.page, 40)
    assert len(app.calls("lesson")) == 1, f"the lesson was written twice: {app.calls()}"
    assert lessons(app, email)[0]["lesson"] == first
    assert flows.wait_text(b.page, "Take the quiz", 20), "B shows the lesson A started"


def test_a_quiz_passed_in_one_tab_isnt_undone_by_the_other(public_app, pages):
    covers("D-daily-save_entry-7", "W-daily-start_this_lesson")
    app = public_app
    a, b, email = two_tabs(app, pages)
    flows.pass_lesson(a)                                  # A: lesson 1 passed
    assert lessons(app, email)[0]["completed"] is True
    before = lessons(app, email)[0]
    app.reset_calls()
    # B still shows lesson 1 unstarted; its press must not undo A's work
    flows.button(b, "Start this lesson", wait=False)
    flows.idle(b.page, 40)
    saved = lessons(app, email)
    assert saved[0]["completed"] is True and saved[0]["quiz"]["score"] == 100, "the other tab undid a passed lesson"
    assert saved[0] == before, "lesson 1 changed under the other tab"
    assert len(app.calls("lesson")) <= 1, "at most the next lesson is written, once"
