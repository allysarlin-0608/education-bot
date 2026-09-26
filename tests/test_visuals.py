from coach import curriculum, settings, visuals

LAYOUTS = {"figure", "instrument", "painting", "pendant"}


def test_every_subject_has_a_complete_world():
    for t in settings.SUBJECTS:
        w = visuals.WORLD[t]
        assert w["kicker"] and w["shows"] and w["layout"] in LAYOUTS and w["title"] in ("serif", "tracked")
        assert w["object"].startswith(("subjects/", "svg:"))
        if w["object"].startswith("svg:"):
            assert w["object"][4:] in visuals.SVGS
        f = visuals.facts(t)
        assert f["lessons"] > 0 and f["units"] > 0 and f["first"]


def test_units_cover_the_syllabus_in_order():
    for t in settings.SUBJECTS:
        us = visuals.units(t)
        assert us[0][1] == 1 and us[-1][2] == curriculum.written(t)
        assert all(a[2] + 1 == b[1] for a, b in zip(us, us[1:]))


def test_the_necklace_is_drawn_in_each_themes_ink():
    html = visuals.object_html("jewelry", "w-object", 6)
    assert 'data-object="jewelry"' in html and "--ink-light" in html and "--ink-dark" in html and "<svg" not in html
    for theme, ink in visuals.INKS.items():
        f = visuals.STATIC / visuals.drawn_file("emerald", theme)
        # the pictures served are the drawing as it is now (python -m coach.visuals rewrites them)
        assert f.read_text(encoding="utf-8") == visuals.drawn_svg("emerald", theme) and ink in f.read_text()
    assert visuals.image_url("jewelry") is None and visuals.has_object("jewelry") and visuals.credit("jewelry") == ""


def test_a_missing_picture_is_never_linked(tmp_path, monkeypatch):
    monkeypatch.setattr(visuals, "STATIC", tmp_path)
    assert visuals.image_url("philosophy") is None
    assert 'data-n="01"' in visuals.object_html("philosophy", "sg-art", 1) and visuals.credit("philosophy") == ""
    (tmp_path / "subjects").mkdir()
    (tmp_path / "subjects" / "philosophy.jpg").write_bytes(b"x")
    assert visuals.image_url("philosophy") == "app/static/subjects/philosophy.jpg"
    assert "background-image" in visuals.object_html("philosophy", "sg-art", 1) and visuals.credit("philosophy")
