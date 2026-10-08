"""Backend tests run against a real PostgreSQL (never a mock): a fresh
database is created for the session and migrated with Alembic, exactly as
staging and production are. Each test runs in a transaction that is rolled
back, so tests never see each other's rows.

GNOSIS_TEST_DATABASE_ADMIN_URL: a server the tests may create databases on
(default: the local test server, postgresql://gnosis@127.0.0.1:5544/postgres)."""
import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND.parent), str(BACKEND.parent / "tests")]

ADMIN_URL = os.environ.get("GNOSIS_TEST_DATABASE_ADMIN_URL", "postgresql+psycopg://gnosis@127.0.0.1:5544/postgres")


def _url(name: str) -> str:
    return ADMIN_URL.rsplit("/", 1)[0] + "/" + name


@pytest.fixture(scope="session")
def database_url():
    name = f"gnosis_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'create database "{name}"'))
    url = _url(name)
    os.environ["GNOSIS_DATABASE_URL"] = url
    from gnosis.infra.config import settings
    settings.cache_clear()
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")
    yield url
    from gnosis.data import db
    if db.engine.cache_info().currsize:
        db.engine().dispose()
    db.engine.cache_clear()
    with admin.connect() as c:
        c.execute(text(f'drop database "{name}" with (force)'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine(database_url):
    eng = create_engine(database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def conn(engine):
    """A connection inside a transaction that is rolled back after the test."""
    with engine.connect() as c:
        tx = c.begin()
        yield c
        tx.rollback()


@pytest.fixture
def alembic_config(database_url):
    from alembic.config import Config
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["url"] = database_url
    return cfg
