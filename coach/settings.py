"""Her settings: which subjects, how much each day, where each subject
starts, and whether there is a reading plan. One row per user in the
user_settings table (a JSON file locally), always found by user_id.

This is the configuration layer only. The learning system (lessons,
quizzes, reading, progress) works as it always has; it reads from here
which subject a day is for, how many lessons a day has, the level a
subject starts at, and whether Reading is on.

Pure functions, no Streamlit, so they can be tested."""
from datetime import date, datetime, timedelta

from coach import catalog, clock, core, paths

DEFAULT_USER_ID = "owner"

# The subjects she can choose, in the order they are offered. General
# Knowledge ("free") is no longer offered (ISS-109): only the original
# weekly setup (is_legacy, the owner's personal app) still has it, on Sundays.
SUBJECTS = ("philosophy", "cosmos", "investing", "business", "fashion", "jewelry", "math")
LEGACY_SUBJECTS = SUBJECTS + ("free",)
DESCRIPTIONS = {
    "philosophy": "Arguments, the great thinkers East and West, and how to live.",
    "cosmos": "The sky, the solar system, stars and galaxies, and how we know.",
    "investing": "How markets work, risk and return, and investing for the long run.",
    "business": "Customers, business models, money, and turning an idea into a plan.",
    "fashion": "Fibres and fabrics, fit and construction, colour and personal style.",
    "jewelry": "Metals and gemstones, how pieces are made, and how to judge them.",
    "math": "From numbers and fractions to calculus, proof and open problems, one small step at a time.",
    "free": "A wide mix: history, psychology, economics, art, science and more.",
}
MIN_SUBJECTS, MAX_SUBJECTS = 1, 3
# her own goals (coach/paths.py) take turns with the subjects; how many she
# may keep active is the plan's to decide (coach/plans.py), this is the most
# the app handles
MAX_GOALS = 5

# lessons a day -> (name, time)
PACES = {1: ("Light", "~10 min"), 3: ("Steady", "~25 min"), 5: ("Focused", "~40 min")}
DEFAULT_PACE = 3

LEVELS = ("Beginner", "Intermediate", "Advanced")

FIELDS = ("user_id", "subjects", "units_per_day", "subject_levels", "reading_enabled",
          "onboarding", "onboarded_at", "updated_at")


def blank(user_id: str) -> dict:
    """A user who hasn't set anything up yet."""
    return {"user_id": user_id, "subjects": [], "units_per_day": DEFAULT_PACE, "subject_levels": {},
            "reading_enabled": False, "onboarding": None, "onboarded_at": None, "updated_at": None}


# Before user_settings existed (and wherever its table hasn't been created
# yet) the app ran on a fixed setup: a subject for each weekday, five
# lessons a day, Reading always there. Kept so that setup runs unchanged.
def legacy(user_id: str) -> dict:
    return dict(blank(user_id), units_per_day=5, reading_enabled=True, legacy=True)


def is_legacy(s: dict) -> bool:
    return bool(s.get("legacy"))


def normalize(row, user_id: str) -> dict:
    """A row from storage, checked and filled in. A row for someone else
    is never taken for hers."""
    s = blank(user_id)
    if not isinstance(row, dict) or row.get("user_id") != user_id:
        return s
    subjects = row.get("subjects")
    if isinstance(subjects, list):
        s["subjects"] = _cap([t for t in dict.fromkeys(subjects) if t in SUBJECTS or catalog.is_goal(t)])
    if row.get("units_per_day") in PACES:
        s["units_per_day"] = row["units_per_day"]
    levels = row.get("subject_levels")
    if isinstance(levels, dict):
        s["subject_levels"] = {t: lv for t, lv in levels.items() if t in SUBJECTS and lv in LEVELS}
    s["reading_enabled"] = bool(row.get("reading_enabled"))
    s["onboarding"] = row.get("onboarding") if isinstance(row.get("onboarding"), dict) else None
    for field in ("onboarded_at", "updated_at"):
        s[field] = row.get(field) or None
    return s


def _cap(items: list) -> list:
    """At most MAX_SUBJECTS subjects and MAX_GOALS goals, in her order."""
    out, subjects, goals = [], 0, 0
    for t in items:
        if t in SUBJECTS and subjects < MAX_SUBJECTS:
            subjects += 1
            out.append(t)
        elif catalog.is_goal(t) and goals < MAX_GOALS:
            goals += 1
            out.append(t)
    return out


def errors(s: dict) -> list:
    """What's wrong with a finished configuration (empty when it's fine)."""
    out = []
    items = s.get("subjects") or []
    subjects = [t for t in items if t in SUBJECTS]
    goals = [t for t in items if catalog.is_goal(t)]
    if len(items) < MIN_SUBJECTS:
        out.append("Choose a subject or set a goal to learn.")
    if len(subjects) > MAX_SUBJECTS:
        out.append(f"Choose at most {MAX_SUBJECTS} subjects.")
    if len(goals) > MAX_GOALS:
        out.append(f"Keep at most {MAX_GOALS} goals.")
    if len(set(items)) != len(items) or len(subjects) + len(goals) != len(items):
        out.append("Unknown or repeated subject.")
    if s.get("units_per_day") not in PACES:
        out.append("Choose a daily pace.")
    levels = s.get("subject_levels") or {}
    if any(levels.get(t) not in LEVELS for t in subjects):       # (a goal's level is its path's)
        out.append("Every subject needs a starting level.")
    if not isinstance(s.get("reading_enabled"), bool):
        out.append("Reading must be on or off.")
    return out


def onboarded(s: dict) -> bool:
    return is_legacy(s) or bool(s.get("onboarded_at"))


def now_iso() -> str:
    return clock.now_iso()


# ------------------------------------------------------------
# The setup in progress (kept in the row until it's finished)
# ------------------------------------------------------------
# The setup's steps (views/setup.py: route() picks the ones her answers call for):
# who she is; what she wants to learn (in her words, or found among broad
# directions: explore); all of it or some parts (scope); what it's for
# (purpose); and a confirmation, whose button is Start learning.
STEPS = ("identity", "want", "explore", "scope", "purpose", "confirm")
DRAFT_VERSION = 3
# drafts saved by earlier setups: their steps, and where each now is
V2_STEPS = ("welcome", "plans", "subjects", "goal", "reading", "selection", "price", "customize", "path", "review")
V1_STEPS = ("welcome", "goal", "path", "subjects", "pace", "level", "reading", "summary")
OLD_STEPS = ("welcome", "subjects", "pace", "level", "reading", "summary")      # (drafts saved before goals)
MOVED = {"welcome": "identity", "plans": "identity", "subjects": "want", "goal": "want", "path": "scope",
         "reading": "purpose", "selection": "confirm", "price": "confirm", "customize": "confirm",
         "review": "confirm", "pace": "confirm", "level": "confirm", "summary": "confirm"}
GOAL = "goal"           # the goal being made, in the draft's order of turns
SCOPES = ("all", "some")


def new_draft() -> dict:
    return {"v": DRAFT_VERSION, "step": 0, "plan": None, "subjects": [], "units_per_day": DEFAULT_PACE, "levels": {},
            "reading_enabled": False, "want_goal": False, "goal_at": 0, "back_to": None,
            "identity": "", "knows": False, "exploring": False, "explore": [], "scope": None, "purpose": "", "keep": [],
            **new_goal_draft()}


def new_goal_draft() -> dict:
    """A goal being made (coach/goalmaker.py): what she wrote, the AI's
    answer when it couldn't plan it yet, and the path while she adjusts it."""
    return {"goal": {"text": "", "why": "", "start": "new", "answers": ""},
            "design": None, "path": None, "path_original": None}


def goal_draft_of(saved: dict) -> dict:
    """The goal part of a stored draft, checked."""
    d = new_goal_draft()
    g = saved.get("goal") if isinstance(saved.get("goal"), dict) else {}
    d["goal"] = {"text": str(g.get("text") or "")[:paths.GOAL_MAX_CHARS * 2],
                 "why": str(g.get("why") or "")[:paths.TEXT_LIMIT],
                 "start": g.get("start") if g.get("start") in paths.STARTS else "new",
                 "answers": str(g.get("answers") or "")[:paths.TEXT_LIMIT]}
    design = saved.get("design")
    if isinstance(design, dict) and design.get("status") in ("ok", "clarify", "narrow", "decline", "error"):
        d["design"] = {"status": design["status"], "message": str(design.get("message") or ""),
                       "questions": [str(q) for q in design.get("questions") or [] if q][:2],
                       "suggestions": [str(q) for q in design.get("suggestions") or [] if q][:3],
                       "for": str(design.get("for") or ""), "text": str(design.get("text") or ""),
                       "calls": design.get("calls") if isinstance(design.get("calls"), int) else 0}
    d["path"] = paths.parse_path(saved.get("path"))
    d["path_original"] = paths.parse_path(saved.get("path_original")) if d["path"] else None
    return d


def draft_of(s: dict) -> dict:
    """Her answers so far, checked (a draft is stored as she goes)."""
    d, saved = new_draft(), s.get("onboarding") or {}
    if isinstance(saved.get("step"), int):
        d["step"] = _step_of(saved)
    if isinstance(saved.get("plan"), str) and len(saved["plan"]) <= 12:
        d["plan"] = saved["plan"]
    d["want_goal"] = saved.get("want_goal") is True
    if isinstance(saved.get("goal_at"), int) and saved["goal_at"] >= 0:
        d["goal_at"] = saved["goal_at"]
    d["back_to"] = saved.get("back_to") if saved.get("back_to") in STEPS else None    # (a change from the review)
    d["identity"] = str(saved.get("identity") or "")[:60]
    d["knows"] = saved.get("knows") is True
    d["exploring"] = saved.get("exploring") is True
    if isinstance(saved.get("explore"), list):
        d["explore"] = [str(x)[:60] for x in saved["explore"]][:3]
    d["scope"] = saved.get("scope") if saved.get("scope") in SCOPES else None
    d["purpose"] = str(saved.get("purpose") or "")[:paths.TEXT_LIMIT]
    if isinstance(saved.get("keep"), list):          # (the setup run again: her turns before it)
        d["keep"] = [t for t in saved["keep"] if isinstance(t, str) and catalog.valid(t)][:MAX_SUBJECTS + MAX_GOALS]
    if isinstance(saved.get("subjects"), list):
        d["subjects"] = [t for t in dict.fromkeys(saved["subjects"]) if t in SUBJECTS][:MAX_SUBJECTS]
    if saved.get("units_per_day") in PACES:
        d["units_per_day"] = saved["units_per_day"]
    if isinstance(saved.get("levels"), dict):
        d["levels"] = {t: dict(v) for t, v in saved["levels"].items() if t in SUBJECTS and isinstance(v, dict)}
    d["reading_enabled"] = bool(saved.get("reading_enabled"))
    d.update(goal_draft_of(saved))
    return d


def _step_of(saved: dict) -> int:
    """The step a stored draft is at, in today's steps (a draft from an
    earlier setup: the same place, under its new name)."""
    step = saved["step"]
    if saved.get("v") == DRAFT_VERSION:
        return min(max(step, 0), len(STEPS) - 1)
    old = V2_STEPS if saved.get("v") == 2 else V1_STEPS if "goal" in saved else OLD_STEPS
    name = old[min(max(step, 0), len(old) - 1)]
    return STEPS.index(MOVED.get(name, name))


def rotation(d: dict) -> list:
    """Her turns, in order: the goal being made (GOAL) first, then any
    subjects in the draft (a draft from an earlier setup may have some)."""
    items = list(d["subjects"])
    if d.get("path"):
        items.insert(min(d.get("goal_at", 0), len(items)), GOAL)
    return items


def toggle_subject(subjects: list, topic: str) -> list:
    """Chosen subjects in the order she chose them (their order of turns).
    A fourth can't be added."""
    if topic in subjects:
        return [t for t in subjects if t != topic]
    if topic not in SUBJECTS or len([t for t in subjects if t in SUBJECTS]) >= MAX_SUBJECTS:
        return list(subjects)          # (her goals don't count toward the three subjects)
    return list(subjects) + [topic]


def level_choice(d: dict, topic: str) -> dict:
    """How a subject's level is being set in the draft: from the basics
    (the default) or by the placement check."""
    c = d["levels"].get(topic) or {}
    return {"way": c.get("way") if c.get("way") in ("basics", "placement") else "basics",
            "answers": c.get("answers") if isinstance(c.get("answers"), list) else [],
            "at": c.get("at") if isinstance(c.get("at"), int) else 0,
            "level": c.get("level") if c.get("level") in LEVELS else None,
            "score": c.get("score") if isinstance(c.get("score"), int) else None}


def draft_levels(d: dict) -> dict:
    """The starting level of each chosen subject (None while a placement
    check is unfinished)."""
    out = {}
    for t in d["subjects"]:
        c = level_choice(d, t)
        out[t] = "Beginner" if c["way"] == "basics" else c["level"]
    return out


def rerun(s: dict, when: str) -> dict:
    """Her settings with the setup to be run again (a test of the setup on an
    account already in use): nothing is deleted. Her turns, pace and reading
    plan are kept in the draft; what she chooses now comes first, then those."""
    d = dict(new_draft(), keep=chosen_subjects(s), units_per_day=units(s), reading_enabled=bool(s.get("reading_enabled")))
    return dict(s, onboarded_at=None, onboarding=d, updated_at=when)


def finish(s: dict, d: dict, when: str, log: dict | None = None) -> dict:
    """The settings she chose, ready to save: onboarded, draft cleared.
    Raises ValueError if anything is missing (never saved half done)."""
    # in her order of turns (her goal first unless she moved it: her first day is for it)
    items = [d["path"]["id"] if t == GOAL else t for t in rotation(d)]
    # the setup run again (Account → Run the setup again): what she had stays, after what she chose now
    items = _cap(list(dict.fromkeys(items + [t for t in d.get("keep") or [] if t in SUBJECTS or catalog.is_goal(t)])))
    if log and d.get("path") and d["path"]["id"] in items:     # (run again: her new goal is her next turn)
        goal = d["path"]["id"]
        rest = [t for t in items if t != goal]
        last = last_turn(dict(s, subjects=rest), clock.today() + timedelta(days=1), log)
        rest.insert(rest.index(last) + 1 if last in rest else 0, goal)
        items = rest
    done = dict(s, subjects=items, units_per_day=d["units_per_day"],
                subject_levels={**(s.get("subject_levels") or {}), **draft_levels(d)},
                reading_enabled=bool(d["reading_enabled"]),
                onboarding=None, onboarded_at=when, updated_at=when)
    problems = errors(done)
    if problems:
        raise ValueError(" ".join(problems))
    return done


def change(s: dict, when: str, **fields) -> dict:
    """Settings with some fields changed (Settings page). A subject added
    later starts at Beginner; its level can then be checked. Levels of
    subjects taken out are kept, in case she comes back to them. Raises
    ValueError on an invalid result."""
    new = dict(s, **fields, updated_at=when)
    levels = dict(s.get("subject_levels") or {})
    for t in new["subjects"]:
        levels.setdefault(t, "Beginner")
    new["subject_levels"] = {**levels, **(fields.get("subject_levels") or {})}
    problems = errors(new)
    if problems:
        raise ValueError(" ".join(problems))
    return new


# ------------------------------------------------------------
# What the learning system reads
# ------------------------------------------------------------

def start_day(s: dict, tz) -> date:
    """Day 1 of the rotation: the day she finished setting up."""
    when = datetime.fromisoformat(s["onboarded_at"].replace("Z", "+00:00"))
    return when.astimezone(tz).date() if when.tzinfo else when.date()


# Her turns: her subjects and goals take turns, one a day of study, in her
# order (a cycle: `subjects`, read round and round). The turn moves on when
# she studies, not with the calendar: a day she doesn't study leaves the
# turn where it was. (It once moved with the calendar, so someone with two
# goals who studied every other day only ever met the first one.)
def last_turn(s: dict, before: date, log: dict | None) -> str | None:
    """The last of her turns she studied before `before` (None: none yet).
    A day she studied more than one of them counts the one whose turn it was."""
    subjects = chosen_subjects(s)
    if not log or not subjects:
        return None
    by_day = {}
    for e in log["entries"]:
        if e["date"] < before.isoformat() and e.get("lessons") and e["topic"] in subjects:
            by_day.setdefault(e["date"], []).append(e["topic"])
    last = None
    for d in sorted(by_day):
        topics = by_day[d]
        expected = next_turn(subjects, last)
        last = expected if expected in topics else min(topics, key=subjects.index)
    return last


def next_turn(subjects: list, last: str | None) -> str:
    """The turn after `last` in her cycle (the first one when there is none)."""
    return subjects[(subjects.index(last) + 1) % len(subjects)] if last in subjects else subjects[0]


def topic_for(s: dict, day: date, tz, log: dict | None = None) -> str:
    """The subject or goal for `day`. A day she has already started keeps it
    (adding or moving one must not swap the day under her: ISS-005). Up to
    today: the turn after the last one she studied. After today: one turn a
    day from today's (as if she studies every day; a day she misses doesn't
    move it on)."""
    subjects = chosen_subjects(s)
    if is_legacy(s) or not subjects:
        return core.scheduled_topic(day)
    if log:
        started = [e["topic"] for e in log["entries"]
                   if e["date"] == day.isoformat() and e.get("lessons") and e["topic"] in subjects]
        if started:
            return started[0]
    today = clock.today()
    if day <= today:
        return next_turn(subjects, last_turn(s, day, log))
    now = topic_for(s, today, tz, log)
    return subjects[(subjects.index(now) + (day - today).days) % len(subjects)]


def days_ahead(s: dict, day: date, tz, log: dict | None = None) -> list:
    """Her coming turns, one per subject or goal: [(day, topic)] from `day`,
    as many days as she has turns (then they repeat)."""
    n = len(chosen_subjects(s))
    return [(day + timedelta(days=k), topic_for(s, day + timedelta(days=k), tz, log)) for k in range(n)]


def order_from(s: dict, order: list) -> dict:
    """Her settings with her turns in `order` (a cycle: what comes after
    what). Shown from today, `order` starts with today's turn and ends with
    the one she studied last (or today's, when today is started): kept in
    place by Goals & Settings → Your days, so the turn after it is order[0]."""
    items = chosen_subjects(s)
    if sorted(order) != sorted(items) or not items or is_legacy(s):
        return s
    return dict(s, subjects=list(order))


def units(s: dict) -> int:
    return s.get("units_per_day") if s.get("units_per_day") in PACES else DEFAULT_PACE


def start_level(s: dict, topic: str):
    """Where a subject starts (None: from the syllabus alone, as before); a
    goal is taught at its path's level."""
    if catalog.is_goal(topic):
        return catalog.level(topic)
    level = (s.get("subject_levels") or {}).get(topic)
    return level if level in LEVELS else None


def chosen_subjects(s: dict) -> list:
    """The subjects she has chosen, in her order. The one source of truth is
    her settings row's `subjects` (user_settings.subjects); every page reads
    it through here. (Levels may be kept for subjects she has taken out, so
    they come back if she adds one again; nothing shows those.)"""
    return [t for t in (s.get("subjects") or []) if t in SUBJECTS or _active_goal(t)]


def _active_goal(t) -> bool:
    """One of her goals still in her turns: active, or not readable just now
    (ISS-045: a goal that didn't load is kept, never dropped by the next save)."""
    if not catalog.is_goal(t):
        return False
    p = catalog.path(t)
    return p["status"] == "active" if p else catalog.unreadable()


def chosen_goals(s: dict) -> list:
    return [t for t in chosen_subjects(s) if catalog.is_goal(t)]


def add_goal(s: dict, goal_id: str, when: str, first_day: date = None, tz=None, log: dict | None = None) -> dict:
    """Her settings with a goal added to her turns. With first_day, the goal
    comes right after the turn she studied last before that day, so that day
    is its turn (the others follow it as before; a day already started keeps
    its subject: topic_for). Without, it joins at the end of the cycle.
    Archived goals leave the turns."""
    items = [t for t in chosen_subjects(s) if t != goal_id]
    if len([t for t in items if catalog.is_goal(t)]) + 1 > MAX_GOALS:
        raise ValueError(f"Keep at most {MAX_GOALS} goals.")
    if first_day is not None and not is_legacy(s):
        last = last_turn(dict(s, subjects=items), first_day, log)
        items.insert(items.index(last) + 1 if last in items else 0, goal_id)
    else:
        items.append(goal_id)
    return dict(s, subjects=items, updated_at=when)


def builtin_offered(s: dict, log: dict = None) -> bool:
    """Our built-in subjects are offered only to someone who has learnt one
    of them (chosen now, or in her record): since anything can be learnt
    from her own words, a new learner isn't shown a fixed list."""
    if is_legacy(s) or any(t in SUBJECTS for t in s.get("subjects") or []):
        return True
    return any(e.get("topic") in SUBJECTS for e in (log or {}).get("entries", []))


def shown_subjects(s: dict) -> list:
    """The subjects the pages show: hers, or all of them on the old setup."""
    return list(LEGACY_SUBJECTS) if is_legacy(s) else chosen_subjects(s)


def reading_on(s: dict) -> bool:
    return is_legacy(s) or bool(s.get("reading_enabled"))


def pace_line(n: int) -> str:
    name, minutes = PACES[n]
    return f"{n} {'lesson' if n == 1 else 'lessons'} · {minutes}"
