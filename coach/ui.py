"""Streamlit helpers shared by the app's pages."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from coach import core

TIMEZONE = ZoneInfo(os.environ.get("COACH_TIMEZONE", "Asia/Taipei"))


def init_state():
    if "api_key" not in st.session_state:
        try:
            secret_key = st.secrets.get("GROQ_API_KEY", "")
        except Exception:  # no secrets.toml at all
            secret_key = ""
        st.session_state.api_key = secret_key or os.environ.get("GROQ_API_KEY", "")
    if "coach_log" not in st.session_state:
        st.session_state.coach_log = core.load_log()
    if "coach_messages" not in st.session_state:
        st.session_state.coach_messages = []
    if "coach_active" not in st.session_state:
        # (date iso, topic) of the lesson the chat belongs to.
        st.session_state.coach_active = None


def today():
    return datetime.now(TIMEZONE).date()


def persist(log):
    try:
        core.save_log(log)
    except OSError as e:
        st.warning(f"學習紀錄沒辦法存到檔案（{e}），記得到「學習紀錄」下載備份。")


def reset_chat():
    """Forget the on-screen chat so the lesson page reloads from the log."""
    st.session_state.coach_messages = []
    st.session_state.coach_active = None
