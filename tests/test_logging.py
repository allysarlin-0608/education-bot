"""Every log line says which session it came from, and only that: a short
tag of Streamlit's random session id, never who the person is."""
import logging
import types

import coach
from streamlit.runtime import scriptrunner


def line(logger_name="coach.test"):
    handler = logging.getLogger("coach").handlers[0]
    record = logging.LogRecord(logger_name, logging.ERROR, __file__, 1, "saving failed", None, None)
    assert all(f.filter(record) for f in handler.filters)
    return handler.format(record)


def test_a_line_names_its_session(monkeypatch):
    ctx = types.SimpleNamespace(session_id="3f2a9c1e-7b41-4d0e-9a55-0c1d2e3f4a5b")
    monkeypatch.setattr(scriptrunner, "get_script_run_ctx", lambda suppress_warning=False: ctx)
    out = line()
    assert "[3f2a9c1e]" in out and "7b41" not in out and "saving failed" in out


def test_outside_a_session_the_tag_is_a_dash():
    assert "[-]" in line() and coach.session_tag() == "-"
