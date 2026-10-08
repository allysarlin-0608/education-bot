"""The application: one FastAPI app, its routers, and its middleware (a
request id on every request and log line; timing; safe error responses)."""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gnosis import __version__
from gnosis.api import admin, health, me
from gnosis.infra import logging as logs
from gnosis.infra.config import settings

logger = logging.getLogger("gnosis.http")


def create_app() -> FastAPI:
    s = settings()
    logs.setup(s.log_level, s.log_json)
    app = FastAPI(title="GNOSIS API", version=__version__,
                  docs_url=None if s.is_production else "/docs", redoc_url=None)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex[:16]
        token = logs.request_id.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:                                   # noqa: BLE001
            logger.exception("unhandled error", extra={"route": request.url.path})
            response = JSONResponse({"error": "internal_error", "request_id": rid}, status_code=500)
        response.headers["x-request-id"] = rid
        logger.info("request", extra={"route": request.url.path, "status": response.status_code,
                                      "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
        logs.request_id.reset(token)
        return response

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(admin.router)
    return app


app = create_app()
