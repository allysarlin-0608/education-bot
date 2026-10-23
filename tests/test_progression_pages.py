"""The pages of the way through a path: where to start (views/diagnostic.py),
the unit gate on Home, the capstone (views/capstone.py), with the model
replaced (no call leaves the test)."""
import json
import re
from datetime import timedelta

import seed_history
from coach import capstone, course, diagnostic, llm, prefs, progression, ui
from test_pages_smoke import app, loads


def fake_model(monkeypatch, calls):
    def ask(system, messages, max_tokens=900, salvage=None):
        text = messages[-1]["content"]
        if system.startswith("You write a short placement check"):
            calls.append("write")
            units = re.findall(r"^Unit (\S+):", text, re.M)
            return {"questions": [{"unit": u, "type": "choice", "question": f"Placement on {u}?",
                                   "options": ["Right", "Wrong", "Also wrong", "No"], "answer": 0,
                                   "notes": ["", "x", "y", "z"], "why": "."} for u in units]}, None
        if system.startswith("You check a quiz"):
            calls.append("check")
            return {"problems": []}, None
        if system.startswith("You design the capstone"):
            calls.append("brief")
            return {"title": "A real budget", "situation": "You plan next month.", "task": "Write your budget.",
                    "steps": ["List income", "List costs", "Balance it"],
                    "rubric": [{"criterion": "Income", "good": "All of it"}, {"criterion": "Costs", "good": "Both kinds"}]}, None
        if system.startswith("You give feedback on a learner's capstone"):
            calls.append("feedback")
            return {"criteria": [{"criterion": "Income", "level": "met", "why": "All listed."},
                                 {"criterion": "Costs", "level": "partly", "why": "Only fixed ones."}],
                    "overall": "A clear start.", "next": "Add variable costs."}, None
        raise AssertionError(system[:60])
    monkeypatch.setattr(llm, "ask_json", ask)


def stored_prefs(tmp_path):
    rows = json.loads((tmp_path / "learner_prefs.json").read_text())
    return prefs.normalize(rows[0]["data"])


def test_where_to_start_places_her_in_a_few_questions_and_she_chooses(monkeypatch, tmp_path):
    # covers: W-diagnostic-dg_go, W-diagnostic-dg_apply, W-daily-diag_open
    calls = []
    fake_model(monkeypatch, calls)
    at = app(monkeypatch, tmp_path, subjects=("math",), history=False)
    loads(at, "views/daily.py")
    assert any(b.key == "diag_open" for b in at.button), "offered before the first lesson"
    at.session_state["course_topic"] = "math"
    loads(at, "views/diagnostic.py", subject="math")
    at.button(key="dg_go").click().run()
    for _ in range(diagnostic.MAX_ITEMS + 1):
        radios = [r for r in at.radio if str(r.key).startswith("dg_math_")]
        if not radios:
            break
        radios[0].set_value(0).run()                       # "Right": she knows each one asked
        at.button(key=f"dg_{len(stored_prefs(tmp_path)['diag']['math']['asked'])}_conf2").click().run()
        assert not at.exception, [e.value for e in at.exception]
    state = stored_prefs(tmp_path)["diag"]["math"]
    assert state["done"] and state["skip"] and not state["applied"]
    assert calls.count("write") <= 4 and calls.count("write") == calls.count("check")
    at.button(key="dg_apply").click().run()
    state = stored_prefs(tmp_path)["diag"]["math"]
    assert state["applied"] and state["spot"]
    loads(at, "views/daily.py")
    assert at.session_state["coach_log"]["skipped"]["math"] == state["skip"]
    assert not any(b.key == "diag_open" for b in at.button), "placed: not offered again"


def test_i_dont_know_yet_starts_her_at_the_beginning(monkeypatch, tmp_path):
    # covers: W-diagnostic-dg_none
    calls = []
    fake_model(monkeypatch, calls)
    at = app(monkeypatch, tmp_path, subjects=("math",), history=False)
    loads(at, "views/diagnostic.py", subject="math")
    at.button(key="dg_go").click().run()
    for _ in range(diagnostic.MAX_ITEMS + 1):
        idk = [b for b in at.button if str(b.key).startswith("dg_idk_")]
        if not idk:
            break
        idk[0].click().run()
    state = stored_prefs(tmp_path)["diag"]["math"]
    assert state["done"] and not state["skip"] and state["start"] == 1
    at.button(key="dg_none").click().run()
    assert stored_prefs(tmp_path)["diag"]["math"]["applied"]


def test_the_next_unit_waits_on_home_for_the_unit_check(monkeypatch, tmp_path):
    # covers: W-daily-gate_check
    first = course.build({"entries": []}, "philosophy")["units"][0]
    day = ui.today()
    entries = seed_history.build(day, days=first["last"], topics=("philosophy",), per_day=1, gaps=(), partial=())
    monkeypatch.setattr(progression, "SWITCH", (day - timedelta(days=first["last"] + 5)).isoformat())
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=entries, pace=1)
    loads(at, "views/daily.py")
    assert any(b.key == "gate_check" for b in at.button), "the check stands before the next unit"
    assert not any(b.label == "Start this lesson" for b in at.button)
    at.button(key="gate_check").click().run()
    assert not at.exception


def test_a_finished_goal_ends_with_its_capstone(monkeypatch, tmp_path):
    # covers: W-capstone-cp_brief, W-capstone-cp_send, W-daily-capstone_open
    calls = []
    fake_model(monkeypatch, calls)
    gid = "g-00c0ffee"
    goal = {"id": gid, "title": "Budget my money", "outcome": "You can plan a month.", "goal": "Budget my money",
            "why": "to save for a trip", "level": "Beginner", "status": "active",
            "created_at": "2026-10-01T00:00:00+00:00",
            "units": [{"name": "Basics", "lessons": [{"title": "Income", "objective": "List income"},
                                                     {"title": "Costs", "objective": "List costs"}]}]}
    day = ui.today() - timedelta(days=1)
    lesson = lambda n, t: {"n": n, "title": t, "unit": "Basics", "kickoff": "k", "lesson": seed_history.LESSON,   # noqa: E731
                           "followups": [], "completed": True, "quiz": seed_history._quiz(f"c{n}", 9)}
    entries = [{"date": day.isoformat(), "topic": gid, "session_number": 1, "level": "Beginner", "completed": True,
                "title": "Lessons 1–2", "followup_question": "", "reflection": "", "lesson": "", "followups": [],
                "kickoff": "", "lessons": [lesson(1, "Income"), lesson(2, "Costs")]}]
    at = app(monkeypatch, tmp_path, subjects=(gid,), paths=[goal], entries=entries)
    loads(at, "views/daily.py")
    assert any(b.key == "capstone_open" for b in at.button), "every lesson done: the capstone"
    loads(at, "views/capstone.py", subject=gid, key=gid)
    at.button(key="cp_brief").click().run()
    assert calls == ["brief"] and stored_prefs(tmp_path)["capstones"][gid]["brief"]["title"] == "A real budget"
    at.text_area(key=f"cp_work_{gid}").input("My income is my wage and a little tutoring. " * 10).run()
    at.button(key="cp_send").click().run()
    assert not at.exception, [e.value for e in at.exception]
    mine = stored_prefs(tmp_path)["capstones"][gid]
    assert calls == ["brief", "feedback"] and mine["feedback"]["criteria"][1]["level"] == "partly" and mine["tries"] == 1


def test_practice_review_cards_and_the_collection_are_one_page(monkeypatch, tmp_path):
    # covers: W-practice_nav-pn_tabs
    at = app(monkeypatch, tmp_path, entries=seed_history.build(ui.today(), days=6, topics=("philosophy",)))
    loads(at, "views/practice.py")
    tabs = next(c for c in at.segmented_control if str(c.key).startswith("pn_tabs_"))
    assert tabs.value == "Practice" and list(tabs.options) == ["Practice", "Review cards", "Collection"]
    tabs.set_value("Review cards").run()
    assert not at.exception and at.session_state["rv_view"] == "Today"
    loads(at, "views/review.py")                      # (the test harness doesn't follow a page switch)
    tabs = next(c for c in at.segmented_control if str(c.key).startswith("pn_tabs_"))
    assert tabs.value == "Review cards"
    tabs.set_value("Collection").run()
    assert not at.exception and at.session_state["rv_view"] == "Collection"


def test_the_learning_dashboard_is_for_admins_only(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/learning.py")
    assert any("Only admins" in c.value for c in at.caption)
