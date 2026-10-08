"""Administration (v1): each route names the permission it needs; the
check is on the server (gnosis/api/deps.py), and every change is audited."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from gnosis.api.deps import Principal, connection, requires, service
from gnosis.data.repositories import accounts
from gnosis.services import insights, learner

router = APIRouter(prefix="/v1", tags=["admin"])
EMAIL = r"^[^@\s]{1,200}@[^@\s]{1,200}$"


class Invite(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=320)
    note: str = Field("", max_length=200)


@router.get("/invites/{email}")
def invited(email: str, _: None = Depends(service), conn: Connection = Depends(connection)) -> dict:
    """At sign-in, before anyone is known: may this email come in? (our server only)"""
    return {"invited": accounts.is_invited(conn, email)}


@router.get("/people/{subject}/roles")
def roles_of(subject: str, _: None = Depends(service), conn: Connection = Depends(connection)) -> dict:
    """At sign-in: the roles of someone known by their old-system id (nobody is made by asking)."""
    uid = accounts.by_legacy_id(conn, subject)
    return {"roles": accounts.roles_of(conn, uid) if uid else []}


@router.get("/admin/invites")
def list_invites(p: Principal = Depends(requires("invites.manage")), conn: Connection = Depends(connection)) -> list:
    return accounts.invites(conn)


@router.post("/admin/invites", status_code=204)
def add_invite(body: Invite, p: Principal = Depends(requires("invites.manage")),
               conn: Connection = Depends(connection)) -> Response:
    accounts.add_invite(conn, body.email, body.note, invited_by=p.user_id)
    accounts.audit(conn, "invite.add", actor=p.user_id, target_type="invite", target_id=body.email.lower())
    return Response(status_code=204)


@router.delete("/admin/invites/{email}", status_code=204)
def remove_invite(email: str, p: Principal = Depends(requires("invites.manage")),
                  conn: Connection = Depends(connection)) -> Response:
    accounts.remove_invite(conn, email)
    accounts.audit(conn, "invite.remove", actor=p.user_id, target_type="invite", target_id=email.lower())
    return Response(status_code=204)


@router.get("/admin/metrics")
def metrics(since: str, p: Principal = Depends(requires("insights.read")),
            conn: Connection = Depends(connection)) -> dict:
    try:
        start = date.fromisoformat(since)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "since must be a date") from None
    return insights.summary(conn, start, learner.server_today())
