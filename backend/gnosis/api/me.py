"""The learner's own data (v1). Every route acts for the signed-in person
only: the user id comes from the principal, never from the request."""
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from gnosis.api.deps import Principal, connection, principal
from gnosis.services import learner

router = APIRouter(prefix="/v1/me", tags=["me"])
DAY = r"^\d{4}-\d{2}-\d{2}$"
NAME = r"^[A-Za-z0-9_.-]{1,80}$"


def _valid(fn):
    try:
        return fn()
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None


class Seen(BaseModel):
    email: str = Field("", max_length=320)
    display_name: str = Field("", max_length=200)
    avatar_url: str = Field("", max_length=1000)


class UsageAdd(BaseModel):
    day: str = Field(pattern=DAY)
    requests: int = Field(ge=0, le=1000)
    tokens: int = Field(ge=0, le=10_000_000)


class Event(BaseModel):
    event: str = Field(pattern=NAME)


@router.get("")
def me(p: Principal = Depends(principal)) -> dict:
    return {"user_id": p.user_id, "email": p.email, "roles": p.roles, "permissions": sorted(p.permissions)}


@router.post("/seen", status_code=204)
def seen(body: Seen, p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> Response:
    learner.seen(conn, p.user_id, body.email, body.display_name, body.avatar_url)
    return Response(status_code=204)


@router.get("/record")
def record(p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> dict:
    return learner.record(conn, p.user_id)


@router.put("/record")
def replace_record(log: dict[str, Any] = Body(...), p: Principal = Depends(principal),
                   conn: Connection = Depends(connection)) -> dict:
    return _valid(lambda: learner.replace_record(conn, p.user_id, log))


@router.get("/days/{day}/{subject}")
def get_day(day: str, subject: str, p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> dict:
    _valid(lambda: __import__("datetime").date.fromisoformat(day))
    return {"entry": learner.day(conn, p.user_id, day, subject)}


@router.put("/days/{day}/{subject}", status_code=204)
def put_day(day: str, subject: str, entry: dict[str, Any] = Body(...), p: Principal = Depends(principal),
            conn: Connection = Depends(connection)) -> Response:
    _valid(lambda: learner.save_day(conn, p.user_id, day, subject, entry))
    return Response(status_code=204)


@router.put("/books/{book_id}", status_code=204)
def put_book(book_id: str, book: dict[str, Any] = Body(...), p: Principal = Depends(principal),
             conn: Connection = Depends(connection)) -> Response:
    _valid(lambda: learner.save_book(conn, p.user_id, book_id, book))
    return Response(status_code=204)


@router.put("/goals/{goal_id}", status_code=204)
def put_goal(goal_id: str, path: dict[str, Any] = Body(...), p: Principal = Depends(principal),
             conn: Connection = Depends(connection)) -> Response:
    _valid(lambda: learner.save_goal(conn, p.user_id, goal_id, path))
    return Response(status_code=204)


@router.get("/settings")
def get_settings(p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> dict:
    return {"settings": learner.settings_of(conn, p.user_id)}


@router.put("/settings", status_code=204)
def put_settings(row: dict[str, Any] = Body(...), p: Principal = Depends(principal),
                 conn: Connection = Depends(connection)) -> Response:
    _valid(lambda: learner.save_settings(conn, p.user_id, row))
    return Response(status_code=204)


@router.get("/preferences")
def get_prefs(p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> dict:
    return {"preferences": learner.prefs_of(conn, p.user_id)}


@router.put("/preferences", status_code=204)
def put_prefs(data: dict[str, Any] = Body(...), p: Principal = Depends(principal),
              conn: Connection = Depends(connection)) -> Response:
    learner.save_prefs(conn, p.user_id, data)
    return Response(status_code=204)


@router.get("/usage/{day}")
def get_usage(day: str, p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> dict:
    return _valid(lambda: learner.usage(conn, p.user_id, day))


@router.post("/usage", status_code=204)
def add_usage(body: UsageAdd, p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> Response:
    _valid(lambda: learner.add_usage(conn, p.user_id, body.day, body.requests, body.tokens))
    return Response(status_code=204)


@router.post("/events", status_code=204)
def add_event(body: Event, p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> Response:
    _valid(lambda: learner.count(conn, p.user_id, body.event))
    return Response(status_code=204)


@router.get("/export")
def export(p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> dict:
    return learner.export(conn, p.user_id)


@router.delete("", status_code=204)
def delete_me(p: Principal = Depends(principal), conn: Connection = Depends(connection)) -> Response:
    learner.delete_everything(conn, p.user_id)
    return Response(status_code=204)
