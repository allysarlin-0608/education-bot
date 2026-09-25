"""The course progress bar: a thin line of pale air-blue liquid in clear
glass (its CSS lives in coach/style.py). The liquid flows in each time she
arrives on a page, and from its last value whenever the value changes;
otherwise it is still."""
from html import escape

import streamlit as st

from coach import rolling


def percent(done: int, total: int) -> int:
    return round(done / total * 100) if total else 0


def count(done: int, total: int, noun: str = "lesson") -> str:
    return f"{done} / {total} {noun if total == 1 else noun + 's'}"


def entering() -> bool:
    """True on the first run after arriving on a page (set by the app)."""
    return st.session_state.get("lq_entering", True)


def build(title: str, done: int, total: int, meta: str = "", *, previous=None,
          label: str = "Course progress", compact: bool = False, noun: str = "lesson",
          bar: bool = True, left: str = None, old: dict = None, topic: str = None) -> str:
    """The block: label, title and percentage, then (with bar=True) the
    liquid line and a count. For a subject, the title is the subject and
    `topic` (the unit she is in) sits underneath it as the detail."""
    pct = percent(done, total)
    classes = ["lq"]
    if compact:
        classes.append("compact")
    if pct == 0:
        classes.append("empty")
    if previous is not None and previous != pct:
        classes.append("flowing")
    parts = [
        f'<section class="{" ".join(classes)}" style="--to:{pct};--from:{previous or 0}" '
        f'role="group" aria-label="{escape(label or title)}">',
        f'<div class="lq-label">{escape(label)}</div>',
        f'<div class="lq-head"><div class="lq-title">{escape(title)}</div>'
        f'<div class="lq-pct" aria-hidden="true">{rolling.html(pct, (old or {}).get("pct"))}<span class="unit">%</span></div></div>',
    ]
    if not label:
        parts.pop(1)
    if topic:
        parts.append(f'<div class="lq-topic"><span class="lq-topic-label">Topic</span>'
                     f'<span class="lq-topic-name">{escape(topic)}</span></div>')
    if bar:
        parts += [
            f'<div class="lq-glass" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
            f'aria-valuenow="{pct}" aria-valuetext="{pct}% · {count(done, total, noun)}">'
            f'<div class="lq-liquid"></div></div>',
            meta_row(left or count(done, total, noun), meta, old=old),
        ]
    parts.append("</section>")
    return "".join(parts)


def meta_row(left: str, right: str = "", old: dict = None) -> str:
    old = old or {}
    extra = f"<span>{rolling.html(right, old.get('right'))}</span>" if right else ""
    return f'<div class="lq-meta"><span>{rolling.html(left, old.get("left"))}</span>{extra}</div>'


def _previous(key: str, pct: int) -> int:
    """Where the liquid flows from: empty on arriving at the page,
    otherwise the value last shown."""
    shown = st.session_state.setdefault("lq_shown", {})
    previous = 0 if entering() else shown.get(key, 0)
    shown[key] = pct
    return previous


def seen(key: str, **texts) -> dict:
    """What the numbers roll from: 0 when she arrives on the page (they
    count up together with the liquid flowing in), otherwise the value last
    shown, so later they roll only when they have really changed."""
    old = rolling.remember(st.session_state.setdefault("lq_texts", {}), key, **texts)
    if entering():
        return {k: rolling.zeroed(v) for k, v in texts.items()}
    return old


def render(key: str, title: str, done: int, total: int, meta: str = "", **kwargs):
    """Show the bar. It flows in from empty on arriving at the page, and
    from where it was when the value has changed since; changed numbers
    roll."""
    pct = percent(done, total)
    left = kwargs.get("left") or count(done, total, kwargs.get("noun", "lesson"))
    old = seen(key, pct=pct, left=left, right=meta)
    st.html(build(title, done, total, meta, previous=_previous(key, pct), old=old, **kwargs))


def today_count(done: int, total: int) -> str:
    return f"{done} of {total} {'lesson' if total == 1 else 'lessons'} today" if total else "No lessons left to do"


def build_vertical(heading: str, subject: str, done: int, total: int, *, previous=None, old: dict = None) -> str:
    """Today in the sidebar: an upright glass tube the liquid rises in, with
    the date, the subject, the percentage and the lesson count beside it."""
    pct = percent(done, total)
    old = old or {}
    classes = ["lqv"] + (["empty"] if pct == 0 else []) + (
        ["flowing"] if previous is not None and previous != pct else [])
    count = today_count(done, total)
    return (
        f'<section class="{" ".join(classes)}" style="--to:{pct};--from:{previous or 0}" '
        f'role="group" aria-label="Today">'
        f'<div class="lqv-tube" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
        f'aria-valuenow="{pct}" aria-valuetext="{pct}% · {escape(count)}"><div class="lqv-liquid"></div></div>'
        f'<div class="lqv-info"><div class="lqv-date">{escape(heading)}</div>'
        f'<div class="lqv-subject">{escape(subject)}</div>'
        f'<div class="lqv-pct" aria-hidden="true">{rolling.html(pct, old.get("pct"))}<span class="unit">%</span></div>'
        f'<div class="lqv-count">{rolling.html(count, old.get("count"))}</div></div>'
        "</section>"
    )


def render_vertical(key: str, heading: str, subject: str, done: int, total: int, where=st):
    pct = percent(done, total)
    old = seen(key, pct=pct, count=today_count(done, total))      # the date doesn't roll
    where.html(build_vertical(heading, subject, done, total, previous=_previous(key, pct), old=old))


def rolled(key: str, text: str) -> str:
    """`text` as HTML whose numbers roll: up from 0 on arriving at the page
    or when they first appear (a new quiz score), and from their last value
    when they change."""
    old = seen(key, t=text).get("t")
    return rolling.html(text, rolling.zeroed(text) if old is None else old)
