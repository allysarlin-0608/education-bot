"""Coming back (coach/streaks.py, coach/habit.py, coach/prefs.py): rest days,
the welcome after a break, a light day, reminders, the week in review and
milestones, over simulated days and weeks."""
from datetime import date, datetime, timedelta

import pytest

from coach import catalog, core, habit, prefs, review, streaks

MON = date(2026, 10, 5)          # a Monday


def days(*offsets, start=MON):
    return {start + timedelta(days=k) for k in offsets}


def log_on(study_days, topic="philosophy", score=90, per_day=1):
    """A record with lessons passed on these days (numbered in order)."""
    entries, n = [], 0
    for d in sorted(study_days):
        lessons = []
        for _ in range(per_day):
            n += 1
            lessons.append({"n": n, "title": f"Lesson {n}", "unit": "Unit", "completed": True, "lesson": "Text",
                            "quiz": {"score": score, "best": score}})
        entries.append({"date": d.isoformat(), "topic": topic, "lessons": lessons, "completed": True,
                        "level": "Beginner", "session_number": 1, "title": "", "followup_question": "",
                        "reflection": ""})
    return {"version": 1, "entries": entries, "books": [], "paths": []}


# ------------------------------------------------------------- rest days
def test_every_seven_study_days_earn_a_rest_day_kept_up_to_two():
    s = streaks.walk(days(*range(7)), MON + timedelta(days=6))
    assert s["current"] == 7 and s["rest"] == 1 and s["earned_in"] == 7
    s = streaks.walk(days(*range(21)), MON + timedelta(days=20))
    assert s["rest"] == streaks.MAX_REST and s["earned_in"] == 0


def test_one_missed_day_uses_a_rest_day_and_the_streak_goes_on():
    study = days(*range(7), 8, 9)                       # day 7 missed
    s = streaks.walk(study, MON + timedelta(days=9))
    assert s["current"] == 9 and s["rest"] == 0 and MON + timedelta(days=7) in s["rest_days"]


def test_a_missed_day_without_a_rest_day_starts_again():
    s = streaks.walk(days(0, 1, 2, 4, 5), MON + timedelta(days=5))
    assert s["current"] == 2 and s["broken_on"] == MON + timedelta(days=3) and s["longest"] == 3


def test_a_break_longer_than_the_rest_days_ends_the_streak_and_keeps_them():
    s = streaks.walk(days(*range(14), 17), MON + timedelta(days=17))   # 3 missed, 2 rest days
    assert s["current"] == 1 and s["rest"] == 2 and s["longest"] == 14


def test_today_never_counts_against_her_and_a_break_in_progress_is_covered():
    study = days(*range(7))
    assert streaks.walk(study, MON + timedelta(days=7))["current"] == 7             # today not over
    s = streaks.walk(study, MON + timedelta(days=8))                                 # yesterday missed
    assert s["current"] == 7 and s["covering"] == 1 and s["rest"] == 0
    assert "covering your break" in streaks.explain(s)
    assert streaks.walk(study, MON + timedelta(days=9))["current"] == 0              # two missed, one rest day


def test_every_page_reads_the_same_streak():
    log = log_on(days(*range(7), 8))
    today = MON + timedelta(days=8)
    assert core.current_streak(log, today) == streaks.walk(core.streak_dates(log), today)["current"] == 8
    assert core.longest_streak(log, today) == 8


# ---------------------------------------------------------- welcome back
def test_a_break_is_noticed_and_the_recap_names_where_she_was():
    log = log_on(days(0, 1, 2))
    assert not habit.returning(log, MON + timedelta(days=3))
    assert not habit.returning(log, MON + timedelta(days=4))       # one day off is just a day off
    back = MON + timedelta(days=10)
    assert habit.returning(log, back) and habit.away(log, back) == 7
    r = habit.recap(log, back)
    assert r["name"] == "Philosophy" and r["n"] == 3 and r["title"] == "Lesson 3"
    assert habit.recap(core.empty_log(), back) is None


def test_a_light_or_returning_day_offers_a_short_review_catch_up():
    log = log_on(days(0, 1, 2))
    p = prefs.blank()
    assert habit.review_limit(log, p, MON + timedelta(days=3)) is None
    assert habit.review_limit(log, p, MON + timedelta(days=20)) == habit.CATCH_UP_REVIEWS
    light = dict(p, light_day=(MON + timedelta(days=3)).isoformat())
    assert habit.lessons_today(light, MON + timedelta(days=3), 5) == 1
    assert habit.lessons_today(light, MON + timedelta(days=4), 5) == 5, "a light day is that day only"


def test_review_never_offers_more_than_the_limit():
    import seed_history
    log = core.parse_log({"entries": seed_history.build(review.LEGACY_FROM - timedelta(days=1), days=40),
                          "books": []})
    many = review.due(log, review.LEGACY_FROM + timedelta(days=60))
    few = review.due(log, review.LEGACY_FROM + timedelta(days=60), limit=habit.CATCH_UP_REVIEWS)
    assert len(few) <= habit.CATCH_UP_REVIEWS <= len(many) and few == many[:len(few)]


# --------------------------------------------------------------- reminders
@pytest.mark.parametrize("now, due", [
    ("18:59", False), ("19:00", True), ("23:59", True), ("00:05", False)])
def test_the_reminder_shows_after_her_time_on_a_day_not_yet_studied(now, due):
    p = dict(prefs.blank(), reminder_on=True, reminder_time="19:00")
    day = MON + timedelta(days=4)
    hh, mm = map(int, now.split(":"))
    assert habit.reminder_due(p, log_on(days(0)), datetime(day.year, day.month, day.day, hh, mm)) == due


def test_no_reminder_once_she_studied_or_was_reminded_or_turned_it_off():
    day = MON + timedelta(days=1)
    at = datetime(day.year, day.month, day.day, 21, 0)
    on = dict(prefs.blank(), reminder_on=True, reminder_time="19:00")
    assert not habit.reminder_due(on, log_on(days(1)), at)
    assert not habit.reminder_due(dict(on, reminded_on=day.isoformat()), log_on(days(0)), at)
    assert not habit.reminder_due(dict(on, reminder_on=False), log_on(days(0)), at)


def test_reminder_preferences_are_checked():
    p = prefs.normalize({"reminder_on": "yes", "reminder_time": "25:00", "seen": ["a", 3, "b"], "light_day": 7})
    assert p["reminder_on"] is False and p["reminder_time"] == prefs.DEFAULT_TIME
    assert p["seen"] == ["a", "b"] and p["light_day"] == ""
    assert prefs.normalize("junk") == prefs.blank()


# --------------------------------------------------------------- the week
def test_a_week_from_monday_to_sunday_against_the_one_before():
    before = days(*range(-7, -4))                  # Mon-Wed the week before, 90%
    this = days(0, 2, 4, 5)                         # 4 days this week
    log = log_on(before | this)
    w = habit.week(log, MON, MON + timedelta(days=6))
    assert w["lessons"] == 4 and w["lessons_before"] == 3 and w["days"] == 4 and w["days_before"] == 3
    assert w["learned"][0]["name"] == "Philosophy" and len(w["learned"][0]["titles"]) == 4
    assert w["quiz_avg"] == 90 and w["suggestion"]


def test_a_lesson_passed_late_sunday_and_early_monday_land_in_their_own_weeks():
    sunday, monday = MON + timedelta(days=6), MON + timedelta(days=7)
    log = log_on({sunday, monday})
    assert habit.week(log, MON, monday)["lessons"] == 1
    assert habit.week(log, monday, monday)["lessons"] == 1
    assert habit.week_of(sunday) == MON and habit.week_of(monday) == monday
    assert habit.week_key(sunday) != habit.week_key(monday)


def test_lessons_worth_reviewing_are_the_shaky_ones():
    log = log_on(days(0, 1), score=80)
    w = habit.week(log, MON, MON + timedelta(days=6))
    assert len(w["review"]) == 2 and all(r["score"] == 80 for r in w["review"])
    assert habit.week(log_on(days(0, 1), score=100), MON, MON + timedelta(days=6))["review"] == []


def test_an_empty_week_says_so_kindly():
    w = habit.week(core.empty_log(), MON, MON + timedelta(days=6))
    assert w["lessons"] == 0 and "fresh week" in w["suggestion"].lower()


# ------------------------------------------------------------ milestones
def test_milestones_are_earned_once_and_never_shown_twice():
    log = log_on(days(*range(10)))
    today = MON + timedelta(days=9)
    keys = {m["key"] for m in habit.milestones(log, today)}
    assert {"streak-7", "lessons-10"} <= keys and "streak-30" not in keys
    p = prefs.mark_seen(prefs.blank(), keys)
    assert habit.new_milestones(log, today, p["seen"]) == []


def test_a_goal_halfway_and_done():
    from test_goals import a_path
    goal = a_path()
    catalog.use([goal])
    try:
        n = sum(len(u["lessons"]) for u in goal["units"])
        log = log_on(days(*range(n // 2)), topic=goal["id"])
        keys = {m["key"] for m in habit.milestones(log, MON + timedelta(days=n))}
        assert f"goal-half-{goal['id']}" in keys and f"goal-done-{goal['id']}" not in keys
        log = log_on(days(*range(n)), topic=goal["id"])
        assert f"goal-done-{goal['id']}" in {m["key"] for m in habit.milestones(log, MON + timedelta(days=n))}
    finally:
        catalog.use([])


# ----------------------------------------------------- how far she's come
def test_where_she_started_and_where_she_is():
    log = log_on(days(*range(12)), score=80)
    for e in log["entries"][-5:]:
        e["lessons"][0]["quiz"]["best"] = 100
    j = habit.journey(log, "philosophy")
    assert j["started"] == MON.isoformat() and j["done"] == 12
    assert j["first_avg"] == 80 and j["recent_avg"] == 100
