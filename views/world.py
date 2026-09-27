"""A subject's world: the subject first, large, with the object that stands
for it; then, quietly, where she is in it, what comes next, what she has
done lately, and her other subjects' worlds.

One page for every subject: its composition, object and title style come
from visuals.WORLD, its content from its own syllabus and her record. The
object arrives from wherever she touched it (motion.py carries it)."""
from datetime import date, timedelta
from html import escape

import streamlit as st

from coach import core, curriculum, settings, ui, visuals

log = st.session_state.coach_log
config = ui.config()
today = ui.today()
mine = settings.shown_subjects(config)

# the one subject this page shows: named in its address first (a refresh, a
# link, the browser's Back), then her session; a subject that isn't one
# (a stale or mistyped address) opens today's subject, and the address is
# rewritten to say so, so the address and the page never disagree
asked = st.query_params.get("subject")
topic = asked if visuals.known(asked) else st.session_state.get("world_topic")
if not visuals.known(topic):
    topic = ui.topic_for(today) if visuals.known(ui.topic_for(today)) else (mine[0] if mine else settings.SUBJECTS[0])
st.session_state.world_topic = topic
if asked != topic:
    st.query_params["subject"] = topic
s = visuals.subject(topic)
w = visuals.WORLD[topic]
name, number, f = s["title"], s["number"], s["facts"]


def next_day(t: str):
    """The next day (from today) the rotation gives to subject t."""
    for k in range(0, 8):
        if ui.topic_for(today + timedelta(days=k)) == t:
            return today + timedelta(days=k)
    return None


def all_subjects() -> None:
    """Back to the subjects (Settings), with this one still in focus there."""
    st.session_state.set_focus = topic
    st.switch_page("views/settings.py", query_params={"subject": topic})


st.html('<div id="world-page" hidden></div>')

# the way back: to all the subjects, this one still in focus
with st.container(key="w_back"):
    if st.button("All subjects", type="tertiary", key="w_all", icon=":material/arrow_back:"):
        all_subjects()

# ---------- the world: its name at the top, its object, and what she can do here ----------
with st.container(key=f"world_{w['layout']}"):
    with st.container(key="w_head"):
        st.html(f'<div class="w-copy w-title-{s["title_style"]}">'
                f'<p class="w-kicker">{number:02d} · {escape(s["kicker"])}</p>'
                f'<h1 class="w-title">{escape(name)}</h1></div>')
    with st.container(key="w_object"):
        st.html(visuals.object_html(topic, "w-object", number)
                + (f'<p class="w-credit">{escape(s["credit"])}</p>' if s["credit"] else ""))
    with st.container(key="w_copy"):
        st.html(f'<div class="w-copy"><p class="w-about">{escape(s["description"])}</p>'
                f'<p class="w-meta">{f["units"]} topics · {f["lessons"]} lessons · '
                f'begins with {escape(f["first"])}</p></div>')
        # what she can do here
        when = next_day(topic)
        with st.container(key="w_actions", horizontal=True, vertical_alignment="center"):
            if when == today:
                entry = core.find_entry(log, today, topic)
                begun = entry is not None and any(x.get("lesson") for x in entry.get("lessons") or [])
                if st.button("Continue today's lessons" if begun else "Begin today's lessons", type="primary",
                             key="w_today"):
                    st.switch_page("views/daily.py")
            else:
                st.html(f'<p class="w-next">{"Next on " + f"{when:%A}, {when:%B} {when.day}" if when else "Not in your rotation"}</p>')
            if st.button("See its lessons so far", type="tertiary", key="w_history"):
                st.session_state.prog_view_next = "Sessions"
                st.session_state.sessions_topic = topic
                st.switch_page("views/records.py")

# ---------- where she is, what comes next, what she has done ----------
unit = curriculum.unit_progress(log, topic)
p = curriculum.progress(log, topic)
level = core.lesson_level(min(p["done"] + 1, curriculum.TOTAL), settings.start_level(config, topic))
upcoming = curriculum.next_numbers(log, topic, 3)
names = [n for n, _, _ in visuals.units(topic)]
after = names[names.index(unit["unit"]) + 1:][:3] if unit and unit["unit"] in names else []
lately = sorted(((e["date"], s) for e in log["entries"] if e["topic"] == topic
                 for s in e.get("lessons") or [] if s.get("completed")), key=lambda x: (x[0], x[1]["n"]))[-3:][::-1]


def section(key: str, title: str, body: str) -> None:
    with st.container(key=f"w_sec_{key}"):
        st.html(f'<p class="w-sec-title">{escape(title)}</p>')
        st.html(f'<div class="w-sec-body">{body}</div>')


pct = round(100 * unit["done"] / unit["total"]) if unit and unit["total"] else 0
section("where", "Where you are",
        f'<p class="w-big">{escape(unit["unit"]) if unit else ""}</p>'
        f'<div class="w-line" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}"><i style="width:{pct}%"></i></div>'
        f'<p class="w-small">{unit["done"] if unit else 0} of {unit["total"] if unit else 0} lessons in this topic · '
        f'{p["done"]:,} of {p["written"]:,} written so far · {escape(level)}</p>')
if upcoming:
    section("next", "Next lessons", "<ol class=\"w-list\">" + "".join(
        f'<li><span class="n">{n}</span><span>{escape(curriculum.lesson(topic, n)["title"])}</span></li>'
        for n in upcoming) + "</ol>")
if after:
    section("ahead", "Topics ahead", '<ol class="w-list">' + "".join(
        f'<li><span class="n">{names.index(u) + 1}</span><span>{escape(u)}</span></li>' for u in after) + "</ol>")
if lately:
    section("lately", "Lately", '<ol class="w-list">' + "".join(
        f'<li><span class="n">{s["n"]}</span><span>{escape(s["title"])}</span>'
        f'<span class="d">{date.fromisoformat(d):%b} {date.fromisoformat(d).day}</span></li>'
        for d, s in lately) + "</ol>")

# ---------- her other subjects: each a world of its own ----------
others = [t for t in mine if t != topic and t in visuals.WORLD]
if others:
    with st.container(key="w_sec_others"):
        st.html('<p class="w-sec-title">Your other subjects</p>')
        with st.container(key="w_others", horizontal=True):
            for t in others:
                o = visuals.subject(t)
                with st.container(key=f"enter_{t}"):
                    st.html(visuals.object_html(t, "w-thumb", o["number"])
                            + f'<p class="w-thumb-name">{escape(o["title"])}</p>')
                    if st.button(f"Enter {o['title']}", key=f"w_enter_{t}"):
                        ui.enter_world(t)
