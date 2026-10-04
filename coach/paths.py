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
from datetime import datetime, timezone

LEVELS = ("Beginner", "Intermediate", "Advanced")
STATUSES = ("active", "archived")
MIN_UNITS, MAX_UNITS = 2, 8
MIN_LESSONS, MAX_LESSONS = 2, 8          # in a unit
MAX_TOTAL = 48
TITLE_LIMIT, NAME_LIMIT, LESSON_LIMIT, TEXT_LIMIT = 60, 80, 110, 400
GOAL_MIN_CHARS, GOAL_MAX_CHARS = 8, 300
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
    return datetime.now(timezone.utc).isoformat()


def _text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


# ------------------------------------------------------------------- her goal
def precheck(goal: str):
    """A quick look before any AI call: None when the goal can go to the
    designer, else a short, kind reason and what to try (no cost to her
    daily allowance)."""
    text = _text(goal, 2000)
    if len(text) < GOAL_MIN_CHARS:
        return "Tell us a little more: what would you like to be able to do?"
    if len(text) > GOAL_MAX_CHARS:
        return f"That's a lot to plan at once. Try one goal in a sentence or two (under {GOAL_MAX_CHARS} characters)."
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if words and len(words) <= 2 and all(w in VAGUE or w in {"learn", "about", "the", "to", "a", "i", "want"} for w in words):
        return (f"“{text}” is a big field. What would you like to be able to do with it? "
                "For example: read a balance sheet, explain how a market works, or plan a first project.")
    return None


# ----------------------------------------------------------- asking the AI
DESIGN_SYSTEM = """You design short, structured learning paths for adults who learn a little every day.
Reply with ONE JSON object and nothing else.

Read the learner's goal, why it matters to them, where they are now, and how many lessons a day they have.

First decide the status:
- "ok": a clear goal that can be learned in about four weeks of short daily lessons.
- "clarify": too vague to plan (e.g. "learn business"). Ask 1-2 short questions and give 3 well-shaped goals they could pick instead.
- "narrow": far too big for a few weeks (e.g. "become a doctor", "learn all of physics"). Explain kindly in one sentence and give 3 first-step goals that fit a few weeks.
- "decline": not something to teach here: instructions that could cause harm; a diagnosis, treatment plan or legal advice for the learner's own situation; which stocks or coins to buy; cheating on tests; hateful or sexual content; topics where accuracy can't be ensured (events after 2024, rules that change by region without a source). Explain kindly in one sentence, and give 3 educational alternatives (e.g. "how blood pressure works" instead of "treat my blood pressure").

For "ok", design the path:
- "title": a short name for the path (max 6 words, no quotes).
- "outcome": one sentence starting "By the end you will be able to" - concrete and checkable.
- "units": {units_min}-{units_max} units in a sensible order; each has "name" (max 6 words) and "lessons": {lessons_min}-{lessons_max} lesson titles.
- Total lessons: {total_min}-{total_max}. Each lesson title names ONE idea or skill a 10-minute lesson can teach, in plain words (max 10 words), building on the ones before. No duplicates, no "Introduction"/"Conclusion"/"Review" lessons, no exam or quiz lessons.
- Only well-established knowledge; nothing that depends on recent news.

JSON shape:
{{"status": "ok|clarify|narrow|decline", "message": "one kind sentence (for clarify/narrow/decline)",
  "questions": ["..."], "suggestions": ["..."],
  "title": "...", "outcome": "...",
  "units": [{{"name": "...", "lessons": ["...", "..."]}}]}}"""


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
    if path is None:
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
        lessons = []
        for t in u.get("lessons") or []:
            title_t = _text(t, LESSON_LIMIT)
            key = title_t.lower()
            if title_t and key not in seen and len(lessons) < MAX_LESSONS and total < MAX_TOTAL:
                seen.add(key)
                lessons.append(title_t)
                total += 1
        if name and lessons:
            units.append({"name": name, "lessons": lessons})
    if not units or total < 4:
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


def lesson_count(path: dict) -> int:
    return sum(len(u["lessons"]) for u in path["units"])


# --------------------------------------------- adjusting, before she starts
def lighter(path: dict) -> dict:
    """A lighter path: each unit keeps its first lessons (about two thirds,
    never fewer than two)."""
    units = [dict(u, lessons=u["lessons"][:max(MIN_LESSONS, -(-len(u["lessons"]) * 2 // 3))]) for u in path["units"]]
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
            units.append(dict(u, lessons=lessons))
    return dict(path, units=units, updated_at=now_iso())


def started(log: dict, goal_id: str) -> bool:
    """Has she begun this goal (a lesson written)? Its outline is fixed from then on."""
    return any(e["topic"] == goal_id and any(s.get("lesson") or s.get("completed") for s in e.get("lessons") or [])
               for e in log["entries"])


def archive(path: dict) -> dict:
    return dict(path, status="archived", updated_at=now_iso())


def restore(path: dict) -> dict:
    return dict(path, status="active", updated_at=now_iso())
