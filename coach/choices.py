"""The choices in the setup and on Settings, drawn the same way in both.

- rows(): a list of options, one row each (a name, a line under it). The
  whole row is the button. The one chosen shows it three ways, not by
  colour alone: a check drawn at the right, a short rule at the left, and
  its name in a heavier weight (style.py). A tap changes the row at once
  (motion.py) and the page follows.
- placement(): the five-question check that sets where a subject starts,
  one question at a time. It keeps its answers in the caller's settings,
  never in the learning log.

Every change goes through a callback, so the page redraws once, already
changed."""
import html

import streamlit as st

from coach import placement as pq

BASICS, PLACEMENT = "basics", "placement"
WAYS = {BASICS: "Start from the basics", PLACEMENT: "I know some already"}


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def rows(group: str, items: list, chosen, on_pick, *, multi: bool = False, full: bool = False,
         args: tuple = ()) -> None:
    """items: [(key, name, line under it)]. `chosen`: the keys chosen.
    With `full`, the rows not chosen can't be picked (a limit is reached).
    A tap calls on_pick(*args, key)."""
    with st.container(key=f"optlist_{group}", gap=None):
        for key, name, sub in items:
            on = key in chosen
            state = "sel" if on else "dis" if full else "unsel"
            with st.container(key=f"opt_{group}_{key}__{state}", gap=None):
                st.html(f'<div class="opt" data-multi="{int(multi)}"><span class="opt-t">{_e(name)}</span>'
                        + (f'<span class="opt-s">{_e(sub)}</span>' if sub else "")
                        + '<span class="opt-mark" aria-hidden="true"></span></div>')
                # the row's button, stretched over it; its words are for screen readers
                st.button(f"{name}, selected" if on else name, key=f"pick_{group}_{key}",
                          disabled=state == "dis", on_click=on_pick, args=(*args, key))


def way_switch(key: str, way: str, on_change, args: tuple = ()) -> None:
    """Start from the basics | I know some already, for one subject."""
    with st.container(key=f"sw_{key}"):
        st.segmented_control("Where to start", list(WAYS), default=way, format_func=WAYS.get,
                             key=key, required=True, label_visibility="collapsed", width="stretch",
                             on_change=on_change, args=args)


def placement(key: str, topic: str, check: dict, on_answer, on_move, on_again) -> None:
    """The check for one subject: a question at a time, or once finished,
    the level it gives. `check`: {"answers", "at", "level", "score"}.
    on_answer(option), on_move(step) (+1 on, -1 back; past the last it
    finishes), on_again() starts it over."""
    qs = pq.questions(topic)
    if check.get("level"):
        with st.container(key=f"pqdone_{key}", horizontal=True, vertical_alignment="center"):
            st.html(f'<p class="pq-result"><b>{_e(check["level"])}</b>'
                    f'<span>{check["score"]} of {pq.COUNT} right</span></p>')
            st.button("Take it again", key=f"pqagain_{key}", type="tertiary", on_click=on_again)
        return
    at = min(max(check.get("at") or 0, 0), pq.COUNT - 1)
    answers = (list(check.get("answers") or []) + [None] * pq.COUNT)[:pq.COUNT]
    question, options, _ = qs[at]
    # a new container for each question, so the next one comes in on its own
    with st.container(key=f"pq_{key}_{at}", gap=None):
        st.html(f'<p class="pq-count">Question {at + 1} of {pq.COUNT}</p><p class="pq-q">{_e(question)}</p>')
        rows(f"pq{key}{at}", [(i, o, "") for i, o in enumerate(options)],
             {answers[at]} if answers[at] is not None else set(), lambda i: on_answer(i))
        with st.container(key=f"pqnav_{key}", horizontal=True, horizontal_alignment="distribute",
                          vertical_alignment="center"):
            if at:
                st.button("Previous", key=f"pqprev_{key}", type="tertiary", on_click=on_move, args=(-1,))
            else:
                st.html('<span class="pq-gap"></span>')
            st.button("See my level" if at == pq.COUNT - 1 else "Next question", key=f"pqnext_{key}",
                      disabled=answers[at] is None, on_click=on_move, args=(1,))


def answer(check: dict, option: int) -> dict:
    at = min(max(check.get("at") or 0, 0), pq.COUNT - 1)
    answers = (list(check.get("answers") or []) + [None] * pq.COUNT)[:pq.COUNT]
    answers[at] = option
    return dict(check, answers=answers, at=at)


def move(check: dict, topic: str, step: int) -> dict:
    """On to the next question (or back); past the last, the level."""
    at = min(max(check.get("at") or 0, 0), pq.COUNT - 1)
    answers = (list(check.get("answers") or []) + [None] * pq.COUNT)[:pq.COUNT]
    if step > 0 and answers[at] is None:
        return check
    if step > 0 and at == pq.COUNT - 1:
        right = pq.score(topic, answers)
        return dict(check, answers=answers, at=at, score=right, level=pq.level_for(right))
    return dict(check, answers=answers, at=min(max(at + step, 0), pq.COUNT - 1))


def fresh() -> dict:
    return {"answers": [], "at": 0, "level": None, "score": None}
