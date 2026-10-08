"""People and what belongs to their account (ADR 0002, 0004): users, sign-in
identities, password credentials, roles and permissions, invites, setup
settings, preferences, and the usage counts. Shapes match what the domain
(`coach.settings`, `coach.prefs`) reads, so the current app can use them."""
from datetime import date

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from coach import prefs as prefs_
from coach import settings as settings_
from gnosis.data import schema as t


# ------------------------------------------------------------------ users
def create_user(conn: Connection, *, email: str = None, legacy_id: str = None, display_name: str = "",
                avatar_url: str = "", created_at=None, last_seen_at=None) -> str:
    values = {"email": email.lower() if email else None, "legacy_id": legacy_id, "display_name": display_name or "",
              "avatar_url": avatar_url or "", "last_seen_at": last_seen_at}
    if created_at is not None:
        values["created_at"] = created_at
    return conn.execute(insert(t.users).values(**values).returning(t.users.c.id)).scalar_one()


def user(conn: Connection, user_id: str):
    return conn.execute(select(t.users).where(t.users.c.id == user_id)).mappings().first()


def by_legacy_id(conn: Connection, legacy_id: str):
    return conn.execute(select(t.users.c.id).where(t.users.c.legacy_id == legacy_id)).scalar()


def by_email(conn: Connection, email: str):
    return conn.execute(select(t.users.c.id).where(t.users.c.email == email.lower())).scalar()


def set_status(conn: Connection, user_id: str, status: str) -> None:
    conn.execute(update(t.users).where(t.users.c.id == user_id).values(status=status, updated_at=func.now()))


def add_identity(conn: Connection, user_id: str, provider: str, subject: str, email: str = None) -> None:
    conn.execute(pg_insert(t.identities).values(user_id=user_id, provider=provider, subject=subject, email=email)
                 .on_conflict_do_nothing(index_elements=["provider", "subject"]))


def identities(conn: Connection, user_id: str) -> list:
    return [dict(r) for r in conn.execute(select(t.identities.c.provider, t.identities.c.subject, t.identities.c.email)
                                          .where(t.identities.c.user_id == user_id)
                                          .order_by(t.identities.c.provider)).mappings()]


def set_credential(conn: Connection, user_id: str, password_hash: str, algorithm: str) -> None:
    conn.execute(pg_insert(t.credentials).values(user_id=user_id, password_hash=password_hash, algorithm=algorithm)
                 .on_conflict_do_update(index_elements=["user_id"],
                                        set_={"password_hash": password_hash, "algorithm": algorithm,
                                              "updated_at": func.now()}))


def credential(conn: Connection, user_id: str):
    return conn.execute(select(t.credentials).where(t.credentials.c.user_id == user_id)).mappings().first()


# ------------------------------------------------------------------ roles
def grant_role(conn: Connection, user_id: str, role: str) -> None:
    conn.execute(pg_insert(t.user_roles).values(user_id=user_id, role=role).on_conflict_do_nothing())


def revoke_role(conn: Connection, user_id: str, role: str) -> None:
    conn.execute(delete(t.user_roles).where(t.user_roles.c.user_id == user_id, t.user_roles.c.role == role))


def roles_of(conn: Connection, user_id: str) -> list:
    return sorted(conn.execute(select(t.user_roles.c.role).where(t.user_roles.c.user_id == user_id)).scalars())


def permissions_of(conn: Connection, user_id: str) -> set:
    q = (select(t.role_permissions.c.permission)
         .join(t.user_roles, t.user_roles.c.role == t.role_permissions.c.role)
         .where(t.user_roles.c.user_id == user_id))
    return set(conn.execute(q).scalars())


# ------------------------------------------------------------------ invites
def add_invite(conn: Connection, email: str, note: str = "", invited_by: str = None) -> None:
    conn.execute(pg_insert(t.invites).values(email=email.lower(), note=note, invited_by=invited_by)
                 .on_conflict_do_update(index_elements=["email"], set_={"note": note}))


def is_invited(conn: Connection, email: str) -> bool:
    return conn.execute(select(t.invites.c.email).where(t.invites.c.email == email.lower())).first() is not None


def invites(conn: Connection) -> list:
    return [dict(r) for r in conn.execute(select(t.invites.c.email, t.invites.c.note)
                                          .order_by(t.invites.c.email)).mappings()]


# ------------------------------------------------------------------ settings
def save_settings(conn: Connection, user_id: str, row: dict) -> None:
    """Her setup, as `coach.settings` shapes it (subjects in turn order, levels, pace…)."""
    s = settings_.normalize(row, user_id)
    for table in (t.user_settings, t.user_subjects, t.subject_levels):
        conn.execute(delete(table).where(table.c.user_id == user_id))
    conn.execute(insert(t.user_settings).values(user_id=user_id, units_per_day=s["units_per_day"],
                                                reading_enabled=s["reading_enabled"], onboarding=s["onboarding"],
                                                onboarded_at=s["onboarded_at"], updated_at=s["updated_at"]))
    if s["subjects"]:
        conn.execute(insert(t.user_subjects), [{"user_id": user_id, "subject": x, "position": k}
                                               for k, x in enumerate(s["subjects"])])
    if s["subject_levels"]:
        conn.execute(insert(t.subject_levels), [{"user_id": user_id, "subject": k, "level": v}
                                                for k, v in s["subject_levels"].items()])


def load_settings(conn: Connection, user_id: str):
    """Her settings row (the shape `coach.settings.normalize` takes), or None."""
    r = conn.execute(select(t.user_settings).where(t.user_settings.c.user_id == user_id)).mappings().first()
    if r is None:
        return None
    subjects = conn.execute(select(t.user_subjects.c.subject).where(t.user_subjects.c.user_id == user_id)
                            .order_by(t.user_subjects.c.position)).scalars().all()
    levels = dict(conn.execute(select(t.subject_levels.c.subject, t.subject_levels.c.level)
                               .where(t.subject_levels.c.user_id == user_id)).all())
    return {"user_id": user_id, "subjects": list(subjects), "units_per_day": r["units_per_day"],
            "subject_levels": levels, "reading_enabled": r["reading_enabled"], "onboarding": r["onboarding"],
            "onboarded_at": r["onboarded_at"], "updated_at": r["updated_at"]}


def save_prefs(conn: Connection, user_id: str, data: dict) -> None:
    data = prefs_.normalize(data)
    conn.execute(pg_insert(t.preferences).values(user_id=user_id, data=data)
                 .on_conflict_do_update(index_elements=["user_id"], set_={"data": data, "updated_at": func.now()}))


def load_prefs(conn: Connection, user_id: str):
    return conn.execute(select(t.preferences.c.data).where(t.preferences.c.user_id == user_id)).scalar()


# ------------------------------------------------------------------ counts
def add_usage(conn: Connection, user_id: str, day: date, requests_: int, tokens_: int) -> None:
    conn.execute(pg_insert(t.ai_usage).values(user_id=user_id, day=day, request_count=max(requests_, 0),
                                              token_count=max(tokens_, 0))
                 .on_conflict_do_update(index_elements=["user_id", "day"],
                                        set_={"request_count": t.ai_usage.c.request_count + max(requests_, 0),
                                              "token_count": t.ai_usage.c.token_count + max(tokens_, 0)}))


def usage_on(conn: Connection, user_id: str, day: date) -> dict:
    r = conn.execute(select(t.ai_usage).where(t.ai_usage.c.user_id == user_id, t.ai_usage.c.day == day)).mappings().first()
    return {"request_count": r["request_count"] if r else 0, "token_count": r["token_count"] if r else 0}


def add_count(conn: Connection, user_id: str, day: date, event: str, by: int = 1, table=None,
              once_a_day: bool = False) -> None:
    """One usage event or learning signal (counts only: no content). A
    "once a day" event (a visit) stays at one."""
    table = table if table is not None else t.usage_events
    stmt = pg_insert(table).values(user_id=user_id, day=day, event=event, count=by)
    conn.execute(stmt.on_conflict_do_update(
        index_elements=["user_id", "day", "event"],
        set_={"count": table.c.count if once_a_day else table.c.count + by}))


def counts_of(conn: Connection, user_id: str, table) -> list:
    return [{"day": r["day"].isoformat(), "event": r["event"], "count": r["count"]}
            for r in conn.execute(select(table).where(table.c.user_id == user_id)
                                  .order_by(table.c.day, table.c.event)).mappings()]


# ------------------------------------------------------------------ audit
def audit(conn: Connection, action: str, *, actor: str = None, target_type: str = None, target_id: str = None,
          ip: str = None, details: dict = None) -> None:
    """An append-only record of something done (admin and security actions)."""
    conn.execute(insert(t.audit_log).values(actor_user_id=actor, action=action, target_type=target_type,
                                            target_id=target_id, ip=ip, details=details or {}))
