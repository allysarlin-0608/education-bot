"""Where the app's configuration is read: Streamlit secrets first, then the
environment. The one way any module reads a setting (a key, a URL, the
mode); none is ever logged or shown. Nothing here depends on the UI, so the
auth, data and AI modules can read their settings without it.

No secrets file is normal (a local run, the tests): the environment is
used. A secrets file that can't be read (a typo in Streamlit Cloud's
Secrets) is not: it is logged as an error, once, and the environment is
used, so the app fails closed (no password: the gate stays shut) and the
log says why."""
import logging
import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

logger = logging.getLogger("coach.appconfig")
NO_FILE = "No secrets found"           # how Streamlit words "there is no secrets file"
_reported = set()


def get_setting(name: str) -> str:
    """A setting from Streamlit secrets, else the environment ("" if neither)."""
    try:
        value = st.secrets.get(name, "")
    except StreamlitSecretNotFoundError as e:
        if not str(e).startswith(NO_FILE) and str(e) not in _reported:
            _reported.add(str(e))
            logger.error("the secrets file can't be read; using the environment instead: %s", e)
        value = ""
    return value or os.environ.get(name, "")
