"""Streamlit helpers shared by the app's pages."""
import hmac
import os
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import streamlit as st

from coach import settings, storage

TIMEZONE = ZoneInfo(os.environ.get("COACH_TIMEZONE", "Asia/Taipei"))


def get_setting(name: str) -> str:
    """Read a setting from Streamlit secrets, falling back to env vars."""
    try:
        value = st.secrets.get(name, "")
    except Exception:  # no secrets.toml at all
        value = ""
    return value or os.environ.get(name, "")


PASSWORD_MISSING = (
    "This app has no password set yet, so it stays closed to protect the records. "
    "In Streamlit, go to Settings → Secrets, add the line APP_PASSWORD = \"your password\", save and refresh."
)


def require_password():
    """Basic gate for a public URL: nothing is loaded until the password
    from secrets (APP_PASSWORD) is entered in this session."""
    if st.session_state.get("coach_authed"):
        return
    # the page she asked for (a refresh, a link): she is taken back to it once in
    try:
        st.session_state.setdefault("coach_asked_path", urlparse(st.context.url).path.strip("/").split("/")[-1])
    except Exception:
        pass
    expected = get_setting("APP_PASSWORD")
    st.markdown("### Daily Learning Coach")
    if not expected:
        st.error(PASSWORD_MISSING)
        st.stop()
    with st.form("login"):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter", type="primary")
    if submitted:
        if hmac.compare_digest(entered.encode(), expected.encode()):
            st.session_state.coach_authed = True
            st.rerun()
        st.error("Wrong password. Try again.")
    st.stop()


# Bump whenever the store or the log's shape changes. Sessions opened
# before an update keep the old objects in st.session_state (e.g. a store
# without save_book, a log without "books"), so on a mismatch those are
# dropped and reloaded from storage, which is always up to date.
STATE_VERSION = 4


def init_state():
    if st.session_state.get("coach_state_version") != STATE_VERSION:
        for key in ("coach_store", "coach_log", "coach_chats", "coach_settings"):
            st.session_state.pop(key, None)
        st.session_state.coach_state_version = STATE_VERSION
    if "api_key" not in st.session_state:
        st.session_state.api_key = get_setting("GROQ_API_KEY")
    if "coach_store" not in st.session_state:
        st.session_state.coach_store = storage.make_store(
            get_setting("SUPABASE_URL"), get_setting("SUPABASE_KEY")
        )
    if "coach_log" not in st.session_state:
        try:
            st.session_state.coach_log = st.session_state.coach_store.load()
        except storage.StorageError as e:
            # Don't cache the failure: the next rerun tries to load again.
            st.error(f"Couldn't load your records ({e}). Refresh the page in a moment to try again.")
            st.stop()
    if "coach_settings" not in st.session_state:
        load_settings()
    if "coach_chats" not in st.session_state:
        # "date|topic" -> that lesson's chat, so switching pages or topics
        # never loses it (restored from the saved entry when missing).
        st.session_state.coach_chats = {}


def user_id() -> str:
    """Whose settings these are. One user for now (a fixed id, which can be
    set with COACH_USER_ID); every read and write of settings goes by it."""
    return get_setting("COACH_USER_ID") or settings.DEFAULT_USER_ID


def load_settings():
    """This user's settings. Where the settings table doesn't exist yet the
    app keeps its old fixed setup, unchanged (settings.legacy)."""
    store, uid = st.session_state.coach_store, user_id()
    try:
        row = store.load_settings(uid)
    except storage.StorageError as e:
        st.error(f"Couldn't load your settings ({e}). Refresh the page in a moment to try again.")
        st.stop()
    st.session_state.coach_settings = (settings.legacy(uid) if store.settings_missing
                                       else settings.normalize(row, uid))


def config() -> dict:
    return st.session_state.coach_settings


def save_settings(new: dict) -> bool:
    """Save her settings (the whole row, found by her user_id) and use
    them from now on. On failure nothing changes and the error is shown
    after the rerun."""
    if settings.is_legacy(new):
        return False
    try:
        st.session_state.coach_store.save_settings(user_id(), new)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"Your settings weren't saved ({e}). Try again in a moment."
        return False
    st.session_state.coach_settings = new
    return True


def topic_for(day):
    """The subject for a day, from her settings."""
    return settings.topic_for(config(), day, TIMEZONE)


WORLD_PAGE = "views/world.py"


def enter_world(topic: str):
    """Into a subject's world. The one subject it shows is kept in her
    session and named in the page's address (?subject=), so a refresh, the
    browser's Back or a link opens that same subject, never another."""
    st.session_state.world_topic = topic
    st.switch_page(WORLD_PAGE, query_params={"subject": topic})


def today():
    return datetime.now(TIMEZONE).date()


def using_cloud() -> bool:
    return st.session_state.coach_store.name == "supabase"


def save_entry(log, entry):
    """Save one entry. Returns True on success; on failure the error is
    kept for show_pending_error() so it survives the st.rerun() that
    usually follows a save."""
    try:
        st.session_state.coach_store.save_entry(log, entry)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"This wasn't saved ({e}). Try again in a moment."
        return False
    return True


def save_book(log, book):
    """Save one book's state; same error handling as save_entry."""
    try:
        st.session_state.coach_store.save_book(log, book)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"Your reading progress wasn't saved ({e}). Try again in a moment."
        return False
    return True


def show_pending_error():
    error = st.session_state.pop("coach_save_error", None)
    if error:
        st.error(error)


def replace_log(log):
    """Replace the whole stored log (backup import). Returns True on success."""
    try:
        st.session_state.coach_store.replace(log)
    except storage.StorageError as e:
        st.error(f"The import wasn't saved ({e}). Try again in a moment.")
        return False
    return True


def reset_chat():
    """Forget the on-screen chats so the lesson page reloads them from the log."""
    st.session_state.coach_chats = {}
