"""Sign-in identity, admins, and the daily AI allowance (APP_MODE=public)."""
import types

import pytest
import streamlit

from coach import auth, llm, quota, storage, ui


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setenv("APP_MODE", "public")
    monkeypatch.setenv("ADMIN_EMAILS", "Boss@Example.com, other@example.com")


def signed_in(monkeypatch, **user):
    monkeypatch.setattr(streamlit, "user", {"is_logged_in": bool(user), **user})


def test_the_user_is_their_sub_never_their_email(public, monkeypatch):
    signed_in(monkeypatch, sub="1234567890", email="A@Example.com", name="Ann")
    assert auth.get_current_user_id() == "1234567890"
    assert auth.identity() == {"sub": "1234567890", "email": "a@example.com", "name": "Ann"}


def test_no_sub_means_not_signed_in(public, monkeypatch):
    signed_in(monkeypatch, email="a@example.com", name="Ann")
    assert auth.identity() is None and auth.get_current_user_id() is None
    signed_in(monkeypatch)
    assert auth.get_current_user_id() is None


def test_personal_mode_keeps_its_one_id(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.setenv("COACH_USER_ID", "")
    signed_in(monkeypatch, sub="someone", email="a@example.com")
    assert not auth.is_public() and auth.get_current_user_id() == "owner"
    assert not auth.is_admin()


def test_admins_by_email_any_case(public, monkeypatch):
    signed_in(monkeypatch, sub="1", email="boss@example.COM")
    assert auth.is_admin()
    signed_in(monkeypatch, sub="2", email="friend@example.com")
    assert not auth.is_admin()


class Usage:
    def __init__(self, requests_=0, tokens_=0):
        self.row = {"request_count": requests_, "token_count": tokens_}
        self.added = []

    def usage_today(self, day):
        return self.row

    def add_usage(self, day, r, t):
        self.added.append((r, t))


def with_store(monkeypatch, store):
    monkeypatch.setattr(quota, "_store", lambda: store)
    return store


def test_limits_default_and_from_secrets(monkeypatch):
    monkeypatch.delenv("AI_DAILY_REQUEST_LIMIT", raising=False)
    monkeypatch.delenv("AI_DAILY_TOKEN_LIMIT", raising=False)
    assert quota.limits() == (80, 150_000)
    monkeypatch.setenv("AI_DAILY_REQUEST_LIMIT", "5")
    monkeypatch.setenv("AI_DAILY_TOKEN_LIMIT", "900")
    assert quota.limits() == (5, 900)


def test_over_either_limit_stops_the_call(public, monkeypatch):
    signed_in(monkeypatch, sub="1", email="friend@example.com")
    with_store(monkeypatch, Usage(79, 10))
    assert not quota.over_limit()
    with_store(monkeypatch, Usage(80, 10))
    assert quota.over_limit()
    with_store(monkeypatch, Usage(1, 150_000))
    assert quota.over_limit()


def test_admins_have_no_limit_but_are_counted(public, monkeypatch):
    signed_in(monkeypatch, sub="1", email="boss@example.com")
    store = with_store(monkeypatch, Usage(10_000, 10**9))
    assert not quota.over_limit()
    quota.record(42)
    assert store.added == [(1, 42)]


def test_personal_mode_neither_counts_nor_limits(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    store = with_store(monkeypatch, Usage(10_000, 10**9))
    assert not quota.over_limit()
    quota.record(42)
    assert store.added == []


def test_over_the_limit_no_ai_call_is_made(public, monkeypatch):
    signed_in(monkeypatch, sub="1", email="friend@example.com")
    with_store(monkeypatch, Usage(80, 0))
    monkeypatch.setattr(llm, "get_client", lambda: pytest.fail("the model was called"))
    assert llm.ask_json("s", [{"role": "user", "content": "q"}]) == (None, quota.LIMIT_REACHED)
    with pytest.raises(llm.CoachError, match="reached today's limit"):
        next(llm.stream_text("s", [{"role": "user", "content": "q"}], 100))
    assert llm.LIMIT == quota.LIMIT_REACHED


def test_every_call_is_recorded_with_its_tokens(public, monkeypatch):
    signed_in(monkeypatch, sub="1", email="friend@example.com")
    store = with_store(monkeypatch, Usage())
    reply = types.SimpleNamespace(usage=types.SimpleNamespace(total_tokens=321), choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content='{"ok": 1}'), finish_reason="stop")])
    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **k: reply)))
    monkeypatch.setattr(llm, "get_client", lambda: client)
    assert llm.ask_json("s", [{"role": "user", "content": "q"}]) == ({"ok": 1}, None)
    assert store.added == [(1, 321)]


def test_a_storage_error_never_blocks_learning(public, monkeypatch):
    signed_in(monkeypatch, sub="1", email="friend@example.com")

    class Down:
        def usage_today(self, day):
            raise storage.StorageError("down")

        def add_usage(self, *a):
            raise storage.StorageError("down")

    with_store(monkeypatch, Down())
    assert not quota.over_limit()
    quota.record(5)                        # logged, not raised
