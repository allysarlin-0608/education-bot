"""Today's session as a small learning loop (docs/LEARNING_DESIGN.md §3):

1. a warm-up: recall before re-reading (retrieval practice), the cards and
   ideas closest to being forgotten (FSRS), 2-4 of them (up to 6 after a
   break), no AI; the lesson is written in the background meanwhile;
2. the lesson in short sections, each of the first two followed by a quick
   check written into the lesson itself (【Quick Check】: three options, a
   note on the mistake behind each wrong one, a hint): a wrong first answer
   gets the hint and a second try, then the answer and why (elaborated
   feedback, not just the key);
3. guided practice: a worked problem with a step or two left to her
   ("steps", the worked example fading into a problem), then a problem of
   her own ("problem"); for an idea she probably knows already, or in the
   "problem first" arm of the fading experiment, the problem comes first and
   the worked steps only after a miss (expertise reversal);
4. the mastery check (coach/quiz.py), with how sure she is of each answer;
5. once the day's first lesson is passed: mixed practice on earlier ideas
   whose basics she has (interleaving: choosing the method is the skill),
   explaining an idea in her own words (once a day), and a short reflection
   with how sure she is that she'll remember it (a judgment of learning,
   compared later with how she does).

A lesson's place in it is kept on its slot, slot["session"]:
{"stage": "learn" | "practice" | "check", "checks": {"0": {"a", "tries",
"right", "conf"}}, "guided": {"items", "answers", "marks", "tries", "conf",
"order"}, "jol": 1-3}. A lesson from before this has no "session": it is
at "check" if its quiz was started, else at "learn" (nothing is rewritten).
The warm-up and the mixed practice are the day's, in her preferences
(prefs["warmup"], prefs["mixed"]). Pure functions; no Streamlit, no AI."""
import hashlib
import random
import re
from datetime import date

from coach import learner, mastery, practice, quiz, review

STAGES = ("learn", "practice", "check")
WARMUP = 3                  # warm-up items on a usual day
WARMUP_BACK = 6             # after a break (coach/habit.returning): never a wall
MIXED = 4                   # mixed practice once the day's first lesson is passed
MIXED_FROM = 0.6            # P(L) an earlier idea needs to be mixed in: its basics are there
KNOWN = 0.7                 # P(L) at which a new idea's practice starts with the problem
TRIES = 2                   # a quick check or a practice item: a second try after the hint

# ------------------------------------------------------- the lesson's checks
CHECK_BLOCK = re.compile(r"^[ \t]*(?:#+[ \t]*)?(?:\*\*)?【\s*Quick Check\s*】(?:\*\*)?[ \t]*[:：]?[ \t]*(.*?)"
                         r"(?=^[ \t]*(?:#+[ \t]*)?(?:\*\*)?【|\Z)", re.MULTILINE | re.DOTALL)
_Q = re.compile(r"^\s*(?:\*\*)?(?:Q|Question)(?:\*\*)?\s*[:：.]\s*(.+)$", re.IGNORECASE)
_OPTION = re.compile(r"^\s*(?:[-*]\s*)?\(?([A-Da-d])[).:]\s*(.+)$")
_HINT = re.compile(r"^\s*(?:\*\*)?Hint(?:\*\*)?\s*[:：]\s*(.+)$", re.IGNORECASE)
_WHY = re.compile(r"^\s*(?:\*\*)?Why(?:\*\*)?\s*[:：]\s*(.+)$", re.IGNORECASE)
_RIGHT = re.compile(r"\s*(?:\(?\s*[✓✔]\s*\)?|\((?:correct|right)\))\s*$", re.IGNORECASE)
_NOTE = re.compile(r"\s+[—–-]+\s*[✗✘x×]\s*(.*)$")


def _one_check(text: str):
    """One quick check from its block, or None if it can't be read whole."""
    question, options, answer, notes, hint, why = "", [], None, [], "", ""
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        if m := _Q.match(line):
            question = m.group(1).strip()
        elif m := _HINT.match(line):
            hint = m.group(1).strip()
        elif m := _WHY.match(line):
            why = m.group(1).strip()
        elif m := _OPTION.match(line):
            body, note = m.group(2), ""
            if n := _NOTE.search(body):
                body, note = body[:n.start()], n.group(1).strip()
            if _RIGHT.search(body):
                body = _RIGHT.sub("", body)
                answer = len(options)
            options.append(body.strip().strip("*").strip())
            notes.append(note)
        elif not question:
            question = line.strip().strip("*").strip()
    if not question or not 3 <= len(options) <= 4 or answer is None or not all(options) \
            or len({o.casefold() for o in options}) != len(options):
        return None
    notes[answer] = ""
    return {"type": "choice", "question": question, "options": options, "answer": answer, "notes": notes,
            "hint": hint, "why": why}


def quick_checks(lesson: str) -> list:
    """The lesson's quick checks, in order (the ones that can be read)."""
    return [c for c in (_one_check(m.group(1)) for m in CHECK_BLOCK.finditer(lesson or "")) if c]


def without_checks(lesson: str) -> list:
    """The lesson cut where its quick checks are: [text, check index or
    None, text, ...] as ("text", str) and ("check", k) parts, in order."""
    parts, pos, k = [], 0, 0
    for m in CHECK_BLOCK.finditer(lesson or ""):
        if lesson[pos:m.start()].strip():
            parts.append(("text", lesson[pos:m.start()]))
        if _one_check(m.group(1)):
            parts.append(("check", k))
            k += 1
        pos = m.end()
    if (lesson or "")[pos:].strip():
        parts.append(("text", lesson[pos:]))
    return parts


def strip_checks(lesson: str) -> str:
    """The lesson without its quick checks (to read it again)."""
    return "".join(part for kind, part in without_checks(lesson) if kind == "text")


def note_for(check: dict, answer) -> str:
    """The mistake behind a wrong option (the lesson's own words for it)."""
    if answer is None or answer == check["answer"]:
        return ""
    return (check.get("notes") or [""] * len(check["options"]))[answer]


# ------------------------------------------------------------ a lesson's stage
def blank() -> dict:
    return {"stage": "learn", "checks": {}, "guided": None}


def of(slot: dict) -> dict:
    """The lesson's place in the loop; worked out for one from before."""
    s = slot.get("session")
    if s:
        return s
    # a quiz written means she had asked for it (the old "Take the quiz"): she was at the check
    started = bool(slot.get("quiz")) or slot.get("completed")
    return dict(blank(), stage="check" if started else "learn")


def stage(slot: dict) -> str:
    return of(slot)["stage"]


def keep(slot: dict) -> dict:
    """Before changing a lesson's place in the loop: store it."""
    if "session" not in slot:
        slot["session"] = of(slot)
    return slot["session"]


def move(slot: dict, to: str) -> None:
    """On to a later stage (or back to the lesson to read it again, which
    never undoes what she has done)."""
    keep(slot)["stage"] = to


def answer_check(slot: dict, k: int, answer: int, right: bool, conf=None) -> dict:
    """Her answer to quick check k (a second try after the hint at most)."""
    c = keep(slot)["checks"].setdefault(str(k), {"a": None, "tries": 0, "right": False, "conf": None})
    if c["right"] or c["tries"] >= TRIES:
        return c
    c.update(a=answer, tries=c["tries"] + 1, right=right)
    if c["tries"] == 1:
        c["conf"] = learner.confidence(conf)
    return c


def checks_done(slot: dict, count: int) -> bool:
    checks = of(slot)["checks"]
    return all((checks.get(str(k)) or {}).get("right") or (checks.get(str(k)) or {}).get("tries", 0) >= TRIES
               for k in range(count))


# --------------------------------------------------------- guided practice
def guided_order(items: list, problem_first: bool) -> list:
    """The worked problem then the problem of her own, or the problem first
    (an idea she probably knows: the worked steps only after a miss)."""
    steps = [q for q in items if q["type"] == "steps"]
    rest = [q for q in items if q["type"] != "steps"]
    return rest + steps if problem_first else steps + rest


def new_guided(items: list, problem_first: bool) -> dict:
    ordered = guided_order(items, problem_first)
    n = len(ordered)
    return {"items": ordered, "answers": [None] * n, "marks": [None] * n, "tries": [0] * n, "conf": [None] * n,
            "order": "problem_first" if problem_first else "faded"}


def answer_guided(g: dict, k: int, answer, conf=None) -> float:
    """Mark item k (a second try after the hint); returns its mark."""
    if g["marks"][k] == 1 or g["tries"][k] >= TRIES:
        return g["marks"][k]
    mark = quiz.mark(g["items"][k], answer)
    g["answers"][k], g["marks"][k] = answer, mark
    g["tries"][k] += 1
    if g["tries"][k] == 1:
        g["conf"][k] = learner.confidence(conf)
    return mark


def guided_left(g: dict) -> list:
    """The items still to do, in order (the page shows the first). In
    "problem first", the worked problem is dropped once she got the problem
    right at the first try: she didn't need the steps."""
    def done(k):
        return g["marks"][k] == 1 or g["tries"][k] >= TRIES
    out = [k for k in range(len(g["items"])) if not done(k)]
    problem = next((k for k, x in enumerate(g["items"]) if x["type"] != "steps"), None)
    if g["order"] == "problem_first" and problem is not None and g["tries"][problem] == 1 and g["marks"][problem] == 1:
        out = [k for k in out if g["items"][k]["type"] != "steps"]
    return out


def parse_guided(data):
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return None
    items = [quiz._saved_question(x) for x in data["items"][:4]]
    if None in items:
        return None                  # (no items is kept: "no practice this time", never asked for again)
    n = len(items)

    def same(key, default):
        v = data.get(key)
        return list(v) if isinstance(v, list) and len(v) == n else [default] * n
    marks = [m if isinstance(m, (int, float)) and not isinstance(m, bool) else None for m in same("marks", None)]
    tries = [t if isinstance(t, int) and not isinstance(t, bool) and 0 <= t <= TRIES else 0 for t in same("tries", 0)]
    return {"items": items, "answers": same("answers", None), "marks": marks, "tries": tries,
            "conf": [learner.confidence(c) for c in same("conf", None)],
            "order": data.get("order") if data.get("order") in ("faded", "problem_first") else "faded"}


def parse(data):
    """A saved session (database or backup), checked, or None."""
    if not isinstance(data, dict) or data.get("stage") not in STAGES:
        return None
    checks = {}
    for k, c in (data.get("checks") or {}).items() if isinstance(data.get("checks"), dict) else ():
        if str(k).isdigit() and isinstance(c, dict):
            tries = c.get("tries") if isinstance(c.get("tries"), int) and not isinstance(c.get("tries"), bool) else 0
            a = c.get("a") if isinstance(c.get("a"), int) and not isinstance(c.get("a"), bool) else None
            checks[str(k)] = {"a": a, "tries": max(0, min(TRIES, tries)), "right": c.get("right") is True,
                              "conf": learner.confidence(c.get("conf"))}
    out = {"stage": data["stage"], "checks": checks, "guided": parse_guided(data.get("guided"))}
    if learner.confidence(data.get("jol")):
        out["jol"] = data["jol"]
    return out


def merge(a, b):
    """Two copies of a lesson's session (two tabs): the one further on, with
    every quick check either answered."""
    if not a or not b:
        return a or b
    order = STAGES.index
    far, near = (a, b) if order(a["stage"]) >= order(b["stage"]) else (b, a)
    out = dict(far, checks={**near["checks"], **far["checks"]})
    if not out.get("guided") and near.get("guided"):
        out["guided"] = near["guided"]
    if "jol" not in out and "jol" in near:
        out["jol"] = near["jol"]
    return out


# --------------------------------------------- the warm-up and mixed practice
def item_id(q: dict) -> str:
    return practice.qid(q)


def warmup(log: dict, today: date, size: int, avoid=()) -> list:
    """What to recall first today: her due review cards, the closest to being
    forgotten first (an error she was sure of before anything), then
    exercises on the ideas she knows least. [{"src": "card", "id"} |
    {"src": "bank", "topic", "n", "q"}]."""
    out = [{"src": "card", "id": c["id"]} for _, _, c in review.due(log, today)[:size] if c["id"] not in avoid]
    if len(out) < size:
        for topic, n, idea in mastery.weakest(log, today, limit=size):
            held = mastery.holder(log, topic, n)
            if held is None or len(out) >= size:
                continue
            mine = [q for q in practice.sources(held[1], topic) if item_id(q) not in avoid]
            if mine:
                rng = random.Random(f"{today.isoformat()}|warm|{topic}|{n}")
                out.append({"src": "bank", "topic": topic, "n": n, "q": rng.choice(mine)})
    return out[:size]


def mixed(log: dict, today: date, exclude: tuple, interleaved: bool, size: int = MIXED, avoid=()) -> list:
    """A mixed set on earlier ideas whose basics she has (P(L) at least
    MIXED_FROM), of different kinds, the ones fading first: in turn (A, B, C)
    when interleaved, else one idea's items together (the "blocked" arm).
    `exclude`: (topic, n) of today's lessons. [{"topic", "n", "q"}]."""
    pool = []
    for t in mastery.topics(log):
        for x in mastery.ideas(log, t, today):
            if x["evidence"] and (t, x["n"]) not in exclude and x["strength"] >= MIXED_FROM:
                pool.append((t, x))
    pool.sort(key=lambda y: (y[1]["recall"], y[1]["last"] or ""))
    per = []
    for t, x in pool[:3]:
        held = mastery.holder(log, t, x["n"])
        if held is None:
            continue
        rng = random.Random(f"{today.isoformat()}|mixed|{t}|{x['n']}")
        mine = [q for q in practice.sources(held[1], t) if item_id(q) not in avoid]
        rng.shuffle(mine)
        kinds, picked = set(), []
        for q in mine:                       # different kinds within an idea: the method has to be chosen
            if q["type"] not in kinds and len(picked) < 2:
                kinds.add(q["type"])
                picked.append({"topic": t, "n": x["n"], "q": q})
        if picked:
            per.append(picked)
    items = []
    if interleaved:
        while any(per) and len(items) < size:
            for group in per:
                if group and len(items) < size:
                    items.append(group.pop(0))
    else:
        for group in per:
            items += group[:max(0, size - len(items))]
    return items


def parse_set(data):
    """A saved warm-up or mixed set (prefs), checked, or None."""
    if not isinstance(data, dict) or not isinstance(data.get("date"), str) or not isinstance(data.get("items"), list):
        return None
    items = []
    for x in data["items"][:8]:
        if not isinstance(x, dict):
            return None
        if x.get("src") == "card" and isinstance(x.get("id"), str):
            items.append({"src": "card", "id": x["id"][:20]})
            continue
        q = quiz._saved_question(x.get("q"))
        if q is None or not isinstance(x.get("topic"), str) or not isinstance(x.get("n"), int):
            return None
        items.append({"src": "bank", "topic": x["topic"], "n": x["n"], "q": q})
        if isinstance(x.get("spot"), str):
            items[-1]["spot"] = x["spot"][:40]      # (a skipped unit asked about again: coach/diagnostic.py)
    n = len(items)
    marks = data.get("marks") if isinstance(data.get("marks"), list) and len(data["marks"]) == n else [None] * n
    conf = data.get("conf") if isinstance(data.get("conf"), list) and len(data["conf"]) == n else [None] * n
    return {"date": data["date"][:10], "items": items,
            "marks": [m if isinstance(m, (int, float)) and not isinstance(m, bool) else None for m in marks],
            "conf": [learner.confidence(c) for c in conf], "done": data.get("done") is True,
            "skipped": data.get("skipped") is True,
            "arm": data.get("arm") if data.get("arm") in ("mixed", "blocked") else ""}


def new_set(today: date, items: list, arm: str = "") -> dict:
    n = len(items)
    return {"date": today.isoformat(), "items": items, "marks": [None] * n, "conf": [None] * n,
            "done": n == 0, "skipped": False, "arm": arm}


def set_left(s: dict) -> list:
    return [k for k, m in enumerate(s["marks"]) if m is None]


def seed(*parts) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)
