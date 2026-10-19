"""Report a problem (audit stage 2): under a lesson, and with a quiz's
results. A small menu: what's wrong (a few reasons), an optional note, Send.
What is sent (coach/reports.py) names the lesson and quotes the question or
the start of the lesson, so it can be checked; never her answers. Used by
views/daily.py and views/course.py."""
from html import escape

import streamlit as st

from coach import reports, storage
from coach.i18n import N_, tr

THANKS = N_("Thanks. We'll check it.")


def _send(report: dict) -> str:
    """Store it; '' when sent, else why not (said beside the button)."""
    store = st.session_state.get("coach_store")
    if report is None or not hasattr(store, "add_report"):
        return tr("This couldn't be sent.")
    try:
        store.add_report(report)
    except storage.StorageError as e:
        return tr("It couldn't be sent ({e}). Try again later.", e=e)
    return ""


def _form(key: str, reasons: tuple, on_send, choices: list = None) -> None:
    """The menu's inside: (which question,) the reason, a note, Send."""
    done = st.session_state.pop(f"{key}_said", None)
    if done is not None:
        st.html(f'<p class="ob-note" role="status">{escape(done or tr(THANKS))}</p>')
    pick = None
    if choices:
        pick = st.selectbox(tr("Which question?"), range(len(choices)), key=f"{key}_which",
                            format_func=lambda i: f"{i + 1}. {choices[i][:70]}")
    reason = st.radio(tr("What's the problem?"), reasons, key=f"{key}_why", format_func=lambda r: tr(reports.REASONS[r]), index=None)
    note = st.text_input(tr("Anything to add? (optional)"), key=f"{key}_note", max_chars=300)
    if st.button(tr("Send"), key=f"{key}_send", type="primary", disabled=reason is None):
        said = on_send(reason, note, pick)
        st.session_state[f"{key}_said"] = said
        for k in (f"{key}_why", f"{key}_note"):
            st.session_state.pop(k, None)
        st.rerun()


def lesson(key: str, topic: str, n: int, title: str, text: str) -> None:
    """Report a problem with this lesson."""
    with st.popover(tr("Report a problem"), key=f"{key}_menu"):
        _form(key, reports.LESSON_REASONS,
              lambda reason, note, _: _send(reports.make(topic, n, title, "lesson", reason, (text or "")[:600], note)))


def question(key: str, topic: str, n: int, title: str, questions: list, on_reported=None) -> None:
    """Report a problem with one of a quiz's questions; on_reported(question)
    is told once it is sent (its review card goes)."""
    texts = [q.get("question", "") for q in questions]

    def send(reason, note, i):
        said = _send(reports.make(topic, n, title, "question", reason, texts[i], note))
        if not said and on_reported:
            on_reported(texts[i])
        return said
    with st.popover(tr("Report a question"), key=f"{key}_menu"):
        _form(key, reports.QUESTION_REASONS, send, choices=texts)
