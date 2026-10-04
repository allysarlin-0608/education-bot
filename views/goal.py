"""A new goal of her own, for someone already learning (Settings → Your
goals → Add a goal). The same two parts as the setup (coach/goalmaker.py):
what she wants to learn, then the path designed for it, to adjust. Add this
goal saves the path and gives it its turn: today, if today's lesson hasn't
been started, so her first lesson for it can begin at once."""
from datetime import timedelta
from html import escape

import streamlit as st

from coach import catalog, core, goalmaker, plans, settings, ui

config = ui.config()
log = st.session_state.coach_log
today = ui.today()

st.html('<div id="setup-page" hidden></div><div id="goal-page" hidden></div>')     # the setup's quieter page


def draft() -> dict:
    return settings.draft_of(ui.config())


def put(d: dict) -> None:
    """Keep the goal being made in her settings' draft (a refresh brings it back)."""
    ui.save_settings(dict(ui.config(), onboarding=d))


def clear() -> None:
    ui.refresh_settings()
    put(dict(draft(), **settings.new_goal_draft()))
    for k in [k for k in st.session_state if k.startswith(("goal_", "gpath_"))]:
        del st.session_state[k]


def started_today() -> bool:
    """Has today's lesson been started (its subject is then kept for today)?"""
    e = core.find_entry(log, today, ui.topic_for(today))
    return bool(e and any(s.get("lesson") or s.get("completed") for s in e.get("lessons") or []))


def add() -> None:
    """Save the path, give it its turn, and open it: today if it's free."""
    ui.refresh_settings()
    d = draft()
    if not d["path"]:
        return
    first = today if not started_today() else today + timedelta(days=1)
    try:
        new = settings.add_goal(ui.config(), d["path"]["id"], settings.now_iso(), first, ui.TIMEZONE)
    except ValueError as e:
        st.session_state.goal_problem = str(e)
        return
    if not ui.save_path(log, d["path"]):
        return
    if ui.save_settings(dict(new, onboarding=dict(d, **settings.new_goal_draft()))):
        ui.record("goal_created")
        st.session_state.goal_added = d["path"]["id"]


if settings.is_legacy(config):
    st.markdown("## A goal of your own")
    st.caption("Goals need the settings table in the database first (see Settings).")
    st.stop()

added = st.session_state.pop("goal_added", None)
if added and catalog.path(added):
    for k in [k for k in st.session_state if k.startswith(("goal_", "gpath_"))]:
        del st.session_state[k]
    if ui.topic_for(today) == added:
        st.switch_page("views/daily.py")          # her first lesson for it, now
    when = ui.next_study_day(added)
    st.markdown(f"## {catalog.name(added)}")
    st.html(f'<p class="ob-lede">Added. Your first lesson is on '
            f'{when:%A}, {when:%B} {when.day}.</p>' if when else '<p class="ob-lede">Added.</p>')
    if st.button("Back to Today", type="primary", key="goal_today"):
        st.switch_page("views/daily.py")
    st.stop()

active = len(settings.chosen_goals(config))
room = plans.active_goals_allowed(config) - active
d = draft()
with st.container(key="ob_grid"):
    with st.container(key="ob_lead"):
        st.markdown("## What do you want to learn?" if not d["path"] else "## Your path")
        st.html('<p class="ob-lede">'
                + ("Say it in your own words, or start from an idea. We'll design a path for it."
                   if not d["path"] else "Designed for your goal. Make it yours before you start.") + "</p>")
    with st.container(key="ob_body"):
        if room <= 0:
            st.html(f'<p class="ob-note">You have {active} goals going. Pause one in Settings to add another.</p>')
        elif not d["path"]:
            goalmaker.form("goal", draft, put, ask_pace=False, pace=settings.units(config))
        else:
            goalmaker.review("gpath", draft, put, settings.units(config))
            problem = st.session_state.pop("goal_problem", "")
            if problem:
                st.html(f'<p class="ob-note">{escape(problem)}</p>')
            with st.container(key="ob_nav", horizontal=True, vertical_alignment="center"):
                st.button("Add this goal", key="goal_add", type="primary", on_click=add)
                st.button("Start over", key="goal_again", type="tertiary", on_click=goalmaker.again, args=(draft, put))
        if st.button("Cancel", key="goal_cancel", type="tertiary"):
            clear()
            st.switch_page("views/settings.py")
