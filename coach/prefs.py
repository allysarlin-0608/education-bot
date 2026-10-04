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
            "light_day": "", "seen": [], "week_seen": "", "reminded_on": ""}


def normalize(row) -> dict:
    """A stored row, checked; anything unknown or malformed falls back."""
    p = blank()
    if not isinstance(row, dict):
        return p
    p["reminder_on"] = row.get("reminder_on") is True
    if isinstance(row.get("reminder_time"), str) and TIME.match(row["reminder_time"]):
        p["reminder_time"] = row["reminder_time"]
    p["reminder_email"] = row.get("reminder_email") is True
    for key in ("light_day", "week_seen", "reminded_on"):
        if isinstance(row.get(key), str) and len(row[key]) <= 12:
            p[key] = row[key]
    if isinstance(row.get("seen"), list):
        p["seen"] = [s for s in row["seen"] if isinstance(s, str) and len(s) <= 120][-SEEN_LIMIT:]
    return p


def mark_seen(p: dict, keys) -> dict:
    """Milestones now shown: never shown again."""
    seen = p["seen"] + [k for k in keys if k not in p["seen"]]
    return dict(p, seen=seen[-SEEN_LIMIT:])
