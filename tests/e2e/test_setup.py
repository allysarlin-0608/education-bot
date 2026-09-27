"""First-time setup: every step, the subject limit, the placement check,
Back, a refresh mid-way, and what is saved when she starts."""
import itertools
import json
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()

# philosophy's five placement questions: the right option of each
RIGHT = ["Epistemology", "Valid", "Marcus Aurelius", "you could will to become a universal law",
         "That we exist; we make what we are by choosing"]
WRONG = ["Ethics", "Persuasive", "Seneca", "a virtuous person would follow", "God's plan for each person"]


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
    covers("W-choices-pick", "W-choices-key", "W-choices-pqprev", "W-choices-pqnext", "W-choices-pqagain",
           "W-setup-ob_back", "W-setup-ob_next", "W-setup-ob_next-2", "W-setup-ob_reading", "D-setup-save_settings",
           "D-ui-save_settings")
    app = request.getfixturevalue(f"{mode}_app")
    if mode == "personal":
        for f in ("learning_log.json", "user_settings.json"):
            (app.state / f).unlink(missing_ok=True)
    p, email = new_person(app, pages)
    flows.button(p, "Get started")
    assert flows.wait_text(p.page, "Choose at least one subject to continue.")
    assert p.page.get_by_role("button", name="Continue").is_disabled()
    for name in ("Philosophy", "Astronomy", "Business Planning"):
        pick_option(p, name)
    assert flows.wait_text(p.page, "3 of 3 chosen · the most you can choose")
    pick_option(p, "General Knowledge")                   # a fourth isn't added
    assert "3 of 3 chosen" in text(p)
    pick_option(p, "Astronomy")                           # taken out again
    assert flows.wait_text(p.page, "2 of 3 chosen")
    flows.button(p, "Continue")
    pick_option(p, "Light")
    flows.button(p, "Back")                               # back to subjects: still two chosen
    assert flows.wait_text(p.page, "2 of 3 chosen")
    flows.button(p, "Continue")
    flows.button(p, "Continue")                           # pace (Light kept)
    # level: placement for Philosophy
    box = p.page.locator(".st-key-sw_lvl_philosophy")
    flows.tap(p, box.get_by_text("I know some already"))
    flows.idle(p.page)
    assert flows.wait_text(p.page, "QUESTION 1 OF 5")
    assert p.page.get_by_role("button", name="Continue").is_disabled(), "can't go on mid-check"
    for k in range(5):
        pick_option(p, RIGHT[k] if k != 2 else WRONG[k])
        if k == 1:                                        # back one and forward again: the answer is kept
            flows.button(p, "Previous")
            assert flows.wait_text(p.page, "QUESTION 1 OF 5")
            flows.button(p, "Next question")
        flows.button(p, "See my level" if k == 4 else "Next question")
    assert flows.wait_text(p.page, "4 of 5 right") and "Intermediate" in text(p)
    flows.button(p, "Take it again")
    assert flows.wait_text(p.page, "QUESTION 1 OF 5")
    for k in range(5):
        pick_option(p, RIGHT[k])
        flows.button(p, "See my level" if k == 4 else "Next question")
    assert flows.wait_text(p.page, "5 of 5 right") and "Advanced" in text(p)
    flows.button(p, "Continue")
    p.page.locator('[data-testid="stToggle"] input, [role="switch"]').first.check(force=True)
    flows.idle(p.page)
    flows.button(p, "Continue")
    t = text(p)
    assert "Philosophy → Business Planning" in t and "Light" in t and "1 lesson a day" in t
    assert "Advanced" in t and "5 of 5 right" in t and "from the basics" in t
    assert "Reading plan" in t and "On" in t
    flows.button(p, "Start learning")
    flows.idle(p.page, 30)
    row = settings_row(app, email)
    assert row["subjects"] == ["philosophy", "business"]
    assert row["units_per_day"] == 1
    assert row["subject_levels"] == {"philosophy": "Advanced", "business": "Beginner"}
    assert row["reading_enabled"] is True and row["onboarded_at"]
    assert "subject=philosophy" in p.page.url, "setup ends in the first day's subject"


def test_a_refresh_mid_setup_keeps_the_step_and_choices(public_app, pages):
    covers("W-setup-ob_next", "D-setup-save_settings")
    app = public_app
    p, _ = new_person(app, pages)
    flows.button(p, "Get started")
    pick_option(p, "Astronomy")
    pick_option(p, "Philosophy")
    flows.button(p, "Continue")
    pick_option(p, "Focused")
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "How much each day?"), "the refresh went back to another step"
    assert "Focused, selected" in p.page.evaluate(
        "[...document.querySelectorAll('button')].map(b => b.innerText).join('|')")
    flows.button(p, "Back")
    assert flows.wait_text(p.page, "2 of 3 chosen")
    assert "Astronomy, selected, day 1" in p.page.evaluate(
        "[...document.querySelectorAll('button')].map(b => b.innerText).join('|')"), "the order she chose them in"


def test_double_click_start_learning(public_app, pages):
    covers("W-setup-ob_next-2")
    app = public_app
    p, email = new_person(app, pages)
    flows.button(p, "Get started")
    pick_option(p, "Philosophy")
    for _ in range(4):
        flows.button(p, "Continue")
    p.page.get_by_role("button", name="Start learning").dblclick()
    flows.idle(p.page, 30)
    assert "Traceback" not in text(p)
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    assert sum(1 for r in d["tables"]["user_settings"] if r["user_id"] == uid) == 1


@pytest.mark.parametrize("width", [390, 768])
def test_setup_on_a_phone_and_tablet(public_app, pages, width):
    covers("W-choices-pick")
    app = public_app
    p, _ = new_person(app, pages, width=width)
    flows.onboard(p, subjects=("Philosophy", "Astronomy"))
    assert p.page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Start this lesson", 20)
