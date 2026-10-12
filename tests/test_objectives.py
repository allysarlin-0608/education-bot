"""Each lesson of a goal has an objective (audit stage 3, P2-1): what she
can do after it, designed in the same AI call as the outline; it stays with
its lesson when parts are ticked or the path is trimmed, goes into the
lesson's and the quiz's instructions, and shows at the top of the lesson.
Paths designed before objectives work as before."""
from datetime import date

from coach import catalog, core, paths, practice, quiz, tokens
from test_goals import a_path, design_reply
from test_pages_smoke import app, loads
from test_goal_pages import texts


def with_objectives():
    units = [{"name": f"Part {u}", "lessons": [{"title": f"Idea {u}.{k}", "objective": f"Do thing {u}.{k}"}
                                               for k in range(4)]} for u in range(4)]
    return paths.read_design(design_reply(units=units), {"text": "Read a company's financial statements"})["path"]


def test_the_ai_is_asked_for_one_checkable_objective_per_lesson_within_budget():
    system, messages = paths.design_messages({"text": "x" * 300, "why": "y" * 400, "answers": "z" * 400}, 5)
    assert '"objective"' in system and "starting with a verb" in system
    assert tokens.estimate_request(system, messages, tokens.PATH_MAX_TOKENS) <= tokens.REQUEST_BUDGET


def test_objectives_are_kept_beside_their_lessons():
    p = with_objectives()
    assert p["units"][0]["lessons"][1] == "Idea 0.1" and p["units"][0]["objectives"][1] == "Do thing 0.1"
    assert paths.objective(p, 6) == "Do thing 1.1" and paths.objective(p, 99) == ""
    kept = paths.keep_units(p, ["Part 2"])                  # some parts: each keeps its own
    assert paths.objective(kept, 1) == "Do thing 2.0"
    gone = paths.remove_lesson(p, 0, 0)
    assert paths.objective(gone, 1) == "Do thing 0.1"
    assert all(len(u["objectives"]) == len(u["lessons"]) for u in paths.lighter(p)["units"])
    assert paths.parse_path(p) == p, "stored and read back as it was"


def test_a_path_designed_before_objectives_works_as_before():
    old = a_path()
    assert "objectives" not in old["units"][0] and paths.objective(old, 1) == ""
    catalog.use([old])
    assert catalog.goal_objective(old["id"], 1) == ""
    catalog.use([])


def test_the_lesson_and_its_quiz_are_told_the_objective():
    p = with_objectives()
    catalog.use([p])
    prompt = core.build_system_prompt(core.empty_log(), p["id"], date(2026, 9, 1),
                                      slot={"n": 2, "title": "Idea 0.1", "unit": "Part 0"}, public=True)
    assert "這一課的學習目標" in prompt and "Do thing 0.1" in prompt
    context = practice.quiz_context(core.empty_log(), p["id"], {"n": 2}, date(2026, 9, 1), goal=p)
    assert context["objective"] == "Do thing 0.1"
    _, messages = quiz.request({"n": 2, "title": "Idea 0.1", "lesson": "Text."}, context)
    assert "This lesson's objective: Do thing 0.1" in messages[0]["content"]
    catalog.use([])


def test_the_objective_shows_at_the_top_of_the_lesson(monkeypatch, tmp_path):
    p = with_objectives()
    at = app(monkeypatch, tmp_path, subjects=(p["id"],), paths=[p], history=False)
    loads(at, "views/daily.py")
    assert "be able to" in texts(at) and "Do thing 0.0" in texts(at)
