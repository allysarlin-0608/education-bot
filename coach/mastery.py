"""What she really knows: each lesson's idea, and how well she knows it.

An idea is one lesson of a subject or goal (the syllabus already makes each
lesson one idea: "Deductive reasoning", "The dichotomy of control"); a unit
groups them. How well she knows it comes from evidence, never from a lesson
being finished:

- "quiz":     the lesson's quiz (its score)
- "recall":   a question on it asked again later in another lesson's quiz
- "review":   a review card from the lesson, answered
- "practice": an exercise on it in Practice
- "explain":  explaining it in her own words (marked by the coach)
- "ask":      a question to the coach that showed she was confused

Each piece of evidence is {"id", "d" (date), "k" (kind), "s" (0..1)},
kept on the lesson's own slot (slot["ev"]), so it is saved, merged
(curriculum.merge_day) and backed up with the lesson. A lesson from before
this existed has its evidence worked out from its quiz and review cards
(derived()), and stored once something new is added (seed()).

From the evidence, in date order:
- strength moves toward each score (newer evidence counts more);
- stability: how long it lasts. It grows with each success on a new day
  (spaced retrieval) and halves after a failure;
- recall now = strength x retention(days since the last evidence), a
  forgetting curve that keeps 90% after `stability` days: an idea not
  practised fades (a solid one in about two weeks, a mastered one in a
  month or more), and practising it brings it back.

Levels: new (no evidence), learning, solid (recall >= SOLID, two
successes on different days), mastered (recall >= MASTERED, three successes
spread over at least MASTERED_SPAN days). One quiz is never "solid": it has to hold
on another day. Pure functions; no AI call."""
import hashlib
from datetime import date, timedelta

from coach import catalog, course, curriculum

LEVELS = ("new", "learning", "solid", "mastered")
LEVEL_NAMES = {"new": "New", "learning": "Learning", "solid": "Solid", "mastered": "Mastered"}
KINDS = ("quiz", "recall", "review", "practice", "explain", "ask")
WEIGHT = {"quiz": 1.0, "recall": 0.8, "review": 0.6, "practice": 0.8, "explain": 1.0, "ask": 0.5}
ALPHA = 0.55              # how far one piece of evidence moves strength (x its weight)
SUCCESS, FAILURE = 0.8, 0.5
STABILITY0 = 3.0          # days an idea lasts after its first success
GROWTH = 2.2              # each spaced success makes it last this much longer
MAX_STABILITY = 180.0
SOLID, MASTERED = 0.6, 0.85
MASTERED_SPAN = 7         # days between the first and last of the successes
MAX_EVENTS = 40           # evidence kept per idea (the oldest go first)
HELD_AFTER = 14           # days: an idea still known this long after its last practice "held"


def _id(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def event(kind: str, score: float, day: date, source: str = "") -> dict:
    return {"id": _id(kind, day.isoformat(), source), "d": day.isoformat(), "k": kind,
            "s": round(min(1.0, max(0.0, float(score))), 2)}


# ----------------------------------------------------------- the evidence
def derived(slot: dict, entry_date: str) -> list:
    """Evidence for a lesson from before mastery was tracked: its best quiz
    score (on the day it was passed, or written), and its review cards as
    they stand (one piece: the share known, on the last day reviewed)."""
    out = []
    q = slot.get("quiz") or {}
    passed = slot.get("completed") or slot.get("passed_on")
    best = q.get("best") if q.get("best") is not None else q.get("score")
    if best is not None and (passed or q.get("answers") is not None):
        day = date.fromisoformat(slot.get("passed_on") or entry_date)
        out.append(event("quiz", best / 100, day, "legacy"))
    elif passed:
        out.append(event("quiz", 0.8, date.fromisoformat(slot.get("passed_on") or entry_date), "legacy"))
    seen = [c for c in slot.get("cards") or [] if c.get("reviews") and c.get("last")]
    if seen:
        known = sum(1 for c in seen if c.get("box", 0) > 0) / len(seen)
        out.append(event("review", known, date.fromisoformat(max(c["last"] for c in seen)), "legacy"))
    return sorted(out, key=lambda e: e["d"])


def evidence(slot: dict, entry_date: str) -> list:
    return list(slot["ev"]) if "ev" in slot else derived(slot, entry_date)


def seed(slot: dict, entry_date: str) -> None:
    """Before adding to a lesson from before mastery: store what it had."""
    if "ev" not in slot:
        slot["ev"] = derived(slot, entry_date)


def add(slot: dict, entry_date: str, kind: str, score: float, day: date, source: str = "") -> list:
    """Add one piece of evidence (once: the same source on the same day is
    one piece). Returns what it showed for the numbers (signals())."""
    seed(slot, entry_date)
    before = list(slot["ev"])
    e = event(kind, score, day, source)
    if any(x["id"] == e["id"] for x in before):
        return []
    slot["ev"] = sorted(before + [e], key=lambda x: x["d"])[-MAX_EVENTS:]
    return signals(before, e)


def merge(a: list, b: list) -> list:
    """Two copies of a lesson's evidence (two tabs): every piece of both."""
    seen, out = set(), []
    for e in sorted((a or []) + (b or []), key=lambda x: (x["d"], x["id"])):
        if e["id"] not in seen:
            seen.add(e["id"])
            out.append(e)
    return out[-MAX_EVENTS:]


def parse(data) -> list:
    """Validate saved evidence (from the database or a backup)."""
    out = []
    for e in data if isinstance(data, list) else []:
        if not isinstance(e, dict) or e.get("k") not in KINDS or not isinstance(e.get("s"), (int, float)):
            continue
        try:
            date.fromisoformat(e.get("d") or "")
        except (TypeError, ValueError):
            continue
        out.append({"id": str(e.get("id") or _id(e["k"], e["d"], len(out))), "d": e["d"], "k": e["k"],
                    "s": round(min(1.0, max(0.0, float(e["s"]))), 2)})
    return sorted(out, key=lambda x: x["d"])[-MAX_EVENTS:]


# -------------------------------------------------------------- the state
def retention(gap: int, stability: float) -> float:
    """How much of it is still there `gap` days after the last practice: a
    forgetting curve (falls fast at first, then slowly), 0.9 after
    `stability` days."""
    return 1 / (1 + gap / (9 * stability))


def _daily(events: list) -> list:
    """A day's evidence of one kind as one piece (its mean): ten review cards
    of one lesson on one day are one day's review, not ten."""
    groups = {}
    for e in events:
        groups.setdefault((e["d"], e["k"]), []).append(e["s"])
    return [{"d": d, "k": k, "s": sum(v) / len(v)} for (d, k), v in sorted(groups.items())]


def state(events: list, today: date) -> dict:
    """How well she knows an idea today, from its evidence. It climbs at
    most one level a day (never from learning to mastered in one sitting)."""
    s = _state(events, today)
    if s["last"]:
        before = [e for e in events if e["d"] < s["last"]]
        prev = _state(before, date.fromisoformat(s["last"]))["level"] if before else "new"
        cap = LEVELS[min(LEVELS.index(prev) + 1, len(LEVELS) - 1)]
        if LEVELS.index(s["level"]) > LEVELS.index(cap):
            s = dict(s, level=cap, fading=False)
    return s


def _state(events: list, today: date) -> dict:
    strength, stability, successes, last_success, first_success = 0.0, STABILITY0, 0, None, None
    last = None
    for e in _daily(events):
        day = date.fromisoformat(e["d"])
        if day > today:
            continue
        strength += ALPHA * WEIGHT[e["k"]] * (e["s"] - strength)
        if e["s"] >= SUCCESS and (last_success is None or day > last_success):
            successes += 1
            if successes > 1:
                stability = min(stability * GROWTH, MAX_STABILITY)
            last_success, first_success = day, first_success or day
        elif e["s"] < FAILURE and e["k"] != "ask":
            stability = max(STABILITY0, stability / 2)
        last = day
    if last is None:
        return {"level": "new", "recall": 0.0, "strength": 0.0, "fading": False, "last": None,
                "successes": 0, "stability": stability, "evidence": 0}
    gap = (today - last).days
    recall = strength * retention(gap, stability)
    span = (last_success - first_success).days if last_success else 0

    def level(r):
        if r >= MASTERED and successes >= 3 and span >= MASTERED_SPAN:
            return "mastered"
        if r >= SOLID and successes >= 2:
            return "solid"
        return "learning"
    now, fresh = level(recall), level(strength)
    return {"level": now, "recall": round(recall, 3), "strength": round(strength, 3),
            "fading": LEVELS.index(now) < LEVELS.index(fresh), "last": last.isoformat(),
            "successes": successes, "stability": round(stability, 1), "evidence": len(events)}


def signals(before: list, new: dict) -> list:
    """What one new piece of evidence shows, for the numbers (coach/metrics.py):
    - "missed": wrong about an idea she had right last time (or never had);
    - "recovered": right now (on a later day) about an idea she had got wrong
      (its first success since that miss);
    - "held" / "slipped": an idea that was solid or mastered, asked again
      HELD_AFTER days or more after its last practice: still known, or not;
    - "mastered": the idea has just become mastered."""
    out = []
    day = date.fromisoformat(new["d"])
    if new["k"] == "ask":
        return out
    graded = [e for e in before if e["k"] != "ask"]
    if new["s"] < FAILURE and (not graded or graded[-1]["s"] >= FAILURE):
        out.append("missed")
    earlier = [e for e in graded if e["d"] < new["d"]]
    misses = [e for e in earlier if e["s"] < FAILURE]
    if new["s"] >= SUCCESS and misses:
        after_miss = [e for e in earlier if e["d"] > max(m["d"] for m in misses) and e["s"] >= SUCCESS]
        if not after_miss:
            out.append("recovered")
    if earlier:
        last = date.fromisoformat(max(e["d"] for e in earlier))
        if (day - last).days >= HELD_AFTER:
            was = state(earlier, last)["level"]       # as it stood when last practised
            if was in ("solid", "mastered"):
                if new["s"] >= SUCCESS:
                    out.append("held")
                elif new["s"] < FAILURE:
                    out.append("slipped")
    if state(before + [new], day)["level"] == "mastered" and state(before, day)["level"] != "mastered":
        out.append("mastered")
    return out


# ------------------------------------------------------------- the ideas
def holder(log: dict, topic: str, n: int):
    """(entry, slot) holding lesson n's content (where its evidence lives), or None."""
    r = course.lesson_record(log, topic, n)
    return (r[0], r[1]) if r else None


def ideas(log: dict, topic: str, today: date) -> list:
    """Every idea of a subject or goal, in syllabus order:
    {n, title, unit, level, recall, fading, last, successes, evidence, reached}."""
    records = course._records(log, topic)
    out = []
    for n, (unit, title) in enumerate(curriculum._load(topic), start=1):
        r = records.get(n) or {}
        slot, entry = r.get("slot"), r.get("entry")
        s = state(evidence(slot, entry["date"]), today) if slot is not None else state([], today)
        out.append({"n": n, "title": title, "unit": unit, "reached": slot is not None,
                    "passed": bool(r.get("passed")), "practised": practised_today(slot or {}, today), **s})
    return out


def counts(items: list) -> dict:
    return {lv: sum(1 for x in items if x["level"] == lv) for lv in LEVELS}


def units(items: list) -> list:
    """The ideas grouped by unit: [{name, ideas, counts}], in order."""
    out = []
    for x in items:
        if not out or out[-1]["name"] != x["unit"]:
            out.append({"name": x["unit"], "ideas": []})
        out[-1]["ideas"].append(x)
    for u in out:
        u["counts"] = counts(u["ideas"])
        u["reached"] = any(x["reached"] for x in u["ideas"])
    return out


def topics(log: dict) -> list:
    """Her subjects and goals with at least one lesson written."""
    seen = []
    for e in sorted(log["entries"], key=lambda x: x["date"]):
        t = e["topic"]
        if t != "reading" and t not in seen and catalog.known(t) and curriculum.has_syllabus(t) \
                and any(s.get("lesson") for s in e.get("lessons") or []):
            seen.append(t)
    return seen


def overview(log: dict, today: date) -> dict:
    """Across everything: {topic: counts} and the totals (only ideas reached)."""
    per = {}
    for t in topics(log):
        per[t] = counts([x for x in ideas(log, t, today) if x["reached"]])
    total = {lv: sum(c[lv] for c in per.values()) for lv in LEVELS}
    return {"topics": per, "total": total}


def practised_today(slot: dict, today: date) -> int:
    return sum(1 for e in slot.get("ev") or [] if e["d"] == today.isoformat() and e["k"] == "practice")


def weakest(log: dict, today: date, limit: int = 3, topic: str = None, before: int = None) -> list:
    """The ideas most in need of practice, weakest first: [(topic, n, idea)].
    Only ideas she has met (with evidence), not mastered, not practised
    twice today already (never a loop on one idea). `before`: only lessons
    before this number (earlier ideas, for the lesson and quiz of `topic`)."""
    out = []
    for t in [topic] if topic else topics(log):
        for x in ideas(log, t, today):
            if not x["evidence"] or x["level"] == "mastered" or (before is not None and x["n"] >= before):
                continue
            if x["practised"] >= 2:
                continue
            out.append((t, x["n"], x))
    # the shakiest first; among equals the one longest unpractised
    out.sort(key=lambda y: (LEVELS.index(y[2]["level"]) - (0.5 if y[2]["fading"] else 0), y[2]["recall"],
                            y[2]["last"] or ""))
    return out[:limit]


def needs_practice(log: dict, today: date) -> list:
    """Ideas worth a Practice today: learning or fading ones."""
    return [w for w in weakest(log, today, limit=50) if w[2]["level"] == "learning" or w[2]["fading"]]


def changes(log: dict, start: date, end: date) -> dict:
    """Between two days: ideas that went up a level, and ideas newly mastered."""
    up, mastered = 0, 0
    for t in topics(log):
        records = course._records(log, t)
        for n, r in records.items():
            if r.get("slot") is None:
                continue
            ev = evidence(r["slot"], r["entry"]["date"])
            a = state([e for e in ev if e["d"] < start.isoformat()], start - timedelta(days=1))["level"]
            b = state([e for e in ev if e["d"] <= end.isoformat()], end)["level"]
            if LEVELS.index(b) > LEVELS.index(a):
                up += 1
                mastered += b == "mastered"
    return {"up": up, "mastered": mastered}


def describe(x: dict) -> str:
    """One calm line about an idea's state, for the skill map."""
    if x["level"] == "new":
        return "Not started yet" if not x["reached"] else "No quiz or practice yet"
    if x["fading"]:
        return "Fading: a little practice brings it back"
    return {"learning": "Getting there: practise it on another day to make it stick",
            "solid": "Solid: it held on another day",
            "mastered": "Mastered: known again and again over time"}[x["level"]]
