"""Her habit preferences and the little state that must follow her across
devices: reminders, a light day, the milestones and weekly reports she
has already seen. One row per person (learner_prefs; a local file in
personal mode), saved whole, so a change is applied onto the row as
stored now (ui.save_prefs).

Pure functions: the shape, checked."""
import re

TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DEFAULT_TIME = "19:00"
SEEN_LIMIT = 200          # milestones remembered (the oldest go first)


def blank() -> dict:
    return {"reminder_on": False, "reminder_time": DEFAULT_TIME, "reminder_email": False,
            "light_day": "", "seen": [], "seen_init": False, "week_seen": "", "reminded_on": "", "reminder_hit": "",
            "practice": None, "practice_made": "", "plan_choice": ""}


def normalize(row) -> dict:
    """A stored row, checked; anything unknown or malformed falls back."""
    p = blank()
    if not isinstance(row, dict):
        return p
    p["reminder_on"] = row.get("reminder_on") is True
    if isinstance(row.get("reminder_time"), str) and TIME.match(row["reminder_time"]):
        p["reminder_time"] = row["reminder_time"]
    p["reminder_email"] = row.get("reminder_email") is True
    p["seen_init"] = row.get("seen_init") is True
    # the plan she chose in the setup (what she asked for; her plan is coach/plans.plan_of)
    for key in ("light_day", "week_seen", "reminded_on", "reminder_hit", "practice_made", "plan_choice"):
        if isinstance(row.get(key), str) and len(row[key]) <= 12:
            p[key] = row[key]
    if isinstance(row.get("seen"), list):
        p["seen"] = [s for s in row["seen"] if isinstance(s, str) and len(s) <= 120][-SEEN_LIMIT:]
    p["practice"] = practice_set(row.get("practice"))
    return p


def practice_set(data):
    """Today's practice set where she left it (views/practice.py), checked:
    {"date", "items": [{"topic", "n", "q"}], "answers", "marks", "before": {idea: level}, "done"}."""
    from coach import quiz
    if not isinstance(data, dict) or not isinstance(data.get("date"), str) or not isinstance(data.get("items"), list):
        return None
    items = []
    for x in data["items"][:12]:
        q = quiz._saved_question(x.get("q")) if isinstance(x, dict) else None
        if q is None or not isinstance(x.get("topic"), str) or not isinstance(x.get("n"), int):
            return None
        items.append({"topic": x["topic"], "n": x["n"], "q": q})
    n = len(items)
    answers = data.get("answers") if isinstance(data.get("answers"), list) and len(data["answers"]) == n else [None] * n
    marks = data.get("marks") if isinstance(data.get("marks"), list) and len(data["marks"]) == n else [None] * n
    marks = [m if isinstance(m, (int, float)) and not isinstance(m, bool) else None for m in marks]
    before = data.get("before") if isinstance(data.get("before"), dict) else {}
    return {"date": data["date"][:10], "items": items, "answers": answers, "marks": marks,
            "before": {str(k): str(v) for k, v in before.items()}, "done": data.get("done") is True,
            "seen": [str(x) for x in data.get("seen") or []][:60] if isinstance(data.get("seen"), list) else []}


def mark_seen(p: dict, keys) -> dict:
    """Milestones now shown: never shown again."""
    seen = p["seen"] + [k for k in keys if k not in p["seen"]]
    return dict(p, seen=seen[-SEEN_LIMIT:])
