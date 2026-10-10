"""The setup's order without a browser: a plan first; the reading plan step
only on a plan that includes it (and switched off when she moves to one
that doesn't); the selection, the price (nothing charged), and the review."""
import json

from test_pages_smoke import app


def texts(at):
    import html
    return html.unescape(" ".join(str(h.proto) for h in at.get("html")) + " ".join(m.value for m in at.markdown))


def draft(tmp_path):
    return json.loads((tmp_path / "settings.json").read_text())["user_settings"][0]["onboarding"]


def test_the_plan_decides_the_reading_step_and_nothing_is_charged(monkeypatch, tmp_path):
    # covers: S-plans_shown
    from coach import plans
    monkeypatch.setattr(plans, "SHOWN", True)              # (plans shown: coach/plans.SHOWN)
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.button(key="ob_next").click().run()                         # Get started
    assert "Choose a plan" in texts(at) and at.button(key="ob_next").disabled, "a plan is chosen first"
    at.button(key="pick_plan_plus").click().run()
    at.button(key="ob_next").click().run()
    at.button(key="pick_subj_philosophy").click().run()
    at.button(key="ob_next").click().run()
    assert "Included in Plus" in texts(at), "Plus: the reading plan is offered"
    at.toggle(key="ob_reading").set_value(True).run()
    assert draft(tmp_path)["reading_enabled"] is True
    at.button(key="ob_back").click().run()
    at.button(key="ob_back").click().run()
    assert "Choose a plan" in texts(at)
    at.button(key="pick_plan_free").click().run()
    assert draft(tmp_path)["reading_enabled"] is False, "a plan without it: no reading plan"
    at.button(key="ob_next").click().run()                         # → subjects (Philosophy kept)
    assert "1 of 3 chosen" in texts(at)
    at.button(key="ob_next").click().run()                         # → straight to the selection
    t = texts(at)
    assert "Your selection" in t and "Not on your plan" in t and "Reading plan (a book" not in t
    at.button(key="ob_next").click().run()
    t = texts(at)
    assert "Price summary" in t and "USD 0.00" in t and "Extra costs" in t and not at.exception
    for _ in range(3):                                              # → customize → path → review
        at.button(key="ob_next").click().run()
    assert "Final review" in texts(at) and at.button(key="ob_next").label == "Start learning"
    assert draft(tmp_path)["plan"] == "free"


def test_a_goal_can_be_left_and_removed(monkeypatch, tmp_path):
    # covers: W-setup-ob_back-2, W-setup-ob_no_goal
    from test_goal_pages import ai, has, to_goal
    from test_goals import design_reply
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at)
    at.button(key="ob_back").click().run()                         # the goal step's Back
    assert has(at, "pick_subj_philosophy") and not at.exception
    at.button(key="ob_next").click().run()                         # (asked for a goal: on to it)
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    assert draft(tmp_path)["path"]
    at.button(key="ob_no_goal").click().run()
    d = draft(tmp_path)
    assert d["path"] is None and d["want_goal"] is False
    assert has(at, "ob_to_goal") and "Choose at least one subject" in texts(at), "back to the subjects"


def test_courses_and_path_pages_lead_to_each_course(monkeypatch, tmp_path):
    # covers: W-subjects-sc_map, W-subjects-sc_map-2, W-subjects-sc_enter, W-subjects-sc_add, W-path-lp_map
    from test_pages_smoke import loads
    at = app(monkeypatch, tmp_path, subjects=("philosophy", "cosmos"))
    loads(at, "views/subjects.py")
    t = texts(at)
    assert "Yours" in t and "More subjects" in t and "lessons passed" in t
    at.button(key="sc_map_mine_philosophy").click().run()
    assert not at.exception and "course-page" in texts(at)
    loads(at, "views/subjects.py")
    at.button(key="sc_enter_mine_cosmos").click().run()
    assert not at.exception and "Astronomy" in texts(at)
    loads(at, "views/subjects.py")
    at.button(key="sc_add_more_investing").click().run()
    assert not at.exception and "Learning Plan" in texts(at)
    loads(at, "views/subjects.py")
    assert not any(b.key == "sc_enter_more_investing" for b in at.button), "no way into a subject that isn't hers"
    at.button(key="sc_map_more_investing").click().run()            # what it covers
    assert not at.exception and "course-page" in texts(at)
    loads(at, "views/path.py")
    t = texts(at)
    assert "Your next days" in t and "Today" in t and "Tomorrow" in t and "Next: lesson" in t
    at.button(key="lp_map_cosmos").click().run()
    assert not at.exception and "course-page" in texts(at)
