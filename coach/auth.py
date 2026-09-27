"""Who is using the app, and whether they may.

APP_MODE (secrets or environment):
- "personal" (the default): one person's app, exactly as it has always been:
  the APP_PASSWORD gate, and one fixed user id (COACH_USER_ID, else "owner").
- "public": sign-in with Google through Streamlit's own st.login() (OIDC; the
  [auth] block in secrets.toml). No password of any kind is handled here.
  A person is their OIDC "sub", never their email (an email can change).
  While in beta only invited emails get in (the allowed_users table, and the
  admins in ADMIN_EMAILS).

get_current_user_id() is the one answer to "whose data is this?"; storage.py
asks it on every call."""
import html

import streamlit as st

from coach import ui

PERSONAL, PUBLIC = "personal", "public"

SIGNIN_FAILED = "Sign-in didn't complete. Please try again."
INVITE_ONLY = "This app is invite-only for now. Ask the person who shared it with you to add your email."
AUTH_MISSING = ("Sign-in isn't set up yet: add an [auth] block to the app's secrets "
                "(see docs/google-sign-in.md), save and reboot the app.")
# set in the browser the moment "Continue with Google" is pressed; if the page
# comes back without a signed-in user, sign-in didn't complete
ATTEMPT_COOKIE = "dlc_signin"


def mode() -> str:
    return PUBLIC if ui.get_setting("APP_MODE").strip().lower() == PUBLIC else PERSONAL


def is_public() -> bool:
    return mode() == PUBLIC


def identity():
    """The signed-in person from Streamlit's st.user, or None. Without a
    "sub" (the OIDC subject, the stable id) there is no one signed in."""
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
    return {"sub": str(sub), "email": email, "name": str(user.get("name") or email.split("@")[0])}


def get_current_user_id():
    """Whose data this session reads and writes. personal: the one fixed id;
    public: the signed-in person's sub, or None when no one is signed in."""
    if not is_public():
        return ui.personal_user_id()
    who = identity()
    return who["sub"] if who else None


def admin_emails() -> set:
    return {e.strip().lower() for e in ui.get_setting("ADMIN_EMAILS").replace(";", ",").split(",") if e.strip()}


def is_admin() -> bool:
    who = identity()
    return bool(is_public() and who and who["email"] in admin_emails())


def _clear_attempt() -> None:
    st.html(f"<script>document.cookie = '{ATTEMPT_COOKIE}=; path=/; max-age=0';</script>",
            unsafe_allow_javascript=True)


def login_page() -> None:
    """Title, one line, one button; st.login() does the rest (Google)."""
    attempted = bool(st.context.cookies.get(ATTEMPT_COOKIE))
    with st.container(key="signin"):
        st.html('<p class="si-title">GNOSIS</p><p class="si-lede">Learn a little every day.</p>')
        if attempted:
            st.html(f'<p class="si-note" role="alert">{html.escape(SIGNIN_FAILED)}</p>')
            _clear_attempt()
        if st.button("Continue with Google", type="primary", key="signin_google"):
            try:
                st.login()
            except Exception:  # noqa: BLE001 - no [auth] in secrets
                st.error(AUTH_MISSING)
    # the attempt is noted as the button is pressed (before the page leaves for Google)
    st.html("<script>(function(){const d=window.parent.document;d.addEventListener('click',function(e){"
            "if(e.target.closest&&e.target.closest('.st-key-signin_google button')){"
            f"d.cookie='{ATTEMPT_COOKIE}=1; path=/; max-age=600';}}}},true);}})();</script>",
            unsafe_allow_javascript=True)
    st.stop()


def invite_only_page() -> None:
    with st.container(key="signin"):
        st.html('<p class="si-title">GNOSIS</p>'
                f'<p class="si-lede">{html.escape(INVITE_ONLY)}</p>')
        if st.button("Sign out", key="signin_out"):
            st.logout()
    st.stop()


def gate(store) -> None:
    """public: no one signed in → the sign-in page; signed in but not invited
    (or no longer) → the invitation message, and nothing is written; invited
    → their users row is made (first time) or touched (once a session), and
    the app goes on. personal: the password, as always."""
    if not is_public():
        ui.require_password()
        return
    who = identity()
    if who is None:
        login_page()
    if st.context.cookies.get(ATTEMPT_COOKIE):
        _clear_attempt()
    from coach import storage
    try:
        allowed = who["email"] in admin_emails() or store.is_invited(who["email"])
    except storage.StorageError as e:
        st.error(f"Couldn't check your invitation ({e}). Refresh the page in a moment to try again.")
        st.stop()
    if not allowed:
        invite_only_page()
    if st.session_state.get("auth_touched") != who["sub"]:
        try:
            store.touch_user(who["email"], who["name"])
        except storage.StorageError as e:
            st.error(f"Couldn't sign you in ({e}). Refresh the page in a moment to try again.")
            st.stop()
        st.session_state.auth_touched = who["sub"]


def account_menu() -> None:
    """At the right end of the bar (public only): their name and email;
    Settings, and Sign out."""
    who = identity()
    if not who:
        return
    initial = (who["name"] or who["email"] or "?")[:1].upper()
    with st.popover(initial, key="account_menu"):
        st.html(f'<p class="acct-name">{html.escape(who["name"])}</p>'
                f'<p class="acct-email">{html.escape(who["email"])}</p>')
        st.page_link("views/settings.py", label="Settings", icon=":material/settings:")
        if st.button("Sign out", key="acct_signout", icon=":material/logout:", type="tertiary"):
            st.logout()
