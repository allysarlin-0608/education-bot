import json
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

    def __init__(self, key=KEY, books_table=True, followups_column=True, missing_columns=(), settings_table=False,
                 paths_table=True):
        self.key = key
        self.settings = {} if settings_table else None
        self.missing = set(missing_columns) | (set() if followups_column else {"followups"})
        self.rows = {}
        self.books = {} if books_table else None
        self.paths = {} if paths_table else None     # learning_paths (supabase/goals.sql)
        self.calls = []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append((method, params, headers))
        assert timeout
        if headers.get("apikey") != self.key:
            return FakeResponse(401, {"message": "Invalid API key"})
        if url == f"{URL}/rest/v1/{storage.BOOKS_TABLE}":
            return self.books_request(method, params, json)
        if url == f"{URL}/rest/v1/{storage.SETTINGS_TABLE}":
            return self.settings_request(method, params, json)
        if url == f"{URL}/rest/v1/{storage.PATHS_TABLE}":
            return self.paths_request(method, params, json)
        if url == f"{URL}/rest/v1/{storage.PREFS_TABLE}":
            return self.prefs_request(method, params, json)
        assert url == f"{URL}/rest/v1/{storage.TABLE}"
        if method == "GET":
            if params and params.get("select") in self.missing:
                return FakeResponse(400, {"code": "42703", "message": f"column learning_entries.{params['select']} does not exist"})
            rows = sorted(self.rows.values(), key=lambda r: (r["date"], r["topic"]))
            if params and params.get("select") == "date,topic":
                return FakeResponse(200, [{"date": r["date"], "topic": r["topic"]} for r in rows])
            return FakeResponse(200, [dict(r, updated_at="2026-09-23T00:00:00Z") for r in rows])
        if method == "POST":
            assert params == {"on_conflict": "date,topic"}
            assert "resolution=merge-duplicates" in headers["Prefer"]
            for col in sorted(self.missing):
                if any(col in r for r in json):
                    return FakeResponse(400, {"code": "PGRST204", "message": f"Could not find the '{col}' column of 'learning_entries' in the schema cache"})
            for row in json:
                key = (row["date"], row["topic"])
                self.rows[key] = {**self.rows.get(key, {}), **row}
            return FakeResponse(201)
        if method == "DELETE":
            if not params:
                return FakeResponse(400, {"message": "DELETE requires a WHERE clause"})
            if "date" in params and "topic" in params:
                self.rows.pop((params["date"].removeprefix("eq."), params["topic"].removeprefix("eq.")), None)
            else:
                self.rows.clear()
            return FakeResponse(204)
        raise AssertionError(method)

    def prefs_request(self, method, params, json):
        if self.paths is None:                 # (made by the same goals.sql)
            return FakeResponse(404, {"code": "42P01", "message": "relation \"public.learner_prefs\" does not exist"})
        if method == "GET":
            return FakeResponse(200, [{"data": self.prefs}] if getattr(self, "prefs", None) else [])
        self.prefs = json[0]["data"]
        return FakeResponse(201)

    def paths_request(self, method, params, json):
        if self.paths is None:
            return FakeResponse(404, {"code": "42P01", "message": "relation \"public.learning_paths\" does not exist"})
        if method == "GET":
            if params.get("select") == "id":
                return FakeResponse(200, [{"id": k} for k in self.paths])
            return FakeResponse(200, [{"data": r["data"]} for r in self.paths.values()])
        if method == "POST":
            for row in json:
                self.paths[row["id"]] = row
            return FakeResponse(201)
        if method == "DELETE":
            self.paths.pop(params["id"].removeprefix("eq."), None)
            return FakeResponse(204)
        raise AssertionError(method)

    def settings_request(self, method, params, json):
        if self.settings is None:
            return FakeResponse(404, {"code": "PGRST205", "message": "Could not find the table 'public.user_settings'"})
        if method == "GET":
            uid = params["user_id"].removeprefix("eq.")        # always by user_id
            return FakeResponse(200, [r for k, r in self.settings.items() if k == uid])
        if method == "POST":
            assert params == {"on_conflict": "user_id"}
            for row in json:
                self.settings[row["user_id"]] = row
            return FakeResponse(201)
        raise AssertionError(method)

    def books_request(self, method, params, json):
        if self.books is None:
            return FakeResponse(404, {"code": "PGRST205", "message": "Could not find the table"})
        if method == "GET":
            if params.get("select") == "id":
                return FakeResponse(200, [{"id": k} for k in self.books])
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
            if "id" in params and params["id"].startswith("eq."):
                self.books.pop(params["id"].removeprefix("eq."), None)
            else:
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


def test_replace_writes_before_it_removes(monkeypatch):
    """BUG-005: if writing the backup fails, nothing already saved is gone."""
    fake, store = make()
    old = core.empty_log()
    core.start_entry(old, date(2026, 9, 1), "free")
    store.replace(old)
    new = core.empty_log()
    core.start_entry(new, date(2026, 9, 2), "fashion")
    real = fake.request

    def failing(method, url, **kw):
        if method == "POST":
            return FakeResponse(500, {"message": "down"})
        return real(method, url, **kw)
    fake.request = failing
    with pytest.raises(storage.StorageError):
        store.replace(new)
    assert ("2026-09-01", "free") in fake.rows          # still there


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

    with pytest.raises(storage.StorageError, match="can't reach the database"):
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
        ("2026-09-01", 1, "Beginner"), ("2026-09-02", 2, "Beginner")]
    assert all(set(e) == set(core.ENTRY_FIELDS) for e in log["entries"])
    assert log["entries"][0]["title"] == "第一章" and log["entries"][1]["completed"] is True


def test_books_round_trip_and_replace():
    fake, store = make()
    log = store.load()
    book = books.new_book(date(2026, 9, 23))
    book["title"] = "原子習慣"
    book["chapters"] = [f"Chapter {k}" for k in range(1, 21)]
    book["chapter_count"] = 20
    book["plan"] = books.allocate(20)
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
    assert store.missing_columns == {"followups"}
    row = fake.rows[("2026-09-23", "cosmos")]
    assert row["completed"] is True and "followups" not in row
    assert store.load()["entries"][0]["followups"] == []


def test_kickoff_round_trip_and_missing_column():
    fake, store = make()
    log = core.empty_log()
    e = core.start_entry(log, date(2026, 9, 23), "cosmos")
    e["kickoff"] = "今天是 2026-09-23，星期三。今天的主題：宇宙學。我今天特別想了解：黑洞"
    store.save_entry(log, e)
    assert store.load()["entries"][0]["kickoff"].endswith("我今天特別想了解：黑洞")
    # a database without the new columns still saves everything else
    fake, store = make(FakePostgrest(missing_columns=("kickoff", "followups")))
    store.save_entry(log, e)
    assert store.missing_columns == {"kickoff", "followups"}
    assert "kickoff" not in fake.rows[("2026-09-23", "cosmos")]


def test_other_400_errors_are_not_swallowed():
    class Bad(FakePostgrest):
        def request(self, method, url, **kw):
            if method == "POST":
                return FakeResponse(400, {"message": "invalid input syntax for type date"})
            return super().request(method, url, **kw)
    _, store = make(Bad())
    log = core.empty_log()
    with pytest.raises(storage.StorageError):
        store.save_entry(log, core.start_entry(log, date(2026, 9, 23), "cosmos"))


def test_levels_saved_in_chinese_by_older_versions_are_read_in_english():
    log = core.parse_log({"entries": [
        {"date": "2026-09-01", "topic": "philosophy", "session_number": 9, "level": "進階"},
        {"date": "2026-09-02", "topic": "fashion", "session_number": 5, "level": "中階"},
    ]})
    assert [e["level"] for e in log["entries"]] == ["Advanced", "Intermediate"]


def test_file_store_keeps_what_another_tab_saved(tmp_path):
    """ISS-009: a save from a tab loaded earlier wrote its whole (older) log
    and wiped what another tab had saved since."""
    store = storage.FileStore(tmp_path / "log.json")
    tab_a, tab_b = store.load(), store.load()
    e = core.start_entry(tab_b, date(2026, 10, 3), "philosophy")
    store.save_entry(tab_b, e)                         # tab B: today's lesson
    book = books.new_book(date(2026, 10, 3))
    tab_a["books"].append(book)
    store.save_book(tab_a, book)                       # tab A (older copy): a book
    e2 = core.start_entry(tab_a, date(2026, 10, 2), "cosmos")
    store.save_entry(tab_a, e2)                        # and an entry of its own
    stored = store.load()
    assert [(x["date"], x["topic"]) for x in stored["entries"]] == [("2026-10-02", "cosmos"), ("2026-10-03", "philosophy")]
    assert [b["id"] for b in stored["books"]] == [book["id"]]


def test_a_file_that_cant_be_read_is_never_saved_over(tmp_path):
    """ISS-020: a damaged file was read as empty, and the next save kept only
    the one entry it was saving."""
    store = storage.FileStore(tmp_path / "log.json")
    log = core.empty_log()
    for d in (1, 2):
        store.save_entry(log, core.start_entry(log, date(2026, 10, d), "philosophy"))
    path = tmp_path / "log.json"
    damaged = path.read_text()[:-5]
    path.write_text(damaged)
    with pytest.raises(storage.StorageError):
        store.save_entry(log, core.start_entry(log, date(2026, 10, 3), "philosophy"))
    assert path.read_text() == damaged                    # left as it was, for repair
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("content", [b"[]", b'{"entries": 5}', b"\xff\xfe not text"], ids=["a list", "wrong shape", "not text"])
def test_a_damaged_file_is_a_clear_error_not_a_crash(tmp_path, content):
    """ISS-027: a log file of the wrong shape raised a raw ValueError on every page."""
    (tmp_path / "log.json").write_bytes(content)
    store = storage.FileStore(tmp_path / "log.json")
    with pytest.raises(storage.StorageError):
        store.load()
    log = core.empty_log()
    with pytest.raises(storage.StorageError):
        store.save_entry(log, core.start_entry(log, date(2026, 10, 3), "philosophy"))
    assert (tmp_path / "log.json").read_bytes() == content


# ---------- her goals (supabase/goals.sql) ----------
def _goal():
    from test_goals import a_path
    return a_path()


def test_a_goal_is_saved_read_back_and_kept_through_a_backup():
    fake, store = make()
    g = _goal()
    log = store.load()
    store.save_path(log, g)
    assert store.load()["paths"] == [g]
    other = dict(_goal(), title="Another")
    store.replace(dict(log, paths=[other]))           # a backup with another goal: hers becomes exactly that
    assert [p["id"] for p in store.load()["paths"]] == [other["id"]]


def test_without_the_goals_table_goals_say_so_and_nothing_else_breaks():
    fake, store = make(FakePostgrest(paths_table=False))
    log = store.load()
    assert log["paths"] == [] and store.paths_error == storage.PATHS_TABLE_MISSING
    with pytest.raises(storage.StorageError, match="goals.sql"):
        store.save_path(log, _goal())
    store.replace(log)                                   # a backup still imports (its goals wait for the table)


def test_file_store_keeps_goals_and_her_counts(tmp_path):
    store = storage.FileStore(tmp_path / "log.json", tmp_path / "s.json", current_user=lambda: "owner")
    g = _goal()
    store.save_path(store.load(), g)
    store.save_path(store.load(), dict(g, status="archived"))
    assert [p["status"] for p in store.load()["paths"]] == ["archived"]
    store.add_event("2026-09-01", "visit")
    store.add_event("2026-09-01", "visit")              # a visit counts once a day
    store.add_event("2026-09-01", "lesson_passed")
    store.add_event("2026-09-01", "lesson_passed")
    data = store.export_my_data()
    assert data["learning_paths"][0]["id"] == g["id"]
    assert sorted((e["event"], e["count"]) for e in data["usage_events"]) == [("lesson_passed", 2), ("visit", 1)]
    assert "text" not in json.dumps(data["usage_events"]), "counts only"


# ---------- a database blip ----------
class Flaky:
    """The fake database, failing the first `n` requests in a given way."""
    def __init__(self, fake, n, how):
        self.fake, self.n, self.how, self.calls = fake, n, how, []

    def request(self, method, url, **kw):
        self.calls.append(method)
        if len(self.calls) <= self.n:
            if self.how == "drop":
                raise requests.ConnectionError("connection reset by peer")
            if self.how == "slow":
                raise requests.ReadTimeout("read timed out")
            return FakeResponse(self.how, {"message": "gateway"})
        return self.fake.request(method, url, **kw)


@pytest.fixture
def no_pause(monkeypatch):
    monkeypatch.setattr(storage, "_sleep", lambda s: None)


@pytest.mark.parametrize("how", ["drop", 503, 502, 504])
def test_a_read_survives_one_blip(no_pause, how):
    fake = FakePostgrest()
    flaky = Flaky(fake, 1, how)
    store = storage.SupabaseStore(URL, KEY, session=flaky)
    assert store.load()["entries"] == []
    assert flaky.calls[:2] == ["GET", "GET"]


def test_a_read_that_keeps_failing_says_so(no_pause):
    flaky = Flaky(FakePostgrest(), 99, "drop")
    with pytest.raises(storage.StorageError, match="can't reach the database"):
        storage.SupabaseStore(URL, KEY, session=flaky).load()
    assert flaky.calls == ["GET", "GET"], "once more, not forever"


@pytest.mark.parametrize("how", ["drop", 503])
def test_a_write_is_never_sent_twice(no_pause, how):
    fake = FakePostgrest()
    store = storage.SupabaseStore(URL, KEY, session=fake)
    log = store.load()
    entry = core.start_entry(log, date(2026, 9, 1), "free")
    flaky = Flaky(fake, 1, how)
    store.session = flaky
    with pytest.raises(storage.StorageError):
        store.save_entry(log, entry)
    assert flaky.calls == ["POST"], "a write that may have landed isn't repeated"


def test_a_real_refusal_isnt_retried(no_pause):
    flaky = Flaky(FakePostgrest(), 1, 400)
    with pytest.raises(storage.StorageError):
        storage.SupabaseStore(URL, KEY, session=flaky).load()
    assert flaky.calls == ["GET"]


def test_a_read_that_timed_out_isnt_asked_again(no_pause):
    """Sent but not answered in time: the database is slow; asking twice
    would double her wait and its load."""
    flaky = Flaky(FakePostgrest(), 1, "slow")
    with pytest.raises(storage.StorageError):
        storage.SupabaseStore(URL, KEY, session=flaky).load()
    assert flaky.calls == ["GET"]
    connect, read = storage.TIMEOUT
    assert connect < read <= 10, "a dead host is noticed in seconds"


# ---------- the local files: saved under one lock, never overwritten when unreadable ----------
def _local(tmp_path, who):
    return storage.FileStore(tmp_path / f"{who}.json", tmp_path / "settings.json", current_user=lambda: who)


def test_two_people_saving_settings_at_once_keep_both(tmp_path):
    import threading
    from coach import settings
    stores = [_local(tmp_path, f"u{k}") for k in range(8)]
    go = threading.Barrier(len(stores))

    def save(store, k):
        go.wait()
        for n in range(15):
            store.save_settings(dict(settings.blank(f"u{k}"), units_per_day=(1, 3, 5)[n % 3]))
    threads = [threading.Thread(target=save, args=(s, k)) for k, s in enumerate(stores)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = json.loads((tmp_path / "settings.json").read_text())["user_settings"]
    assert sorted(r["user_id"] for r in rows) == [f"u{k}" for k in range(8)], "no one's row was lost"


@pytest.mark.parametrize("damage", ["{not json", '"just text"', '{"other": 1}'])
def test_a_damaged_settings_file_is_reported_and_left_alone(tmp_path, damage):
    from coach import settings
    (tmp_path / "settings.json").write_text(damage)
    store = _local(tmp_path, "u1")
    with pytest.raises(storage.StorageError, match="can't be read"):
        store.save_settings(settings.blank("u1"))
    with pytest.raises(storage.StorageError):
        store.load_settings()
    assert (tmp_path / "settings.json").read_text() == damage, "left as it was, for repair"


def test_a_damaged_usage_file_is_never_overwritten(tmp_path):
    store = _local(tmp_path, "u1")
    store.add_usage("2026-09-01", 1, 10)
    path = store._table_path(storage.USAGE_TABLE)
    path.write_text("[{broken")
    with pytest.raises(storage.StorageError):
        store.add_usage("2026-09-01", 1, 10)
    assert path.read_text() == "[{broken"
