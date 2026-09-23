"""Draws a lesson as separate cards (topic, concept, example, tasks,
question, reminder, disclaimer)."""
import streamlit as st

from coach import core, style


def _card(key, title, body, title_cls="t-headline"):
    with st.container(key=key):
        style.text(title, title_cls)
        if body:
            st.markdown(body)


def render(raw: str, key: str, interactive: bool = True):
    """raw is the saved lesson (JSON, or the older 【…】 text). key keeps
    widget and card keys unique when several lessons are on one page.
    Task checkboxes only exist when interactive (they are for today's
    screen and aren't saved)."""
    lesson = core.parse_lesson(raw)
    if lesson is None:
        with st.container(key=f"card_raw_{key}"):
            st.markdown(raw)
        return
    with st.container(key=f"card_topic_{key}"):
        style.text(lesson["topic"] or "今天的課", "t-large" if interactive else "t-title2")
    if lesson["core_concept"]:
        _card(f"card_concept_{key}", "核心概念", lesson["core_concept"])
    if lesson["example"]:
        _card(f"card_example_{key}", "具體例子", lesson["example"])
    if lesson["tasks"]:
        with st.container(key=f"card_tasks_{key}"):
            style.text("今日任務", "t-headline")
            for i, task in enumerate(lesson["tasks"]):
                if interactive:
                    st.checkbox(task, key=f"task_{key}_{i}")
                else:
                    st.markdown(f"- {task}")
    if lesson["followup_question"]:
        _card(f"card_question_{key}", "延伸提問", lesson["followup_question"])
    if lesson["reminder"]:
        _card(f"card_reminder_{key}", "小提醒", lesson["reminder"])
    if lesson["disclaimer"]:
        with st.container(key=f"card_disclaimer_{key}"):
            st.markdown(lesson["disclaimer"])
    style.text(core.CLOSING_LINE, "t-footnote")
