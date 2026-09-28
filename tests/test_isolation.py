"""Two people, A and B, each with settings, lessons, a quiz, a book and AI
usage. Neither may ever see, change or delete the other's. Run against:

- the local files (scoped),
- Supabase through a fake PostgREST holding the tables as the migrations
  make them, in two ways:
  * "supabase-rls": the database's row level security as supabase/accounts.sql
    sets it up (each request is made as the person, by their access token);
  * "supabase-norls": no row level security at all, only the filters the app
    sends, so a missing user_id filter in the app would leak and fail here.
Either layer alone keeps A and B apart."""
from datetime import date

import pytest

from coach import books, core, settings, storage

from fake_supabase import KEY, OWN_ROWS, SCHEMA, URL, USER_TABLES, FakeDB  # noqa: F401


class Who:
    """get_current_user_id() and the access token, switchable between people."""
    def __init__(self):
        self.uid = None
        self.email = ""

    def __call__(self):
        return self.uid

    def token(self):
        return f"tok|{self.uid}|{self.email}" if self.uid else None

    def be(self, uid, email=""):
        self.uid, self.email = uid, email or (f"{uid}@example.com" if uid else "")


def supabase(db, who):
    return storage.SupabaseStore(URL, KEY, session=db, scoped=True, current_user=who, access_token=who.token)


@pytest.fixture(params=["file", "supabase-rls", "supabase-norls"])
def world(request, tmp_path):
    who = Who()
    if request.param == "file":
        store = storage.FileStore(tmp_path / "learning_log.json", tmp_path / "user_settings.json",
                                  scoped=True, current_user=who)
        db = None
    else:
        db = FakeDB(rls=request.param == "supabase-rls")
        store = supabase(db, who)
    return store, who, db


QUIZ = {"questions": [{"type": "choice", "question": "Q1", "options": ["a", "b", "c", "d"], "answer": 1}],
        "answers": [1]}


def fill(store, who, uid, email, topic, book_title, subjects):
    """Everything a person makes: users row, settings, a day with a lesson and
    its quiz, a book, and AI usage."""
    who.be(uid, email)
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
        who.be(me, f"{me[-1]}@example.com")
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

    who.be("sub-a", "a@example.com")
    assert store.load_settings()["subjects"] == ["cosmos"]
    who.be("sub-b", "b@example.com")
    assert store.load_settings()["subjects"] == ["fashion", "investing"]


def test_writes_never_touch_the_other(world):
    store, who, _ = world
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    fill(store, who, "sub-b", "b@example.com", "cosmos", "B's book", ["fashion"])
    who.be("sub-b", "b@example.com")
    store.replace(core.empty_log())                  # B wipes their log (backup import)
    store.add_usage("2026-09-26", 50, 9)
    who.be("sub-a", "a@example.com")
    log = store.load()
    assert len(log["entries"]) == 1 and len(log["books"]) == 1
    assert store.usage_today("2026-09-26") == {**store.usage_today("2026-09-26"), "request_count": 3, "token_count": 1000}


def test_delete_my_account_takes_only_mine(world):
    store, who, db = world
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    fill(store, who, "sub-b", "b@example.com", "cosmos", "B's book", ["fashion"])
    who.be("sub-a", "a@example.com")
    store.delete_my_account()
    assert store.load() == core.empty_log()
    assert store.load_settings() is None and store.user_row() is None
    assert store.usage_today("2026-09-26")["request_count"] == 0
    assert store.export_my_data()["learning_entries"] == []
    who.be("sub-b", "b@example.com")
    assert len(store.load()["entries"]) == 1 and store.user_row()["email"] == "b@example.com"
    if db:
        for t in USER_TABLES:
            assert not [r for r in db.tables[t].values() if r.get("user_id") == "sub-a"], t


def test_delete_is_all_or_nothing():
    db, who = FakeDB(), Who()
    store = supabase(db, who)
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    db.fail_delete_at = storage.USERS_TABLE          # the last step fails
    with pytest.raises(storage.StorageError):
        store.delete_my_account()
    assert len(store.load()["entries"]) == 1 and store.user_row() is not None


def test_no_one_signed_in_reads_and_writes_nothing(world):
    store, who, db = world
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    who.be(None)
    for call in (store.load, store.load_settings, store.user_row, store.export_my_data,
                 store.delete_my_account, lambda: store.save_settings({}),
                 lambda: store.add_usage("2026-09-26", 1, 1), lambda: store.touch_user("x@y.z", "x")):
        with pytest.raises(storage.StorageError, match=storage.NO_USER):
            call()
    who.be("sub-a", "a@example.com")
    assert len(store.load()["entries"]) == 1


def test_invites_are_lower_case_and_immediate(world):
    store, who, db = world
    who.be("admin", "boss@example.com")
    if db:
        db.tables[storage.ADMINS_TABLE][("boss@example.com",)] = {"email": "boss@example.com"}
    store.add_invite("Friend@Example.COM", "from class")
    assert store.is_invited("friend@example.com") and store.is_invited("FRIEND@example.com")
    assert [r["email"] for r in store.list_invites()] == ["friend@example.com"]
    store.remove_invite("friend@example.com")
    assert not store.is_invited("friend@example.com") and store.list_invites() == []


def test_first_sign_in_makes_the_row_later_ones_touch_it(world):
    store, who, _ = world
    who.be("sub-a", "a@example.com")
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
    sup = storage.SupabaseStore(URL, "sb_secret_owner", session=FakeDB(rls=False), current_user=lambda: "owner")
    assert sup._mine({"select": "*"}) == {"select": "*"}          # no user_id filter
    assert "Authorization" not in sup.headers                   # the secret key alone, as before


def test_only_storage_talks_to_the_database():
    """Every read and write of data goes through coach/storage.py (sign-in
    itself goes through coach/supa_auth.py, to /auth/v1 only)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    allowed = {"requests": {"storage.py", "supa_auth.py"}}
    offenders = []
    for p in root.rglob("*.py"):
        if "tests" in p.parts or ".venv" in p.parts or p.name.startswith("_sim"):
            continue
        if p.parts[len(root.parts)] == "tools":     # command-line tools run by hand, never part of the app
            continue
        text = p.read_text(encoding="utf-8")
        if p.name != "storage.py" and ("/rest/v1" in text or "SupabaseStore(" in text):
            offenders.append(str(p.relative_to(root)))
        if "import requests" in text and p.name not in allowed["requests"]:
            offenders.append(str(p.relative_to(root)))
    assert offenders == []


def test_public_mode_refuses_a_key_that_bypasses_security():
    who = Who()
    for key in ("sb_secret_abc", "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.x"):
        with pytest.raises(storage.StorageError, match="publishable"):
            storage.SupabaseStore(URL, key, session=FakeDB(), scoped=True, current_user=who, access_token=who.token)


def test_with_rls_a_forged_user_id_is_refused_by_the_database():
    """Even if the app sent the wrong user_id, the database would refuse."""
    db, who = FakeDB(), Who()
    store = supabase(db, who)
    fill(store, who, "sub-a", "a@example.com", "cosmos", "A's book", ["cosmos"])
    who.be("sub-b", "b@example.com")
    forged = lambda: "sub-a"            # noqa: E731 - the app believes it is A, the token says B
    evil = storage.SupabaseStore(URL, KEY, session=db, scoped=True, current_user=forged, access_token=who.token)
    assert evil.load()["entries"] == []                       # B's token sees none of A's rows
    with pytest.raises(storage.StorageError):
        evil.save_settings({"subjects": ["fashion"], "units_per_day": 3})
    who.be("sub-a", "a@example.com")
    assert store.load_settings()["subjects"] == ["cosmos"]


def test_admin_is_what_the_database_says():
    db, who = FakeDB(), Who()
    store = supabase(db, who)
    db.tables[storage.ADMINS_TABLE][("boss@example.com",)] = {"email": "boss@example.com"}
    who.be("u1", "boss@example.com")
    assert store.is_admin("boss@example.com")
    who.be("u2", "b@example.com")
    assert not store.is_admin("b@example.com") and not store.is_admin("boss@example.com")
    with pytest.raises(storage.StorageError):
        store.add_invite("x@example.com")
