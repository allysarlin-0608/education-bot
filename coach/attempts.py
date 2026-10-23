"""One row per answer, for measuring learning (docs/LEARNING_DESIGN.md §7b;
table learning_attempts, supabase/learning_attempts.sql).

What a row says, and only this: the day; which idea (subject or goal id,
lesson number); where it was answered (CONTEXTS); the kind of exercise and
its difficulty (or, for ctx "step", the step of the session she reached:
STEPS); whether it was her first try at that item; the score
(0..1); how sure she said she was (1 guessed, 2 fairly sure, 3 sure);
roughly how many seconds it took; how many days since she last practised
that idea; and the experiment arms in force (coach/experiments.py). Never
the question, her answer, or anything she wrote. The rows go with her
account (deleted with it; in her data export).

From them (coach/learnmetrics.py): first-attempt accuracy, delayed
retention, time to mastery, calibration, where sessions stop.
Pure functions: the shape, checked."""
from datetime import date

CONTEXTS = ("warmup", "check", "guided", "quiz", "mixed", "practice", "review", "unit", "diag", "jol", "explain",
            "step")
# a session's steps, recorded as she reaches each (ctx "step"): where sessions stop
STEPS = ("warmup", "learn", "practice", "quiz", "passed", "mixed", "explain", "reflect")
KINDS = ("choice", "scenario", "blank", "order", "match", "short", "apply", "steps", "spot", "problem",
         "word", "point", "explain", "jol") + STEPS
MAX_ROWS = 40               # rows in one write
MAX_SECONDS = 3600


def _int(value, low, high):
    return value if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high else None


def row(day: date, topic: str, n: int, ctx: str, kind: str, score=None, first: bool = True, conf=None,
        secs=None, gap=None, diff=None, variants=()) -> dict:
    """One answer, as stored (see the module's docstring)."""
    return parse({"day": day.isoformat(), "topic": str(topic or "")[:60], "n": n, "ctx": ctx, "kind": kind,
                  "score": score, "first": first, "conf": conf, "secs": secs, "gap": gap, "diff": diff,
                  "variant": ",".join(variants)})


def parse(data):
    """A row, checked (None if it can't be one)."""
    if not isinstance(data, dict) or data.get("ctx") not in CONTEXTS or data.get("kind") not in KINDS:
        return None
    try:
        day = date.fromisoformat(str(data.get("day") or "")).isoformat()
    except ValueError:
        return None
    n = _int(data.get("n"), 0, 100000)
    if n is None or not isinstance(data.get("topic"), str) or not data["topic"]:
        return None
    score = data.get("score")
    if score is not None:
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            return None
        score = round(min(1.0, max(0.0, float(score))), 3)
    secs = data.get("secs")
    secs = int(min(MAX_SECONDS, max(0, secs))) if isinstance(secs, (int, float)) and not isinstance(secs, bool) else None
    return {"day": day, "topic": data["topic"][:60], "n": n, "ctx": data["ctx"], "kind": data["kind"],
            "score": score, "first": data.get("first") is not False, "conf": _int(data.get("conf"), 1, 3),
            "secs": secs, "gap": _int(data.get("gap"), 0, 10000), "diff": _int(data.get("diff"), 1, 3),
            "variant": str(data.get("variant") or "")[:120]}


def rows(data) -> list:
    """The usable rows of a list (at most MAX_ROWS)."""
    out = [parse(r) for r in data if isinstance(data, list)] if isinstance(data, list) else []
    return [r for r in out if r][:MAX_ROWS]


def gap(evidence: list, today: date):
    """Days since the idea was last practised before today (None: never)."""
    days = [e["d"] for e in evidence or [] if e.get("d") and e["d"] < today.isoformat()]
    return (today - date.fromisoformat(max(days))).days if days else None
