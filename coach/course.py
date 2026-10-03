"""A subject's course map: its units and lessons in order, and where she is
on the path. Pure functions over the syllabus (coach/curriculum.py) and her
record, so they can be tested; views/course.py draws them.

A lesson is one of:
- "done":    passed (the day it was passed and its best score are known)
- "today":   on today's plan for this subject, not passed yet
- "next":    the first lesson not passed (when it isn't on today's plan)
- "started": written on an earlier day, not passed (it comes back on a later day)
- "ahead":   not reached: only its title is known (lessons are written when reached)

Units are the syllabus's own: "done" when every lesson in them is passed,
"current" for the one holding her next lesson, "ahead" or "behind" otherwise."""
from datetime import date

from coach import core, curriculum


def _records(log: dict, topic: str) -> dict:
    """For each lesson number: its content slot (lesson, chat, quizzes), the
    day it was first written, and the day it was passed."""
    out = {}
    for e in sorted(log["entries"], key=lambda x: x["date"]):
        if e["topic"] != topic:
            continue
        for slot in e.get("lessons") or []:
            r = out.setdefault(slot["n"], {"slot": None, "entry": None, "started": None, "passed": None})
            if slot.get("lesson") and not slot.get("from"):
                r["slot"], r["entry"] = slot, e            # (the latest written copy)
                r["started"] = r["started"] or e["date"]
            if slot.get("completed") and not r["passed"]:
                r["passed"] = e["date"]
            if slot.get("passed_on") and not r["passed"]:
                r["passed"] = slot["passed_on"]
    return out


def lesson_record(log: dict, topic: str, n: int):
    """(entry, slot, passed_on) of lesson n's written lesson, or None."""
    r = _records(log, topic).get(n)
    if not r or r["slot"] is None:
        return None
    return r["entry"], r["slot"], r["passed"]


def build(log: dict, topic: str, today_plan: list = ()) -> dict:
    """The whole map: units with their lessons and states, and a summary."""
    lessons = curriculum._load(topic)
    records = _records(log, topic)
    done = curriculum.completed_numbers(log, topic)
    upcoming = curriculum.next_numbers(log, topic, 1)
    nxt = upcoming[0] if upcoming else None
    on_today = {s["n"] for s in today_plan}
    units = []
    for n, (unit, title) in enumerate(lessons, start=1):
        if not units or units[-1]["name"] != unit:
            units.append({"name": unit, "lessons": []})
        r = records.get(n, {})
        if n in done:
            state = "done"
        elif n in on_today:
            state = "today"
        elif n == nxt:
            state = "next"
        elif r.get("slot") is not None:
            state = "started"
        else:
            state = "ahead"
        q = (r.get("slot") or {}).get("quiz") or {}
        units[-1]["lessons"].append({"n": n, "title": title, "state": state, "passed": r.get("passed"),
                                     "started": r.get("started"), "best": q.get("best"),
                                     "readable": r.get("slot") is not None})
    current = None
    for k, u in enumerate(units):
        states = [x["state"] for x in u["lessons"]]
        u["first"], u["last"] = u["lessons"][0]["n"], u["lessons"][-1]["n"]
        u["done_count"] = states.count("done")
        if all(s == "done" for s in states):
            u["state"] = "done"
        elif current is None and any(s in ("today", "next") for s in states):
            u["state"], current = "current", k
        else:
            u["state"] = "open" if u["done_count"] or "started" in states else "ahead"
    if current is None:          # everything written is passed, or nothing to point at
        current = next((k for k, u in enumerate(units) if u["state"] != "done"), len(units) - 1 if units else None)
    return {"topic": topic, "units": units, "current": current, "done": len(done), "written": len(lessons),
            "next": nxt, "total": curriculum.TOTAL}


def short_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def subject_name(topic: str) -> str:
    return core.TOPICS.get(topic, topic)
