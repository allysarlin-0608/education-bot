from coach import steps


def day(*completed):
    return [{"n": k + 1, "title": f"T{k + 1}", "completed": c} for k, c in enumerate(completed)]


def kinds(plan, viewing):
    return [(s["state"], s["viewing"]) for s in steps.states(plan, viewing)]


def test_start_of_day():
    plan = day(False, False, False, False, False)
    assert steps.viewing(plan, None) == 0
    assert kinds(plan, 0) == [("current", True)] + [("locked", False)] * 4
    assert steps.label(plan) == "Lesson 1 of 5 · 0 done"


def test_one_done_viewing_the_next():
    plan = day(True, False, False, False, False)
    assert steps.viewing(plan, None) == 1
    assert kinds(plan, 1) == [("completed", False), ("current", True)] + [("locked", False)] * 3
    assert steps.label(plan) == "Lesson 2 of 5 · 1 done"


def test_reviewing_a_completed_lesson():
    plan = day(True, False, False, False, False)
    assert steps.viewing(plan, 0) == 0
    assert kinds(plan, 0)[:2] == [("completed", True), ("current", False)]


def test_a_locked_lesson_cant_be_opened():
    plan = day(True, False, False, False, False)
    assert steps.viewing(plan, 3) == 1                  # falls back to the current one
    assert steps.unlock_message(plan, 3) == "Unlocks after you pass Lesson 3's quiz"


def test_all_done():
    plan = day(True, True, True, True, True)
    assert steps.current(plan) is None
    assert steps.viewing(plan, None) is None            # the day's summary
    assert steps.viewing(plan, 2) == 2                  # reviewing still works
    assert [s["state"] for s in steps.states(plan, None)] == ["completed"] * 5
    assert steps.label(plan) == "All 5 lessons done"


def test_states_follow_the_data_not_positions():
    plan = day(True, True, False, False, False)
    plan[0]["n"], plan[3]["n"] = 11, 14                 # numbers come from the lessons
    assert [s["state"] for s in steps.states(plan, 2)] == ["completed", "completed", "current", "locked", "locked"]
    assert steps.unlock_message(plan, 4) == "Unlocks after you pass Lesson 14's quiz"
