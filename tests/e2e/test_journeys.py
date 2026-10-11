"""Whole journeys, start to finish, as a new learner and as one coming back,
at phone, iPad and desktop widths: every page on the way loads without an
error, nothing scrolls sideways, each step lands where it should and shows
what she chose, and the obvious next step is there.

1. Sign in → setup (who she is, a goal of her own) → first lesson → quiz
   failed, then passed → the rest of the day → the next day → review, course
   map, knowledge map, record, plan, courses, path, account, practice, week.
2. Plan: pace, a subject added and taken out, reading on, a goal added,
   paused, resumed, paused and removed; account; sign out and back in."""
import time
from datetime import date, timedelta

import pytest

import flows
from conftest import covers

D = date(2026, 11, 2)


def text(p):
    return p.page.evaluate("document.body.innerText")


def sound(p, where):
    """The page as she sees it: no error, nothing sideways, at the top."""
    flows.idle(p.page)
    t = text(p)
    assert "Traceback" not in t and "Something went wrong" not in t, where
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"{where}: sideways"
    return t


@pytest.mark.parametrize("width", [390, 820, 1440])
def test_a_new_learner_from_sign_in_to_her_second_day(public_app, pages, width):
    covers("W-topnav-p")
    app = public_app
    app.set_llm()
    app.set_clock(D)
    p = pages(width=width)
    flows.sign_in(p, app, email=f"jny{width}-{int(time.time() * 1000)}@example.com")
    assert "Who are you?" in sound(p, "welcome")
    flows.button(p, "Working adult")
    flows.button(p, "Get started")
    assert p.page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollTop") < 40, \
        "a new step opens at its top"
    p.page.get_by_label("In your own words").fill("Read a company's financial statements")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    flows.button(p, "Design my path", wait=False)
    assert flows.wait_text(p.page, "All of it, or some parts?", 40)
    sound(p, "outline")
    flows.tap(p, p.page.get_by_text("Yes, all of it", exact=True))
    flows.idle(p.page)
    flows.button(p, "Continue")
    sound(p, "what it's for")
    flows.tap(p, p.page.locator('[class*="st-key-obp_pp_0"] button').first)
    flows.idle(p.page)
    flows.button(p, "Continue")
    t = sound(p, "confirm")
    assert "Is this right?" in t and "Reading financial statements" in t
    assert "Price" not in t and "Plus" not in t
    flows.button(p, "Start learning")
    flows.idle(p.page, 30)
    flows.open_app(p, app)
    assert "Start this lesson" in sound(p, "first day")
    flows.start_lesson(p)
    assert "Check it yourself" in sound(p, "lesson")
    flows.take_quiz(p, correct=False)
    assert "You need 80%" in sound(p, "quiz failed")
    flows.take_quiz(p, correct=True, start="Try a new quiz")
    assert "Passed with" in sound(p, "quiz passed")
    while p.page.get_by_role("button", name="Next lesson →").count():
        flows.button(p, "Next lesson →")
        flows.pass_lesson(p)
    flows.button(p, "See today's summary →")
    assert "Today's done" in sound(p, "day done")
    app.set_clock(D + timedelta(days=1))
    flows.open_app(p, app)
    t = sound(p, "next day")
    assert "Reading financial statements" in t and "Review ·" in t, "her goal again, and what's due"
    goal = next(g["data"]["id"] for g in app.get("/__dump")["tables"]["learning_paths"]
                if g["user_id"] == app.user_id(p.email))
    for path, marker in (("/review", "Review"), (f"/course?subject={goal}", "COURSE MAP"),
                         ("/skills", "Knowledge Map"), ("/records", "Learning Record"), ("/settings", "Goals & Settings"),
                         ("/courses", "Courses"), ("/path", "Your next days"), ("/account", "Profile"),
                         ("/practice", "Practice"), ("/week", "Your week")):
        flows.open_app(p, app, path)
        assert marker.lower() in sound(p, path).lower(), path
    app.set_clock(None)


@pytest.mark.parametrize("width", [390, 1440])
def test_changing_her_plan_and_coming_back_after_signing_out(public_app, pages, width):
    covers("W-settings-setgoal_remove", "W-settings-setgoal_remove_go")
    app = public_app
    app.set_llm()
    p = pages(width=width)
    email = f"jnyb{width}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=("Philosophy",))
    flows.open_app(p, app, "/settings")
    flows.button(p, "Light")
    flows.button(p, "Astronomy")
    assert "Philosophy → Astronomy" in sound(p, "subject added")
    flows.button(p, "Astronomy, selected", exact=False)
    assert "Astronomy" not in text(p).split("one a day, in this order:")[1].split("\n")[0]
    p.page.locator('.st-key-set_sec_reading [role="switch"]').first.check(force=True)
    flows.idle(p.page)
    flows.open_app(p, app, "/reading")
    assert "Start a new book" in sound(p, "reading")
    flows.open_app(p, app, "/settings")
    flows.button(p, "Add a goal")
    assert "What do you want to learn?" in sound(p, "new goal")
    p.page.get_by_label("In your own words").fill("Read a company's financial statements")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    flows.button(p, "Design my path", wait=False)
    assert flows.wait_text(p.page, "Add this goal", 40)
    flows.tap(p, p.page.get_by_text("Yes, all of it", exact=True))
    flows.idle(p.page)
    flows.tap(p, p.page.locator('[class*="st-key-gp_pp_0"] button').first)
    flows.idle(p.page)
    flows.button(p, "Add this goal")
    flows.idle(p.page, 30)
    sound(p, "goal added")
    flows.open_app(p, app, "/settings")
    flows.button(p, "Pause")
    flows.button(p, "Resume")
    flows.button(p, "Pause")
    flows.button(p, "Remove")
    flows.button(p, "Remove goal")
    assert "was removed" in sound(p, "goal removed")
    flows.open_app(p, app, "/account")
    sound(p, "account")
    flows.open_app(p, app)
    p.page.locator(".st-key-account_menu button").first.click()
    flows.idle(p.page)
    p.page.get_by_text("Sign out", exact=True).last.click()
    flows.idle(p.page, 30)
    assert flows.wait_text(p.page, "You've signed out", 20)
    flows.public_sign_in(p, app, email, create=False)
    t = sound(p, "back in")
    assert "Philosophy" in t and "Get started" not in t, "back where she was"
