"""Moving out of Supabase, checked: a copy of a Supabase database (its
auth.users and auth.identities, and the app's tables as the SQL files in
supabase/ made them) is imported into our schema. Every person's record
comes back exactly, password hashes and Google identities are kept, admins
keep their role, a person who can't be copied is rolled back alone, a dry
run keeps nothing, a second run replaces the first. The "Download my data"
file of the current app imports too."""
import copy
import json
import uuid

import pytest
from sqlalchemy import create_engine, select, text

from coach import core, prefs, settings
from gnosis.data import schema as t
from gnosis.data.repositories import accounts, learning
from gnosis.migrate import supabase as mig
from test_learning_repository import rich_log
from conftest import ADMIN_URL, _url

ANN, BOB, CY = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
HASH = "$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy"

SUPABASE_DDL = """
create schema auth;
create table auth.users (id uuid primary key, email text, encrypted_password text, raw_user_meta_data jsonb,
  created_at timestamptz default now(), last_sign_in_at timestamptz);
create table auth.identities (id text, user_id uuid, provider text, provider_id text, identity_data jsonb);
create table public.users (user_id text primary key, email text not null, display_name text not null default '',
  avatar_url text not null default '', created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now());
create table public.app_admins (email text primary key);
create table public.allowed_users (email text primary key, invited_at timestamptz default now(), note text default '');
create table public.user_settings (user_id text primary key, subjects jsonb not null default '[]',
  units_per_day integer not null default 3, subject_levels jsonb not null default '{}',
  reading_enabled boolean not null default false, onboarding jsonb, onboarded_at timestamptz, updated_at timestamptz);
create table public.learning_entries (user_id text, date date not null, topic text not null,
  session_number integer not null, level text not null, completed boolean not null default false,
  title text not null default '', followup_question text not null default '', reflection text not null default '',
  lesson text not null default '', followups jsonb not null default '[]', kickoff text not null default '',
  lessons jsonb not null default '[]');
create table public.reading_books (user_id text, id text, data jsonb not null, updated_at timestamptz default now());
create table public.learning_paths (user_id text, id text, data jsonb not null, updated_at timestamptz default now());
create table public.learner_prefs (user_id text primary key, data jsonb not null);
create table public.ai_usage (user_id text, date date, request_count integer, token_count integer);
create table public.usage_events (user_id text, day date, event text, count integer);
"""                                                       # (no learning_signals: mastery.sql not run there yet)


@pytest.fixture
def supabase_copy():
    name = f"supa_{uuid.uuid4().hex[:8]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'create database "{name}"'))
    eng = create_engine(_url(name))
    with eng.begin() as c:
        c.exec_driver_sql(SUPABASE_DDL)
        log = core.parse_log(rich_log())
        c.execute(text("insert into auth.users (id, email, encrypted_password, raw_user_meta_data) values "
                       "(:a, 'ann@example.com', :h, '{\"full_name\": \"Ann\"}'), (:b, 'bob@example.com', '', '{}'), "
                       "(:c, 'ann@example.com', '', '{}')"), {"a": ANN, "b": BOB, "c": CY, "h": HASH})
        c.execute(text("insert into auth.identities (id, user_id, provider, provider_id, identity_data) values "
                       "('1', cast(:a as uuid), 'email', :a2, '{\"email\": \"ann@example.com\"}'), "
                       "('2', :b, 'google', '1099887766', '{\"sub\": \"1099887766\", \"email\": \"bob@example.com\"}')"),
                  {"a": ANN, "a2": ANN, "b": BOB})
        c.execute(text("insert into public.users (user_id, email, display_name) values (:a, 'ann@example.com', 'Ann'), "
                       "(:b, 'Bob@Example.com', 'Bob')"), {"a": ANN, "b": BOB})
        c.execute(text("insert into public.app_admins values ('ann@example.com')"))
        c.execute(text("insert into public.allowed_users (email, note) values ('bob@example.com', 'friend')"))
        c.execute(text("insert into public.user_settings (user_id, subjects, units_per_day, subject_levels, "
                       "reading_enabled, onboarded_at) values (:a, '[\"philosophy\", \"cosmos\"]', 3, "
                       "'{\"philosophy\": \"Beginner\", \"cosmos\": \"Intermediate\"}', true, '2026-10-01T08:00:00+00')"),
                  {"a": ANN})
        for e in log["entries"]:
            row = {k: e[k] for k in core.ENTRY_FIELDS}
            c.execute(text("insert into public.learning_entries (user_id, date, topic, session_number, level, completed, "
                           "title, followup_question, reflection, lesson, followups, kickoff, lessons) values (:u, :date, "
                           ":topic, :session_number, :level, :completed, :title, :followup_question, :reflection, :lesson, "
                           "cast(:followups as jsonb), :kickoff, cast(:lessons as jsonb))"),
                      dict(row, u=ANN, followups=json.dumps(row["followups"]), lessons=json.dumps(row["lessons"])))
        for b in log["books"]:
            c.execute(text("insert into public.reading_books (user_id, id, data) values (:u, :i, cast(:d as jsonb))"),
                      {"u": ANN, "i": b["id"], "d": json.dumps(b)})
        for g in log["paths"]:
            c.execute(text("insert into public.learning_paths (user_id, id, data) values (:u, :i, cast(:d as jsonb))"),
                      {"u": ANN, "i": g["id"], "d": json.dumps(g)})
        c.execute(text("insert into public.learner_prefs values (:u, cast(:d as jsonb))"),
                  {"u": ANN, "d": json.dumps(dict(prefs.blank(), reminder_on=True))})
        c.execute(text("insert into public.ai_usage values (:u, '2026-11-01', 12, 30000), (:u, '2026-11-02', 3, 9000)"),
                  {"u": ANN})
        c.execute(text("insert into public.usage_events values (:u, '2026-11-02', 'visit', 1), "
                       "(:u, '2026-11-02', 'lesson_passed', 4)"), {"u": ANN})
        c.execute(text("insert into public.learning_entries (user_id, date, topic, session_number, level) values "
                       "(null, '2026-01-01', 'philosophy', 1, 'Beginner')"))          # from before accounts: no owner
    yield _url(name), log
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f'drop database "{name}" with (force)'))
    admin.dispose()


def by_source(report):
    return {r["source_id"]: r for r in report["imported"]}


def test_every_person_comes_across_exactly(engine, supabase_copy):
    url, log = supabase_copy
    report = mig.import_all(engine, mig.PostgresSource(url))
    assert [f["source_id"] for f in report["failed"]] == [CY], "the third account shares Ann's email: refused alone"
    assert "email" not in json.dumps(report["failed"]).replace("this email", ""), "no email addresses in the report"
    done = by_source(report)
    with engine.begin() as c:
        ann, bob = done[ANN]["user_id"], done[BOB]["user_id"]
        assert learning.load_log(c, ann) == log, "her whole record, exactly"
        assert done[ANN]["ai_requests"] == 15 and done[ANN]["events"] == 5
        assert accounts.credential(c, ann) == {"user_id": ann, "password_hash": HASH, "algorithm": "bcrypt",
                                               "updated_at": accounts.credential(c, ann)["updated_at"]}
        assert accounts.credential(c, bob) is None, "a Google account has no password"
        assert accounts.identities(c, bob) == [{"provider": "google", "subject": "1099887766", "email": "bob@example.com"}]
        assert accounts.roles_of(c, ann) == ["admin", "user"] and accounts.roles_of(c, bob) == ["user"]
        assert accounts.user(c, bob)["email"] == "bob@example.com" and accounts.user(c, ann)["display_name"] == "Ann"
        s = accounts.load_settings(c, ann)
        assert s["subjects"] == ["philosophy", "cosmos"] and s["onboarded_at"].startswith("2026-10-01T08:00:00")
        assert settings.onboarded(settings.normalize(s, ann))
        assert accounts.load_prefs(c, ann)["reminder_on"] is True
        assert accounts.is_invited(c, "bob@example.com")
        audit = c.execute(select(t.audit_log.c.action)).scalars().all()
        assert audit.count("migrate.import_person") >= 2
        for uid in (ann, bob):                                     # (leave the shared test database clean)
            c.execute(t.users.delete().where(t.users.c.id == uid))
        c.execute(t.invites.delete())
        c.execute(t.audit_log.delete())


def test_a_dry_run_keeps_nothing_and_a_second_run_replaces_the_first(engine, supabase_copy):
    url, log = supabase_copy
    report = mig.import_all(engine, mig.PostgresSource(url), dry_run=True)
    assert by_source(report)[ANN]["days"] == len(log["entries"])
    with engine.connect() as c:
        assert c.execute(select(t.users)).first() is None and c.execute(select(t.invites)).first() is None
    first = mig.import_all(engine, mig.PostgresSource(url))
    second = mig.import_all(engine, mig.PostgresSource(url))
    with engine.begin() as c:
        assert c.execute(text("select count(*) from users")).scalar() == 2, "re-run: replaced, not doubled"
        assert by_source(second)[ANN]["user_id"] != by_source(first)[ANN]["user_id"]
        assert learning.load_log(c, by_source(second)[ANN]["user_id"]) == log
        c.execute(t.users.delete())
        c.execute(t.invites.delete())
        c.execute(t.audit_log.delete())


def test_the_current_apps_download_my_data_file_imports(engine, tmp_path, monkeypatch):
    from coach import storage
    monkeypatch.setenv("COACH_LOG_PATH", str(tmp_path / "log.json"))
    store = storage.FileStore(tmp_path / "log.json", tmp_path / "settings.json", scoped=True,
                              current_user=lambda: "personal-1")
    log = rich_log()
    store.replace(copy.deepcopy(log))
    store.save_settings(dict(settings.blank("personal-1"), subjects=["philosophy"], units_per_day=1,
                             subject_levels={"philosophy": "Beginner"}, onboarded_at="2026-10-01T00:00:00+00:00"))
    store.touch_user("me@example.com", "Me")
    store.add_usage("2026-11-02", 2, 500)
    path = tmp_path / "my-data.json"
    path.write_text(json.dumps(store.export_my_data(), default=str))
    report = mig.import_all(engine, mig.ExportSource([str(path)]))
    assert not report["failed"], report
    with engine.begin() as c:
        uid = report["imported"][0]["user_id"]
        assert learning.load_log(c, uid) == core.parse_log(log)
        assert accounts.load_settings(c, uid)["subjects"] == ["philosophy"]
        assert accounts.usage_on(c, uid, __import__("datetime").date(2026, 11, 2))["token_count"] == 500
        c.execute(t.users.delete())
        c.execute(t.audit_log.delete())
