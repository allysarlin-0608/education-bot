"""The pages with a goal of her own, without a browser (part of the check
before every push): the setup's goal and path steps, the New goal page,
Today on a goal's first day, Settings → Your goals, and every page that
shows a subject, with a goal among them."""
import html
import json

import pytest

from coach import catalog, llm, paths, settings, ui
from test_goals import a_path, design_reply
from test_pages_smoke import PAGES, app, loads


def ai(monkeypatch, *replies):
    """The model answers these, in order; returns the list of calls made."""
    calls, queue = [], list(replies)

    def ask(system, messages, max_tokens=0, salvage=None):
        calls.append(system)
        reply = queue.pop(0)
        return (None, reply) if isinstance(reply, str) else (reply, None)
    monkeypatch.setattr(llm, "ask_json", ask)
    return calls


def stored(tmp_path):
    return (json.loads((tmp_path / "settings.json").read_text())["user_settings"][0],
            json.loads((tmp_path / "log.json").read_text()) if (tmp_path / "log.json").exists() else {})


def has(at, key) -> bool:
    try:
        at.button(key=key)
    except KeyError:
        return False
    return True


def texts(at):
    return html.unescape( " ".join(str(h.proto) for h in at.get("html")) + " ".join(m.value for m in at.markdown))


def test_every_page_with_a_goal_first(monkeypatch, tmp_path):
    goal = a_path()
    at = app(monkeypatch, tmp_path, subjects=(goal["id"], "philosophy"), paths=[goal], history=False)
    assert not at.exception, [e.value for e in at.exception]
    for page in PAGES + ["views/goal.py"]:
        loads(at, page)
    loads(at, "views/course.py", subject=goal["id"])
    assert goal["outcome"] in texts(at), "the course map says what the path is for"
    loads(at, "views/world.py", subject=goal["id"])           # a goal has no world: today's subject's opens
    loads(at, "views/settings.py")
    assert goal["title"] in texts(at) and has(at, "set_goal_add")


def test_today_on_a_goals_first_day_is_made_for_her(monkeypatch, tmp_path):
    goal = a_path()
    at = app(monkeypatch, tmp_path, subjects=(goal["id"],), paths=[goal], history=False)
    loads(at, "views/daily.py")
    t = texts(at)
    assert "Made for you" in t and goal["title"] in t and "Because: “I want to invest”" in t
    assert not has(at, "today_world"), "a goal has no world to enter"


def test_the_setup_from_a_goal_to_the_first_day(monkeypatch, tmp_path):
    calls = ai(monkeypatch, {"status": "clarify", "message": "What for?", "questions": ["For work?"],
                             "suggestions": ["Read a company's financial statements"]}, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.button(key="ob_next").click().run()                         # Get started
    at.text_area(key="obg_text").input("Get good at business stuff").run()
    at.button(key="obg_design").click().run()
    assert not at.exception and "What for?" in texts(at), "a vague goal is asked about"
    at.button(key="obg_sugg_0").click().run()                     # her pick of the suggestions
    at.text_input(key="obg_why").input("I want to invest").run()
    at.button(key="obg_design").click().run()
    assert len(calls) == 2 and "Reading financial statements" in texts(at), "on to her path"
    # covers: W-goalmaker-k_key_f_up_i
    at.button(key="obp_skip_0").click().run()                     # she knows the first part
    at.button(key="obp_up_1").click().run()
    s, _ = stored(tmp_path)
    assert [u["name"] for u in s["onboarding"]["path"]["units"]] == ["Part 2", "Part 1", "Part 3"]
    at.button(key="obp_undo").click().run()
    assert len(stored(tmp_path)[0]["onboarding"]["path"]["units"]) == 4
    at.button(key="obp_lighter").click().run()
    for _ in range(3):                                              # path → subjects → reading → summary
        at.button(key="ob_next").click().run()
    assert "Your goal" in texts(at) and not at.exception
    at.button(key="ob_next").click().run()                          # Start learning
    s, log = stored(tmp_path)
    goal_id = log["paths"][0]["id"]
    assert s["onboarded_at"] and s["subjects"] == [goal_id] and s["onboarding"] is None
    assert log["paths"][0]["why"] == "I want to invest" and paths.lesson_count(log["paths"][0]) < 16
    assert len(calls) == 2, "nothing asked again on the way"


def test_a_refresh_mid_goal_keeps_her_words_and_path(monkeypatch, tmp_path):
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.button(key="ob_next").click().run()
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    calls = ai(monkeypatch)                                        # no more answers: a call would fail the test
    again = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False,
                onboarding=stored(tmp_path)[0]["onboarding"])
    assert not again.exception and "Reading financial statements" in texts(again) and not calls


def test_back_from_the_path_to_her_words_and_forward_again(monkeypatch, tmp_path):
    # covers: W-setup-ob_to_path
    calls = ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.button(key="ob_next").click().run()
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    at.button(key="ob_back").click().run()
    assert at.text_area(key="obg_text").value == "Read a company's financial statements"
    at.button(key="ob_to_path").click().run()
    assert "Reading financial statements" in texts(at) and len(calls) == 1


def test_subjects_instead_of_a_goal_is_the_setup_as_before(monkeypatch, tmp_path):
    # covers: W-goalmaker-k_key_skip
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.button(key="ob_next").click().run()
    at.button(key="obg_skip").click().run()
    assert not at.exception and "Choose up to three" in texts(at)


@pytest.mark.parametrize("reply, shown", [
    ({"status": "narrow", "message": "That's years of study.", "suggestions": ["Learn basic first aid"]}, "years of study"),
    ({"status": "decline", "message": "We can't teach that here.", "suggestions": ["How investing works"]}, "can't teach"),
    (llm.LIMIT, "today's limit"),
    ({"status": "ok", "units": []}, "couldn't design a path"),
])
def test_a_goal_that_cant_be_planned_is_answered_kindly(monkeypatch, tmp_path, reply, shown):
    ai(monkeypatch, reply)
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.button(key="ob_next").click().run()
    at.text_area(key="obg_text").input("Become a doctor by next month").run()
    at.button(key="obg_design").click().run()
    assert not at.exception and shown in texts(at)
    assert at.text_area(key="obg_text").value == "Become a doctor by next month", "her words are kept"


def test_a_new_goal_for_someone_already_learning_starts_today(monkeypatch, tmp_path):
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/goal.py")
    at.text_area(key="goal_text").input("Read a company's financial statements").run()
    at.button(key="goal_design").click().run()
    at.button(key="goal_add").click().run()
    assert not at.exception
    s, log = stored(tmp_path)
    goal_id = log["paths"][0]["id"]
    catalog.use(log["paths"])
    assert goal_id in s["subjects"] and settings.topic_for(s, ui.today(), ui.TIMEZONE) == goal_id
    assert "Made for you" in texts(at), "straight to her first lesson"


def test_a_new_goal_when_today_is_already_started_begins_tomorrow(monkeypatch, tmp_path):
    # covers: W-goal-goal_today, W-goal-goal_again, W-goal-goal_cancel
    from datetime import timedelta
    import seed_history
    ai(monkeypatch, design_reply(), design_reply())
    day = seed_history.build(ui.today() + timedelta(days=1), days=1, topics=("philosophy",))
    for e in day:
        e["date"] = ui.today().isoformat()
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), entries=day)
    loads(at, "views/goal.py")
    at.text_area(key="goal_text").input("Read a company's financial statements").run()
    at.button(key="goal_design").click().run()
    at.button(key="goal_again").click().run()                     # start over: her words stay
    assert at.text_area(key="goal_text").value == "Read a company's financial statements"
    at.button(key="goal_design").click().run()
    at.button(key="goal_add").click().run()
    assert not at.exception and "Your first lesson is on" in texts(at)
    s, log = stored(tmp_path)
    catalog.use(log["paths"])
    assert settings.topic_for(s, ui.today() + timedelta(days=1), ui.TIMEZONE) == log["paths"][0]["id"]
    at.button(key="goal_today").click().run()
    assert not at.exception
    loads(at, "views/goal.py")
    at.text_area(key="goal_text").input("Something else to learn").run()
    at.button(key="goal_cancel").click().run()
    assert not at.exception and stored(tmp_path)[0]["onboarding"]["goal"]["text"] == ""


def test_pausing_and_resuming_a_goal(monkeypatch, tmp_path):
    goal = a_path()
    at = app(monkeypatch, tmp_path, subjects=("philosophy", goal["id"]), paths=[goal], history=False)
    loads(at, "views/settings.py")
    at.button(key=f"setgoal_pause_{goal['id']}").click().run()
    s, log = stored(tmp_path)
    assert s["subjects"] == ["philosophy"] and log["paths"][0]["status"] == "archived"
    at.button(key=f"setgoal_resume_{goal['id']}").click().run()
    s, log = stored(tmp_path)
    assert s["subjects"] == ["philosophy", goal["id"]] and log["paths"][0]["status"] == "active"


def test_the_last_goal_cant_be_paused(monkeypatch, tmp_path):
    goal = a_path()
    at = app(monkeypatch, tmp_path, subjects=(goal["id"],), paths=[goal], history=False)
    loads(at, "views/settings.py")
    at.button(key=f"setgoal_pause_{goal['id']}").click().run()
    assert "Keep at least one subject or goal." in texts(at)
    assert stored(tmp_path)[0]["subjects"] == [goal["id"]]
