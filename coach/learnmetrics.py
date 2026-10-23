"""Is GNOSIS making people learn? The numbers from the answer rows
(coach/attempts.py), as docs/LEARNING_DESIGN.md §7 defines them, for the
learning dashboard (views/learning.py, admins only) and the report
(tools/learning_report.py). Learning first; engagement is kept apart and
named as such.

- First-attempt accuracy: of first tries, the share right, by where (warm-up,
  quick check, practice, the check...) and by difficulty. 70-85% is the
  range where practice is hard enough to teach and easy enough to keep at.
- Delayed retention: reviews and warm-up items on an idea last practised 1+,
  7+ and 30+ days before: the share remembered.
- Time to remembered: for each idea, the days from its first answer to its
  first right answer a week or more after the one before (known a week
  later): the median, and how many ideas got there.
- Calibration: for each "how sure" (guessing, fairly sure, sure), the share
  right; how often "sure" was wrong; the Brier score (lower is better; the
  three ratings read as 1/3, 2/3 and 0.9). And the day's "will you remember"
  against the next answer on that idea a day or more later.
- Where sessions stop: of the sessions that reached each step, how many
  reached the next.
- Experiments (coach/experiments.py): each arm's outcome with a 95%
  confidence interval and the difference between arms; below MIN_N answers
  an arm, "not enough data" rather than a conclusion.
Pure functions."""
import math
from collections import defaultdict
from statistics import median

MIN_N = 30                  # answers an arm needs before its difference is worth reading
CONF_P = {1: 1 / 3, 2: 2 / 3, 3: 0.9}
DELAYS = (1, 7, 30)
RETRIEVAL = ("review", "warmup", "mixed", "practice", "unit")
FIRST_CTX = ("warmup", "check", "guided", "quiz", "mixed", "practice", "review", "unit", "diag")


def _right(r) -> bool:
    return r["score"] is not None and r["score"] >= 0.999


def _rate(rows) -> dict:
    scored = [r for r in rows if r["score"] is not None]
    n = len(scored)
    right = sum(1 for r in scored if _right(r))
    return {"n": n, "right": right, "share": right / n if n else None, "ci": wilson(right, n)}


def wilson(k: int, n: int, z: float = 1.96):
    """A 95% interval for a share k/n (Wilson's: sound for small n)."""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))


def difference(a: dict, b: dict):
    """(b - a, its 95% interval) for two shares, or None below MIN_N each."""
    if a["n"] < MIN_N or b["n"] < MIN_N:
        return None
    pa, pb = a["right"] / a["n"], b["right"] / b["n"]
    se = math.sqrt(pa * (1 - pa) / a["n"] + pb * (1 - pb) / b["n"])
    d = pb - pa
    return {"diff": d, "ci": (d - 1.96 * se, d + 1.96 * se)}


def _idea(r) -> tuple:
    return (r.get("learner", ""), r["topic"], r["n"])


def first_attempts(rows: list) -> dict:
    firsts = [r for r in rows if r["first"] and r["ctx"] in FIRST_CTX and r["score"] is not None]
    by_ctx = {c: _rate([r for r in firsts if r["ctx"] == c]) for c in FIRST_CTX}
    by_diff = {d: _rate([r for r in firsts if r.get("diff") == d]) for d in (1, 2, 3)}
    return {"all": _rate(firsts), "by_ctx": {k: v for k, v in by_ctx.items() if v["n"]},
            "by_diff": {k: v for k, v in by_diff.items() if v["n"]}}


def retention(rows: list) -> dict:
    out = {}
    for d in DELAYS:
        out[d] = _rate([r for r in rows if r["ctx"] in ("review", "warmup") and r.get("gap") is not None and r["gap"] >= d])
    return out


def time_to_remembered(rows: list) -> dict:
    """Days from an idea's first answer to its first right answer 7+ days after
    the answer before it (known a week later)."""
    by = defaultdict(list)
    for r in rows:
        if r["ctx"] not in ("step", "jol", "diag", "explain"):
            by[_idea(r)].append(r)
    days = []
    for answers in by.values():
        answers.sort(key=lambda r: r["day"])
        start = answers[0]["day"]
        hit = next((r for r in answers if r["ctx"] in RETRIEVAL and _right(r) and (r.get("gap") or 0) >= 7), None)
        if hit:
            days.append(_days(start, hit["day"]))
    return {"ideas": len(by), "remembered": len(days), "median_days": median(days) if days else None}


def _days(a: str, b: str) -> int:
    from datetime import date
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def calibration(rows: list) -> dict:
    rated = [r for r in rows if r.get("conf") and r["score"] is not None and r["ctx"] not in ("jol", "step")]
    by = {c: _rate([r for r in rated if r["conf"] == c]) for c in (1, 2, 3)}
    sure = [r for r in rated if r["conf"] == 3]
    brier = (sum((CONF_P[r["conf"]] - (1.0 if _right(r) else 0.0)) ** 2 for r in rated) / len(rated)) if rated else None
    # the day's judgment of learning against the next answer on that idea a day or more later
    later = defaultdict(list)
    for r in rows:
        if r["ctx"] in RETRIEVAL and r["score"] is not None:
            later[_idea(r)].append(r)
    jol = {}
    for c in (1, 2, 3):
        hits = []
        for j in (r for r in rows if r["ctx"] == "jol" and r.get("conf") == c):
            nxt = sorted((r for r in later.get(_idea(j), []) if r["day"] > j["day"]), key=lambda r: r["day"])
            if nxt:
                hits.append(nxt[0])
        jol[c] = _rate(hits)
    return {"by_conf": by, "sure_but_wrong": (sum(1 for r in sure if not _right(r)) / len(sure)) if sure else None,
            "sure_n": len(sure), "brier": brier, "jol": jol}


def funnel(rows: list) -> list:
    """[(step, sessions that reached it, share of the step before)], in order."""
    from coach import attempts
    reached = defaultdict(set)
    for r in rows:
        if r["ctx"] == "step":
            reached[r["kind"]].add((r.get("learner", ""), r["day"]))
    out, before = [], None
    for step in attempts.STEPS:
        n = len(reached.get(step, ()))
        out.append((step, n, (n / before) if before else None))
        before = n or before
    return out


def experiments(rows: list) -> dict:
    """Each experiment's arms: their outcome, and the difference."""
    out = {}
    # interleave: delayed retention of ideas, by the arm of their last mixed practice before it
    last_arm = {}
    delayed = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["day"]):
        tag = next((v.split(":")[1] for v in r["variant"].split(",") if v.startswith("interleave:")), None)
        if r["ctx"] == "mixed" and tag:
            last_arm[_idea(r)] = tag
        elif r["ctx"] in ("review", "warmup") and (r.get("gap") or 0) >= 7 and _idea(r) in last_arm:
            delayed[last_arm[_idea(r)]].append(r)
    out["interleave"] = _arms(("mixed", "blocked"), {k: _rate(v) for k, v in delayed.items()},
                              "Remembered a week or more later")
    # fading: first-try accuracy on the idea's check, by how its practice went
    arm_of = {}
    for r in rows:
        tag = next((v.split(":")[1] for v in r["variant"].split(",") if v.startswith("fading:")), None)
        if r["ctx"] == "guided" and tag:
            arm_of[_idea(r)] = tag
    checks = defaultdict(list)
    for r in rows:
        if r["ctx"] == "quiz" and r["first"] and _idea(r) in arm_of:
            checks[arm_of[_idea(r)]].append(r)
    out["fading"] = _arms(("faded", "problem_first"), {k: _rate(v) for k, v in checks.items()},
                          "Right on the check, first try")
    # retention target: remembered on reviews, by the learner's arm
    by = defaultdict(list)
    for r in rows:
        tag = next((v.split(":")[1] for v in r["variant"].split(",") if v.startswith("retention:")), None)
        if tag and r["ctx"] in ("review", "warmup"):
            by[tag].append(r)
    out["retention"] = _arms(("r90", "r85"), {k: _rate(v) for k, v in by.items()}, "Remembered on reviews")
    return out


def _arms(names: tuple, rates: dict, measure: str) -> dict:
    blank = {"n": 0, "right": 0, "share": None, "ci": None}
    a, b = rates.get(names[0], blank), rates.get(names[1], blank)
    return {"measure": measure, "arms": {names[0]: a, names[1]: b}, "difference": difference(a, b),
            "enough": a["n"] >= MIN_N and b["n"] >= MIN_N}


def engagement(rows: list) -> dict:
    """Named as what it is: activity, not learning."""
    sessions = {(r.get("learner", ""), r["day"]) for r in rows}
    learners = {r.get("learner", "") for r in rows}
    return {"learners": len(learners), "sessions": len(sessions), "answers": sum(1 for r in rows if r["score"] is not None)}


def summarize(rows: list) -> dict:
    rows = [dict(r, variant=r.get("variant") or "") for r in rows if isinstance(r, dict) and r.get("ctx")]
    return {"first": first_attempts(rows), "retention": retention(rows), "remembered": time_to_remembered(rows),
            "calibration": calibration(rows), "funnel": funnel(rows), "experiments": experiments(rows),
            "engagement": engagement(rows)}
