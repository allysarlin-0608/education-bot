"""Structured logs: one JSON object per line (time, level, logger, message,
request id), ready for any log collector. No secret, token, password or
lesson text is ever logged; personal data is limited to internal ids."""
import contextvars
import json
import logging
import sys
import time

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"t": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
               "level": record.levelname, "logger": record.name, "msg": record.getMessage(),
               "request_id": request_id.get()}
        for key in ("route", "status", "duration_ms", "user_id", "event"):
            if hasattr(record, key):
                out[key] = getattr(record, key)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def setup(level: str = "INFO", as_json: bool = True) -> None:
    root = logging.getLogger("gnosis")
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter() if as_json else logging.Formatter("%(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    root.propagate = False
