"""The few numbers that say whether GNOSIS works, and the events they come from.

Only what's needed is kept: per person, per day, how many times one of four
things happened. No lesson, answer, goal text or anything she wrote.
- "visit": she opened GNOSIS that day (once a day)
- "setup_done": she finished setting up
- "goal_created": she added a goal of her own
- "lesson_passed": she passed a lesson (counted)
- "reminder_shown": her daily reminder was shown to her (once a day)
- "reminded_session": she passed a lesson after a reminder that day (once a day)

The numbers (for admins, Settings → Insights), for people who signed up since
a date:
- signed up → set up a goal or subjects → passed a first lesson
- came back the day after signing up
- still opened GNOSIS a week or more after signing up
- lessons passed per learner per week
- reminders shown, and how many led to a lesson the same day

summarize() is the same arithmetic as gnosis_metrics() in supabase/goals.sql,
for the local store and the tests."""
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EVENTS = ("visit", "setup_done", "goal_created", "lesson_passed", "reminder_shown", "reminded_session")
TZ = ZoneInfo("Asia/Taipei")


def signup_day(created_at: str) -> date:
    when = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(TZ).date()


def summarize(users: list, events: list, since: date, today: date) -> dict:
    """users: rows with user_id and created_at; events: rows with user_id,
    day, event, count."""
    by_user = defaultdict(list)
    for e in events:
        by_user[e["user_id"]].append(e)
    cohort = []
    for u in users:
        if not u.get("created_at"):
            continue
        day0 = signup_day(u["created_at"])
        if day0 >= since:
            cohort.append((u["user_id"], day0))

    def has(uid, test):
        return any(test(e) for e in by_user.get(uid, []))

    def day(e):
        return e["day"] if isinstance(e["day"], date) else date.fromisoformat(str(e["day"]))

    weeks = defaultdict(int)
    for e in events:
        if e["event"] == "lesson_passed" and day(e) >= since:
            d = day(e)
            weeks[(e["user_id"], d - timedelta(days=d.weekday()))] += int(e.get("count") or 0)
    return {
        "since": since.isoformat(),
        "signed_up": len(cohort),
        "set_up": sum(1 for uid, _ in cohort if has(uid, lambda e: e["event"] in ("setup_done", "goal_created"))),
        "first_lesson": sum(1 for uid, _ in cohort if has(uid, lambda e: e["event"] == "lesson_passed")),
        "came_back_next_day": sum(1 for uid, d0 in cohort
                                  if has(uid, lambda e, d0=d0: e["event"] == "visit" and day(e) == d0 + timedelta(days=1))),
        "eligible_next_day": sum(1 for _, d0 in cohort if d0 + timedelta(days=1) <= today),
        "active_after_a_week": sum(1 for uid, d0 in cohort
                                   if has(uid, lambda e, d0=d0: e["event"] == "visit" and day(e) >= d0 + timedelta(days=7))),
        "eligible_week": sum(1 for _, d0 in cohort if d0 + timedelta(days=7) <= today),
        "lessons_per_learner_week": _round1(Decimal(sum(weeks.values())) / len(weeks)) if weeks else 0,
        "reminders_shown": sum(int(e.get("count") or 0) for e in events
                               if e["event"] == "reminder_shown" and day(e) >= since),
        "reminded_sessions": sum(int(e.get("count") or 0) for e in events
                                 if e["event"] == "reminded_session" and day(e) >= since),
    }


def _round1(x: Decimal) -> float:
    """To one place, halves up: as Postgres's round() (2.25 is 2.3)."""
    return float(x.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def share(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "—"
