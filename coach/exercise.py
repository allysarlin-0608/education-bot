"""One exercise on screen, of any kind (coach/quiz.py), the same in the
lesson's quiz, Review and Practice: the input, and the feedback once it is
marked (right or not said in words, not only colour, and the specific
mistake). UI helper: it draws, it never decides a mark."""
from html import escape

import streamlit as st

from coach import quiz
from coach.i18n import tr

ORDINALS = ("1st", "2nd", "3rd", "4th", "5th")


def label(k, item) -> str:
    return f"**{k}.** {item['question']}" if k else f"**{item['question']}**"


def kind_tag(item) -> None:
    st.html(f'<p class="ex-kind">{escape(tr(quiz.KIND_NAMES[item["type"]]) if item["type"] in quiz.KIND_NAMES else "")}</p>')


def field(item: dict, key: str, value=None, k: int = None, tag: bool = True):
    """Draw the input for one exercise; returns her answer so far (None or
    a list with None while unanswered; "" for an empty text box)."""
    kind = item["type"]
    if tag:
        kind_tag(item)
    if kind == "scenario":
        st.html(f'<p class="ex-scenario">{escape(item["scenario"])}</p>')
    if kind in quiz.CHOICE_LIKE:
        return st.radio(label(k, item), range(len(item["options"])), index=value, key=key,
                        format_func=lambda o, item=item: item["options"][o])
    if kind == "spot":
        # the worked lines, numbered, then which one is wrong
        st.markdown(label(k, item))
        st.html('<ol class="ex-lines">' + "".join(f"<li>{escape(x)}</li>" for x in item["lines"]) + "</ol>")
        return st.radio(tr("The line with the mistake"), range(len(item["lines"])), index=value, key=key,
                        format_func=lambda o: tr("Line {n}", n=o + 1), horizontal=True)
    if kind == "steps":
        # the worked example: the steps shown, the gaps hers to fill
        st.markdown(label(k, item))
        out, j = [], 0
        start = value if isinstance(value, list) and len(value) == len(item["answers"]) else [""] * len(item["answers"])
        for n, line in enumerate(item["steps"], start=1):
            if "____" in line:
                out.append(st.text_input(f"{n}. {line}", value=start[j] or "", key=f"{key}_{j}",
                                         placeholder=tr("What goes in the gap")))
                j += 1
            else:
                st.html(f'<p class="ex-step"><span>{n}.</span> {escape(line)}</p>')
        return out
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
                                    placeholder=tr("Choose its match") if kind == "match" else tr("Choose a step"),
                                    format_func=lambda o, names=names: names[o], key=keys[j]))
        return out
    if kind == "blank":
        return st.text_input(label(k, item), value=value or "", key=key, placeholder=tr("The missing word or phrase"))
    placeholder = (tr("One real example from your own life, work or goal")
                   if kind == "apply" else tr("Answer in a sentence or two, in your own words"))
    return st.text_area(label(k, item), value=value or "", key=key, height=90, placeholder=placeholder)


def sign(mark) -> str:
    return "✓" if mark == 1 else ("◐" if mark else "✗")


def verdict(mark) -> str:
    return tr("Right.") if mark == 1 else (tr("Partly right.") if mark else tr("Not quite."))


def result(item: dict, answer, mark, feedback: str = "", k: int = None, show_question: bool = True) -> None:
    """How she did on one exercise, and why."""
    if show_question:
        st.markdown(f"{sign(mark)} {f'{k}. ' if k else ''}{item['question']}")
    kind = item["type"]
    if kind == "spot":
        if mark == 1:
            st.caption((tr("Right: line {n} has the mistake. It should say: {fix}", n=item["answer"] + 1,
                           fix=item["fix"]) + " " + item["why"]).strip())
        else:
            st.caption(f"{quiz.mistake(item, answer)} {item['why']}".strip())
        return
    if kind == "steps":
        filled = iter(item["answers"])
        worked = [line.replace("____", f"**{next(filled)}**") if "____" in line else line for line in item["steps"]]
        st.markdown("\n".join(f"{n}. {line}" for n, line in enumerate(worked, start=1)))
        st.caption(f"{quiz.mistake(item, answer)} {item['why']}".strip())
        return
    if kind in quiz.CHOICE_LIKE:
        if mark == 1:
            st.caption((tr("Your answer: {answer}.", answer=item['options'][answer]) + " " + item['why']).strip())
        else:
            st.caption(f"{quiz.mistake(item, answer)} {item['why']}".strip())
    elif kind in ("match", "order", "blank"):
        miss = quiz.mistake(item, answer)
        if kind == "match" and mark != 1:
            miss = tr("{right} of {n} pairs right.", right=f"{mark * len(item['key']):g}", n=len(item['key'])) + " " + miss
        if kind == "order" and mark != 1:
            miss = tr("{right} of {n} in the right place.", right=f"{mark * len(item['key']):g}", n=len(item['key'])) + " " + miss
        if kind == "blank" and mark == 1 and not miss:
            miss = tr("Your answer: {answer}.", answer=answer)
        st.caption(f"{miss} {item['why']}".strip())
    else:
        st.caption(tr('Your answer: {answer}', answer=answer))
        note = feedback or item["why"]
        if mark == 1:
            st.caption(note)
        else:
            st.caption(tr("What's missing: {note}", note=note) if mark else tr("Why it's marked wrong: {note}", note=note))
            st.caption(tr("What a good answer shows: {answer}", answer=item["answer"]) if kind == "apply"
                       else tr("A good answer: {answer}", answer=item["answer"]))
