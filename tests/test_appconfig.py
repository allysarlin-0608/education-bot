"""Reading settings: no secrets file is normal; a broken one is reported."""
import logging

import pytest
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from coach import appconfig


class Broken:
    def __init__(self, message):
        self.message = message

    def get(self, *a):
        raise StreamlitSecretNotFoundError(self.message)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(appconfig, "_reported", set())
    monkeypatch.setenv("SOME_SETTING", "from-env")


def test_no_secrets_file_quietly_uses_the_environment(monkeypatch, caplog):
    monkeypatch.setattr(st, "secrets", Broken("No secrets found. Valid paths for a secrets.toml file are: x"))
    with caplog.at_level(logging.ERROR, logger="coach.appconfig"):
        assert appconfig.get_setting("SOME_SETTING") == "from-env"
    assert not caplog.records


def test_a_broken_secrets_file_is_reported_once(monkeypatch, caplog):
    monkeypatch.setattr(st, "secrets", Broken("Error parsing secrets file at /app/.streamlit/secrets.toml: bad"))
    with caplog.at_level(logging.ERROR, logger="coach.appconfig"):
        assert appconfig.get_setting("SOME_SETTING") == "from-env"
        assert appconfig.get_setting("OTHER") == ""
    assert len(caplog.records) == 1 and "can't be read" in caplog.records[0].getMessage()
