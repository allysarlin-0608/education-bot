"""The current app on our backend (step M2): the app's own `ApiStore`
(coach/storage.py), talking HTTP to this API, does everything the app's
other stores do, with the same results, so switching the site over changes
nothing for anyone. Each operation is done on the local file store and on
the API store, and the results compared."""
import copy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from coach import core, prefs, settings, storage
from gnosis.data import schema as t
from test_learning_repository import rich_log

TOKEN = "store-contract-token-0123456789"


class Bridge:
    """requests.Session's request(), served by the test client (no network)."""

    def __init__(self, client):
        self.client = client

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        return self.client.request(method, url.replace("http://api.test", ""), json=json, params=params,
                                   headers=headers)


@pytest.fixture
def stores(database_url, monkeypatch, engine, tmp_path):
    monkeypatch.setenv("GNOSIS_SERVICE_TOKENS", TOKEN)
    from gnosis.data import db
    from gnosis.infra.config import settings as cfg
    cfg.cache_clear()
    db.engine.cache_clear()
    from gnosis.app import create_app
    client = TestClient(create_app(), raise_server_exceptions=False)
    api = storage.ApiStore("http://api.test", TOKEN, session=Bridge(client), current_user=lambda: "supa-1",
                           current_email=lambda: "learner@example.com")
    files = storage.FileStore(tmp_path / "log.json", tmp_path / "settings.json", scoped=True,
                              current_user=lambda: "supa-1")
    yield api, files
    with engine.begin() as c:
        for table in (t.users, t.invites, t.audit_log):
            c.execute(table.delete())
    cfg.cache_clear()
    db.engine.cache_clear()


def both(stores, op, *args):
    api, files = stores
    return getattr(api, op)(*copy.deepcopy(args)), getattr(files, op)(*copy.deepcopy(args))


def test_the_record_day_by_day_as_the_app_saves_it(stores):
    api, files = stores
    log = core.parse_log(rich_log())
    for e in log["entries"]:
        both(stores, "save_entry", log, e)
    for b in log["books"]:
        both(stores, "save_book", log, b)
    for p in log["paths"]:
        both(stores, "save_path", log, p)
    a, f = both(stores, "load")
    assert a == f == log
    e = log["entries"][-2]
    assert api.load_entry(e["date"], e["topic"]) == files.load_entry(e["date"], e["topic"]) == e
    assert api.load_entry("2001-01-01", "philosophy") is None
    assert api.load_books() == log["books"]


def test_a_backup_restored_replaces_everything(stores):
    api, files = stores
    log = core.parse_log(rich_log())
    both(stores, "replace", log)
    smaller = dict(log, entries=log["entries"][:2])
    both(stores, "replace", smaller)
    assert api.load() == files.load() == core.parse_log(smaller)


def test_settings_preferences_usage_and_counts(stores):
    api, files = stores
    assert api.load_settings() is None
    row = dict(settings.blank("supa-1"), subjects=["philosophy", "cosmos"], units_per_day=3,
               subject_levels={"philosophy": "Beginner", "cosmos": "Advanced"}, reading_enabled=True,
               onboarded_at="2026-10-01T00:00:00+00:00")
    both(stores, "save_settings", row)
    a, f = both(stores, "load_settings")
    assert settings.normalize(a, "supa-1")["subjects"] == settings.normalize(f, "supa-1")["subjects"] == ["philosophy", "cosmos"]
    p = dict(prefs.blank(), reminder_on=True, light_day="2026-11-02")
    both(stores, "save_prefs", p)
    a, f = both(stores, "load_prefs")
    assert prefs.normalize(a) == prefs.normalize(f) == prefs.normalize(p)
    for _ in range(2):
        both(stores, "add_usage", "2026-11-02", 1, 700)
    a, f = both(stores, "usage_today", "2026-11-02")
    count = lambda r: {k: r[k] for k in ("request_count", "token_count")}     # noqa: E731  (what the quota reads)
    assert count(a) == count(f) == {"request_count": 2, "token_count": 1400}
    api.add_event("2026-11-02", "lesson_passed")             # (counted on the server's date)


def test_sign_in_invitations_and_admins(stores, engine):
    api, files = stores
    assert api.is_admin("learner@example.com") is False, "unknown yet: not an admin, and not made by asking"
    with engine.connect() as c:
        assert c.execute(t.users.select()).first() is None
    assert api.is_invited("someone@example.com") is False
    api.touch_user("learner@example.com", "Learner", "https://example.com/me.png")
    assert api.user_row()["display_name"] == "Learner"
    uid = api.user_row()["user_id"]
    with engine.begin() as c:
        c.execute(t.user_roles.insert().values(user_id=uid, role="admin"))
    assert api.is_admin("learner@example.com") is True
    api.add_invite("Friend@Example.com", "hi")
    assert api.list_invites() == [{"email": "friend@example.com", "note": "hi"}] and api.is_invited("friend@example.com")
    api.remove_invite("friend@example.com")
    assert api.list_invites() == []
    m = api.metrics(date(2026, 1, 1), date(2026, 11, 2))
    assert m["signed_up"] == 1


def test_her_copy_and_deleting_her_account(stores):
    api, files = stores
    api.replace(core.parse_log(rich_log()))
    copy_ = api.export_my_data()
    assert len(copy_["learning_entries"]) == len(core.parse_log(rich_log())["entries"])
    api.delete_my_account()
    assert api.load()["entries"] == []


def test_a_wrong_service_token_is_a_setup_error_not_a_session_to_refresh(stores):
    api, _ = stores
    api.token = "wrong"
    with pytest.raises(storage.StorageError) as e:
        api.load()
    assert e.value.status is None and "settings" in str(e.value)
