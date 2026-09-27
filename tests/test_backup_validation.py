"""BUG-006: whatever a backup (or a stored row) holds, what comes out of
parse_log has the right shape, and nothing built on it breaks."""
from datetime import date

import pytest

from coach import books, core, curriculum, history

EVIL_VALUES = [None, 5, -1, 10**12, "text", "", [], ["a"], {}, {"x": 1}, True, 3.5]


def _evil_entries():
    out = []
    for k, v in enumerate(EVIL_VALUES):
        out.append({"date": f"2026-09-{k + 1:02d}", "topic": "philosophy", "session_number": v, "level": v,
                    "completed": v, "title": v, "followup_question": v, "reflection": v, "lesson": v,
                    "kickoff": v, "followups": v, "lessons": v})
    out.append({"date": "2026-09-20", "topic": "philosophy",
                "lessons": [{"n": 1, "title": {"t": 1}, "unit": 5, "quiz": "x", "followups": "y", "completed": "yes"},
                            {"n": "2"}, "junk"]})
    return out


def test_every_field_has_its_type():
    log = core.parse_log({"entries": _evil_entries()})
    for e in log["entries"]:
        assert isinstance(e["session_number"], int) and not isinstance(e["session_number"], bool)
        assert 0 < e["session_number"] < 100000
        assert isinstance(e["completed"], bool)
        for f in core.TEXT_FIELDS:
            assert isinstance(e[f], str), (f, e[f])
        assert isinstance(e["followups"], list) and isinstance(e["lessons"], list)
        for s in e["lessons"]:
            assert isinstance(s["title"], str) and isinstance(s["unit"], str) and isinstance(s["completed"], bool)


def test_derived_numbers_still_work():
    log = core.parse_log({"entries": _evil_entries()})
    curriculum.unit_progress(log, "philosophy")
    core.current_streak(log, date(2026, 9, 30))
    for d in range(1, 21):
        history.day_stats(log, date(2026, 9, d), date(2026, 9, 30))
    history.month_summary(log, 2026, 9, date(2026, 9, 30))


@pytest.mark.parametrize("bad", EVIL_VALUES)
def test_books_with_any_field_wrong_are_made_safe_or_dropped(bad):
    raw = {"id": "b1", "status": "reading", "title": bad, "author": bad, "chapter_count": bad, "total_pages": bad,
           "chapters": bad, "pending_toc": bad, "pending_numbers": bad, "plan": bad, "checks": bad,
           "started_on": bad, "last_active_on": bad, "finished_on": bad, "final_summary": bad}
    book = books.normalize_book(raw)
    if book is None:
        return
    assert isinstance(book["title"], str) and isinstance(book["chapters"], list)
    assert all(isinstance(c, str) for c in book["chapters"])
    assert book["status"] in books.STATUSES
    if book["status"] in ("reading", "finished"):
        assert len(book["plan"]) == books.DAYS
        n = len(book["chapters"])
        assert all(isinstance(c, int) and 1 <= c <= n for day in book["plan"] for c in day)
        for d in range(1, books.DAYS + 1):
            books.day_description(book, d)
        books.next_day(book)
    assert isinstance(book["checks"], dict)


def test_a_book_without_an_id_is_dropped():
    assert books.normalize_book({"title": "x"}) is None
    assert books.normalize_book({"id": 5}) is None
    assert books.normalize_book("nope") is None
