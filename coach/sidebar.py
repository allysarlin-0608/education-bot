"""The sidebar on every page: today's date, today's subject and how much
of today's lessons is done, as liquid rising in an upright glass tube."""
import streamlit as st

from coach import core, curriculum, progress_bar, ui


def render(log: dict) -> None:
    today = ui.today()
    topic = core.scheduled_topic(today)
    plan = curriculum.day_plan(log, topic, core.find_entry(log, today, topic))
    done = sum(1 for s in plan if s.get("completed"))
    progress_bar.render_vertical(
        "sidebar_today", f"{core.weekday_name(today)}\n{today:%B} {today.day}",   # weekday, then the date
        core.TOPICS[topic], done, len(plan), where=st.sidebar)
