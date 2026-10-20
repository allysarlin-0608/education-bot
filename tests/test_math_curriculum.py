"""The math curriculum (data/math_curriculum_zh-Hant.json, coach/mathcourse.py,
views/math.py): the file holds together, the page shows every phase with its
units' summaries, outcomes, practice, prerequisites and sources, a
prerequisite opens its unit, and Courses and the Menu lead there."""
import copy

from coach import mathcourse, topnav
from test_pages_smoke import app, loads


def test_the_file_holds_together():
    assert mathcourse.check() == []
    c = mathcourse.counts()
    assert c["phases"] == 9 and c["units"] == 160 and c["sources"] == 811
    assert [p["id"] for p in mathcourse.phases()] == [f"L{k}" for k in range(9)]


def test_what_check_catches():
    data = copy.deepcopy(mathcourse.load())
    u = data["phases"][1]["units"][0]
    u["prerequisites"] = ["L9-99"]
    u["sources"] = ["nowhere"]
    data["phases"][0]["units"].append(dict(data["phases"][0]["units"][1]))
    problems = mathcourse.check(data)
    assert any("L9-99 isn't a unit" in x for x in problems)
    assert any("source nowhere isn't listed" in x for x in problems)
    assert any("id used twice" in x for x in problems)


def test_a_loop_of_prerequisites_is_caught():
    data = copy.deepcopy(mathcourse.load())
    a, b = data["phases"][0]["units"][:2]
    a["prerequisites"], b["prerequisites"] = [b["id"]], [a["id"]]
    assert any("needs itself" in x for x in mathcourse.check(data))


def test_prerequisites_leads_and_sources():
    every = mathcourse.units()
    assert [u["id"] for u in mathcourse.prerequisites("L1-03")] == ["L0-08", "L1-02"]
    assert "L1-03" in [u["id"] for u in mathcourse.leads_to("L0-08")]
    assert mathcourse.prerequisites("L0-01") == [] and mathcourse.phase_of("L1-03") == "L1"
    assert all(s["url"].startswith("https://") for u in every.values() for s in mathcourse.sources_of(u))


def html(at) -> str:
    return " ".join(str(h.proto.body) for h in at.get("html"))


def test_the_page_shows_every_phase_and_unit(monkeypatch, tmp_path):
    # covers: W-math-mc_phase
    at = loads(app(monkeypatch, tmp_path), "views/math.py")
    labels = [e.label for e in at.expander]
    assert len(labels) == 9 and labels[0].startswith("L0 · 數感與基本運算 · 入門")
    body = html(at)
    for u in mathcourse.units().values():
        assert u["title"] in body and u["summary"] in body and u["learning_outcomes"][0] in body
    assert "You'll be able to" in body and "Practice" in body and "Learn first" in body
    assert 'href="https://www.thecorestandards.org/Math/Content/K/introduction/" target="_blank" rel="noopener noreferrer"' in body
    assert mathcourse.load()["attribution_and_use"] in body
    pre = [b for b in at.button if b.key == "mc_go_L1-03_L0-08"]
    assert pre and pre[0].label.startswith("L0-08 ")


def test_a_prerequisite_opens_its_unit(monkeypatch, tmp_path):
    # covers: W-math-mc_go
    at = loads(app(monkeypatch, tmp_path), "views/math.py")
    next(b for b in at.button if b.key == "mc_go_L1-03_L0-08").click().run()
    assert not at.exception
    assert at.query_params["unit"] == ["L0-08"] and at.session_state["mc_phase_L0"] is True


def test_an_address_naming_a_unit_opens_its_phase(monkeypatch, tmp_path):
    at = loads(app(monkeypatch, tmp_path), "views/math.py", unit="L2-03")
    assert at.session_state["mc_phase_L2"] is True
    at = loads(app(monkeypatch, tmp_path), "views/math.py", unit="nonsense")
    assert not at.exception


def test_courses_and_the_menu_lead_there(monkeypatch, tmp_path):
    # covers: W-subjects-sc_math
    at = loads(app(monkeypatch, tmp_path), "views/subjects.py")
    assert "Math, from zero to research" in html(at)
    assert any(b.key == "sc_math" for b in at.button)
    assert ("Math Curriculum", "Math Curriculum") in dict(topnav.SECTIONS)["Learn"]


# ---------------------------------------------------------------- math as a subject: its syllabus
def test_the_syllabus_is_the_curriculum_one_lesson_per_outcome():
    """coach/curriculum/math.txt: a unit per curriculum unit ("<id> <title>"),
    a lesson per learning outcome, every unit after the ones it needs."""
    from coach import curriculum, visuals
    every = mathcourse.units()
    units = [name.split(" ")[0] for name, _, _ in visuals.units("math")]
    assert sorted(units) == sorted(every), "every unit, once"
    for name, first, last in visuals.units("math"):
        uid = name.split(" ")[0]
        assert last - first + 1 == len(every[uid]["learning_outcomes"]), uid
    for k, uid in enumerate(units):
        assert all(units.index(p) < k for p in every[uid]["prerequisites"]), f"{uid} comes before what it needs"
    assert curriculum.written("math") == sum(len(u["learning_outcomes"]) for u in every.values())


def test_each_lesson_is_taught_with_its_unit_and_at_its_phase_level():
    from coach import core, curriculum
    first, last = curriculum.lesson("math", 1), curriculum.lesson("math", curriculum.written("math"))
    assert first["unit"].startswith("L0-01 ") and last["unit"].startswith("L8-10 ")
    assert curriculum.level_for(1, "math") == "Beginner" and curriculum.level_for(curriculum.written("math"), "math") == "Advanced"
    lines = "\n".join(core._syllabus_lines("math", curriculum.new_slot("math", 7)))
    assert "L0-03「加法」" in lines and mathcourse.units()["L0-03"]["summary"] in lines
    assert "建議練習方向" in lines
    assert "數學" in core.load_system_prompt("math", public=True)


def test_math_is_a_subject_with_its_own_placement_and_picture():
    from coach import placement, settings, visuals
    assert "math" in settings.SUBJECTS and settings.DESCRIPTIONS["math"]
    assert len(placement.QUESTIONS["math"]) == placement.COUNT
    assert visuals.has_object("math") and visuals.credit("math")


def test_the_course_map_and_the_curriculum_lead_to_each_other(monkeypatch, tmp_path):
    # covers: W-course-cm_math, W-math-mc_map
    at = loads(app(monkeypatch, tmp_path, subjects=("math",)), "views/course.py", subject="math")
    assert any(b.key == "cm_math" for b in at.button)
    at = loads(app(monkeypatch, tmp_path, subjects=("math",)), "views/math.py")
    assert any(b.key == "mc_map" for b in at.button) and "You're learning this" in html(at)


def test_the_curriculum_offers_to_add_mathematics(monkeypatch, tmp_path):
    # covers: W-math-mc_add, D-math-save_settings
    at = loads(app(monkeypatch, tmp_path, subjects=("philosophy",)), "views/math.py")
    assert not any(b.key == "mc_map" for b in at.button)
    next(b for b in at.button if b.key == "mc_add").click().run()
    assert not at.exception and "Added." in html(at)
    assert at.session_state["coach_settings"]["subjects"] == ["philosophy", "math"]
    assert any(b.key == "mc_map" for b in at.button), "now hers: its course map"


def test_with_three_subjects_it_says_where_to_make_room(monkeypatch, tmp_path):
    at = loads(app(monkeypatch, tmp_path, subjects=("philosophy", "cosmos", "fashion")), "views/math.py")
    next(b for b in at.button if b.key == "mc_add").click().run()
    assert "remove one in Goals &amp; Settings" in html(at)
    assert "math" not in at.session_state["coach_settings"]["subjects"]
