from coach import place


def test_marker_carries_the_lesson_and_jump():
    out = place.html("2026-09-25|jewelry|3", "current-quiz", "Lesson 3:")
    assert 'id="coach-place"' in out
    assert 'data-key="2026-09-25|jewelry|3"' in out
    assert 'data-jump="current-quiz"' in out and 'data-want="Lesson 3:"' in out
    assert "<script>" in out


def test_no_jump_by_default_and_text_is_escaped():
    out = place.html('a"b')
    assert 'data-jump=""' in out and 'data-key="a&quot;b"' in out
