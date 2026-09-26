from coach import curriculum, settings, visuals

LAYOUTS = {"figure", "instrument", "painting", "pendant"}


def test_every_subject_has_a_complete_world():
    for t in settings.SUBJECTS:
        w = visuals.WORLD[t]
        assert w["kicker"] and w["shows"] and w["layout"] in LAYOUTS and w["title"] in ("serif", "tracked")
        assert w["object"].startswith("subjects/") and visuals.has_object(t)
        f = visuals.facts(t)
        assert f["lessons"] > 0 and f["units"] > 0 and f["first"]


def test_units_cover_the_syllabus_in_order():
    for t in settings.SUBJECTS:
        us = visuals.units(t)
        assert us[0][1] == 1 and us[-1][2] == curriculum.written(t)
        assert all(a[2] + 1 == b[1] for a, b in zip(us, us[1:]))


def test_free_standing_objects_are_marked_and_have_no_backdrop():
    from PIL import Image
    for t, w in visuals.WORLD.items():
        html = visuals.object_html(t, "w-object", 1)
        assert ("is-cut" in html) == bool(w.get("cut"))
        if w.get("cut"):
            # a cut object is a picture with its own transparency, clear at its corners
            im = Image.open(visuals.STATIC / w["object"])
            assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0
    assert visuals.WORLD["jewelry"]["cut"] and visuals.credit("jewelry")


def test_a_missing_picture_is_never_linked(tmp_path, monkeypatch):
    monkeypatch.setattr(visuals, "STATIC", tmp_path)
    assert visuals.image_url("philosophy") is None
    assert 'data-n="01"' in visuals.object_html("philosophy", "sg-art", 1) and visuals.credit("philosophy") == ""
    (tmp_path / "subjects").mkdir()
    (tmp_path / "subjects" / "philosophy.webp").write_bytes(b"x")
    assert visuals.image_url("philosophy") == "app/static/subjects/philosophy.webp"
    assert "background-image" in visuals.object_html("philosophy", "sg-art", 1) and visuals.credit("philosophy")
