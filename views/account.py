"""Account: who she is (Profile), her plan (Subscription), and her account
settings: a copy of her data or all of it deleted; for admins, who may sign
in and whether GNOSIS works (Insights). Her learning settings are Learning
Plan (views/settings.py).

The plan is shown as it is: everyone is on Free while plans are prepared
(coach/plans.py: nothing enforced, no payment exists); the plan she chose in
the setup is shown as her choice, never as a paid subscription."""
import json
from datetime import timedelta
from html import escape

import streamlit as st

from coach import auth, metrics, plans, storage, ui

st.html('<div id="settings-page" hidden></div>')        # (the same quiet sections as Learning Plan)
st.markdown("## Account")

# ---------- Profile ----------
with st.container(key="set_sec_profile"):
    st.markdown("#### Profile")
    who = auth.identity() if auth.is_public() else None
    if who:
        st.html('<dl class="ins-list">'
                f'<div><dt>Name</dt><dd>{escape(who["name"] or "—")}<small></small></dd></div>'
                f'<div><dt>Email</dt><dd>{escape(who["email"])}<small>Used to sign in</small></dd></div></dl>'
                '<p class="ob-note">Your name and picture come from how you signed in. Changing them here '
                "isn't available yet.</p>")
    else:
        st.html('<p class="ob-note">This is your personal GNOSIS: there is no account to sign in to, '
                "and your learning is kept with this app.</p>")

# ---------- Subscription ----------
with st.container(key="set_sec_plan"):
    st.markdown("#### Subscription")
    current = plans.plan_of(ui.config())
    chosen = ui.prefs().get("plan_choice")
    rows = [("Your plan", plans.NAMES[current], plans.price_line(current))]
    if plans.known(chosen) and chosen != current:
        rows.append(("You chose", plans.NAMES[chosen], plans.price_line(chosen)))
    rows.append(("Payments", "None", "Nothing has been charged"))
    st.html('<dl class="ins-list">' + "".join(
        f'<div><dt>{escape(a)}</dt><dd>{escape(b)}<small>{escape(c)}</small></dd></div>' for a, b, c in rows) + "</dl>"
        '<p class="ob-note">Paid plans aren\'t open yet. While they are being prepared, everyone can use every '
        "feature that exists, at no cost. Upgrading, changing and cancelling a plan will be here once payments "
        "open.</p>")


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


# ---------- Insights (public, admins only): whether GNOSIS works (coach/metrics.py) ----------
if auth.is_admin():
    with st.container(key="set_sec_insights"):
        st.markdown("#### Insights")
        since = st.date_input("People who signed up since", value=ui.today() - timedelta(days=30),
                              max_value=ui.today(), key="ins_since")
        try:
            m = st.session_state.coach_store.metrics(since, ui.today())
        except storage.StorageError as e:
            st.html(f'<p class="ob-note">Couldn\'t load the numbers ({escape(str(e))}). '
                    "If the goals tables aren't set up yet, run supabase/goals.sql first.</p>")
        else:
            rows = [("Signed up", str(m["signed_up"]), ""),
                    ("Set a goal or subjects", str(m["set_up"]), metrics.share(m["set_up"], m["signed_up"])),
                    ("Passed a first lesson", str(m["first_lesson"]), metrics.share(m["first_lesson"], m["signed_up"])),
                    ("Came back the next day", str(m["came_back_next_day"]),
                     metrics.share(m["came_back_next_day"], m["eligible_next_day"])),
                    ("Still active after a week", str(m["active_after_a_week"]),
                     metrics.share(m["active_after_a_week"], m["eligible_week"])),
                    ("Lessons per learner per week", str(m["lessons_per_learner_week"]), ""),
                    ("Reminders shown", str(m.get("reminders_shown", 0)), ""),
                    ("…followed by a lesson that day", str(m.get("reminded_sessions", 0)),
                     metrics.share(m.get("reminded_sessions", 0), m.get("reminders_shown", 0)))]
            st.html('<dl class="ins-list">' + "".join(
                f'<div><dt>{escape(a)}</dt><dd>{escape(b)}<small>{escape(c)}</small></dd></div>' for a, b, c in rows)
                + "</dl>")
            st.html('<p class="ob-note">Counts only: no lesson, answer or goal text is kept for these. '
                    "Next day and a week are out of the people who signed up at least that long ago.</p>")
            # Phase 3: is learning happening? (learning_signals, supabase/mastery.sql; all learners, since the date)
            g = lambda k: int(m.get(k) or 0)          # noqa: E731
            learning = [
                ("Ideas got wrong, then right later", f"{g('recovered')} of {g('missed')}",
                 metrics.share(g("recovered"), g("missed")),
                 "After a mistake, how often the idea is answered right on a later day."),
                ("Still known after two weeks", f"{g('held')} of {g('held') + g('slipped')}",
                 metrics.share(g("held"), g("held") + g("slipped")),
                 "Solid or mastered ideas asked again 14+ days after their last practice."),
                ("Ideas mastered", str(g("mastered")), "", "Ideas that reached mastered (known again and again over time)."),
                ("Practice sets finished", str(g("practice_done")), "", ""),
                ("Ideas explained back", str(g("explained")), "", ""),
                ("Questions to the coach", str(g("tutor_question")), "", ""),
                ("…that showed a misunderstanding", str(g("tutor_confused")),
                 metrics.share(g("tutor_confused"), g("tutor_question")), "These ideas come back in Review the next day."),
            ]
            st.markdown("##### Learning")
            st.html('<dl class="ins-list">' + "".join(
                f'<div><dt>{escape(a)}{f"<small>{escape(d)}</small>" if d else ""}</dt>'
                f'<dd>{escape(b)}<small>{escape(c)}</small></dd></div>' for a, b, c, d in learning) + "</dl>")
            if "missed" not in m:
                st.html('<p class="ob-note">The learning numbers need supabase/mastery.sql run first.</p>')

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
        # Her data is gathered when she asks for it, in this run (where who
        # she is is known: a deferred download runs on another thread, signed
        # in as no one, ISS-019), not on every click on this page (ISS-015).
        if st.session_state.pop("data_wanted", False):
            try:
                st.session_state.data_export = json.dumps(
                    st.session_state.coach_store.export_my_data(), ensure_ascii=False, indent=2, default=str)
            except storage.StorageError as e:
                st.html(f'<p class="ob-note">Couldn\'t gather your data ({escape(str(e))}). Try again in a moment.</p>')
        with st.container(key="data_actions", horizontal=True, vertical_alignment="center"):
            if st.session_state.get("data_export") is None:
                st.button("Download my data", key="data_prepare",
                          on_click=lambda: st.session_state.update(data_wanted=True))
            else:
                st.download_button("Save my data as a file", st.session_state.data_export,
                                   file_name="gnosis-data.json", mime="application/json", key="data_download",
                                   on_click=lambda: st.session_state.pop("data_export", None))
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
                            auth._go(auth.signout_url(deleted=True))    # revoke the session, clear the cookie
                    st.button("Cancel", key="del_cancel", type="tertiary", on_click=cancel_delete)
