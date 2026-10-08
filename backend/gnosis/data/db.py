"""The database connection: one engine per process, connections borrowed
per unit of work, every write inside a transaction."""
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from gnosis.infra.config import settings


@lru_cache
def engine() -> Engine:
    s = settings()
    return create_engine(s.database_url.get_secret_value(), pool_size=s.db_pool_size, pool_pre_ping=True,
                         connect_args={"connect_timeout": int(s.db_timeout_seconds)})


@contextmanager
def transaction(eng: Engine = None) -> Connection:
    """A unit of work: committed if the block finishes, rolled back if it raises."""
    with (eng or engine()).begin() as conn:
        yield conn


def ping(eng: Engine = None) -> bool:
    try:
        with (eng or engine()).connect() as conn:
            return conn.execute(text("select 1")).scalar() == 1
    except Exception:          # noqa: BLE001  (readiness: any failure means not ready)
        return False
