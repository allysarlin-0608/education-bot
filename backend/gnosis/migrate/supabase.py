"""Moving every account out of Supabase into our database (step M1-M3 of
docs/ARCHITECTURE_ASSESSMENT.md), checked.

Two sources give the same per-person bundle:
- `PostgresSource`: Supabase's own Postgres, read directly (Dashboard →
  Project Settings → Database → connection string). Includes sign-in
  identities and password hashes (bcrypt, from auth.users), so nobody has
  to reset a password after the switch.
- `ExportSource`: the files people downloaded with "Download my data"
  (no password: they sign in with Google, or set a password once).

`import_all` writes each person in their own transaction, reads it back and
compares it with the source (days, lessons, quizzes, cards, evidence,
messages, books, goals, usage). A person whose copy doesn't match is rolled
back and reported; running it again replaces what an earlier run wrote
(people are matched by their Supabase id). `dry_run` does everything and
keeps nothing.

    python -m gnosis.migrate.supabase --source "postgresql://…supabase…" [--dry-run]
    python -m gnosis.migrate.supabase --export my-data.json [--dry-run]

The target is GNOSIS_DATABASE_URL. Nothing is ever written to the source."""
import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from coach import core, settings as settings_
from gnosis.data import schema as t
from gnosis.data.repositories import accounts, learning

logger = logging.getLogger("gnosis.migrate")
ENTRY_COLUMNS = core.ENTRY_FIELDS


@dataclass
class Person:
    legacy_id: str
    email: str = None
    display_name: str = ""
    avatar_url: str = ""
    created_at: datetime = None
    last_seen_at: datetime = None
    password_hash: str = None
    identities: list = field(default_factory=list)        # [(provider, subject, email)]
    settings: dict = None
    log: dict = field(default_factory=lambda: {"entries": [], "books": [], "paths": []})
    prefs: dict = None
    ai_usage: list = field(default_factory=list)           # [{"date", "request_count", "token_count"}]
    usage_events: list = field(default_factory=list)       # [{"day", "event", "count"}]
    learning_signals: list = field(default_factory=list)
    admin: bool = False


def _iso(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


# ------------------------------------------------------------------ sources
class PostgresSource:
    """Supabase's database, read-only (one read-only transaction)."""

    def __init__(self, url: str):
        self.engine = create_engine(url)

    def _rows(self, c, sql, missing_ok=True) -> list:
        try:
            with c.begin_nested():
                return [dict(r) for r in c.execute(text(sql)).mappings()]
        except Exception as e:                           # noqa: BLE001  (a table made by a later SQL file may be missing)
            if not missing_ok:
                raise
            logger.warning("source query skipped (%s): %s", sql.split()[3] if len(sql.split()) > 3 else sql, e)
            return []

    def people(self) -> tuple:
        """(people, invites): everything there is, by person."""
        with self.engine.connect() as c:
            c.execute(text("set transaction read only"))
            auth_users = {str(r["id"]): r for r in self._rows(
                c, "select id, email, encrypted_password, raw_user_meta_data, created_at, last_sign_in_at from auth.users")}
            idents = self._rows(c, "select user_id, provider, provider_id, identity_data from auth.identities")
            app_users = {r["user_id"]: r for r in self._rows(c, "select * from public.users")}
            admins = {r["email"].lower() for r in self._rows(c, "select email from public.app_admins")}
            invites = [{"email": r["email"], "note": r.get("note") or ""}
                       for r in self._rows(c, "select email, note from public.allowed_users")]
            ids = sorted(set(auth_users) | set(app_users))
            people = {i: Person(legacy_id=i) for i in ids}
            for i, p in people.items():
                a, u = auth_users.get(i) or {}, app_users.get(i) or {}
                meta = a.get("raw_user_meta_data") or {}
                p.email = (u.get("email") or a.get("email") or None)
                p.email = p.email.lower() if p.email else None
                p.display_name = u.get("display_name") or meta.get("full_name") or meta.get("name") or ""
                p.avatar_url = u.get("avatar_url") or meta.get("avatar_url") or meta.get("picture") or ""
                p.created_at = u.get("created_at") or a.get("created_at")
                p.last_seen_at = u.get("last_seen_at") or a.get("last_sign_in_at")
                p.password_hash = a.get("encrypted_password") or None
                p.admin = bool(p.email and p.email in admins)
            for r in idents:
                p = people.get(str(r["user_id"]))
                if p is not None:
                    data = r.get("identity_data") or {}
                    p.identities.append((r["provider"], str(r.get("provider_id") or data.get("sub") or ""),
                                         (data.get("email") or "").lower() or None))
            for r in self._rows(c, "select * from public.user_settings"):
                if r["user_id"] in people:
                    people[r["user_id"]].settings = {k: _iso(r.get(k)) for k in settings_.FIELDS}
            for r in self._rows(c, "select * from public.learning_entries order by date, topic"):
                p = people.get(r.get("user_id"))
                if p is None:
                    logger.warning("a learning entry with no known person (%s %s) is left out", r.get("date"), r.get("topic"))
                    continue
                p.log["entries"].append({k: _iso(r.get(k)) for k in ENTRY_COLUMNS})
            for r in self._rows(c, "select user_id, data from public.reading_books order by updated_at"):
                if r.get("user_id") in people:
                    people[r["user_id"]].log["books"].append(r["data"])
            for r in self._rows(c, "select user_id, data from public.learning_paths order by updated_at"):
                if r.get("user_id") in people:
                    people[r["user_id"]].log["paths"].append(r["data"])
            for r in self._rows(c, "select user_id, data from public.learner_prefs"):
                if r.get("user_id") in people:
                    people[r["user_id"]].prefs = r["data"]
            for r in self._rows(c, "select * from public.ai_usage"):
                if r.get("user_id") in people:
                    people[r["user_id"]].ai_usage.append({"date": _iso(r["date"]), "request_count": r["request_count"],
                                                          "token_count": r["token_count"]})
            for table, attr in (("usage_events", "usage_events"), ("learning_signals", "learning_signals")):
                for r in self._rows(c, f"select * from public.{table}"):
                    if r.get("user_id") in people:
                        getattr(people[r["user_id"]], attr).append(
                            {"day": _iso(r["day"]), "event": r["event"], "count": r["count"]})
        # if two sign-in accounts share an email, the one the app knows (its users row, its learning) goes
        # first and keeps it; the other is reported, never merged silently
        ordered = sorted(people.values(), key=lambda p: (p.legacy_id not in app_users, not p.log["entries"],
                                                         str(p.created_at or ""), p.legacy_id))
        return ordered, invites


class ExportSource:
    """Files from "Download my data" (coach/storage.py export_my_data)."""

    def __init__(self, paths: list):
        self.paths = paths

    def people(self) -> tuple:
        out = []
        for path in self.paths:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            user = d.get("user") or {}
            p = Person(legacy_id=str(user.get("user_id") or (d.get("settings") or {}).get("user_id") or path),
                       email=(user.get("email") or "").lower() or None, display_name=user.get("display_name") or "",
                       avatar_url=user.get("avatar_url") or "", created_at=user.get("created_at"),
                       last_seen_at=user.get("last_seen_at"))
            p.settings = d.get("settings")
            p.log = {"entries": d.get("learning_entries") or [], "books": d.get("reading_books") or [],
                     "paths": d.get("learning_paths") or []}
            p.prefs = d.get("learner_prefs")
            p.ai_usage = [{"date": r["date"], "request_count": r["request_count"], "token_count": r["token_count"]}
                          for r in d.get("ai_usage") or []]
            p.usage_events = [{"day": r["day"], "event": r["event"], "count": r["count"]} for r in d.get("usage_events") or []]
            p.learning_signals = [{"day": r["day"], "event": r["event"], "count": r["count"]}
                                  for r in d.get("learning_signals") or []]
            if p.email:
                p.identities.append(("email", p.email, p.email))
            out.append(p)
        return out, []


# ------------------------------------------------------------------ writing
def _expected(p: Person) -> dict:
    found = learning.counts(core.parse_log(p.log))
    found["ai_requests"] = sum(int(r["request_count"]) for r in p.ai_usage)
    found["events"] = sum(int(r["count"]) for r in p.usage_events) + sum(int(r["count"]) for r in p.learning_signals)
    return found


def _actual(conn: Connection, uid: str) -> dict:
    found = learning.counts(learning.load_log(conn, uid))
    found["ai_requests"] = conn.execute(text("select coalesce(sum(request_count), 0) from ai_usage where user_id = :u"),
                                        {"u": uid}).scalar()
    found["events"] = sum(r["count"] for tb in (t.usage_events, t.learning_signals) for r in accounts.counts_of(conn, uid, tb))
    return found


class Mismatch(Exception):
    pass


def write_person(conn: Connection, p: Person) -> dict:
    """One person, written and checked inside the caller's transaction."""
    old = accounts.by_legacy_id(conn, p.legacy_id)
    if old is not None:                                  # an earlier run: replaced whole
        conn.execute(t.users.delete().where(t.users.c.id == old))
    if p.email and accounts.by_email(conn, p.email):
        raise Mismatch("another account already has this email")
    uid = accounts.create_user(conn, email=p.email, legacy_id=p.legacy_id, display_name=p.display_name,
                               avatar_url=p.avatar_url, created_at=p.created_at, last_seen_at=p.last_seen_at)
    for provider, subject, email in p.identities:
        if subject:
            accounts.add_identity(conn, uid, provider, subject, email)
    if p.password_hash and p.password_hash.startswith("$2"):
        accounts.set_credential(conn, uid, p.password_hash, "bcrypt")
    accounts.grant_role(conn, uid, "user")
    if p.admin:
        accounts.grant_role(conn, uid, "admin")
    if p.settings:
        accounts.save_settings(conn, uid, dict(p.settings, user_id=uid))
    if p.prefs is not None:
        accounts.save_prefs(conn, uid, p.prefs)
    learning.save_log(conn, uid, p.log)
    for r in p.ai_usage:
        accounts.add_usage(conn, uid, date.fromisoformat(str(r["date"])), int(r["request_count"]), int(r["token_count"]))
    for rows, table in ((p.usage_events, t.usage_events), (p.learning_signals, t.learning_signals)):
        for r in rows:
            accounts.add_count(conn, uid, date.fromisoformat(str(r["day"])), r["event"], by=int(r["count"]), table=table)
    want, got = _expected(p), _actual(conn, uid)
    if want != got:
        raise Mismatch(f"the copy doesn't match the source: expected {want}, found {got}")
    return {"user_id": uid, **got}


def import_all(engine, source, dry_run: bool = False) -> dict:
    """Every person from `source` into the database `engine` points at.
    Returns {"imported": [...], "failed": [...], "invites": n}."""
    people, invites = source.people()
    report = {"imported": [], "failed": [], "invites": 0, "dry_run": dry_run}
    for p in people:
        conn = engine.connect()
        tx = conn.begin()
        try:
            result = write_person(conn, p)
            accounts.audit(conn, "migrate.import_person", target_type="user", target_id=result["user_id"],
                           details={"source_id": p.legacy_id, "counts": {k: v for k, v in result.items() if k != "user_id"}})
            (tx.rollback if dry_run else tx.commit)()
            report["imported"].append({"source_id": p.legacy_id, **result})      # (ids only: no email in reports)
        except Exception as e:                           # noqa: BLE001  (one person's failure never stops the others)
            tx.rollback()
            logger.error("import of %s failed: %s", p.legacy_id, e)
            report["failed"].append({"source_id": p.legacy_id, "error": str(e)})
        finally:
            conn.close()
    with engine.connect() as conn:
        tx = conn.begin()
        for inv in invites:
            accounts.add_invite(conn, inv["email"], inv["note"])
        (tx.rollback if dry_run else tx.commit)()
        report["invites"] = len(invites)
    return report


def main(argv=None) -> int:
    from gnosis.data import db
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--source", help="Supabase's Postgres connection URL (read only)")
    src.add_argument("--export", nargs="+", help='"Download my data" files')
    ap.add_argument("--dry-run", action="store_true", help="check everything, keep nothing")
    a = ap.parse_args(argv)
    source = PostgresSource(a.source) if a.source else ExportSource(a.export)
    report = import_all(db.engine(), source, dry_run=a.dry_run)
    print(json.dumps(report, indent=1, default=str, ensure_ascii=False))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
