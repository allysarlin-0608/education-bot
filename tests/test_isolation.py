"""Two people, A and B, each with settings, lessons, a quiz, a book and AI
usage. Neither may ever see, change or delete the other's. Run against both
stores in APP_MODE=public (scoped) form: the local files, and Supabase through
a fake PostgREST that holds the tables exactly as supabase/multiuser.sql
makes them and applies only the filters it is sent (so a missing user_id
filter would leak, and this test would catch it)."""
from datetime import date

import pytest

from coach import books, core, settings, storage

URL = "https://abc.supabase.co"
KEY = "sb_secret_test"

# table -> its primary key, after multiuser.sql
SCHEMA = {
    storage.TABLE: ("user_id", "date", "topic"),
    storage.BOOKS_TABLE: ("user_id", "id"),
    storage.SETTINGS_TABLE: ("user_id",),
    storage.USERS_TABLE: ("user_id",),
    storage.INVITES_TABLE: ("email",),
    storage.USAGE_TABLE: ("user_id", "date"),
}
USER_TABLES = [t for t in SCHEMA if t != storage.INVITES_TABLE]


class Resp:
    def __init__(self, status_code=200, data=None):
        self.status_code, self._data = status_code, data
        self.text = "" if data is None else str(data)

    def json(self):
        return self._data


def _match(row, params):
    for col, cond in (params or {}).items():
        if col in ("select", "order", "limit", "on_conflict"):
            continue
        op, _, val = cond.partition(".")
        have = "" if row.get(col) is None else str(row.get(col))
        if op == "eq" and have != val:
            return False
        if op == "neq" and have == val:
            return False
        if op == "gte" and not have >= val:
            return False
    return True


class FakeDB:
    """In-memory tables plus the two functions, as PostgREST serves them."""

    def __init__(self):
        self.tables = {t: {} for t in SCHEMA}
        self.fail_delete_at = None           # to show delete_user_data is all-or-nothing

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        assert headers["apikey"] == KEY and timeout
        name = url.removeprefix(f"{URL}/rest/v1/")
        if name.startswith("rpc/"):
            return self.rpc(name[4:], json)
        table, pk = self.tables[name], SCHEMA[name]
        if method == "GET":
            rows = [r for r in table.values() if _match(r, params)]
            cols = params.get("select", "*")
            if cols != "*":
                rows = [{c: r.get(c) for c in cols.split(",")} for r in rows]
            return Resp(200, rows)
        if method == "POST":
            if tuple(params["on_conflict"].split(",")) != pk:
                return Resp(400, {"code": "42P10", "message": "no unique constraint matching the ON CONFLICT"})
            for row in json:
                if any(row.get(c) in (None, "") for c in pk):
                    return Resp(400, {"code": "23502", "message": f"null value in {pk} of {name}"})
            for row in json:
                key = tuple(str(row[c]) for c in pk)
                table[key] = {**table.get(key, {}), **row}
            return Resp(201)
        if method == "DELETE":
            if not any(k not in ("select", "order") for k in params or {}):
                return Resp(400, {"message": "DELETE requires a WHERE clause"})
            for key in [k for k, r in table.items() if _match(r, params)]:
                del table[key]
            return Resp(204)
        raise AssertionError(method)

    def rpc(self, fn, args):
        if fn == "add_ai_usage":
            key = (args["p_user_id"], args["p_date"])
            row = self.tables[storage.USAGE_TABLE].setdefault(
                key, {"user_id": key[0], "date": key[1], "request_count": 0, "token_count": 0})
            row["request_count"] += args["p_requests"]
            row["token_count"] += args["p_tokens"]
            return Resp(204)
        if fn == "delete_user_data":
            uid = args["p_user_id"]
            if not uid:
                return Resp(400, {"message": "no user"})
            snapshot = {t: dict(rows) for t, rows in self.tables.items()}
            for t in USER_TABLES:
                if t == self.fail_delete_at:
                    self.tables = snapshot                    # rolled back
                    return Resp(500, {"message": "boom"})
                for key in [k for k, r in self.tables[t].items() if r.get("user_id") == uid]:
                    del self.tables[t][key]
            return Resp(204)
        raise AssertionError(fn)


class Who:
    """get_current_user_id(), switchable between A and B."""
    def __init__(self):
        self.uid = None

    def __call__(self):
        return self.uid


@pytest.fixture(params=["file", "supabase"])
def world(request, tmp_path):
    who = Who()
    if request.param == "file":
        store = storage.FileStore(tmp_path / "learning_log.json", tmp_path / "user_settings.json",
                                  scoped=True, current_user=who)
        db = None
    else:
        db = FakeDB()
        store = storage.SupabaseStore(URL, KEY, session=db, scoped=True, current_user=who)
    return store, who, db


QUIZ = {"questions": [{"type": "choice", "question": "Q1", "options": ["a", "b", "c", "d"], "answer": 1}],
        "answers": [1]}


def fill(store, who, uid, email, topic, book_title, subjects):
    """Everything a person makes: users row, settings, a day with a lesson and
    its quiz, a book, and AI usage."""
    who.uid = uid
    store.touch_user(email, uid.upper())
    s = settings.finish(settings.blank(uid),
                        dict(settings.new_draft(), subjects=subjects, units_per_day=3), "2026-09-26T02:00:00+00:00")
    store.save_settings(s)
    log = store.load()
    e = core.start_entry(log, date(2026, 9, 26), topic)
    e["title"] = f"{uid} lesson"
    e["lessons"] = [{"n": 1, "title": f"{uid} unit 1", "unit": "U1", "kickoff": "", "lesson": f"{uid} text",
                     "followups": [], "completed": True, "quiz": QUIZ}]
    store.save_entry(log, e)
    b = books.new_book(date(2026, 9, 26))
    b["title"] = book_title
    log["books"].append(b)
    store.save_book(log, b)
    store.add_usage("2026-09-26", 3, 1000)
    return log


def test_a_and_b_see_only_their_own(world):
    store, who, _ = world
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    fill(store, who, "sub-b", "b@example.com", "cosmos", "B's book", ["fashion", "investing"])  # same day, same topic

    for me, other in (("sub-a", "sub-b"), ("sub-b", "sub-a")):
        who.uid = me
        log = store.load()
        assert [e["title"] for e in log["entries"]] == [f"{me} lesson"]
        assert log["entries"][0]["lessons"][0]["lesson"] == f"{me} text"
        assert log["entries"][0]["lessons"][0]["quiz"]["answers"] == [1]
        assert [b["title"] for b in log["books"]] == [f"{me[-1].upper()}'s book"]
        assert store.load_settings()["user_id"] == me
        assert store.user_row()["user_id"] == me
        assert store.usage_today("2026-09-26")["request_count"] == 3
        dump = repr(store.export_my_data())
        assert other not in dump and f"{other[-1].upper()}'s book" not in dump

    who.uid = "sub-a"
    assert store.load_settings()["subjects"] == ["cosmos"]
    who.uid = "sub-b"
    assert store.load_settings()["subjects"] == ["fashion", "investing"]


def test_writes_never_touch_the_other(world):
    store, who, _ = world
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    fill(store, who, "sub-b", "b@example.com", "cosmos", "B's book", ["fashion"])
    who.uid = "sub-b"
    store.replace(core.empty_log())                  # B wipes their log (backup import)
    store.add_usage("2026-09-26", 50, 9)
    who.uid = "sub-a"
    log = store.load()
    assert len(log["entries"]) == 1 and len(log["books"]) == 1
    assert store.usage_today("2026-09-26") == {**store.usage_today("2026-09-26"), "request_count": 3, "token_count": 1000}


def test_delete_my_account_takes_only_mine(world):
    store, who, db = world
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    fill(store, who, "sub-b", "b@example.com", "cosmos", "B's book", ["fashion"])
    who.uid = "sub-a"
    store.delete_my_account()
    assert store.load() == core.empty_log()
    assert store.load_settings() is None and store.user_row() is None
    assert store.usage_today("2026-09-26")["request_count"] == 0
    assert store.export_my_data()["learning_entries"] == []
    who.uid = "sub-b"
    assert len(store.load()["entries"]) == 1 and store.user_row()["email"] == "b@example.com"
    if db:
        for t in USER_TABLES:
            assert not [r for r in db.tables[t].values() if r.get("user_id") == "sub-a"], t


def test_delete_is_all_or_nothing():
    db, who = FakeDB(), Who()
    store = storage.SupabaseStore(URL, KEY, session=db, scoped=True, current_user=who)
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    db.fail_delete_at = storage.USERS_TABLE          # the last step fails
    with pytest.raises(storage.StorageError):
        store.delete_my_account()
    assert len(store.load()["entries"]) == 1 and store.user_row() is not None


def test_no_one_signed_in_reads_and_writes_nothing(world):
    store, who, db = world
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    who.uid = None
    for call in (store.load, store.load_settings, store.user_row, store.export_my_data,
                 store.delete_my_account, lambda: store.save_settings({}),
                 lambda: store.add_usage("2026-09-26", 1, 1), lambda: store.touch_user("x@y.z", "x")):
        with pytest.raises(storage.StorageError, match=storage.NO_USER):
            call()
    who.uid = "sub-a"
    assert len(store.load()["entries"]) == 1


def test_invites_are_lower_case_and_immediate(world):
    store, who, _ = world
    who.uid = "admin"
    store.add_invite("Friend@Example.COM", "from class")
    assert store.is_invited("friend@example.com") and store.is_invited("FRIEND@example.com")
    assert [r["email"] for r in store.list_invites()] == ["friend@example.com"]
    store.remove_invite("friend@example.com")
    assert not store.is_invited("friend@example.com") and store.list_invites() == []


def test_first_sign_in_makes_the_row_later_ones_touch_it(world):
    store, who, _ = world
    who.uid = "sub-a"
    store.touch_user("a@example.com", "A")
    first = store.user_row()
    store.touch_user("a@example.com", "A")
    again = store.user_row()
    assert again["created_at"] == first["created_at"] and again["last_seen_at"] >= first["last_seen_at"]


def test_personal_mode_is_unscoped_as_before(tmp_path):
    """APP_MODE=personal: the one log file, keyed as it always was."""
    store = storage.FileStore(tmp_path / "learning_log.json", tmp_path / "s.json", current_user=lambda: "owner")
    log = core.empty_log()
    store.save_entry(log, core.start_entry(log, date(2026, 9, 26), "cosmos"))
    assert (tmp_path / "learning_log.json").exists()
    db = FakeDB()
    sup = storage.SupabaseStore(URL, KEY, session=db, current_user=lambda: "owner")
    assert sup._mine({"select": "*"}) == {"select": "*"}          # no user_id filter


def test_only_storage_talks_to_the_database():
    """Every read and write goes through coach/storage.py."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    offenders = [str(p.relative_to(root)) for p in root.rglob("*.py")
                 if "tests" not in p.parts and p.name != "storage.py" and ".venv" not in p.parts
                 and any(s in p.read_text(encoding="utf-8") for s in ("import requests", "/rest/v1", "SupabaseStore("))]
    assert offenders == []
