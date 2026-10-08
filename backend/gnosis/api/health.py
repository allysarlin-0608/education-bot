"""Health checks for the reverse proxy, the orchestrator and monitoring:
/health (the process is up) and /ready (it can reach its database)."""
from fastapi import APIRouter, Response

from gnosis import __version__
from gnosis.data import db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/ready")
def ready(response: Response) -> dict:
    ok = db.ping()
    if not ok:
        response.status_code = 503
    return {"status": "ready" if ok else "unavailable", "database": ok}
