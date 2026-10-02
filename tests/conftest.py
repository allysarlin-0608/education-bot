"""The end-to-end suite (tests/e2e) is slow and starts servers: it only runs
when asked for by path (`pytest tests/e2e`), not with the unit tests."""
import sys

import pytest


def pytest_ignore_collect(collection_path, config):
    if "e2e" in collection_path.parts and not any("e2e" in str(a) for a in config.args):
        return True
    return None


@pytest.fixture(autouse=True)
def _fresh_server_state():
    """Each test starts with an empty per-minute token window (llm.py),
    which is kept for the whole server."""
    def clear():
        llm = sys.modules.get("coach.llm")          # (e2e: the app has its own process)
        if llm:
            llm._window.clear()
    clear()
    yield
    clear()
