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

Phase 3, learning (learning_signals, the same shape: counts per person per day):
- "missed" / "recovered": an idea answered wrong, and later answered right
  again (recovered / missed: how often a mistake gets fixed)
- "held" / "slipped": a solid or mastered idea asked again two weeks or more
  after its last practice, still known or not (held / both: does it last?)
- "mastered": an idea that became mastered
- "practice_done", "explained": a practice set finished, an explanation marked
- "tutor_question", "tutor_confused": questions to the coach, and those that
  showed a misunderstanding

summarize() is the same arithmetic as gnosis_metrics() in supabase/goals.sql,
for the local store and the tests."""
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EVENTS = ("visit", "setup_done", "goal_created", "lesson_passed", "reminder_shown", "reminded_session")
# Phase 3: is she learning? (table learning_signals, supabase/mastery.sql; counts only)
SIGNALS = ("practice_done", "explained", "tutor_question", "tutor_confused",
           "missed", "recovered", "held", "slipped", "mastered")
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
        **{s: sum(int(e.get("count") or 0) for e in events if e["event"] == s and day(e) >= since)
           for s in SIGNALS},
    }


def _round1(x: Decimal) -> float:
    """To one place, halves up: as Postgres's round() (2.25 is 2.3)."""
    return float(x.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def share(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "—"


# How often the AI made her wait or failed her (table ai_waits, supabase/ai_health.sql;
# counts only), to check the AI plan before more people are invited.
WAIT_KINDS = ("busy", "failed", "slow")
SLOW_S = 15                    # an answer after this many seconds counts as slow
WAITS_PER_DAY = 500            # one person's count of each kind a day, at most


def wait_kind(outcome: str, waited_s: float):
    """What an AI call's ending counts as (None: nothing worth counting)."""
    if outcome in ("busy", "failed"):
        return outcome
    return "slow" if outcome == "ok" and waited_s > SLOW_S else None


def ai_health(waits: list, usage: list, since: date) -> dict:
    """What ai_health_summary gives: calls answered (ai_usage), and how many
    were busy, failed or slow, how many people met each, and day by day."""
    mine = [w for w in waits if str(w["day"]) >= since.isoformat()]
    by_kind, people, days = defaultdict(int), defaultdict(set), defaultdict(dict)
    for w in mine:
        by_kind[w["kind"]] += int(w["count"])
        people[w["kind"]].add(w["user_id"])
        days[str(w["day"])][w["kind"]] = days[str(w["day"])].get(w["kind"], 0) + int(w["count"])
    return {"answered": sum(int(u.get("request_count") or 0) for u in usage if str(u["date"]) >= since.isoformat()),
            "by_kind": dict(by_kind), "people": {k: len(v) for k, v in people.items()},
            "days": [dict({"day": d, "busy": None, "failed": None, "slow": None}, **v) for d, v in sorted(days.items())]}
