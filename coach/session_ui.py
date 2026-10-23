"""The parts of today's session on screen (coach/session.py; views/daily.py
puts them in order). UI helpers: they draw and report what she did; the
page decides and saves.

- check buttons that ask how sure she is: one tap answers and rates it
  (guessing, fairly sure, sure), so calibration costs her no extra step;
- one exercise with a second try: a first miss shows the mistake behind her
  answer and a hint (never the answer), then she tries again; after that,
  the answer and why;
- the warm-up and the mixed practice: one item at a time from a saved set;
- the stepper (read, practise, check) and the day's reflection."""
import time
from datetime import date
from html import escape

import streamlit as st

from coach import attempts, catalog, exercise, learner, mastery, quiz, review, session, ui
from coach.i18n import N_, tr, trn

CONF_LABELS = {1: N_("Guessing"), 2: N_("Fairly sure"), 3: N_("Sure")}
JOL_LABELS = {1: N_("Not yet"), 2: N_("Mostly"), 3: N_("Yes, clearly")}
STEP_NAMES = {"learn": N_("Read"), "practice": N_("Practise"), "check": N_("Check")}


# ------------------------------------------------------------------ timing
def shown(key: str) -> None:
    """When an item first came on screen (for how long it took)."""
    st.session_state.setdefault("ss_t0", {}).setdefault(key, time.monotonic())


def seconds(key: str):
    t0 = st.session_state.get("ss_t0", {}).pop(key, None)
    return round(time.monotonic() - t0) if t0 else None


# ----------------------------------------------------------- answering one
def confidence_buttons(key: str, ready: bool, ask: bool = True):
    """The way to check an answer. Asked: three buttons, one per how sure she
    is (pressing one checks it), returning 1-3; not asked (a second try): one
    "Check again", returning 0. None until pressed."""
    if not ask:
        pressed = st.button(tr("Check again"), type="primary", key=f"{key}_again", disabled=not ready, width="stretch")
        return 0 if pressed else None
    st.html('<p class="ss-ask">' + tr("How sure are you? Your answer is checked when you choose.") + "</p>")
    chosen = None
    with st.container(horizontal=True, key=f"ssconf_{key}", gap="small"):
        for c in (1, 2, 3):
            if st.button(tr(CONF_LABELS[c]), key=f"{key}_conf{c}", disabled=not ready, width="stretch"):
                chosen = c
    return chosen


def miss_note(item: dict, answer) -> str:
    """After a first miss: the mistake behind her answer, without the answer."""
    if item["type"] in quiz.CHOICE_LIKE and isinstance(answer, int):
        note = (item.get("notes") or [""] * len(item["options"]))[answer]
        return note or tr("That option doesn't fit.")
    if item["type"] == "spot":
        return tr("That line is right as it is.")
    if item["type"] == "steps":
        wrong = [j + 1 for j, a in enumerate(answer or []) if quiz.gap_result(item, j, a) == "wrong"]
        return trn("Gap {gaps} isn't right yet.", "Gaps {gaps} aren't right yet.", len(wrong),
                   gaps=", ".join(map(str, wrong))) if wrong else ""
    return tr("Some of it isn't right yet.")


def exercise_try(item: dict, key: str, tries: int, answer=None, tag: bool = True):
    """One exercise to answer (a first try, or a second after the hint).
    Returns (answer, confidence or None) once she checks it, else None."""
    if tries == 1:
        note = miss_note(item, answer)
        hint = item.get("hint") or ""
        st.html('<div class="ss-hint" role="status"><p><b>' + tr("Not quite.") + "</b> " + escape(note) + "</p>"
                + (f'<p><span>{tr("Hint")}</span>{escape(hint)}</p>' if hint else "")
                + "<p>" + tr("Try once more.") + "</p></div>")
    shown(f"{key}_{tries}")
    value = exercise.field(item, f"{key}_t{tries}", None, tag=tag and tries == 0)
    c = confidence_buttons(f"{key}_{tries}", quiz.answered(item, value), ask=tries == 0)
    if c is None:
        return None
    return value, (c or None)


def exercise_done(item: dict, answer, mark, tries: int) -> None:
    """How it went, and why (the answer is shown once it's done)."""
    right_first = mark == 1 and tries == 1
    said = (tr("Right.") if right_first else tr("Right on the second try.") if mark == 1
            else tr("Partly right.") if mark else tr("Not this time. Here's how it goes:"))
    st.html(f'<p class="ss-verdict">{exercise.sign(mark)} {escape(said)}</p>')
    exercise.result(item, answer, mark, show_question=False)


def row(day: date, topic: str, n: int, ctx: str, item: dict, score, first: bool, conf, secs, gap, variants=()):
    return attempts.row(day, topic, n, ctx, item["type"] if item["type"] in attempts.KINDS else "choice",
                        score=score, first=first, conf=conf, secs=secs, gap=gap, diff=item.get("diff"),
                        variants=variants)


# ---------------------------------------------------------------- the stepper
def stepper(now: str, passed: bool) -> None:
    """Where she is in the lesson: read, practise, check (words, not only a dot)."""
    k = session.STAGES.index(now)
    cells = []
    for j, name in enumerate(session.STAGES):
        state = "done" if passed or j < k else ("now" if j == k else "next")
        label = tr(STEP_NAMES[name])
        mark = "✓" if state == "done" else str(j + 1)
        cells.append(f'<li class="ss-step ss-{state}"' + (' aria-current="step"' if state == "now" else "")
                     + f'><span class="ss-dot">{mark}</span><span class="ss-name">{escape(label)}</span></li>')
    st.html('<ol class="ss-steps" aria-label="' + escape(tr("This lesson's steps")) + '">' + "".join(cells) + "</ol>")


def eyebrow(text: str, sub: str = "") -> None:
    st.html(f'<p class="hb-eyebrow">{escape(text)}</p>' + (f'<p class="ss-sub">{escape(sub)}</p>' if sub else ""))


def pace(done: int, n: int) -> None:
    share = done / n if n else 1
    st.html(f'<div class="rv-pace"><div class="rv-line"><span style="width:{share * 100:.0f}%"></span></div><p>'
            + tr("{done} of {n} done", done=done, n=n) + "</p></div>")


# --------------------------------------------- a card or exercise from a set
def card_item(log: dict, card: dict):
    """A review card as something to answer: (item, recall) where recall is
    (prompt, answer) for a card she recalls and rates herself."""
    if card["kind"] == "question" and card["question"]["type"] in quiz.LOCAL:
        return card["question"], None
    if card["kind"] == "word":
        q = review.word_question(log, card)
        if q is not None:
            return q, None
        return None, (tr("What does “{word}” mean?", word=card["front"]),
                      card["back"] + (f" — {card['example']}" if card.get("example") else ""))
    if card["kind"] == "question":
        return None, (card["question"]["question"], review._answer_text(card["question"]))
    return None, (review.front(card), card["back"])


def recall_buttons(key: str, prompt: str, answer: str):
    """Recall it, look, say honestly whether she knew it: True / False / None."""
    st.markdown(f"**{prompt}**")
    shown_key = f"ss_shown_{key}"
    if not st.session_state.get(shown_key):
        st.caption(tr("Say it to yourself first, then look."))
        if st.button(tr("Show the answer"), type="primary", key=f"{key}_show", width="stretch"):
            st.session_state[shown_key] = True
            st.rerun()
        return None
    st.markdown(answer)
    out = None
    with st.container(horizontal=True, key=f"ssself_{key}"):
        if st.button(tr("I knew it"), type="primary", key=f"{key}_yes", width="stretch"):
            out = True
        if st.button(tr("Not yet"), key=f"{key}_no", width="stretch"):
            out = False
    if out is not None:
        st.session_state.pop(shown_key, None)
    return out


def source_line(topic: str, n: int, log: dict) -> str:
    held = mastery.holder(log, topic, n)
    title = held[1]["title"] if held else ""
    return " · ".join(x for x in (catalog.name(topic, ""), tr("Lesson {n}: {title}", n=n, title=title) if title
                                  else tr("Lesson {n}", n=n)) if x)


# ------------------------------------------------------------- the reflection
def jol_buttons(key: str):
    """How sure she is she'll remember today's idea next week (a judgment of
    learning): 1-3 once chosen."""
    st.html('<p class="ss-ask">' + tr("Will you remember today's idea next week?") + "</p>")
    chosen = None
    with st.container(horizontal=True, key=f"ssjol_{key}", gap="small"):
        for c in (1, 2, 3):
            if st.button(tr(JOL_LABELS[c]), key=f"{key}_jol{c}", width="stretch"):
                chosen = c
    return chosen


def recall_chance(log, topic, n, today) -> float:
    held = mastery.holder(log, topic, n)
    if held is None:
        return 0.0
    return mastery.state(mastery.evidence(held[1], held[0]["date"]), today)["recall"]


def confidence(value):
    return learner.confidence(value)
