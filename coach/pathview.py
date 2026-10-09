"""Her learning path, drawn: the order her subjects and goals take turns in
(one a day), and where each one's course goes first. Shared by the setup's
Your path step (views/setup.py) and the Learning Path page (views/path.py),
so both say the same thing the same way. HTML only; no model calls (lesson
titles come from the syllabus, or her goal's path)."""
from html import escape

from coach import catalog, curriculum, settings

SHOWN_UNITS = 3


def turns_html(names: list, pace: int, labels: list = None) -> str:
    """The order of her days: Day 1 → the first, Day 2 → the next… then
    around again. With `labels`, each day is named by them (actual days:
    `names` then is what each of those days is for)."""
    if not names:
        return ""
    labels = labels or [f"Day {k + 1}" for k in range(len(names))]
    rows = "".join(f'<li><span class="pv-day">{escape(lb)}</span><span>{escape(nm)}</span></li>'
                   for lb, nm in zip(labels, names))
    turns = len(dict.fromkeys(names))
    again = ("Every day" if turns == 1 else
             "One a day, taking turns" + ("" if len(labels) > len(names) or labels[0] != "Day 1"
                                           else f"; after day {len(names)} the turns start again"))
    n = pace
    return (f'<div class="pv-turns"><ol>{rows}</ol>'
            f'<p class="ob-note">{escape(again)} · {n} {"lesson" if n == 1 else "lessons"} on each day</p></div>')


def units_of(topic: str) -> list:
    """Its course's units in order: [(name, lessons in it)]."""
    out = []
    for unit, _title in curriculum._load(topic):
        if out and out[-1][0] == unit:
            out[-1] = (unit, out[-1][1] + 1)
        else:
            out.append((unit, 1))
    return out


def outline_html(topic: str, name: str = "", level: str = "", units: list = None) -> str:
    """Where a course goes first: its first units, each with its lessons."""
    units = units if units is not None else units_of(topic)
    shown = units[:SHOWN_UNITS]
    more = len(units) - len(shown)
    name = name or catalog.name(topic)
    items = "".join(f'<li><span>{escape(u)}</span><small>{k} {"lesson" if k == 1 else "lessons"}</small></li>'
                    for u, k in shown)
    tail = (f'<p class="ob-note">…then {more} more {"part" if more == 1 else "parts"}, '
            "each lesson unlocked by passing the one before.</p>" if more > 0 else "")
    return (f'<div class="pv-course"><p class="pv-name">{escape(name)}'
            + (f' <small>· starts at {escape(level)}</small>' if level else "")
            + f'</p><ol class="pv-units">{items}</ol>{tail}</div>')


def subject_outline(topic: str, level: str = "") -> str:
    """A subject of ours (its syllabus file)."""
    if not curriculum.has_syllabus(topic):
        return ""
    return outline_html(topic, level=level or (settings.LEVELS[0]))
