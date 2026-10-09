"""A goal of her own: the path the AI designs (coach/paths.py), how it
becomes a subject like the others (coach/catalog.py, settings, curriculum,
the lesson prompt), the making of it (coach/goalmaker.py) and the numbers
(coach/metrics.py)."""
import threading
from datetime import date, timedelta

import pytest
import streamlit as st

from coach import catalog, core, curriculum, goalmaker, llm, metrics, paths, settings

TZ = None


def design_reply(**over):
    data = {"status": "ok", "title": "Reading financial statements",
            "outcome": "By the end you will be able to read the three main statements.",
            "level": "Beginner",
            "units": [{"name": f"Part {u}", "lessons": [f"Idea {u}.{k}" for k in range(4)]} for u in range(4)]}
    data.update(over)
    return data


def a_path(**over):
    goal = {"text": "Read a company's financial statements", "why": "I want to invest", "start": "new"}
    path = paths.read_design(design_reply(), goal)["path"]
    path.update(over)
    return path


@pytest.fixture(autouse=True)
def no_goals():
    catalog.use([])
    yield
    catalog.use([])


# ------------------------------------------------------------------ her goal
@pytest.mark.parametrize("text, ok", [
    ("Read a company's financial statements", True),
    ("hi", False),                                  # too short to plan
    ("x" * (paths.GOAL_MAX_CHARS + 1), False),     # too much at once
    ("business", False),                            # a field, not a goal
    ("learn history", False),
    ("history of Japan before a trip", True),
])
def test_a_goal_is_looked_at_before_any_ai_call(text, ok):
    assert (paths.precheck(text) is None) == ok


def test_a_good_reply_becomes_a_path_with_her_reasons():
    p = a_path()
    assert catalog.is_goal(p["id"]) and p["status"] == "active"
    assert p["why"] == "I want to invest" and paths.lesson_count(p) == 16


@pytest.mark.parametrize("status", ["clarify", "narrow", "decline"])
def test_a_goal_that_cant_be_planned_yet_comes_back_kindly(status):
    r = paths.read_design({"status": status, "questions": ["q1", "q2", "q3"], "suggestions": ["a", "b", "c", "d"]}, {})
    assert r["status"] == status and r["message"] and len(r["questions"]) <= 2 and len(r["suggestions"]) == 3


@pytest.mark.parametrize("reply", [None, "text", {}, {"status": "maybe"},
                                   design_reply(units=[{"name": "One", "lessons": ["a", "b"]}]),   # too short
                                   design_reply(title=""), design_reply(units="nope")])
def test_a_reply_that_cant_be_used_is_an_error_and_nothing_is_kept(reply):
    assert paths.read_design(reply, {"text": "x"}) == {"status": "error"}


def test_a_path_is_trimmed_to_its_limits_and_repeats_dropped():
    units = [{"name": f"U{u}", "lessons": ["Same lesson"] + [f"L{u}.{k}" for k in range(20)]} for u in range(12)]
    p = paths.parse_path(dict(a_path(), units=units))
    assert len(p["units"]) <= paths.MAX_UNITS and all(len(u["lessons"]) <= paths.MAX_LESSONS for u in p["units"])
    titles = [t for u in p["units"] for t in u["lessons"]]
    assert titles.count("Same lesson") == 1 and len(titles) <= paths.MAX_TOTAL


def test_a_stored_path_with_a_bad_id_or_shape_is_not_read():
    assert paths.parse_path(dict(a_path(), id="../x")) is None
    assert paths.parse_path("path") is None


# ------------------------------------------------------------------ adjusting
def test_adjustments_need_no_ai_and_keep_at_least_one_lesson():
    p = a_path()
    assert paths.lesson_count(paths.lighter(p)) < paths.lesson_count(p)
    assert paths.with_level(p, "Advanced")["level"] == "Advanced"
    assert paths.with_level(p, "Expert")["level"] == p["level"]
    moved = paths.move_unit(p, 0, 1)
    assert [u["name"] for u in moved["units"][:2]] == ["Part 1", "Part 0"]
    assert paths.move_unit(p, 0, -1) == p                      # nowhere to go
    assert len(paths.remove_unit(p, 1)["units"]) == 3
    one = dict(p, units=[{"name": "Only", "lessons": ["a"]}])
    assert paths.remove_unit(one, 0) == one and paths.remove_lesson(one, 0, 0) == one
    gone = paths.remove_lesson(dict(p, units=[{"name": "A", "lessons": ["x"]}, {"name": "B", "lessons": ["y", "z"]}]), 0, 0)
    assert [u["name"] for u in gone["units"]] == ["B"], "a part left with no lesson goes too"


# ---------------------------------------------- a subject like the others
def test_her_goals_are_hers_alone_in_each_session():
    mine, theirs = a_path(), a_path()
    seen = {}

    def other():
        catalog.use([theirs])
        seen["other"] = (catalog.known(mine["id"]), catalog.known(theirs["id"]))

    catalog.use([mine])
    t = threading.Thread(target=other)
    t.start()
    t.join()
    assert catalog.known(mine["id"]) and not catalog.known(theirs["id"])
    assert seen["other"] == (False, True)


def test_a_goal_has_a_syllabus_a_name_and_a_level():
    p = a_path(level="Intermediate")
    catalog.use([p])
    g = p["id"]
    assert curriculum.has_syllabus(g) and curriculum.written(g) == 16
    assert curriculum.lesson(g, 5) == {"n": 5, "unit": "Part 1", "title": "Idea 1.0"}
    assert catalog.name(g) == p["title"] and catalog.name("g-00000000") == "Your goal"
    assert settings.start_level(settings.blank("u"), g) == "Intermediate"
    plan = curriculum.day_plan(core.empty_log(), g, None, 3)
    assert [s["n"] for s in plan] == [1, 2, 3] and plan[0]["title"] == "Idea 0.0"


def test_a_goal_in_her_records_survives_a_backup():
    p = a_path()
    log = core.parse_log({"entries": [], "books": [], "paths": [p, p, {"id": "bad"}]})
    assert log["paths"] == [p]


# ------------------------------------------------------------------ her turns
def onboarded(subjects, day0):
    return dict(settings.blank("u"), subjects=subjects, subject_levels={"philosophy": "Beginner", "cosmos": "Beginner"},
                onboarded_at=f"{day0.isoformat()}T01:00:00+00:00")


def test_a_new_goal_takes_today_and_the_others_shift():
    p = a_path()
    catalog.use([p])
    day0 = date(2026, 9, 1)
    s = onboarded(["philosophy", "cosmos"], day0)
    for k in range(4):
        today = day0 + timedelta(days=k)
        new = settings.add_goal(s, p["id"], "now", today, TZ)
        assert settings.topic_for(new, today, TZ) == p["id"], f"day {k}"
        assert set(settings.chosen_subjects(new)) == {"philosophy", "cosmos", p["id"]}


def test_a_day_already_started_keeps_its_subject():
    p = a_path()
    catalog.use([p])
    day0 = date(2026, 9, 1)
    s = onboarded(["philosophy", "cosmos"], day0)
    log = {"entries": [{"date": day0.isoformat(), "topic": "philosophy", "lessons": [{"n": 1}]}]}
    new = settings.add_goal(s, p["id"], "now", day0, TZ)
    assert settings.topic_for(new, day0, TZ, log) == "philosophy"


def test_paused_goals_leave_the_turns_and_the_limit_holds():
    goals = [a_path() for _ in range(settings.MAX_GOALS + 1)]
    catalog.use(goals[:-1] + [dict(goals[-1], status="archived")])
    s = dict(settings.blank("u"), subjects=[g["id"] for g in goals])
    assert goals[-1]["id"] not in settings.chosen_subjects(s)
    full = dict(s, subjects=[g["id"] for g in goals[:-1]])
    with pytest.raises(ValueError):
        settings.add_goal(full, goals[-1]["id"], "now")


def test_a_goal_alone_is_a_whole_setup_and_comes_first():
    p = a_path()
    d = dict(settings.new_draft(), path=p, subjects=["cosmos"])
    catalog.use([p])
    done = settings.finish(settings.blank("u"), d, "2026-09-01T00:00:00+00:00")
    assert done["subjects"] == [p["id"], "cosmos"]
    alone = settings.finish(settings.blank("u"), dict(settings.new_draft(), path=p), "2026-09-01T00:00:00+00:00")
    assert alone["subjects"] == [p["id"]] and not settings.errors(alone)


def test_the_goal_being_made_is_kept_in_the_draft_and_checked():
    p = a_path()
    s = dict(settings.blank("u"), onboarding={"goal": {"text": "Learn x", "why": 3, "start": "pro"},
                                              "design": {"status": "clarify", "message": "More?", "calls": 1},
                                              "path": p, "path_original": {"id": "bad"}})
    d = settings.draft_of(s)
    assert d["goal"] == {"text": "Learn x", "why": "3", "start": "new", "answers": ""}
    assert d["design"]["status"] == "clarify" and d["path"] == p and d["path_original"] is None
    assert settings.draft_of(dict(s, onboarding={"path": "x"}))["path"] is None


# -------------------------------------------------------------- the lesson
def test_a_goal_lesson_is_taught_from_her_words_with_sources():
    p = a_path()
    catalog.use([p])
    prompt = core.build_system_prompt(core.empty_log(), p["id"], date(2026, 9, 1),
                                      slot={"n": 1, "title": "Idea 0.0", "unit": "Part 0"}, public=True)
    assert p["goal"] in prompt and "I want to invest" in prompt and p["outcome"] in prompt
    assert "Source:" in prompt and "第一課" in prompt
    assert "Allysa" not in prompt and "17" not in prompt


def test_the_personal_app_prompt_is_unchanged():
    original = (core.PROMPTS_DIR / "learner.md").read_text(encoding="utf-8") + "\n" + \
        (core.PROMPTS_DIR / "core.md").read_text(encoding="utf-8")
    assert core.load_system_prompt("cosmos").startswith(original)
    assert "Allysa" in original and all(k in core.load_system_prompt("business") for k in core.PUBLIC_EDITS)
    public = core.load_system_prompt("business", public=True)
    assert not any(k in public for k in core.PUBLIC_EDITS if k), "every personal line has its public form"


# ------------------------------------------------------------ making a goal
class Draft:
    """A draft kept where goalmaker keeps it, and the AI calls it made."""
    def __init__(self, replies):
        self.d = settings.new_draft()
        self.replies = list(replies)
        self.calls = 0

    def get(self):
        return {**self.d, "goal": dict(self.d["goal"])}

    def put(self, d):
        self.d = d

    def ask(self, system, messages, max_tokens=0):
        self.calls += 1
        reply = self.replies.pop(0)
        return (None, reply) if isinstance(reply, str) else (reply, None)


@pytest.fixture
def maker(monkeypatch):
    def make(*replies):
        box = Draft(replies)
        monkeypatch.setattr(llm, "ask_json", box.ask)
        for k in [k for k in st.session_state if k.startswith("t_")]:
            del st.session_state[k]
        return box
    return make


def say(text, answers=""):
    st.session_state["t_text"] = text
    st.session_state["t_answers"] = answers


def test_the_same_answers_are_never_designed_twice(maker):
    box = maker(design_reply())
    say("Read a company's financial statements")
    assert goalmaker.design("t", box.get(), box.put, 3)
    assert goalmaker.design("t", box.get(), box.put, 3), "a second click finds the path"
    assert box.calls == 1 and box.d["path"]["title"] == "Reading financial statements"


def test_a_vague_goal_gets_one_more_try_with_her_answer(maker):
    box = maker({"status": "clarify", "questions": ["For work?"]}, {"status": "clarify"}, design_reply())
    say("Get good at business stuff")
    assert not goalmaker.design("t", box.get(), box.put, 3)
    assert box.d["design"]["status"] == "clarify"
    say("Get good at business stuff", answers="For my own shop")
    assert not goalmaker.design("t", box.get(), box.put, 3)
    say("Get good at business stuff", answers="Pricing")
    assert not goalmaker.design("t", box.get(), box.put, 3), "past the tries: pick a goal or write another"
    assert box.calls == paths.DESIGN_ATTEMPTS
    say("Plan and price a small side business")             # another goal: its own tries
    assert goalmaker.design("t", box.get(), box.put, 3) and box.calls == 3


def test_a_failed_call_keeps_her_goal_and_can_be_tried_again(maker):
    box = maker(llm.LIMIT, design_reply())
    say("Read a company's financial statements")
    assert not goalmaker.design("t", box.get(), box.put, 3)
    assert box.d["design"]["status"] == "error" and box.d["design"]["message"] == llm.LIMIT
    assert box.d["goal"]["text"] == "Read a company's financial statements"
    assert goalmaker.design("t", box.get(), box.put, 3) and box.calls == 2


def test_a_goal_too_short_to_plan_costs_no_call(maker):
    box = maker()
    say("hi")
    assert not goalmaker.design("t", box.get(), box.put, 3) and box.calls == 0


def test_a_new_goal_that_cant_be_planned_drops_the_old_path(maker):
    box = maker(design_reply(), {"status": "narrow", "suggestions": ["a"]})
    say("Read a company's financial statements")
    goalmaker.design("t", box.get(), box.put, 3)
    say("Become a doctor in a month")
    assert not goalmaker.design("t", box.get(), box.put, 3)
    assert box.d["path"] is None and box.d["design"]["status"] == "narrow"


# ----------------------------------------------------------------- numbers
def test_the_numbers_count_people_not_content():
    d0 = date(2026, 9, 1)
    users = [{"user_id": "a", "created_at": "2026-09-01T02:00:00Z"},
             {"user_id": "b", "created_at": "2026-09-01T03:00:00Z"},
             {"user_id": "c", "created_at": "2026-09-09T03:00:00Z"},
             {"user_id": "old", "created_at": "2026-01-01T03:00:00Z"}]
    ev = [("a", d0, "goal_created", 1), ("a", d0, "lesson_passed", 3), ("a", d0 + timedelta(days=1), "visit", 1),
          ("a", d0 + timedelta(days=8), "visit", 1), ("a", d0 + timedelta(days=8), "lesson_passed", 2),
          ("b", d0, "setup_done", 1), ("b", d0, "visit", 1),
          ("old", d0, "lesson_passed", 5)]
    events = [{"user_id": u, "day": d, "event": e, "count": n} for u, d, e, n in ev]
    m = metrics.summarize(users, events, d0, d0 + timedelta(days=9))
    assert m["signed_up"] == 3 and m["set_up"] == 2 and m["first_lesson"] == 1
    assert m["came_back_next_day"] == 1 and m["eligible_next_day"] == 3
    assert m["active_after_a_week"] == 1 and m["eligible_week"] == 2
    assert m["lessons_per_learner_week"] == round((3 + 2 + 5) / 3, 1)
    assert metrics.share(1, 2) == "50%" and metrics.share(1, 0) == "—"


# ------------------------------------------- found by the review (ISS-044 …)
def test_a_path_she_takes_down_to_one_lesson_is_still_hers():
    p = a_path()
    for _ in range(3):
        p = paths.remove_unit(p, 0)
    p = paths.remove_lesson(p, 0, 0)
    d = settings.draft_of(dict(settings.blank("u"), onboarding={"goal": {"text": "x"}, "path": p, "path_original": p}))
    assert d["path"] == p and paths.lesson_count(p) == 3
    assert paths.read_design(design_reply(units=[{"name": "U", "lessons": ["a", "b", "c"]}]), {}) == {"status": "error"}, \
        "the AI's path itself must have four or more"


def test_a_path_let_go_of_is_designed_again_for_the_same_words(maker):
    box = maker(design_reply(), design_reply())
    say("Read a company's financial statements")
    goalmaker.design("t", box.get(), box.put, 3)
    box.d["path"] = None                                   # (gone from the draft)
    assert goalmaker.design("t", box.get(), box.put, 3) and box.calls == 2, "never stuck with no path and no way on"


def test_goals_that_couldnt_be_read_stay_in_her_turns():
    p = a_path()
    s = dict(settings.blank("u"), subjects=["philosophy", p["id"]])
    was = (catalog._source, catalog._failed)
    catalog.bind(lambda: [], lambda: True)                  # her goals unreadable this run
    try:
        assert settings.chosen_subjects(s) == ["philosophy", p["id"]]
        assert settings.toggle_subject(settings.chosen_subjects(s), "cosmos") == ["philosophy", p["id"], "cosmos"]
        catalog.bind(lambda: [], lambda: False)             # read, and not there: gone
        assert settings.chosen_subjects(s) == ["philosophy"]
    finally:
        catalog.bind(*was)


@pytest.mark.parametrize("old, now", [(1, "subjects"), (2, "customize"), (3, "customize"), (4, "reading"),
                                      (5, "review")])
def test_a_setup_draft_from_before_goals_opens_on_the_same_step(old, now):
    d = settings.draft_of(dict(settings.blank("u"), onboarding={"step": old, "subjects": ["cosmos"]}))
    assert settings.STEPS[d["step"]] == now


@pytest.mark.parametrize("old, now", [(0, "welcome"), (1, "goal"), (2, "path"), (3, "subjects"), (4, "customize"),
                                      (5, "customize"), (6, "reading"), (7, "review")])
def test_a_setup_draft_from_before_plans_opens_on_the_same_step(old, now):
    d = settings.draft_of(dict(settings.blank("u"), onboarding={"step": old, "goal": {"text": "x"}}))
    assert settings.STEPS[d["step"]] == now and d["plan"] is None, "(her plan is asked: the setup goes back to it)"


def test_a_draft_keeps_its_plan_and_her_order_of_turns():
    p = a_path()
    saved = dict(settings.new_draft(), step=settings.STEPS.index("price"), plan="plus", subjects=["cosmos", "philosophy"],
                 path=p, path_original=p, goal_at=1)
    d = settings.draft_of(dict(settings.blank("u"), onboarding=saved))
    assert settings.STEPS[d["step"]] == "price" and d["plan"] == "plus"
    assert settings.rotation(d) == ["cosmos", settings.GOAL, "philosophy"]
    d = settings.move_turn(d, "philosophy", -2)
    assert settings.rotation(d) == ["philosophy", "cosmos", settings.GOAL]
    d = settings.move_turn(d, settings.GOAL, -9)                     # (as far as it goes)
    assert settings.rotation(d) == [settings.GOAL, "philosophy", "cosmos"]
    d["levels"] = {}
    done = settings.finish(settings.blank("u"), d, "2026-10-09T00:00:00+00:00")
    assert done["subjects"] == [p["id"], "philosophy", "cosmos"], "saved in her order"


def test_the_weekly_average_rounds_as_the_database_does():
    d0 = date(2026, 9, 7)
    events = [{"user_id": u, "day": d0, "event": "lesson_passed", "count": n} for u, n in (("a", 2), ("b", 2), ("c", 2), ("d", 3))]
    assert metrics.summarize([], events, d0, d0)["lessons_per_learner_week"] == 2.3     # 9 / 4 = 2.25
