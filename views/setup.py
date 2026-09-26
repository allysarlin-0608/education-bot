"""First-time setup: six short steps, one decision each (Welcome,
Subjects, Daily pace, Level, Reading, Summary).

Her answers are kept in her settings row as she goes (settings "onboarding"),
so a refresh brings her back to the same step with everything she chose.
She counts as set up only once she presses Start learning: then the
settings are checked, saved with onboarded_at, and Today opens."""
from html import escape

import streamlit as st

from coach import choices, core, settings, ui

STEP_NAMES = ("Welcome", "Subjects", "Daily pace", "Level", "Reading", "Summary")
WELCOME, SUBJECTS, PACE, LEVEL, READING, SUMMARY = range(6)


def draft() -> dict:
    return settings.draft_of(ui.config())


def put(d: dict) -> None:
    """Keep her answers so far (not yet a finished setup: onboarded_at stays empty)."""
    ui.save_settings(dict(ui.config(), onboarding=d))


def reachable(d: dict) -> int:
    """The furthest step her answers allow (a stale draft can't skip ahead)."""
    if not d["subjects"]:
        return SUBJECTS
    if any(v is None for v in settings.draft_levels(d).values()):
        return LEVEL
    return SUMMARY


def go(step: int) -> None:
    d = draft()
    st.session_state.ob_way = "fwd" if step > d["step"] else "back"
    st.session_state.ob_from = d["step"]
    d["step"] = min(step, reachable(d))
    put(d)


def pick_subject(topic: str) -> None:
    d = draft()
    d["subjects"] = settings.toggle_subject(d["subjects"], topic)
    put(d)


def pick_pace(n: int) -> None:
    put(dict(draft(), units_per_day=n))


def set_level(topic: str, change) -> None:
    d = draft()
    d["levels"][topic] = change(settings.level_choice(d, topic))
    put(d)


def set_way(topic: str) -> None:
    way = st.session_state[f"lvl_{topic}"] or choices.BASICS
    set_level(topic, lambda c: dict(c, way=way))


def set_reading() -> None:
    put(dict(draft(), reading_enabled=bool(st.session_state.ob_reading)))


def start() -> None:
    """Start learning: check everything, save it as her settings, and Today opens."""
    try:
        done = settings.finish(ui.config(), draft(), settings.now_iso())
    except ValueError as e:
        st.session_state.ob_problem = str(e)
        return
    if ui.save_settings(done):
        st.session_state.pop("ob_way", None)


def nav(back: bool = True, label: str = "Continue", ready: bool = True, note: str = "", on=None) -> None:
    """Back and Continue, at the foot of the step (a note on what's missing just above)."""
    if note:
        st.html(f'<p class="ob-note">{escape(note)}</p>')
    with st.container(key="ob_nav", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        if back:
            st.button("Back", key="ob_back", type="tertiary", on_click=go, args=(step - 1,))
        else:
            st.html('<span class="pq-gap"></span>')
        st.button(label, key="ob_next", type="primary", disabled=not ready,
                  on_click=on or go, args=() if on else (step + 1,))


d = draft()
step = min(d["step"], reachable(d))
came = st.session_state.pop("ob_way", "none")
was = st.session_state.pop("ob_from", step)

st.html('<div id="setup-page" hidden></div>')     # a narrower, quieter page (style.py)
# where she is: a hairline that fills step by step, and the step's name
st.html(f'<div class="ob-progress" role="progressbar" aria-label="Setup" aria-valuemin="1" aria-valuemax="6" '
        f'aria-valuenow="{step + 1}" aria-valuetext="Step {step + 1} of 6, {STEP_NAMES[step]}">'
        f'<div class="ob-track"><i style="--from:{(was + 1) / 6:.4f};--to:{(step + 1) / 6:.4f}"></i></div>'
        f'<div class="ob-where"><span>{STEP_NAMES[step]}</span><span>{step + 1} of 6</span></div></div>')

# each step is its own block, so it comes in from the side she is heading to
with st.container(key=f"ob_step_{step}_{came}"):
    if step == WELCOME:
        st.markdown("## Learn a little every day")
        st.html('<p class="ob-lede">Choose what you want to learn and how much time you have. '
                "Each day brings one subject: a few short lessons, each with a quiz to check it stayed.</p>")
        with st.container(key="ob_nav", horizontal=True, horizontal_alignment="left"):
            st.button("Get started", key="ob_next", type="primary", on_click=go, args=(SUBJECTS,))

    elif step == SUBJECTS:
        st.markdown("## What would you like to learn?")
        st.html('<p class="ob-lede">Choose up to three. They take turns, one a day, in the order you choose them.</p>')
        full = len(d["subjects"]) >= settings.MAX_SUBJECTS
        choices.rows("subj", [(t, core.TOPICS[t], settings.DESCRIPTIONS[t]) for t in settings.SUBJECTS],
                     d["subjects"], pick_subject, multi=True, full=full)
        n = len(d["subjects"])
        order = " → ".join(core.TOPICS[t] for t in d["subjects"])
        nav(ready=n >= settings.MIN_SUBJECTS,
            note=(f"{n} of {settings.MAX_SUBJECTS} chosen · {order}" if n else "Choose at least one subject to continue."))

    elif step == PACE:
        st.markdown("## How much each day?")
        st.html('<p class="ob-lede">One subject a day, in short lessons. You can change this later in Settings.</p>')
        choices.rows("pace", [(n, name, settings.pace_line(n)) for n, (name, _) in settings.PACES.items()],
                     {d["units_per_day"]}, pick_pace)
        nav()

    elif step == LEVEL:
        st.markdown("## Where should each subject start?")
        st.html('<p class="ob-lede">Start from the basics, or answer five quick questions to find your level.</p>')
        levels = settings.draft_levels(d)
        for t in d["subjects"]:
            c = settings.level_choice(d, t)
            with st.container(key=f"ob_subject_{t}"):
                st.html(f'<p class="ob-subject">{escape(core.TOPICS[t])}</p>')
                choices.way_switch(f"lvl_{t}", c["way"], set_way, args=(t,))
                if c["way"] == choices.PLACEMENT:
                    choices.placement(
                        t, t, c,
                        on_answer=lambda i, t=t: set_level(t, lambda c: choices.answer(c, i)),
                        on_move=lambda k, t=t: set_level(t, lambda c: choices.move(c, t, k)),
                        on_again=lambda t=t: set_level(t, lambda c: dict(c, **choices.fresh())))
        waiting = [core.TOPICS[t] for t, lv in levels.items() if lv is None]
        nav(ready=not waiting, note=f"Finish the questions for {', '.join(waiting)} to continue." if waiting else "")

    elif step == READING:
        st.markdown("## Reading")
        st.html('<p class="ob-lede">Choose a book and it is split into 14 days: read your part each day, '
                "then come back and talk it through.</p>")
        with st.container(key="ob_toggle"):
            st.toggle("Add a 14-day reading plan", value=d["reading_enabled"], key="ob_reading", on_change=set_reading)
        nav()

    else:
        st.markdown("## Your plan")
        st.html('<p class="ob-lede">Everything can be changed later in Settings.</p>')
        levels = settings.draft_levels(d)
        name, minutes = settings.PACES[d["units_per_day"]]
        n = d["units_per_day"]

        def level_line(t):
            c = settings.level_choice(d, t)
            how = f"{c['score']} of 5 right" if c["way"] == choices.PLACEMENT else "from the basics"
            return (f'<span class="ob-pair"><span>{escape(core.TOPICS[t])}</span>'
                    f'<span>{escape(levels[t] or "")} <small>· {how}</small></span></span>')

        st.html('<dl class="ob-summary">'
                f'<div><dt>Subjects</dt><dd>{escape(" → ".join(core.TOPICS[t] for t in d["subjects"]))}'
                f'<small>{"Every day" if len(d["subjects"]) == 1 else "One a day, taking turns"}</small></dd></div>'
                f'<div><dt>Daily pace</dt><dd>{name}<small>{n} {"lesson" if n == 1 else "lessons"} a day · {minutes}</small></dd></div>'
                f'<div><dt>Starting level</dt><dd>{"".join(level_line(t) for t in d["subjects"])}</dd></div>'
                f'<div><dt>Reading plan</dt><dd>{"On" if d["reading_enabled"] else "Off"}'
                f'<small>{"A book over 14 days" if d["reading_enabled"] else "You can add one later"}</small></dd></div>'
                "</dl>")
        problem = st.session_state.pop("ob_problem", "")
        nav(label="Start learning", ready=not settings.errors(dict(settings.blank(""), subjects=d["subjects"],
                                                                    units_per_day=d["units_per_day"],
                                                                    subject_levels=levels,
                                                                    reading_enabled=d["reading_enabled"])),
            note=problem, on=start)
