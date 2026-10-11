"""A goal of her own, in a real browser: from the first screen to the first
lesson; vague, huge and unsuitable goals; the AI failing, slow, or clicked
twice; a refresh mid-way; a second goal from Settings taking its turn over
several days; pausing it; and the numbers an admin sees.

The fake model (harness/fake_groq.py) designs a 16-lesson path for any clear
goal, asks about "business stuff", narrows "doctor" and declines "hack"."""
import itertools
import time
from datetime import date, timedelta

import pytest

import flows
from conftest import covers

_n = itertools.count()
GOAL = "Read a company's financial statements"
D = date(2026, 11, 2)


def text(p):
    return p.page.evaluate("document.body.innerText")


def new_person(app, pages, width=1180):
    p = pages(width=width)
    email = f"goal{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    return p, email


def mine(app, email, table):
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    return [r for r in d["tables"][table] if r["user_id"] == uid]


def write_goal(p, goal):
    box = p.page.get_by_label("In your own words")
    box.fill(goal)
    p.page.keyboard.press("Tab")
    flows.idle(p.page)


def design(p, wait_for="All of it, or some parts?"):
    flows.button(p, "Design my path", wait=False)
    assert flows.wait_text(p.page, wait_for, 40), f"{wait_for!r} never came"
    flows.idle(p.page)


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def test_from_the_first_screen_to_a_first_lesson_made_for_her(public_app, pages):
    covers("W-setup-ob_next", "W-goalmaker-k_key_text", "W-goalmaker-k_key_start",
           "W-goalmaker-k_key_design", "AI-goalmaker-ask_json", "W-goalmaker-k_key_scope",
           "W-goalmaker-k_key_f_part_i", "W-goalmaker-k_key_f_pp_i", "W-setup-ob_next-2", "D-setup-save_settings")
    app = public_app
    app.set_llm()
    p, email = new_person(app, pages)
    flows.to_goal(p)
    assert flows.wait_text(p.page, "What do you want to learn?")
    write_goal(p, GOAL)
    flows.tap(p, p.page.get_by_text("I know the basics", exact=True))
    flows.idle(p.page)
    app.reset_calls()
    design(p)
    t = text(p)
    assert "Reading financial statements" in t and "By the end you will be able to" in t
    assert "16 lessons in 4 parts" in t and "Price" not in t and "Plus" not in t
    # only some parts: she knows the first one
    flows.tap(p, p.page.get_by_text("No, only some parts", exact=True))
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_text("Part 1: Foundations", exact=False))
    flows.idle(p.page)
    assert flows.wait_text(p.page, "You chose 12 of 16 lessons")
    flows.button(p, "Continue")
    flows.tap(p, p.page.locator('[class*="st-key-obp_pp_0"] button').first)   # Useful at work
    flows.idle(p.page)
    flows.button(p, "Continue")
    t = text(p)
    assert "Is this right?" in t and "Reading financial statements" in t and "Useful at work" in t
    flows.button(p, "Start learning")
    flows.idle(p.page, 30)
    assert flows.wait_text(p.page, "MADE FOR YOU"), "her first day opens on her goal"
    assert "Reading financial statements" in text(p) and "Because: “Useful at work”" in text(p)
    assert len(app.calls("design")) == 1, "one AI call made the outline"
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "First step done. 11 lessons to go"), "a small win, said plainly"
    goals = mine(app, email, "learning_paths")
    assert len(goals) == 1 and goals[0]["data"]["why"] == "Useful at work"
    events = {r["event"]: r["count"] for r in mine(app, email, "usage_events")}
    assert events == {"visit": 1, "setup_done": 1, "goal_created": 1, "lesson_passed": 1}, events
    assert app.calls("lesson"), "the lesson was written"


def test_vague_huge_and_unsuitable_goals_are_answered_kindly(public_app, pages):
    covers("W-goalmaker-k_key_answers", "W-goalmaker-k_key_f_sugg_k", "W-goalmaker-k_key_f_idea_group",
           "W-setup-ob_again", "W-setup-obg", "W-goalmaker-k_key_idea_group")
    app = public_app
    app.set_llm()
    p, email = new_person(app, pages, width=390)
    flows.to_goal(p)
    write_goal(p, "Get better at business stuff")
    design(p, wait_for="What would you like to be able to do?")
    assert "starting something of your own" in text(p), "a question, not a refusal"
    p.page.get_by_label("Your answer").fill("I want to open a small online shop")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    design(p)
    assert "Reading financial statements" not in text(p), "her answer made it clear: an outline for that"
    flows.button(p, "Back")
    flows.button(p, "Something else")
    assert flows.wait_text(p.page, "Design my path")
    write_goal(p, "Become a doctor")
    design(p, wait_for="Becoming a doctor takes years")
    flows.button(p, "Learn basic first aid")        # a first step that fits
    assert p.page.get_by_label("In your own words").input_value() == "Learn basic first aid"
    write_goal(p, "hack my school's grade system")
    design(p, wait_for="We can't help with that here")
    assert "Understand how investing works" in text(p), "with what we can teach instead"
    write_goal(p, "ab")                              # too little to plan: no AI call
    n = len(app.calls("design"))
    flows.button(p, "Design my path")
    assert flows.wait_text(p.page, "Tell us a little more") and len(app.calls("design")) == n
    flows.tap(p, p.page.get_by_role("radio", name="Study", exact=True))         # ideas for studying
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_role("radio", name="Learn how to study: memory, focus and planning"))  # an idea
    flows.idle(p.page)
    assert p.page.get_by_label("In your own words").input_value() == "Learn how to study: memory, focus and planning"


def test_the_ai_failing_slow_or_clicked_twice_and_a_refresh(public_app, pages):
    covers("W-goalmaker-k_key_design")
    app = public_app
    p, email = new_person(app, pages, width=1440)
    flows.to_goal(p)
    write_goal(p, GOAL)
    app.set_llm(mode="500", fail_kinds=["design"])
    design(p, wait_for="try again")
    assert p.page.get_by_label("In your own words").input_value() == GOAL, "her goal is kept"
    app.set_llm(delay=3.0)
    app.reset_calls()
    btn = p.page.get_by_role("button", name="Design my path")
    btn.dblclick()
    assert flows.wait_text(p.page, "All of it, or some parts?", 40)
    flows.idle(p.page)
    assert len(app.calls("design")) == 1, "a second click never asks again"
    app.set_llm()
    flows.open_app(p, app)                            # a refresh: her path is still there
    assert flows.wait_text(p.page, "Reading financial statements") and len(app.calls("design")) == 1
    assert "Traceback" not in text(p)


def test_a_second_goal_takes_its_turn_and_can_be_paused(public_app, pages, clock):
    covers("W-settings-set_goal_add", "W-goal-goal", "W-goal-goal_add", "D-goal-save_settings",
           "D-goal-save_settings-2", "W-settings-setgoal_pause", "W-settings-setgoal_resume",
           "W-settings-setgoal_map", "D-settings-save_settings-2")
    app = public_app
    app.set_llm()
    clock(D)
    p, email = new_person(app, pages, width=1180)
    flows.onboard(p, subjects=("Philosophy",))
    flows.open_app(p, app, "/settings")
    flows.button(p, "Add a goal")
    assert flows.wait_text(p.page, "What do you want to learn?")
    write_goal(p, GOAL)
    design(p, wait_for="Add this goal")
    flows.tap(p, p.page.get_by_text("Yes, all of it", exact=True))
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_text("No particular goal: I want to learn all of it", exact=True))
    flows.idle(p.page)
    flows.button(p, "Add this goal")
    flows.idle(p.page, 30)
    assert flows.wait_text(p.page, "first turn is today"), "how it shares her days, said first"
    assert "Philosophy" in text(p) and "Tomorrow" in text(p)
    flows.button(p, "Start its first lesson")
    assert flows.wait_text(p.page, "MADE FOR YOU"), "today is free: the goal starts now"
    flows.pass_lesson(p)
    for k, expect in ((1, "Philosophy"), (2, "Reading financial statements")):
        clock(D + timedelta(days=k))
        flows.open_app(p, app)
        assert flows.wait_text(p.page, expect), f"day {k}: {expect}'s turn"
    flows.go(p, app, "Record")
    assert flows.wait_text(p.page, "Reading financial statements"), "the goal is in Progress"
    flows.open_app(p, app, "/settings")
    flows.button(p, "Pause")
    assert flows.wait_text(p.page, "paused")
    flows.open_app(p, app)
    assert "Reading financial statements" not in text(p).split("Course map")[0], "a paused goal leaves the turns"
    flows.open_app(p, app, "/settings")
    flows.button(p, "Resume")
    flows.tap(p, p.page.locator('[class*="st-key-setgoal_"]').get_by_role("button", name="Course map"))
    flows.idle(p.page)
    assert flows.wait_text(p.page, "By the end you will be able to"), "the goal's course map"
    goals = mine(app, email, "learning_paths")
    assert len(goals) == 1 and goals[0]["data"]["status"] == "active"


def test_insights_for_admins_only(public_app, pages):
    covers("W-account-ins_since")
    app = public_app
    p = pages(width=1440)
    flows.admin_sign_in(p, app)
    if flows.wait_text(p.page, "Get started", 3):
        flows.onboard(p)
    flows.open_app(p, app, "/account")
    assert flows.wait_text(p.page, "Insights")
    t = text(p)
    assert "Passed a first lesson" in t and "Lessons per learner per week" in t
    q, _ = new_person(app, pages)
    flows.onboard(q)
    flows.open_app(q, app, "/account")
    flows.idle(q.page)
    assert "Insights" not in text(q)


def test_a_goal_added_to_three_subjects_is_saved(public_app, pages):
    """ISS-061: her own goal plus three subjects is four entries; it must be
    saved and take its turn (it did nothing where the database still
    allowed three). Someone already learning three of our subjects."""
    covers("W-goal-goal_add")
    app = public_app
    app.set_llm()
    p, email = new_person(app, pages, width=1180)
    flows.onboard(p, subjects=("Philosophy", "Astronomy", "Stocks, Investing & Crypto"))
    flows.open_app(p, app, "/goal")
    write_goal(p, GOAL)
    design(p, wait_for="Add this goal")
    flows.tap(p, p.page.get_by_text("Yes, all of it", exact=True))
    flows.idle(p.page)
    flows.tap(p, p.page.locator('[class*="st-key-gp_pp_0"] button').first)
    flows.idle(p.page)
    flows.button(p, "Add this goal")
    flows.idle(p.page, 30)
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "MADE FOR YOU", 20), text(p)[:600]
    d = app.get("/__dump")
    uid = next(u["id"] for u in d["users"] if u["email"] == email)
    row = next(r for r in d["tables"]["user_settings"] if r["user_id"] == uid)
    assert len(row["subjects"]) == 4 and row["onboarded_at"]
