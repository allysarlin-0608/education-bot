"""Math curriculum: from zero to research, to browse (coach/mathcourse.py).

The phases in order, each folded to one line; opened, its goal and its
units: the summary, what she will be able to do, what to practise, the
units to learn first (each opens that unit, wherever it is), and the
sources it draws on (linked, in a new tab). All the sources and how they
may be used close the page. ?unit=L4-02 opens that unit's phase and brings
it into view. Mathematics is also a subject (coach/curriculum/math.txt): a
lesson per learning outcome; the page leads to her course map, or to
where it is added. Nothing here changes her settings or calls the model."""
from html import escape

import streamlit as st

from coach import mathcourse, settings, ui
from coach.i18n import tr, trn

data = mathcourse.load()
every = mathcourse.units(data)

asked = st.query_params.get("unit")
if asked not in every:
    asked = None


def go_to(uid: str) -> None:
    """A prerequisite pressed: its phase open, its unit in view."""
    st.session_state[f"mc_phase_{every[uid]['phase']}"] = True
    st.query_params["unit"] = uid
    st.session_state.mc_scroll = uid


if asked and st.session_state.get("mc_seen") != asked:      # arriving from an address: open it once
    st.session_state[f"mc_phase_{every[asked]['phase']}"] = True
    st.session_state.mc_scroll = asked
st.session_state.mc_seen = asked


def add_math() -> None:
    """Mathematics into her days, after what she has (it comes in its turn);
    with three subjects already, she is told where to make room."""
    ui.refresh_settings()
    now = settings.chosen_subjects(ui.config())
    new = settings.toggle_subject(now, "math")
    if new == now:
        st.session_state.mc_added = tr("You already have {n} subjects: remove one in Goals & Settings to make "
                                       "room for Mathematics.", n=settings.MAX_SUBJECTS)
        return
    if ui.save_settings(settings.change(ui.config(), settings.now_iso(), subjects=new)):
        st.session_state.mc_added = tr("Added. Mathematics takes its turn with your other subjects, "
                                       "starting with lesson 1.")


def link(s: dict) -> str:
    return (f'<a href="{escape(s["url"])}" target="_blank" rel="noopener noreferrer">'
            f'{escape(s["title"])} ↗</a>')


def unit(u: dict) -> None:
    here = u["id"] == asked
    found = mathcourse.sources_of(u, data)
    with st.container(key=f"mc_u_{u['id'].replace('-', '_')}" + ("_here" if here else ""), gap="small"):
        st.html(f'<div id="mc-{escape(u["id"])}" class="jump-anchor"></div>'
                f'<p class="mc-t"><span>{escape(u["id"])}</span>{escape(u["title"])}</p>'
                f'<p class="mc-sum">{escape(u["summary"])}</p>'
                + '<p class="mc-k">' + tr("You'll be able to") + '</p><ul class="mc-list">'
                + "".join(f"<li>{escape(x)}</li>" for x in u["learning_outcomes"]) + "</ul>"
                + '<p class="mc-k">' + tr("Practice") + f'</p><p class="mc-v">{escape(u["practice_focus"])}</p>'
                + ('<p class="mc-k">' + tr("Sources") + '</p><p class="mc-v mc-src">' + " · ".join(link(s) for s in found)
                   + "</p>" if found else ""))
        before = mathcourse.prerequisites(u["id"], data)
        with st.container(key=f"mc_pre_{u['id'].replace('-', '_')}", horizontal=True,
                          vertical_alignment="center", gap="small"):
            st.html(tr('<p class="mc-k">Learn first</p>'))
            if not before:
                st.html(tr('<p class="mc-v">Nothing: a starting point</p>'))
            for p in before:
                st.button(f"{p['id']} {p['title']}", key=f"mc_go_{u['id']}_{p['id']}", type="tertiary",
                          on_click=go_to, args=(p["id"],))


st.html('<div id="math-page"></div>')
st.html(tr('<p class="cm-eyebrow cm-top">Curriculum</p>'))
st.markdown(f"## {escape(data['title'])}")
st.html(f'<p class="cm-outcome">{escape(data["description"])}</p>')
c = mathcourse.counts(data)
st.html(tr('<div class="cm-head"><p>{phases} phases · {units} units · {sources} sources</p></div>', phases=c["phases"], units=c["units"], sources=c["sources"]))
# learning it day by day: Mathematics is a subject, a lesson for each learning outcome
mine = "math" in settings.shown_subjects(ui.config())
with st.container(key="mc_learn", horizontal=True, vertical_alignment="center"):
    st.html('<p class="ob-note">' + (tr("You're learning this: a short lesson for each learning outcome, in this order.")
                                     if mine else tr("Learn it day by day: Mathematics is a subject, with a short lesson "
                                                     "for each learning outcome, in this order.")) + "</p>")
    if mine:
        if st.button(tr("Your course map"), key="mc_map", type="tertiary"):
            ui.open_course("math")
    else:
        st.button(tr("Add Mathematics to my days"), key="mc_add", type="tertiary", on_click=add_math)
if (said := st.session_state.pop("mc_added", None)):
    st.html(f'<p class="ob-note sc-next">{escape(said)}</p>')
st.html(f'<p class="ob-note">{escape(data["progression_policy"])}</p>')

with st.container(key="mc_phases"):
    for p in mathcourse.phases(data):
        n = len(p["units"])
        with st.expander(f"{p['id']} · {p['title']} · {p['level']} · " + trn("{n} unit", "{n} units", n),
                         key=f"mc_phase_{p['id']}", on_change="rerun"):
            st.html(f'<p class="cm-outcome">{escape(p["goal"])}</p>')
            for u in p["units"]:
                unit(dict(u, phase=p["id"]))

with st.container(key="mc_sources"):
    st.html('<div id="mc-sources" class="jump-anchor"></div>')
    st.markdown(tr("#### Sources"))
    for s in data["sources"]:
        st.html(f'<p class="set-goal"><span>{link(s)}</span><b>{escape(s["organization"])} · {escape(s["type"])}</b></p>'
                f'<p class="ob-note">{escape(s["coverage"])}</p>')
    st.html(f'<p class="ob-note mc-use">{escape(data["scope_note"])}</p>'
            f'<p class="ob-note mc-use">{escape(data["attribution_and_use"])}</p>')

if (target := st.session_state.pop("mc_scroll", None)):
    st.html('<script>setTimeout(() => { const e = window.parent.document.getElementById('
            f'"mc-{escape(target)}"); if (e) e.scrollIntoView({{behavior: "smooth", block: "start"}}); }}, 300);</script>',
            unsafe_allow_javascript=True)
