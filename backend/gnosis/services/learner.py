"""What a learner's own data allows (one person, always the caller): her
record, a day, a book, a goal, her settings and preferences, her usage and
counts, a copy of everything, deleting everything. Validation is the
domain's (`coach`); storage is the repositories'."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.engine import Connection

from coach import metrics
from gnosis.data import schema as t
from gnosis.data.repositories import accounts, learning
from gnosis.infra.config import settings

COUNTED = set(metrics.EVENTS) | set(metrics.SIGNALS)


def server_today() -> date:
    """The server's date for counts (never one a client sends)."""
    return datetime.now(ZoneInfo(settings().timezone)).date()


def record(conn: Connection, uid: str) -> dict:
    return learning.load_log(conn, uid)


def replace_record(conn: Connection, uid: str, log: dict) -> dict:
    return learning.save_log(conn, uid, log)


def day(conn: Connection, uid: str, day_: str, subject: str):
    return learning.load_entry(conn, uid, day_, subject)


def save_day(conn: Connection, uid: str, day_: str, subject: str, entry: dict) -> None:
    if entry.get("date") != day_ or entry.get("topic") != subject:
        raise ValueError("the day in the address and in the body differ")
    learning.save_entry(conn, uid, entry)


def save_book(conn: Connection, uid: str, book_id: str, book: dict) -> None:
    if book.get("id") != book_id:
        raise ValueError("the book in the address and in the body differ")
    learning.save_book(conn, uid, book)


def save_goal(conn: Connection, uid: str, goal_id: str, path: dict) -> None:
    if path.get("id") != goal_id:
        raise ValueError("the goal in the address and in the body differ")
    learning.save_goal(conn, uid, path)


def settings_of(conn: Connection, uid: str):
    return accounts.load_settings(conn, uid)


def save_settings(conn: Connection, uid: str, row: dict) -> None:
    accounts.save_settings(conn, uid, dict(row, user_id=uid))


def prefs_of(conn: Connection, uid: str):
    return accounts.load_prefs(conn, uid)


def save_prefs(conn: Connection, uid: str, data: dict) -> None:
    accounts.save_prefs(conn, uid, data)


def seen(conn: Connection, uid: str, email: str, name: str, picture: str) -> None:
    """She signed in: her name and picture as the sign-in gave them, and when."""
    from sqlalchemy import func, update
    values = {"display_name": (name or "")[:200], "avatar_url": (picture or "")[:1000], "last_seen_at": func.now()}
    if email and accounts.by_email(conn, email) in (None, uid):
        values["email"] = email.lower()
    conn.execute(update(t.users).where(t.users.c.id == uid).values(**values))


def usage(conn: Connection, uid: str, day_: str) -> dict:
    return accounts.usage_on(conn, uid, date.fromisoformat(day_))


def add_usage(conn: Connection, uid: str, day_: str, requests_: int, tokens_: int) -> None:
    accounts.add_usage(conn, uid, date.fromisoformat(day_), requests_, tokens_)


def count(conn: Connection, uid: str, event: str) -> None:
    """One usage event or learning signal, on the server's date (counts only)."""
    if event not in COUNTED:
        raise ValueError("not an event we count")
    table = t.learning_signals if event in metrics.SIGNALS else t.usage_events
    accounts.add_count(conn, uid, server_today(), event, table=table, once_a_day=event == "visit")


def export(conn: Connection, uid: str) -> dict:
    """A copy of everything of hers, in the shape the app's "Download my data" has always had."""
    u = accounts.user(conn, uid)
    log = learning.load_log(conn, uid)
    usage_rows = conn.execute(t.ai_usage.select().where(t.ai_usage.c.user_id == uid)
                              .order_by(t.ai_usage.c.day)).mappings().all()
    return {"user": {"user_id": uid, "email": u["email"], "display_name": u["display_name"],
                     "avatar_url": u["avatar_url"], "created_at": u["created_at"].isoformat(),
                     "last_seen_at": u["last_seen_at"].isoformat() if u["last_seen_at"] else None},
            "settings": accounts.load_settings(conn, uid), "learning_entries": log["entries"],
            "reading_books": log["books"], "learning_paths": log["paths"],
            "ai_usage": [{"date": r["day"].isoformat(), "request_count": r["request_count"],
                          "token_count": r["token_count"]} for r in usage_rows],
            "usage_events": accounts.counts_of(conn, uid, t.usage_events),
            "learning_signals": accounts.counts_of(conn, uid, t.learning_signals),
            "learner_prefs": accounts.load_prefs(conn, uid),
            "identities": accounts.identities(conn, uid), "roles": accounts.roles_of(conn, uid)}


def delete_everything(conn: Connection, uid: str) -> None:
    """Her account and everything of hers, in one transaction (the audit
    entry keeps only her internal id and that it happened)."""
    accounts.audit(conn, "user.deleted_self", actor=None, target_type="user", target_id=uid)
    conn.execute(t.users.delete().where(t.users.c.id == uid))
