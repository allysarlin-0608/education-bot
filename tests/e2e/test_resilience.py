"""When things go wrong: a slow network, going offline and back, the
database failing to read or write, and the sign-in service being down.
Each time: a clear message, nothing lost, and the app recovers."""
import itertools
import time

import flows
from conftest import covers

_n = itertools.count()


def person(app, pages, width=1440):
    p = pages(width=width)
    p.email = f"res{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=p.email)
    flows.onboard(p)
    flows.open_app(p, app)
    app.set_llm()
    return p


def text(p):
    return p.page.evaluate("document.body.innerText")


def entries(app, email):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    return [e for e in d["tables"]["learning_entries"] if e["user_id"] == uid]


def test_a_slow_network_still_works(public_app, pages):
    covers("W-daily-start_this_lesson")
    app = public_app
    p = person(app, pages)
    cdp = p.ctx.new_cdp_session(p.page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 400,
                                                  "downloadThroughput": 50_000, "uploadThroughput": 20_000})
    t0 = time.time()
    flows.go(p, app, "Record")
    assert flows.wait_text(p.page, "Backup and restore", 30)
    flows.go(p, app, "Home")
    flows.start_lesson(p)
    assert time.time() - t0 < 90
    assert "Traceback" not in text(p)


def test_offline_and_back_keeps_the_answers(public_app, pages):
    covers("D-daily-save_entry-6")
    app = public_app
    p = person(app, pages)
    flows.start_lesson(p)
    flows.button(p, "Take the quiz", wait=False)
    assert flows.wait_text(p.page, "Submit answers", 40)
    flows.idle(p.page)
    flows.tap(p, p.page.locator('[data-testid="stRadio"]').first.get_by_text("Solar flares", exact=True))
    flows.idle(p.page)
    p.ctx.set_offline(True)
    p.page.wait_for_timeout(3000)
    p.ctx.set_offline(False)
    p.page.wait_for_timeout(4000)
    flows.idle(p.page, 40)
    # the session may have been replaced on reconnect: the answer is still there either way
    if not flows.wait_text(p.page, "Submit answers", 10):
        flows.open_app(p, app)
    assert flows.wait_text(p.page, "Submit answers", 20)
    first = p.page.locator('[data-testid="stRadio"]').first
    assert first.get_by_role("radio", name="Solar flares").is_checked(), "the answer given before going offline was lost"


def test_a_failed_save_says_so_and_the_next_one_catches_up(public_app, pages):
    covers("D-daily-save_entry")
    app = public_app
    p = person(app, pages)
    app.post("/__fail", {"method": "POST", "table": "learning_entries", "times": 1})
    flows.start_lesson(p)
    assert flows.wait_text(p.page, "wasn't saved", 10), "a failed save must be reported"
    assert entries(app, p.email) == [], "the injected failure didn't happen"
    # the next save writes the whole entry, lesson included
    flows.idle(p.page)
    p.page.get_by_text("My thoughts on the question to explore", exact=False).click()
    flows.idle(p.page)
    p.page.get_by_label("Question to explore").fill("A thought.")
    p.page.keyboard.press("Tab")
    flows.button(p, "Save my thoughts")
    assert flows.wait_text(p.page, "Saved.", 10)
    saved = entries(app, p.email)
    assert len(saved) == 1 and saved[0]["reflection"] == "A thought."
    lessons = saved[0]["lessons"]
    assert lessons[0]["lesson"], "the lesson written while the save failed was caught up"


def test_the_database_failing_to_read_shows_a_message(public_app, pages):
    covers("W-topnav-p")
    app = public_app
    p = person(app, pages)
    app.post("/__fail", {"method": "GET", "table": "learning_entries", "times": 1})
    flows.open_app(p, app)
    t = text(p)
    assert "Traceback" not in t
    assert "database" in t.lower() or "try again" in t.lower() or "refresh" in t.lower(), t[:500]
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Start this lesson", 20), "the app recovers once the database answers"


def test_the_invitation_check_failing_is_explained(public_app, pages):
    covers("W-auth-si_form")
    app = public_app
    p = person(app, pages)
    app.post("/__fail", {"method": "GET", "table": "allowed_users", "times": 2})
    app.post("/__fail", {"method": "GET", "table": "app_admins", "times": 2})
    p.page.context.clear_cookies()
    flows.public_sign_in(p, app, p.email, create=False)
    t = text(p)
    assert "Traceback" not in t
    assert "Couldn't check your invitation" in t or "Start this lesson" in t
