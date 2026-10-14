"""The math curriculum, from zero to research (data/math_curriculum_zh-Hant.json).

A reference curriculum to browse, not a course she takes: phases (L0–L7) in
order, each with its units: a summary, what she will be able to do, what to
practise, the units to know first, and where the material comes from (the
sources list, linked). Read from the file once; nothing here calls the model
or writes anything. The page is views/math.py; check() is what the tests and
tools/check.sh hold the file to (every prerequisite and source it names
exists, ids are unique, no unit needs itself through a loop). A unit may
need one listed after it in its phase (multivariable calculus needs linear
algebra): the order in a phase is not the order to learn it in, the
prerequisites are."""
import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "math_curriculum_zh-Hant.json"


@lru_cache(maxsize=None)
def load(path: str = str(PATH)) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def phases(data: dict = None) -> list:
    return (data or load())["phases"]


def units(data: dict = None) -> dict:
    """Every unit by its id, in order, each with its phase's id."""
    out = {}
    for p in phases(data):
        for u in p["units"]:
            out[u["id"]] = dict(u, phase=p["id"])
    return out


def sources(data: dict = None) -> dict:
    return {s["id"]: s for s in (data or load())["sources"]}


def prerequisites(uid: str, data: dict = None) -> list:
    """The units to know before this one (the ones that exist)."""
    every = units(data)
    return [every[k] for k in every.get(uid, {}).get("prerequisites", []) if k in every]


def leads_to(uid: str, data: dict = None) -> list:
    """The units that name this one as a prerequisite."""
    return [u for u in units(data).values() if uid in u.get("prerequisites", [])]


def sources_of(unit: dict, data: dict = None) -> list:
    known = sources(data)
    return [known[k] for k in unit.get("sources", []) if k in known]


def phase_of(uid: str, data: dict = None):
    """The phase id a unit is in (None: no such unit)."""
    return units(data).get(uid, {}).get("phase")


def counts(data: dict = None) -> dict:
    return {"phases": len(phases(data)), "units": len(units(data)), "sources": len(sources(data))}


def check(data: dict = None) -> list:
    """What is wrong with the file, one line each ([] when nothing)."""
    data = data or load()
    problems, seen, order = [], set(), {}
    known = sources(data)
    for p in data.get("phases", []):
        for key in ("id", "title", "level", "goal", "units"):
            if not p.get(key):
                problems.append(f"phase {p.get('id', '?')}: no {key}")
        for u in p.get("units", []):
            uid = u.get("id", "?")
            if uid in seen:
                problems.append(f"{uid}: id used twice")
            seen.add(uid)
            order[uid] = len(order)
            for key in ("title", "summary", "learning_outcomes", "practice_focus", "sources"):
                if not u.get(key):
                    problems.append(f"{uid}: no {key}")
    for u in units(data).values():
        for k in u.get("prerequisites", []):
            if k not in order:
                problems.append(f"{u['id']}: prerequisite {k} isn't a unit")
        for k in u.get("sources", []):
            if k not in known:
                problems.append(f"{u['id']}: source {k} isn't listed")
    for uid in order:
        if _loops(uid, data):
            problems.append(f"{uid}: needs itself through its prerequisites")
    for s in known.values():
        if not str(s.get("url", "")).startswith("https://"):
            problems.append(f"source {s['id']}: no https link")
    return problems


def _loops(uid: str, data: dict) -> bool:
    every, stack, seen = units(data), list(units(data).get(uid, {}).get("prerequisites", [])), set()
    while stack:
        k = stack.pop()
        if k == uid:
            return True
        if k not in seen and k in every:
            seen.add(k)
            stack += every[k].get("prerequisites", [])
    return False
