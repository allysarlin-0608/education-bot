"""The password gate (P1-4): no data is loaded until APP_PASSWORD is entered."""
from pathlib import Path

import requests
from streamlit.testing.v1 import AppTest

from test_storage import FakePostgrest

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")


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
