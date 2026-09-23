from datetime import date, datetime

import pytest
import requests

from coach import books, core, storage

URL = "https://abc.supabase.co"
KEY = "sb_secret_test"


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data
        self.text = "" if data is None else str(data)

    def json(self):
        return self._data


class FakePostgrest:
    """Just enough of PostgREST's /rest/v1/<table> behavior for the store."""

    def __init__(self, key=KEY, books_table=True, followups_column=True):
        self.key = key
        self.followups_column = followups_column
        self.rows = {}
        self.books = {} if books_table else None
        self.calls = []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append((method, params, headers))
        assert timeout
        if headers.get("apikey") != self.key:
            return FakeResponse(401, {"message": "Invalid API key"})
        if url == f"{URL}/rest/v1/{storage.BOOKS_TABLE}":
            return self.books_request(method, params, json)
        assert url == f"{URL}/rest/v1/{storage.TABLE}"
        if method == "GET":
            rows = sorted(self.rows.values(), key=lambda r: (r["date"], r["topic"]))
            return FakeResponse(200, [dict(r, updated_at="2026-09-23T00:00:00Z") for r in rows])
        if method == "POST":
            assert params == {"on_conflict": "date,topic"}
            assert "resolution=merge-duplicates" in headers["Prefer"]
            if not self.followups_column and any("followups" in r for r in json):
                return FakeResponse(400, {"code": "PGRST204", "message": "Could not find the 'followups' column"})
            for row in json:
                key = (row["date"], row["topic"])
                self.rows[key] = {**self.rows.get(key, {}), **row}
            return FakeResponse(201)
        if method == "DELETE":
            if not params:
                return FakeResponse(400, {"message": "DELETE requires a WHERE clause"})
            self.rows.clear()
            return FakeResponse(204)
        raise AssertionError(method)

    def books_request(self, method, params, json):
        if self.books is None:
            return FakeResponse(404, {"code": "PGRST205", "message": "Could not find the table"})
        if method == "GET":
            return FakeResponse(200, [{"data": b["data"]} for b in
                                      sorted(self.books.values(), key=lambda b: b["updated_at"])])
        if method == "POST":
            assert params == {"on_conflict": "id"}
            for row in json:
                datetime.fromisoformat(row["updated_at"])     # a real timestamp
                self.books[row["id"]] = row
            return FakeResponse(201)
        if method == "DELETE":
            assert params
            self.books.clear()
            return FakeResponse(204)
        raise AssertionError(method)


def make(fake=None, key=KEY):
    fake = fake or FakePostgrest()
    return fake, storage.SupabaseStore(URL, key, session=fake)


def test_make_store_picks_backend():
    assert isinstance(storage.make_store(URL, KEY), storage.SupabaseStore)
    assert isinstance(storage.make_store("", ""), storage.FileStore)
    assert isinstance(storage.make_store(URL, ""), storage.FileStore)


def test_round_trip_one_entry_at_a_time():
    fake, store = make()
    assert store.load() == core.empty_log()
    log = core.empty_log()
    e = core.start_entry(log, date(2026, 9, 23), "reading")
    e["title"] = "看書 — 第一章（入門）"
    store.save_entry(log, e)
    e["completed"] = True
    store.save_entry(log, e)          # upsert, not a second row
    assert len(fake.rows) == 1
    assert store.load() == log


def test_save_entry_only_sends_that_entry():
    fake, store = make()
    log = core.empty_log()
    for d in (1, 2, 3):
        core.start_entry(log, date(2026, 9, d), "cosmos")
    store.save_entry(log, log["entries"][1])
    assert list(fake.rows) == [("2026-09-02", "cosmos")]


def test_replace_clears_then_inserts():
    fake, store = make()
    old = core.empty_log()
    core.start_entry(old, date(2026, 9, 1), "free")
    store.replace(old)
    new = core.empty_log()
    core.start_entry(new, date(2026, 9, 2), "fashion")
    store.replace(new)
    assert list(fake.rows) == [("2026-09-02", "fashion")]
    delete = [c for c in fake.calls if c[0] == "DELETE"][0]
    assert delete[1]                  # filtered, as PostgREST requires


def test_auth_headers_by_key_type():
    fake, store = make()
    store.load()
    assert "Authorization" not in fake.calls[0][2]
    jwt = "eyJhbGciOiJIUzI1NiJ9.x.y"
    fake, store = make(FakePostgrest(key=jwt), key=jwt)
    store.load()
    assert fake.calls[0][2]["Authorization"] == f"Bearer {jwt}"


def test_errors_become_storage_errors():
    _, store = make(FakePostgrest(key="other"))
    with pytest.raises(storage.StorageError) as info:
        store.load()
    assert info.value.status == 401
    assert "Invalid API key" not in str(info.value)     # details stay in the log

    class Down:
        def request(self, *a, **k):
            raise requests.ConnectionError("no route")

    with pytest.raises(storage.StorageError, match="連不到資料庫"):
        storage.SupabaseStore(URL, KEY, session=Down()).load()


def test_file_store_round_trip(tmp_path):
    store = storage.FileStore(tmp_path / "log.json")
    log = core.empty_log()
    e = core.start_entry(log, date(2026, 9, 23), "philosophy")
    store.save_entry(log, e)
    assert store.load() == log


def test_parse_log_fills_missing_fields():
    log = core.parse_log({"entries": [
        {"date": "2026-09-02", "topic": "reading", "completed": True},
        {"date": "2026-09-01", "topic": "reading", "title": "第一章"},
        {"date": "not a date", "topic": "reading"},
        {"date": "2026-09-03", "topic": "unknown"},
    ]})
    assert [(e["date"], e["session_number"], e["level"]) for e in log["entries"]] == [
        ("2026-09-01", 1, "入門"), ("2026-09-02", 2, "入門")]
    assert all(set(e) == set(core.ENTRY_FIELDS) for e in log["entries"])
    assert log["entries"][0]["title"] == "第一章" and log["entries"][1]["completed"] is True


def test_books_round_trip_and_replace():
    fake, store = make()
    log = store.load()
    book = books.new_book(date(2026, 9, 23))
    book["title"] = "原子習慣"
    log["books"].append(book)
    store.save_book(log, book)
    book["status"] = "reading"
    store.save_book(log, book)
    assert len(fake.books) == 1
    loaded = store.load()
    assert loaded["books"] == [book] and store.books_error is None
    store.replace(core.empty_log())
    assert fake.books == {}


def test_missing_books_table_only_disables_books():
    fake, store = make(FakePostgrest(books_table=False))
    log = core.empty_log()
    store.save_entry(log, core.start_entry(log, date(2026, 9, 23), "cosmos"))
    loaded = store.load()
    assert len(loaded["entries"]) == 1 and loaded["books"] == []
    assert store.books_error == storage.BOOKS_TABLE_MISSING
    store.replace(loaded)                  # doesn't touch the missing table
    assert len(fake.rows) == 1


def test_url_with_or_without_rest_suffix():
    for url in (URL, URL + "/", URL + "/rest/v1", URL + "/rest/v1/", " " + URL + " "):
        fake = FakePostgrest()
        storage.SupabaseStore(url, KEY, session=fake).load()   # fake asserts the exact URL


def test_followups_round_trip():
    fake, store = make()
    log = core.empty_log()
    e = core.start_entry(log, date(2026, 9, 23), "cosmos")
    e["followups"] = [{"role": "user", "content": "再舉個例子"}, {"role": "assistant", "content": "好"}]
    store.save_entry(log, e)
    assert store.load()["entries"][0]["followups"] == e["followups"]


def test_missing_followups_column_still_saves_the_entry():
    fake, store = make(FakePostgrest(followups_column=False))
    log = core.empty_log()
    e = core.start_entry(log, date(2026, 9, 23), "cosmos")
    e.update(completed=True, followups=[{"role": "user", "content": "q"}])
    store.save_entry(log, e)                       # no error
    assert store.followups_supported is False
    row = fake.rows[("2026-09-23", "cosmos")]
    assert row["completed"] is True and "followups" not in row
    assert store.load()["entries"][0]["followups"] == []
