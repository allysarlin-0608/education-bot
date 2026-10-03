from datetime import date

from coach import history


def entry(day, topic="philosophy", done=5, total=5, legacy=False):
    e = {"date": day, "topic": topic, "completed": done == total}
    if not legacy:
        e["lessons"] = [{"n": k, "title": "t", "completed": k < done} for k in range(total)]
    return e


LOG = {"entries": [entry("2026-09-01"), entry("2026-09-02", "business", 2),
                   entry("2026-08-30", legacy=True)], "books": []}
TODAY = date(2026, 9, 25)


def test_day_stats():
    assert history.day_stats(LOG, date(2026, 9, 1), TODAY) == {
        "date": date(2026, 9, 1), "status": "done", "done": 5, "total": 5, "topics": ["philosophy"]}
    partial = history.day_stats(LOG, date(2026, 9, 2), TODAY)
    assert (partial["status"], partial["done"], partial["total"]) == ("partial", 2, 5)
    assert history.day_stats(LOG, date(2026, 9, 3), TODAY)["status"] == "none"
    assert history.day_stats(LOG, date(2026, 9, 30), TODAY)["status"] == "future"
    old = history.day_stats(LOG, date(2026, 8, 30), TODAY)     # before the syllabus: one session
    assert (old["done"], old["total"], old["status"]) == (1, 1, "done")


def test_month_grid_is_full_weeks_from_monday():
    grid = history.month_grid(LOG, 2026, 9, TODAY)
    assert all(len(w) == 7 for w in grid)
    assert grid[0][0]["date"] == date(2026, 8, 31) and not grid[0][0]["in_month"]   # a Monday
    assert grid[0][1]["date"] == date(2026, 9, 1) and grid[0][1]["status"] == "done"


def test_month_summary_and_range():
    assert history.month_summary(LOG, 2026, 9, TODAY) == {"studied": 2, "completed": 1, "lessons": 7}
    assert history.first_month(LOG, TODAY) == (2026, 8)
    assert history.first_month({"entries": []}, TODAY) == (2026, 9)
    assert history.shift(2026, 1, -1) == (2025, 12) and history.shift(2026, 12, 1) == (2027, 1)


def test_amount_steps():
    assert history.amount({"done": 0, "total": 5}) == 0
    assert history.amount({"done": 1, "total": 5}) == 1
    assert history.amount({"done": 5, "total": 5}) == 5
    assert history.amount({"done": 0, "total": 0}) == 0


def test_streak_days_completed_studied_calendar_agree_with_a_lesson_passed_a_day_later():
    """Issue 1: one rule for the whole Progress page. Oct 1: lesson 1 written,
    not passed. Oct 2: it's passed there (D2 link) plus lesson 2 not passed.
    Oct 3: every lesson of the day passed."""
    from datetime import date

    from coach import core, history
    first = {"n": 1, "title": "t", "unit": "", "lesson": "x", "completed": False, "passed_on": "2026-10-02"}
    link = {"n": 1, "title": "t", "unit": "", "lesson": "", "from": "2026-10-01", "completed": True}
    open2 = {"n": 2, "title": "t", "unit": "", "lesson": "y", "completed": False}
    done3 = {"n": 3, "title": "t", "unit": "", "lesson": "z", "completed": True}
    log = {"entries": [
        {"date": "2026-10-01", "topic": "fashion", "completed": False, "lessons": [first]},
        {"date": "2026-10-02", "topic": "fashion", "completed": False, "lessons": [link, open2]},
        {"date": "2026-10-03", "topic": "fashion", "completed": True, "lessons": [done3]}]}
    today = date(2026, 10, 3)
    assert core.current_streak(log, today) == 2                  # Oct 2 and 3: a lesson passed each day
    assert core.longest_streak(log) == 2
    assert len(core.completed_dates(log)) == 1                   # only Oct 3 finished every lesson
    assert len({e["date"] for e in log["entries"]}) == 3         # studied all three days
    stats = [history.day_stats(log, date(2026, 10, d), today) for d in (1, 2, 3)]
    assert [s["status"] for s in stats] == ["partial", "partial", "done"]
    assert [s["done"] for s in stats] == [0, 1, 1]               # the lesson counts once, on Oct 2
    assert history.month_summary(log, 2026, 10, today)["lessons"] == 2


def test_a_day_with_reading_reads_the_same_in_every_figure():
    """ISS-012: 1 of 3 lessons passed plus a reading check-in: the top figure
    said the day was completed, the calendar Partly done; the month counted
    the check-in as a lesson."""
    from coach import core
    log = {"entries": [entry("2026-10-01", done=1, total=3),
                       {"date": "2026-10-01", "topic": "reading", "completed": True, "lessons": []},
                       {"date": "2026-10-02", "topic": "reading", "completed": True, "lessons": []}], "books": []}
    today = date(2026, 10, 3)
    assert history.day_stats(log, date(2026, 10, 1), today)["status"] == "partial"
    assert date(2026, 10, 1) not in core.completed_dates(log)
    assert history.day_stats(log, date(2026, 10, 2), today)["status"] == "done"      # a reading day alone
    assert core.completed_dates(log) == {date(2026, 10, 2)}
    month = history.month_summary(log, 2026, 10, today)
    assert month["completed"] == len(core.completed_dates(log))
    assert month["lessons"] == core.lessons_passed(log) == 1
