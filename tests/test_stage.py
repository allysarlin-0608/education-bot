import re

from coach import settings, stage, visuals


def test_every_subject_record_comes_from_one_place():
    for t in settings.SUBJECTS:
        s = visuals.subject(t)
        assert s["key"] == t and s["title"] and s["description"] == settings.DESCRIPTIONS[t]
        assert s["number"] == settings.SUBJECTS.index(t) + 1
    assert not visuals.known("nonsense") and not visuals.known(None)


def test_the_stage_is_drawn_with_its_focus_showing():
    html = stage.html("jewelry", "subj")
    assert 'data-focus="jewelry"' in html and 'data-group="subj"' in html
    # only the subject in focus is exposed; every layer's name, words and object are its own subject's
    assert re.findall(r'data-t="(\w+)" aria-hidden="false"', html) == ["jewelry"]
    for t in settings.SUBJECTS:
        layer = html.split(f'data-t="{t}"')[1].split('class="sg-layer"')[0]
        s = visuals.subject(t)
        assert f'data-object="{t}"' in layer and s["description"] in layer
        assert all(f'data-object="{o}"' not in layer for o in settings.SUBJECTS if o != t)


def test_focus_never_falls_back_to_a_subject_that_was_not_asked_for():
    assert stage.focus_of("cosmos", ["philosophy"]) == "cosmos"
    assert stage.focus_of(None, ["philosophy", "jewelry"]) == "jewelry"      # her last chosen
    assert stage.focus_of("nonsense", []) == settings.SUBJECTS[0]           # nothing yet: the first, drawn as focus
    assert [r[0] for r in stage.rows()] == list(settings.SUBJECTS)
