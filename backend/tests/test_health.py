"""The process is up (/health) and can reach its database (/ready); every
response carries a request id; an error never leaks internals."""
from fastapi.testclient import TestClient


def client():
    from gnosis.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def test_health_and_ready(database_url):
    c = client()
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.headers["x-request-id"]
    r = c.get("/ready", headers={"x-request-id": "abc123"})
    assert r.status_code == 200 and r.json() == {"status": "ready", "database": True}
    assert r.headers["x-request-id"] == "abc123", "a caller's request id is kept (traces across services)"


def test_not_ready_without_a_database(monkeypatch, database_url):
    from gnosis.data import db
    from gnosis.infra.config import settings
    monkeypatch.setenv("GNOSIS_DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:1/none")
    settings.cache_clear()
    db.engine.cache_clear()
    try:
        r = client().get("/ready")
        assert r.status_code == 503 and r.json()["database"] is False
    finally:
        monkeypatch.setenv("GNOSIS_DATABASE_URL", database_url)
        settings.cache_clear()
        db.engine.cache_clear()
