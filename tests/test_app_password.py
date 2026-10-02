"""The password gate (P1-4): no data is loaded until APP_PASSWORD is entered."""
from pathlib import Path

import requests
from streamlit.testing.v1 import AppTest

from test_storage import FakePostgrest

APP = str(Path(__file__).resolve().parent.parent / "gnosis.py")


def start(monkeypatch, password, **db_options):
    db = FakePostgrest(**db_options)
    monkeypatch.setattr(requests, "Session", lambda: db)
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "sb_secret_test")
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    if password is None:
        monkeypatch.delenv("APP_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("APP_PASSWORD", password)
    return AppTest.from_file(APP, default_timeout=30).run(), db


def test_without_a_password_configured_nothing_opens(monkeypatch):
    at, db = start(monkeypatch, None)
    assert "APP_PASSWORD" in at.error[0].value
    assert db.calls == [] and not at.selectbox


def test_wrong_password_is_refused_and_loads_nothing(monkeypatch):
    # covers: S-app_password, W-ui-login, W-ui-password, W-ui-enter
    at, db = start(monkeypatch, "correct horse")
    at.text_input[0].input("guess").run()
    at.button[0].click().run()
    assert at.error[0].value == "Wrong password. Try again."
    assert db.calls == [] and not at.selectbox


def test_right_password_opens_the_app(monkeypatch):
    at, db = start(monkeypatch, "correct horse")
    at.text_input[0].input("correct horse").run()
    at.button[0].click().run()
    assert not at.exception
    assert not at.selectbox                                      # no topic picker: the day decides
    assert any(m.value.startswith("### ") for m in at.markdown)  # today's topic heading
    assert any(method == "GET" for method, *_ in db.calls)


def test_with_the_settings_table_a_new_user_sets_up_first(monkeypatch):
    at, db = start(monkeypatch, "correct horse", settings_table=True)
    at.text_input[0].input("correct horse").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("Learn a little every day" in m.value for m in at.markdown)
    assert db.settings == {}                      # nothing saved just by looking


def test_the_server_key_never_reaches_the_page(monkeypatch):
    # covers: S-groq_api_key
    """BUG-003: with the groq package unavailable the key box appears, but
    it must never be filled with the key from the app's secrets."""
    from coach import llm
    monkeypatch.setattr(llm, "GROQ_AVAILABLE", False)
    at, db = start(monkeypatch, "correct horse")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_SERVER_SECRET")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("correct horse").run()
    at.button[0].click().run()
    assert not at.exception
    values = [t.value for t in at.text_input]
    assert all("gsk_SERVER_SECRET" not in (v or "") for v in values), values


def test_a_personal_app_without_a_key_takes_one_and_never_shows_it(monkeypatch):
    # covers: W-daily-set_the_api_key, W-daily-groq_key_entry
    at, db = start(monkeypatch, "correct horse")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("correct horse").run()
    at.button[0].click().run()
    assert not at.exception
    assert any(e.label == "Set the API key" for e in at.expander)
    box = next(t for t in at.text_input if t.label == "Groq API key")
    box.input("gsk_typed_by_me").run()
    assert at.session_state.api_key == "gsk_typed_by_me"
    assert not any(t.label == "Groq API key" for t in at.text_input), "the box goes once a key is set"


def test_five_wrong_tries_close_the_gate_for_15_minutes_then_it_opens(monkeypatch):
    """BUG-011: after five wrong passwords in a row (any session) nothing is
    checked for 15 minutes, not even the right one; then it opens by itself."""
    from coach import ui
    now = {"t": 1_000_000.0}
    monkeypatch.setattr(ui, "_clock", lambda: now["t"])
    monkeypatch.setitem(ui._gate, "failures", 0)
    monkeypatch.setitem(ui._gate, "until", 0.0)
    for k in range(5):
        at, db = start(monkeypatch, "correct horse")            # a new session each time
        at.text_input[0].input(f"guess {k}").run()
        at.button[0].click().run()
    assert at.error[0].value == "Too many wrong tries. Try again in 15 minutes."
    at, db = start(monkeypatch, "correct horse")
    assert at.error[0].value.startswith("Too many wrong tries")     # shown to a new session too
    at.text_input[0].input("correct horse").run()
    at.button[0].click().run()
    assert at.error[0].value.startswith("Too many wrong tries") and db.calls == []
    now["t"] += 14 * 60 + 1
    at, db = start(monkeypatch, "correct horse")
    assert at.error[0].value == "Too many wrong tries. Try again in 1 minute."
    now["t"] += 60
    at, db = start(monkeypatch, "correct horse")
    assert not at.error
    at.text_input[0].input("correct horse").run()
    at.button[0].click().run()
    assert not at.exception and not at.error and any(method == "GET" for method, *_ in db.calls)


def test_a_right_password_resets_the_count(monkeypatch):
    from coach import ui
    monkeypatch.setitem(ui._gate, "failures", 0)
    monkeypatch.setitem(ui._gate, "until", 0.0)
    for entered in ("a", "b", "c", "d", "correct horse", "e", "f"):
        at, _ = start(monkeypatch, "correct horse")
        at.text_input[0].input(entered).run()
        at.button[0].click().run()
    assert ui._gate["failures"] == 2 and ui._gate["until"] == 0.0
