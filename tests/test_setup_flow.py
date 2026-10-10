"""The setup's order without a browser: who she is (or that she knows
what she wants), what she wants to learn (or finding it among broad
directions), all of it or some parts, what it's for, and the confirmation."""
import json

from test_pages_smoke import app


def texts(at):
    import html
    return html.unescape(" ".join(str(h.proto) for h in at.get("html")) + " ".join(m.value for m in at.markdown))


def draft(tmp_path):
    return json.loads((tmp_path / "settings.json").read_text())["user_settings"][0]["onboarding"]


def test_who_she_is_is_asked_unless_she_knows_what_she_wants(monkeypatch, tmp_path):
    # covers: W-setup-ob_identity_own, W-setup-ob_knows
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    assert "Who are you?" in texts(at) and at.button(key="ob_next").disabled, "who she is, or that she knows"
    at.checkbox(key="ob_knows").check().run()
    assert not at.button(key="ob_next").disabled
    at.checkbox(key="ob_knows").uncheck().run()
    at.text_input(key="ob_identity_own").input("Nurse").run()
    assert draft(tmp_path)["identity"] == "Nurse" and not at.button(key="ob_next").disabled
    at.button(key="ob_next").click().run()
    assert "What do you want to learn?" in texts(at)
    at.button(key="ob_back").click().run()
    assert at.text_input(key="ob_identity_own").value == "Nurse", "her own words, kept"
    at.button(key="pick_ident_Student").click().run()
    assert draft(tmp_path)["identity"] == "Student"


def test_skipping_who_she_is_and_what_its_for(monkeypatch, tmp_path):
    # covers: W-goalmaker-k_key_all, W-goalmaker-k_key_own, W-setup-ob_to_review, W-setup-ob_change
    from test_goal_pages import ai, all_of_it, stored
    from test_goals import design_reply
    ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    at.checkbox(key="ob_knows").check().run()
    at.button(key="ob_next").click().run()
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    all_of_it(at)
    at.button(key="ob_next").click().run()                          # → what it's for
    assert at.button(key="obp_pp_1").label == "Out of curiosity" and at.button(key="ob_next").disabled, "general goals; one is needed"
    at.text_input(key="obp_own").input("To invest for my kids").run()
    assert draft(tmp_path)["purpose"] == "To invest for my kids"
    at.checkbox(key="obp_all").check().run()                        # no particular goal: all of it
    assert draft(tmp_path)["purpose"] == "To learn all of it"
    at.button(key="ob_next").click().run()
    t = texts(at)
    assert "Is this right?" in t and "Learning all of Reading financial statements: 16 lessons." in t
    assert "You're" not in t, "nothing said about who she is"
    at.button(key="ob_change_purpose").click().run()                # a change, and straight back
    at.button(key="obp_pp_0").click().run()
    at.button(key="ob_to_review").click().run()
    assert "Is this right?" in texts(at) and "Useful at work or study" in texts(at)
    at.button(key="ob_next").click().run()                          # Start learning
    s, log = stored(tmp_path)
    assert s["onboarded_at"] and log["paths"][0]["why"] == "Useful at work or study"


def test_a_different_goal_and_writing_it_herself(monkeypatch, tmp_path):
    # covers: W-setup-ob_back-2, W-setup-ob_write
    from test_goal_pages import ai, has, to_goal
    from test_goals import design_reply
    calls = ai(monkeypatch, design_reply())
    at = app(monkeypatch, tmp_path, subjects=(), history=False, onboarded=False)
    to_goal(at, "Retired")
    assert at.segmented_control(key="obg_idea_group").value == "Curiosity", "ideas that fit who she is"
    at.button(key="obg_skip").click().run()
    at.button(key="pick_dir0_Arts").click().run()
    at.button(key="ob_write").click().run()                         # she'd rather write it
    assert has(at, "obg_design") and draft(tmp_path)["exploring"] is False and not calls
    at.button(key="obg_skip").click().run()
    at.button(key="ob_back").click().run()                          # the top of the directions: back to her words
    assert has(at, "obg_design")
    at.text_area(key="obg_text").input("Read a company's financial statements").run()
    at.button(key="obg_design").click().run()
    at.segmented_control(key="obs_scope").set_value("some").run()
    at.button(key="ob_back").click().run()
    at.button(key="ob_again").click().run()                         # something else: outline and answers go
    d = draft(tmp_path)
    assert d["path"] is None and d["scope"] is None and has(at, "obg_design") and len(calls) == 1


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
