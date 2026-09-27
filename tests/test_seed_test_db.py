"""tools/seed_test_db.py refuses anything but the TEST project and never
overwrites; a dry run writes nothing."""
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import seed_test_db  # noqa: E402

URL, REF, UID = "https://abcd1234.supabase.co", "abcd1234", "11111111-2222-3333-4444-555555555555"


class Resp:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, tables):
        self.tables, self.posts, self.headers = tables, [], {}

    def get(self, url, params=None, timeout=None):
        table = url.rsplit("/", 1)[-1]
        if table not in self.tables:
            return Resp(404)
        rows = self.tables[table]
        if "user_id" in (params or {}):
            rows = [r for r in rows if "eq." + r.get("user_id", "") == params["user_id"]]
        return Resp(200, rows)

    def post(self, url, json=None, timeout=None, headers=None):
        self.posts.append((url, json, headers))
        return Resp(201)


def run(monkeypatch, tables, *extra, key="service-key"):
    fake = FakeSession(tables)
    monkeypatch.setattr(seed_test_db.requests, "Session", lambda: fake)
    if key:
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
    else:
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    seed_test_db.main(["--url", URL, "--ref", REF, "--user-id", UID, *extra])
    return fake


TEST_DB = {"app_admins": [{"email": "a@example.com"}], "users": [{"user_id": UID}], "learning_entries": []}


def test_a_mistyped_project_is_refused(monkeypatch):
    with pytest.raises(SystemExit, match="Refused"):
        seed_test_db.main(["--url", URL, "--ref", "other", "--user-id", UID])


def test_no_key_is_refused(monkeypatch):
    with pytest.raises(SystemExit, match="SUPABASE_SERVICE_KEY"):
        run(monkeypatch, TEST_DB, key="")


def test_a_database_without_the_accounts_setup_is_refused(monkeypatch):
    personal_like = {"users": [{"user_id": UID}], "learning_entries": []}
    with pytest.raises(SystemExit, match="isn't the TEST project"):
        run(monkeypatch, personal_like, "--apply")


def test_someone_with_entries_is_never_overwritten(monkeypatch):
    busy = dict(TEST_DB, learning_entries=[{"user_id": UID, "date": "2026-01-01"}])
    with pytest.raises(SystemExit, match="already has learning entries"):
        run(monkeypatch, busy, "--apply")


def test_an_unknown_person_is_refused(monkeypatch):
    with pytest.raises(SystemExit, match="no signed-up person"):
        run(monkeypatch, dict(TEST_DB, users=[]), "--apply")


def test_a_dry_run_writes_nothing(monkeypatch, capsys):
    fake = run(monkeypatch, TEST_DB)
    assert fake.posts == []
    assert "Dry run" in capsys.readouterr().out


def test_apply_adds_new_rows_only(monkeypatch):
    fake = run(monkeypatch, TEST_DB, "--apply", "--days", "31")
    (url, rows, headers), = fake.posts
    assert url.endswith("/learning_entries") and headers["Prefer"].startswith("resolution=ignore-duplicates")
    assert len(rows) >= 28 and all(r["user_id"] == UID for r in rows)
    assert "service-key" not in str(rows)
