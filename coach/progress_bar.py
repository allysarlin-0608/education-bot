"""The course progress bar: a thin line of pale air-blue liquid in clear
glass (its CSS lives in coach/style.py). The liquid flows in each time she
arrives on a page, and from its last value whenever the value changes;
otherwise it is still."""
from html import escape

import streamlit as st


def percent(done: int, total: int) -> int:
    return round(done / total * 100) if total else 0


def count(done: int, total: int, noun: str = "lesson") -> str:
    return f"{done} / {total} {noun if total == 1 else noun + 's'}"


def entering() -> bool:
    """True on the first run after arriving on a page (set by the app)."""
    return st.session_state.get("lq_entering", True)


def build(title: str, done: int, total: int, meta: str = "", *, previous=None,
          label: str = "Course progress", compact: bool = False, noun: str = "lesson",
          bar: bool = True) -> str:
    """The block: label, title and percentage, then (with bar=True) the
    liquid line and a count."""
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
        f'role="group" aria-label="{escape(label)}">',
        f'<div class="lq-label">{escape(label)}</div>',
        f'<div class="lq-head"><div class="lq-title">{escape(title)}</div>'
        f'<div class="lq-pct" aria-hidden="true">{pct}<span>%</span></div></div>',
    ]
    if bar:
        parts += [
            f'<div class="lq-glass" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
            f'aria-valuenow="{pct}" aria-valuetext="{pct}% · {count(done, total, noun)}">'
            f'<div class="lq-liquid"></div></div>',
            meta_row(count(done, total, noun), meta),
        ]
    parts.append("</section>")
    return "".join(parts)


def meta_row(left: str, right: str = "") -> str:
    extra = f"<span>{escape(right)}</span>" if right else ""
    return f'<div class="lq-meta"><span>{escape(left)}</span>{extra}</div>'


def render(key: str, title: str, done: int, total: int, meta: str = "", **kwargs):
    """Show the bar. It flows in from empty on arriving at the page, and
    from where it was when the value has changed since."""
    shown = st.session_state.setdefault("lq_shown", {})
    previous = 0 if entering() else shown.get(key, 0)
    shown[key] = percent(done, total)
    st.html(build(title, done, total, meta, previous=previous, **kwargs))


def lesson_motion(key: str, done_flags: list) -> str:
    """How the lesson bar on Today should move this run: "flow" (fill up
    lesson by lesson, on arriving), "tickN" (lesson N just filled) or
    "still"."""
    shown = st.session_state.setdefault("lq_lessons", {})
    before = shown.get(key)
    shown[key] = list(done_flags)
    if entering() or before is None or len(before) != len(done_flags):
        return "flow"
    new = [k for k, (was, now) in enumerate(zip(before, done_flags), 1) if now and not was]
    return f"tick{new[0]}" if len(new) == 1 else ("flow" if new else "still")
