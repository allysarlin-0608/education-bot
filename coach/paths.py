"""A learner's own goal, and the path the AI designs for it.

She says what she wants to learn, why, where she is now and how much time
she has. One AI call (design()) turns that into a path: what she will be able
to do at the end, a few units, and the lesson titles in each. Only the
outline is written now; each lesson is written when she reaches it, as for
the built-in subjects. The path is hers to adjust before she starts
(lighter, skip what she knows, reorder, remove), without another AI call.

A goal the AI can't turn into a good path comes back as one of:
- "clarify": too vague to plan ("learn business"): a question or two, and
  well-shaped goals she can pick instead;
- "narrow": too big for a few weeks ("become a doctor"): first steps that are;
- "decline": not something to learn here (harm, a diagnosis or legal advice
  for her own case, picks of what to buy, cheating), kindly, with an
  educational alternative.

Pure functions: no Streamlit, no storage; the pages and coach/storage.py use
them."""
import re
import secrets

from coach import clock

LEVELS = ("Beginner", "Intermediate", "Advanced")
STATUSES = ("active", "archived", "removed")     # archived: paused; removed: off her list (its lessons stay in her record)
MIN_UNITS, MAX_UNITS = 2, 8
MIN_LESSONS, MAX_LESSONS = 2, 8          # in a unit
MAX_TOTAL = 48
MIN_DESIGNED = 4                          # lessons the AI must give; she may then take it down to one
TITLE_LIMIT, NAME_LIMIT, LESSON_LIMIT, TEXT_LIMIT = 60, 80, 110, 400
OBJECTIVE_LIMIT = 140         # a lesson's objective: one checkable action
GOAL_MIN_CHARS, GOAL_MAX_CHARS = 3, 300
DESIGN_ATTEMPTS = 2                       # AI calls one new goal may use (a vague goal gets one more after its answer)

# where she is now, in her words → the level the path starts at
STARTS = {
    "new": ("I'm new to this", "Beginner"),
    "some": ("I know the basics", "Intermediate"),
    "solid": ("I know it well and want depth", "Advanced"),
}

# how long a path is, by her daily pace (settings.PACES: lessons a day):
# about four weeks of her turns, sized to what she has time for
LENGTH = {1: (10, 16), 3: (18, 30), 5: (24, 40)}

# goals to start from, for the three kinds of learner GNOSIS is for first
SUGGESTIONS = {
    "Work and money": [
        "Read a company's financial statements with confidence",
        "Understand how investing works before I put money in",
        "Run better meetings and give clear feedback",
        "Plan and price a small side business",
    ],
    "Curiosity": [
        "Look at a painting and understand what I'm seeing",
        "Know the night sky well enough to find planets myself",
        "Understand the big ideas of Stoic philosophy and use them",
        "Learn the history and culture of Japan before a trip",
    ],
    "Study": [
        "Understand statistics well enough for my university course",
        "Write a clear, well-argued essay",
        "Get the basics of macroeconomics for my exam",
        "Learn how to study: memory, focus and planning",
    ],
}

VAGUE = {"business", "history", "science", "art", "money", "finance", "investing", "english", "math", "maths",
         "physics", "chemistry", "biology", "coding", "programming", "psychology", "philosophy", "economics",
         "marketing", "design", "music", "language", "languages", "everything", "anything", "stuff", "learning",
         "something", "life", "health", "cooking", "writing", "photography"}


def new_id() -> str:
    return "g-" + secrets.token_hex(4)


def now_iso() -> str:
    return clock.now_iso()


def _text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


# ------------------------------------------------------------------- her goal
def precheck(goal: str):
    """A quick look before any AI call: None when the goal can go to the
    designer, else a short, kind reason and what to try (no cost to her
    daily allowance)."""
    text = _text(goal, 2000)
    # a Chinese, Japanese or Korean character says about as much as a short word:
    # 我想學吉他 is a whole goal in five characters (it was "too short" when counted as letters)
    dense = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]", text))
    if len(text) + 2 * dense < GOAL_MIN_CHARS:
        return "Tell us a little more: what would you like to be able to do?"
    if len(text) > GOAL_MAX_CHARS:
        return f"That's a lot to plan at once. Try one goal in a sentence or two (under {GOAL_MAX_CHARS} characters)."
    # (a field in a word or two, "history", is planned too: an outline of the
    # whole, from which she keeps the parts she wants: the setup's scope step)
    return None


# ---------------------------------------------------- a goal she already has
# words that don't tell two goals apart ("Basics of Investing for Beginners" is
# "Investing Basics for Beginners")
_FILLER = {"a", "an", "the", "of", "for", "to", "and", "in", "on", "with", "my", "me", "i", "want", "learn", "learning",
           "about", "how", "what", "basics", "basic", "intro", "introduction", "beginner", "beginners", "understand",
           "understanding", "get", "good", "at", "better", "some", "more", "be", "able", "is", "are", "it", "its",
           "fundamentals", "essentials", "guide", "course", "101", "start", "starting", "know", "into"}


def _words(text: str) -> set:
    out = set()
    for w in re.findall(r"[^\W_]+", str(text or "").casefold()):
        if w in _FILLER or len(w) < 2 and not w.isdigit() or re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", w):
            continue                         # (CJK is compared by pairs of characters, below)
        if len(w) > 4 and w.endswith("ing"):
            w = w[:-3]                       # investing ~ invest
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]                       # statements ~ statement
        out.add(w)
    dense = re.sub(r"[^\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", "", str(text or ""))
    out |= {dense[k:k + 2] for k in range(len(dense) - 1)}       # (CJK: pairs of characters)
    return out


def similar(a: str, b: str) -> bool:
    """Two goals that are the same thing in other words (or other order)."""
    x, y = _words(a), _words(b)
    if not x or not y:
        return False
    if x == y:
        return True
    small, big = sorted((x, y), key=len)
    # the same words, or nearly; or the whole of one inside the other ("History of Japan"
    # in "History of Japan before a trip"): an offer to continue it, never a refusal
    return len(small) >= 2 and (small <= big or len(small & big) / len(small | big) >= 0.75)


def similar_goal(text: str, goals: list, title: str = ""):
    """One of her goals (on her list) that this one repeats: by what she wrote
    or by the designed title; None when it is new."""
    for g in goals:
        if any(similar(mine, theirs) for mine in (text, title) if mine
               for theirs in (g.get("title"), g.get("goal")) if theirs):
            return g
    return None


# ----------------------------------------------------------- asking the AI
DESIGN_SYSTEM = """You design short, structured learning paths for adults who learn a little every day.
Reply with ONE JSON object and nothing else.

Read the learner's goal, why it matters to them, where they are now, and how many lessons a day they have.
The goal may be written in any language; write everything you reply in English (the app's language).

First decide the status:
- "ok": a clear goal that can be learned in about four weeks of short daily lessons.
- A whole field named in a word or two ("history", "physics", "investing") is "ok": design an overview of the
  field, its main parts as units, from the foundations; the learner then keeps the parts they want.
- "clarify": only when you can't tell what it is about at all (e.g. "stuff I need"). Ask 1-2 short questions and
  give 3 well-shaped goals they could pick instead.
- "narrow": a whole career or degree (e.g. "become a doctor"). Explain kindly in one sentence and give 3
  first-step goals that fit a few weeks.
- "decline": not something to teach here: instructions that could cause harm; a diagnosis, treatment plan or legal advice for the learner's own situation; which stocks or coins to buy; cheating on tests; hateful or sexual content; topics where accuracy can't be ensured (events after 2024, rules that change by region without a source). Explain kindly in one sentence, and give 3 educational alternatives (e.g. "how blood pressure works" instead of "treat my blood pressure").

For "ok", design the path:
- "title": a short name for the path (max 6 words, no quotes).
- "outcome": one sentence starting "By the end you will be able to" - concrete and checkable.
- "units": {units_min}-{units_max} units in a sensible order; each has "name" (max 6 words) and "lessons": {lessons_min}-{lessons_max} lessons.
- Each lesson is {{"title": "...", "objective": "..."}}. The objective is what the learner can do after that one
  lesson, as one checkable action starting with a verb (max 14 words): "Explain why an index fund's costs are low",
  not "Understand index funds".
- Total lessons: {total_min}-{total_max}. Each lesson title names ONE idea or skill a 10-minute lesson can teach, in plain words (max 10 words), building on the ones before. No duplicates, no "Introduction"/"Conclusion"/"Review" lessons, no exam or quiz lessons.
- Only well-established knowledge; nothing that depends on recent news.
- Fit where they are now. For someone new, start with the way beginners really start: the simplest
  tools and shortcuts people use today (e.g. a tuner app before tuning by ear, a phrasebook phrase
  before grammar tables, an index fund before stock picking). Skills that take months of practice
  (by ear, from memory, at speed) come late or not at all; every lesson can be done by a beginner
  after the lessons before it. For someone with experience, skip what they already know.
- Units go from foundations to what builds on them; a later unit must not be needed for an earlier one.

JSON shape:
{{"status": "ok|clarify|narrow|decline", "message": "one kind sentence (for clarify/narrow/decline)",
  "questions": ["..."], "suggestions": ["..."],
  "title": "...", "outcome": "...",
  "units": [{{"name": "...", "lessons": [{{"title": "...", "objective": "..."}}]}}]}}"""


def design_messages(goal: dict, pace: int) -> tuple:
    """(system, messages) for the one call that designs a path."""
    lo, hi = LENGTH.get(pace, LENGTH[3])
    system = DESIGN_SYSTEM.format(units_min=3, units_max=6, lessons_min=3, lessons_max=6,
                                  total_min=lo, total_max=hi)
    start = STARTS.get(goal.get("start"), STARTS["new"])[0]
    lines = [f"Goal: {_text(goal.get('text'), GOAL_MAX_CHARS)}",
             f"Why it matters to me: {_text(goal.get('why'), TEXT_LIMIT) or '(not given)'}",
             f"Where I am now: {start}",
             f"Lessons a day: {pace} (about {pace * 8} minutes)"]
    if goal.get("answers"):
        lines.append(f"More about my goal: {_text(goal.get('answers'), TEXT_LIMIT)}")
    return system, [{"role": "user", "content": "\n".join(lines)}]


def read_design(data, goal: dict) -> dict:
    """The AI's reply, checked: {"status": "ok", "path": {...}} or
    {"status": "clarify|narrow|decline", "message", "questions", "suggestions"},
    or {"status": "error"} when it can't be used (the page offers to try
    again; nothing is saved)."""
    if not isinstance(data, dict):
        return {"status": "error"}
    status = data.get("status")
    if status in ("clarify", "narrow", "decline"):
        message = _text(data.get("message"), TEXT_LIMIT) or {
            "clarify": "Tell us a little more about what you'd like to be able to do.",
            "narrow": "That's a big goal. Here are first steps that fit a few weeks.",
            "decline": "That isn't something we can teach well here. Here is what we can help with.",
        }[status]
        return {"status": status, "message": message,
                "questions": [q for q in (_text(x, 160) for x in (data.get("questions") or [])[:2]) if q],
                "suggestions": [g for g in (_text(x, 120) for x in (data.get("suggestions") or [])[:3]) if g]}
    if status != "ok":
        return {"status": "error"}
    start = goal.get("start") if goal.get("start") in STARTS else "new"
    path = parse_path({"id": new_id(), "title": data.get("title"), "outcome": data.get("outcome"),
                       "level": STARTS[start][1], "units": data.get("units"),       # (where she said she is)
                       "goal": goal.get("text"), "why": goal.get("why"), "start": goal.get("start"),
                       "status": "active", "created_at": now_iso(), "updated_at": now_iso()})
    if path is None or lesson_count(path) < MIN_DESIGNED:      # (too thin to be a path worth starting)
        return {"status": "error"}
    return {"status": "ok", "path": path}


# ------------------------------------------------------------ a stored path
def parse_path(data):
    """A path from the AI, storage or a backup, checked and trimmed to its
    limits; None when it can't be used (no title, too few lessons...)."""
    if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not re.match(r"^g-[0-9a-f]{8}$", data["id"]):
        return None
    title = _text(data.get("title"), TITLE_LIMIT).strip("\"'“”")
    outcome = _text(data.get("outcome"), TEXT_LIMIT)
    if not title or not outcome:
        return None
    units, seen, total = [], set(), 0
    for u in data.get("units") or []:
        if not isinstance(u, dict) or len(units) >= MAX_UNITS:
            continue
        name = _text(u.get("name"), NAME_LIMIT)
        lessons, objectives = [], []
        stored = u.get("objectives") if isinstance(u.get("objectives"), list) else []
        for k, t in enumerate(u.get("lessons") or []):
            # a lesson: its title (paths saved before objectives), or {"title", "objective"} (the AI's reply)
            title_t = _text(t.get("title") if isinstance(t, dict) else t, LESSON_LIMIT)
            goal_t = _text(t.get("objective") if isinstance(t, dict) else (stored[k] if k < len(stored) else ""),
                           OBJECTIVE_LIMIT)
            key = title_t.lower()
            if title_t and key not in seen and len(lessons) < MAX_LESSONS and total < MAX_TOTAL:
                seen.add(key)
                lessons.append(title_t)
                objectives.append(goal_t)
                total += 1
        if name and lessons:
            # objectives sit beside the titles, one each ("" where there is none), only when there are any
            units.append({"name": name, "lessons": lessons, **({"objectives": objectives} if any(objectives) else {})})
    if not units:            # (one lesson is a path: she may have skipped the rest, paths.remove_*)
        return None
    return {
        "id": data["id"], "title": title, "outcome": outcome,
        "level": data.get("level") if data.get("level") in LEVELS else "Beginner",
        "units": units,
        "goal": _text(data.get("goal"), GOAL_MAX_CHARS), "why": _text(data.get("why"), TEXT_LIMIT),
        "start": data.get("start") if data.get("start") in STARTS else "new",
        "status": data.get("status") if data.get("status") in STATUSES else "active",
        "created_at": str(data.get("created_at") or now_iso()), "updated_at": str(data.get("updated_at") or now_iso()),
    }


def objective(path: dict, n: int) -> str:
    """What lesson n (from 1, in the path's order) lets her do; "" when the
    path was designed before objectives."""
    k = 0
    for u in (path or {}).get("units") or []:
        for i, _ in enumerate(u["lessons"]):
            k += 1
            if k == n:
                return (u.get("objectives") or [""] * len(u["lessons"]))[i] if i < len(u.get("objectives") or []) else ""
    return ""


def lesson_count(path: dict) -> int:
    return sum(len(u["lessons"]) for u in path["units"])


# --------------------------------------------- adjusting, before she starts
def lighter(path: dict) -> dict:
    """A lighter path: each unit keeps its first lessons (about two thirds,
    never fewer than two)."""
    units = []
    for u in path["units"]:
        keep = max(MIN_LESSONS, -(-len(u["lessons"]) * 2 // 3))
        units.append(dict(u, lessons=u["lessons"][:keep], **({"objectives": u["objectives"][:keep]} if "objectives" in u else {})))
    return dict(path, units=units, updated_at=now_iso())


def with_level(path: dict, level: str) -> dict:
    """Deeper or gentler: the same lessons, taught at another level."""
    return dict(path, level=level, updated_at=now_iso()) if level in LEVELS else path


def remove_unit(path: dict, i: int) -> dict:
    """Without unit i (she knows it, or doesn't want it); one unit always stays."""
    if len(path["units"]) <= 1 or not 0 <= i < len(path["units"]):
        return path
    return dict(path, units=[u for k, u in enumerate(path["units"]) if k != i], updated_at=now_iso())


def move_unit(path: dict, i: int, step: int) -> dict:
    j = i + step
    if not (0 <= i < len(path["units"]) and 0 <= j < len(path["units"])):
        return path
    units = list(path["units"])
    units[i], units[j] = units[j], units[i]
    return dict(path, units=units, updated_at=now_iso())


def remove_lesson(path: dict, i: int, k: int) -> dict:
    """Without lesson k of unit i; a unit left with no lesson goes too (one lesson always stays)."""
    if lesson_count(path) <= 1 or not 0 <= i < len(path["units"]) or not 0 <= k < len(path["units"][i]["lessons"]):
        return path
    units = []
    for n, u in enumerate(path["units"]):
        lessons = [t for m, t in enumerate(u["lessons"]) if not (n == i and m == k)]
        if lessons:
            unit = dict(u, lessons=lessons)
            if "objectives" in u:
                unit["objectives"] = [o for m, o in enumerate(u["objectives"]) if not (n == i and m == k)]
            units.append(unit)
    return dict(path, units=units, updated_at=now_iso())


def keep_units(original: dict, names) -> dict:
    """The designed path with only the parts she ticked, in the designed order
    (at least one part always stays: with none ticked, the whole path)."""
    keep = [u for u in original["units"] if u["name"] in set(names)]
    return dict(original, units=keep or list(original["units"]), updated_at=now_iso())


def started(log: dict, goal_id: str) -> bool:
    """Has she begun this goal (a lesson written)? Its outline is fixed from then on."""
    return any(e["topic"] == goal_id and any(s.get("lesson") or s.get("completed") for s in e.get("lessons") or [])
               for e in log["entries"])


def archive(path: dict) -> dict:
    return dict(path, status="archived", updated_at=now_iso())


def remove(path: dict) -> dict:
    """Off her list: not in her turns, not among her goals. Nothing is deleted:
    the lessons she took for it stay in her record, under its name."""
    return dict(path, status="removed", updated_at=now_iso())


def restore(path: dict) -> dict:
    return dict(path, status="active", updated_at=now_iso())
