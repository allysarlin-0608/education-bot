"""Courses: what there is to learn (the curriculum). Her subjects
and goals first, each with how far she is, the lesson that comes next, and
the way to its course map and its world; then the rest of our subjects, each with its course map, and the
way to add it (in Goals & Settings, where what she learns is chosen). Nothing
here changes her settings. No AI call: course maps show titles only. Last, what
there is to browse: the math curriculum (views/math.py)."""
from html import escape

import streamlit as st

from coach import catalog, course, mathcourse, settings, ui, visuals
from coach.i18n import tr, trn

log = st.session_state.coach_log
config = ui.config()
mine = settings.shown_subjects(config)

st.html('<div id="settings-page" hidden></div>')        # (quiet sections on hairlines, as Goals & Settings)
st.markdown(tr("## Courses"))
st.caption(tr("Your courses: each is a series of short lessons in order. To learn something new, add a goal "
           "in Goals & Settings."))


def describe(t: str) -> str:
    if catalog.is_goal(t):
        p = catalog.path(t) or {}
        return p.get("outcome") or tr("Your goal")
    return tr(settings.DESCRIPTIONS.get(t, ""))


def course_row(t: str, k: str, chosen: bool) -> None:
    m = course.build(log, t)
    unit = m["units"][m["current"]]["name"] if m["units"] and m["current"] is not None else ""
    where = (trn("{n} lesson passed", "{n} lessons passed", m['done']) + (" · " + tr("now in {unit}", unit=unit) if unit else "")
             if chosen else tr("{n} parts to start with", n=len(m['units'])))
    nxt = next((x for u in m["units"] for x in u["lessons"] if x["n"] == m["next"]), None) if chosen else None
    with st.container(key=f"sc_{k}_{t}"):
        st.html(f'<p class="set-goal"><span>{escape(catalog.name(t))}</span><b>{escape(where)}</b></p>'
                f'<p class="ob-note">{escape(describe(t))}</p>'
                + ('<p class="ob-note sc-next">' + tr("Next: lesson {n}, {title}", n=nxt["n"], title=escape(nxt["title"]))
                   + "</p>" if nxt else ""))
        with st.container(key=f"sc_acts_{k}_{t}", horizontal=True):
            if chosen:                     # hers: its map and its world
                if st.button(tr("Learning map"), key=f"sc_map_{k}_{t}", type="tertiary"):
                    ui.open_course(t)
                if visuals.known(t) and st.button(tr('Enter {p0}', p0=catalog.name(t)), key=f"sc_enter_{k}_{t}", type="tertiary"):
                    ui.enter_world(t)
            else:                          # not hers yet: what it covers, and the way to add it
                if st.button(tr("Add to my days"), key=f"sc_add_{k}_{t}", type="tertiary"):
                    st.switch_page("views/settings.py", query_params={"subject": t})
                if st.button(tr("See what it covers"), key=f"sc_map_{k}_{t}", type="tertiary"):
                    ui.open_course(t)


with st.container(key="set_sec_mine"):
    st.markdown(tr("#### Yours"))
    if not mine:
        st.html(tr('<p class="ob-note">No subjects or goals chosen yet. Choose them in Goals & Settings.</p>'))
    for t in mine:
        course_row(t, "mine", True)

rest = [t for t in settings.SUBJECTS if t not in mine]
if rest and settings.builtin_offered(config, log):         # (new learners: their own goals only)
    with st.container(key="set_sec_more"):
        st.markdown(tr("#### More subjects"))
        for t in rest:
            course_row(t, "more", False)

with st.container(key="set_sec_reference"):        # a curriculum to browse, not one of her courses
    st.markdown(tr("#### To browse"))
    c = mathcourse.counts()
    with st.container(key="sc_ref_math"):
        st.html(tr('<p class="set-goal"><span>Math, from zero to research</span><b>{p0} phases · {p1} units</b></p><p class="ob-note">The mathematics curriculum in Traditional Chinese: each unit with what it covers, what you\'ll be able to do, what to practise, what to learn first and where the material comes from.</p>', p0=c["phases"], p1=c["units"]))
        if st.button(tr("Open the curriculum"), key="sc_math", type="tertiary"):
            st.switch_page("views/math.py")
