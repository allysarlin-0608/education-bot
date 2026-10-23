"""Mastery before moving on (docs/LEARNING_DESIGN.md §4; Bloom's mastery
learning): a unit that later units build on has to be shown as learned as
a whole (its unit check, coach/unitcheck.py, 80%) before they open.

- Which units a unit builds on: for mathematics, its prerequisites in the
  curriculum file; for a goal's path or a subject, the unit before it.
- A unit is cleared when its check is passed; when every lesson in it was
  skipped as already known (the diagnostic, coach/diagnostic.py); when it
  has too few questions to make a check of (nothing to ask: it doesn't
  hold her up); or when she finished it before this came in (SWITCH: no
  one already on her way is stopped for units she finished under the old
  rules).
- The gate: her next lesson opens a unit that builds on a finished unit not
  cleared yet. Home then points to that check (and, when she misses it, to
  the corrective practice on the ideas she missed, then a fresh set).
  Every check can be taken straight away: that is also how she tests out.
Pure functions; no AI call."""
from coach import course, curriculum, mastery, unitcheck

SWITCH = mastery.SWITCH.isoformat()


def prerequisites(topic: str, units: list) -> dict:
    """{unit name: [names of the units it builds on]}."""
    names = [u["name"] for u in units]
    if topic == "math":
        from coach import mathcourse
        known = mathcourse.units()
        by_id = {n.split(" ")[0]: n for n in names}
        return {n: [by_id[p] for p in (known.get(n.split(" ")[0]) or {}).get("prerequisites", []) if p in by_id]
                for n in names}
    return {n: names[k - 1:k] for k, n in enumerate(names)}


def _passed_on(u: dict) -> str:
    return max((x.get("passed") or "" for x in u["lessons"]), default="")


def cleared(log: dict, topic: str, u: dict) -> bool:
    if u.get("state") != "done":
        return False
    skipped = set(curriculum.skipped(log, topic))
    if all(x["n"] in skipped for x in u["lessons"]):
        return True
    unit = dict(u, key=f"u{u['first']}")
    if unitcheck.result(log, topic, unit).get("passed_on"):
        return True
    if not unitcheck.offered(log, topic, unit):
        return True
    last = _passed_on(u)
    return bool(last) and last[:10] < SWITCH


def gate(log: dict, topic: str):
    """The finished unit, not cleared yet, that her next lesson's unit builds
    on (with "key" for its check page), or None."""
    if not curriculum.has_syllabus(topic):
        return None
    m = course.build(log, topic)
    if m["next"] is None:
        return None
    units = m["units"]
    here = next((u for u in units if u["first"] <= m["next"] <= u["last"]), None)
    if here is None:
        return None
    by_name = {u["name"]: u for u in units}
    for name in prerequisites(topic, units).get(here["name"], []):
        u = by_name.get(name)
        if u is not None and u["state"] == "done" and not cleared(log, topic, u):
            return dict(u, key=f"u{u['first']}", opens=here["name"])
    return None
