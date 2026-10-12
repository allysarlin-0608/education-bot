"""The unit check (coach/unitcheck.py, views/unit.py): offered once a unit's
lessons are all passed, made only of questions she has met (never one she
reported), the same set until it is marked, kept with her record, and
reached from Home and the course map. No AI call anywhere in it."""
import json
from datetime import date, timedelta

from coach import course, curriculum, llm, review, ui, unitcheck
from test_habit_pages import history_until
from test_mastery_pages import texts
from test_pages_smoke import app, loads

TODAY = date(2026, 10, 12)


def a_log(days=20):
    return {"entries": history_until(TODAY - timedelta(days=1), days=days, topics=("philosophy",)), "books": [], "paths": []}


def first_done(log):
    return next(u for u in unitcheck.units(log, "philosophy") if u["state"] == "done")


def test_offered_once_every_lesson_of_the_unit_is_passed():
    log = a_log()
    us = unitcheck.units(log, "philosophy")
    done = [u for u in us if u["state"] == "done"]
    assert done, "the seeded history finishes a unit"
    assert all(unitcheck.offered(log, "philosophy", u) for u in done)
    assert not any(unitcheck.offered(log, "philosophy", u) for u in us if u["state"] != "done")


def test_a_set_takes_from_every_lesson_in_turn_and_stays_the_same_until_marked():
    log = a_log()
    u = first_done(log)
    a = unitcheck.build(log, "philosophy", u, 0)
    assert len(a) == unitcheck.SIZE == 10
    lessons = {x["n"] for x in u["lessons"]}
    assert {it["n"] for it in a} == lessons, "every lesson of the unit has a question"
    assert a == unitcheck.build(log, "philosophy", u, 0), "the same set for the same attempt"
    assert [it["n"] for it in a] != [it["n"] for it in unitcheck.build(log, "philosophy", u, 1)] or \
        a != unitcheck.build(log, "philosophy", u, 1), "a new attempt, a new set"
    marks, pct = unitcheck.score(a, [0] * len(a))
    assert marks == [1] * len(a) and pct == 100
    assert unitcheck.score(a, [1] * len(a))[1] == 0


def test_a_reported_question_is_never_used():
    log = a_log()
    u = first_done(log)
    for x in u["lessons"]:
        _, slot, _ = course.lesson_record(log, "philosophy", x["n"])
        for q in slot["quiz"]["questions"][:9]:            # all but one question of each lesson reported
            review.drop_question(slot, "philosophy", q["question"])
    left = unitcheck.pool(log, "philosophy", u)
    assert all(len(qs) == 1 for _, qs in left)
    assert {q["question"] for _, qs in left for q in qs} == {"Seeded question 10?"}
    assert unitcheck.size(log, "philosophy", u) == len(u["lessons"])
    if len(u["lessons"]) < unitcheck.MIN_SIZE:
        assert not unitcheck.offered(log, "philosophy", u), "too few questions left: no check"


def test_home_points_only_to_the_unit_just_finished():
    log = a_log()
    u = unitcheck.just_finished(log, "philosophy", TODAY)
    assert u is not None and u["state"] == "done"
    assert u["last"] == max(x["last"] for x in unitcheck.units(log, "philosophy") if x["state"] == "done")
    assert unitcheck.just_finished(log, "philosophy", TODAY + timedelta(days=30)) is None, "a month on: not pointed to"
    _, slot, _ = course.lesson_record(log, "philosophy", u["last"])
    unitcheck.record(slot, 50, TODAY)
    assert unitcheck.just_finished(log, "philosophy", TODAY) is None, "taken once: the course map keeps it"


def test_the_result_is_kept_with_the_record_and_merged():
    slot = {"n": 5}
    r = unitcheck.record(slot, 70, TODAY)
    assert r == {"attempts": 1, "best": 70, "passed_on": "", "last_on": TODAY.isoformat()}
    r = unitcheck.record(slot, 90, TODAY + timedelta(days=1))
    assert r["attempts"] == 2 and r["best"] == 90 and r["passed_on"] == (TODAY + timedelta(days=1)).isoformat()
    r = unitcheck.record(slot, 60, TODAY + timedelta(days=2))
    assert r["best"] == 90 and r["passed_on"] == (TODAY + timedelta(days=1)).isoformat(), "a pass is never undone"
    other = {"attempts": 4, "best": 80, "passed_on": TODAY.isoformat(), "last_on": TODAY.isoformat()}
    m = unitcheck.merge(r, other)
    assert m["attempts"] == 4 and m["best"] == 90 and m["passed_on"] == TODAY.isoformat()
    assert unitcheck.parse({"attempts": 0}) is None and unitcheck.parse("x") is None
    assert unitcheck.parse({"attempts": 1, "best": 999, "passed_on": "nope"})["best"] is None
    # saved, read back, and kept when another copy of the day is saved
    saved = curriculum.parse_slots([{"n": 5, "lesson": "x", "unit_check": r}])
    assert saved[0]["unit_check"] == r
    assert "unit_check" not in curriculum.parse_slots([{"n": 5, "from": "2026-10-01", "unit_check": r}])[0]
    mine = {"date": "2026-10-10", "topic": "philosophy", "lessons": [{"n": 5, "lesson": "x", "completed": True}]}
    stored = {"date": "2026-10-10", "topic": "philosophy", "lessons": [{"n": 5, "lesson": "x", "completed": True,
                                                                         "unit_check": r}]}
    curriculum.merge_day(mine, stored, [5], None)
    assert mine["lessons"][0]["unit_check"] == r, "a save from an older copy never loses it"


def stored_check(tmp_path):
    log = json.loads((tmp_path / "log.json").read_text())
    return [s["unit_check"] for e in log["entries"] for s in e["lessons"] if s.get("unit_check")]


def test_from_home_to_a_passed_unit_check_and_the_course_map(monkeypatch, tmp_path):
    # covers: W-daily-today_unit, W-unit-uc_check, D-unit-save_day, W-unit-uc_again, W-unit-uc_back
    # covers: W-course-cm_uc_go
    monkeypatch.setattr(llm, "ask_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no AI call")))
    at = app(monkeypatch, tmp_path, subjects=("philosophy",),
             entries=history_until(ui.today() - timedelta(days=1), days=20, topics=("philosophy",)))
    loads(at, "views/daily.py")
    assert "Unit check ·" in texts(at) and "10 questions" in texts(at)
    at.button(key="today_unit").click().run()
    assert not at.exception and "80% passes it" in texts(at)
    loads(at, "views/unit.py", **{k: at.query_params[k][0] for k in ("subject", "unit")})   # (stay on it in the test)
    assert at.button(key="uc_check").disabled, "every question answered first"
    for r in at.radio:
        r.set_value(0)
    at.run()
    at.button(key="uc_check").click().run()
    t = texts(at)
    assert not at.exception and "100% · Passed" in t and "From lesson" in t
    kept = stored_check(tmp_path)
    assert len(kept) == 1 and kept[0]["best"] == 100 and kept[0]["passed_on"] == ui.today().isoformat()
    at.button(key="uc_again").click().run()
    assert not at.exception and at.button(key="uc_check").disabled, "a fresh set to take"
    at.button(key="uc_back").click().run()
    assert not at.exception and "unit check passed · best 100%" in texts(at)
    loads(at, "views/daily.py")
    assert "Unit check ·" not in texts(at), "taken: Home no longer points to it"


def test_not_passed_then_from_the_course_map(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path, subjects=("philosophy",),
             entries=history_until(ui.today() - timedelta(days=1), days=20, topics=("philosophy",)))
    loads(at, "views/course.py", subject="philosophy")
    go = [b for b in at.button if str(b.key).startswith("cm_uc_go_")]
    assert go and "Take the check" in str(go[0].proto.label)
    go[0].click().run()
    loads(at, "views/unit.py", subject="philosophy", unit=str(go[0].key).removeprefix("cm_uc_go_"))
    for r in at.radio:
        r.set_value(1)
    at.run()
    at.button(key="uc_check").click().run()
    t = texts(at)
    assert "0% · Not yet" in t and "You need 80%" in t
    assert stored_check(tmp_path)[0]["passed_on"] == ""
    at.button(key="uc_again").click().run()
    assert not at.exception and at.button(key="uc_check").disabled, "a new set, nothing answered yet"


def test_a_unit_not_finished_has_no_check(monkeypatch, tmp_path):
    # covers: W-unit-uc_back_none
    at = app(monkeypatch, tmp_path, subjects=("philosophy",),
             entries=history_until(ui.today() - timedelta(days=1), days=20, topics=("philosophy",)))
    loads(at, "views/unit.py", subject="philosophy", unit="u999")
    assert "Nothing to check here yet" in texts(at)
    at.button(key="uc_back_none").click().run()
    assert not at.exception
