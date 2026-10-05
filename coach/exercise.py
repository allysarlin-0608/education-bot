"""One exercise on screen, of any kind (coach/quiz.py), the same in the
lesson's quiz, Review and Practice: the input, and the feedback once it is
marked (right or not said in words, not only colour, and the specific
mistake). UI helper: it draws, it never decides a mark."""
from html import escape

import streamlit as st

from coach import quiz

ORDINALS = ("1st", "2nd", "3rd", "4th", "5th")


def label(k, item) -> str:
    return f"**{k}.** {item['question']}" if k else f"**{item['question']}**"


def kind_tag(item) -> None:
    st.html(f'<p class="ex-kind">{escape(quiz.KIND_NAMES.get(item["type"], ""))}</p>')


def field(item: dict, key: str, value=None, k: int = None, tag: bool = True):
    """Draw the input for one exercise; returns her answer so far (None or
    a list with None while unanswered; "" for an empty text box)."""
    kind = item["type"]
    if tag:
        kind_tag(item)
    if kind == "scenario":
        st.html(f'<p class="ex-scenario">{escape(item["scenario"])}</p>')
    if kind in ("choice", "scenario"):
        return st.radio(label(k, item), range(len(item["options"])), index=value, key=key,
                        format_func=lambda o, item=item: item["options"][o])
    if kind in ("match", "order"):
        st.markdown(label(k, item))
        keys = [f"{key}_{j}" for j in range(len(item["key"]))]
        start = value if isinstance(value, list) and len(value) == len(keys) else [None] * len(keys)
        chosen = [st.session_state.get(kk, start[j]) for j, kk in enumerate(keys)]
        out = []
        names = item["right"] if kind == "match" else item["items"]
        rows = item["left"] if kind == "match" else [f"{ORDINALS[j]}" for j in range(len(keys))]
        for j, row in enumerate(rows):
            # what's already placed elsewhere isn't offered again
            taken = {c for m, c in enumerate(chosen) if m != j and c is not None}
            options = [o for o in range(len(names)) if o not in taken]
            current = chosen[j] if chosen[j] in options else None
            out.append(st.selectbox(row, options, index=options.index(current) if current is not None else None,
                                    placeholder="Choose its match" if kind == "match" else "Choose a step",
                                    format_func=lambda o, names=names: names[o], key=keys[j]))
        return out
    if kind == "blank":
        return st.text_input(label(k, item), value=value or "", key=key, placeholder="The missing word or phrase")
    placeholder = ("One real example from your own life, work or goal"
                   if kind == "apply" else "Answer in a sentence or two, in your own words")
    return st.text_area(label(k, item), value=value or "", key=key, height=90, placeholder=placeholder)


def sign(mark) -> str:
    return "✓" if mark == 1 else ("◐" if mark else "✗")


def verdict(mark) -> str:
    return "Right." if mark == 1 else ("Partly right." if mark else "Not quite.")


def result(item: dict, answer, mark, feedback: str = "", k: int = None, show_question: bool = True) -> None:
    """How she did on one exercise, and why."""
    if show_question:
        st.markdown(f"{sign(mark)} {f'{k}. ' if k else ''}{item['question']}")
    kind = item["type"]
    if kind in ("choice", "scenario"):
        if mark == 1:
            st.caption(f"Your answer: {item['options'][answer]}. {item['why']}".strip())
        else:
            st.caption(f"{quiz.mistake(item, answer)} {item['why']}".strip())
    elif kind in ("match", "order", "blank"):
        miss = quiz.mistake(item, answer)
        if kind == "match" and mark != 1:
            miss = f"{mark * len(item['key']):g} of {len(item['key'])} pairs right. {miss}"
        if kind == "order" and mark != 1:
            miss = f"{mark * len(item['key']):g} of {len(item['key'])} in the right place. {miss}"
        if kind == "blank" and mark == 1 and not miss:
            miss = f"Your answer: {answer}."
        st.caption(f"{miss} {item['why']}".strip())
    else:
        st.caption(f"Your answer: {answer}")
        note = feedback or item["why"]
        if mark == 1:
            st.caption(note)
        else:
            st.caption(("What's missing: " if mark else "Why it's marked wrong: ") + note)
            st.caption(("What a good answer shows: " if kind == "apply" else "A good answer: ") + item["answer"])
