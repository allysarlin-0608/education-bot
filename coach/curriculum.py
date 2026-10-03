"""The fixed syllabus: each lesson topic has up to TOTAL numbered lessons,
taken in order, PER_DAY on the day the topic is scheduled.

A syllabus is a text file per topic in coach/curriculum/: one lesson title
per line, in teaching order. Lines starting with "#" name the unit the
lessons below them belong to; blank lines are ignored. Lesson numbers are
positions in the file (1-based), so lessons are only ever appended.

A day's lessons live in that day's entry, entry["lessons"]: a list of
{"n", "title", "unit", "kickoff", "lesson", "followups", "completed", "quiz"}.
A lesson is completed by passing its quiz (coach/quiz.py); the day is
complete once every lesson in it is completed.

A lesson not passed on its day isn't written again: on a later day its
slot is a link, {"n", "title", "unit", "from": that first day, "completed"}
with no content of its own. The lesson, its chat and every quiz attempt
stay on the original slot (origin()); "completed" on the link is the day
it was passed (streaks count that day), while the original day stays not
completed and its slot gets "passed_on"."""
from datetime import date
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
    # "cards" from the start: a lesson written since review began makes its own
    # cards; only lessons without the key are worked out as old ones (review.legacy)
    return {"n": n, "title": info["title"], "unit": info["unit"],
            "kickoff": "", "lesson": "", "followups": [], "completed": False, "quiz": None, "cards": []}


def _written_before(log: dict, topic: str, n: int):
    """(entry, slot) holding lesson n's content, not passed: the latest one
    (from before links existed a lesson could have been written twice)."""
    found = None
    for e in log["entries"]:
        if e["topic"] != topic:
            continue
        for slot in e.get("lessons") or []:
            if (slot["n"] == n and slot.get("lesson") and not slot.get("from")
                    and not slot.get("completed") and not slot.get("passed_on")):
                if found is None or e["date"] >= found[0]["date"]:
                    found = (e, slot)
    return found


def plan_slot(log: dict, topic: str, n: int) -> dict:
    """A slot for lesson n on a new day: a link to where it was already
    written (not passed), or a fresh slot."""
    slot = new_slot(topic, n)
    before = _written_before(log, topic, n)
    if before is not None:
        slot["from"] = before[0]["date"]
        del slot["cards"]                   # a link holds no content of its own
    return slot


def origin(log: dict, topic: str, slot: dict):
    """For a link: (entry, slot) of the lesson it points to, or None (a slot
    holding its own lesson, or a link whose day isn't in the log)."""
    if not slot.get("from"):
        return None
    for e in log["entries"]:
        if e["topic"] == topic and e["date"] == slot["from"]:
            for s in e.get("lessons") or []:
                if s["n"] == slot["n"] and not s.get("from"):
                    return e, s
    return None


def content(log: dict, topic: str, slot: dict) -> dict:
    """The slot whose lesson, chat and quizzes to show for this one."""
    found = origin(log, topic, slot)
    return found[1] if found else slot


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
    return [plan_slot(log, topic, n) for n in next_numbers(log, topic, count)]


def _touched(slot: dict) -> bool:
    return bool(slot.get("completed") or slot.get("lesson") or slot.get("quiz"))


def worked_on(entry: dict) -> bool:
    """Anything done on this day's own record: a lesson written, a quiz,
    a question asked, a lesson passed, her thoughts."""
    return bool(entry.get("completed") or (entry.get("reflection") or "").strip() or any(
        _touched(s) or s.get("followups") for s in entry.get("lessons") or []))


def fit(log: dict, topic: str, slots: list, count: int) -> list:
    """A day already started, after her pace changed: the lessons she has
    begun or finished stay; untouched ones past the new count go, and new
    ones are added up to it. A finished day stays exactly as it was."""
    if len(slots) == count or day_complete(slots):
        return slots
    kept = [s for k, s in enumerate(slots) if k < count or _touched(s)]
    have = {s["n"] for s in kept}
    extra = [n for n in next_numbers(log, topic, count + len(have)) if n not in have]
    kept += [plan_slot(log, topic, n) for n in extra[:max(0, count - len(kept))]]
    return sorted(kept, key=lambda s: s["n"])


def progress_of(slot: dict) -> tuple:
    """How far a lesson has got, in order: passed, quiz attempts, a quiz,
    written, questions asked. Saves never move a lesson back along it."""
    q = slot.get("quiz") or {}
    return (bool(slot.get("completed") or slot.get("passed_on")), q.get("attempts") or 0, bool(q),
            bool(slot.get("lesson")), len(slot.get("followups") or []))


def merge_day(mine: dict, stored: dict, ns, since, keep=(), recount=False) -> None:
    """`mine` (this session's copy of a day, which may be old: another tab or
    device may have saved since) written into the day as stored now, in place.
    - lessons `ns` (the ones this page worked on): this page's copy, unless
      the stored one has got further (passed, a newer quiz attempt...); then
      the stored one, so progress is never undone (ISS-024);
    - their review cards: the stored ones (graded or deleted elsewhere win)
      plus the cards this page made: those added on or after `since` (the
      day the page was opened, not the clock: a quiz submitted after
      midnight, ISS-028), or, with `since` None (work a save failed on,
      kept as this session holds it), every card the store doesn't have;
    - every other lesson, and the day's other fields: as stored, except the
      fields in `keep` (what this page changed, e.g. her thoughts);
    - with `recount` (today's day), completed when its lessons are; an
      earlier day keeps its own (a lesson carried on is passed later, there).
    The lesson objects of `ns` stay the same objects (pages hold them)."""
    own = {s["n"]: s for s in mine["lessons"] if s["n"] in ns}
    lessons = []
    for s in stored["lessons"]:
        m = own.get(s["n"])
        if m is None:
            lessons.append(s)
            continue
        if progress_of(s) > progress_of(m):
            m.clear()
            m.update(s)
        elif "cards" in s:
            have = {c["id"] for c in s["cards"]}
            removed = set(s.get("removed") or []) | set(m.get("removed") or [])
            m["cards"] = s["cards"] + [c for c in m.get("cards") or [] if c["id"] not in have | removed
                                       and (since is None or c.get("added", "") >= since.isoformat())]
            if removed:
                m["removed"] = sorted(removed)
        lessons.append(m)
    lessons += [m for n, m in own.items() if n not in {s["n"] for s in stored["lessons"]}]
    lessons.sort(key=lambda s: s["n"])
    kept = {k: mine[k] for k in keep if k in mine}
    mine.update({k: v for k, v in stored.items() if k != "lessons"}, lessons=lessons, **kept)
    if recount:
        mine["completed"] = day_complete(lessons)


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
        for field in ("from", "passed_on"):         # a link's first day; the day a lesson was passed later
            if _is_date(s.get(field)):
                slots[-1][field] = s[field]
        from coach import review
        if isinstance(s.get("cards"), list):        # kept even when empty: no cards left is not "never had any"
            slots[-1]["cards"] = review.parse_cards(s["cards"])
        if isinstance(s.get("removed"), list):      # ids of cards she deleted (review.remove)
            slots[-1]["removed"] = sorted({str(x) for x in s["removed"]})
        if slots[-1].get("from"):                   # a link holds no content of its own
            slots[-1].update(kickoff="", lesson="", followups=[], quiz=None)
            slots[-1].pop("cards", None)
            slots[-1].pop("removed", None)
    return slots


def _is_date(value) -> bool:
    try:
        return isinstance(value, str) and bool(date.fromisoformat(value))
    except ValueError:
        return False
