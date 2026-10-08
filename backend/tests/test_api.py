"""The learner and admin API (step M2), through HTTP as the current app will
call it: nobody gets in without the service token and a person; every route
but the health checks is closed by default; a person only ever reaches
their own data; admin routes need their permission and are audited; what is
saved comes back exactly; bad input is refused, not stored."""
import copy
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from coach import core, prefs, settings
from gnosis.data import schema as t
from test_learning_repository import rich_log

TOKEN = "test-service-token-0123456789abcdef"


@pytest.fixture
def api(database_url, monkeypatch, engine):
    monkeypatch.setenv("GNOSIS_SERVICE_TOKENS", f"old-token-xyz, {TOKEN}")
    from gnosis.infra.config import settings as cfg
    from gnosis.data import db
    cfg.cache_clear()
    db.engine.cache_clear()
    from gnosis.app import create_app
    yield TestClient(create_app(), raise_server_exceptions=False)
    with engine.begin() as c:                       # each test leaves the shared database clean
        for table in (t.users, t.invites, t.audit_log):
            c.execute(table.delete())
    cfg.cache_clear()
    db.engine.cache_clear()


def as_(subject, email=None, token=TOKEN):
    h = {"Authorization": f"Bearer {token}", "X-Gnosis-Subject": subject}
    if email:
        h["X-Gnosis-Email"] = email
    return h


ANN = as_("supa-ann", "Ann@Example.com")
BOB = as_("supa-bob", "bob@example.com")


def test_nobody_gets_in_without_the_service_token_and_a_person(api):
    assert api.get("/v1/me").status_code == 401
    assert api.get("/v1/me", headers=as_("x", token="wrong")).status_code == 401
    assert api.get("/v1/me", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 401, "no person named"
    assert api.get("/v1/me", headers=as_("supa-ann", token="old-token-xyz")).status_code == 200, "a rotated token works"
    assert api.get("/health").status_code == 200, "health checks stay open"


def test_every_route_is_closed_by_default(api):
    paths = api.get("/openapi.json").json()["paths"]
    open_ = []
    for path, methods in paths.items():
        url = re.sub(r"\{[^}]+\}", "2026-11-02", path)
        for method in methods:
            r = api.request(method.upper(), url, json={})
            if r.status_code != 401:
                open_.append(f"{method.upper()} {path} -> {r.status_code}")
    assert open_ == ["GET /health -> 200", "GET /ready -> 200"], open_


def test_a_person_is_made_on_first_sight_and_found_again(api, engine):
    me = api.get("/v1/me", headers=ANN).json()
    assert me["roles"] == ["user"] and me["email"] == "ann@example.com" and me["permissions"] == []
    assert api.get("/v1/me", headers=ANN).json()["user_id"] == me["user_id"]
    assert api.get("/v1/me", headers=as_("supa-ann-2", "ann@example.com")).status_code == 409, \
        "someone else can't take her email"
    with engine.connect() as c:
        assert c.execute(select(t.audit_log.c.action)).scalars().all() == ["user.created"]


def test_her_record_and_days_come_back_exactly_and_only_to_her(api):
    log = rich_log()
    r = api.put("/v1/me/record", headers=ANN, json=log)
    assert r.status_code == 200 and r.json()["days"] == len(core.parse_log(copy.deepcopy(log))["entries"])
    assert api.get("/v1/me/record", headers=ANN).json() == core.parse_log(copy.deepcopy(log))
    assert api.get("/v1/me/record", headers=BOB).json()["entries"] == [], "Bob sees only his own (nothing)"
    day = copy.deepcopy(core.parse_log(copy.deepcopy(log))["entries"][-2])
    day["reflection"] = "New thoughts."
    assert api.put(f"/v1/me/days/{day['date']}/{day['topic']}", headers=ANN, json=day).status_code == 204
    got = api.get(f"/v1/me/days/{day['date']}/{day['topic']}", headers=ANN).json()["entry"]
    assert got == day
    assert api.get("/v1/me/days/2001-01-01/philosophy", headers=ANN).json() == {"entry": None}
    assert api.put(f"/v1/me/days/2026-01-01/{day['topic']}", headers=ANN, json=day).status_code == 422, \
        "the address and the body must agree"
    assert api.get("/v1/me/days/notaday/philosophy", headers=ANN).status_code == 422
    assert api.put("/v1/me/record", headers=ANN, json={"nope": 1}).status_code == 422


def test_books_goals_settings_and_preferences(api):
    log = core.parse_log(rich_log())
    book, goal = log["books"][0], log["paths"][0]
    assert api.put(f"/v1/me/books/{book['id']}", headers=ANN, json=book).status_code == 204
    assert api.put(f"/v1/me/goals/{goal['id']}", headers=ANN, json=goal).status_code == 204
    assert api.put("/v1/me/goals/g-00000000", headers=ANN, json=goal).status_code == 422
    rec = api.get("/v1/me/record", headers=ANN).json()
    assert rec["books"] == [book] and rec["paths"] == [goal]
    assert api.get("/v1/me/settings", headers=ANN).json() == {"settings": None}
    row = dict(settings.blank("ignored"), subjects=["philosophy"], units_per_day=1,
               subject_levels={"philosophy": "Beginner"}, onboarded_at="2026-10-01T00:00:00+00:00")
    assert api.put("/v1/me/settings", headers=ANN, json=row).status_code == 204
    got = api.get("/v1/me/settings", headers=ANN).json()["settings"]
    assert got["subjects"] == ["philosophy"] and got["user_id"] != "ignored", "the id is hers, not what was sent"
    p = dict(prefs.blank(), reminder_on=True)
    assert api.put("/v1/me/preferences", headers=ANN, json=p).status_code == 204
    assert api.get("/v1/me/preferences", headers=ANN).json()["preferences"]["reminder_on"] is True


def test_usage_and_counts(api, engine):
    for _ in range(2):
        assert api.post("/v1/me/usage", headers=ANN, json={"day": "2026-11-02", "requests": 1, "tokens": 900}).status_code == 204
    assert api.get("/v1/me/usage/2026-11-02", headers=ANN).json() == {"request_count": 2, "token_count": 1800}
    assert api.post("/v1/me/usage", headers=ANN, json={"day": "2026-11-02", "requests": -1, "tokens": 0}).status_code == 422
    for _ in range(3):
        api.post("/v1/me/events", headers=ANN, json={"event": "visit"})
        api.post("/v1/me/events", headers=ANN, json={"event": "recovered"})
    assert api.post("/v1/me/events", headers=ANN, json={"event": "made_up"}).status_code == 422
    with engine.connect() as c:
        visits = c.execute(text("select sum(count) from usage_events where event = 'visit'")).scalar()
        recovered = c.execute(text("select sum(count) from learning_signals where event = 'recovered'")).scalar()
    assert visits == 1 and recovered == 3, "a visit once a day; signals add up"


def test_a_copy_of_everything_and_deleting_everything(api, engine):
    api.put("/v1/me/record", headers=ANN, json=rich_log())
    api.post("/v1/me/seen", headers=ANN, json={"email": "ann@example.com", "display_name": "Ann", "avatar_url": ""})
    copy_ = api.get("/v1/me/export", headers=ANN).json()
    assert {"user", "settings", "learning_entries", "reading_books", "learning_paths", "ai_usage", "usage_events",
            "learning_signals", "learner_prefs"} <= set(copy_), "the same keys the app's download has always had"
    assert copy_["user"]["display_name"] == "Ann" and len(copy_["learning_entries"]) > 3
    uid = copy_["user"]["user_id"]
    assert api.delete("/v1/me", headers=ANN).status_code == 204
    with engine.connect() as c:
        for table in (t.users, t.study_days, t.day_lessons, t.goals, t.reading_books):
            col = table.c.id if table is t.users else table.c.user_id
            assert c.execute(select(table).where(col == uid)).first() is None, table.name
        assert c.execute(select(t.audit_log.c.action).where(t.audit_log.c.target_id == uid)).scalar() == "user.deleted_self"
    assert api.get("/v1/me", headers=ANN).json()["user_id"] != uid, "signing in again is a fresh start"


def test_admin_routes_need_their_permission_and_are_audited(api, engine):
    assert api.get("/v1/admin/invites", headers=ANN).status_code == 403
    assert api.get("/v1/admin/metrics?since=2026-01-01", headers=ANN).status_code == 403
    uid = api.get("/v1/me", headers=ANN).json()["user_id"]
    with engine.begin() as c:
        c.execute(t.user_roles.insert().values(user_id=uid, role="admin"))
    assert api.post("/v1/admin/invites", headers=ANN, json={"email": "New@Example.com", "note": "hi"}).status_code == 204
    assert api.post("/v1/admin/invites", headers=ANN, json={"email": "not an email"}).status_code == 422
    assert api.get("/v1/admin/invites", headers=ANN).json() == [{"email": "new@example.com", "note": "hi"}]
    assert api.get("/v1/invites/new@example.com", headers={"Authorization": f"Bearer {TOKEN}"}).json() == {"invited": True}
    assert api.delete("/v1/admin/invites/new@example.com", headers=ANN).status_code == 204
    m = api.get("/v1/admin/metrics?since=2026-01-01", headers=ANN).json()
    assert m["signed_up"] >= 1 and "recovered" in m
    with engine.connect() as c:
        actions = c.execute(select(t.audit_log.c.action).where(t.audit_log.c.actor_user_id == uid)).scalars().all()
    assert actions.count("invite.add") == 1 and actions.count("invite.remove") == 1


def test_a_suspended_account_is_refused(api, engine):
    uid = api.get("/v1/me", headers=ANN).json()["user_id"]
    with engine.begin() as c:
        c.execute(t.users.update().where(t.users.c.id == uid).values(status="suspended"))
    assert api.get("/v1/me/record", headers=ANN).status_code == 403


def test_errors_never_leak_internals(api, monkeypatch):
    from gnosis.services import learner

    def boom(*a, **k):
        raise RuntimeError("secret detail: password=hunter2")
    monkeypatch.setattr(learner, "record", boom)
    r = api.get("/v1/me/record", headers=ANN)
    assert r.status_code == 500 and "hunter2" not in r.text and r.json()["error"] == "internal_error"
