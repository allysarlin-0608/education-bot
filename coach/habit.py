"""Coming back: the day's rhythm, a welcome after a break, reminders, the
week in review, milestones, and how far she has come. Everything here is
worked out from her record and settings (no AI call, nothing stored but
her preferences, coach/prefs.py), so every page and device agrees.

Pure functions; the pages (views/daily.py, views/week.py, views/records.py)
draw them."""
from datetime import date, datetime, timedelta

from coach import catalog, core, course, curriculum, streaks

AWAY_DAYS = 3                 # days without studying that make a return a "welcome back"
CATCH_UP_REVIEWS = 8          # review cards offered on a light or returning day (never a wall)
LIGHT_LESSONS = 1             # lessons on a light day


# ------------------------------------------------------------------- the day
def last_study_day(log: dict, today: date):
    days = [d for d in core.streak_dates(log) if d < today]
    return max(days) if days else None


def away(log: dict, today: date) -> int:
    """Whole days since she last studied (0: studied yesterday or today, or never)."""
    if today in core.streak_dates(log):
        return 0
    last = last_study_day(log, today)
    return (today - last).days - 1 if last else 0


def returning(log: dict, today: date) -> bool:
    return away(log, today) >= AWAY_DAYS - 1


def light_today(p: dict, today: date) -> bool:
    return p.get("light_day") == today.isoformat()


def lessons_today(p: dict, today: date, units: int) -> int:
    """Lessons in today's plan: her pace, or one on a light day."""
    return LIGHT_LESSONS if light_today(p, today) else units


def review_limit(log: dict, p: dict, today: date):
    """Review cards offered today: a short catch-up on a light day or after
    a break (the rest wait their turn, oldest first), else the usual limit."""
    return CATCH_UP_REVIEWS if light_today(p, today) or returning(log, today) else None


def recap(log: dict, today: date):
    """Where she was, for a welcome back: the subject and the last lesson she
    passed, or None if she has never passed one."""
    best = None
    for e in log["entries"]:
        if e["date"] >= today.isoformat() or e["topic"] == "reading":
            continue
        for s in e.get("lessons") or []:
            if s.get("completed") and s.get("title"):
                key = (e["date"], s.get("n", 0))
                if best is None or key > best[0]:
                    best = (key, e["topic"], s)
    if best is None:
        return None
    _, topic, s = best
    return {"topic": topic, "name": catalog.name(topic), "n": s.get("n"), "title": s["title"],
            "on": best[0][0]}


# --------------------------------------------------------------- reminders
def reminder_due(p: dict, log: dict, now: datetime) -> bool:
    """Her reminder, shown in the app: on, past her time today, and nothing
    studied yet today. Once a day at most (the page notes when it showed)."""
    if not p.get("reminder_on"):
        return False
    today = now.date()
    if today in core.streak_dates(log) or p.get("reminded_on") == today.isoformat():
        return False
    hh, mm = (int(x) for x in p["reminder_time"].split(":"))
    return (now.hour, now.minute) >= (hh, mm)


# ---------------------------------------------------------------- the week
def week_of(day: date) -> date:
    """The Monday that starts the week a day is in."""
    return day - timedelta(days=day.weekday())


def week_key(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def _passed_in(log: dict, start: date, end: date) -> list:
    """(day, topic, slot) for every lesson passed from start to end (inclusive),
    counted on the day it was passed (as Progress counts it)."""
    out = []
    for e in log["entries"]:
        d = date.fromisoformat(e["date"])
        if not start <= d <= end or e["topic"] == "reading":
            continue
        for s in e.get("lessons") or []:
            if s.get("completed"):
                held = curriculum.content(log, e["topic"], s) if s.get("from") else s
                out.append((d, e["topic"], held))
    return sorted(out, key=lambda x: (x[0], x[1], x[2].get("n", 0)))


def _scores(passed: list) -> list:
    out = []
    for _, _, s in passed:
        q = s.get("quiz") or {}
        best = q.get("best", q.get("score"))
        if isinstance(best, (int, float)):
            out.append(best)
    return out


def _avg(xs):
    return round(sum(xs) / len(xs)) if xs else None


def week(log: dict, monday: date, today: date) -> dict:
    """Her week from Monday (through today if it isn't over): what she
    learned, how it went against the week before, what's worth reviewing,
    and a suggestion for the week ahead."""
    end = min(monday + timedelta(days=6), today)
    passed = _passed_in(log, monday, end)
    before = _passed_in(log, monday - timedelta(days=7), monday - timedelta(days=1))
    study = core.streak_dates(log)
    days = sorted(d for d in study if monday <= d <= end)
    days_before = [d for d in study if monday - timedelta(days=7) <= d < monday]
    learned = {}
    for _, topic, s in passed:
        learned.setdefault(topic, []).append(s.get("title") or f"Lesson {s.get('n')}")
    shaky = sorted(((s.get("quiz") or {}).get("best", 100), topic, s.get("title") or "")
                   for _, topic, s in passed if ((s.get("quiz") or {}).get("best") or 100) < 90)[:3]
    avg, avg_before = _avg(_scores(passed)), _avg(_scores(before))
    s = streaks.walk(study, today)
    return {
        "monday": monday, "end": end, "over": end < today or end.weekday() == 6 and end == today,
        "lessons": len(passed), "lessons_before": len(before),
        "days": len(days), "days_before": len(days_before), "study_days": days,
        "learned": [{"topic": t, "name": catalog.name(t), "titles": titles} for t, titles in learned.items()],
        "quiz_avg": avg, "quiz_avg_before": avg_before,
        "review": [{"name": catalog.name(t), "title": title, "score": score} for score, t, title in shaky],
        "streak": s["current"], "rest": s["rest"],
        "suggestion": suggestion(len(days), len(days_before), len(passed)),
    }


def suggestion(days: int, days_before: int, lessons: int) -> str:
    """One gentle idea for the week ahead, from what this week looked like."""
    if days == 0:
        return "A fresh week. One short lesson on a day that suits you is a good start."
    if days <= 2:
        return "Try one more day than this week. A light day, one lesson, counts just as much."
    if days < days_before:
        return "A lighter week than the one before, and that's fine. Pick the days that fit; small and steady wins."
    if days >= 6:
        return "A strong rhythm. Keep it, and take a light day whenever a day is full: your rest days have you covered."
    return "A good rhythm. Keep the same days next week, or add one if you have the time."


# --------------------------------------------------------------- milestones
STREAKS = (7, 30, 100)
LESSONS = (10, 50, 100, 250, 500)


def milestones(log: dict, today: date) -> list:
    """Every milestone she has reached: [{"key", "text"}], the most recent kinds last."""
    out = []
    best = core.longest_streak(log, today)
    out += [{"key": f"streak-{n}", "text": f"A {n}-day streak"} for n in STREAKS if best >= n]
    total = core.lessons_passed(log)
    out += [{"key": f"lessons-{n}", "text": f"{n} lessons passed"} for n in LESSONS if total >= n]
    topics = {e["topic"] for e in log["entries"] if e["topic"] != "reading"} | {p["id"] for p in catalog.goals()}
    for topic in sorted(topics):
        if not catalog.known(topic) or not curriculum.has_syllabus(topic):
            continue
        m = course.build(log, topic)
        for u in m["units"]:
            if u["state"] == "done":
                out.append({"key": f"unit-{topic}-{u['first']}",
                            "text": f"Finished “{u['name']}” in {catalog.name(topic)}"})
        if catalog.is_goal(topic) and m["written"]:
            if m["done"] * 2 >= m["written"]:
                out.append({"key": f"goal-half-{topic}", "text": f"Halfway through “{catalog.name(topic)}”"})
            if m["done"] >= m["written"]:
                out.append({"key": f"goal-done-{topic}", "text": f"Completed “{catalog.name(topic)}”"})
    return out


def new_milestones(log: dict, today: date, seen: list) -> list:
    return [m for m in milestones(log, today) if m["key"] not in seen]


# --------------------------------------------------------- how far she's come
def journey(log: dict, topic: str, start_level: str = None) -> dict:
    """Where she started on a subject or goal, and where she is now."""
    m = course.build(log, topic)
    passed = sorted((x for u in m["units"] for x in u["lessons"] if x["state"] == "done"), key=lambda x: x["n"])
    started = min((e["date"] for e in log["entries"] if e["topic"] == topic and core.lessons_in(e)[0]), default=None)
    first, last = [x["best"] for x in passed[:5] if x["best"] is not None], \
        [x["best"] for x in passed[-5:] if x["best"] is not None]
    cur = m["units"][m["current"]]["name"] if m["current"] is not None else ""
    return {
        "started": started, "start_level": core.lesson_level(1, start_level),
        "level": core.lesson_level(min(m["done"] + 1, curriculum.TOTAL), start_level),
        "done": m["done"], "written": m["written"], "unit": cur,
        "first_avg": _avg(first) if len(passed) >= 6 else None,
        "recent_avg": _avg(last) if len(passed) >= 6 else None,
    }

