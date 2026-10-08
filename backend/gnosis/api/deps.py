"""Who is calling, and may they (ADR 0004): every route declares what it
needs, and this is the only place that decides.

Until our own sign-in (step M3) the only caller is the current app's
server. It proves itself with a service token (Authorization: Bearer …,
compared in constant time) and names the person it has signed in
(X-Gnosis-Subject: their id from the old system; X-Gnosis-Email). The
person is found, or made on first sight, by that id. A suspended or deleted
account is refused. In M3 this is replaced by our own session cookie; the
routes don't change."""
import hmac
from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.engine import Connection

from gnosis.data import db
from gnosis.data.repositories import accounts
from gnosis.infra.config import settings


@dataclass
class Principal:
    user_id: str
    email: str = None
    roles: list = field(default_factory=list)
    permissions: set = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def connection():
    """One transaction per request: committed if the route finishes, rolled back if it raises."""
    with db.transaction() as conn:
        yield conn


def service(authorization: str = Header(default="")) -> None:
    """The caller is our own app server (a valid service token)."""
    tokens = [x.strip() for x in settings().service_tokens.get_secret_value().split(",") if x.strip()]
    given = authorization.removeprefix("Bearer ").strip()
    if not given or not any(hmac.compare_digest(given.encode(), t.encode()) for t in tokens):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthorized")


def principal(_: None = Depends(service), conn: Connection = Depends(connection),
              x_gnosis_subject: str = Header(default=""), x_gnosis_email: str = Header(default="")) -> Principal:
    subject = x_gnosis_subject.strip()
    if not subject or len(subject) > 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no one is signed in")
    uid = accounts.by_legacy_id(conn, subject)
    email = x_gnosis_email.strip().lower()[:320] or None
    if uid is None:
        if email and accounts.by_email(conn, email):
            raise HTTPException(status.HTTP_409_CONFLICT, "this email belongs to another account")
        uid = accounts.create_user(conn, email=email, legacy_id=subject)
        accounts.grant_role(conn, uid, "user")
        accounts.audit(conn, "user.created", actor=uid, target_type="user", target_id=uid, details={"via": "service"})
    user = accounts.user(conn, uid)
    if user["status"] != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this account isn't active")
    return Principal(user_id=uid, email=user["email"], roles=accounts.roles_of(conn, uid),
                     permissions=accounts.permissions_of(conn, uid))


def requires(permission: str):
    """A route that needs a permission (checked here, on the server, every time)."""
    def check(p: Principal = Depends(principal)) -> Principal:
        if not p.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not allowed")
        return p
    check.permission = permission
    return check
