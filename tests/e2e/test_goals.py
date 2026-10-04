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


def write_goal(p, goal, why=""):
    box = p.page.get_by_label("In your own words")
    box.fill(goal)
    if why:
        p.page.get_by_label("Why does it matter to you? (optional)").fill(why)
    p.page.keyboard.press("Tab")
    flows.idle(p.page)


def design(p, wait_for="Your path"):
    flows.button(p, "Design my path", wait=False)
    assert flows.wait_text(p.page, wait_for, 40), f"{wait_for!r} never came"
    flows.idle(p.page)


@pytest.fixture
def clock(public_app):
    yield public_app.set_clock
    public_app.set_clock(None)


def test_from_the_first_screen_to_a_first_lesson_made_for_her(public_app, pages):
    covers("W-setup-ob_next", "W-goalmaker-k_key_text", "W-goalmaker-k_key_why", "W-goalmaker-k_key_start",
           "W-goalmaker-k_key_pace", "W-goalmaker-k_key_design", "AI-goalmaker-ask_json", "W-goalmaker-k_key_f_skip_i",
           "W-goalmaker-k_key_f_down_i", "W-goalmaker-k_key_level", "W-goalmaker-k_key_f_rmpop_i",
           "W-goalmaker-k_key_f_rm_i_k", "W-goalmaker-k_key_lighter", "W-goalmaker-k_key_undo", "W-setup-ob_next-2",
           "D-setup-save_settings")
    app = public_app
    app.set_llm()
    p, email = new_person(app, pages)
    flows.button(p, "Get started")
    assert flows.wait_text(p.page, "What do you want to learn?")
    write_goal(p, GOAL, why="I want to invest my savings well")
    flows.tap(p, p.page.get_by_text("I know the basics", exact=True))
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_text("10 min a day", exact=True))
    flows.idle(p.page)
    app.reset_calls()
    design(p)
    t = text(p)
    assert "Reading financial statements" in t and "By the end you will be able to" in t
    assert "Because: “I want to invest my savings well”" in t, "her reason shows"
    assert "16 lessons in 4 parts" in t and "about 16 study days at 1 a day" in t, "sized to her time"
    # make it hers: skip a part, move one, take a lesson out, deeper, shorter, then undo it all
    flows.button(p, "I know this: skip it")
    assert flows.wait_text(p.page, "12 lessons in 3 parts")
    flows.button(p, "Move down")
    flows.tap(p, p.page.get_by_role("button", name="Remove a lesson").first)
    flows.idle(p.page)
    flows.tap(p, p.page.get_by_role("button", name="Putting it together: idea 1", exact=True))
    flows.idle(p.page)
    assert flows.wait_text(p.page, "11 lessons in 3 parts")
    flows.tap(p, p.page.get_by_text("Advanced", exact=True))
    flows.idle(p.page)
    assert flows.wait_text(p.page, "· Advanced ·")
    flows.button(p, "Undo my changes")
    assert flows.wait_text(p.page, "16 lessons in 4 parts")
    flows.button(p, "Make it shorter")
    assert flows.wait_text(p.page, "12 lessons in 4 parts")
    flows.button(p, "Continue")                     # path → subjects (optional now)
    assert flows.wait_text(p.page, "Add a subject?")
    flows.button(p, "Continue")                     # → reading
    flows.button(p, "Continue")                     # → summary
    t = text(p)
    assert "YOUR FIRST LESSON IS TODAY" in t.upper()
    assert "Reading financial statements" in t and "Every day" in t
    flows.button(p, "Start learning")
    flows.idle(p.page, 30)
    assert flows.wait_text(p.page, "MADE FOR YOU"), "her first day opens on her goal"
    assert "Reading financial statements" in text(p)
    assert len(app.calls("design")) == 1, "one AI call made the path"
    flows.pass_lesson(p)
    assert flows.wait_text(p.page, "First step done. 11 lessons to go"), "a small win, said plainly"
    goals = mine(app, email, "learning_paths")
    assert len(goals) == 1 and goals[0]["data"]["level"] == "Intermediate" and goals[0]["data"]["why"]
    events = {r["event"]: r["count"] for r in mine(app, email, "usage_events")}
    assert events == {"visit": 1, "setup_done": 1, "goal_created": 1, "lesson_passed": 1}, events
    lesson_prompt = [c for c in app.calls("lesson")]
    assert lesson_prompt, "the lesson was written"


def test_vague_huge_and_unsuitable_goals_are_answered_kindly(public_app, pages):
    covers("W-goalmaker-k_key_answers", "W-goalmaker-k_key_f_sugg_k", "W-goalmaker-k_key_f_idea_group",
           "W-setup-ob_again", "W-setup-obg", "W-goalmaker-k_key_idea_group")
    app = public_app
    app.set_llm()
    p, email = new_person(app, pages, width=390)
    flows.button(p, "Get started")
    write_goal(p, "Get better at business stuff")
    design(p, wait_for="What would you like to be able to do?")
    assert "starting something of your own" in text(p), "a question, not a refusal"
    p.page.get_by_label("Your answer").fill("I want to open a small online shop")
    p.page.keyboard.press("Tab")
    flows.idle(p.page)
    design(p)
    assert "Reading financial statements" not in text(p) and "Your path" in text(p)
    flows.button(p, "Start over with a different goal")
    assert flows.wait_text(p.page, "What do you want to learn?")
    write_goal(p, "Become a doctor")
    design(p, wait_for="Becoming a doctor takes years")
    flows.button(p, "Learn basic first aid")        # a first step that fits
    assert p.page.get_by_label("In your own words").input_value() == "Learn basic first aid"
    write_goal(p, "hack my school's grade system")
    design(p, wait_for="We can't help with that here")
    assert "Understand how investing works" in text(p), "with what we can teach instead"
    write_goal(p, "learn")                           # too little to plan: no AI call
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
    flows.button(p, "Get started")
    write_goal(p, GOAL)
    app.set_llm(mode="500", fail_kinds=["design"])
    design(p, wait_for="try again")
    assert p.page.get_by_label("In your own words").input_value() == GOAL, "her goal is kept"
    app.set_llm(delay=3.0)
    app.reset_calls()
    btn = p.page.get_by_role("button", name="Design my path")
    btn.dblclick()
    assert flows.wait_text(p.page, "Your path", 40)
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
    design(p)
    flows.button(p, "Add this goal")
    flows.idle(p.page, 30)
    assert flows.wait_text(p.page, "MADE FOR YOU"), "today is free: the goal starts now"
    flows.pass_lesson(p)
    for k, expect in ((1, "Philosophy"), (2, "Reading financial statements")):
        clock(D + timedelta(days=k))
        flows.open_app(p, app)
        assert flows.wait_text(p.page, expect), f"day {k}: {expect}'s turn"
    flows.go(p, app, "Progress")
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
    covers("W-settings-ins_since")
    app = public_app
    p = pages(width=1440)
    flows.admin_sign_in(p, app)
    if flows.wait_text(p.page, "Get started", 3):
        flows.onboard(p)
    flows.open_app(p, app, "/settings")
    assert flows.wait_text(p.page, "Insights")
    t = text(p)
    assert "Passed a first lesson" in t and "Lessons per learner per week" in t
    q, _ = new_person(app, pages)
    flows.onboard(q)
    flows.open_app(q, app, "/settings")
    flows.idle(q.page)
    assert "Insights" not in text(q)
