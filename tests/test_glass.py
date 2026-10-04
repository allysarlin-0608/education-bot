from coach import glass


def test_the_page_script_runs_once_and_adds_no_effects():
    js = glass.script()
    assert "gnosisPage" in js                         # once per page, whatever page comes first
    assert "dataset.scheme" in js                     # light or dark marked for the stylesheet
    assert "data-picking" in js                       # the calendar answers a tap at once
    for effect in ("filter", "refract", "feDisplacementMap", "atob("):
        assert effect not in js, effect               # solid and flat: no glass left (Sharp Minimalism)
