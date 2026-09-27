"""Settings: her subjects, daily pace, reading plan, and where each subject
starts. A change is saved as she makes it (by her user_id) and the other
pages use it straight away. Levels aren't edited by hand: the placement
check sets them. Nothing here touches her learning history."""
import json
from html import escape

import streamlit as st

from coach import auth, choices, core, settings, stage, storage, ui, visuals

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
# the same stage as the setup's: the subject in focus, and the way into its world
with st.container(key="set_sec_subjects"):
    st.markdown("#### Subjects")
    chosen = config["subjects"]
    # the subject in focus: the one she touched last, else the one the address
    # names (a refresh, Back from a world); the address is kept saying the same
    asked = st.query_params.get("subject")
    looked = st.session_state.get("set_focus")
    focus = stage.focus_of(looked if looked in settings.SUBJECTS else asked, chosen)
    st.session_state.set_focus = focus
    if asked != focus:
        st.query_params["subject"] = focus
    with st.container(key="set_grid_subjects"):
        with st.container(key="set_stage"):
            st.html(stage.html(focus, "setsubj"))
            with st.container(key=f"enter_{focus}", horizontal=True):
                if st.button(f"Enter {visuals.subject(focus)['title']}", type="tertiary", key="set_world",
                             icon=":material/arrow_outward:"):
                    ui.enter_world(focus)
        with st.container(key="set_body"):
            choices.rows("setsubj", stage.rows(), chosen, pick_subject, multi=True,
                         full=len(chosen) >= settings.MAX_SUBJECTS, focus=focus, style="index")
            order = " → ".join(visuals.subject(t)["title"] for t in chosen)
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


# ---------- Invites (public, admins only): who may sign in while in beta ----------
def _email_ok(e: str) -> bool:
    return "@" in e and "." in e.split("@")[-1] and " " not in e


def add_invite() -> None:
    email = st.session_state.inv_email.strip().lower()
    if not _email_ok(email):
        st.session_state.inv_problem = "That doesn't look like an email address."
        return
    try:
        st.session_state.coach_store.add_invite(email, st.session_state.inv_note.strip())
    except storage.StorageError as e:
        st.session_state.inv_problem = f"Couldn't add it ({e})."
        return
    st.session_state.inv_email = st.session_state.inv_note = ""


def remove_invite(email: str) -> None:
    try:
        st.session_state.coach_store.remove_invite(email)
    except storage.StorageError as e:
        st.session_state.inv_problem = f"Couldn't remove it ({e})."


if auth.is_admin():
    with st.container(key="set_sec_invites"):
        st.markdown("#### Invites")
        st.html('<p class="ob-note">Only these emails can sign in. A change takes effect at once.</p>')
        with st.container(key="inv_add", horizontal=True, vertical_alignment="bottom"):
            st.text_input("Email", key="inv_email", placeholder="name@example.com")
            st.text_input("Note", key="inv_note", placeholder="Optional")
            st.button("Invite", key="inv_add_btn", on_click=add_invite)
        problem_i = st.session_state.pop("inv_problem", "")
        if problem_i:
            st.html(f'<p class="ob-note">{escape(problem_i)}</p>')
        try:
            invites = st.session_state.coach_store.list_invites()
        except storage.StorageError as e:
            invites = []
            st.html(f'<p class="ob-note">Couldn\'t load the list ({escape(str(e))}).</p>')
        for inv in invites:
            slug = "".join(c if c.isalnum() else "_" for c in inv["email"])
            with st.container(key=f"inv_row_{slug}", horizontal=True, vertical_alignment="center"):
                st.html(f'<p class="set-level"><span>{escape(inv["email"])}</span>'
                        f'<b>{escape(inv.get("note") or "")}</b></p>')
                st.button("Remove", key=f"inv_rm_{slug}", type="tertiary",
                          on_click=remove_invite, args=(inv["email"],))


# ---------- Your data (public): a copy of it all, or all of it gone ----------
DELETE_WARNING = "This permanently deletes your account and all your learning history. This can't be undone."


def ask_delete() -> None:
    st.session_state.del_open = True


def cancel_delete() -> None:
    st.session_state.del_open = False
    st.session_state.del_confirm = ""


if auth.is_public():
    with st.container(key="set_sec_data"):
        st.markdown("#### Your data")
        try:
            mine = json.dumps(st.session_state.coach_store.export_my_data(), ensure_ascii=False, indent=2, default=str)
        except storage.StorageError as e:
            mine = None
            st.html(f'<p class="ob-note">Couldn\'t gather your data ({escape(str(e))}). Refresh in a moment.</p>')
        with st.container(key="data_actions", horizontal=True, vertical_alignment="center"):
            if mine is not None:
                st.download_button("Download my data", mine, file_name="daily-learning-coach-data.json",
                                   mime="application/json", key="data_download")
            st.button("Delete my account", key="data_delete", type="tertiary", on_click=ask_delete)
        if st.session_state.get("del_open"):
            with st.container(key="del_confirm_box"):
                st.html(f'<p class="del-warn" role="alert">{escape(DELETE_WARNING)}</p>')
                st.text_input("Type DELETE to confirm", key="del_confirm")
                with st.container(key="del_buttons", horizontal=True):
                    if st.button("Delete everything", key="del_go", type="primary",
                                 disabled=st.session_state.get("del_confirm", "").strip() != "DELETE"):
                        try:
                            st.session_state.coach_store.delete_my_account()
                        except storage.StorageError as e:
                            st.error(f"Nothing was deleted ({e}). Try again in a moment.")
                        else:
                            for key in list(st.session_state.keys()):
                                del st.session_state[key]
                            st.logout()
                    st.button("Cancel", key="del_cancel", type="tertiary", on_click=cancel_delete)
