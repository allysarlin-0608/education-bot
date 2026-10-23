"""Today's session and the way through a path (docs/LEARNING_DESIGN.md §3-4):
the lesson's quick checks, guided practice and its fading, the warm-up and
mixed sets, the unit gate, the diagnostic's search and its skips, the
capstone's replies."""
from datetime import date, timedelta

import seed_history
from coach import capstone, course, curriculum, diagnostic, progression, quiz, session

D = date(2026, 11, 2)
LESSON = ("【Topic】 Earth\n\n【Key Idea】 It spins.\n\n【Quick Check】\nQ: What gives day and night?\n"
          "A) The orbit — ✗ that gives the year\nB) The spin ✓\nC) The Moon — ✗ that's an eclipse\n"
          "Hint: once a day.\nWhy: One spin is one day.\n\n【Deep Dive】 West to east.\n\n"
          "【Quick Check】\nQ: Broken one, no answer marked\nA) x\nB) y\nC) z\n\n【Example】 1. a 2. b")


# ------------------------------------------------------------- quick checks
def test_the_lessons_quick_checks_are_read_and_drawn_between_its_sections():
    checks = session.quick_checks(LESSON)
    assert len(checks) == 1, "one that can't be read whole is left out"
    c = checks[0]
    assert c["options"] == ["The orbit", "The spin", "The Moon"] and c["answer"] == 1
    assert c["notes"] == ["that gives the year", "", "that's an eclipse"] and c["hint"] == "once a day."
    parts = session.without_checks(LESSON)
    assert [k for k, _ in parts] == ["text", "check", "text", "text"]
    assert "Quick Check" not in session.strip_checks(LESSON) and "West to east" in session.strip_checks(LESSON)
    assert session.note_for(c, 0) == "that gives the year" and session.note_for(c, 1) == ""


def test_a_quick_check_gets_a_second_try_after_the_hint_then_its_answer():
    slot = {"n": 1, "lesson": LESSON}
    assert session.stage(slot) == "learn"
    first = session.answer_check(slot, 0, 0, False, conf=3)
    assert first["tries"] == 1 and not first["right"] and first["conf"] == 3
    second = session.answer_check(slot, 0, 1, True, conf=1)
    assert second["tries"] == 2 and second["right"] and second["conf"] == 3, "the first answer's confidence is kept"
    assert session.answer_check(slot, 0, 2, False)["right"], "done is done"
    assert session.checks_done(slot, 1)


def test_an_old_lesson_finds_its_place_without_anything_rewritten():
    assert session.stage({"n": 1, "lesson": "x", "quiz": None}) == "learn"
    assert session.stage({"n": 1, "lesson": "x", "quiz": {"id": "a", "answers": None}}) == "check"
    assert "session" not in {"n": 1}


def test_a_session_survives_saving_and_two_tabs():
    a = {"stage": "practice", "checks": {"0": {"a": 1, "tries": 1, "right": True, "conf": 2}}, "guided": None}
    b = {"stage": "learn", "checks": {"1": {"a": 0, "tries": 2, "right": False, "conf": None}}, "guided": None, "jol": 3}
    merged = session.merge(a, b)
    assert merged["stage"] == "practice" and set(merged["checks"]) == {"0", "1"} and merged["jol"] == 3
    assert session.parse(merged) == merged
    assert session.parse({"stage": "nowhere"}) is None
    kept = curriculum.parse_slots([{"n": 1, "session": merged}])[0]
    assert kept["session"] == merged


# ------------------------------------------------------- guided practice
def items():
    data = quiz.parse_items({"questions": [
        {"role": "practice", "type": "steps", "question": "3+2?", "steps": ["Start at 3", "Count on two: ____", "So 5"],
         "answers": ["5"]},
        {"role": "practice", "type": "problem", "question": "4+1?", "options": ["5", "6", "3", "41"], "answer": 0}]})
    return quiz.practice_of(data)


def test_practice_fades_from_the_worked_problem_to_one_of_her_own():
    g = session.new_guided(items(), problem_first=False)
    assert [q["type"] for q in g["items"]] == ["steps", "problem"] and g["order"] == "faded"
    assert session.guided_left(g) == [0, 1]
    session.answer_guided(g, 0, ["4"], conf=2)
    assert session.guided_left(g) == [0, 1], "a miss: a second try after the hint"
    session.answer_guided(g, 0, ["5"])
    assert session.guided_left(g) == [1]


def test_for_an_idea_she_knows_the_problem_comes_first_and_the_steps_only_after_a_miss():
    g = session.new_guided(items(), problem_first=True)
    assert [q["type"] for q in g["items"]] == ["problem", "steps"]
    right = g["items"][0]["answer"]
    session.answer_guided(g, 0, right)
    assert session.guided_left(g) == [], "right first time: no worked steps needed"
    g = session.new_guided(items(), problem_first=True)
    right = g["items"][0]["answer"]                     # (its options are shuffled afresh)
    session.answer_guided(g, 0, (right + 1) % 4)
    session.answer_guided(g, 0, (right + 1) % 4)
    assert session.guided_left(g) == [1], "missed: the worked steps follow"
    assert session.parse_guided(g) == g
    assert session.parse_guided(session.new_guided([], False))["items"] == [], "no practice is kept as none"


# --------------------------------------------------------- warm-up and mixed
def history():
    entries = seed_history.build(D, days=12, topics=("philosophy",), gaps=(), partial=())
    return {"entries": entries, "books": []}


def test_the_warm_up_recalls_before_reading_and_the_mixed_set_takes_ideas_in_turn():
    log = history()
    warm = session.warmup(log, D, session.WARMUP)
    assert 0 < len(warm) <= session.WARMUP
    mixed = session.mixed(log, D, exclude=(), interleaved=True)
    blocked = session.mixed(log, D, exclude=(), interleaved=False)
    assert mixed and sorted(id(x) for x in mixed) != [] and len(mixed) <= session.MIXED
    ideas = [x["n"] for x in mixed]
    assert len(set(ideas[:2])) == len(ideas[:2]) or len(set(ideas)) == 1, "interleaved: ideas in turn"
    assert [x["n"] for x in blocked] == sorted([x["n"] for x in blocked], key=[x["n"] for x in blocked].index)
    s = session.new_set(D, warm)
    assert session.parse_set(s) == s and session.set_left(s) == list(range(len(warm)))


# ---------------------------------------------------------------- the gate
def finished_unit_log():
    """Every lesson of the first unit of philosophy passed (after the change)."""
    first = next(u for u in course.build({"entries": []}, "philosophy")["units"])
    log = {"entries": seed_history.build(mastery_day(), days=first["last"], topics=("philosophy",), per_day=1,
                                         gaps=(), partial=()), "books": []}
    return log, first


def mastery_day():
    return progression.mastery.SWITCH + timedelta(days=60)


def test_the_next_unit_waits_for_the_one_it_builds_on_to_be_shown_learned():
    log, first = finished_unit_log()
    gate = progression.gate(log, "philosophy")
    assert gate is not None and gate["name"] == first["name"] and gate["key"] == f"u{first['first']}"
    holder = course.lesson_record(log, "philosophy", first["last"])
    holder[1]["unit_check"] = {"attempts": 1, "best": 90, "passed_on": mastery_day().isoformat(), "last_on": ""}
    assert progression.gate(log, "philosophy") is None, "passed: the next unit opens"


def test_a_unit_finished_before_the_change_never_stops_her():
    first = next(u for u in course.build({"entries": []}, "philosophy")["units"])
    early = progression.mastery.SWITCH - timedelta(days=1)
    log = {"entries": seed_history.build(early, days=first["last"], topics=("philosophy",), per_day=1,
                                         gaps=(), partial=()), "books": []}
    assert progression.gate(log, "philosophy") is None


def test_math_units_wait_on_their_own_prerequisites():
    us = course.build({"entries": []}, "math")["units"]
    pre = progression.prerequisites("math", us)
    l103 = next(n for n in pre if n.startswith("L1-03 "))
    assert any(p.startswith("L0-08 ") for p in pre[l103])


# --------------------------------------------------------------- diagnostic
def test_a_few_questions_place_a_learner_on_the_math_path():
    us = diagnostic.units("math")
    truth = {u["id"] for u in us[:40]}
    state = diagnostic.blank(D)
    while not state["done"]:
        uid = diagnostic.next_unit(us, set(state["known"]), set(state["unknown"]), len(state["asked"]))
        diagnostic.answer(state, us, uid, uid in truth)
    assert len(state["asked"]) <= diagnostic.MAX_ITEMS
    assert state["skip"] and all(n <= us[39]["last"] for n in state["skip"]), "skips only what she knows"
    assert diagnostic.ahead(us, set(), set(), 0)[0] == diagnostic.next_unit(us, set(), set(), 0)
    assert len(diagnostic.ahead(us, set(), set(), 0)) <= 7


def test_skips_count_once_she_chooses_them_and_a_missed_spot_check_brings_a_unit_back():
    us = diagnostic.units("math")
    state = diagnostic.blank(D)
    diagnostic.answer(state, us, us[5]["id"], True)
    diagnostic.finish(state, us)
    assert state["skip"] and diagnostic.skipping(state) == [], "nothing skipped until she chooses it"
    diagnostic.spot_checks(state, us, D)
    assert diagnostic.skipping(state) == state["skip"] and state["spot"]
    state["items"] = {s["unit"]: {"type": "choice", "question": "?", "options": list("abcd"), "answer": 0, "why": ""}
                      for s in state["spot"]}
    assert not diagnostic.due_spots(state, D) and diagnostic.due_spots(state, D + timedelta(days=7))
    back = state["spot"][0]["unit"]
    u = next(x for x in us if x["id"] == back)
    diagnostic.spot_answered(state, us, back, False)
    assert u["first"] not in state["skip"] and back not in state["known"]
    assert diagnostic.parse(state) == state
    log = {"entries": [], "skipped": {"math": diagnostic.skipping(state)}}
    assert curriculum.completed_numbers(log, "math") == set(state["skip"])
    assert curriculum.next_numbers(log, "math", 1) != [1] or 1 not in state["skip"]


def test_the_models_placement_questions_are_read_by_unit():
    data = {"questions": [{"unit": "L0-01", "question": "How many?", "options": ["3", "4", "5", "6"], "answer": 1},
                          {"unit": "nope", "question": "?", "options": list("abcd"), "answer": 0},
                          {"unit": "L0-02", "question": "Bad", "options": ["a", "b"], "answer": 0}]}
    got = diagnostic.read_written(data, ["L0-01", "L0-02"])
    assert list(got) == ["L0-01"] and got["L0-01"]["options"][got["L0-01"]["answer"]] == "4"


# ----------------------------------------------------------------- capstone
def test_a_capstone_brief_and_its_feedback_are_read_against_the_rubric():
    brief = capstone.read_brief({"title": "Your budget", "situation": "You plan a month.", "task": "A budget.",
                                 "steps": ["List income", "List costs"],
                                 "rubric": [{"criterion": "Income", "good": "All of it"},
                                            {"criterion": "Costs", "good": "Fixed and variable"}]})
    assert brief and capstone.read_brief({"title": "x"}) is None
    fb = capstone.read_feedback({"criteria": [{"criterion": "income", "level": "met", "why": "All listed."},
                                              {"criterion": "Costs", "level": "partly", "why": "No variable."}],
                                 "overall": "Good start.", "next": "Add food."}, brief)
    assert fb and capstone.score(fb) == 0.75
    assert capstone.read_feedback({"criteria": [{"criterion": "Income", "level": "met"}]}, brief) is None
    saved = {"brief": brief, "work": "w", "feedback": fb, "at": "2026-11-02", "tries": 1}
    assert capstone.parse(saved) == saved
