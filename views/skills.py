"""The skill map: what she really knows, idea by idea (coach/mastery.py).

Every lesson of a subject or goal is one idea, grouped by unit; each is new,
learning, solid or mastered from the evidence (quizzes, review, practice,
explaining it, her questions), and fades if it isn't practised. One calm
picture across everything first, then one subject at a time. No AI call."""
from html import escape

import streamlit as st

from coach import catalog, mastery, ui

log = st.session_state.coach_log
today = ui.today()
st.html('<div id="skills-page" hidden></div>')
st.markdown("## Skill map")
st.caption("What you really know, idea by idea: each lesson is one idea. An idea is solid once it holds on "
           "another day, mastered once it keeps holding over a week or more, and it fades if it isn't practised.")

topics = mastery.topics(log)
if not topics:
    st.markdown("### Your map starts with your first lesson")
    st.caption("Take a lesson and its quiz: the idea appears here, and grows with review, practice and "
               "explaining it in your own words.")
    if st.button("Back to Today", key="sk_back", type="tertiary"):
        st.switch_page("views/daily.py")
    st.stop()


def bar(c: dict) -> str:
    """The levels as one quiet bar: mastered, solid, learning (ideas reached only)."""
    total = sum(c[lv] for lv in ("learning", "solid", "mastered")) or 1
    parts = "".join(f'<span class="sk-seg sk-{lv}" style="width:{c[lv] / total * 100:.1f}%"></span>'
                    for lv in ("mastered", "solid", "learning") if c[lv])
    return f'<div class="sk-bar">{parts}</div>'


def legend(c: dict) -> str:
    return "".join(f'<span class="sk-key"><i class="sk-dot sk-{lv}"></i>{c[lv]} {mastery.LEVEL_NAMES[lv].lower()}</span>'
                   for lv in ("mastered", "solid", "learning"))


ov = mastery.overview(log, today)
total = ov["total"]
fading = [w for w in mastery.needs_practice(log, today) if w[2]["fading"]]
st.html(f'<div class="sk-summary">{bar(total)}<p class="sk-legend">{legend(total)}'
        + (f'<span class="sk-key">· {len(fading)} fading</span>' if fading else "") + "</p></div>")

weak = mastery.needs_practice(log, today)
with st.container(key="sk_actions", horizontal=True, vertical_alignment="center"):
    if weak:
        if st.button(f"Practise the {min(3, len(weak))} shakiest", type="primary", key="sk_practice"):
            st.switch_page("views/practice.py")
    elif st.button("Practice", key="sk_practice_any", type="tertiary"):
        st.switch_page("views/practice.py")

# ---------------------------------------------------------------- one subject
pick = st.session_state.get("sk_topic")
if pick not in topics:
    pick = ui.topic_for(today) if ui.topic_for(today) in topics else topics[0]
if len(topics) > 1:
    pick = st.segmented_control("Subject", topics, default=pick, key="sk_pick", required=True,
                                format_func=lambda t: catalog.name(t), label_visibility="collapsed") or pick
st.session_state.sk_topic = pick
items = mastery.ideas(log, pick, today)
reached = [x for x in items if x["reached"]]
c = mastery.counts(reached)
st.markdown(f"### {escape(catalog.name(pick))}")
st.caption(f"{len(reached)} of {len(items)} ideas met · {c['mastered']} mastered · {c['solid']} solid · "
           f"{c['learning']} learning")

for u in mastery.units(items):
    if not u["reached"]:
        continue
    uc = u["counts"]
    with st.container(key=f"sk_unit_{u['ideas'][0]['n']}"):
        st.html(f'<p class="sk-unit">{escape(u["name"])}</p>{bar(uc)}')
        rows = []
        for x in u["ideas"]:
            if not x["reached"]:
                rows.append(f'<li class="sk-ahead"><span class="sk-t">{escape(x["title"])}</span>'
                            '<span class="sk-chip sk-new">Not yet</span></li>')
                continue
            tag = mastery.LEVEL_NAMES[x["level"]] + (" · fading" if x["fading"] else "")
            rows.append(f'<li><span class="sk-t">{escape(x["title"])}<small>{escape(mastery.describe(x))}</small></span>'
                        f'<span class="sk-chip sk-{x["level"]}{" sk-fading" if x["fading"] else ""}">{escape(tag)}</span></li>')
        st.html('<ul class="sk-ideas">' + "".join(rows) + "</ul>")

ahead = sum(1 for u in mastery.units(items) if not u["reached"])
if ahead:
    st.caption(f"{ahead} more {'unit' if ahead == 1 else 'units'} ahead on the course map.")
with st.container(key="sk_links", horizontal=True):
    if st.button("Course map", key="sk_course", type="tertiary"):
        ui.open_course(pick)
    if st.button("Back to Today", key="sk_today", type="tertiary"):
        st.switch_page("views/daily.py")
