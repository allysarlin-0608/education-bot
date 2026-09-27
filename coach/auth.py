"""Who is using the app, and whether they may.

APP_MODE (secrets or environment):
- "personal" (the default): one person's app, exactly as it has always been:
  the APP_PASSWORD gate, and one fixed user id (COACH_USER_ID, else "owner").
- "public": accounts with Supabase Auth — Google, or email and password (with
  email confirmation and password reset). Passwords go straight from this
  server to Supabase; they are never stored, logged or shown here.
  A person is their Supabase user id (a uuid), the same whichever way they
  sign in; Supabase links a Google sign-in to an existing account with the
  same verified email. While in beta only invited emails can make an account
  (a database hook refuses the rest; supabase/accounts.sql).

The session lives in HttpOnly cookies written by the server (routes.py,
session_cookie.py); here it is st.user, and the database is always asked as
that person (their access token), so row level security applies.

get_current_user_id() is the one answer to "whose data is this?"; storage.py
asks it on every call."""
import html
import json
import re
import time

import streamlit as st

from coach import ui

PERSONAL, PUBLIC = "personal", "public"
MIN_PASSWORD = 7

SIGNIN_FAILED = "Sign-in didn't complete. Please try again."
INVITE_ONLY = "This app is invite-only for now. Ask the person who shared it with you to add your email."
NEUTRAL = "If an account can be created with this email, we've sent you a link. Check your inbox."
NETWORK = "We couldn't reach the sign-in service. Check your connection and try again."
PASSWORD_RULE = f"At least {MIN_PASSWORD} characters, with letters and numbers."
PASSWORD_PROBLEM = f"Use at least {MIN_PASSWORD} characters, with at least one letter and one number."

NOTES = {   # ?auth=… / ?auth_error=… left by routes.py, shown once
    "signed_out": "You've signed out.",
    "deleted": "Your account and all your learning history have been deleted.",
    "google": SIGNIN_FAILED,
    "link": "This link has expired or has already been used. You can ask for a new one below.",
    "link_unknown": ("We couldn't finish that link here. If you were confirming your email, "
                     "try signing in; if you were resetting your password, ask for a new link."),
    "expired": "That took too long. Please sign in again.",
    "network": NETWORK,
}
ERRORS = {  # supa_auth.AuthError codes → what the person reads
    "invalid_credentials": "That email and password don't match. Try again, or reset your password.",
    "email_not_confirmed": "Please confirm your email first — the link is in your inbox.",
    "weak_password": PASSWORD_PROBLEM,
    "invalid_email": "Enter a valid email address.",
    "rate_limited": "Too many attempts. Please wait a few minutes and try again.",
    "not_invited": INVITE_ONLY,
    "session_expired": "Your session has ended. Please sign in again.",
    "network": NETWORK,
    "failed": "Something went wrong. Please try again.",
}


def mode() -> str:
    return PUBLIC if ui.get_setting("APP_MODE").strip().lower() == PUBLIC else PERSONAL


def is_public() -> bool:
    return mode() == PUBLIC


def identity():
    """The signed-in person (st.user, from the session cookie), or None.
    Without a "sub" (their user id) there is no one signed in."""
    try:
        user = st.user
        if not user.get("is_logged_in"):
            return None
        sub = user.get("sub")
    except Exception:  # no [auth] configured: st.user has nothing
        return None
    if not sub:
        return None
    email = str(user.get("email") or "").strip().lower()
    return {"sub": str(sub), "email": email, "name": str(user.get("name") or email.split("@")[0]),
            "picture": str(user.get("picture") or ""), "exp": int(user.get("exp") or 0),
            "recovery": bool(user.get("recovery"))}


def access_token():
    """The signed-in person's access token (for the database), or None."""
    try:
        return st.user.tokens.get("access") if st.user.get("is_logged_in") else None
    except Exception:
        return None


def get_current_user_id():
    """Whose data this session reads and writes. personal: the one fixed id;
    public: the signed-in person's user id, or None when no one is signed in."""
    if not is_public():
        return ui.personal_user_id()
    who = identity()
    return who["sub"] if who else None


def is_admin() -> bool:
    """May manage invitations (and has no daily AI limit): their email is in
    the app_admins table. Asked once per session."""
    who = identity() if is_public() else None
    if not who:
        return False
    cache = st.session_state.setdefault("auth_admin", {})
    if who["sub"] not in cache:
        from coach import storage
        store = st.session_state.get("coach_store")
        try:
            cache[who["sub"]] = bool(store and store.is_admin(who["email"]))
        except storage.StorageError:
            return False                     # not cached: asked again next time
    return cache[who["sub"]]


# ---------------------------------------------------------------- navigation
LEAVE_FRAME = "a.si-google, a.si-plain, a.acct-out, a.si-continue"


def _raw(markup: str) -> None:
    """Our own markup for links that leave the app. Streamlit's sanitizer
    drops target=, so one delegated handler (installed once per page) opens
    them in the whole window, not the app's frame; the Google button also
    shows that it's working. Never pass it anything unescaped."""
    st.html(markup)
    st.html("<script>(function(){"
            "const docs=[document];try{if(window.parent&&window.parent.document!==document)docs.push(window.parent.document)}catch(e){}"
            "for(const d of docs){if(d.__gnLeave)continue;d.__gnLeave=true;"
            "d.addEventListener('click',function(e){"
            f"const a=e.target.closest&&e.target.closest({json.dumps(LEAVE_FRAME)});if(!a)return;"
            "e.preventDefault();if(a.classList.contains('si-google')){a.classList.add('is-busy');"
            "const t=a.querySelector('span');if(t)t.textContent='Opening Google\u2026';}"
            "(window.top||window).location.href=a.href;},true);}})();</script>",
            unsafe_allow_javascript=True)


def _go(url: str) -> None:
    """Send the whole window (not just the app's frame) to url."""
    st.html(f"<script>(window.top || window).location.replace({json.dumps(url)});</script>",
            unsafe_allow_javascript=True)
    _raw(f'<p class="si-note">Continuing… <a class="si-continue" href="{html.escape(url)}">Continue</a></p>')
    st.stop()


def _routes_base() -> str:
    from coach import session_cookie
    return session_cookie.routes_base()


def signout_url(deleted: bool = False) -> str:
    return f"{_routes_base()}/auth/signout" + ("?why=deleted" if deleted else "")


def _take_note() -> None:
    """Move ?auth=… / ?auth_error=… into the session and out of the address."""
    for key in ("auth", "auth_error"):
        value = st.query_params.get(key)
        if value:
            st.session_state.auth_note = (key, value)
            del st.query_params[key]


def _reload_for_fresh_session() -> None:
    """The access token is about to expire: reload the page so the server
    renews the session (routes.RefreshSession). Once a minute at most."""
    last = st.session_state.get("auth_reloaded_at", 0)
    if time.time() - last < 60:
        return
    st.session_state.auth_reloaded_at = time.time()
    st.html("<script>(window.top || window).location.reload();</script>", unsafe_allow_javascript=True)
    st.stop()


# ---------------------------------------------------------------- the sign-in page
def password_ok(password: str) -> bool:
    """The same rule Supabase enforces (Auth → Email: minimum 7, letters and
    digits); checked here first only to say so sooner."""
    return (len(password) >= MIN_PASSWORD and any(c.isalpha() for c in password)
            and any(c.isdigit() for c in password))


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(e: str) -> bool:
    return bool(EMAIL_RE.match(e)) and len(e) <= 254


def _view(name: str) -> None:
    st.session_state.auth_view = name
    st.session_state.pop("auth_problem", None)
    if name == "resend" and st.session_state.get("auth_resend_email"):
        st.session_state.rs_email = st.session_state.auth_resend_email


FORM_KEYS = {"signin": ("si_email", "si_password"), "signup": ("su_email", "su_password", "su_confirm"),
             "forgot": ("fp_email",), "resend": ("rs_email",), "reset": ("rp_password", "rp_confirm")}


def _queue(action: str) -> None:
    """A form was sent: take what was typed and note what to do; the next run
    shows the button as busy while it's done, so it can't be sent twice. The
    values (a password included) live only until that run has used them."""
    st.session_state.auth_pending = (action, {k: str(st.session_state.get(k) or "") for k in FORM_KEYS[action]})
    st.session_state.pop("auth_problem", None)


def _form_values(*keys) -> list:
    sent = st.session_state.get("auth_sent", {})
    return [sent.get(k, "") for k in keys]


def _forget_passwords() -> None:
    st.session_state.pop("auth_sent", None)
    for k in ("si_password", "su_password", "su_confirm", "rp_password", "rp_confirm"):
        st.session_state.pop(k, None)


def _browser():
    from coach import session_cookie
    return session_cookie.browser_key(st.context.cookies)


def _signed_in(session: dict, **flags) -> None:
    """A session from Supabase: hand it to the server to become the cookie."""
    from coach import routes, supa_auth
    _forget_passwords()
    url = routes.handoff(supa_auth.profile(session["user"]), session, _browser(), **flags)
    _go(url)


def _run(action: str) -> None:
    """Do what a form asked (called while the page shows it as busy)."""
    from coach import routes, supa_auth
    problem, done = None, None
    try:
        if action == "signin":
            email, password = _form_values("si_email", "si_password")
            email = email.strip().lower()
            if not _valid_email(email):
                problem = ERRORS["invalid_email"]
            elif not password:
                problem = "Enter your password."
            else:
                session = supa_auth.sign_in(email, password)
                _signed_in(session)
        elif action == "signup":
            email, password, confirm = _form_values("su_email", "su_password", "su_confirm")
            email = email.strip().lower()
            if not _valid_email(email):
                problem = ERRORS["invalid_email"]
            elif not password_ok(password):
                problem = PASSWORD_PROBLEM
            elif password != confirm:
                problem = "The passwords don't match."
            else:
                supa_auth.sign_up(email, password, *routes.email_flow("signup"))
                done = "sent"
        elif action == "forgot":
            (email,) = _form_values("fp_email")
            email = email.strip().lower()
            if not _valid_email(email):
                problem = ERRORS["invalid_email"]
            else:
                supa_auth.request_reset(email, *routes.email_flow("recovery"))
                done = "sent"
        elif action == "resend":
            (email,) = _form_values("rs_email")
            email = email.strip().lower()
            if not _valid_email(email):
                problem = ERRORS["invalid_email"]
            else:
                supa_auth.resend_confirmation(email, *routes.email_flow("signup"))
                done = "sent"
    except supa_auth.AuthError as e:
        if e.code == "not_invited":
            done = "invite"
        elif e.code == "exists" or (action in ("signup", "forgot", "resend") and e.code == "failed"):
            done = "sent"            # never say whether an email is registered
        else:
            problem = ERRORS.get(e.code, ERRORS["failed"])
            if e.code == "email_not_confirmed":
                st.session_state.auth_resend_email = _form_values("si_email")[0].strip().lower()
                st.session_state.auth_unconfirmed = True
    _forget_passwords()
    if done:
        _view(done)
    elif problem:
        st.session_state.auth_problem = problem


def _google_button(busy: bool) -> None:
    href = html.escape(f"{_routes_base()}/auth/google")
    _raw(f'<a class="si-google{" is-off" if busy else ""}" href="{href}"><span>Continue with Google</span></a>')
    st.html('<p class="si-or"><span>or</span></p>')


def _note_line() -> None:
    note = st.session_state.pop("auth_note", None)
    if note and note[1] in NOTES:
        st.html(f'<p class="si-note" role="status">{html.escape(NOTES[note[1]])}</p>')
        if note[1] in ("link", "link_unknown"):
            st.session_state.auth_link_expired = True
    problem = st.session_state.get("auth_problem")
    if problem:
        st.html(f'<p class="si-note si-problem" role="alert">{html.escape(problem)}</p>')


def _switch(label: str, to: str, key: str, busy: bool) -> None:
    st.button(label, key=key, type="tertiary", on_click=_view, args=(to,))


def login_page() -> None:
    """Sign in / Create an account / Forgot password / Resend confirmation,
    in the app's own quiet style."""
    if st.session_state.get("auth_note") == ("auth", "invite"):      # came back from Google, not invited
        st.session_state.pop("auth_note")
        _view("invite")
    view = st.session_state.get("auth_view", "signin")
    pending = st.session_state.get("auth_pending")
    busy = bool(pending)
    with st.container(key="signin"):
        st.html('<p class="si-title">GNOSIS</p><p class="si-lede">Learn a little every day.</p>')
        if view == "sent":
            st.html(f'<p class="si-note" role="status">{html.escape(NEUTRAL)}</p>')
            _switch("Back to sign in", "signin", "si_back", busy)
        elif view == "invite":
            st.html(f'<p class="si-note" role="status">{html.escape(INVITE_ONLY)}</p>')
            _switch("Back to sign in", "signin", "si_back", busy)
        elif view in ("signin", "signup"):
            _google_button(busy)
            _note_line()
            if view == "signin":
                with st.form("si_form", border=False, enter_to_submit=True):
                    st.text_input("Email", key="si_email", autocomplete="email")
                    st.text_input("Password", key="si_password", type="password",
                                  autocomplete="current-password")
                    st.form_submit_button("Signing in…" if busy else "Sign in", type="primary",
                                          on_click=_queue, args=("signin",), disabled=busy,
                                          use_container_width=True)
                with st.container(key="si_links", horizontal=True):
                    _switch("Forgot password?", "forgot", "si_to_forgot", busy)
                    _switch("Create an account", "signup", "si_to_signup", busy)
                if st.session_state.get("auth_unconfirmed") or st.session_state.get("auth_link_expired"):
                    _switch("Resend confirmation email", "resend", "si_to_resend", busy)
            else:
                with st.form("su_form", border=False, enter_to_submit=True):
                    st.text_input("Email", key="su_email", autocomplete="email")
                    st.text_input("Password", key="su_password", type="password",
                                  autocomplete="new-password")
                    st.html(f'<p class="si-rule">{PASSWORD_RULE}</p>')
                    st.text_input("Confirm password", key="su_confirm", type="password",
                                  autocomplete="new-password")
                    st.form_submit_button("Creating your account…" if busy else "Create account", type="primary",
                                          on_click=_queue, args=("signup",), disabled=busy,
                                          use_container_width=True)
                with st.container(key="si_links", horizontal=True):
                    st.html('<p class="si-hint">Already have an account?</p>')
                    _switch("Sign in", "signin", "si_to_signin", busy)
        else:   # forgot / resend
            forgot = view == "forgot"
            _note_line()
            st.html('<p class="si-hint">' + ("Enter your email and we'll send you a link to set a new password."
                                             if forgot else "Enter your email and we'll send the confirmation link again.")
                    + "</p>")
            with st.form("fp_form" if forgot else "rs_form", border=False, enter_to_submit=True):
                st.text_input("Email", key="fp_email" if forgot else "rs_email", autocomplete="email")
                label = ("Send reset link" if forgot else "Resend confirmation email")
                st.form_submit_button("Sending…" if busy else label, type="primary", on_click=_queue,
                                      args=("forgot" if forgot else "resend",), disabled=busy,
                                      use_container_width=True)
            _switch("Back to sign in", "signin", "si_back", busy)
    if pending:
        action, st.session_state.auth_sent = st.session_state.pop("auth_pending")
        _run(action)
        st.rerun()
    st.stop()


def reset_password_page(who: dict) -> None:
    """Arrived from a password-reset link: choose a new password first."""
    from coach import routes, supa_auth
    pending = st.session_state.get("auth_pending")
    busy = bool(pending) and pending[0] == "reset"
    with st.container(key="signin"):
        st.html('<p class="si-title">GNOSIS</p>'
                f'<p class="si-lede">Set a new password for {html.escape(who["email"])}.</p>')
        _note_line()
        with st.form("rp_form", border=False, enter_to_submit=True):
            st.text_input("New password", key="rp_password", type="password", autocomplete="new-password")
            st.html(f'<p class="si-rule">{PASSWORD_RULE}</p>')
            st.text_input("Confirm new password", key="rp_confirm", type="password",
                          autocomplete="new-password")
            st.form_submit_button("Saving…" if busy else "Save new password", type="primary", on_click=_queue,
                                  args=("reset",), disabled=busy, use_container_width=True)
    if busy:
        st.session_state.auth_sent = st.session_state.pop("auth_pending")[1]
        password, confirm = _form_values("rp_password", "rp_confirm")
        _forget_passwords()
        if not password_ok(password):
            st.session_state.auth_problem = PASSWORD_PROBLEM
        elif password != confirm:
            st.session_state.auth_problem = "The passwords don't match."
        else:
            try:
                supa_auth.set_password(access_token(), password)
            except supa_auth.AuthError as e:
                st.session_state.auth_problem = ERRORS.get(e.code, "Your password wasn't changed. Please try again.")
            else:
                st.session_state.pop("auth_problem", None)
                _go(routes.handoff(None, None, _browser(), note="auth=password_set", recovery=False))
        st.rerun()
    st.stop()


def invite_only_page() -> None:
    with st.container(key="signin"):
        st.html('<p class="si-title">GNOSIS</p>'
                f'<p class="si-lede">{html.escape(INVITE_ONLY)}</p>')
        _raw(f'<a class="si-plain" href="{html.escape(signout_url())}">Sign out</a>')
    st.stop()


def gate(store) -> None:
    """public: no one signed in → the sign-in page; signed in from a reset
    link → set a new password; signed in but not invited (or no longer) →
    the invitation message, and nothing is written; invited → their users
    row is made (first time) or touched (once a session), and the app goes
    on. personal: the password, as always."""
    if not is_public():
        ui.require_password()
        return
    _take_note()
    who = identity()
    if who is None:
        login_page()
    if who["exp"] and who["exp"] - time.time() < 120:
        _reload_for_fresh_session()
    if who["recovery"]:
        reset_password_page(who)
    note = st.session_state.pop("auth_note", None)
    if note == ("auth", "password_set"):
        st.toast("Your password has been updated.")
    elif note == ("auth", "confirmed"):
        st.toast("Your email is confirmed. Welcome.")
    from coach import storage
    try:
        allowed = is_admin() or store.is_invited(who["email"])
    except storage.StorageError as e:
        if e.status == 401:
            _reload_for_fresh_session()
        st.error(f"Couldn't check your invitation ({e}). Refresh the page in a moment to try again.")
        st.stop()
    if not allowed:
        invite_only_page()
    if st.session_state.get("auth_touched") != who["sub"]:
        try:
            store.touch_user(who["email"], who["name"], who["picture"])
        except storage.StorageError as e:
            st.error(f"Couldn't sign you in ({e}). Refresh the page in a moment to try again.")
            st.stop()
        st.session_state.auth_touched = who["sub"]


def account_menu() -> None:
    """At the right end of the bar (public only): who is signed in, Settings,
    and Sign out."""
    who = identity()
    if not who:
        return
    initial = (who["name"] or who["email"] or "?")[:1].upper()
    with st.popover(initial, key="account_menu"):
        pic = (f'<img class="acct-pic" src="{html.escape(who["picture"])}" alt="" referrerpolicy="no-referrer">'
               if who["picture"].startswith("https://") else "")
        st.html(f'<div class="acct-who">{pic}<div><p class="acct-name">{html.escape(who["name"])}</p>'
                f'<p class="acct-email">{html.escape(who["email"])}</p></div></div>')
        st.page_link("views/settings.py", label="Settings", icon=":material/settings:")
        _raw(f'<a class="acct-out" href="{html.escape(signout_url())}">Sign out</a>')
