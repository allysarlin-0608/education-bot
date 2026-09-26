"""The stage: the subject in focus, large, beside the list of subjects (the
setup's Subjects step, and Settings).

One subject is in focus at a time: the row the lens lies over, which is the
page's own record of it (the setup's ob_focus, Settings' set_focus). The
stage is drawn with that subject already showing (data-focus), so it never
opens on another; every subject is drawn once, a layer each, all from
visuals.subject(), and the page (motion.py) only moves data-focus when a row
is touched, so a subject's name, words, object and state always arrive and
leave together."""
from html import escape

from coach import settings, visuals


def html(focus: str, group: str) -> str:
    """group: the list of rows it follows (choices.rows' group)."""
    layers = []
    for t in settings.SUBJECTS:
        s = visuals.subject(t)
        f = s["facts"]
        layers.append(
            f'<div class="sg-layer" data-t="{t}" aria-hidden="{"false" if t == focus else "true"}">'
            + visuals.object_html(t, "sg-art", s["number"])
            + f'<div class="sg-head sg-title-{s["title_style"]}">'
            f'<p class="sg-kicker">{s["number"]:02d} · {escape(s["kicker"])}</p>'
            f'<p class="sg-title">{escape(s["title"])}</p></div>'
            f'<div class="sg-copy"><p class="sg-desc">{escape(s["description"])}</p>'
            f'<p class="sg-meta">{f["units"]} topics · {f["lessons"]} lessons · begins with {escape(f["first"])}</p>'
            f'<p class="sg-state" data-on="0">Not chosen</p>'
            + (f'<p class="sg-credit">{escape(s["credit"])}</p>' if s["credit"] else "")
            + "</div></div>")
    return (f'<div class="sg-stage" data-focus="{escape(focus)}" data-group="{escape(group)}" role="region" '
            f'aria-label="The subject in focus" aria-live="polite">{"".join(layers)}</div>')


def focus_of(looked_at, chosen) -> str:
    """The subject in focus: the one she last touched; before she has touched
    any, her last chosen one, else the first in the list (a state of its
    own, drawn and marked as such: the lens lies on it too)."""
    if looked_at in settings.SUBJECTS:
        return looked_at
    return chosen[-1] if chosen else settings.SUBJECTS[0]


def rows() -> list:
    """The list of subjects beside the stage, from the same records."""
    return [(s["key"], s["title"], s["description"], {"n": s["number"]})
            for s in map(visuals.subject, settings.SUBJECTS)]
