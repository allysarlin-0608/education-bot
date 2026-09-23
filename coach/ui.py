"""Streamlit helpers shared by the app's pages."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from coach import storage

TIMEZONE = ZoneInfo(os.environ.get("COACH_TIMEZONE", "Asia/Taipei"))


def get_setting(name: str) -> str:
    """Read a setting from Streamlit secrets, falling back to env vars."""
    try:
        value = st.secrets.get(name, "")
    except Exception:  # no secrets.toml at all
        value = ""
    return value or os.environ.get(name, "")


# Bump whenever the store or the log's shape changes. Sessions opened
# before an update keep the old objects in st.session_state (e.g. a store
# without save_book, a log without "books"), so on a mismatch those are
# dropped and reloaded from storage, which is always up to date.
STATE_VERSION = 2


def init_state():
    if st.session_state.get("coach_state_version") != STATE_VERSION:
        for key in ("coach_store", "coach_log"):
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
            st.error(f"讀不到學習紀錄（{e}），等一下重新整理頁面再試一次。")
            st.stop()
    if "coach_messages" not in st.session_state:
        st.session_state.coach_messages = []
    if "coach_active" not in st.session_state:
        # (date iso, topic) of the lesson the chat belongs to.
        st.session_state.coach_active = None


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
        st.session_state.coach_save_error = f"這筆紀錄沒有存成功（{e}），等一下再試一次。"
        return False
    return True


def save_book(log, book):
    """Save one book's state; same error handling as save_entry."""
    try:
        st.session_state.coach_store.save_book(log, book)
    except storage.StorageError as e:
        st.session_state.coach_save_error = f"讀書進度沒有存成功（{e}），等一下再試一次。"
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
        st.error(f"匯入沒有存成功（{e}），等一下再試一次。")
        return False
    return True


def reset_chat():
    """Forget the on-screen chat so the lesson page reloads from the log."""
    st.session_state.coach_messages = []
    st.session_state.coach_active = None
