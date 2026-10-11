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


def to_goal(at, identity="Working adult"):
    """From who she is (asked once) to what she wants to learn."""
    at.button(key=f"pick_ident_{identity}").click().run()
    at.button(key="ob_next").click().run()                         # Get started


def all_of_it(at, scope_key="obs_scope"):
    """The outline: all of it."""
    at.segmented_control(key=scope_key).set_value("all").run()


def first_purpose(at, key="obp"):
    at.button(key=f"{key}_pp_0").click().run()


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
    # covers: W-goalmaker-k_key_scope, W-goalmaker-k_key_f_part_i, W-goalmaker-k_key_f_pp_i
    calls = ai(monkeypatch, {"status": "clarify", "message": "What for?", "questions": ["For work?"],
                             "suggestions": ["Read a company's financial statements"]}, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.text_area(key="obg_text").input("Get good at business stuff").run()
    at.button(key="obg_design").click().run()
    assert not at.exception and "What for?" in texts(at), "a goal it can't tell is asked about"
    at.button(key="obg_sugg_0").click().run()                     # her pick of the suggestions
    at.button(key="obg_design").click().run()
    assert len(calls) == 2 and "16 lessons in 4 parts" in texts(at), "on to the outline"
    at.segmented_control(key="obs_scope").set_value("some").run()
    at.checkbox(key="obs_part_0").uncheck().run()                  # she knows the first part
    s, _ = stored(tmp_path)
    assert [u["name"] for u in s["onboarding"]["path"]["units"]] == ["Part 1", "Part 2", "Part 3"]
    assert "You chose 12 of 16 lessons" in texts(at)
    at.button(key="ob_next").click().run()                          # → what it's for
    first_purpose(at)
    at.button(key="ob_next").click().run()                          # → confirm
    t = texts(at)
    assert "Is this right?" in t and "You're a working adult" in t and "12 lessons" in t and "Useful at work" in t
    at.button(key="ob_next").click().run()                          # Start learning
    s, log = stored(tmp_path)
    goal_id = log["paths"][0]["id"]
    assert s["onboarded_at"] and s["subjects"] == [goal_id] and s["onboarding"] is None
    assert log["paths"][0]["why"] == "Useful at work" and paths.lesson_count(log["paths"][0]) == 12
    assert len(calls) == 2, "nothing asked again on the way"
    from test_habit_pages import stored_prefs
    assert stored_prefs(tmp_path)["identity"] == "Working adult", "who she is is kept"


def test_a_refresh_mid_goal_keeps_her_words_and_path(monkeypatch, tmp_path):
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    calls = ai(monkeypatch)                                        # no more answers: a call would fail the test
    again = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False,
                onboarding=stored(tmp_path)[0]["onboarding"])
    assert not again.exception and "Reading financial statements" in texts(again) and not calls


def test_back_to_her_goal_and_a_different_one(monkeypatch, tmp_path):
    # covers: W-setup-ob_again
    calls = ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    assert "All of it, or some parts?" in texts(at)
    at.button(key="ob_back").click().run()                          # back: what she asked for, as it was
    assert "Reading financial statements" in texts(at) and len(calls) == 1
    at.button(key="ob_again").click().run()                         # something else: her words stay
    assert at.text_area(key="obg_text").value == "Read a company's financial statements" and len(calls) == 1


def test_someone_who_doesnt_know_yet_narrows_it_down_to_an_outline(monkeypatch, tmp_path):
    # covers: W-goalmaker-k_key_skip, W-choices-pick, W-setup-ob_back-3
    calls = ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.button(key="obg_skip").click().run()                         # I don't know yet
    t = texts(at)
    assert all(x in t for x in ("Languages", "Math", "Natural science", "Society", "Arts", "Technology"))
    at.button(key="pick_dir0_Society").click().run()
    at.button(key="pick_dir1_Economics").click().run()
    at.button(key="ob_back").click().run()                          # one level back up
    assert "Economics" in texts(at) and has(at, "pick_dir1_Psychology")
    at.button(key="pick_dir1_Economics").click().run()
    at.button(key="pick_dir2_Behavioral economics").click().run()   # nothing narrower: its outline
    assert not at.exception and len(calls) == 1 and "All of it, or some parts?" in texts(at)
    s, _ = stored(tmp_path)
    assert s["onboarding"]["goal"]["text"] == "Economics: Behavioral economics"


@pytest.mark.parametrize("reply, shown", [
    ({"status": "narrow", "message": "That's years of study.", "suggestions": ["Learn basic first aid"]}, "years of study"),
    ({"status": "decline", "message": "We can't teach that here.", "suggestions": ["How investing works"]}, "can't teach"),
    (llm.LIMIT, "today's limit"),
    ({"status": "ok", "units": []}, "couldn't design a path"),
])
def test_a_goal_that_cant_be_planned_is_answered_kindly(monkeypatch, tmp_path, reply, shown):
    ai(monkeypatch, reply)
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
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
    assert at.button(key="goal_add").disabled, "all of it or some parts, and what it's for, first"
    all_of_it(at, "gs_scope")
    first_purpose(at, "gp")
    at.button(key="goal_add").click().run()
    assert not at.exception
    s, log = stored(tmp_path)
    goal_id = log["paths"][0]["id"]
    catalog.use(log["paths"])
    assert goal_id in s["subjects"] and settings.topic_for(s, ui.today(), ui.TIMEZONE) == goal_id
    assert "first turn is today" in texts(at), "how it shares her days, said first"
    at.button(key="goal_today").click().run()                       # Start its first lesson
    loads(at, "views/daily.py")
    assert "Made for you" in texts(at), "her first lesson"


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
    all_of_it(at, "gs_scope")
    first_purpose(at, "gp")
    at.button(key="goal_add").click().run()
    assert not at.exception and "first turn is on" in texts(at), "today is taken: tomorrow"
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


def test_the_goal_page_saves_onto_what_another_tab_changed(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path, history=False)
    loads(at, "views/goal.py")
    s, _ = stored(tmp_path)
    other = dict(s, subjects=["philosophy", "cosmos", "fashion"], units_per_day=5)     # another tab, since
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"user_settings": [other]}))
    at.text_area(key="goal_text").input("Read a company's financial statements").run()
    s, _ = stored(tmp_path)
    assert s["subjects"] == ["philosophy", "cosmos", "fashion"] and s["units_per_day"] == 5
    assert s["onboarding"]["goal"]["text"] == "Read a company's financial statements"


def test_a_goal_that_couldnt_be_read_is_never_replaced_by_another_lesson(monkeypatch, tmp_path):
    from coach import storage
    goal = a_path()
    monkeypatch.setattr(storage.FileStore, "paths_error", "Your goals: the database is busy. Refresh in a moment.")
    calls = ai(monkeypatch)
    at = app(monkeypatch, tmp_path, subjects=(goal["id"],), history=False)       # (no paths in her records now)
    loads(at, "views/daily.py")
    assert any("the database is busy" in w.value for w in at.warning), "she is told"
    assert not any("Start this lesson" in str(b.proto) for b in at.button), "and no other lesson takes its place"
    loads(at, "views/goal.py")
    assert "the database is busy" in texts(at) and not has(at, "goal_design") and not calls


def test_setup_says_so_while_goals_cant_be_saved(monkeypatch, tmp_path):
    # covers: W-goalmaker-k_key_skip-2
    from coach import storage
    monkeypatch.setattr(storage.FileStore, "paths_error", storage.PATHS_TABLE_MISSING)
    calls = ai(monkeypatch)
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    assert "goals.sql" in texts(at) and not has(at, "obg_design") and not calls, "said plainly, no AI call"
