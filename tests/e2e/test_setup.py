"""First-time setup, in a real browser: who she is (or that she knows what
she wants), what she wants to learn (in her words, or narrowed down from
broad directions), all of it or some parts, what it's for, and the
confirmation; Back, a change and straight back, a refresh mid-way, and what
is saved when she starts."""
import itertools
import json
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()


def new_person(app, pages, width=1440):
    p = pages(width=width)
    email = f"setup{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    return p, email


def settings_row(app, email):
    if app.mode == "personal":
        return json.loads((app.state / "user_settings.json").read_text())["user_settings"][0]
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    return next(r for r in d["tables"]["user_settings"] if r["user_id"] == uid)


def text(p):
    return p.page.evaluate("document.body.innerText")


def pick_option(p, name):
    """A row in a choice list (its button's name starts with the row's name)."""
    flows.tap(p, p.page.get_by_role("button", name=name, exact=False).first)
    flows.idle(p.page)


@pytest.mark.parametrize("mode", ["public", "personal"])
def test_every_step_and_what_is_saved(mode, pages, request):
    covers("W-choices-pick", "W-choices-key", "W-setup-ob_back", "W-setup-ob_next", "W-setup-ob_next-2",
           "D-setup-save_settings", "D-ui-save_settings", "W-setup-ob_change", "W-setup-ob_to_review",
           "W-goalmaker-k_key_skip", "W-goalmaker-k_key_scope", "W-goalmaker-k_key_f_part_i",
           "W-goalmaker-k_key_own")
    app = request.getfixturevalue(f"{mode}_app")
    app.set_llm()
    if mode == "personal":
        for f in ("learning_log.json", "user_settings.json", "learner_prefs.json"):
            (app.state / f).unlink(missing_ok=True)
    p, email = new_person(app, pages)
    # who she is: needed (or that she knows what she wants)
    assert flows.wait_text(p.page, "Who are you?")
    assert p.page.get_by_role("button", name="Get started").is_disabled()
    pick_option(p, "Student")
    flows.button(p, "Get started")
    # what she wants to learn: she doesn't know yet, so broad directions, then narrower
    assert flows.wait_text(p.page, "What do you want to learn?")
    flows.button(p, "I don't know yet")
    t = text(p)
    assert all(x in t for x in ("Languages", "Math", "Natural science", "Society", "Arts", "Technology"))
    pick_option(p, "Natural science")
    pick_option(p, "Earth and space")
    flows.button(p, "Back")                                 # one level up
    assert flows.wait_text(p.page, "Physics")
    pick_option(p, "Earth and space")
    pick_option(p, "The night sky")                         # nothing narrower: its outline is designed
    assert flows.wait_text(p.page, "All of it, or some parts?", 40)
    assert "16 lessons in 4 parts" in text(p)
    # some parts
    flows.tap(p, p.page.get_by_text("No, only some parts", exact=True))
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_text("Part 1: Foundations", exact=False))
    flows.idle(p.page)
    assert flows.wait_text(p.page, "You chose 12 of 16 lessons")
    flows.button(p, "Continue")
    # what it's for: a student's goals, or her own words
    assert flows.wait_text(p.page, "What's it for?") and "For an exam" in text(p)
    p.page.get_by_label("Or in your own words").fill("A school project about the stars")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    flows.button(p, "Continue")
    # confirm: one sentence of everything; a change goes to its step and straight back
    t = text(p)
    assert "Is this right?" in t and "You're a student" in t and "12 lessons" in t
    assert "A school project about the stars" in t and "USD" not in t
    for change, lands in (("Change who you are", "Who are you?"), ("Change the parts", "All of it, or some parts?"),
                          ("Change what it's for", "What's it for?")):
        flows.button(p, change)
        assert flows.wait_text(p.page, lands), change
        flows.button(p, "Back to confirm")
        assert flows.wait_text(p.page, "Is this right?") and "12 lessons" in text(p), change
    # Start learning
    flows.button(p, "Start learning")
    flows.idle(p.page, 30)
    row = settings_row(app, email)
    assert len(row["subjects"]) == 1 and row["subjects"][0].startswith("g-"), "her goal, nothing else"
    assert row["units_per_day"] == 3 and row["onboarded_at"] and not row.get("onboarding")
    assert flows.wait_text(p.page, "MADE FOR YOU", 20), "her first day opens on it"


def test_a_refresh_mid_setup_keeps_the_step_and_choices(public_app, pages):
    covers("W-setup-ob_next", "D-setup-save_settings")
    app = public_app
    app.set_llm()
    p, _ = new_person(app, pages)
    flows.to_goal(p, "Retired")
    p.page.get_by_label("In your own words").fill("Read a company's financial statements")
    flows.button(p, "Design my path")
    assert flows.wait_text(p.page, "All of it, or some parts?", 40)
    flows.tap(p, p.page.get_by_text("No, only some parts", exact=True))
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_text("Part 2: Core skills", exact=False))
    flows.idle(p.page)
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "All of it, or some parts?"), "the refresh went back to another step"
    assert "You chose 12 of 16 lessons" in text(p)
    flows.button(p, "Continue")
    assert flows.wait_text(p.page, "To keep my mind active"), "a retired learner's goals"
    flows.button(p, "Back")
    flows.button(p, "Back")
    assert flows.wait_text(p.page, "Reading financial statements"), "what she asked for, as it was"


def test_double_click_start_learning(public_app, pages):
    covers("W-setup-ob_next-2")
    app = public_app
    app.set_llm()
    p, email = new_person(app, pages)
    flows.to_goal(p)
    p.page.get_by_label("In your own words").fill("Read a company's financial statements")
    flows.button(p, "Design my path")
    assert flows.wait_text(p.page, "All of it, or some parts?", 40)
    flows.tap(p, p.page.get_by_text("Yes, all of it", exact=True))
    flows.idle(p.page)
    flows.button(p, "Continue")
    flows.tap(p, p.page.get_by_text("No particular goal: I want to learn all of it", exact=True))
    flows.idle(p.page)
    flows.button(p, "Continue")
    p.page.get_by_role("button", name="Start learning").dblclick()
    flows.idle(p.page, 30)
    assert "Traceback" not in text(p)
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    assert sum(1 for r in d["tables"]["user_settings"] if r["user_id"] == uid) == 1
    assert len([r for r in d["tables"]["learning_paths"] if r["user_id"] == uid]) == 1


@pytest.mark.parametrize("width", [390, 768, 1180])
def test_setup_on_a_phone_and_tablet(public_app, pages, width):
    covers("W-choices-pick")
    app = public_app
    app.set_llm()
    p, _ = new_person(app, pages, width=width)
    def fits(step):
        assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"{step}: sideways"
    flows.set_up_goal(p, each=fits)
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Start this lesson", 20)
