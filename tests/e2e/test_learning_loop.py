"""The learning system (docs/LEARNING_DESIGN.md, ISS-110) in a real browser,
journey by journey, each screen photographed and checked for layout faults
(sideways scroll, text under the chat box, overlap) at the four widths, in
light and dark:

- the first session: the lesson's quick checks (a miss, the hint, a second
  try), guided practice, the check with how sure she is, the day's close
  and its reflection;
- the next day: the warm-up before the lesson, mixed practice at the close;
- a busy day (five minutes: recall and practice) and coming back after a
  break (welcome back, a longer warm-up);
- where to start (the placement check, its shared questions), the unit gate
  and its corrective path, the capstone, the learning dashboard."""
import itertools
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

import flows
from conftest import covers
from test_screens import SIZES, shot

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_history  # noqa: E402

_n = itertools.count()
D = date(2026, 11, 2)
LAYOUT = ("sideways", "under", "overlap")


def text(p):
    return p.page.evaluate("document.body.innerText")


def faults(problems):
    return {k: v for k, v in problems.items() if any(w in str(v) for w in LAYOUT)}


def person(app, pages, width=1180, scheme="light", subjects=("Philosophy",), pace="Light"):
    p = pages(width=width, height=SIZES.get(width, 900), scheme=scheme)
    email = f"loop{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, subjects=subjects, pace=pace)
    return p, email


def attempts(app, email):
    uid = app.user_id(email)
    return [r for r in app.get("/__dump")["tables"]["learning_attempts"] if r["user_id"] == uid]


def with_cards(entries):
    """Each seeded lesson with a key point to review, due by now."""
    for e in entries:
        lessons = json.loads(e["lessons"]) if isinstance(e["lessons"], str) else e["lessons"]
        for sl in lessons:
            if sl.get("completed") and not sl.get("from"):
                sl["cards"] = [{"id": f"pt{e['date']}{sl['n']}", "kind": "point", "front": f"The key idea of {sl['title']}",
                                "back": "Seeded key idea.", "box": 0, "due": e["date"], "added": e["date"], "last": None,
                                "reviews": 0, "lapses": 0, "paused": False, "topic": e["topic"], "n": sl["n"]}]
        e["lessons"] = lessons
    return entries


def do_set(p, name, right=True, stop=None):
    """Answer a warm-up or mixed set (`name`) item by item until it's done
    (or, with `stop`, until that many are answered)."""
    page = p.page
    box = page.locator(f".st-key-ss_{name}")
    answered = 0
    for _ in range(30):
        flows.idle(page)
        if not box.count() or not box.first.is_visible():
            return
        nxt = box.locator(f'.st-key-ss_{name}_next button')
        if nxt.count():
            if stop is not None and answered >= stop:
                return
            flows.tap(p, nxt.first)                      # "Next", or "Continue" after the last
            continue
        answered += 1
        if box.get_by_role("button", name="Show the answer", exact=True).count():
            flows.tap(p, box.get_by_role("button", name="Show the answer", exact=True).first)
            flows.idle(page)
            flows.tap(p, box.get_by_role("button", name="I knew it" if right else "Not yet", exact=True).first)
            continue
        flows.answer_all(p, correct=right, scope=box.first)
        flows.tap(p, box.get_by_role("button", name="Fairly sure", exact=True).first)
    raise AssertionError(f"the {name} set never finished")


def quick_check(p, k, wrong, right):
    """Quick check k of lesson 1: `wrong` first (if given), the hint, then `right`."""
    page = p.page
    box = page.locator(f".st-key-qc_1_{k}").first
    box.scroll_into_view_if_needed()
    if wrong:
        flows.tap(p, box.get_by_text(wrong, exact=True))
        flows.idle(page)
        flows.tap(p, box.get_by_role("button", name="Sure", exact=True))
        assert flows.wait_text(page, "Try once more.", 10), "a miss: the mistake and a hint, then a second try"
        flows.tap(p, box.get_by_text(right, exact=True))
        flows.idle(page)
        flows.tap(p, box.get_by_role("button", name="Check again", exact=True))
        assert flows.wait_text(page, "Right on the second try.", 10)
    else:
        flows.tap(p, box.get_by_text(right, exact=True))
        flows.idle(page)
        flows.tap(p, box.get_by_role("button", name="Fairly sure", exact=True))
        assert flows.wait_text(page, "Right.", 10)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", list(SIZES))
def test_the_first_day_and_the_next(public_app, pages, width, scheme):
    """The whole loop: read with quick checks, practise, the check, the close;
    the next day's warm-up, a lesson and mixed practice."""
    covers("W-daily-to_practice", "W-daily-to_check_done", "W-daily-guided_next", "W-daily-take_check",
           "W-daily-ckey", "W-daily-see_the_check", "W-daily-the_lesson", "W-daily-reflect", "W-daily-ss_next",
           "W-daily-to_check", "W-session_ui-conf", "W-session_ui-again", "W-session_ui-jol", "W-session_ui-show",
           "W-session_ui-yes", "W-exercise-x", "AI-lessonprep-stream_text", "S-gnosis_experiments", "D-daily-save_day-5")
    app = public_app
    app.set_llm()
    app.set_clock(D, "02:00:00")
    problems = {}
    tag = f"{width}_{scheme}"
    try:
        p, email = person(app, pages, width, scheme)
        page = p.page
        flows.open_app(p, app)
        shot(p, f"L01_home_first_day_{tag}", problems)
        flows.start_lesson(p)
        assert page.locator(".st-key-qc_1_0").count() == 1 and page.locator(".st-key-qc_1_1").count() == 1, "the lesson's two quick checks"
        shot(p, f"L02_lesson_quick_check_{tag}", problems)
        quick_check(p, 0, "Earth orbiting the Sun", "Earth spinning on its axis")
        shot(p, f"L03_quick_check_second_try_{tag}", problems)
        quick_check(p, 1, None, "West to east")
        flows.button(p, "Next: practise it →", wait=False)
        assert flows.wait_text(page, "A worked example", 40) or flows.wait_text(page, "Now one on your own", 5)
        shot(p, f"L04_guided_practice_{tag}", problems)
        _guided(p)
        assert flows.wait_text(page, "Submit answers", 2) or flows.wait_text(page, "Start the check", 20)
        if not flows.wait_text(page, "Submit answers", 2):
            flows.button(p, "Start the check", wait=False)
        assert flows.wait_text(page, "Submit answers", 40)
        flows.answer_all(p, correct=True)
        sure = page.locator('[class*="st-key-quizconf_"]').first
        flows.tap(p, sure.get_by_role("button", name="Sure", exact=True).or_(sure.get_by_text("Sure", exact=True)).first)
        shot(p, f"L05_the_check_{tag}", problems)
        flows.button(p, "Submit answers", wait=False)
        assert flows.wait_text(page, "Passed with 100%", 40)
        flows.open_panel(p, "See the check")
        flows.open_panel(p, "The lesson")
        shot(p, f"L06_passed_{tag}", problems)
        flows.button(p, "Finish today →")
        assert flows.wait_text(page, "Today's done") and "streak" not in text(p).lower()
        shot(p, f"L07_day_close_{tag}", problems)
        flows.reflect(p, "The spin makes the day.", sure="Yes, clearly")
        rows = attempts(app, email)
        ctx = {r["ctx"] for r in rows}
        assert {"check", "guided", "quiz", "jol", "step"} <= ctx, ctx
        assert any(r["ctx"] == "check" and r["first"] and r["score"] == 0 for r in rows), "the first try is the evidence"
        assert all(not str(r.get("topic", "")).startswith("goal:") or len(r["topic"]) == 13 for r in rows)

        # the next day: recall first, then the lesson (written meanwhile), then mixed practice at the close
        app.set_clock(D + timedelta(days=1), "02:00:00")
        flows.open_app(p, app, warmup=True)
        assert flows.wait_text(page, "Warm-up", 15, ci=True), "the day starts by recalling yesterday"
        shot(p, f"L08_warm_up_{tag}", problems)
        do_set(p, "warmup")
        assert flows.wait_text(page, "Start this lesson", 20) or flows.wait_text(page, "Next: practise it", 5)
        if page.get_by_role("button", name="Start this lesson", exact=True).count():
            flows.start_lesson(p)
        flows.take_quiz(p, correct=True)                 # "I know this": straight to the check
        flows.button(p, "Finish today →")
        assert flows.wait_text(page, "Before you go")
        if flows.wait_text(page, "Mixed practice", 3, ci=True):
            shot(p, f"L09_mixed_practice_{tag}", problems)
            do_set(p, "mixed")
        flows.reflect(p)
        assert {"warmup"} <= {r["ctx"] for r in attempts(app, email)}
        assert "Traceback" not in text(p)
    finally:
        app.set_clock(None)
    assert not faults(problems), problems


def _guided(p):
    """Guided practice: the worked steps' gap and her own problem, a miss on
    the first to see the hint, then on to the check."""
    page = p.page
    for _ in range(6):
        flows.idle(page)
        if page.get_by_role("button", name="Next: the check →", exact=True).count():
            break
        box = page.locator('[class*="st-key-guided_"]').first
        if page.get_by_role("button", name="Next", exact=True).count():
            flows.tap(p, page.get_by_role("button", name="Next", exact=True).first)
            continue
        if page.get_by_role("button", name="Check again", exact=True).count():
            flows.answer_all(p, correct=True, scope=box)
            flows.tap(p, page.get_by_role("button", name="Check again", exact=True).first)
            continue
        flows.answer_all(p, correct=True, scope=box)
        flows.tap(p, box.get_by_role("button", name="Fairly sure", exact=True))
    flows.button(p, "Next: the check →")


@pytest.mark.parametrize("width,scheme", [(1180, "light"), (390, "dark")])
def test_a_busy_day_and_coming_back_after_a_break(public_app, pages, width, scheme):
    covers("W-daily-light_menu", "W-daily-brief_on", "W-daily-brief_more", "W-daily-brief_off", "W-daily-ss_skip",
           "W-session_ui-no", "W-daily-guided_skip", "W-daily-reread", "W-daily-practice_preparing")
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    try:
        app.set_clock(D - timedelta(days=1), "02:00:00")     # (signed up the day before: today's warm-up is untouched)
        p, email = person(app, pages, width, scheme)
        app.set_clock(D, "02:00:00")
        # ten days of lessons, the last eleven days ago (all before the mastery rules: no gate stops her)
        app.seed_entries(email, with_cards(seed_history.build(D - timedelta(days=10), days=10, topics=("philosophy",),
                                                              per_day=1, gaps=(), partial=())))
        page = p.page
        # back after a break: welcome back, a longer warm-up (left part way)
        flows.open_app(p, app, warmup=True)
        assert flows.wait_text(page, "Welcome back", 15, ci=True)
        assert flows.wait_text(page, "Warm-up", 10, ci=True)
        shot(p, f"L10_welcome_back_{tag}", problems)
        warm = page.locator(".st-key-ss_warmup")
        assert "0 of 6 done" in warm.first.inner_text(), "back after a break: a longer warm-up"
        do_set(p, "warmup", right=False, stop=1)        # one recalled (or not), then the rest skipped
        flows.tap(p, page.locator(".st-key-ss_warmup_next button").first)      # on to the next...
        flows.idle(page)
        flows.button(p, "Skip the rest")                                       # ...and the rest left
        assert not page.locator(".st-key-ss_warmup").count()
        # a five-minute day: recall and mixed practice, no new lesson
        flows.tap(p, page.get_by_role("button", name="Short on time?"))
        shot(p, f"L11_short_on_time_{tag}", problems)
        flows.button(p, "Five minutes: recall and practice")
        assert flows.wait_text(page, "A five-minute day", 10)
        flows.idle(page)
        shot(p, f"L12_five_minutes_{tag}", problems)
        do_set(p, "mixed")
        assert flows.wait_text(page, "Do a lesson too", 10)
        shot(p, f"L13_five_minutes_done_{tag}", problems)
        flows.button(p, "Do a lesson too")
        assert flows.wait_text(page, "Start this lesson", 15), text(p)[-1500:]
        # the lesson: skip the practice, fail the check, back to the lesson
        flows.start_lesson(p)
        flows.button(p, "Next: practise it →", wait=False)
        assert flows.wait_text(page, "Skip to the check", 40)
        flows.button(p, "Skip to the check")
        flows.take_quiz(p, correct=False)
        flows.button(p, "Read the lesson again")
        assert flows.wait_text(page, "Next: practise it", 10), text(p)[-2500:]
        # the next day: a five-minute day turned back into a lesson day before starting
        app.set_clock(D + timedelta(days=1), "02:00:00")
        flows.open_app(p, app)
        flows.tap(p, page.get_by_role("button", name="Short on time?"))
        flows.button(p, "Five minutes: recall and practice")
        assert flows.wait_text(page, "A five-minute day", 10)
        flows.button(p, "Do a lesson too")
        assert not flows.wait_text(page, "A five-minute day", 2)
        assert "Traceback" not in text(p)
    finally:
        app.set_clock(None)
    assert not faults(problems), problems


@pytest.mark.parametrize("width,scheme", [(1440, "dark"), (390, "light")])
def test_where_to_start_then_the_capstone(public_app, pages, width, scheme):
    covers("W-daily-diag_open", "W-diagnostic-dg_go", "W-diagnostic-dg_idk", "W-diagnostic-dg_apply",
           "W-diagnostic-dg_home", "W-diagnostic-dg_none", "W-diagnostic-dg_back_none", "W-course-cm_diag",
           "AI-diagnostic-ask_json", "AI-diagnostic-ask_json-2", "W-daily-capstone_open", "W-capstone-cp_brief",
           "W-capstone-cp_brief_wait", "W-capstone-cp_work", "W-capstone-cp_send", "W-capstone-cp_send_wait",
           "W-capstone-cp_back_none", "W-course-cm_cap", "AI-capstone-ask_json", "AI-capstone-ask_json-2")
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    p = pages(width=width, height=SIZES[width], scheme=scheme)
    email = f"place{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.set_up_goal(p)
    page = p.page
    flows.open_app(p, app, "/start")
    assert flows.wait_text(page, "Nothing to place here", 15)
    flows.button(p, "Back to Home")
    goal = next(g["data"] for g in app.get("/__dump")["tables"]["learning_paths"] if g["user_id"] == app.user_id(email))
    goal = json.loads(goal) if isinstance(goal, str) else goal
    flows.open_app(p, app, f"/course?subject={goal['id']}")
    assert page.get_by_role("button", name="Find my starting point").count(), "the learning map offers it too"
    flows.open_app(p, app)
    flows.button(p, "Find my starting point", wait=False)
    assert flows.wait_text(page, "A few questions on this path", 20)
    shot(p, f"L20_where_to_start_{tag}", problems)
    flows.button(p, "Find my starting point", wait=False)
    for k in range(10):
        flows.idle(page, 40)
        if flows.wait_text(page, "Start from there", 2) or flows.wait_text(page, "Start from the beginning", 1) \
                and not page.get_by_role("button", name="I don't know yet").count():
            break
        if k == 0:
            shot(p, f"L21_placement_question_{tag}", problems)
        if k % 3 == 2:
            flows.button(p, "I don't know yet", wait=False)
            continue
        flows.answer_all(p, correct=True)
        flows.tap(p, page.get_by_role("button", name="Fairly sure", exact=True).first)
    assert flows.wait_text(page, "You start at Lesson", 15), text(p)[-1500:]
    shot(p, f"L22_placement_result_{tag}", problems)
    applied = page.get_by_role("button", name="Start from there", exact=True)
    if applied.count() and applied.is_enabled():
        flows.button(p, "Start from there")
    else:
        flows.button(p, "Start from the beginning")
    flows.open_app(p, app, f"/start?subject={goal['id']}")
    flows.button(p, "Back to Home")
    assert any(r["ctx"] == "diag" for r in attempts(app, email))
    assert len(app.calls("placement")) >= 1

    # every lesson of the goal done: the capstone
    flows.open_app(p, app, f"/capstone?subject={goal['id']}")
    assert flows.wait_text(page, "Not open yet", 15)
    flows.button(p, "Back to Home")
    lessons = [(u["name"], t) for u in goal["units"] for t in u["lessons"]]      # (stored: titles)
    day = date.today() - timedelta(days=1)
    slots = [{"n": n, "title": t, "unit": u, "kickoff": "k", "lesson": seed_history.LESSON, "followups": [],
              "completed": True, "quiz": seed_history._quiz(f"c{n}", 9)} for n, (u, t) in enumerate(lessons, start=1)]
    app.seed_entries(email, [{"date": day.isoformat(), "topic": goal["id"], "session_number": 1, "level": "Beginner",
                              "completed": True, "title": "All of it", "followup_question": "", "reflection": "",
                              "lesson": "", "followups": [], "kickoff": "", "lessons": slots}])
    flows.open_app(p, app)
    assert flows.wait_text(page, "Goal complete", 15, ci=True), text(p)[-1200:]
    shot(p, f"L23_goal_complete_{tag}", problems)
    flows.open_app(p, app, f"/course?subject={goal['id']}")
    flows.button(p, "Capstone ·", exact=False)
    assert flows.wait_text(page, "Write my capstone brief", 15)
    flows.open_app(p, app)
    flows.button(p, "Open your capstone")
    flows.button(p, "Write my capstone brief", wait=False)
    assert flows.wait_text(page, "What good work shows", 30, ci=True)
    shot(p, f"L24_capstone_brief_{tag}", problems)
    page.get_by_label("Your work").fill("My summary of the report. " * 12)
    page.keyboard.press("Tab")
    flows.idle(page)
    flows.button(p, "Hand it in for feedback", wait=False)
    assert flows.wait_text(page, "Feedback", 30) and flows.wait_text(page, "Partly", 5)
    shot(p, f"L25_capstone_feedback_{tag}", problems)
    assert app.calls("capstone_brief") and app.calls("capstone_feedback")
    assert "Traceback" not in text(p)
    assert not faults(problems), problems


def test_the_math_placement_shares_its_questions(public_app, pages):
    """The second learner placed on the curriculum gets the questions the
    first one's were written into (no new call), and can report one."""
    covers("W-diagnostic-dg_bad", "W-diagnostic-dg_skip")
    app = public_app
    app.set_llm()
    for k in range(2):
        p, email = person(app, pages, 1180, subjects=("Mathematics",))
        page = p.page
        flows.open_app(p, app, "/start?subject=math")
        if k == 0:
            flows.button(p, "Find my starting point", wait=False)
            for _ in range(10):
                flows.idle(page, 40)
                if flows.wait_text(page, "You start at Lesson", 2):
                    break
                flows.answer_all(p, correct=True)
                flows.tap(p, page.get_by_role("button", name="Sure", exact=True).first)
            written = len(app.calls("placement"))
            assert written >= 1
            assert app.get("/__dump")["tables"]["shared_items"], "the questions went into the shared bank"
        else:
            app.reset_calls()
            flows.button(p, "Find my starting point", wait=False)
            assert flows.wait_text(page, "This question is wrong", 30)
            assert not app.calls("placement"), "the bank's questions: no call"
            flows.button(p, "This question is wrong", wait=False)
            flows.idle(page)
            reported = [r for r in app.get("/__dump")["tables"]["shared_items"] if r["by"]]
            assert len(reported) == 1
            flows.open_app(p, app, "/start?subject=math")
    # someone who'd rather start at the beginning
    p, _ = person(app, pages, 1180, subjects=("Mathematics",))
    flows.open_app(p, p.app, "/start?subject=math")
    flows.button(p, "Start from the beginning")
    assert flows.wait_text(p.page, "Start this lesson", 15)


@pytest.mark.parametrize("width,scheme", [(820, "light"), (1440, "dark")])
def test_the_unit_gate_and_its_corrective_path(public_app, pages, width, scheme):
    covers("W-daily-gate_check", "W-unit-uc_practise", "W-practice-practice", "W-exercise-key-4")
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    day = date(2026, 11, 12)
    app.set_clock(day, "02:00:00")
    try:
        p, email = person(app, pages, width, scheme)
        app.seed_entries(email, seed_history.build(day, days=6, topics=("philosophy",), per_day=1, gaps=(), partial=()))
        page = p.page
        flows.open_app(p, app)
        assert flows.wait_text(page, "Take the unit check", 15), "the next unit waits for this one's check"
        shot(p, f"L30_unit_gate_{tag}", problems)
        flows.button(p, "Take the unit check")
        assert flows.wait_text(page, "80% passes it")
        for group in page.get_by_role("radiogroup").all():
            group.get_by_text("Wrong", exact=True).first.click()
            page.wait_for_timeout(60)
        flows.idle(page)
        flows.button(p, "Check my answers")
        assert flows.wait_text(page, "To work on first", 15)
        shot(p, f"L31_corrective_path_{tag}", problems)
        flows.button(p, "Practise these ideas")
        assert "/practice" in page.url and flows.wait_text(page, "Practice", 10)
        shot(p, f"L32_focused_practice_{tag}", problems)
        assert "Traceback" not in text(p)
    finally:
        app.set_clock(None)
    assert not faults(problems), problems


@pytest.mark.parametrize("width,scheme", [(1440, "light"), (390, "dark")])
def test_the_learning_dashboard(public_app, pages, width, scheme):
    covers("W-account-ins_learning", "W-learning-ld_csv", "W-review-collection_if_view_collection_else_revie")
    app = public_app
    app.set_llm()
    problems = {}
    tag = f"{width}_{scheme}"
    # a learner's day first, so there are answers to read
    p, email = person(app, pages, width, scheme)
    flows.open_app(p, app)
    flows.start_lesson(p)
    flows.take_quiz(p, correct=True)
    flows.open_app(p, app, "/review")
    page = p.page
    flows.tap(p, page.get_by_role("button", name="Collection").or_(page.get_by_role("radio", name="Collection")).first)
    flows.idle(page)
    shot(p, f"L40_collection_tab_{tag}", problems)
    a = pages(width=width, height=SIZES[width], scheme=scheme)
    flows.admin_sign_in(a, app)
    if flows.wait_text(a.page, "Get started", 3):
        flows.onboard(a)
    flows.open_app(a, app, "/account")
    flows.button(a, "Open the learning dashboard")
    assert flows.wait_text(a.page, "Learning dashboard", 15)
    assert flows.wait_text(a.page, "First-attempt accuracy", 10, ci=True) or flows.wait_text(a.page, "first try", 5, ci=True)
    shot(a, f"L41_learning_dashboard_{tag}", problems)
    t = text(a)
    assert email not in t, "no one is named"
    with a.page.expect_download() as got:
        flows.tap(a, a.page.get_by_role("button", name="Download the answers (CSV)"))
    rows = Path(got.value.path()).read_text().splitlines()
    assert len(rows) > 1 and email not in "\n".join(rows) and "user_id" not in rows[0]
    flows.open_app(p, app, "/learning")
    assert flows.wait_text(p.page, "Only admins", 10)
    assert not faults(problems), problems
