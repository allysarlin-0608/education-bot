"""The setup on a fresh account, Back from every step and every change on
the confirmation, at phone and desktop widths: never Home before Start
learning, never a subject she didn't choose (fourth round, item 8); and the
setup run again on an account in use (admins, public site), losing nothing."""
import itertools
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()
NEVER = ("Philosophy", "Astronomy", "Jewelry", "Fashion", "Start this lesson")


def text(p):
    return p.page.evaluate("document.body.innerText")


def still_setup(p, where):
    t = text(p)
    assert not [w for w in NEVER if w in t], f"{where}: {[w for w in NEVER if w in t]}"
    assert "Traceback" not in t
    return t


def settings_row(app, email):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    return next(r for r in d["tables"]["user_settings"] if r["user_id"] == uid)


@pytest.mark.parametrize("width", [390, 1440])
def test_a_fresh_account_back_from_every_step(public_app, pages, width):
    covers("W-setup-ob_back", "W-setup-ob_change", "W-setup-ob_to_review")
    app = public_app
    app.set_llm()
    email = f"fresh{next(_n)}-{int(time.time() * 1000)}@example.com"
    p = pages(width=width)
    flows.sign_in(p, app, email=email)
    assert flows.wait_text(p.page, "Who are you?")
    flows.button(p, "Student")
    flows.button(p, "Get started")
    assert flows.wait_text(p.page, "What do you want to learn?")
    flows.button(p, "Back")                                        # want → who she is
    assert flows.wait_text(p.page, "Who are you?") and still_setup(p, "back to identity")
    flows.button(p, "Get started")
    flows.button(p, "I don't know yet")
    flows.tap(p, p.page.get_by_role("button", name="Arts", exact=False).first)
    flows.idle(p.page)
    flows.button(p, "Back")                                        # one level up
    assert flows.wait_text(p.page, "Technology") and still_setup(p, "directions")
    flows.button(p, "Back")                                        # out of the directions
    assert flows.wait_text(p.page, "Design my path")
    p.page.get_by_label("In your own words").fill("Read a company's financial statements")
    flows.button(p, "Design my path")
    assert flows.wait_text(p.page, "All of it, or some parts?", 40)
    flows.button(p, "Back")                                        # outline → what she asked for, as it was
    assert flows.wait_text(p.page, "Reading financial statements") and still_setup(p, "back to want")
    flows.button(p, "Continue")
    flows.tap(p, p.page.get_by_text("Yes, all of it", exact=True))
    flows.idle(p.page)
    flows.button(p, "Continue")
    assert flows.wait_text(p.page, "What's it for?")
    flows.button(p, "Back")                                        # what it's for → the outline, kept
    assert flows.wait_text(p.page, "16 lessons in 4 parts") and still_setup(p, "back to scope")
    flows.button(p, "Continue")
    flows.button(p, "For an exam")
    flows.button(p, "Continue")
    assert flows.wait_text(p.page, "Is this right?")
    flows.button(p, "Back")                                        # confirm → what it's for, kept
    assert flows.wait_text(p.page, "What's it for?") and still_setup(p, "back to purpose")
    flows.button(p, "Continue")
    for change, lands in (("Change who you are", "Who are you?"), ("Change what you learn", "What do you want"),
                          ("Change the parts", "All of it, or some parts?"), ("Change what it's for", "What's it for?")):
        flows.button(p, change)
        assert flows.wait_text(p.page, lands), change
        still_setup(p, change)
        assert not settings_row(app, email)["onboarded_at"], "a change never finishes the setup"
        if change == "Change what you learn":
            flows.button(p, "Continue")
        flows.button(p, "Back to confirm")
        assert flows.wait_text(p.page, "Is this right?") and "For an exam" in text(p), change
    flows.button(p, "Start learning")
    flows.idle(p.page, 30)
    assert flows.wait_text(p.page, "MADE FOR YOU", 20)
    t = text(p)
    assert "Reading financial statements" in t and not [w for w in NEVER[:4] if w in t]


def test_an_admin_runs_the_setup_again_and_loses_nothing(public_app, pages):
    covers("W-account-acct_rerun", "W-account-acct_rerun_go", "W-account-acct_rerun_cancel", "D-account-save_settings")
    app = public_app
    app.set_llm()
    p = pages(width=1180)
    flows.admin_sign_in(p, app)
    p.email = "admin@example.com"
    flows.onboard(p, subjects=("Philosophy",))
    before = settings_row(app, p.email)["subjects"]
    flows.open_app(p, app, "/account")
    flows.button(p, "Run the setup again")
    flows.button(p, "Cancel")
    assert settings_row(app, p.email)["onboarded_at"], "cancelled: nothing changed"
    flows.button(p, "Run the setup again")
    flows.button(p, "Run the setup now")
    flows.idle(p.page, 30)
    assert flows.wait_text(p.page, "Who are you?", 20), "the setup, as a new learner sees it"
    flows.set_up_goal(p, goal="Learn to sketch people")
    row = settings_row(app, p.email)
    assert row["onboarded_at"] and row["subjects"][1:] == before and row["subjects"][0].startswith("g-")
    assert flows.wait_text(p.page, "MADE FOR YOU", 20)
