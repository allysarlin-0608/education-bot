"""The sidebar on every page: where she is today. Three quiet steps down:
the day, today's subject (its topic, how far through the day's lessons
she is, as liquid rising in an upright glass tube), then the book she is
reading (when she has a reading plan). The pages themselves are in the control at the top."""
from html import escape

import streamlit as st

from coach import books, core, curriculum, progress_bar, settings, shelf, steps, ui


def _reading(log: dict) -> str:
    book = books.current_book(log.get("books", []))
    if not book:
        return ('<hr class="sb-rule"><div class="sb-label">Reading</div>'
                '<div class="sb-quiet">No book in progress</div>')
    reading_days = [d for d in range(1, books.DAYS + 1) if book["plan"][d - 1]]
    done = sum(1 for d in reading_days if str(d) in book["checks"])
    pct = progress_bar.percent(done, len(reading_days))
    return ('<hr class="sb-rule"><div class="sb-label">Reading</div>'
            f'<div class="sb-book">{escape(book["title"] or "(untitled)")}</div>'
            + (f'<div class="sb-author">{escape(book["author"])}</div>' if book.get("author") else "")
            + f'<div class="sb-line" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}">'
            f'<i style="width:{pct}%"></i></div>'
            f'<div class="sb-meta">{escape(shelf.line_label(book))}</div>')


def render(log: dict) -> None:
    today, config = ui.today(), ui.config()
    topic = ui.topic_for(today)
    plan = curriculum.day_plan(log, topic, core.find_entry(log, today, topic), settings.units(config))
    done = sum(1 for s in plan if s.get("completed"))
    unit = curriculum.unit_progress(log, topic)["unit"] if curriculum.has_syllabus(topic) else None
    progress_bar.render_vertical(
        "sidebar_today", f"{core.weekday_name(today)}, {today:%B} {today.day}",
        core.TOPICS[topic], done, len(plan), where=st.sidebar,
        topic=unit, count=steps.label(plan) if plan else None,
        after=_reading(log) if settings.reading_on(config) else "")
