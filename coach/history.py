"""Her learning history by day and by month, for the calendar on the
Progress page. Pure functions over the log, so they can be tested."""
import calendar
from datetime import date

from coach import core


def entries_on(log: dict, day: date) -> list:
    iso = day.isoformat()
    return [e for e in log["entries"] if e["date"] == iso]


def day_stats(log: dict, day: date, today: date) -> dict:
    """What happened on one day: the lessons passed and planned (a day from
    before the syllabus counts as one session), whether it was completed,
    and the subjects studied."""
    entries = entries_on(log, day)
    done = total = 0
    for e in entries:
        if e.get("lessons"):
            total += len(e["lessons"])
            done += sum(1 for s in e["lessons"] if s["completed"])
        else:
            total += 1
            done += 1 if e.get("completed") else 0
    if day > today:
        status = "future"
    elif entries and all(e.get("completed") for e in entries):
        status = "done"
    elif entries:
        status = "partial"
    else:
        status = "none"
    return {"date": day, "status": status, "done": done, "total": total,
            "topics": [e["topic"] for e in entries]}


def month_grid(log: dict, year: int, month: int, today: date) -> list:
    """Monday-first weeks covering the month; days of the months either side
    are included (marked out of month) so every row is a full week."""
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    return [[{**day_stats(log, d, today), "in_month": d.month == month} for d in week] for week in weeks]


def month_summary(log: dict, year: int, month: int, today: date) -> dict:
    days = [day_stats(log, date(year, month, d), today) for d in range(1, calendar.monthrange(year, month)[1] + 1)]
    return {
        "studied": sum(1 for d in days if d["status"] in ("done", "partial")),
        "completed": sum(1 for d in days if d["status"] == "done"),
        "lessons": sum(d["done"] for d in days),
    }


def first_month(log: dict, today: date) -> tuple:
    """The earliest month there is anything to show (this month if nothing yet)."""
    if not log["entries"]:
        return today.year, today.month
    first = date.fromisoformat(min(e["date"] for e in log["entries"]))
    return first.year, first.month


def shift(year: int, month: int, by: int) -> tuple:
    k = year * 12 + (month - 1) + by
    return k // 12, k % 12 + 1


def amount(stats: dict) -> int:
    """How much of the day's work was done, as a step of 0–5 (for the bar under
    each day), so a partly done day reads at a glance."""
    if not stats["total"]:
        return 0
    return max(1, round(5 * stats["done"] / stats["total"])) if stats["done"] else 0


def short_topic(topic: str) -> str:
    return core.TOPICS[topic].split(" ")[0].rstrip(",&")
