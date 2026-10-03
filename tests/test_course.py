"""The course map: units, states of lessons, the current unit."""
from coach import course, curriculum


def written(topic, n, completed=False, **extra):
    s = curriculum.new_slot(topic, n)
    s.update(lesson=f"lesson {n}", completed=completed, **extra)
    return s


def test_states_follow_her_record_and_today():
    t = "fashion"
    log = {"entries": [
        {"date": "2026-10-01", "topic": t, "lessons": [written(t, 1, True, quiz={"best": 90}),
                                                       written(t, 2, False, passed_on="2026-10-03"),
                                                       written(t, 3)]},
        {"date": "2026-10-03", "topic": t, "lessons": [{**curriculum.new_slot(t, 2), "from": "2026-10-01", "completed": True},
                                                       written(t, 4, True)]}]}
    plan = [curriculum.new_slot(t, 5), curriculum.new_slot(t, 6)]
    m = course.build(log, t, plan)
    states = {x["n"]: x for u in m["units"] for x in u["lessons"]}
    assert states[1]["state"] == "done" and states[1]["passed"] == "2026-10-01" and states[1]["best"] == 90
    assert states[2]["state"] == "done" and states[2]["passed"] == "2026-10-03"    # passed a day later (D2)
    assert states[3]["state"] == "next" and states[3]["readable"]                  # written, not passed: next
    assert states[4]["state"] == "done"
    assert states[5]["state"] == "today" and states[6]["state"] == "today"
    assert states[7]["state"] == "ahead" and not states[7]["readable"]
    assert m["done"] == 3 and m["next"] == 3 and m["written"] == curriculum.written(t)
    assert sum(len(u["lessons"]) for u in m["units"]) == m["written"]


def test_units_done_current_and_ahead():
    t = "fashion"
    lessons = curriculum._load(t)
    first_unit = [n for n, (u, _) in enumerate(lessons, start=1) if u == lessons[0][0]]
    log = {"entries": [{"date": "2026-10-01", "topic": t,
                        "lessons": [written(t, n, True) for n in first_unit]}]}
    m = course.build(log, t)
    assert m["units"][0]["state"] == "done" and m["units"][0]["done_count"] == len(first_unit)
    assert m["current"] == 1 and m["units"][1]["state"] == "current"
    assert all(u["state"] == "ahead" for u in m["units"][2:])
    entry, slot, passed = course.lesson_record(log, t, first_unit[0])
    assert slot["lesson"] and passed == "2026-10-01"
    assert course.lesson_record(log, t, 999) is None


def test_a_new_learner_starts_at_lesson_one():
    m = course.build({"entries": []}, "cosmos")
    assert m["done"] == 0 and m["next"] == 1 and m["current"] == 0
    assert m["units"][0]["lessons"][0]["state"] == "next"
