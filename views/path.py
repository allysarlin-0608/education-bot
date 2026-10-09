"""Learning Path: her sequence. The order of her coming days (her subjects
and goals take turns, one a day), and for each course where she is and what
comes next, unit by unit. The order, pace and choices themselves are changed
in Learning Plan; a goal's path is adjusted from its course map. No AI call."""
from datetime import timedelta
from html import escape

import streamlit as st

from coach import catalog, course, pathview, settings, ui

log = st.session_state.coach_log
config = ui.config()
today = ui.today()
mine = settings.shown_subjects(config)

st.html('<div id="settings-page" hidden></div>')
st.markdown("## Learning Path")
st.caption("The order of your days, and where each course goes next. Each lesson opens once the one before "
           "it is passed. To change the order, the pace or what you learn, go to Learning Plan.")

with st.container(key="set_sec_days"):
    st.markdown("#### Your next days")
    days = [today + timedelta(days=k) for k in range(7)]
    labels = ["Today", "Tomorrow"] + [f"{d:%a} {d.day}" for d in days[2:]]
    st.html(pathview.turns_html([catalog.name(ui.topic_for(d)) for d in days], settings.units(config),
                                labels=labels))

with st.container(key="set_sec_courses"):
    st.markdown("#### Where each course goes next")
    for t in mine:
        m = course.build(log, t)
        if not m["units"]:
            continue
        k = m["current"] if m["current"] is not None else 0
        ahead = [(u["name"], len(u["lessons"])) for u in m["units"][k:]]
        nxt = next((x for u in m["units"] for x in u["lessons"] if x["n"] == m["next"]), None)
        with st.container(key=f"lp_{t}"):
            st.html(pathview.outline_html(t, level=settings.start_level(config, t) or "", units=ahead)
                    + (f'<p class="ob-note">Next: lesson {nxt["n"]}, {escape(nxt["title"])} · '
                       f'{m["done"]} passed so far</p>' if nxt else ""))
            if st.button("Course map", key=f"lp_map_{t}", type="tertiary"):
                ui.open_course(t)
    if not mine:
        st.html('<p class="ob-note">Choose subjects or a goal in Learning Plan to see your path.</p>')
