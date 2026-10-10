"""A new goal of her own, for someone already learning (Settings → Your
goals → Add a goal). The same parts as the setup (coach/goalmaker.py): what
she wants to learn, then on one page its outline (all of it, or the parts she
ticks) and what it's for. Add this goal saves the path and gives it its turn:
today, if today's lesson hasn't been started, so her first lesson for it can
begin at once."""
from datetime import timedelta
from html import escape

import streamlit as st

from coach import catalog, core, directions, goalmaker, plans, settings, ui

config = ui.config()
log = st.session_state.coach_log
today = ui.today()

st.html('<div id="setup-page" hidden></div><div id="goal-page" hidden></div>')     # the setup's quieter page


def draft() -> dict:
    return settings.draft_of(ui.config())


def put(d: dict) -> None:
    """Keep the goal being made in her settings' draft (a refresh brings it back)."""
    ui.refresh_settings()       # onto the row as stored now (another tab may have changed it; ISS-044)
    ui.save_settings(dict(ui.config(), onboarding=d))


def other() -> None:
    """A different goal: the outline goes (her words stay), and so do her answers about it."""
    goalmaker.again(draft, put)
    put(dict(draft(), scope=None, purpose=""))
    for k in [k for k in st.session_state if k.startswith(("gs_", "gp_"))]:
        del st.session_state[k]


def same_goal(p: dict):
    """One of her goals that this path repeats (the same id, or the same title), or None."""
    title = p["title"].strip().casefold()
    return next((g for g in catalog.goals(active_only=False)
                 if g["id"] == p["id"] or g["title"].strip().casefold() == title), None)


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
    twin = same_goal(d["path"])
    if twin:                    # never two of the same goal
        st.session_state.goal_problem = (f"“{twin['title']}” is already one of your goals"
                                         + ("." if twin["status"] == "active" else ": resume it in Learning Plan."))
        return
    first = today if not started_today() else today + timedelta(days=1)
    try:
        new = settings.add_goal(ui.config(), d["path"]["id"], settings.now_iso(), first, ui.TIMEZONE)
    except ValueError as e:
        st.session_state.goal_problem = str(e)
        return
    if not ui.save_path(log, dict(d["path"], why="" if d.get("purpose") == directions.ALL_OF_IT else d.get("purpose", ""))):
        return
    if ui.save_settings(dict(new, onboarding=dict(d, scope=None, purpose="", **settings.new_goal_draft()))):
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
    if st.button("Back to Home", type="primary", key="goal_today"):
        st.switch_page("views/daily.py")
    st.stop()

active = len(settings.chosen_goals(config))
room = plans.active_goals_allowed(config) - active
d = draft()
if d["path"] and catalog.path(d["path"]["id"]):     # a path already saved, left in the draft: start fresh
    ui.clear_goal_draft()
    d = draft()
identity = ui.prefs().get("identity", "")
ready = bool(d["path"] and d.get("scope") and d.get("purpose"))
with st.container(key="ob_grid"):
    with st.container(key="ob_lead"):
        st.markdown("## What do you want to learn?" if not d["path"] else "## All of it, or some parts?")
        st.html('<p class="ob-lede">'
                + ("Anything at all: a subject, a skill, a question you're curious about. A word is enough."
                   if not d["path"] else "Here's what it covers. Keep all of it or tick the parts you want, "
                                         "then say what it's for.") + "</p>")
    with st.container(key="ob_body"):
        if room <= 0:
            st.html(f'<p class="ob-note">You have {active} goals going. Pause one in Learning Plan to add another.</p>')
        elif not d["path"]:
            goalmaker.form("goal", draft, put, pace=settings.units(config), ideas=directions.IDEAS.get(identity))
        else:
            # the same steps as the setup, on one page: all of it or some parts, then what it's for
            goalmaker.scope("gs", draft, put)
            st.markdown("#### What's it for?")
            goalmaker.purpose("gp", draft, put, identity)
            problem = st.session_state.pop("goal_problem", "")
            if problem:
                st.html(f'<p class="ob-note">{escape(problem)}</p>')
            elif not ready:
                st.html('<p class="ob-note" role="status">Choose all of it or some parts, and what it\'s for, '
                        "to add this goal.</p>")
            with st.container(key="ob_nav", horizontal=True, vertical_alignment="center"):
                st.button("Add this goal", key="goal_add", type="primary", on_click=add, disabled=not ready)
                st.button("Something else", key="goal_again", type="tertiary", on_click=other)
        if st.button("Cancel", key="goal_cancel", type="tertiary"):
            ui.clear_goal_draft()
            st.switch_page("views/settings.py")
