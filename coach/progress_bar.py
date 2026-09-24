"""The course progress bar: a thin line of pale air-blue liquid in clear
glass (its CSS lives in coach/style.py). When the value changes the liquid
flows from where it was last shown to where it is now; otherwise it is
still."""
from html import escape

import streamlit as st


def percent(done: int, total: int) -> int:
    return round(done / total * 100) if total else 0


def build(title: str, done: int, total: int, meta: str = "", *, previous=None,
          label: str = "Course progress", compact: bool = False) -> str:
    pct = percent(done, total)
    classes = ["lq"]
    if compact:
        classes.append("compact")
    if pct == 0:
        classes.append("empty")
    if previous is not None and previous != pct:
        classes.append("flowing")
    lessons = f"{done} / {total} {'lesson' if total == 1 else 'lessons'}"
    extra = f"<span>{escape(meta)}</span>" if meta else ""
    return (
        f'<section class="{" ".join(classes)}" style="--to:{pct};--from:{previous or 0}" '
        f'role="group" aria-label="{escape(label)}">'
        f'<div class="lq-label">{escape(label)}</div>'
        f'<div class="lq-head"><div class="lq-title">{escape(title)}</div>'
        f'<div class="lq-pct" aria-hidden="true">{pct}<span>%</span></div></div>'
        f'<div class="lq-glass" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
        f'aria-valuenow="{pct}" aria-valuetext="{pct}% · {done} of {total} lessons">'
        f'<div class="lq-liquid"></div></div>'
        f'<div class="lq-meta"><span>{lessons}</span>{extra}</div>'
        "</section>"
    )


def render(key: str, title: str, done: int, total: int, meta: str = "", **kwargs):
    """Show the bar; it flows only if this session last showed it at a
    different value."""
    shown = st.session_state.setdefault("lq_shown", {})
    previous = shown.get(key)
    shown[key] = percent(done, total)
    st.html(build(title, done, total, meta, previous=previous, **kwargs))
