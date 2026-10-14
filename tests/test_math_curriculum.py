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
    assert c["phases"] == 8 and c["units"] > 60 and c["sources"] == 7
    assert [p["id"] for p in mathcourse.phases()] == [f"L{k}" for k in range(8)]


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
    assert [u["id"] for u in mathcourse.prerequisites("L4-02")] == ["L4-01", "L4-03"]
    assert "L4-02" in [u["id"] for u in mathcourse.leads_to("L4-03")]
    assert mathcourse.prerequisites("L0-01") == [] and mathcourse.phase_of("L4-02") == "L4"
    assert all(s["url"].startswith("https://") for u in every.values() for s in mathcourse.sources_of(u))


def html(at) -> str:
    return " ".join(str(h.proto.body) for h in at.get("html"))


def test_the_page_shows_every_phase_and_unit(monkeypatch, tmp_path):
    # covers: W-math-mc_phase
    at = loads(app(monkeypatch, tmp_path), "views/math.py")
    labels = [e.label for e in at.expander]
    assert len(labels) == 8 and labels[0].startswith("L0 · 數字與基本運算 · 入門")
    body = html(at)
    for u in mathcourse.units().values():
        assert u["title"] in body and u["summary"] in body and u["learning_outcomes"][0] in body
    assert "You'll be able to" in body and "Practice" in body and "Learn first" in body
    assert 'href="https://openstax.org/k12/math" target="_blank" rel="noopener noreferrer"' in body
    assert mathcourse.load()["attribution_and_use"] in body
    pre = [b for b in at.button if b.key == "mc_go_L4-02_L4-03"]
    assert pre and pre[0].label.startswith("L4-03 ")


def test_a_prerequisite_opens_its_unit(monkeypatch, tmp_path):
    # covers: W-math-mc_go
    at = loads(app(monkeypatch, tmp_path), "views/math.py")
    next(b for b in at.button if b.key == "mc_go_L4-02_L4-03").click().run()
    assert not at.exception
    assert at.query_params["unit"] == ["L4-03"] and at.session_state["mc_phase_L4"] is True


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
