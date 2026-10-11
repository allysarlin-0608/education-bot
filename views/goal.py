"""A new goal of her own, for someone already learning (Settings → Your
goals → Add a goal). The same parts as the setup (coach/goalmaker.py): what
she wants to learn, then on one page its outline (all of it, or the parts she
ticks) and what it's for. Add this goal saves the path and gives it its turn:
today, if today's lesson hasn't been started, so her first lesson for it can
begin at once."""
from datetime import timedelta
from html import escape

import streamlit as st

from coach import catalog, core, curriculum, directions, goalmaker, paths, plans, settings, ui

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


def her_goals() -> list:
    """Every goal she has had: on her list (active or paused) and removed."""
    return catalog.goals(active_only=False) + catalog.removed_goals()


def near_goal(d: dict):
    """A goal of hers that this one repeats in other words (what she wrote,
    or the designed title), unless she said it's different."""
    text = d["goal"]["text"].strip()
    title = (d.get("path") or {}).get("title", "")
    if st.session_state.get("goal_dup_ok") in (text, title):
        return None
    return paths.similar_goal(text, her_goals(), title)


def continue_goal(goal_id: str) -> None:
    """She'd rather go on with the goal she has: back on her list and in her
    turns if it was paused or removed (from today if today is free), then open it."""
    ui.refresh_settings()
    p = catalog.path(goal_id)
    if not p:
        return
    if goal_id not in settings.chosen_subjects(ui.config()):
        first = today if not started_today() else today + timedelta(days=1)
        try:
            new = settings.add_goal(ui.config(), goal_id, settings.now_iso(), first, ui.TIMEZONE, log)
        except ValueError as e:
            st.session_state.goal_problem = str(e)
            return
        if not (ui.save_path(log, paths.restore(p)) and ui.save_settings(new)):
            return
    ui.clear_goal_draft()
    st.session_state.goal_added = goal_id          # (opens it: today's lesson, or when its turn is)
    st.session_state.goal_continued = True


def different() -> None:
    """It isn't the same goal: design it (or add it) after all."""
    d = draft()
    st.session_state.goal_dup_ok = d["goal"]["text"].strip() if not d.get("path") else d["path"]["title"]
    if not d.get("path"):
        st.session_state["goal_go"] = True          # (the design she asked for, now)


def dup_notice(g: dict) -> None:
    """You already have it: continue that one, or go on with this one."""
    pr = curriculum.progress(log, g["id"])
    state = {"active": "", "archived": " · paused", "removed": " · removed"}.get(g["status"], "")
    with st.container(key="goal_dup"):
        st.html(f'<p class="gm-reply" role="status">You already have a goal like this: <b>{escape(g["title"])}</b> '
                f'({pr["done"]} of {pr["written"]} lessons{state}). Continue it, and keep what you\'ve done?</p>')
        with st.container(key="goal_dup_btns", horizontal=True):
            st.button("Continue it", key="goal_dup_go", type="primary", on_click=continue_goal, args=(g["id"],))
            st.button("No, this one is different", key="goal_dup_new", type="tertiary", on_click=different)


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
    if near_goal(d):            # (asked first: continue it, or this one is different)
        return
    twin = same_goal(d["path"])
    if twin:                    # never two of the same goal
        st.session_state.goal_problem = (f"“{twin['title']}” is already one of your goals"
                                         + ("." if twin["status"] == "active" else ": resume it in Goals & Settings."))
        return
    first = today if not started_today() else today + timedelta(days=1)
    try:
        new = settings.add_goal(ui.config(), d["path"]["id"], settings.now_iso(), first, ui.TIMEZONE, log)
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

# where she goes from the page that says it was added (a button's press reruns the page, so
# the page stays until she chooses: a choice made on a page drawn only once was lost)
leave = st.session_state.pop("goal_leave", None)
if leave:
    st.session_state.pop("goal_shown", None)
    st.switch_page(leave)
if "goal_added" in st.session_state:
    st.session_state.goal_shown = (st.session_state.pop("goal_added"), st.session_state.pop("goal_continued", False))
added, continued = st.session_state.get("goal_shown") or (None, False)
if added and catalog.path(added):
    for k in [k for k in st.session_state if k.startswith(("goal_", "gpath_")) and k != "goal_shown"]:
        del st.session_state[k]
    # what happens now, said plainly: when its turn is, and how it shares the days with the others
    ahead = settings.days_ahead(ui.config(), today, ui.TIMEZONE, log)
    now = ui.topic_for(today) == added
    st.markdown(f"## {catalog.name(added)}")
    if len(ahead) <= 1:
        lede = "It's what you learn every day now."
    else:
        when = ui.next_study_day(added)
        first = ("today" if now else f"on {when:%A}, {when:%B} {when.day}" if when else "soon")
        lede = (f"{'Back in your days' if continued else 'Added'}. Your subjects and goals take turns, one a day; "
                f"this one's first turn is {first}.")
    st.html(f'<p class="ob-lede">{escape(lede)}</p>')
    if len(ahead) > 1:
        rows = "".join(f'<li><span>{"Today" if (d_ - today).days == 0 else "Tomorrow" if (d_ - today).days == 1 else f"{d_:%a} {d_:%b} {d_.day}"}</span>'
                       f'<b>{escape(catalog.name(t))}</b></li>' for d_, t in ahead)
        st.html(f'<ol class="goal-turns" aria-label="Your coming days">{rows}</ol>'
                '<p class="ob-note">Then the same order again. You can change it, or pause a goal, in Goals & Settings.</p>')
    with st.container(key="goal_done_btns", horizontal=True, vertical_alignment="center"):
        st.button("Start its first lesson" if now and not continued else "Go to Home" if not now else "Continue it",
                  type="primary", key="goal_today", on_click=lambda: st.session_state.update(goal_leave="views/daily.py"))
        if len(ahead) > 1:
            st.button("Change the order", type="tertiary", key="goal_order",
                      on_click=lambda: st.session_state.update(goal_leave="views/settings.py"))
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
            st.html(f'<p class="ob-note">You have {active} goals going. Pause one in Goals & Settings to add another.</p>')
        elif not d["path"]:
            # a goal she already has, in other words: asked before any AI call (continue it, or it's different)
            if st.session_state.get("goal_go") and near_goal(d):
                st.session_state.pop("goal_go")
                st.session_state.goal_dup_for = d["goal"]["text"].strip()
            twin = near_goal(d) if st.session_state.get("goal_dup_for") == d["goal"]["text"].strip() else None
            if twin:
                dup_notice(twin)
            goalmaker.form("goal", draft, put, pace=settings.units(config), ideas=directions.IDEAS.get(identity))
        else:
            twin = near_goal(d)            # (the designed title repeats one of hers)
            if twin:
                dup_notice(twin)
            ready = ready and not twin
            # the same steps as the setup, on one page: all of it or some parts, then what it's for
            goalmaker.scope("gs", draft, put, pace=settings.units(config))
            st.markdown("#### What's it for?")
            goalmaker.purpose("gp", draft, put, identity)
            problem = st.session_state.pop("goal_problem", "")
            if problem:
                st.html(f'<p class="ob-note">{escape(problem)}</p>')
            elif twin:
                st.html('<p class="ob-note" role="status">Continue the goal you have, or say this one is different '
                        "(above), to add it.</p>")
            elif not ready:
                st.html('<p class="ob-note" role="status">Choose all of it or some parts, and what it\'s for, '
                        "to add this goal.</p>")
            with st.container(key="ob_nav", horizontal=True, vertical_alignment="center"):
                st.button("Add this goal", key="goal_add", type="primary", on_click=add, disabled=not ready)
                st.button("Something else", key="goal_again", type="tertiary", on_click=other)
        if st.button("Cancel", key="goal_cancel", type="tertiary"):
            ui.clear_goal_draft()
            st.switch_page("views/settings.py")
