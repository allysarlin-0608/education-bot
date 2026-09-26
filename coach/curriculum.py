"""The fixed syllabus: each lesson topic has up to TOTAL numbered lessons,
taken in order, PER_DAY on the day the topic is scheduled.

A syllabus is a text file per topic in coach/curriculum/: one lesson title
per line, in teaching order. Lines starting with "#" name the unit the
lessons below them belong to; blank lines are ignored. Lesson numbers are
positions in the file (1-based), so lessons are only ever appended.

A day's lessons live in that day's entry, entry["lessons"]: a list of
{"n", "title", "unit", "kickoff", "lesson", "followups", "completed", "quiz"}.
A lesson is completed by passing its quiz (coach/quiz.py); the day is
complete once every lesson in it is completed."""
from functools import lru_cache
from pathlib import Path

from coach import quiz

TOTAL = 3000            # lessons planned per topic
PER_DAY = 5             # lessons on the day a topic is scheduled
# Level by position in the syllabus: 1–1000 Beginner, 1001–2000 Intermediate,
# 2001–3000 Advanced.
LEVELS = ("Beginner", "Intermediate", "Advanced")
LEVEL_SIZE = TOTAL // 3

DIR = Path(__file__).resolve().parent / "curriculum"


def has_syllabus(topic: str) -> bool:
    return (DIR / f"{topic}.txt").exists()


@lru_cache(maxsize=None)
def _load(topic: str) -> tuple:
    lessons, unit = [], ""
    for raw in (DIR / f"{topic}.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            unit = line.lstrip("#").strip()
        else:
            lessons.append((unit, line))
    return tuple(lessons)


def written(topic: str) -> int:
    """How many lessons of the syllabus are written so far."""
    return len(_load(topic))


def lesson(topic: str, n: int) -> dict:
    """Lesson n (1-based): its unit and title, or None past what's written."""
    lessons = _load(topic)
    if not 1 <= n <= len(lessons):
        return None
    unit, title = lessons[n - 1]
    return {"n": n, "unit": unit, "title": title}


def level_for(n: int) -> str:
    return LEVELS[min((n - 1) // LEVEL_SIZE, 2)]


def completed_numbers(log: dict, topic: str) -> set:
    return {
        slot["n"]
        for e in log["entries"] if e["topic"] == topic
        for slot in e.get("lessons") or []
        if slot.get("completed")
    }


def next_numbers(log: dict, topic: str, count: int = PER_DAY) -> list:
    """The first `count` lessons she hasn't completed yet, in order. A
    lesson left unfinished on an earlier day comes first."""
    done = completed_numbers(log, topic)
    out = []
    n = 1
    while len(out) < count and n <= written(topic):
        if n not in done:
            out.append(n)
        n += 1
    return out


def new_slot(topic: str, n: int) -> dict:
    info = lesson(topic, n)
    return {"n": n, "title": info["title"], "unit": info["unit"],
            "kickoff": "", "lesson": "", "followups": [], "completed": False, "quiz": None}


def unit_progress(log: dict, topic: str) -> dict:
    """The unit she is in now (the one holding her next lesson, or the last
    unit once everything written is done) and how far through it she is."""
    lessons = _load(topic)
    if not lessons:
        return None
    upcoming = next_numbers(log, topic, 1)
    n = upcoming[0] if upcoming else len(lessons)
    unit = lessons[n - 1][0]
    first = last = n
    while first > 1 and lessons[first - 2][0] == unit:
        first -= 1
    while last < len(lessons) and lessons[last][0] == unit:
        last += 1
    done = completed_numbers(log, topic)
    return {
        "unit": unit,
        "first": first,
        "last": last,
        "total": last - first + 1,
        "done": sum(1 for k in range(first, last + 1) if k in done),
    }


def refresh_titles(topic: str, slots: list) -> list:
    """Show saved lessons under the syllabus's current wording (lesson
    numbers never change, only titles can be reworded or translated)."""
    for slot in slots:
        info = lesson(topic, slot["n"])
        if info:
            slot["title"], slot["unit"] = info["title"], info["unit"]
    return slots


def day_plan(log: dict, topic: str, entry, count: int = PER_DAY) -> list:
    """The day's lessons: the saved ones if the day has started, otherwise
    the next `count` lessons (not saved until one is started). `count` is
    her daily pace (settings)."""
    if entry is not None and entry.get("lessons"):
        return fit(log, topic, refresh_titles(topic, entry["lessons"]), count)
    return [new_slot(topic, n) for n in next_numbers(log, topic, count)]


def _touched(slot: dict) -> bool:
    return bool(slot.get("completed") or slot.get("lesson") or slot.get("quiz"))


def fit(log: dict, topic: str, slots: list, count: int) -> list:
    """A day already started, after her pace changed: the lessons she has
    begun or finished stay; untouched ones past the new count go, and new
    ones are added up to it. A finished day stays exactly as it was."""
    if len(slots) == count or day_complete(slots):
        return slots
    kept = [s for k, s in enumerate(slots) if k < count or _touched(s)]
    have = {s["n"] for s in kept}
    extra = [n for n in next_numbers(log, topic, count + len(have)) if n not in have]
    kept += [new_slot(topic, n) for n in extra[:max(0, count - len(kept))]]
    return sorted(kept, key=lambda s: s["n"])


def blocking(slots: list, i: int):
    """The first earlier lesson of the day not finished yet, or None.
    Lessons are finished strictly in order: lesson i can't be started or
    quizzed while one before it is open."""
    return next((s for s in slots[:i] if not s.get("completed")), None)


def day_complete(slots: list) -> bool:
    return bool(slots) and all(s.get("completed") for s in slots)


def progress(log: dict, topic: str) -> dict:
    """Lessons completed on a topic, the current level and how far into it."""
    done = len(completed_numbers(log, topic))
    current = min(done + 1, TOTAL)
    level = level_for(current)
    start = LEVELS.index(level) * LEVEL_SIZE
    return {
        "done": done,
        "total": TOTAL,
        "written": written(topic),
        "level": level,
        "level_done": done - start,
        "level_size": LEVEL_SIZE,
    }


def parse_slots(data) -> list:
    """Validate saved lessons (from the database or an uploaded backup)."""
    if not isinstance(data, list):
        return []
    slots = []
    for s in data:
        if not isinstance(s, dict) or not isinstance(s.get("n"), int):
            continue
        followups = [
            {"role": m["role"], "content": m["content"]}
            for m in s.get("followups") or []
            if isinstance(m, dict) and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)
        ]
        slots.append({
            "n": s["n"],
            "title": str(s.get("title") or ""),
            "unit": str(s.get("unit") or ""),
            "kickoff": str(s.get("kickoff") or ""),
            "lesson": str(s.get("lesson") or ""),
            "followups": followups,
            "completed": bool(s.get("completed")),
            "quiz": quiz.parse_saved(s.get("quiz")),
        })
    return slots
