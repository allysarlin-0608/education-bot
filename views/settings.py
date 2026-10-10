"""Learning Plan (the settings of her learning): her subjects and goals,
daily pace, where each subject starts, reminders and the reading plan. A
change is saved as she makes it (by her user_id) and the other pages use it
straight away. Levels aren't edited by hand: the placement check sets them.
Nothing here touches her learning history. Her account (profile, plan, her
data, and the admin's tools) is on its own page, views/account.py."""
from datetime import time as dtime
from datetime import timedelta
from html import escape

import streamlit as st

from coach import catalog, choices, curriculum, paths, settings, stage, storage, ui, visuals
from coach import prefs as prefs_

config = ui.config()

st.html('<div id="settings-page" hidden></div>')
st.markdown("## Learning Plan")
st.caption("What you learn, how much each day, and in what order. Your profile, plan and data are in Account.")

if settings.is_legacy(config):
    st.caption("Settings need their table in the database first. Run supabase/user_settings.sql in "
               "Supabase's SQL Editor, then refresh: you'll be asked to choose your subjects and pace.")
    st.code(storage.SETTINGS_SQL, language="sql")
    st.stop()


def update(**fields) -> bool:
    """Save a change now; if it isn't valid, say why and keep what was there."""
    ui.refresh_settings()          # apply the change to what is stored now (another tab may have changed it)
    try:
        new = settings.change(ui.config(), settings.now_iso(), **fields)
    except ValueError:
        st.session_state.set_problem = "Keep at least one subject or goal."
        return False
    return ui.save_settings(new)


def pick_subject(topic: str) -> None:
    st.session_state.set_focus = topic           # the lens goes to the row she touched
    ui.refresh_settings()
    now = settings.chosen_subjects(ui.config())
    new = settings.toggle_subject(now, topic)
    if new != now and update(subjects=new):          # past the limit: only looked at, nothing changes
        st.session_state.set_subjects_changed = True


def pick_pace(n: int) -> None:
    if update(units_per_day=n):
        ui.refit_today(n)


def set_reading() -> None:
    update(reading_enabled=bool(st.session_state.set_reading))


# the placement check being retaken (kept for this visit only; nothing is
# saved until it gives a level)
def retake(topic) -> None:
    st.session_state.set_retake = topic
    st.session_state.set_check = choices.fresh()


def cancel() -> None:
    st.session_state.pop("set_retake", None)


def check_answer(i: int) -> None:
    st.session_state.set_check = choices.answer(st.session_state.set_check, i)


def check_move(k: int) -> None:
    topic = st.session_state.set_retake
    c = st.session_state.set_check = choices.move(st.session_state.set_check, topic, k)
    if c.get("level"):
        ui.refresh_settings()
        levels = dict(ui.config()["subject_levels"], **{topic: c["level"]})
        if update(subject_levels=levels):
            st.session_state.set_placed = (topic, c["level"], c["score"])
        st.session_state.pop("set_retake", None)


problem = st.session_state.pop("set_problem", "")

# ---------- Subjects ----------
# the same stage as the setup's: the subject in focus, and the way into its world
with st.container(key="set_sec_subjects"):
    st.markdown("#### Subjects")
    chosen = settings.chosen_subjects(config)
    builtin = [t for t in chosen if t in settings.SUBJECTS]       # (her goals have their own section)
    # the subject in focus: the one she touched last, else the one the address
    # names (a link from a world). The address isn't rewritten to follow it:
    # Streamlit adds a browser history step for every such change, so Back
    # would walk through them instead of leaving the page.
    asked = st.query_params.get("subject")
    looked = st.session_state.get("set_focus")
    focus = stage.focus_of(looked if looked in settings.SUBJECTS else asked, builtin)
    st.session_state.set_focus = focus
    with st.container(key="set_grid_subjects"):
        with st.container(key="set_stage"):
            st.html(stage.html(focus, "setsubj"))
            # the ways into a subject are for hers; one not chosen is added by tapping its row
            if focus in builtin:
                with st.container(key="set_links", horizontal=True):
                    with st.container(key=f"enter_{focus}", horizontal=True):
                        if st.button(f"Enter {visuals.subject(focus)['title']}", type="tertiary", key="set_world"):
                            ui.enter_world(focus)
                    if st.button("Course map", type="tertiary", key="set_course"):
                        ui.open_course(focus)
            else:
                st.html(f'<p class="ob-note set-notyet">Not in your days yet. Tap '
                        f'{escape(visuals.subject(focus)["title"])} in the list to add it.</p>')
        with st.container(key="set_body"):
            choices.rows("setsubj", stage.rows(), builtin, pick_subject, multi=True,
                         full=len(builtin) >= settings.MAX_SUBJECTS, focus=focus, style="index")
            order = " → ".join(catalog.name(t) for t in chosen)
            st.html(f'<p class="ob-note">{len(builtin)} of {settings.MAX_SUBJECTS} · one a day, in this order: {escape(order)}</p>'
                    + (f'<p class="ob-note">{escape(problem)}</p>' if problem else "")
                    + ('<p class="ob-note set-kept">Your existing learning history will be preserved.</p>'
                       if st.session_state.get("set_subjects_changed") else ""))

# ---------- Your goals: her own, each with the path designed for it ----------
def pause_goal(goal_id: str) -> None:
    ui.refresh_settings()
    rest = [t for t in settings.chosen_subjects(ui.config()) if t != goal_id]
    if not rest:
        st.session_state.goal_set_problem = "Keep at least one subject or goal."
        return
    if update(subjects=rest):
        ui.save_path(st.session_state.coach_log, paths.archive(catalog.path(goal_id)))


def resume_goal(goal_id: str) -> None:
    ui.refresh_settings()
    try:
        new = settings.add_goal(ui.config(), goal_id, settings.now_iso())
    except ValueError as e:
        st.session_state.goal_set_problem = str(e)
        return
    if ui.save_path(st.session_state.coach_log, paths.restore(catalog.path(goal_id))):
        ui.save_settings(new)


with st.container(key="set_sec_goals"):
    st.markdown("#### Your goals")
    mine = catalog.goals(active_only=False)
    unreadable = getattr(st.session_state.coach_store, "paths_error", None)
    if unreadable:
        st.html(f'<p class="ob-note" role="status">{escape(unreadable)}</p>')
    elif not mine:
        st.html('<p class="ob-note">Tell us what you want to learn and we\'ll design a path for it.</p>')
    for g in mine:
        on = g["status"] == "active"
        p = curriculum.progress(st.session_state.coach_log, g["id"])
        with st.container(key=f"setgoal_{g['id']}_{'on' if on else 'off'}", horizontal=True, vertical_alignment="center"):
            st.html(f'<p class="set-goal"><span>{escape(g["title"])}</span>'
                    f'<b>{p["done"]} of {p["written"]} lessons · {escape(g["level"])}{"" if on else " · paused"}</b></p>')
            if st.button("Course map", key=f"setgoal_map_{g['id']}", type="tertiary"):
                ui.open_course(g["id"])
            if on:
                st.button("Pause", key=f"setgoal_pause_{g['id']}", type="tertiary", on_click=pause_goal, args=(g["id"],))
            else:
                st.button("Resume", key=f"setgoal_resume_{g['id']}", type="tertiary", on_click=resume_goal, args=(g["id"],))
    goal_problem = st.session_state.pop("goal_set_problem", "")
    if goal_problem:
        st.html(f'<p class="ob-note">{escape(goal_problem)}</p>')
    if st.button("Add a goal", key="set_goal_add"):
        ui.clear_goal_draft()                     # a new goal: never a draft left from before
        st.switch_page("views/goal.py")

# ---------- Daily pace ----------
with st.container(key="set_sec_pace"):
    st.markdown("#### Daily pace")
    choices.rows("setpace", [(n, name, settings.pace_line(n), {"bars": n}) for n, (name, _) in settings.PACES.items()],
                 [config["units_per_day"]], pick_pace, style="pace")

# ---------- Starting level (of our subjects: a goal's is its path's) ----------
if builtin:
    with st.container(key="set_sec_level"):
        st.markdown("#### Starting level")
        placed = st.session_state.pop("set_placed", None)
        open_topic = st.session_state.get("set_retake")
        for t in builtin:
            level = settings.start_level(config, t) or "Beginner"
            with st.container(key=f"setlvl_{t}", horizontal=True, vertical_alignment="center"):
                st.html(f'<p class="set-level"><span>{escape(catalog.name(t))}</span><b>{escape(level)}</b></p>')
                if open_topic == t:
                    st.button("Cancel", key=f"setcancel_{t}", type="tertiary", on_click=cancel)
                else:
                    st.button("Retake placement quiz", key=f"setretake_{t}", type="tertiary",
                              on_click=retake, args=(t,))
            if open_topic == t:
                choices.placement(f"set_{t}", t, st.session_state.set_check,
                                  on_answer=check_answer, on_move=check_move, on_again=lambda t=t: retake(t))
            if placed and placed[0] == t:
                st.html(f'<p class="ob-note">{escape(catalog.name(t))} now starts at {escape(placed[1])} '
                        f'({placed[2]} of 5 right).</p>')

# ---------- Reminders: a gentle note at her time, if she hasn't studied yet ----------
def set_reminder() -> None:
    on = bool(st.session_state.set_rem_on)
    at = st.session_state.get("set_rem_time")
    ui.update_prefs(reminder_on=on, reminder_time=at.strftime("%H:%M") if at else prefs_.DEFAULT_TIME)


with st.container(key="set_sec_reminders"):
    st.markdown("#### Reminders")
    habits = ui.prefs()
    with st.container(key="ob_toggle_rem"):
        st.toggle("Remind me to learn", value=habits["reminder_on"], key="set_rem_on", on_change=set_reminder)
    if habits["reminder_on"]:
        hh, mm = map(int, habits["reminder_time"].split(":"))
        st.time_input("At", value=dtime(hh, mm), step=timedelta(minutes=30), key="set_rem_time",
                      on_change=set_reminder)
    st.html('<p class="ob-note">'
            + (f"If you haven't studied by {escape(habits['reminder_time'])}, Today shows a short, friendly note. "
               "Never more than once a day." if habits["reminder_on"]
               else "Off. Turn it on for a short, friendly note at a time you choose, once a day at most.")
            + "</p>")
    if st.session_state.get("coach_prefs_error"):
        st.html(f'<p class="ob-note">{escape(st.session_state.coach_prefs_error)}</p>')

# ---------- Reading ----------
with st.container(key="set_sec_reading"):
    st.markdown("#### Reading")
    with st.container(key="ob_toggle"):
        st.toggle("Add a 14-day reading plan", value=config["reading_enabled"], key="set_reading",
                  on_change=set_reading)
