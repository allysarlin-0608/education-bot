"""Settings: her subjects, daily pace, reading plan, and where each subject
starts. A change is saved as she makes it (by her user_id) and the other
pages use it straight away. Levels aren't edited by hand: the placement
check sets them. Nothing here touches her learning history."""
from html import escape

import streamlit as st

from coach import choices, core, settings, storage, ui

config = ui.config()

st.html('<div id="settings-page" hidden></div>')
st.markdown("## Settings")

if settings.is_legacy(config):
    st.caption("Settings need their table in the database first. Run supabase/user_settings.sql in "
               "Supabase's SQL Editor, then refresh: you'll be asked to choose your subjects and pace.")
    st.code(storage.SETTINGS_SQL, language="sql")
    st.stop()


def update(**fields) -> bool:
    """Save a change now; if it isn't valid, say why and keep what was there."""
    try:
        new = settings.change(ui.config(), settings.now_iso(), **fields)
    except ValueError:
        st.session_state.set_problem = "Keep at least one subject."
        return False
    return ui.save_settings(new)


def pick_subject(topic: str) -> None:
    st.session_state.set_focus = topic           # the lens goes to the row she touched
    now = ui.config()["subjects"]
    new = settings.toggle_subject(now, topic)
    if new != now and update(subjects=new):          # past the limit: only looked at, nothing changes
        st.session_state.set_subjects_changed = True


def pick_pace(n: int) -> None:
    update(units_per_day=n)


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
        levels = dict(ui.config()["subject_levels"], **{topic: c["level"]})
        if update(subject_levels=levels):
            st.session_state.set_placed = (topic, c["level"], c["score"])
        st.session_state.pop("set_retake", None)


problem = st.session_state.pop("set_problem", "")

# ---------- Subjects ----------
with st.container(key="set_sec_subjects"):
    st.markdown("#### Subjects")
    chosen = config["subjects"]
    focus = st.session_state.get("set_focus")
    choices.rows("setsubj", [(t, core.TOPICS[t], settings.DESCRIPTIONS[t], {"n": k})
                             for k, t in enumerate(settings.SUBJECTS, start=1)],
                 chosen, pick_subject, multi=True, full=len(chosen) >= settings.MAX_SUBJECTS,
                 focus=focus if focus in settings.SUBJECTS else (chosen[0] if chosen else None), style="index")
    order = " → ".join(core.TOPICS[t] for t in chosen)
    st.html(f'<p class="ob-note">{len(chosen)} of {settings.MAX_SUBJECTS} · one a day, in this order: {escape(order)}</p>'
            + (f'<p class="ob-note">{escape(problem)}</p>' if problem else "")
            + ('<p class="ob-note set-kept">Your existing learning history will be preserved.</p>'
               if st.session_state.get("set_subjects_changed") else ""))

# ---------- Daily pace ----------
with st.container(key="set_sec_pace"):
    st.markdown("#### Daily pace")
    choices.rows("setpace", [(n, name, settings.pace_line(n), {"bars": n}) for n, (name, _) in settings.PACES.items()],
                 [config["units_per_day"]], pick_pace, style="pace")

# ---------- Starting level ----------
with st.container(key="set_sec_level"):
    st.markdown("#### Starting level")
    placed = st.session_state.pop("set_placed", None)
    open_topic = st.session_state.get("set_retake")
    for t in chosen:
        level = settings.start_level(config, t) or "Beginner"
        with st.container(key=f"setlvl_{t}", horizontal=True, vertical_alignment="center"):
            st.html(f'<p class="set-level"><span>{escape(core.TOPICS[t])}</span><b>{escape(level)}</b></p>')
            if open_topic == t:
                st.button("Cancel", key=f"setcancel_{t}", type="tertiary", on_click=cancel)
            else:
                st.button("Retake placement quiz", key=f"setretake_{t}", type="tertiary",
                          on_click=retake, args=(t,))
        if open_topic == t:
            choices.placement(f"set_{t}", t, st.session_state.set_check,
                              on_answer=check_answer, on_move=check_move, on_again=lambda t=t: retake(t))
        if placed and placed[0] == t:
            st.html(f'<p class="ob-note">{escape(core.TOPICS[t])} now starts at {escape(placed[1])} '
                    f'({placed[2]} of 5 right).</p>')

# ---------- Reading ----------
with st.container(key="set_sec_reading"):
    st.markdown("#### Reading")
    with st.container(key="ob_toggle"):
        st.toggle("Add a 14-day reading plan", value=config["reading_enabled"], key="set_reading",
                  on_change=set_reading)
