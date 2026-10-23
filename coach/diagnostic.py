"""Where to start a goal (docs/LEARNING_DESIGN.md §4): a short adaptive
check, so she skips what she already knows.

It asks one question per unit, and each answer says more than itself, by
the units' prerequisites (knowledge space theory, Doignon & Falmagne): a
right answer means the units it builds on are known too; a wrong one, that
the units built on it aren't. The next question is on the unit that would
settle the most either way, so a whole path is placed in a few questions
(MAX_ITEMS at most; "I don't know yet" is a fine answer, and counts as a
miss). Nothing is said right or wrong as she goes: it is a starting point,
not a test (and a pretest also primes what she is about to learn).

Then: the units known are skipped (their lessons count as done), and she
starts at the first unit not known; she can also start from the beginning.
A week later, one question on a unit she skipped comes back in her warm-up
(SPOT_AFTER days): missed, that unit's lessons come back into her path.

Questions are written by the model, one per unit (on its outcomes), checked
by the same checking call as every quiz, then kept: for the math curriculum
in the shared bank (coach/itembank.py: one learner's questions serve
everyone after her, in her language), for her own goal with her record.
They are written a few at a time, for the questions the next answers could
lead to (a tree three deep: about three batches of two calls for the
mathematics curriculum the first time, none after; two calls for a goal).

Her result is kept in her preferences, prefs["diag"][topic]:
{"date", "asked": [{"unit", "right"}], "known", "unknown", "done", "skip":
[lesson numbers], "start", "items": {unit: question}, "spot": [{"unit",
"due"}], "applied"}. Pure functions; the model's request and reply are read
here, the page (views/diagnostic.py) makes the calls."""
from datetime import date, timedelta

from coach import curriculum, quiz

MAX_ITEMS = 8
DEPTH = 3                   # questions written ahead: the next one, and what each answer leads to
SPOT_AFTER = 7              # days before a skipped unit is asked about again (in the warm-up)
SPOTS = 2                   # units asked about again


# ------------------------------------------------------------------- units
def units(topic: str) -> list:
    """The path's units in order: [{"id", "name", "first", "last", "about",
    "prereq": [ids]}], or [] when there is nothing to place (one unit)."""
    lessons = curriculum._load(topic)
    out = []
    for n, (unit, title) in enumerate(lessons, start=1):
        if not out or out[-1]["name"] != unit:
            out.append({"id": unit.split(" ")[0] if topic == "math" else f"u{n}", "name": unit, "first": n,
                        "last": n, "titles": []})
        out[-1]["last"] = n
        out[-1]["titles"].append(title)
    if topic == "math":
        from coach import mathcourse
        known = mathcourse.units()
        ids = {u["id"] for u in out}
        for u in out:
            m = known.get(u["id"], {})
            u["about"] = "; ".join(m.get("learning_outcomes_en") or u["titles"])[:600]
            u["prereq"] = [p for p in m.get("prerequisites", []) if p in ids]
    else:
        for k, u in enumerate(out):
            u["about"] = "; ".join(u["titles"])[:600]
            u["prereq"] = [out[k - 1]["id"]] if k else []
    for u in out:
        u.pop("titles")
    return out if len(out) > 1 else []


def offered(topic: str) -> bool:
    """A path to place: the mathematics curriculum, or a goal of hers."""
    from coach import catalog
    return (topic == "math" or catalog.is_goal(topic)) and bool(units(topic))


def _closure(start: str, edges: dict) -> set:
    seen, todo = set(), [start]
    while todo:
        for x in edges.get(todo.pop(), ()):
            if x not in seen:
                seen.add(x)
                todo.append(x)
    return seen


def graph(us: list) -> tuple:
    """(ancestors, descendants): {id: set of ids}."""
    up = {u["id"]: set(u["prereq"]) for u in us}
    down = {u["id"]: set() for u in us}
    for u in us:
        for p in u["prereq"]:
            down[p].add(u["id"])
    return ({k: _closure(k, up) for k in up}, {k: _closure(k, down) for k in down})


# -------------------------------------------------------------- the search
def blank(today: date) -> dict:
    return {"date": today.isoformat(), "asked": [], "known": [], "unknown": [], "done": False, "skip": [],
            "start": 1, "items": {}, "spot": [], "applied": False, "bank": {}}


def _split(uid: str, open_: set, anc: dict, desc: dict) -> tuple:
    """How much one question on `uid` settles: (the smaller of what a right
    and a wrong answer would settle, the larger)."""
    right = len((anc[uid] | {uid}) & open_)
    wrong = len((desc[uid] | {uid}) & open_)
    return min(right, wrong), right + wrong


def next_unit(us: list, known: set, unknown: set, asked: int):
    """The unit to ask about next, or None when it is settled (or enough asked)."""
    if asked >= MAX_ITEMS:
        return None
    anc, desc = graph(us)
    open_ = {u["id"] for u in us} - known - unknown
    if not open_:
        return None
    order = [u["id"] for u in us if u["id"] in open_]
    return max(order, key=lambda k: (_split(k, open_, anc, desc), -abs(order.index(k) - len(order) // 2)))


def settle(us: list, known: set, unknown: set, uid: str, right: bool) -> tuple:
    anc, desc = graph(us)
    if right:
        return known | anc[uid] | {uid}, unknown - anc[uid] - {uid}
    return known - desc[uid] - {uid}, unknown | desc[uid] | {uid}


def ahead(us: list, known: set, unknown: set, asked: int, depth: int = DEPTH) -> list:
    """The units the next `depth` questions could be on, whatever she answers."""
    out = []

    def walk(k, u, n, d):
        uid = next_unit(us, k, u, n)
        if uid is None or d == 0:
            return
        if uid not in out:
            out.append(uid)
        walk(*settle(us, k, u, uid, True), n + 1, d - 1)
        walk(*settle(us, k, u, uid, False), n + 1, d - 1)
    walk(set(known), set(unknown), asked, depth)
    return out


def answer(state: dict, us: list, uid: str, right: bool) -> dict:
    known, unknown = settle(us, set(state["known"]), set(state["unknown"]), uid, right)
    order = [u["id"] for u in us]
    state["asked"].append({"unit": uid, "right": bool(right)})
    state["known"] = [k for k in order if k in known]
    state["unknown"] = [k for k in order if k in unknown]
    if next_unit(us, known, unknown, len(state["asked"])) is None:
        finish(state, us)
    return state


def finish(state: dict, us: list) -> dict:
    """Where she starts: the first unit not known; what she skips: the
    lessons of every unit known."""
    known = set(state["known"])
    first = next((u for u in us if u["id"] not in known), None)
    state["start"] = first["first"] if first else us[-1]["last"] + 1
    state["skip"] = [n for u in us if u["id"] in known for n in range(u["first"], u["last"] + 1)]
    state["done"] = True
    return state


def spot_checks(state: dict, us: list, today: date) -> dict:
    """Once she starts from her result: SPOTS skipped units to ask about again
    in a week, the ones she was asked about directly first."""
    known = [x["unit"] for x in state["asked"] if x["right"] and x["unit"] in state["known"]]
    picks = known[:SPOTS] or state["known"][:SPOTS]
    state["spot"] = [{"unit": k, "due": (today + timedelta(days=SPOT_AFTER)).isoformat()} for k in picks]
    state["applied"] = True
    return state


def due_spots(state: dict, today: date) -> list:
    return [s for s in state.get("spot") or [] if s["due"] <= today.isoformat() and s["unit"] in state["items"]]


def spot_answered(state: dict, us: list, uid: str, right: bool) -> dict:
    """A skipped unit asked about again: kept skipped, or (missed) its lessons
    come back into her path."""
    state["spot"] = [s for s in state["spot"] if s["unit"] != uid]
    if not right:
        u = next((x for x in us if x["id"] == uid), None)
        if u:
            back = set(range(u["first"], u["last"] + 1))
            state["skip"] = [n for n in state["skip"] if n not in back]
            state["known"] = [k for k in state["known"] if k != uid]
    return state


# --------------------------------------------------------------- the model
WRITER = """You write a short placement check for a learning path: ONE multiple-choice question per unit
you are given, that someone who has really learned that unit answers right and someone who hasn't
gets wrong. Test the unit's core outcome (what it says the learner can do), not a detail or a term.
Exactly 4 short options, exactly one correct; wrong options are the typical mistakes of someone who
hasn't learned it; "notes" gives, for each option in order, that mistake in a few words ("" for the
right one). No "all of the above". Correctness first: the keyed answer must be factually correct in
the real world and the only defensible option; if unsure, ask something you are sure of.
"diff" is 2. "why" is one sentence.

Reply with JSON only: {"questions": [{"unit": "the unit id as given", "type": "choice", "question": "...",
"options": ["...", "...", "...", "..."], "answer": 0, "notes": ["", "...", "...", "..."], "diff": 2,
"why": "..."}]}"""


def write_request(us: list, ids: list):
    by = {u["id"]: u for u in us}
    lines = [f"Unit {k}: {by[k]['name']}\nIts outcomes: {by[k]['about']}" for k in ids if k in by]
    return WRITER, [{"role": "user", "content": "\n\n".join(lines)}]


def read_written(data, ids: list) -> dict:
    """{unit id: question} of the usable questions the model wrote."""
    items = data.get("questions") if isinstance(data, dict) else None
    out = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or str(item.get("unit")) not in ids or str(item["unit"]) in out:
            continue
        parsed = quiz.parse_items({"questions": [dict(item, type="choice")]})
        if parsed and parsed[0]["type"] == "choice":
            q = parsed[0]
            q.pop("role", None)
            out[str(item["unit"])] = q
    return out


# -------------------------------------------------------------- saved form
def parse(data):
    if not isinstance(data, dict) or not isinstance(data.get("date"), str):
        return None
    out = {"date": data["date"][:10], "done": data.get("done") is True, "applied": data.get("applied") is True}
    asked = data.get("asked") if isinstance(data.get("asked"), list) else []
    out["asked"] = [{"unit": str(x["unit"])[:40], "right": x.get("right") is True} for x in asked[:40]
                    if isinstance(x, dict) and isinstance(x.get("unit"), str)]
    for key in ("known", "unknown"):
        v = data.get(key)
        out[key] = [str(x)[:40] for x in v[:400] if isinstance(x, str)] if isinstance(v, list) else []
    skip = data.get("skip")
    out["skip"] = sorted({n for n in skip if isinstance(n, int) and not isinstance(n, bool) and 0 < n <= 5000})[:3000] \
        if isinstance(skip, list) else []
    out["start"] = data["start"] if isinstance(data.get("start"), int) and not isinstance(data.get("start"), bool) else 1
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    out["items"] = {str(k)[:40]: q for k, q in ((k, quiz._saved_question(v)) for k, v in list(items.items())[:200]) if q}
    bank = data.get("bank") if isinstance(data.get("bank"), dict) else {}
    out["bank"] = {str(k)[:40]: v for k, v in list(bank.items())[:200] if isinstance(v, int) and not isinstance(v, bool)}
    spot = data.get("spot") if isinstance(data.get("spot"), list) else []
    out["spot"] = [{"unit": str(s["unit"])[:40], "due": str(s.get("due") or "")[:10]} for s in spot[:SPOTS * 2]
                   if isinstance(s, dict) and isinstance(s.get("unit"), str)]
    if not out["applied"]:
        out["skip"] = [] if not out["done"] else out["skip"]
    return out


def parse_all(data) -> dict:
    if not isinstance(data, dict):
        return {}
    return {str(t)[:60]: d for t, d in ((t, parse(v)) for t, v in list(data.items())[:20]) if d}


def skipping(state) -> list:
    """The lessons skipped (only once she chose to start from her result)."""
    return list(state.get("skip") or []) if state and state.get("applied") else []
