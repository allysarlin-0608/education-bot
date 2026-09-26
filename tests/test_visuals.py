from coach import settings, visuals


def test_every_subject_has_its_art_entry_and_facts_from_its_syllabus():
    for t in settings.SUBJECTS:
        kicker, shows, path = visuals.ART[t]
        assert kicker and shows and path.startswith("subjects/")
        f = visuals.facts(t)
        assert f["lessons"] > 0 and f["units"] > 0 and f["first"]


def test_a_missing_picture_is_never_linked(tmp_path, monkeypatch):
    monkeypatch.setattr(visuals, "STATIC", tmp_path)
    assert visuals.image_url("philosophy") is None
    (tmp_path / "subjects").mkdir()
    (tmp_path / "subjects" / "philosophy.jpg").write_bytes(b"x")
    assert visuals.image_url("philosophy") == "app/static/subjects/philosophy.jpg"
