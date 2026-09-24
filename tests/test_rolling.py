"""Rolling numbers: which digits move, which way, and what stays still."""
import re

from coach import rolling


def windows(html):
    """(from, to) strip positions of each rolling digit."""
    return [(int(a), int(b)) for a, b in re.findall(r'--a:(\d+);--b:(\d+)', html)]


def test_only_the_changing_digit_rolls():
    html = rolling.html("129", "128")
    assert windows(html) == [(9, 10)]                     # 8 → 9; "1" and "2" stay still
    assert html.count('class="rd-still"') == 2
    assert windows(rolling.html("143", "128")) == [(3, 5), (9, 4 + 10)]   # 2→4, 8→3 rolls on through


def test_counting_up_rolls_forward_and_down_rolls_back():
    assert windows(rolling.html("40", "39")) == [(4, 5), (10, 1 + 10)]    # 3→4, 9→0 carries forward
    assert windows(rolling.html("39", "40")) == [(5, 4), (1 + 10, 10)]    # and back again


def test_the_decimal_point_and_words_stay_put():
    html = rolling.html("43.2", "42.5")
    assert '<span class="rd-sep">.</span>' in html
    assert windows(html) == [(3, 4), (6, 3 + 10)]
    html = rolling.html("3 / 5 lessons today", "2 / 5 lessons today")
    assert " / 5 lessons today" in html and windows(html) == [(3, 4)]


def test_a_new_digit_appears_from_blank():
    assert windows(rolling.html("10", "9")) == [(0, 2), (10, 1 + 10)]    # blank → 1, 9 → 0


def test_nothing_rolls_without_a_change_or_a_matching_shape():
    assert rolling.html("40", "40") == "40"
    assert rolling.html("40", None) == "40"
    assert rolling.html("3 of 5", "No lessons left") == "3 of 5"
    assert rolling.html("<b>1</b>", None) == "&lt;b&gt;1&lt;/b&gt;"


def test_remember_hands_back_what_was_shown_last():
    store = {}
    assert rolling.remember(store, "k", pct=40) == {}
    assert rolling.remember(store, "k", pct=60) == {"pct": 40}


def test_on_arrival_numbers_count_up_from_zero(monkeypatch):
    from coach import progress_bar
    state = {"lq_entering": True}
    monkeypatch.setattr(progress_bar.st, "session_state", state)
    assert rolling.zeroed("3 / 5 lessons today") == "0 / 0 lessons today"
    old = progress_bar.seen("card", pct=40, left="2 / 5 lessons today")
    assert old == {"pct": "0", "left": "0 / 0 lessons today"}                  # arriving: count up from 0
    assert windows(rolling.html("40", old["pct"])) == [(0, 5)]                 # blank → 4, the 0 stays still
    state["lq_entering"] = False
    assert progress_bar.seen("card", pct=40, left="2 / 5 lessons today") == {"pct": 40, "left": "2 / 5 lessons today"}
