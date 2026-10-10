"""Subjects & Courses: what there is to learn (the curriculum). Her subjects
and goals first, each with how far she is and the way to its course map and
its world; then the rest of our subjects, each with its course map, and the
way to add it (in Learning Plan, where what she learns is chosen). Nothing
here changes her settings. No AI call: course maps show titles only."""
from html import escape

import streamlit as st

from coach import catalog, course, settings, ui, visuals

log = st.session_state.coach_log
config = ui.config()
mine = settings.shown_subjects(config)

st.html('<div id="settings-page" hidden></div>')        # (quiet sections on hairlines, as Learning Plan)
st.markdown("## Subjects & Courses")
st.caption("Every course you can take. Each subject has a course of short lessons in order; a goal of your own "
           "has the path designed for it. What you learn each day is chosen in Learning Plan.")


def describe(t: str) -> str:
    if catalog.is_goal(t):
        p = catalog.path(t) or {}
        return p.get("outcome") or "Your goal"
    return settings.DESCRIPTIONS.get(t, "")


def course_row(t: str, k: str, chosen: bool) -> None:
    m = course.build(log, t)
    unit = m["units"][m["current"]]["name"] if m["units"] and m["current"] is not None else ""
    where = (f"{m['done']} {'lesson' if m['done'] == 1 else 'lessons'} passed" + (f" · now in {unit}" if unit else "")
             if chosen else f"{len(m['units'])} parts to start with")
    with st.container(key=f"sc_{k}_{t}"):
        st.html(f'<p class="set-goal"><span>{escape(catalog.name(t))}</span><b>{escape(where)}</b></p>'
                f'<p class="ob-note">{escape(describe(t))}</p>')
        with st.container(key=f"sc_acts_{k}_{t}", horizontal=True):
            if chosen:                     # hers: its map and its world
                if st.button("Course map", key=f"sc_map_{k}_{t}", type="tertiary"):
                    ui.open_course(t)
                if visuals.known(t) and st.button(f"Enter {catalog.name(t)}", key=f"sc_enter_{k}_{t}", type="tertiary"):
                    ui.enter_world(t)
            else:                          # not hers yet: what it covers, and the way to add it
                if st.button("Add to my days", key=f"sc_add_{k}_{t}", type="tertiary"):
                    st.switch_page("views/settings.py", query_params={"subject": t})
                if st.button("See what it covers", key=f"sc_map_{k}_{t}", type="tertiary"):
                    ui.open_course(t)


with st.container(key="set_sec_mine"):
    st.markdown("#### Yours")
    if not mine:
        st.html('<p class="ob-note">No subjects or goals chosen yet. Choose them in Learning Plan.</p>')
    for t in mine:
        course_row(t, "mine", True)

rest = [t for t in settings.SUBJECTS if t not in mine]
if rest:
    with st.container(key="set_sec_more"):
        st.markdown("#### More subjects")
        for t in rest:
            course_row(t, "more", False)
