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
