"""What the second round of testing found, held: a setup can't leave the
account half set up; a change from the final review goes to its step and
back; a goal the session hasn't loaded is loaded, never replaced by a subject
she didn't choose; a new goal starts fresh and can't be added twice; what she
set aside comes back one item at a time; lessons show no source the model
named, only links to check it herself; diagrams read as words; the quiz
checker reads the lesson."""
import json
from datetime import datetime, timezone

from coach import catalog, lesson_view, paths, quiz, settings
from test_goal_pages import ai, has, texts, to_goal
from test_goals import a_path, design_reply
from test_pages_smoke import app, loads


def stored(tmp_path):
    return json.loads((tmp_path / "settings.json").read_text())["user_settings"][0]


# ---------------------------------------------------------------- 1. setup state
def test_every_change_on_the_final_review_goes_to_its_step_and_back(monkeypatch, tmp_path):
    # covers: W-setup-ob_to_review
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    for _ in range(5):                                       # goal → reading → selection → customize → path → review
        at.button(key="ob_next").click().run()
    assert "Final review" in texts(at)
    for name, lands in (("goal", "A goal of your own"), ("subjects", "What would you like to learn?"),
                        ("reading", "Reading plan"), ("customize", "Customize your learning"), ("path", "Your path")):
        at.button(key=f"ob_change_{name}").click().run()
        assert lands in texts(at) and not at.exception, name
        assert stored(tmp_path)["onboarded_at"] is None, "a change never finishes the setup"
        at.button(key="ob_to_review").click().run()          # straight back, nothing lost
        t = texts(at)
        assert "Final review" in t and "Reading financial statements" in t, name
    assert "Jewelry" not in texts(at)


def test_a_click_left_on_a_finished_setup_saves_no_draft(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.button(key="ob_next").click().run()                   # Get started
    at.button(key="pick_subj_philosophy").click().run()
    # meanwhile the setup is finished (another tab, or Start learning just before)
    row = stored(tmp_path)
    row.update(subjects=["philosophy"], onboarded_at=datetime.now(timezone.utc).isoformat(), onboarding=None,
               subject_levels={"philosophy": "Beginner"})
    (tmp_path / "settings.json").write_text(json.dumps({"user_settings": [row]}))
    at.button(key="ob_next").click().run()                   # the click left on the old page
    assert stored(tmp_path)["onboarding"] is None, "no draft written onto a finished setup"
    assert not at.exception and "Philosophy" in texts(at)


def test_a_goal_the_session_hasnt_loaded_is_loaded_not_replaced(monkeypatch, tmp_path):
    goal = a_path()
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), history=False)
    # the goal is made elsewhere: settings name it, this session's records don't have it yet
    (tmp_path / "log.json").write_text(json.dumps({"version": 1, "entries": [], "books": [], "paths": [goal]}))
    row = stored(tmp_path)
    row["subjects"] = [goal["id"]]
    (tmp_path / "settings.json").write_text(json.dumps({"user_settings": [row]}))
    at.run()
    assert not at.exception and goal["title"] in texts(at), "her goal, loaded"
    for other in ("Jewelry", "Fashion", "Astronomy"):
        assert other not in texts(at), f"{other}: a subject she never chose"


# ---------------------------------------------------------------- 2. a new goal
def test_add_a_goal_starts_fresh_and_a_goal_is_never_added_twice(monkeypatch, tmp_path):
    goal = a_path()
    at = app(monkeypatch, tmp_path, subjects=(goal["id"], "philosophy"), paths=[goal], history=False)
    row = stored(tmp_path)
    row["onboarding"] = dict(settings.new_draft(), path=goal, path_original=goal)     # a draft left behind
    (tmp_path / "settings.json").write_text(json.dumps({"user_settings": [row]}))
    loads(at, "views/settings.py")
    at.button(key="set_goal_add").click().run()
    assert not at.exception and not has(at, "goal_add") and has(at, "goal_design"), "an empty form"
    loads(at, "views/goal.py")                       # (the test app keeps the page it was last sent to)
    assert stored(tmp_path)["onboarding"]["path"] is None
    # the same goal designed again (another id, the same title): not added twice
    ai(monkeypatch, design_reply())
    at.text_area(key="goal_text").input("Read a company's financial statements").run()
    at.button(key="goal_design").click().run()
    at.button(key="goal_add").click().run()
    assert "already one of your goals" in texts(at)
    log = json.loads((tmp_path / "log.json").read_text())
    assert len(log["paths"]) == 1


# ---------------------------------------------------------------- 3. set aside, brought back
def test_what_she_set_aside_comes_back_one_item_at_a_time():
    orig = a_path()
    p = paths.remove_unit(orig, 1)                                   # Part 1 skipped
    p = paths.remove_lesson(p, 0, 2)                                 # Idea 0.2 taken out
    p = paths.move_unit(p, 0, 1)                                     # Part 2 before Part 0
    aside = paths.set_aside(p, orig)
    assert aside == [{"kind": "lesson", "unit": "Part 0", "title": "Idea 0.2"},
                     {"kind": "unit", "unit": "Part 1", "lessons": 4}]
    back = paths.bring_back(p, orig, aside[1])
    assert [u["name"] for u in back["units"]] == ["Part 2", "Part 0", "Part 1", "Part 3"], "after the part before it"
    assert "Idea 0.2" not in back["units"][1]["lessons"], "the other change stays"
    back = paths.bring_back(back, orig, aside[0])
    assert back["units"][1]["lessons"] == ["Idea 0.0", "Idea 0.1", "Idea 0.2", "Idea 0.3"], "in its designed place"
    assert paths.set_aside(back, orig) == []
    assert "builds" not in (paths.order_note(orig, orig) or "") and paths.order_note(orig, orig) is None
    assert "“Part 2” now comes before “Part 0”" in paths.order_note(back, orig)


def test_bringing_back_from_the_page(monkeypatch, tmp_path):
    # covers: W-goalmaker-k_key_f_back_i
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    for _ in range(4):
        at.button(key="ob_next").click().run()
    at.button(key="obp_skip_0").click().run()
    at.button(key="obp_lighter").click().run()
    assert "Set aside" in texts(at) and has(at, "obp_back_0")
    at.button(key="obp_back_0").click().run()                        # one item back, the rest still aside
    d = stored(tmp_path)["onboarding"]
    assert any(u["name"] == "Part 0" for u in d["path"]["units"]) and len(paths.set_aside(
        paths.parse_path(d["path"]), paths.parse_path(d["path_original"]))) > 0


# ---------------------------------------------------------------- 4/5. sources and diagrams
def test_no_source_the_model_named_and_links_to_check_it_instead():
    assert lesson_view.unsourced("Bonds pay interest (Source: Investopedia). More.") == "Bonds pay interest. More."
    assert lesson_view.unsourced("A 規則（出處：WHO）。") == "A 規則。"


def test_diagram_labels_read_as_words_and_a_lone_box_is_left_out():
    dot = lesson_view.styled("digraph { Return -> CapitalGains; Return -> Income }", dark=False)
    assert '[label="Capital gains"]' in dot
    assert lesson_view.styled("digraph { Alone }", dark=False) is None
    assert lesson_view.humane("OpportunityCost") == "Opportunity cost"


def test_the_quiz_checker_reads_the_lesson():
    qs = [{"type": "short", "question": "Why?", "answer": "Because."}]
    _, msgs = quiz.check_request(qs, "LESSON TEXT")
    assert "LESSON TEXT" in msgs[0]["content"]
    assert "lesson doesn't teach" in quiz.CHECKER


def test_no_plan_or_price_anywhere_while_plans_arent_shown(monkeypatch, tmp_path):
    from coach import plans
    assert plans.SHOWN is False
    at = app(monkeypatch, tmp_path, subjects=("philosophy",))
    for page in ("views/account.py", "views/settings.py"):
        loads(at, page)
        t = texts(at)
        assert "Subscription" not in t and "Price" not in t and "Plus" not in t, page


def test_a_goal_in_chinese_japanese_or_korean_is_not_too_short():
    for goal in ("我想學吉他", "學習投資基礎", "日本語を勉強したい", "한국어 배우기"):
        assert paths.precheck(goal) is None, goal
    assert paths.precheck("學") is not None, "one character is still too little to plan"
    assert "write everything you reply in English" in paths.DESIGN_SYSTEM


def test_a_page_that_breaks_shows_a_calm_message_not_an_error(monkeypatch, tmp_path):
    # covers: W-ui-calm_retry, W-ui-calm_home, S-gnosis_raise_errors
    monkeypatch.setenv("GNOSIS_RAISE_ERRORS", "0")
    from coach import course
    at = app(monkeypatch, tmp_path, subjects=("philosophy",))

    def boom(*a, **k):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(course, "build", boom)
    loads(at, "views/subjects.py")
    t = texts(at)
    assert "Something went wrong on this page" in t and "secret internal detail" not in t
    assert has(at, "calm_retry") and has(at, "calm_home")


def test_a_paused_goal_can_be_removed_and_its_lessons_stay(monkeypatch, tmp_path):
    # covers: W-settings-setgoal_remove, W-settings-setgoal_remove_go, W-settings-setgoal_remove_cancel
    goal = a_path(status="archived")
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), paths=[goal], history=False)
    loads(at, "views/settings.py")
    at.button(key=f"setgoal_remove_{goal['id']}").click().run()
    assert "stay in your Learning Record" in texts(at)
    at.button(key=f"setgoal_remove_cancel_{goal['id']}").click().run()
    assert not has(at, f"setgoal_remove_go_{goal['id']}"), "cancelled: nothing changed"
    at.button(key=f"setgoal_remove_{goal['id']}").click().run()
    at.button(key=f"setgoal_remove_go_{goal['id']}").click().run()
    log = json.loads((tmp_path / "log.json").read_text())
    assert log["paths"][0]["status"] == "removed", "kept, marked removed: nothing deleted"
    assert not has(at, f"setgoal_resume_{goal['id']}") and "was removed" in texts(at)
    catalog.use([paths.parse_path(log["paths"][0])])
    assert catalog.goals(active_only=False) == [] and catalog.name(goal["id"]) == goal["title"], \
        "off her list, still named in her record"
    catalog.use([])


def test_the_menu_holds_only_what_works_unless_a_preview_is_asked_for(monkeypatch):
    # covers: S-gnosis_show_coming
    from coach import topnav
    shown = [label for _, items in topnav._sections() for label, t in items]
    assert all(t for _, items in topnav._sections() for _, t in items), "no entry without a page"
    assert "Research" not in shown and "Certificates" not in shown and "Knowledge Exploration" not in shown
    monkeypatch.setattr(topnav, "SHOW_COMING", True)
    assert "Research Portfolio" in [label for _, items in topnav._sections() for label, _ in items]


def test_an_empty_record_says_how_to_start(monkeypatch, tmp_path):
    # covers: W-records-prog_start
    at = app(monkeypatch, tmp_path, subjects=("philosophy",), history=False)
    loads(at, "views/records.py")
    assert "Your record starts with your first lesson" in texts(at)
    at.button(key="prog_start").click().run()
    assert not at.exception and "Start this lesson" in " ".join(str(b.proto) for b in at.button)
