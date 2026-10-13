"""The unit check (audit P2-2): once every lesson of a unit is passed, a
short test on the whole unit, to show it was learned, not only passed one
lesson at a time.

Its questions are ones she has already met in the unit's lessons (each
lesson's quiz, its practice exercises, the questions she missed), the kinds
marked here at once (quiz.LOCAL), taken from every lesson in turn. No AI
call. A question she reported, or a card she deleted, is never used
(review: the ids in a lesson's "removed"). PASS_MARK (80%) passes it; a
fresh set can be taken as often as she likes.

What is kept is small and lives with the unit's last lesson, in her record:
slot["unit_check"] = {"attempts", "best", "passed_on", "last_on"}. And each
lesson asked about gets what the set showed (by_lesson): a piece of
"recall" evidence for the Knowledge Map (coach/mastery.py), and a review
card for each question she missed (review.add_missed).
Pure functions, no Streamlit."""
import random
from datetime import date, timedelta

from coach import course, practice, quiz, review

SIZE = 10               # questions in a set
MIN_SIZE = 5            # fewer than this in the unit: no check is offered
PASS_MARK = quiz.PASS_MARK
FRESH_DAYS = 7          # Home points to a unit's check this long after it is finished


def units(log: dict, topic: str) -> list:
    """The course's units (course.build), each with its key ("u" + the first
    lesson's number)."""
    m = course.build(log, topic)
    return [dict(u, key=f"u{u['first']}") for u in m["units"]]


def find(log: dict, topic: str, key: str):
    return next((u for u in units(log, topic) if u["key"] == key), None)


def pool(log: dict, topic: str, unit: dict) -> list:
    """Every question she can be asked on this unit, per lesson: [(n, [question])]."""
    out = []
    for x in unit["lessons"]:
        held = course.lesson_record(log, topic, x["n"])
        if held is None:
            continue
        slot = held[1]
        gone = set(slot.get("removed") or [])
        mine = [q for q in practice.sources(slot, topic)
                if review.question_card_id(topic, x["n"], q["question"]) not in gone]
        if mine:
            out.append((x["n"], mine))
    return out


def size(log: dict, topic: str, unit: dict) -> int:
    return min(SIZE, sum(len(qs) for _, qs in pool(log, topic, unit)))


def offered(log: dict, topic: str, unit: dict) -> bool:
    """Every lesson passed, and enough questions to make a check of."""
    return unit.get("state") == "done" and size(log, topic, unit) >= MIN_SIZE


def build(log: dict, topic: str, unit: dict, attempt: int) -> list:
    """A set: [{"n", "q"}], one lesson after another in turn, the same set
    for the same attempt (so a rerun of the page doesn't change it)."""
    rng = random.Random(f"{topic}|{unit['key']}|{attempt}")
    per = []
    for n, qs in pool(log, topic, unit):
        qs = list(qs)
        rng.shuffle(qs)
        per.append([{"n": n, "q": q} for q in qs])
    rng.shuffle(per)
    items = []
    while any(per) and len(items) < SIZE:
        for group in per:
            if group and len(items) < SIZE:
                items.append(group.pop(0))
    return items


def score(items: list, answers: list) -> tuple:
    """(marks, percent) for her answers."""
    marks = [quiz.mark(it["q"], a) for it, a in zip(items, answers)]
    return marks, round(100 * sum(marks) / len(marks)) if marks else 0


def by_lesson(items: list, marks: list) -> dict:
    """What a marked set says about each lesson: {n: (its average mark,
    {"questions": [...], "marks": [...]})}, the second in the shape
    review.add_missed takes."""
    out = {}
    for it, m in zip(items, marks):
        q = out.setdefault(it["n"], {"questions": [], "marks": []})
        q["questions"].append(it["q"])
        q["marks"].append(m)
    return {n: (sum(q["marks"]) / len(q["marks"]), q) for n, q in out.items()}


def holder(log: dict, topic: str, unit: dict):
    """(entry, slot) of the unit's last lesson, where the result is kept."""
    held = course.lesson_record(log, topic, unit["last"])
    return (held[0], held[1]) if held else None


def result(log: dict, topic: str, unit: dict) -> dict:
    held = holder(log, topic, unit)
    return parse((held[1] if held else {}).get("unit_check")) or {}


def record(slot: dict, percent: int, today: date) -> dict:
    """A set just marked, kept on the unit's last lesson."""
    old = parse(slot.get("unit_check")) or {"attempts": 0, "best": None, "passed_on": "", "last_on": ""}
    new = {"attempts": old["attempts"] + 1, "best": max(percent, old["best"] or 0),
           "passed_on": old["passed_on"] or (today.isoformat() if quiz.passed(percent) else ""),
           "last_on": today.isoformat()}
    slot["unit_check"] = new
    return new


def merge(a, b):
    """Two copies of a result (another tab or device): the further on."""
    a, b = parse(a), parse(b)
    if not a or not b:
        return a or b
    passed = sorted(x for x in (a["passed_on"], b["passed_on"]) if x)
    return {"attempts": max(a["attempts"], b["attempts"]), "best": max(a["best"] or 0, b["best"] or 0),
            "passed_on": passed[0] if passed else "", "last_on": max(a["last_on"], b["last_on"])}


def parse(data):
    """A stored result, checked (None if there isn't one)."""
    if not isinstance(data, dict) or not isinstance(data.get("attempts"), int) or data["attempts"] < 1:
        return None
    best = data.get("best")
    best = best if isinstance(best, int) and not isinstance(best, bool) and 0 <= best <= 100 else None

    def day(v):
        try:
            return v if isinstance(v, str) and date.fromisoformat(v) else ""
        except ValueError:
            return ""
    return {"attempts": min(data["attempts"], 10_000), "best": best,
            "passed_on": day(data.get("passed_on")), "last_on": day(data.get("last_on"))}


def just_finished(log: dict, topic: str, today: date):
    """The unit she finished last, if that was in the last FRESH_DAYS days and
    its check is offered and never taken (Home points to it once; older
    units wait on the course map)."""
    done = [u for u in units(log, topic) if u["state"] == "done"]
    if not done:
        return None
    u = max(done, key=lambda x: max(y["passed"] or "" for y in x["lessons"]))
    last = max(y["passed"] or "" for y in u["lessons"])
    if not last or last < (today - timedelta(days=FRESH_DAYS)).isoformat():
        return None
    return u if offered(log, topic, u) and not result(log, topic, u).get("attempts") else None
