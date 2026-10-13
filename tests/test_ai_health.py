"""How often the AI made people wait (supabase/ai_health.sql): a busy,
failed or slow call is counted for the person, on the day, counts only;
admins see the totals and how many people met each (never who); her
counts go with her account; counting never gets in her way."""
import types
from datetime import date

import pytest

from coach import llm, metrics, quota, storage
from fake_supabase import FakeDB
from test_accounts import public, signed_in, with_store  # noqa: F401
from test_isolation import Who, supabase

SINCE = date(2026, 1, 1)


def test_what_counts_as_a_wait():
    assert metrics.wait_kind("busy", 1) == "busy" and metrics.wait_kind("failed", 0) == "failed"
    assert metrics.wait_kind("ok", metrics.SLOW_S + 0.1) == "slow"
    assert metrics.wait_kind("ok", metrics.SLOW_S) is None and metrics.wait_kind("ok", 2) is None


def test_the_summary_adds_up_and_never_says_who():
    waits = [{"user_id": "user-a", "day": "2026-02-01", "kind": "busy", "count": 3},
             {"user_id": "user-b", "day": "2026-02-01", "kind": "busy", "count": 1},
             {"user_id": "user-b", "day": "2026-02-02", "kind": "slow", "count": 2},
             {"user_id": "user-a", "day": "2025-12-31", "kind": "failed", "count": 9}]        # before `since`
    usage = [{"user_id": "user-a", "date": "2026-02-01", "request_count": 40},
             {"user_id": "user-b", "date": "2025-12-30", "request_count": 99}]
    h = metrics.ai_health(waits, usage, SINCE)
    assert h["answered"] == 40 and h["by_kind"] == {"busy": 4, "slow": 2} and h["people"] == {"busy": 2, "slow": 1}
    assert h["days"] == [{"day": "2026-02-01", "busy": 4, "failed": None, "slow": None},
                         {"day": "2026-02-02", "busy": None, "failed": None, "slow": 2}]
    assert "user-" not in str(h)


def test_in_the_database_hers_only_admins_read_and_it_goes_with_her_account():
    db, who = FakeDB(), Who()
    store = supabase(db, who)
    db.tables[storage.ADMINS_TABLE][("boss@example.com",)] = {"email": "boss@example.com"}
    who.be("u1")
    store.add_ai_wait("busy")
    store.add_ai_wait("busy")
    store.add_ai_wait("slow")
    with pytest.raises(storage.StorageError):
        store.add_ai_wait("bored")                     # only the three kinds
    with pytest.raises(storage.StorageError):
        store.ai_health(SINCE)                         # not an admin
    who.be("u2")
    store.add_ai_wait("failed")
    who.be("u9", "boss@example.com")
    h = store.ai_health(SINCE)
    assert h["by_kind"] == {"busy": 2, "slow": 1, "failed": 1} and h["people"] == {"busy": 1, "slow": 1, "failed": 1}
    who.be("u1")
    store.delete_my_account()
    who.be("u9", "boss@example.com")
    assert store.ai_health(SINCE)["by_kind"] == {"failed": 1}, "hers went with her account"


def test_the_local_store_the_same(tmp_path):
    who = Who()
    store = storage.FileStore(tmp_path / "log.json", tmp_path / "settings.json", scoped=True, current_user=who)
    who.be("u1")
    for _ in range(metrics.WAITS_PER_DAY + 3):
        store.add_ai_wait("busy")
    assert store.ai_health(SINCE)["by_kind"] == {"busy": metrics.WAITS_PER_DAY}, "at most 500 a day"
    assert store.export_my_data()["ai_waits"][0]["count"] == metrics.WAITS_PER_DAY
    store.delete_my_account()
    assert store.ai_health(SINCE)["by_kind"] == {}


class Counting:
    def __init__(self, fails=False):
        self.waits, self.fails = [], fails

    def usage_today(self, day):
        return {"request_count": 0, "token_count": 0}

    def add_usage(self, *a):
        pass

    def add_ai_wait(self, kind):
        if self.fails:
            raise storage.StorageError("relation ai_waits does not exist")
        self.waits.append(kind)


def client(create):
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def test_a_busy_or_slow_call_is_counted_and_counting_never_gets_in_her_way(public, monkeypatch):  # noqa: F811
    signed_in(monkeypatch, sub="1", email="friend@example.com")
    store = with_store(monkeypatch, Counting())
    reply = types.SimpleNamespace(usage=types.SimpleNamespace(total_tokens=5), choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content='{"ok": 1}'), finish_reason="stop")])
    monkeypatch.setattr(llm, "get_client", lambda: client(lambda **k: reply))
    assert llm.ask_json("s", [{"role": "user", "content": "q"}]) == ({"ok": 1}, None)
    assert store.waits == [], "a quick answer isn't counted"
    ticks = iter(range(0, 10_000, metrics.SLOW_S + 5))          # a slow AI: every look at the clock, 20 s on
    monkeypatch.setattr(llm, "_now", lambda: float(next(ticks)))
    llm.ask_json("s", [{"role": "user", "content": "q"}])
    assert store.waits == ["slow"]

    def refuse(**k):
        raise RuntimeError("bad request")
    monkeypatch.setattr(llm, "_now", lambda: 0.0)
    monkeypatch.setattr(llm, "get_client", lambda: client(refuse))
    assert llm.ask_json("s", [{"role": "user", "content": "q"}])[1] == llm.FAILED
    assert store.waits == ["slow", "failed"]
    with_store(monkeypatch, Counting(fails=True))     # the table isn't there yet: she sees only the AI's answer
    assert llm.ask_json("s", [{"role": "user", "content": "q"}])[1] == llm.FAILED


def test_personal_mode_counts_nothing(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    store = with_store(monkeypatch, Counting())
    quota.note_wait("busy")
    assert store.waits == []
