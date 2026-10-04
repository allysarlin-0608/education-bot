"""Streaks, with rest days: one missed day doesn't erase weeks of effort.

The rule, as a learner reads it (Progress shows it in these words):
- A study day is a day she passed a lesson (or checked in on her reading).
- Every 7 study days earn a rest day; she can keep up to 2.
- A missed day uses a rest day by itself, so the streak keeps going. A
  break longer than the rest days she has ends the streak (her rest days
  stay for next time).
- Today doesn't count against her until it's over.

Everything is worked out from her record, never stored: every page and
every device shows the same numbers, and nothing can drift. Pure functions."""
from datetime import date, timedelta

EARN_EVERY = 7          # study days for one rest day
MAX_REST = 2            # rest days kept at most


def _days(a: date, b: date):
    """The days strictly between a and b."""
    d = a + timedelta(days=1)
    while d < b:
        yield d
        d += timedelta(days=1)


def walk(study: set, today: date) -> dict:
    """Her streaks through today. study: the dates she studied.

    {"current": study days in the streak going now (0: none),
     "longest": the longest streak ever (study days),
     "rest": rest days she has now, "earned_in": study days until the next,
     "rest_days": the missed days a rest day covered (for the calendar),
     "covering": missed days up to yesterday covered right now (0: none),
     "broken_on": the day a streak last ended, or None}"""
    days = sorted(d for d in study if d <= today)
    rest, since, run, best = 0, 0, 0, 0
    rest_days, broken_on, prev = set(), None, None
    for d in days:
        if prev is not None:
            gap = list(_days(prev, d))
            if gap and len(gap) <= rest:
                rest -= len(gap)
                rest_days.update(gap)
            elif gap:
                run, broken_on = 0, gap[0]
        run += 1
        best = max(best, run)
        since += 1
        if since == EARN_EVERY:
            since = 0
            rest = min(MAX_REST, rest + 1)
        prev = d
    covering = 0
    if prev is not None:
        # since the last study day, up to yesterday (today isn't over)
        gap = list(_days(prev, today))
        if gap and len(gap) <= rest:
            rest -= len(gap)
            rest_days.update(gap)
            covering = len(gap)
        elif gap:
            run, broken_on = 0, gap[0]
    return {"current": run, "longest": best, "rest": rest,
            "earned_in": EARN_EVERY - since if rest < MAX_REST else 0,
            "rest_days": rest_days, "covering": covering, "broken_on": broken_on}


def explain(s: dict) -> str:
    """One calm line about where she is, for Progress and the week."""
    if s["covering"]:
        n = s["covering"]
        return (f"{'A rest day is' if n == 1 else f'{n} rest days are'} covering your break. "
                "A lesson today keeps your streak going.")
    if s["rest"] == MAX_REST:
        return f"You have {MAX_REST} rest days saved: miss a day and your streak keeps going."
    have = f"You have {s['rest']} rest day{'s' if s['rest'] != 1 else ''} saved. " if s["rest"] else ""
    return f"{have}{s['earned_in']} more study day{'s' if s['earned_in'] != 1 else ''} earn{'s' if s['earned_in'] == 1 else ''} a rest day."
