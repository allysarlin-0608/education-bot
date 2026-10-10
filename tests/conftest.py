"""The end-to-end suite (tests/e2e) is slow and starts servers: it only runs
when asked for by path (`pytest tests/e2e`), not with the unit tests."""
import os
import sys

import pytest

os.environ.setdefault("GNOSIS_RAISE_ERRORS", "1")      # a page's error reaches the test, not the calm page (ui.calm_failure)
os.environ.setdefault("STREAMLIT_CLIENT_SHOW_ERROR_DETAILS", "full")    # (visitors see none: .streamlit/config.toml)


def pytest_ignore_collect(collection_path, config):
    if "e2e" in collection_path.parts and not any("e2e" in str(a) for a in config.args):
        return True
    return None


@pytest.fixture(autouse=True)
def _full_error_details():
    """The tests read a page's real error (visitors see none: .streamlit/config.toml)."""
    from streamlit import config
    config.set_option("client.showErrorDetails", "full")
    yield


@pytest.fixture(autouse=True)
def _fresh_server_state():
    """Each test starts with an empty per-minute token window (llm.py) and
    no wrong-password count (ui.py): both are kept for the whole server."""
    def clear():
        llm, ui = sys.modules.get("coach.llm"), sys.modules.get("coach.ui")   # (e2e: the app has its own process)
        if llm:
            llm._window.clear()
        if ui:
            ui._gate.update(failures=0, until=0.0)
    clear()
    yield
    clear()
