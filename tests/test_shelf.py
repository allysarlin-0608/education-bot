from datetime import date

from coach import books, shelf


def book(status="reading", checks=(), plan=None, **kw):
    b = books.new_book(date(2026, 9, 1))
    b.update({"title": "Walden", "author": "Thoreau", "status": status,
              "chapters": [f"Ch {i}" for i in range(1, 14)],
              "plan": plan or [[i] for i in range(1, 14)] + [[]],
              "started_on": "2026-09-01"})
    b["checks"] = {str(d): {"passed_on": f"2026-09-{d:02d}", "summary": f"notes {d}"} for d in checks}
    b.update(kw)
    return b


def test_day_states_mark_done_current_and_ahead():
    s = shelf.day_states(book(checks=(1, 2, 3)))
    assert s[:3] == ["done"] * 3 and s[3] == "current" and set(s[4:]) == {"ahead"}


def test_a_rest_day_behind_her_counts_as_done():
    plan = [[1], [], [2]] + [[i] for i in range(3, 14)]
    assert shelf.day_states(book(checks=(1, 3), plan=plan))[:4] == ["done", "done", "done", "current"]


def test_line_has_fourteen_days_and_one_end():
    html = shelf.line_html(book(checks=(1, 2)))
    assert html.count('class="bk-seg') == 14 and html.count(" end") == 1
    assert "Day 3 of 14 · 2 of 13 reading days done" in html


def test_today_says_the_range_or_when_it_opens():
    b = book(checks=(1,))
    assert "Today · Day 2" in shelf.today_html(b, date(2026, 9, 5))
    assert "opens on September 2" in shelf.today_html(b, date(2026, 9, 1))


def test_shelf_holds_finished_and_stopped_books_newest_first():
    old = book("finished", checks=range(1, 14), id="a", finished_on="2026-08-20")
    new = book("switched", checks=(1, 2, 3, 4, 5), id="b", last_active_on="2026-09-10")
    now = book("reading", id="c")
    assert [b["id"] for b in shelf.on_shelf([old, now, new])] == ["b", "a"]


def test_status_lines():
    assert shelf.status(book("finished", finished_on="2026-09-30")) == "Finished · Sep 30"
    assert shelf.status(book("switched", checks=(1, 2, 3, 4, 5))) == "Stopped at day 5"


def test_empty_shelf_is_one_grey_line():
    assert shelf.shelf_html([book()]) == '<p class="bk-empty">Books you finish will appear here.</p>'


def test_an_opened_book_shows_every_day_her_words_and_the_wrap_up():
    b = book("finished", checks=range(1, 14), finished_on="2026-09-13", final_summary="**Great** read\n\n- one\n- two")
    html = shelf.shelf_html([b], open_id=b["id"])
    assert "<details class=\"bk-book\" open>" in html
    assert html.count("<li class=") == 14 and "notes 7" in html and "Passed · Sep 7" in html and "Rest" in html
    assert "<strong>Great</strong>" in html and "<li>one</li>" in html


def test_her_words_are_escaped():
    b = book("finished", checks=(1,), finished_on="2026-09-02")
    b["checks"]["1"]["summary"] = "<script>x</script>"
    assert "<script>" not in shelf.shelf_html([b])


def test_wrap_up_italics_and_rest_days_without_a_tick():
    assert "<em>simplicity</em>" in shelf._text("kept *simplicity* close")
    plan = [[1], [], [2]] + [[i] for i in range(3, 14)]
    assert 'class="bk-seg done rest"' in shelf.line_html(book(checks=(1, 3), plan=plan))


def test_a_stopped_book_shows_the_days_read_and_folds_the_rest():
    b = book("switched", checks=(1, 2, 3, 4, 5))
    html = shelf.shelf_html([b])
    assert html.count("<li class=") == 14 and html.count(" later") == 9
    assert "9 days not read" in html and 'class="bk-close">Close<' in html


def test_a_finished_book_folds_nothing():
    html = shelf.shelf_html([book("finished", checks=range(1, 14), finished_on="2026-09-13")])
    assert " later" not in html and "not read</span>" not in html
