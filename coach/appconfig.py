"""Where the app's configuration is read: Streamlit secrets first, then the
environment. The one way any module reads a setting (a key, a URL, the
mode); none is ever logged or shown. Nothing here depends on the UI, so the
auth, data and AI modules can read their settings without it."""
import os

import streamlit as st


def get_setting(name: str) -> str:
    """A setting from Streamlit secrets, else the environment ("" if neither)."""
    try:
        value = st.secrets.get(name, "")
    except FileNotFoundError:          # no secrets file at all (a local run, the tests)
        value = ""
    return value or os.environ.get(name, "")
